"""IAM memberships service — user-org and user-workspace memberships."""

from __future__ import annotations

import importlib

_repo = importlib.import_module("04_backend.02_features.iam.memberships.repository")
_errors_mod = importlib.import_module("04_backend.01_core.errors")
_audit = importlib.import_module("04_backend.02_features.audit.service")

AppError = _errors_mod.AppError


# ---------------------------------------------------------------------------
# Org memberships
# ---------------------------------------------------------------------------

async def list_user_orgs(
    conn: object,
    *,
    user_id: str,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    items, total = await _repo.list_user_orgs(conn, user_id=user_id, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


async def add_user_to_org(
    conn: object,
    *,
    user_id: str,
    org_id: str,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    async with conn.transaction():  # type: ignore[union-attr]
        membership_id = await _repo.create_user_org(
            conn, user_id=user_id, org_id=org_id, actor_id=actor_id
        )
        await _audit.emit(
            conn,
            category="iam",
            action="membership.org.add",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=membership_id,
            target_type="iam_user_org",
        )

    row = await _repo.get_user_org(conn, membership_id)
    return row  # type: ignore[return-value]


async def remove_user_from_org(
    conn: object,
    membership_id: str,
    *,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> None:
    row = await _repo.get_user_org(conn, membership_id)
    if row is None:
        raise AppError("MEMBERSHIP_NOT_FOUND", f"Org membership '{membership_id}' not found.", 404)

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.delete_user_org(conn, membership_id)
        await _audit.emit(
            conn,
            category="iam",
            action="membership.org.remove",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=membership_id,
            target_type="iam_user_org",
        )


# ---------------------------------------------------------------------------
# Workspace memberships
# ---------------------------------------------------------------------------

async def list_user_workspaces(
    conn: object,
    *,
    user_id: str,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    items, total = await _repo.list_user_workspaces(
        conn, user_id=user_id, limit=limit, offset=offset
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


async def add_user_to_workspace(
    conn: object,
    *,
    user_id: str,
    workspace_id: str,
    org_id: str,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    async with conn.transaction():  # type: ignore[union-attr]
        membership_id = await _repo.create_user_workspace(
            conn,
            user_id=user_id,
            workspace_id=workspace_id,
            org_id=org_id,
            actor_id=actor_id,
        )
        await _audit.emit(
            conn,
            category="iam",
            action="membership.workspace.add",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=membership_id,
            target_type="iam_user_workspace",
        )

    row = await _repo.get_user_workspace(conn, membership_id)
    return row  # type: ignore[return-value]


async def remove_user_from_workspace(
    conn: object,
    membership_id: str,
    *,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> None:
    row = await _repo.get_user_workspace(conn, membership_id)
    if row is None:
        raise AppError(
            "MEMBERSHIP_NOT_FOUND",
            f"Workspace membership '{membership_id}' not found.",
            404,
        )

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.delete_user_workspace(conn, membership_id)
        await _audit.emit(
            conn,
            category="iam",
            action="membership.workspace.remove",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=membership_id,
            target_type="iam_user_workspace",
        )
