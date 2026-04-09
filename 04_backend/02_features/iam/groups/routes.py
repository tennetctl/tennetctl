"""IAM groups routes.

POST   /v1/groups                          create group (org-scoped)
GET    /v1/groups                          list groups (filter by org_id)
GET    /v1/groups/{id}                     get group
PATCH  /v1/groups/{id}                     update group (name/slug/description)
DELETE /v1/groups/{id}                     soft-delete group

POST   /v1/groups/{id}/members             add user to group
GET    /v1/groups/{id}/members             list members
DELETE /v1/groups/{id}/members/{user_id}   remove member
"""

from __future__ import annotations

import importlib

from fastapi import APIRouter, Depends, Query

_db = importlib.import_module("04_backend.01_core.db")
_service = importlib.import_module("04_backend.02_features.iam.groups.service")
_resp = importlib.import_module("04_backend.01_core.response")
_auth = importlib.import_module("04_backend.01_core.auth")
_schemas = importlib.import_module("04_backend.02_features.iam.groups.schemas")
_errors_mod = importlib.import_module("04_backend.01_core.errors")

AppError = _errors_mod.AppError

router = APIRouter(prefix="/v1/groups", tags=["groups"])


# ---------------------------------------------------------------------------
# Group CRUD
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
async def create_group(
    body: _schemas.CreateGroupRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Create a new group scoped to an org."""
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    org_id_audit: str | None = token.get("org")
    workspace_id_audit: str | None = token.get("wid")

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.create_group(
            conn,
            name=body.name,
            slug=body.slug,
            org_id=body.org_id,
            description=body.description,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_audit,
            workspace_id_audit=workspace_id_audit,
        )
    return _resp.ok(result)


@router.get("")
async def list_groups(
    org_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """List groups, optionally filtered by org_id."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.list_groups(
            conn,
            limit=limit,
            offset=offset,
            org_id=org_id,
        )
    return _resp.ok(result)


@router.get("/{group_id}")
async def get_group(
    group_id: str,
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Get a single group by ID."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.get_group(conn, group_id)
    return _resp.ok(result)


@router.patch("/{group_id}")
async def update_group(
    group_id: str,
    body: _schemas.UpdateGroupRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Update group name, slug, or description."""
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    org_id_audit: str | None = token.get("org")
    workspace_id_audit: str | None = token.get("wid")

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.update_group(
            conn,
            group_id,
            name=body.name,
            slug=body.slug,
            description=body.description,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_audit,
            workspace_id_audit=workspace_id_audit,
        )
    return _resp.ok(result)


@router.delete("/{group_id}", status_code=204)
async def delete_group(
    group_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    """Soft-delete a group."""
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    org_id_audit: str | None = token.get("org")
    workspace_id_audit: str | None = token.get("wid")

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.delete_group(
            conn,
            group_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_audit,
            workspace_id_audit=workspace_id_audit,
        )


# ---------------------------------------------------------------------------
# Member management
# ---------------------------------------------------------------------------

@router.post("/{group_id}/members", status_code=201)
async def add_member(
    group_id: str,
    body: _schemas.AddMemberRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Add a user to the group."""
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    org_id_audit: str | None = token.get("org")
    workspace_id_audit: str | None = token.get("wid")

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.add_member(
            conn,
            group_id,
            body.user_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_audit,
            workspace_id_audit=workspace_id_audit,
        )
    return _resp.ok(result)


@router.get("/{group_id}/members")
async def list_members(
    group_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """List active members of the group."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.list_members(
            conn,
            group_id,
            limit=limit,
            offset=offset,
        )
    return _resp.ok(result)


@router.delete("/{group_id}/members/{user_id}", status_code=204)
async def remove_member(
    group_id: str,
    user_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    """Remove a user from the group (soft-remove)."""
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    org_id_audit: str | None = token.get("org")
    workspace_id_audit: str | None = token.get("wid")

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.remove_member(
            conn,
            group_id,
            user_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_audit,
            workspace_id_audit=workspace_id_audit,
        )
