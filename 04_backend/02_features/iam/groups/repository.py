"""IAM groups repository — raw SQL for group CRUD + member management.

All attr_def_ids are resolved dynamically from 07_dim_attr_defs by code.
No hardcoded IDENTITY values anywhere in this file.

10_fct_groups is pure-EAV: id, org_id, is_system, is_active, deleted_at,
created_by, updated_by, created_at, updated_at only.
All name/slug/description data lives in 20_dtl_attrs.
"""

from __future__ import annotations

import importlib

_iam_ids = importlib.import_module("04_backend.02_features.iam._iam_attr_ids")
_id_mod = importlib.import_module("scripts.00_core._id")


# ---------------------------------------------------------------------------
# Group reads
# ---------------------------------------------------------------------------

async def list_groups(
    conn: object,
    *,
    limit: int = 50,
    offset: int = 0,
    org_id: str | None = None,
    include_deleted: bool = False,
) -> tuple[list[dict], int]:
    """Return (page, total) from v_groups."""
    conditions = []
    params: list = [limit, offset]

    if org_id is not None:
        params.append(org_id)
        conditions.append(f"org_id = ${len(params)}")

    if not include_deleted:
        conditions.append("is_deleted = FALSE")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = await conn.fetch(  # type: ignore[union-attr]
        f"""
        SELECT id, org_id, name, slug, description,
               is_system, is_active, is_deleted, member_count,
               created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_groups
          {where}
         ORDER BY created_at DESC
         LIMIT $1 OFFSET $2
        """,
        *params,
    )
    filter_params = params[2:]
    count_conditions = []
    param_idx = 1
    count_params = []
    if org_id is not None:
        count_conditions.append(f"org_id = ${param_idx}")
        count_params.append(org_id)
        param_idx += 1
    if not include_deleted:
        count_conditions.append("is_deleted = FALSE")
    count_where = ("WHERE " + " AND ".join(count_conditions)) if count_conditions else ""

    total = await conn.fetchval(  # type: ignore[union-attr]
        f'SELECT COUNT(*) FROM "03_iam".v_groups {count_where}',
        *count_params,
    )
    return [dict(r) for r in rows], int(total)


async def get_group(conn: object, group_id: str) -> dict | None:
    """Return a single group from v_groups or None."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, org_id, name, slug, description,
               is_system, is_active, is_deleted, member_count,
               created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_groups
         WHERE id = $1
        """,
        group_id,
    )
    return dict(row) if row else None


async def check_slug_exists(conn: object, org_id: str, slug: str) -> bool:
    """Check if a slug already exists within the given org (active groups only)."""
    count = await conn.fetchval(  # type: ignore[union-attr]
        """
        SELECT COUNT(*)
          FROM "03_iam".v_groups
         WHERE org_id = $1
           AND slug = $2
           AND is_deleted = FALSE
        """,
        org_id,
        slug,
    )
    return int(count) > 0


async def check_user_exists(conn: object, user_id: str) -> bool:
    """Check if a user exists and is not deleted."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id FROM "03_iam"."10_fct_users"
         WHERE id = $1 AND deleted_at IS NULL
        """,
        user_id,
    )
    return row is not None


# ---------------------------------------------------------------------------
# Group writes
# ---------------------------------------------------------------------------

async def insert_group(
    conn: object,
    *,
    group_id: str,
    org_id: str,
    is_system: bool,
    actor_id: str,
) -> None:
    """Insert the group fact row (pure-EAV shape)."""
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."10_fct_groups"
            (id, org_id, is_system, created_by, updated_by, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $4, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        group_id,
        org_id,
        is_system,
        actor_id,
    )


async def upsert_group_attr(
    conn: object,
    *,
    id: str,
    entity_type_id: int,
    entity_id: str,
    attr_def_id: int,
    value: str,
) -> None:
    """Upsert one EAV attribute row for a group."""
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."20_dtl_attrs"
            (id, entity_type_id, entity_id, attr_def_id,
             key_text, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (entity_id, attr_def_id)
        DO UPDATE SET key_text   = EXCLUDED.key_text,
                      updated_at = CURRENT_TIMESTAMP
        """,
        id,
        entity_type_id,
        entity_id,
        attr_def_id,
        value,
    )


async def update_group_meta(
    conn: object,
    group_id: str,
    *,
    actor_id: str,
) -> None:
    """Touch updated_by/updated_at on the fct row."""
    await conn.execute(  # type: ignore[union-attr]
        """
        UPDATE "03_iam"."10_fct_groups"
           SET updated_by = $2,
               updated_at = CURRENT_TIMESTAMP
         WHERE id = $1
        """,
        group_id,
        actor_id,
    )


async def soft_delete_group(conn: object, group_id: str, *, actor_id: str) -> None:
    """Soft-delete a group."""
    await conn.execute(  # type: ignore[union-attr]
        """
        UPDATE "03_iam"."10_fct_groups"
           SET deleted_at = CURRENT_TIMESTAMP,
               is_active  = FALSE,
               updated_by = $2,
               updated_at = CURRENT_TIMESTAMP
         WHERE id = $1
        """,
        group_id,
        actor_id,
    )


# ---------------------------------------------------------------------------
# Member reads
# ---------------------------------------------------------------------------

async def list_members(
    conn: object,
    group_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
    active_only: bool = True,
) -> tuple[list[dict], int]:
    """Return (page, total) of group members from v_group_members."""
    conditions = [f"group_id = $3"]
    params: list = [limit, offset, group_id]

    if active_only:
        conditions.append("is_active = TRUE")

    where = "WHERE " + " AND ".join(conditions)

    rows = await conn.fetch(  # type: ignore[union-attr]
        f"""
        SELECT id, group_id, user_id, added_by, is_active, added_at, username, email
          FROM "03_iam".v_group_members
          {where}
         ORDER BY added_at ASC
         LIMIT $1 OFFSET $2
        """,
        *params,
    )

    count_where = "WHERE group_id = $1" + (" AND is_active = TRUE" if active_only else "")
    total = await conn.fetchval(  # type: ignore[union-attr]
        f'SELECT COUNT(*) FROM "03_iam".v_group_members {count_where}',
        group_id,
    )
    return [dict(r) for r in rows], int(total)


async def get_member(conn: object, group_id: str, user_id: str) -> dict | None:
    """Return the membership row or None."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, group_id, user_id, added_by, is_active, added_at
          FROM "03_iam"."40_lnk_group_members"
         WHERE group_id = $1 AND user_id = $2 AND is_active = TRUE
        """,
        group_id,
        user_id,
    )
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Member writes
# ---------------------------------------------------------------------------

async def insert_member(
    conn: object,
    *,
    member_id: str,
    group_id: str,
    user_id: str,
    added_by: str,
) -> dict:
    """Insert a group membership row. Raises if duplicate (unique constraint)."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."40_lnk_group_members"
            (id, group_id, user_id, added_by, is_active, added_at)
        VALUES ($1, $2, $3, $4, TRUE, CURRENT_TIMESTAMP)
        RETURNING id, group_id, user_id, added_by, is_active, added_at
        """,
        member_id,
        group_id,
        user_id,
        added_by,
    )
    return dict(row)  # type: ignore[arg-type]


async def remove_member(conn: object, group_id: str, user_id: str) -> bool:
    """Soft-remove a member (is_active = FALSE). Returns True if a row was updated."""
    result = await conn.execute(  # type: ignore[union-attr]
        """
        UPDATE "03_iam"."40_lnk_group_members"
           SET is_active = FALSE
         WHERE group_id = $1 AND user_id = $2 AND is_active = TRUE
        """,
        group_id,
        user_id,
    )
    return result != "UPDATE 0"
