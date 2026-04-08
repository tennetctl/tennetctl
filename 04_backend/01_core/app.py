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

from fastapi import FastAPI

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
_logging = importlib.import_module("04_backend.01_core.logging")

# Feature routes
_vault_routes = importlib.import_module("04_backend.02_features.vault.runtime.routes")
_sessions_routes = importlib.import_module("04_backend.02_features.iam.sessions.routes")
_users_routes = importlib.import_module("04_backend.02_features.iam.users.routes")
_orgs_routes = importlib.import_module("04_backend.02_features.iam.orgs.routes")
_workspaces_routes = importlib.import_module("04_backend.02_features.iam.workspaces.routes")
_memberships_routes = importlib.import_module("04_backend.02_features.iam.memberships.routes")


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

    # CORS — allow the frontend dev server and any localhost port.
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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

    return fastapi_app


app = create_app()
