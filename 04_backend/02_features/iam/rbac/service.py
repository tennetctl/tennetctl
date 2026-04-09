"""RBAC service — business logic for three-tier roles + runtime permission checks.

conn = asyncpg connection (never pool).
All mutations emit audit events.
"""

from __future__ import annotations

import importlib

_repo = importlib.import_module("04_backend.02_features.iam.rbac.repository")
_id_mod = importlib.import_module("scripts.00_core._id")
_errors_mod = importlib.import_module("04_backend.01_core.errors")
_audit = importlib.import_module("04_backend.02_features.audit.service")

AppError = _errors_mod.AppError


# ---------------------------------------------------------------------------
# Permissions catalog
# ---------------------------------------------------------------------------

async def list_permissions(conn: object) -> dict:
    items = await _repo.list_permissions(conn)
    return {"items": items, "total": len(items)}


# ---------------------------------------------------------------------------
# Platform roles
# ---------------------------------------------------------------------------

async def list_platform_roles(conn: object) -> dict:
    items = await _repo.list_platform_roles(conn)
    return {"items": items, "total": len(items)}


async def get_platform_role(conn: object, role_id: str) -> dict:
    role = await _repo.get_platform_role(conn, role_id)
    if role is None:
        raise AppError("PLATFORM_ROLE_NOT_FOUND", f"Platform role '{role_id}' not found.", 404)
    return role


async def create_platform_role(
    conn: object,
    *,
    code: str,
    name: str,
    category_code: str,
    is_system: bool = False,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    # Validate category
    category_id = await _repo.get_role_category_id(conn, category_code)
    if category_id is None:
        raise AppError("INVALID_CATEGORY", f"Role category '{category_code}' not found.", 422)

    # Check uniqueness
    existing = await _repo.get_platform_role_by_code(conn, code)
    if existing is not None:
        raise AppError("PLATFORM_ROLE_CODE_CONFLICT", f"Platform role code '{code}' already exists.", 409)

    role_id = _id_mod.uuid7()
    await _repo.insert_platform_role(
        conn,
        id=role_id,
        code=code,
        name=name,
        category_id=category_id,
        is_system=is_system,
        actor_id=actor_id,
    )
    await _audit.emit(
        conn,
        category="iam",
        action="platform_role.create",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=role_id,
        target_type="platform_role",
    )
    role = await _repo.get_platform_role(conn, role_id)
    return role  # type: ignore[return-value]


async def update_platform_role(
    conn: object,
    role_id: str,
    *,
    name: str | None = None,
    is_active: bool | None = None,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    role = await _repo.get_platform_role(conn, role_id)
    if role is None:
        raise AppError("PLATFORM_ROLE_NOT_FOUND", f"Platform role '{role_id}' not found.", 404)

    if name is None and is_active is None:
        return role

    await _repo.update_platform_role(
        conn, role_id, name=name, is_active=is_active, actor_id=actor_id,
    )
    await _audit.emit(
        conn,
        category="iam",
        action="platform_role.update",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=role_id,
        target_type="platform_role",
    )
    updated = await _repo.get_platform_role(conn, role_id)
    return updated  # type: ignore[return-value]


async def delete_platform_role(
    conn: object,
    role_id: str,
    *,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> None:
    role = await _repo.get_platform_role(conn, role_id)
    if role is None:
        raise AppError("PLATFORM_ROLE_NOT_FOUND", f"Platform role '{role_id}' not found.", 404)
    if role.get("is_system"):
        raise AppError("SYSTEM_ROLE_PROTECTED", "System roles cannot be deleted.", 403)

    await _repo.soft_delete_platform_role(conn, role_id, actor_id=actor_id)
    await _audit.emit(
        conn,
        category="iam",
        action="platform_role.delete",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=role_id,
        target_type="platform_role",
    )


async def add_platform_role_permission(
    conn: object,
    role_id: str,
    permission_id: str,
    *,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    role = await _repo.get_platform_role(conn, role_id)
    if role is None:
        raise AppError("PLATFORM_ROLE_NOT_FOUND", f"Platform role '{role_id}' not found.", 404)

    perm = await _repo.get_permission_by_id(conn, permission_id)
    if perm is None:
        raise AppError("PERMISSION_NOT_FOUND", f"Permission '{permission_id}' not found.", 404)

    try:
        await _repo.add_platform_role_permission(
            conn,
            id=_id_mod.uuid7(),
            platform_role_id=role_id,
            permission_id=permission_id,
        )
    except Exception as exc:
        if "uq_iam_lnk_platform_role_perms" in str(exc):
            raise AppError("PERMISSION_ALREADY_ASSIGNED", "Permission already assigned to this role.", 409) from exc
        raise

    await _audit.emit(
        conn,
        category="iam",
        action="platform_role.permission.add",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=role_id,
        target_type="platform_role",
    )
    perms = await _repo.list_platform_role_permissions(conn, role_id)
    return {"role_id": role_id, "permissions": perms}


async def remove_platform_role_permission(
    conn: object,
    role_id: str,
    permission_id: str,
    *,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> None:
    role = await _repo.get_platform_role(conn, role_id)
    if role is None:
        raise AppError("PLATFORM_ROLE_NOT_FOUND", f"Platform role '{role_id}' not found.", 404)

    deleted = await _repo.remove_platform_role_permission(
        conn, platform_role_id=role_id, permission_id=permission_id,
    )
    if not deleted:
        raise AppError("PERMISSION_NOT_FOUND", "Permission not assigned to this role.", 404)

    await _audit.emit(
        conn,
        category="iam",
        action="platform_role.permission.remove",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=role_id,
        target_type="platform_role",
    )


async def assign_user_platform_role(
    conn: object,
    user_id: str,
    platform_role_id: str,
    *,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    user = await _repo.get_user_by_id(conn, user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", f"User '{user_id}' not found.", 404)

    role = await _repo.get_platform_role(conn, platform_role_id)
    if role is None:
        raise AppError("PLATFORM_ROLE_NOT_FOUND", f"Platform role '{platform_role_id}' not found.", 404)

    existing = await _repo.get_user_platform_role_assignment(
        conn, user_id=user_id, platform_role_id=platform_role_id,
    )
    if existing and existing.get("is_active"):
        raise AppError("ROLE_ALREADY_ASSIGNED", "User already has this platform role.", 409)

    assignment_id = _id_mod.uuid7()
    if existing and not existing.get("is_active"):
        # Re-activate
        await conn.execute(  # type: ignore[union-attr]
            """
            UPDATE "03_iam"."40_lnk_user_platform_roles"
               SET is_active = true, granted_by = $3, granted_at = CURRENT_TIMESTAMP
             WHERE user_id = $1 AND platform_role_id = $2
            """,
            user_id, platform_role_id, actor_id,
        )
        assignment_id = existing["id"]
    else:
        await _repo.assign_user_platform_role(
            conn,
            id=assignment_id,
            user_id=user_id,
            platform_role_id=platform_role_id,
            granted_by=actor_id,
        )

    await _audit.emit(
        conn,
        category="iam",
        action="platform_role.assign",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=user_id,
        target_type="iam_user",
    )
    return {"user_id": user_id, "platform_role_id": platform_role_id, "is_active": True}


async def revoke_user_platform_role(
    conn: object,
    user_id: str,
    role_id: str,
    *,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> None:
    revoked = await _repo.revoke_user_platform_role(conn, user_id=user_id, role_id=role_id)
    if not revoked:
        raise AppError("ROLE_ASSIGNMENT_NOT_FOUND", "Role assignment not found.", 404)

    await _audit.emit(
        conn,
        category="iam",
        action="platform_role.revoke",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=user_id,
        target_type="iam_user",
    )


# ---------------------------------------------------------------------------
# Org roles
# ---------------------------------------------------------------------------

async def list_org_roles(conn: object, org_id: str) -> dict:
    items = await _repo.list_org_roles(conn, org_id)
    return {"items": items, "total": len(items)}


async def get_org_role(conn: object, role_id: str) -> dict:
    role = await _repo.get_org_role(conn, role_id)
    if role is None:
        raise AppError("ORG_ROLE_NOT_FOUND", f"Org role '{role_id}' not found.", 404)
    return role


async def create_org_role(
    conn: object,
    org_id: str,
    *,
    code: str,
    name: str,
    category_code: str,
    is_system: bool = False,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    org = await _repo.get_org_by_id(conn, org_id)
    if org is None:
        raise AppError("ORG_NOT_FOUND", f"Org '{org_id}' not found.", 404)

    category_id = await _repo.get_role_category_id(conn, category_code)
    if category_id is None:
        raise AppError("INVALID_CATEGORY", f"Role category '{category_code}' not found.", 422)

    role_id = _id_mod.uuid7()
    try:
        await _repo.insert_org_role(
            conn,
            id=role_id,
            org_id=org_id,
            code=code,
            name=name,
            category_id=category_id,
            is_system=is_system,
            actor_id=actor_id,
        )
    except Exception as exc:
        if "uq_iam_fct_org_roles_org_code" in str(exc):
            raise AppError("ORG_ROLE_CODE_CONFLICT", f"Org role code '{code}' already exists in this org.", 409) from exc
        raise

    await _audit.emit(
        conn,
        category="iam",
        action="org_role.create",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=role_id,
        target_type="org_role",
    )
    role = await _repo.get_org_role(conn, role_id)
    return role  # type: ignore[return-value]


async def update_org_role(
    conn: object,
    role_id: str,
    *,
    name: str | None = None,
    is_active: bool | None = None,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    role = await _repo.get_org_role(conn, role_id)
    if role is None:
        raise AppError("ORG_ROLE_NOT_FOUND", f"Org role '{role_id}' not found.", 404)

    if name is None and is_active is None:
        return role

    await _repo.update_org_role(
        conn, role_id, name=name, is_active=is_active, actor_id=actor_id,
    )
    await _audit.emit(
        conn,
        category="iam",
        action="org_role.update",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=role_id,
        target_type="org_role",
    )
    updated = await _repo.get_org_role(conn, role_id)
    return updated  # type: ignore[return-value]


async def delete_org_role(
    conn: object,
    role_id: str,
    *,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> None:
    role = await _repo.get_org_role(conn, role_id)
    if role is None:
        raise AppError("ORG_ROLE_NOT_FOUND", f"Org role '{role_id}' not found.", 404)
    if role.get("is_system"):
        raise AppError("SYSTEM_ROLE_PROTECTED", "System roles cannot be deleted.", 403)

    await _repo.soft_delete_org_role(conn, role_id, actor_id=actor_id)
    await _audit.emit(
        conn,
        category="iam",
        action="org_role.delete",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=role_id,
        target_type="org_role",
    )


async def add_org_role_permission(
    conn: object,
    role_id: str,
    permission_id: str,
    *,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    role = await _repo.get_org_role(conn, role_id)
    if role is None:
        raise AppError("ORG_ROLE_NOT_FOUND", f"Org role '{role_id}' not found.", 404)

    perm = await _repo.get_permission_by_id(conn, permission_id)
    if perm is None:
        raise AppError("PERMISSION_NOT_FOUND", f"Permission '{permission_id}' not found.", 404)

    try:
        await _repo.add_org_role_permission(
            conn,
            id=_id_mod.uuid7(),
            org_role_id=role_id,
            permission_id=permission_id,
        )
    except Exception as exc:
        if "uq_iam_lnk_org_role_perms" in str(exc):
            raise AppError("PERMISSION_ALREADY_ASSIGNED", "Permission already assigned to this role.", 409) from exc
        raise

    await _audit.emit(
        conn,
        category="iam",
        action="org_role.permission.add",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=role_id,
        target_type="org_role",
    )
    perms_rows = await conn.fetch(  # type: ignore[union-attr]
        """
        SELECT p.id, p.resource, p.action, p.description, p.is_active
          FROM "03_iam"."40_lnk_org_role_permissions" lnk
          JOIN "03_iam"."10_fct_permissions" p ON p.id = lnk.permission_id
         WHERE lnk.org_role_id = $1
         ORDER BY p.resource, p.action
        """,
        role_id,
    )
    return {"role_id": role_id, "permissions": [dict(r) for r in perms_rows]}


async def remove_org_role_permission(
    conn: object,
    role_id: str,
    permission_id: str,
    *,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> None:
    role = await _repo.get_org_role(conn, role_id)
    if role is None:
        raise AppError("ORG_ROLE_NOT_FOUND", f"Org role '{role_id}' not found.", 404)

    deleted = await _repo.remove_org_role_permission(
        conn, org_role_id=role_id, permission_id=permission_id,
    )
    if not deleted:
        raise AppError("PERMISSION_NOT_FOUND", "Permission not assigned to this role.", 404)

    await _audit.emit(
        conn,
        category="iam",
        action="org_role.permission.remove",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=role_id,
        target_type="org_role",
    )


async def assign_user_org_role(
    conn: object,
    user_id: str,
    *,
    org_id: str,
    org_role_id: str,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    user = await _repo.get_user_by_id(conn, user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", f"User '{user_id}' not found.", 404)

    org = await _repo.get_org_by_id(conn, org_id)
    if org is None:
        raise AppError("ORG_NOT_FOUND", f"Org '{org_id}' not found.", 404)

    role = await _repo.get_org_role(conn, org_role_id)
    if role is None:
        raise AppError("ORG_ROLE_NOT_FOUND", f"Org role '{org_role_id}' not found.", 404)

    existing = await _repo.get_user_org_role_assignment(
        conn, user_id=user_id, org_id=org_id, org_role_id=org_role_id,
    )
    if existing and existing.get("is_active"):
        raise AppError("ROLE_ALREADY_ASSIGNED", "User already has this org role.", 409)

    assignment_id = _id_mod.uuid7()
    if existing and not existing.get("is_active"):
        await conn.execute(  # type: ignore[union-attr]
            """
            UPDATE "03_iam"."40_lnk_user_org_roles"
               SET is_active = true, granted_by = $4, granted_at = CURRENT_TIMESTAMP
             WHERE user_id = $1 AND org_id = $2 AND org_role_id = $3
            """,
            user_id, org_id, org_role_id, actor_id,
        )
        assignment_id = existing["id"]
    else:
        await _repo.assign_user_org_role(
            conn,
            id=assignment_id,
            user_id=user_id,
            org_id=org_id,
            org_role_id=org_role_id,
            granted_by=actor_id,
        )

    await _audit.emit(
        conn,
        category="iam",
        action="org_role.assign",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=user_id,
        target_type="iam_user",
    )
    return {
        "id": assignment_id,
        "user_id": user_id,
        "org_id": org_id,
        "org_role_id": org_role_id,
        "is_active": True,
    }


async def revoke_user_org_role(
    conn: object,
    assignment_id: str,
    *,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> None:
    revoked = await _repo.revoke_user_org_role(conn, assignment_id)
    if not revoked:
        raise AppError("ROLE_ASSIGNMENT_NOT_FOUND", "Org role assignment not found.", 404)

    await _audit.emit(
        conn,
        category="iam",
        action="org_role.revoke",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=assignment_id,
        target_type="org_role_assignment",
    )


# ---------------------------------------------------------------------------
# Workspace roles
# ---------------------------------------------------------------------------

async def list_workspace_roles(conn: object, workspace_id: str) -> dict:
    items = await _repo.list_workspace_roles(conn, workspace_id)
    return {"items": items, "total": len(items)}


async def get_workspace_role(conn: object, role_id: str) -> dict:
    role = await _repo.get_workspace_role(conn, role_id)
    if role is None:
        raise AppError("WORKSPACE_ROLE_NOT_FOUND", f"Workspace role '{role_id}' not found.", 404)
    return role


async def create_workspace_role(
    conn: object,
    workspace_id: str,
    *,
    code: str,
    name: str,
    category_code: str,
    org_id: str,
    is_system: bool = False,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    ws = await _repo.get_workspace_by_id(conn, workspace_id)
    if ws is None:
        raise AppError("WORKSPACE_NOT_FOUND", f"Workspace '{workspace_id}' not found.", 404)

    category_id = await _repo.get_role_category_id(conn, category_code)
    if category_id is None:
        raise AppError("INVALID_CATEGORY", f"Role category '{category_code}' not found.", 422)

    role_id = _id_mod.uuid7()
    try:
        await _repo.insert_workspace_role(
            conn,
            id=role_id,
            org_id=org_id,
            workspace_id=workspace_id,
            code=code,
            name=name,
            category_id=category_id,
            is_system=is_system,
            actor_id=actor_id,
        )
    except Exception as exc:
        if "uq_iam_fct_workspace_roles_ws_code" in str(exc):
            raise AppError("WORKSPACE_ROLE_CODE_CONFLICT", f"Workspace role code '{code}' already exists in this workspace.", 409) from exc
        raise

    await _audit.emit(
        conn,
        category="iam",
        action="workspace_role.create",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=role_id,
        target_type="workspace_role",
    )
    role = await _repo.get_workspace_role(conn, role_id)
    return role  # type: ignore[return-value]


async def update_workspace_role(
    conn: object,
    role_id: str,
    *,
    name: str | None = None,
    is_active: bool | None = None,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    role = await _repo.get_workspace_role(conn, role_id)
    if role is None:
        raise AppError("WORKSPACE_ROLE_NOT_FOUND", f"Workspace role '{role_id}' not found.", 404)

    if name is None and is_active is None:
        return role

    await _repo.update_workspace_role(
        conn, role_id, name=name, is_active=is_active, actor_id=actor_id,
    )
    await _audit.emit(
        conn,
        category="iam",
        action="workspace_role.update",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=role_id,
        target_type="workspace_role",
    )
    updated = await _repo.get_workspace_role(conn, role_id)
    return updated  # type: ignore[return-value]


async def delete_workspace_role(
    conn: object,
    role_id: str,
    *,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> None:
    role = await _repo.get_workspace_role(conn, role_id)
    if role is None:
        raise AppError("WORKSPACE_ROLE_NOT_FOUND", f"Workspace role '{role_id}' not found.", 404)
    if role.get("is_system"):
        raise AppError("SYSTEM_ROLE_PROTECTED", "System roles cannot be deleted.", 403)

    await _repo.soft_delete_workspace_role(conn, role_id, actor_id=actor_id)
    await _audit.emit(
        conn,
        category="iam",
        action="workspace_role.delete",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=role_id,
        target_type="workspace_role",
    )


async def add_workspace_role_permission(
    conn: object,
    role_id: str,
    permission_id: str,
    *,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    role = await _repo.get_workspace_role(conn, role_id)
    if role is None:
        raise AppError("WORKSPACE_ROLE_NOT_FOUND", f"Workspace role '{role_id}' not found.", 404)

    perm = await _repo.get_permission_by_id(conn, permission_id)
    if perm is None:
        raise AppError("PERMISSION_NOT_FOUND", f"Permission '{permission_id}' not found.", 404)

    try:
        await _repo.add_workspace_role_permission(
            conn,
            id=_id_mod.uuid7(),
            workspace_role_id=role_id,
            permission_id=permission_id,
        )
    except Exception as exc:
        if "uq_iam_lnk_workspace_role_perms" in str(exc):
            raise AppError("PERMISSION_ALREADY_ASSIGNED", "Permission already assigned to this role.", 409) from exc
        raise

    await _audit.emit(
        conn,
        category="iam",
        action="workspace_role.permission.add",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=role_id,
        target_type="workspace_role",
    )
    perms_rows = await conn.fetch(  # type: ignore[union-attr]
        """
        SELECT p.id, p.resource, p.action, p.description, p.is_active
          FROM "03_iam"."40_lnk_workspace_role_permissions" lnk
          JOIN "03_iam"."10_fct_permissions" p ON p.id = lnk.permission_id
         WHERE lnk.workspace_role_id = $1
         ORDER BY p.resource, p.action
        """,
        role_id,
    )
    return {"role_id": role_id, "permissions": [dict(r) for r in perms_rows]}


async def remove_workspace_role_permission(
    conn: object,
    role_id: str,
    permission_id: str,
    *,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> None:
    role = await _repo.get_workspace_role(conn, role_id)
    if role is None:
        raise AppError("WORKSPACE_ROLE_NOT_FOUND", f"Workspace role '{role_id}' not found.", 404)

    deleted = await _repo.remove_workspace_role_permission(
        conn, workspace_role_id=role_id, permission_id=permission_id,
    )
    if not deleted:
        raise AppError("PERMISSION_NOT_FOUND", "Permission not assigned to this role.", 404)

    await _audit.emit(
        conn,
        category="iam",
        action="workspace_role.permission.remove",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=role_id,
        target_type="workspace_role",
    )


async def assign_user_workspace_role(
    conn: object,
    user_id: str,
    *,
    workspace_id: str,
    workspace_role_id: str,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    user = await _repo.get_user_by_id(conn, user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", f"User '{user_id}' not found.", 404)

    ws = await _repo.get_workspace_by_id(conn, workspace_id)
    if ws is None:
        raise AppError("WORKSPACE_NOT_FOUND", f"Workspace '{workspace_id}' not found.", 404)

    role = await _repo.get_workspace_role(conn, workspace_role_id)
    if role is None:
        raise AppError("WORKSPACE_ROLE_NOT_FOUND", f"Workspace role '{workspace_role_id}' not found.", 404)

    existing = await _repo.get_user_workspace_role_assignment(
        conn, user_id=user_id, workspace_id=workspace_id, workspace_role_id=workspace_role_id,
    )
    if existing and existing.get("is_active"):
        raise AppError("ROLE_ALREADY_ASSIGNED", "User already has this workspace role.", 409)

    assignment_id = _id_mod.uuid7()
    org_id = str(ws["org_id"])

    if existing and not existing.get("is_active"):
        await conn.execute(  # type: ignore[union-attr]
            """
            UPDATE "03_iam"."40_lnk_user_workspace_roles"
               SET is_active = true, granted_by = $4, granted_at = CURRENT_TIMESTAMP
             WHERE user_id = $1 AND workspace_id = $2 AND workspace_role_id = $3
            """,
            user_id, workspace_id, workspace_role_id, actor_id,
        )
        assignment_id = existing["id"]
    else:
        await _repo.assign_user_workspace_role(
            conn,
            id=assignment_id,
            user_id=user_id,
            org_id=org_id,
            workspace_id=workspace_id,
            workspace_role_id=workspace_role_id,
            granted_by=actor_id,
        )

    await _audit.emit(
        conn,
        category="iam",
        action="workspace_role.assign",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=user_id,
        target_type="iam_user",
    )
    return {
        "id": assignment_id,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "workspace_role_id": workspace_role_id,
        "is_active": True,
    }


async def revoke_user_workspace_role(
    conn: object,
    assignment_id: str,
    *,
    actor_id: str,
    session_id: str,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> None:
    revoked = await _repo.revoke_user_workspace_role(conn, assignment_id)
    if not revoked:
        raise AppError("ROLE_ASSIGNMENT_NOT_FOUND", "Workspace role assignment not found.", 404)

    await _audit.emit(
        conn,
        category="iam",
        action="workspace_role.revoke",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=assignment_id,
        target_type="workspace_role_assignment",
    )


# ---------------------------------------------------------------------------
# Runtime check
# ---------------------------------------------------------------------------

async def rbac_check(
    conn: object,
    *,
    user_id: str,
    resource: str,
    action: str,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict:
    """Return {allowed: bool} for a given user + resource + action + optional context."""
    user = await _repo.get_user_by_id(conn, user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", f"User '{user_id}' not found.", 404)

    allowed = await _repo.check_user_has_permission(
        conn,
        user_id=user_id,
        resource=resource,
        action=action,
        org_id=org_id,
        workspace_id=workspace_id,
    )
    return {"allowed": allowed, "user_id": user_id, "resource": resource, "action": action}


async def get_effective_permissions(
    conn: object,
    user_id: str,
    *,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict:
    """Return all permissions effective for a user in a given context."""
    user = await _repo.get_user_by_id(conn, user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", f"User '{user_id}' not found.", 404)

    perms = await _repo.get_effective_permissions(
        conn, user_id=user_id, org_id=org_id, workspace_id=workspace_id,
    )
    return {"user_id": user_id, "permissions": perms, "total": len(perms)}
