"""Vault runtime API routes.

GET  /v1/vault/status  — vault initialization and seal status
"""

from __future__ import annotations

import importlib

from fastapi import APIRouter

_db = importlib.import_module("04_backend.01_core.db")
_service = importlib.import_module("04_backend.02_features.vault.runtime.service")
_schemas = importlib.import_module("04_backend.02_features.vault.runtime.schemas")
_resp = importlib.import_module("04_backend.01_core.response")

router = APIRouter(prefix="/v1/vault", tags=["vault"])


@router.get("/status")
async def get_vault_status() -> dict:
    """Return vault initialization and seal status."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        status = await _service.get_vault_status(conn)

    # Overlay the live in-memory seal state
    status["status"] = "unsealed" if _service.is_unsealed() else "sealed"
    return _resp.ok(status)
