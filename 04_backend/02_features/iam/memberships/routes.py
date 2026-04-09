"""IAM memberships routes.

GET    /v1/memberships/orgs              — list user's org memberships (?user_id=)
POST   /v1/memberships/orgs             — add user to org
DELETE /v1/memberships/orgs/{id}        — remove user from org (hard delete, 204)

GET    /v1/memberships/workspaces        — list user's workspace memberships (?user_id=)
POST   /v1/memberships/workspaces        — add user to workspace
DELETE /v1/memberships/workspaces/{id}   — remove user from workspace (hard delete, 204)
"""

from __future__ import annotations

import importlib

from fastapi import APIRouter, Depends, Query

_db = importlib.import_module("04_backend.01_core.db")
_service = importlib.import_module("04_backend.02_features.iam.memberships.service")
_resp = importlib.import_module("04_backend.01_core.response")
_auth = importlib.import_module("04_backend.01_core.auth")
_schemas = importlib.import_module("04_backend.02_features.iam.memberships.schemas")

router = APIRouter(prefix="/v1/memberships", tags=["memberships"])


# ---------------------------------------------------------------------------
# Org memberships
# ---------------------------------------------------------------------------

@router.get("/orgs")
async def list_user_orgs(
    user_id: str = Query(...),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _token: dict = Depends(_auth.require_auth),
) -> dict:
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.list_user_orgs(
            conn, user_id=user_id, limit=limit, offset=offset
        )
    return _resp.ok(result)


@router.post("/orgs", status_code=201)
async def add_user_to_org(
    body: _schemas.OrgMembershipCreate,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        membership = await _service.add_user_to_org(
            conn,
            user_id=body.user_id,
            org_id=body.org_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=token.get("oid"),
            workspace_id_audit=token.get("wid"),
        )
    return _resp.ok(membership)


@router.delete("/orgs/{membership_id}", status_code=204)
async def remove_user_from_org(
    membership_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.remove_user_from_org(
            conn,
            membership_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=token.get("oid"),
            workspace_id_audit=token.get("wid"),
        )


# ---------------------------------------------------------------------------
# Workspace memberships
# ---------------------------------------------------------------------------

@router.get("/workspaces")
async def list_user_workspaces(
    user_id: str = Query(...),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _token: dict = Depends(_auth.require_auth),
) -> dict:
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.list_user_workspaces(
            conn, user_id=user_id, limit=limit, offset=offset
        )
    return _resp.ok(result)


@router.post("/workspaces", status_code=201)
async def add_user_to_workspace(
    body: _schemas.WorkspaceMembershipCreate,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        membership = await _service.add_user_to_workspace(
            conn,
            user_id=body.user_id,
            workspace_id=body.workspace_id,
            org_id=body.org_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=token.get("oid"),
            workspace_id_audit=token.get("wid"),
        )
    return _resp.ok(membership)


@router.delete("/workspaces/{membership_id}", status_code=204)
async def remove_user_from_workspace(
    membership_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.remove_user_from_workspace(
            conn,
            membership_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=token.get("oid"),
            workspace_id_audit=token.get("wid"),
        )
