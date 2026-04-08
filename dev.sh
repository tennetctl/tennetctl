#!/usr/bin/env bash
# dev.sh — start backend + frontend locally with hot reload
# Usage: ./dev.sh
# Stop: Ctrl+C (kills both processes)

set -e
cd "$(dirname "$0")"

# ── Config ──────────────────────────────────────────────────────────────────
BACKEND_PORT=58000
FRONTEND_PORT=3000
DATABASE_URL="${DATABASE_URL:-postgresql://tennetctl_admin:tennetctl_admin_dev@localhost:55432/tennetctl}"
ALLOWED_ORIGINS="http://localhost:${FRONTEND_PORT},http://127.0.0.1:${FRONTEND_PORT}"

# ── Infra check ──────────────────────────────────────────────────────────────
if ! pg_isready -h localhost -p 55432 -U tennetctl_admin -q 2>/dev/null; then
  echo "⚠  Postgres not reachable on :55432. Start infra first:"
  echo "   docker compose -f 11_infra/docker-compose.yml up -d postgres valkey"
  exit 1
fi

# ── Backend ──────────────────────────────────────────────────────────────────
echo "▶  backend  → http://localhost:${BACKEND_PORT}"
DATABASE_URL="${DATABASE_URL}" \
ALLOWED_ORIGINS="${ALLOWED_ORIGINS}" \
DISABLE_RATE_LIMIT=1 \
  04_backend/.venv/bin/python -m uvicorn 04_backend.01_core.app:app \
    --host 0.0.0.0 \
    --port "${BACKEND_PORT}" \
    --reload \
    --reload-dir 04_backend \
    &
BACKEND_PID=$!

# ── Frontend ─────────────────────────────────────────────────────────────────
echo "▶  frontend → http://localhost:${FRONTEND_PORT}"
cd 06_frontend
NEXT_PUBLIC_API_URL="http://localhost:${BACKEND_PORT}" \
  npm run dev -- --port "${FRONTEND_PORT}" \
  &
FRONTEND_PID=$!
cd ..

# ── Cleanup on exit ──────────────────────────────────────────────────────────
trap "echo ''; echo 'stopping...'; kill ${BACKEND_PID} ${FRONTEND_PID} 2>/dev/null; wait" INT TERM

echo ""
echo "  backend  http://localhost:${BACKEND_PORT}/healthz"
echo "  frontend http://localhost:${FRONTEND_PORT}"
echo "  docs     http://localhost:${BACKEND_PORT}/docs"
echo ""
echo "Ctrl+C to stop both"
wait
