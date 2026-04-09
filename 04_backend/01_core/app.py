"""FastAPI application factory.

Run with:
    cd /path/to/tennetctl
    DATABASE_URL=... .venv/bin/python -m uvicorn 04_backend.01_core.app:app \
        --host 0.0.0.0 --port 8000 --reload

Or via the scripts.00_core._paths helper which adds the project root to sys.path.

Boot sequence:
  1. Read DATABASE_URL from env.
  2. Open asyncpg pool.
  3. Unseal vault (derive MDK from DATABASE_URL password + system_meta.unseal_salt).
  4. Warm JWT secret cache (one vault decrypt read).
  5. Mount routes; serve.
"""

from __future__ import annotations

import importlib
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

# Ensure project root is on sys.path so importlib paths resolve.
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Core imports (this file lives in 04_backend/01_core/ — accessed via --app-dir OR importlib)
_config = importlib.import_module("04_backend.01_core.config")
_db = importlib.import_module("04_backend.01_core.db")
_response = importlib.import_module("04_backend.01_core.response")
_errors_mod = importlib.import_module("04_backend.01_core.errors")
_vault_state = importlib.import_module("04_backend.01_core.vault_state")
_jwt_utils = importlib.import_module("04_backend.01_core.jwt_utils")
_settings = importlib.import_module("04_backend.01_core.settings")
_ratelimit = importlib.import_module("04_backend.01_core.ratelimit")
_logging = importlib.import_module("04_backend.01_core.log_config")
_core_id = importlib.import_module("scripts.00_core._id")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard security response headers on every request.

    HSTS is only emitted outside of dev (TENNETCTL_ENV != 'dev') because
    local dev runs over plain HTTP and browsers would pin the dev host.
    """

    def __init__(self, app, *, is_prod: bool) -> None:
        super().__init__(app)
        self._is_prod = is_prod

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        if self._is_prod:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attaches an X-Request-ID to every request for log/audit correlation.

    If the client sends X-Request-ID, it is trusted and echoed. Otherwise
    a fresh UUID v7 is generated. The ID is stored on request.state so
    downstream code (services, audit) can read it.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or _core_id.uuid7()
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

# Feature routes
_vault_routes = importlib.import_module("04_backend.02_features.vault.runtime.routes")
_sessions_routes = importlib.import_module("04_backend.02_features.iam.sessions.routes")
_users_routes = importlib.import_module("04_backend.02_features.iam.users.routes")
_orgs_routes = importlib.import_module("04_backend.02_features.iam.orgs.routes")
_workspaces_routes = importlib.import_module("04_backend.02_features.iam.workspaces.routes")
_memberships_routes = importlib.import_module("04_backend.02_features.iam.memberships.routes")
_audit_routes = importlib.import_module("04_backend.02_features.audit.routes")
_groups_routes = importlib.import_module("04_backend.02_features.iam.groups.routes")
_catalog_routes = importlib.import_module("04_backend.02_features.iam.catalog.routes")
_products_routes = importlib.import_module("04_backend.02_features.iam.products.routes")
_feature_registry_routes = importlib.import_module("04_backend.02_features.iam.feature_registry.routes")
_feature_flags_routes = importlib.import_module("04_backend.02_features.iam.feature_flags.routes")
_rbac_routes = importlib.import_module("04_backend.02_features.iam.rbac.routes")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    _logging.configure_logging()
    settings = _config.load_settings()
    await _db.init_pool(settings.database_url)
    await _vault_state.unseal_on_boot(_db.get_pool())
    await _jwt_utils.warm_cache()
    await _settings.load_settings_from_db(_db.get_pool())
    try:
        yield
    finally:
        await _ratelimit.close()
        await _db.close_pool()


def create_app() -> FastAPI:
    from fastapi.middleware.cors import CORSMiddleware  # noqa: PLC0415

    fastapi_app = FastAPI(
        title="tennetctl",
        version="0.0.1",
        lifespan=lifespan,
    )

    # CORS — allowed origins come from the ALLOWED_ORIGINS env var
    # (comma-separated). Defaults to localhost dev origins.
    _app_settings = _config.load_settings()
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=_app_settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Security headers on every response.
    fastapi_app.add_middleware(
        SecurityHeadersMiddleware,
        is_prod=(_app_settings.tennetctl_env != "dev"),
    )

    # X-Request-ID propagation for log/audit correlation.
    fastapi_app.add_middleware(RequestIdMiddleware)

    # Register error handlers
    _errors_mod.register_error_handlers(fastapi_app)

    # Health endpoints (no auth required)
    @fastapi_app.get("/healthz")
    async def healthz() -> dict:
        return _response.ok({"status": "ok"})

    @fastapi_app.get("/readyz")
    async def readyz() -> dict:
        pool = _db.get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return _response.ok({"status": "ready"})

    # Feature routers
    fastapi_app.include_router(_vault_routes.router)
    fastapi_app.include_router(_sessions_routes.router)
    fastapi_app.include_router(_users_routes.router)
    fastapi_app.include_router(_orgs_routes.router)
    fastapi_app.include_router(_workspaces_routes.router)
    fastapi_app.include_router(_memberships_routes.router)
    fastapi_app.include_router(_audit_routes.router)
    fastapi_app.include_router(_groups_routes.router)
    fastapi_app.include_router(_catalog_routes.router)
    fastapi_app.include_router(_products_routes.router)
    fastapi_app.include_router(_feature_registry_routes.router)
    fastapi_app.include_router(_feature_flags_routes.router)
    fastapi_app.include_router(_rbac_routes.router)

    return fastapi_app


app = create_app()
