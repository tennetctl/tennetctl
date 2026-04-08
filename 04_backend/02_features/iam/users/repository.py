"""IAM users repository — reads v_users, writes 10_fct_users + 20_dtl_attrs."""

from __future__ import annotations


async def fetch_user_by_id(conn: object, user_id: str) -> dict | None:
    """Return a single user from v_users or None."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, org_id, account_type, auth_type,
               username, email, is_active, is_deleted,
               created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_users
         WHERE id = $1
        """,
        user_id,
    )
    return dict(row) if row else None


async def fetch_users(conn: object, *, limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    """Return (page, total) from v_users, ordered by created_at desc."""
    rows = await conn.fetch(  # type: ignore[union-attr]
        """
        SELECT id, org_id, account_type, auth_type,
               username, email, is_active, is_deleted,
               created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_users
         ORDER BY created_at DESC
         LIMIT $1 OFFSET $2
        """,
        limit,
        offset,
    )
    total = await conn.fetchval(  # type: ignore[union-attr]
        'SELECT COUNT(*) FROM "03_iam".v_users'
    )
    return [dict(r) for r in rows], int(total)


async def update_user_is_active(conn: object, *, user_id: str, is_active: bool, actor_id: str) -> None:
    """Toggle is_active flag."""
    await conn.execute(  # type: ignore[union-attr]
        """
        UPDATE "03_iam"."10_fct_users"
           SET is_active  = $2,
               updated_by = $3,
               updated_at = CURRENT_TIMESTAMP
         WHERE id = $1
        """,
        user_id,
        is_active,
        actor_id,
    )


async def upsert_user_email(conn: object, *, attr_id: str, user_id: str, email: str) -> None:
    """Upsert the email EAV attribute for a user (attr_def_id=2)."""
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."20_dtl_attrs"
            (id, entity_type_id, entity_id, attr_def_id,
             key_text, created_at, updated_at)
        VALUES ($1, 1, $2, 2, $3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (entity_id, attr_def_id)
        DO UPDATE SET key_text   = EXCLUDED.key_text,
                      updated_at = CURRENT_TIMESTAMP
        """,
        attr_id,
        user_id,
        email,
    )
