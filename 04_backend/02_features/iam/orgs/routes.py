"""IAM orgs routes.

GET    /v1/orgs          — list orgs
POST   /v1/orgs          — create org
GET    /v1/orgs/{id}     — get org
PATCH  /v1/orgs/{id}     — update org
DELETE /v1/orgs/{id}     — soft-delete org (archive)
"""

from __future__ import annotations

import importlib

from fastapi import APIRouter, Depends, Query

_db = importlib.import_module("04_backend.01_core.db")
_service = importlib.import_module("04_backend.02_features.iam.orgs.service")
_resp = importlib.import_module("04_backend.01_core.response")
_auth = importlib.import_module("04_backend.01_core.auth")
_schemas = importlib.import_module("04_backend.02_features.iam.orgs.schemas")

router = APIRouter(prefix="/v1/orgs", tags=["orgs"])


@router.get("")
async def list_orgs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    is_active: bool | None = Query(default=None),
    token: dict = Depends(_auth.require_auth),
) -> dict:
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.list_orgs(conn, limit=limit, offset=offset, is_active=is_active)
    return _resp.ok(result)


@router.post("", status_code=201)
async def create_org(
    body: _schemas.OrgCreate,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        org = await _service.create_org(
            conn,
            name=body.name,
            slug=body.slug,
            description=body.description,
            owner_id=body.owner_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=token.get("oid"),
            workspace_id_audit=token.get("wid"),
        )
    return _resp.ok(org)


@router.get("/{org_id}")
async def get_org(
    org_id: str,
    _token: dict = Depends(_auth.require_auth),
) -> dict:
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        org = await _service.get_org(conn, org_id)
    return _resp.ok(org)


@router.patch("/{org_id}")
async def update_org(
    org_id: str,
    body: _schemas.OrgUpdate,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        org = await _service.update_org(
            conn,
            org_id,
            name=body.name,
            slug=body.slug,
            description=body.description,
            status_code=body.status_code,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=token.get("oid"),
            workspace_id_audit=token.get("wid"),
        )
    return _resp.ok(org)


@router.delete("/{org_id}", status_code=204)
async def delete_org(
    org_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.delete_org(
            conn,
            org_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=token.get("oid"),
            workspace_id_audit=token.get("wid"),
        )
