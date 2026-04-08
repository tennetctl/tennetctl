"""IAM catalog routes — read-only endpoints for dim tables.

GET /v1/scopes
GET /v1/categories?category_type=role|feature|flag|product
GET /v1/environments
"""

from __future__ import annotations

import importlib

from fastapi import APIRouter, Query

_db = importlib.import_module("04_backend.01_core.db")
_resp = importlib.import_module("04_backend.01_core.response")

router = APIRouter(tags=["catalog"])


@router.get("/v1/scopes")
async def list_scopes() -> dict:
    """Return all active scopes (platform, org, workspace)."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, code, label, description
              FROM "03_iam"."06_dim_scopes"
             WHERE deprecated_at IS NULL
             ORDER BY id
            """
        )
    return _resp.ok({"items": [dict(r) for r in rows]})


@router.get("/v1/categories")
async def list_categories(
    category_type: str | None = Query(None, description="Filter by type: role|feature|flag|product"),
) -> dict:
    """Return categories, optionally filtered by category_type."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        if category_type is not None:
            rows = await conn.fetch(
                """
                SELECT id, category_type, code, label, description
                  FROM "03_iam"."06_dim_categories"
                 WHERE deprecated_at IS NULL
                   AND category_type = $1
                 ORDER BY id
                """,
                category_type,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, category_type, code, label, description
                  FROM "03_iam"."06_dim_categories"
                 WHERE deprecated_at IS NULL
                 ORDER BY category_type, id
                """
            )
    return _resp.ok({"items": [dict(r) for r in rows]})


@router.get("/v1/environments")
async def list_environments() -> dict:
    """Return all active environments (dev, staging, prod)."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, code, label, description
              FROM "03_iam"."06_dim_environments"
             WHERE deprecated_at IS NULL
             ORDER BY id
            """
        )
    return _resp.ok({"items": [dict(r) for r in rows]})
