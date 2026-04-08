"""IAM workspaces routes.

GET    /v1/workspaces          — list workspaces (filter: ?org_id=)
POST   /v1/workspaces          — create workspace
GET    /v1/workspaces/{id}     — get workspace
PATCH  /v1/workspaces/{id}     — update workspace
DELETE /v1/workspaces/{id}     — soft-delete workspace (archive)
"""

from __future__ import annotations

import importlib

from fastapi import APIRouter, Depends, Query

_db = importlib.import_module("04_backend.01_core.db")
_service = importlib.import_module("04_backend.02_features.iam.workspaces.service")
_resp = importlib.import_module("04_backend.01_core.response")
_auth = importlib.import_module("04_backend.01_core.auth")
_schemas = importlib.import_module("04_backend.02_features.iam.workspaces.schemas")

router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])


@router.get("")
async def list_workspaces(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    org_id: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    _token: dict = Depends(_auth.require_auth),
) -> dict:
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.list_workspaces(
            conn, limit=limit, offset=offset, org_id=org_id, is_active=is_active
        )
    return _resp.ok(result)


@router.post("", status_code=201)
async def create_workspace(
    body: _schemas.WorkspaceCreate,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        ws = await _service.create_workspace(
            conn,
            org_id=body.org_id,
            name=body.name,
            slug=body.slug,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=token.get("oid"),
            workspace_id_audit=token.get("wid"),
        )
    return _resp.ok(ws)


@router.get("/{workspace_id}")
async def get_workspace(
    workspace_id: str,
    _token: dict = Depends(_auth.require_auth),
) -> dict:
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        ws = await _service.get_workspace(conn, workspace_id)
    return _resp.ok(ws)


@router.patch("/{workspace_id}")
async def update_workspace(
    workspace_id: str,
    body: _schemas.WorkspaceUpdate,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        ws = await _service.update_workspace(
            conn,
            workspace_id,
            name=body.name,
            slug=body.slug,
            status_code=body.status_code,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=token.get("oid"),
            workspace_id_audit=token.get("wid"),
        )
    return _resp.ok(ws)


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(
    workspace_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.delete_workspace(
            conn,
            workspace_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=token.get("oid"),
            workspace_id_audit=token.get("wid"),
        )
