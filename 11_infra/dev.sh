#!/usr/bin/env bash
# =============================================================================
# dev.sh — local fast-iteration runner for tennetctl
#
# What it does:
#   1. Ensures docker compose infra (postgres, valkey, minio, nats) is up.
#   2. Starts the FastAPI backend as a host process via uvicorn (auto-reload).
#   3. Starts the Next.js frontend as a host process via `next dev`.
#   4. Tees both stdout/stderr into 08_logs/{backend,frontend}.log.
#   5. Each invocation wipes 08_logs/ first so logs are session-scoped.
#
# Why not docker for backend/frontend?
#   Avoids a full image rebuild on every code change. The Dockerfiles are
#   still the source of truth for production builds; this script is the
#   inner-loop dev experience only.
#
# Usage (run from anywhere — the script resolves repo root from its own path):
#   11_infra/dev.sh start         # default — start everything
#   11_infra/dev.sh stop          # stop backend + frontend (leaves infra running)
#   11_infra/dev.sh restart       # stop then start
#   11_infra/dev.sh down          # stop everything including docker infra
#   11_infra/dev.sh logs backend  # tail backend log
#   11_infra/dev.sh logs frontend # tail frontend log
#   11_infra/dev.sh status        # show what's running
#
# Ports (deliberately high to avoid host conflicts):
#   postgres  → 55432
#   backend   → 58000
#   frontend  → 53000
# =============================================================================

set -euo pipefail

INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${INFRA_DIR}/.." && pwd)"
LOG_DIR="${ROOT_DIR}/08_logs"
PID_DIR="${LOG_DIR}/.pids"

BACKEND_LOG="${LOG_DIR}/backend.log"
FRONTEND_LOG="${LOG_DIR}/frontend.log"
BACKEND_PID="${PID_DIR}/backend.pid"
FRONTEND_PID="${PID_DIR}/frontend.pid"

BACKEND_PORT=58000
FRONTEND_PORT=53000
POSTGRES_PORT=55432

# Write-role DSN. Resolution order:
#   1. $DATABASE_URL from the caller's environment (set this after running the setup wizard)
#   2. 08_logs/.dev.env file   (auto-written by dev.sh when you pass --set-dsn, see below)
#   3. Fatal error with a clear message
DEV_ENV_FILE="${ROOT_DIR}/.dev.env"

resolve_database_url() {
  if [[ -n "${DATABASE_URL:-}" ]]; then
    return 0  # caller already exported it
  fi
  if [[ -f "${DEV_ENV_FILE}" ]]; then
    # shellcheck source=/dev/null
    source "${DEV_ENV_FILE}"
  fi
  if [[ -z "${DATABASE_URL:-}" ]]; then
    die "DATABASE_URL is not set. After running the setup wizard, run:
    export DATABASE_URL=\"<write_dsn from setup output>\"
  or save it once with:
    echo 'export DATABASE_URL=\"<dsn>\"' >> ${DEV_ENV_FILE}
  then re-run dev.sh start."
  fi
}

# Frontend origin — matches FRONTEND_PORT above so CORS just works.
ALLOWED_ORIGINS_DEV="http://localhost:${FRONTEND_PORT},http://127.0.0.1:${FRONTEND_PORT}"

# ----- helpers ---------------------------------------------------------------

c_red()    { printf '\033[31m%s\033[0m' "$*"; }
c_green()  { printf '\033[32m%s\033[0m' "$*"; }
c_yellow() { printf '\033[33m%s\033[0m' "$*"; }
c_blue()   { printf '\033[34m%s\033[0m' "$*"; }

log()  { printf '%s %s\n' "$(c_blue '[dev]')" "$*"; }
warn() { printf '%s %s\n' "$(c_yellow '[dev]')" "$*" >&2; }
die()  { printf '%s %s\n' "$(c_red '[dev]')" "$*" >&2; exit 1; }

is_running() {
  local pid_file="$1"
  [[ -f "${pid_file}" ]] || return 1
  local pid
  pid="$(cat "${pid_file}")"
  [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null
}

stop_pid() {
  local label="$1"
  local pid_file="$2"
  if is_running "${pid_file}"; then
    local pid
    pid="$(cat "${pid_file}")"
    log "stopping ${label} (pid ${pid})"
    # Try the process group first (works on Linux); fall back to PID on macOS.
    kill -TERM -- "-${pid}" 2>/dev/null || kill -TERM "${pid}" 2>/dev/null || true
    # Also kill any child processes (uvicorn reload/next dev fork workers).
    pkill -TERM -P "${pid}" 2>/dev/null || true
    for _ in 1 2 3 4 5 6 7 8; do
      kill -0 "${pid}" 2>/dev/null || break
      sleep 0.5
    done
    if kill -0 "${pid}" 2>/dev/null; then
      warn "${label} did not exit; sending SIGKILL"
      pkill -KILL -P "${pid}" 2>/dev/null || true
      kill -KILL "${pid}" 2>/dev/null || true
    fi
    rm -f "${pid_file}"
  else
    log "${label} not running"
  fi
}

reset_logs() {
  log "resetting log directory ${LOG_DIR}"
  rm -rf "${LOG_DIR}"
  mkdir -p "${LOG_DIR}" "${PID_DIR}"
  : > "${BACKEND_LOG}"
  : > "${FRONTEND_LOG}"
}

ensure_infra() {
  log "ensuring docker compose infra is up (postgres, valkey, minio, nats)"
  ( cd "${INFRA_DIR}" && docker compose up -d postgres valkey minio nats >/dev/null )
  log "waiting for postgres health"
  for i in $(seq 1 30); do
    if docker exec tennetctl-postgres pg_isready -U tennetctl_admin -d tennetctl >/dev/null 2>&1; then
      log "postgres ready"
      return 0
    fi
    sleep 1
  done
  die "postgres did not become ready in 30s"
}

ensure_backend_deps() {
  if [[ ! -d "${ROOT_DIR}/.venv" ]]; then
    log "creating root venv (uv sync)"
    ( cd "${ROOT_DIR}" && uv sync ) >> "${BACKEND_LOG}" 2>&1 \
      || die "uv sync failed — see ${BACKEND_LOG}"
  fi
}

ensure_frontend_deps() {
  if [[ ! -d "${ROOT_DIR}/06_frontend/node_modules" ]]; then
    log "installing frontend deps (npm install)"
    ( cd "${ROOT_DIR}/06_frontend" && npm install --no-audit --no-fund ) >> "${FRONTEND_LOG}" 2>&1 \
      || die "npm install failed — see ${FRONTEND_LOG}"
  fi
}

start_backend() {
  if is_running "${BACKEND_PID}"; then
    log "backend already running (pid $(cat "${BACKEND_PID}"))"
    return 0
  fi
  ensure_backend_deps
  resolve_database_url
  log "starting backend on http://127.0.0.1:${BACKEND_PORT}"
  (
    # Run from 04_backend/ so --app-dir 01_core resolves correctly, but use
    # the root venv Python to avoid the 01_core/logging.py → stdlib circular
    # import that bites the 04_backend venv's uvicorn reloader.
    cd "${ROOT_DIR}/04_backend"
    DATABASE_URL="${DATABASE_URL}" \
    ALLOWED_ORIGINS="${ALLOWED_ORIGINS_DEV}" \
    TENNETCTL_ENV=dev \
    nohup "${ROOT_DIR}/.venv/bin/python" -m uvicorn app:app \
      --app-dir 01_core \
      --host 127.0.0.1 \
      --port "${BACKEND_PORT}" \
      --reload \
      >> "${BACKEND_LOG}" 2>&1 &
    echo $! > "${BACKEND_PID}"
  )
  sleep 1
  if is_running "${BACKEND_PID}"; then
    log "backend started (pid $(cat "${BACKEND_PID}")) → logs: ${BACKEND_LOG}"
  else
    die "backend failed to start — tail ${BACKEND_LOG}"
  fi
}

start_frontend() {
  if is_running "${FRONTEND_PID}"; then
    log "frontend already running (pid $(cat "${FRONTEND_PID}"))"
    return 0
  fi
  ensure_frontend_deps
  log "starting frontend on http://127.0.0.1:${FRONTEND_PORT}"
  (
    cd "${ROOT_DIR}/06_frontend"
    nohup npm run dev -- --port "${FRONTEND_PORT}" --hostname 127.0.0.1 \
      >> "${FRONTEND_LOG}" 2>&1 &
    echo $! > "${FRONTEND_PID}"
  )
  sleep 1
  if is_running "${FRONTEND_PID}"; then
    log "frontend started (pid $(cat "${FRONTEND_PID}")) → logs: ${FRONTEND_LOG}"
  else
    die "frontend failed to start — tail ${FRONTEND_LOG}"
  fi
}

cmd_start() {
  # Resolve DSN before reset_logs wipes the dir (so .dev.env survives across restarts)
  resolve_database_url
  reset_logs
  ensure_infra
  start_backend
  start_frontend
  log "$(c_green 'all up')"
  log "  backend  → http://127.0.0.1:${BACKEND_PORT}"
  log "  frontend → http://127.0.0.1:${FRONTEND_PORT}/"
  log "  logs     → ${LOG_DIR}/"
  log "  sign in  → admin / ChangeMe123!  (change after first login)"
}

cmd_stop() {
  stop_pid backend  "${BACKEND_PID}"
  stop_pid frontend "${FRONTEND_PID}"
}

cmd_restart() {
  cmd_stop
  cmd_start
}

cmd_down() {
  cmd_stop
  log "stopping docker compose infra"
  ( cd "${INFRA_DIR}" && docker compose down )
}

cmd_status() {
  if is_running "${BACKEND_PID}";  then log "backend  $(c_green 'UP')   pid $(cat "${BACKEND_PID}")  port ${BACKEND_PORT}";  else log "backend  $(c_red 'DOWN')"; fi
  if is_running "${FRONTEND_PID}"; then log "frontend $(c_green 'UP')   pid $(cat "${FRONTEND_PID}") port ${FRONTEND_PORT}"; else log "frontend $(c_red 'DOWN')"; fi
  if docker ps --format '{{.Names}}' | grep -q '^tennetctl-postgres$'; then
    log "postgres $(c_green 'UP')   port ${POSTGRES_PORT}"
  else
    log "postgres $(c_red 'DOWN')"
  fi
}

cmd_logs() {
  local target="${1:-}"
  case "${target}" in
    backend)  exec tail -F "${BACKEND_LOG}" ;;
    frontend) exec tail -F "${FRONTEND_LOG}" ;;
    "")       exec tail -F "${BACKEND_LOG}" "${FRONTEND_LOG}" ;;
    *)        die "unknown log target: ${target} (use backend|frontend)" ;;
  esac
}

# ----- dispatch --------------------------------------------------------------

main() {
  local cmd="${1:-start}"
  shift || true
  case "${cmd}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_restart ;;
    down)    cmd_down ;;
    status)  cmd_status ;;
    logs)    cmd_logs "${@:-}" ;;
    -h|--help|help)
      sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      ;;
    set-dsn)
      local dsn="${1:-}"
      [[ -n "${dsn}" ]] || die "usage: dev.sh set-dsn <postgresql://...>"
      mkdir -p "${LOG_DIR}"
      printf 'export DATABASE_URL="%s"\n' "${dsn}" > "${DEV_ENV_FILE}"
      log "saved DSN to ${DEV_ENV_FILE}"
      ;;
    *) die "unknown command: ${cmd} (use: start|stop|restart|down|status|logs|set-dsn)" ;;
  esac
}

main "$@"
