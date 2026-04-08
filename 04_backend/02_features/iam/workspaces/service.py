"""IAM workspaces service — CRUD with audit events."""

from __future__ import annotations

import importlib

_repo = importlib.import_module("04_backend.02_features.iam.workspaces.repository")
_id_mod = importlib.import_module("scripts.00_core._id")
_errors_mod = importlib.import_module("04_backend.01_core.errors")
_audit = importlib.import_module("04_backend.02_features.audit.service")

AppError = _errors_mod.AppError


async def list_workspaces(
    conn: object,
    *,
    limit: int = 50,
    offset: int = 0,
    org_id: str | None = None,
    is_active: bool | None = None,
) -> dict:
    items, total = await _repo.list_workspaces(
        conn, limit=limit, offset=offset, org_id=org_id, is_active=is_active
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


async def get_workspace(conn: object, workspace_id: str) -> dict:
    ws = await _repo.get_workspace(conn, workspace_id)
    if ws is None:
        raise AppError("WORKSPACE_NOT_FOUND", f"Workspace '{workspace_id}' not found.", 404)
    return ws


async def create_workspace(
    conn: object,
    *,
    org_id: str,
    name: str,
    slug: str,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    if await _repo.slug_exists_in_org(conn, org_id, slug):
        raise AppError("WORKSPACE_SLUG_CONFLICT", f"Slug '{slug}' already exists in this org.", 409)

    workspace_id = _id_mod.uuid7()

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.create_workspace(
            conn,
            workspace_id=workspace_id,
            org_id=org_id,
            name=name,
            slug=slug,
            actor_id=actor_id,
        )
        await _audit.emit(
            conn,
            category="iam",
            action="workspace.create",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=workspace_id,
            target_type="iam_workspace",
        )

    return await _repo.get_workspace(conn, workspace_id)


async def update_workspace(
    conn: object,
    workspace_id: str,
    *,
    name: str | None = None,
    slug: str | None = None,
    status_code: str | None = None,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    existing = await _repo.get_workspace(conn, workspace_id)
    if existing is None:
        raise AppError("WORKSPACE_NOT_FOUND", f"Workspace '{workspace_id}' not found.", 404)

    if slug is not None and slug != existing.get("slug"):
        if await _repo.slug_exists_in_org(conn, existing["org_id"], slug, exclude_id=workspace_id):
            raise AppError("WORKSPACE_SLUG_CONFLICT", f"Slug '{slug}' already exists in this org.", 409)

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.update_workspace(
            conn,
            workspace_id,
            name=name,
            slug=slug,
            status_code=status_code,
            actor_id=actor_id,
        )
        await _audit.emit(
            conn,
            category="iam",
            action="workspace.update",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=workspace_id,
            target_type="iam_workspace",
        )

    return await _repo.get_workspace(conn, workspace_id)


async def delete_workspace(
    conn: object,
    workspace_id: str,
    *,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> None:
    existing = await _repo.get_workspace(conn, workspace_id)
    if existing is None:
        raise AppError("WORKSPACE_NOT_FOUND", f"Workspace '{workspace_id}' not found.", 404)

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.delete_workspace(conn, workspace_id, actor_id=actor_id)
        await _audit.emit(
            conn,
            category="iam",
            action="workspace.delete",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=workspace_id,
            target_type="iam_workspace",
        )
