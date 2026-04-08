"""IAM memberships repository — lnk_user_orgs and lnk_user_workspaces.

lnk_* tables are immutable: rows are inserted or hard-deleted only.
No updated_at column on lnk_* tables.
"""

from __future__ import annotations

import importlib

_id_mod = importlib.import_module("scripts.00_core._id")


# ---------------------------------------------------------------------------
# Org memberships
# ---------------------------------------------------------------------------

async def list_user_orgs(
    conn: object,
    *,
    user_id: str,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Return (page, total) of org memberships for a user."""
    rows = await conn.fetch(  # type: ignore[union-attr]
        """
        SELECT id, user_id, org_id, org_slug, org_name,
               org_status, org_is_active, created_by, created_at
          FROM "03_iam".v_user_orgs
         WHERE user_id = $1
         ORDER BY created_at ASC
         LIMIT $2 OFFSET $3
        """,
        user_id,
        limit,
        offset,
    )
    total = await conn.fetchval(  # type: ignore[union-attr]
        'SELECT COUNT(*) FROM "03_iam".v_user_orgs WHERE user_id = $1',
        user_id,
    )
    return [dict(r) for r in rows], int(total)


async def get_user_org(conn: object, membership_id: str) -> dict | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, user_id, org_id, created_by, created_at
          FROM "03_iam"."40_lnk_user_orgs"
         WHERE id = $1
        """,
        membership_id,
    )
    return dict(row) if row else None


async def create_user_org(
    conn: object,
    *,
    user_id: str,
    org_id: str,
    actor_id: str,
) -> str:
    """Insert user-org membership. Returns new row id."""
    membership_id = _id_mod.uuid7()
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."40_lnk_user_orgs"
            (id, org_id, user_id, created_by, created_at)
        VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
        """,
        membership_id,
        org_id,
        user_id,
        actor_id,
    )
    return membership_id


async def delete_user_org(conn: object, membership_id: str) -> None:
    """Hard-delete a user-org membership (lnk_* rows are immutable once inserted)."""
    await conn.execute(  # type: ignore[union-attr]
        'DELETE FROM "03_iam"."40_lnk_user_orgs" WHERE id = $1',
        membership_id,
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
) -> tuple[list[dict], int]:
    """Return (page, total) of workspace memberships for a user."""
    rows = await conn.fetch(  # type: ignore[union-attr]
        """
        SELECT id, user_id, workspace_id, org_id,
               workspace_slug, workspace_name,
               workspace_status, workspace_is_active,
               created_by, created_at
          FROM "03_iam".v_user_workspaces
         WHERE user_id = $1
         ORDER BY created_at ASC
         LIMIT $2 OFFSET $3
        """,
        user_id,
        limit,
        offset,
    )
    total = await conn.fetchval(  # type: ignore[union-attr]
        'SELECT COUNT(*) FROM "03_iam".v_user_workspaces WHERE user_id = $1',
        user_id,
    )
    return [dict(r) for r in rows], int(total)


async def get_user_workspace(conn: object, membership_id: str) -> dict | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, user_id, workspace_id, org_id, created_by, created_at
          FROM "03_iam"."40_lnk_user_workspaces"
         WHERE id = $1
        """,
        membership_id,
    )
    return dict(row) if row else None


async def create_user_workspace(
    conn: object,
    *,
    user_id: str,
    workspace_id: str,
    org_id: str,
    actor_id: str,
) -> str:
    """Insert user-workspace membership. Returns new row id."""
    membership_id = _id_mod.uuid7()
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."40_lnk_user_workspaces"
            (id, org_id, workspace_id, user_id, created_by, created_at)
        VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
        """,
        membership_id,
        org_id,
        workspace_id,
        user_id,
        actor_id,
    )
    return membership_id


async def delete_user_workspace(conn: object, membership_id: str) -> None:
    """Hard-delete a user-workspace membership."""
    await conn.execute(  # type: ignore[union-attr]
        'DELETE FROM "03_iam"."40_lnk_user_workspaces" WHERE id = $1',
        membership_id,
    )
