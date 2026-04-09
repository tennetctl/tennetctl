"""RBAC routes — three-tier roles + permissions + runtime check.

Platform roles:
  GET    /v1/platform-roles
  POST   /v1/platform-roles
  GET    /v1/platform-roles/{id}
  PATCH  /v1/platform-roles/{id}
  DELETE /v1/platform-roles/{id}
  POST   /v1/platform-roles/{id}/permissions
  DELETE /v1/platform-roles/{id}/permissions/{pid}
  POST   /v1/users/{id}/platform-roles
  DELETE /v1/users/{id}/platform-roles/{role_id}

Org roles:
  GET    /v1/orgs/{org_id}/roles
  POST   /v1/orgs/{org_id}/roles
  PATCH  /v1/orgs/{org_id}/roles/{id}
  DELETE /v1/orgs/{org_id}/roles/{id}
  POST   /v1/orgs/{org_id}/roles/{id}/permissions
  DELETE /v1/orgs/{org_id}/roles/{id}/permissions/{pid}
  POST   /v1/users/{id}/org-roles
  DELETE /v1/users/{id}/org-roles/{assignment_id}

Workspace roles:
  GET    /v1/workspaces/{ws_id}/roles
  POST   /v1/workspaces/{ws_id}/roles
  PATCH  /v1/workspaces/{ws_id}/roles/{id}
  DELETE /v1/workspaces/{ws_id}/roles/{id}
  POST   /v1/workspaces/{ws_id}/roles/{id}/permissions
  DELETE /v1/workspaces/{ws_id}/roles/{id}/permissions/{pid}
  POST   /v1/users/{id}/workspace-roles
  DELETE /v1/users/{id}/workspace-roles/{assignment_id}

Permissions catalog:
  GET    /v1/permissions

Runtime:
  POST   /v1/rbac/check
  GET    /v1/users/{id}/permissions/effective
"""

from __future__ import annotations

import importlib
from typing import Optional

from fastapi import APIRouter, Depends, Query

_db = importlib.import_module("04_backend.01_core.db")
_service = importlib.import_module("04_backend.02_features.iam.rbac.service")
_resp = importlib.import_module("04_backend.01_core.response")
_auth = importlib.import_module("04_backend.01_core.auth")
_schemas = importlib.import_module("04_backend.02_features.iam.rbac.schemas")

router = APIRouter(tags=["rbac"])


def _actor(token: dict) -> tuple[str, str, str | None, str | None]:
    """Return (actor_id, session_id, org_id, workspace_id) from token."""
    return (
        token["sub"],
        token.get("sid", ""),
        token.get("org"),
        token.get("wid"),
    )


# ---------------------------------------------------------------------------
# Permissions catalog
# ---------------------------------------------------------------------------

@router.get("/v1/permissions")
async def list_permissions(
    token: dict = Depends(_auth.require_auth),
) -> dict:
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.list_permissions(conn)
    return _resp.ok(result)


# ---------------------------------------------------------------------------
# Platform roles
# ---------------------------------------------------------------------------

@router.get("/v1/platform-roles")
async def list_platform_roles(
    token: dict = Depends(_auth.require_auth),
) -> dict:
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.list_platform_roles(conn)
    return _resp.ok(result)


@router.post("/v1/platform-roles", status_code=201)
async def create_platform_role(
    body: _schemas.CreatePlatformRoleRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.create_platform_role(
            conn,
            code=body.code,
            name=body.name,
            category_code=body.category_code,
            is_system=body.is_system,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )
    return _resp.ok(result)


@router.get("/v1/platform-roles/{role_id}")
async def get_platform_role(
    role_id: str,
    token: dict = Depends(_auth.require_auth),
) -> dict:
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.get_platform_role(conn, role_id)
    return _resp.ok(result)


@router.patch("/v1/platform-roles/{role_id}")
async def update_platform_role(
    role_id: str,
    body: _schemas.UpdatePlatformRoleRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.update_platform_role(
            conn,
            role_id,
            name=body.name,
            is_active=body.is_active,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )
    return _resp.ok(result)


@router.delete("/v1/platform-roles/{role_id}", status_code=204)
async def delete_platform_role(
    role_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.delete_platform_role(
            conn,
            role_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )


@router.post("/v1/platform-roles/{role_id}/permissions", status_code=201)
async def add_platform_role_permission(
    role_id: str,
    body: _schemas.AddPermissionRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.add_platform_role_permission(
            conn,
            role_id,
            body.permission_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )
    return _resp.ok(result)


@router.delete("/v1/platform-roles/{role_id}/permissions/{permission_id}", status_code=204)
async def remove_platform_role_permission(
    role_id: str,
    permission_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.remove_platform_role_permission(
            conn,
            role_id,
            permission_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )


@router.post("/v1/users/{user_id}/platform-roles", status_code=201)
async def assign_user_platform_role(
    user_id: str,
    body: _schemas.AssignPlatformRoleRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.assign_user_platform_role(
            conn,
            user_id,
            body.platform_role_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )
    return _resp.ok(result)


@router.delete("/v1/users/{user_id}/platform-roles/{role_id}", status_code=204)
async def revoke_user_platform_role(
    user_id: str,
    role_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.revoke_user_platform_role(
            conn,
            user_id,
            role_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )


# ---------------------------------------------------------------------------
# Org roles
# ---------------------------------------------------------------------------

@router.get("/v1/orgs/{org_id}/roles")
async def list_org_roles(
    org_id: str,
    token: dict = Depends(_auth.require_auth),
) -> dict:
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.list_org_roles(conn, org_id)
    return _resp.ok(result)


@router.post("/v1/orgs/{org_id}/roles", status_code=201)
async def create_org_role(
    org_id: str,
    body: _schemas.CreateOrgRoleRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.create_org_role(
            conn,
            org_id,
            code=body.code,
            name=body.name,
            category_code=body.category_code,
            is_system=body.is_system,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )
    return _resp.ok(result)


@router.patch("/v1/orgs/{org_id}/roles/{role_id}")
async def update_org_role(
    org_id: str,
    role_id: str,
    body: _schemas.UpdateOrgRoleRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.update_org_role(
            conn,
            role_id,
            name=body.name,
            is_active=body.is_active,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )
    return _resp.ok(result)


@router.delete("/v1/orgs/{org_id}/roles/{role_id}", status_code=204)
async def delete_org_role(
    org_id: str,
    role_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.delete_org_role(
            conn,
            role_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )


@router.post("/v1/orgs/{org_id}/roles/{role_id}/permissions", status_code=201)
async def add_org_role_permission(
    org_id: str,
    role_id: str,
    body: _schemas.AddPermissionRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.add_org_role_permission(
            conn,
            role_id,
            body.permission_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )
    return _resp.ok(result)


@router.delete("/v1/orgs/{org_id}/roles/{role_id}/permissions/{permission_id}", status_code=204)
async def remove_org_role_permission(
    org_id: str,
    role_id: str,
    permission_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.remove_org_role_permission(
            conn,
            role_id,
            permission_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )


@router.post("/v1/users/{user_id}/org-roles", status_code=201)
async def assign_user_org_role(
    user_id: str,
    body: _schemas.AssignOrgRoleRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.assign_user_org_role(
            conn,
            user_id,
            org_id=body.org_id,
            org_role_id=body.org_role_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )
    return _resp.ok(result)


@router.delete("/v1/users/{user_id}/org-roles/{assignment_id}", status_code=204)
async def revoke_user_org_role(
    user_id: str,
    assignment_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.revoke_user_org_role(
            conn,
            assignment_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )


# ---------------------------------------------------------------------------
# Workspace roles
# ---------------------------------------------------------------------------

@router.get("/v1/workspaces/{ws_id}/roles")
async def list_workspace_roles(
    ws_id: str,
    token: dict = Depends(_auth.require_auth),
) -> dict:
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.list_workspace_roles(conn, ws_id)
    return _resp.ok(result)


@router.post("/v1/workspaces/{ws_id}/roles", status_code=201)
async def create_workspace_role(
    ws_id: str,
    body: _schemas.CreateWorkspaceRoleRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.create_workspace_role(
            conn,
            ws_id,
            code=body.code,
            name=body.name,
            category_code=body.category_code,
            org_id=body.org_id,
            is_system=body.is_system,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )
    return _resp.ok(result)


@router.patch("/v1/workspaces/{ws_id}/roles/{role_id}")
async def update_workspace_role(
    ws_id: str,
    role_id: str,
    body: _schemas.UpdateWorkspaceRoleRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.update_workspace_role(
            conn,
            role_id,
            name=body.name,
            is_active=body.is_active,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )
    return _resp.ok(result)


@router.delete("/v1/workspaces/{ws_id}/roles/{role_id}", status_code=204)
async def delete_workspace_role(
    ws_id: str,
    role_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.delete_workspace_role(
            conn,
            role_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )


@router.post("/v1/workspaces/{ws_id}/roles/{role_id}/permissions", status_code=201)
async def add_workspace_role_permission(
    ws_id: str,
    role_id: str,
    body: _schemas.AddPermissionRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.add_workspace_role_permission(
            conn,
            role_id,
            body.permission_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )
    return _resp.ok(result)


@router.delete("/v1/workspaces/{ws_id}/roles/{role_id}/permissions/{permission_id}", status_code=204)
async def remove_workspace_role_permission(
    ws_id: str,
    role_id: str,
    permission_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.remove_workspace_role_permission(
            conn,
            role_id,
            permission_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )


@router.post("/v1/users/{user_id}/workspace-roles", status_code=201)
async def assign_user_workspace_role(
    user_id: str,
    body: _schemas.AssignWorkspaceRoleRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.assign_user_workspace_role(
            conn,
            user_id,
            workspace_id=body.workspace_id,
            workspace_role_id=body.workspace_role_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )
    return _resp.ok(result)


@router.delete("/v1/users/{user_id}/workspace-roles/{assignment_id}", status_code=204)
async def revoke_user_workspace_role(
    user_id: str,
    assignment_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    actor_id, session_id, org_id_a, ws_id_a = _actor(token)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.revoke_user_workspace_role(
            conn,
            assignment_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id_a,
            workspace_id_audit=ws_id_a,
        )


# ---------------------------------------------------------------------------
# Runtime check
# ---------------------------------------------------------------------------

@router.post("/v1/rbac/check")
async def rbac_check(
    body: _schemas.RbacCheckRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Check whether a user has a given permission in the provided context."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.rbac_check(
            conn,
            user_id=body.user_id,
            resource=body.resource,
            action=body.action,
            org_id=body.org_id,
            workspace_id=body.workspace_id,
        )
    return _resp.ok(result)


@router.get("/v1/users/{user_id}/permissions/effective")
async def get_effective_permissions(
    user_id: str,
    org_id: Optional[str] = Query(default=None),
    workspace_id: Optional[str] = Query(default=None),
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Return all effective permissions for a user in the given context."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.get_effective_permissions(
            conn,
            user_id,
            org_id=org_id,
            workspace_id=workspace_id,
        )
    return _resp.ok(result)
