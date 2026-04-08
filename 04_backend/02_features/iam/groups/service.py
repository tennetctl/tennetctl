"""IAM groups service — CRUD with audit events + member management."""

from __future__ import annotations

import importlib

_repo = importlib.import_module("04_backend.02_features.iam.groups.repository")
_id_mod = importlib.import_module("scripts.00_core._id")
_errors_mod = importlib.import_module("04_backend.01_core.errors")
_audit = importlib.import_module("04_backend.02_features.audit.service")
_iam_ids = importlib.import_module("04_backend.02_features.iam._iam_attr_ids")

AppError = _errors_mod.AppError


async def _write_group_attrs(
    conn: object,
    group_id: str,
    attrs: dict,
    entity_type_id: int,
    *,
    name: str | None = None,
    slug: str | None = None,
    description: str | None = None,
) -> None:
    """Write EAV attrs for a group. Only writes non-None values."""
    for attr_code, value in [("name", name), ("slug", slug), ("description", description)]:
        if value is not None:
            await _repo.upsert_group_attr(
                conn,
                id=_id_mod.uuid7(),
                entity_type_id=entity_type_id,
                entity_id=group_id,
                attr_def_id=attrs[attr_code],
                value=value,
            )


async def list_groups(
    conn: object,
    *,
    limit: int = 50,
    offset: int = 0,
    org_id: str | None = None,
) -> dict:
    items, total = await _repo.list_groups(
        conn, limit=limit, offset=offset, org_id=org_id
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


async def get_group(conn: object, group_id: str) -> dict:
    group = await _repo.get_group(conn, group_id)
    if group is None:
        raise AppError("GROUP_NOT_FOUND", f"Group '{group_id}' not found.", 404)
    return group


async def create_group(
    conn: object,
    *,
    name: str,
    slug: str,
    org_id: str,
    description: str | None = None,
    is_system: bool = False,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    # Check slug uniqueness within the org
    slug_taken = await _repo.check_slug_exists(conn, org_id, slug)
    if slug_taken:
        raise AppError(
            "GROUP_SLUG_CONFLICT",
            f"A group with slug '{slug}' already exists in this org.",
            409,
        )

    group_id = _id_mod.uuid7()
    attrs = await _iam_ids.iam_attr_ids(conn, "iam_group")
    entity_type_id = await _iam_ids.iam_entity_type_id(conn, "iam_group")

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.insert_group(
            conn,
            group_id=group_id,
            org_id=org_id,
            is_system=is_system,
            actor_id=actor_id,
        )
        await _write_group_attrs(
            conn,
            group_id,
            attrs,
            entity_type_id,
            name=name,
            slug=slug,
            description=description,
        )
        await _audit.emit(
            conn,
            category="iam",
            action="group.create",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=group_id,
            target_type="iam_group",
        )

    group = await _repo.get_group(conn, group_id)
    return group  # type: ignore[return-value]


async def update_group(
    conn: object,
    group_id: str,
    *,
    name: str | None = None,
    slug: str | None = None,
    description: str | None = None,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    existing = await _repo.get_group(conn, group_id)
    if existing is None:
        raise AppError("GROUP_NOT_FOUND", f"Group '{group_id}' not found.", 404)

    # If slug is being changed, check uniqueness
    if slug is not None and slug != existing.get("slug"):
        slug_taken = await _repo.check_slug_exists(conn, existing["org_id"], slug)
        if slug_taken:
            raise AppError(
                "GROUP_SLUG_CONFLICT",
                f"A group with slug '{slug}' already exists in this org.",
                409,
            )

    attrs = await _iam_ids.iam_attr_ids(conn, "iam_group")
    entity_type_id = await _iam_ids.iam_entity_type_id(conn, "iam_group")

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.update_group_meta(conn, group_id, actor_id=actor_id)
        await _write_group_attrs(
            conn,
            group_id,
            attrs,
            entity_type_id,
            name=name,
            slug=slug,
            description=description,
        )
        await _audit.emit(
            conn,
            category="iam",
            action="group.update",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=group_id,
            target_type="iam_group",
        )

    return await _repo.get_group(conn, group_id)  # type: ignore[return-value]


async def delete_group(
    conn: object,
    group_id: str,
    *,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> None:
    existing = await _repo.get_group(conn, group_id)
    if existing is None:
        raise AppError("GROUP_NOT_FOUND", f"Group '{group_id}' not found.", 404)

    # Idempotent: already deleted — no error, just return
    if existing.get("is_deleted"):
        return

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.soft_delete_group(conn, group_id, actor_id=actor_id)
        await _audit.emit(
            conn,
            category="iam",
            action="group.delete",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=group_id,
            target_type="iam_group",
        )


# ---------------------------------------------------------------------------
# Member management
# ---------------------------------------------------------------------------

async def list_members(
    conn: object,
    group_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    # Verify group exists
    group = await _repo.get_group(conn, group_id)
    if group is None:
        raise AppError("GROUP_NOT_FOUND", f"Group '{group_id}' not found.", 404)

    items, total = await _repo.list_members(conn, group_id, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


async def add_member(
    conn: object,
    group_id: str,
    user_id: str,
    *,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    # Verify group exists
    group = await _repo.get_group(conn, group_id)
    if group is None:
        raise AppError("GROUP_NOT_FOUND", f"Group '{group_id}' not found.", 404)

    # Verify user exists
    user_exists = await _repo.check_user_exists(conn, user_id)
    if not user_exists:
        raise AppError("USER_NOT_FOUND", f"User '{user_id}' not found.", 404)

    # Check if already an active member
    existing = await _repo.get_member(conn, group_id, user_id)
    if existing is not None:
        raise AppError(
            "MEMBER_ALREADY_EXISTS",
            f"User '{user_id}' is already a member of this group.",
            409,
        )

    member_id = _id_mod.uuid7()

    async with conn.transaction():  # type: ignore[union-attr]
        member = await _repo.insert_member(
            conn,
            member_id=member_id,
            group_id=group_id,
            user_id=user_id,
            added_by=actor_id,
        )
        await _audit.emit(
            conn,
            category="iam",
            action="group.member.add",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=group_id,
            target_type="iam_group",
        )

    return member


async def remove_member(
    conn: object,
    group_id: str,
    user_id: str,
    *,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> None:
    # Verify group exists
    group = await _repo.get_group(conn, group_id)
    if group is None:
        raise AppError("GROUP_NOT_FOUND", f"Group '{group_id}' not found.", 404)

    removed = await _repo.remove_member(conn, group_id, user_id)
    if not removed:
        raise AppError(
            "MEMBER_NOT_FOUND",
            f"User '{user_id}' is not an active member of this group.",
            404,
        )

    await _audit.emit(
        conn,
        category="iam",
        action="group.member.remove",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=group_id,
        target_type="iam_group",
    )


# ---------------------------------------------------------------------------
# Auto-create system groups for a new org
# ---------------------------------------------------------------------------

async def create_everyone_group(
    conn: object,
    org_id: str,
    *,
    actor_id: str,
    session_id: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    """Create the "everyone" system group for a newly created org.

    This is called by the orgs service after a successful org creation.
    The group is marked is_system=True and cannot be renamed/deleted by users.
    """
    return await create_group(
        conn,
        name="Everyone",
        slug="everyone",
        org_id=org_id,
        description="Automatically includes all members of this org.",
        is_system=True,
        actor_id=actor_id,
        session_id=session_id,
        org_id_audit=org_id,
        workspace_id_audit=workspace_id_audit,
    )
