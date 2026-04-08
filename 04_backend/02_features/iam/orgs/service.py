"""IAM orgs service — CRUD with audit events."""

from __future__ import annotations

import importlib

_repo = importlib.import_module("04_backend.02_features.iam.orgs.repository")
_id_mod = importlib.import_module("scripts.00_core._id")
_errors_mod = importlib.import_module("04_backend.01_core.errors")
_audit = importlib.import_module("04_backend.02_features.audit.service")
_groups_svc = importlib.import_module("04_backend.02_features.iam.groups.service")

AppError = _errors_mod.AppError


async def list_orgs(
    conn: object,
    *,
    limit: int = 50,
    offset: int = 0,
    is_active: bool | None = None,
) -> dict:
    items, total = await _repo.list_orgs(conn, limit=limit, offset=offset, is_active=is_active)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


async def get_org(conn: object, org_id: str) -> dict:
    org = await _repo.get_org(conn, org_id)
    if org is None:
        raise AppError("ORG_NOT_FOUND", f"Org '{org_id}' not found.", 404)
    return org


async def create_org(
    conn: object,
    *,
    name: str,
    slug: str,
    description: str | None = None,
    owner_id: str,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    org_id = _id_mod.uuid7()

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.create_org(
            conn,
            org_id=org_id,
            name=name,
            slug=slug,
            description=description,
            owner_id=owner_id,
            actor_id=actor_id,
        )
        await _audit.emit(
            conn,
            category="iam",
            action="org.create",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=org_id,
            target_type="iam_org",
        )
        # Auto-create the "everyone" system group for this org
        await _groups_svc.create_everyone_group(
            conn,
            org_id,
            actor_id=actor_id,
            session_id=session_id,
            workspace_id_audit=workspace_id_audit,
        )

    return await _repo.get_org(conn, org_id)


async def update_org(
    conn: object,
    org_id: str,
    *,
    name: str | None = None,
    slug: str | None = None,
    description: str | None = None,
    status_code: str | None = None,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    existing = await _repo.get_org(conn, org_id)
    if existing is None:
        raise AppError("ORG_NOT_FOUND", f"Org '{org_id}' not found.", 404)

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.update_org(
            conn,
            org_id,
            name=name,
            slug=slug,
            description=description,
            status_code=status_code,
            actor_id=actor_id,
        )
        await _audit.emit(
            conn,
            category="iam",
            action="org.update",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=org_id,
            target_type="iam_org",
        )

    return await _repo.get_org(conn, org_id)
