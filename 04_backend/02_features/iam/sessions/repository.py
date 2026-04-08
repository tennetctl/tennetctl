"""IAM session repository — raw SQL for login, refresh, logout.

EAV attr_def_id constants (seeded by migration 003 via INSERT...SELECT...JOIN):
  User attrs (entity_type_id=1):
    1 = password_hash
    2 = email
    3 = username
  Session attrs (entity_type_id=2):
    4 = jti
    5 = refresh
    6 = user_agent
    7 = ip_address
    8 = token_hash

NOTE: The migration uses a dynamic INSERT ... SELECT from VALUES with a JOIN,
so the IDENTITY sequence order depends on how Postgres processes the rows.
These IDs were verified against a live install; see 07_dim_attr_defs.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Login lookup
# ---------------------------------------------------------------------------

async def fetch_user_by_username(conn: object, username: str) -> dict | None:
    """Return (id, password_hash) for login verification.

    Uses the partial index on attr_def_id = 1 (username) for fast lookup.
    password_hash is fetched in the same query because login is the only
    place that needs it; v_users deliberately excludes it.
    """
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT
            u.id,
            u.account_type_id,
            u.is_active,
            u.deleted_at,
            ph.key_text  AS password_hash
        FROM "03_iam"."10_fct_users" u
        JOIN "03_iam"."20_dtl_attrs" un
               ON un.entity_id    = u.id
              AND un.attr_def_id  = 3
        LEFT JOIN "03_iam"."20_dtl_attrs" ph
               ON ph.entity_id    = u.id
              AND ph.attr_def_id  = 1
        WHERE un.key_text = $1
        """,
        username,
    )
    return dict(row) if row else None

# NOTE: attr_def_id=3 for username (verified from live DB: 1=password_hash, 2=email, 3=username)


# ---------------------------------------------------------------------------
# Session writes
# ---------------------------------------------------------------------------

async def insert_session(
    conn: object,
    *,
    id: str,
    user_id: str,
    status_id: int,
    token_prefix: str,
    expires_at: object,        # datetime
    absolute_expires_at: object,
    refresh_expires_at: object,
) -> None:
    """Create the session fact row."""
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."20_fct_sessions"
            (id, user_id, status_id, token_prefix,
             refresh_expires_at, expires_at, absolute_expires_at,
             created_by, updated_by, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $8,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        id,
        user_id,
        status_id,
        token_prefix,
        refresh_expires_at,
        expires_at,
        absolute_expires_at,
        user_id,  # created_by = user_id for normal login
    )


async def insert_session_attr(
    conn: object,
    *,
    id: str,
    entity_type_id: int,
    entity_id: str,
    attr_def_id: int,
    value: str,
) -> None:
    """Insert one EAV attribute row for a session."""
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."20_dtl_attrs"
            (id, entity_type_id, entity_id, attr_def_id,
             key_text, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        id,
        entity_type_id,
        entity_id,
        attr_def_id,
        value,
    )


async def update_session_refresh(
    conn: object,
    *,
    session_id: str,
    refresh_token_hash: str,
    refresh_token_prefix: str,
    refresh_expires_at: object,
) -> None:
    """Store a new refresh token hash after rotation."""
    await conn.execute(  # type: ignore[union-attr]
        """
        UPDATE "03_iam"."20_fct_sessions"
           SET refresh_token_hash   = $2,
               refresh_token_prefix = $3,
               refresh_expires_at   = $4,
               updated_at           = CURRENT_TIMESTAMP
         WHERE id = $1
        """,
        session_id,
        refresh_token_hash,
        refresh_token_prefix,
        refresh_expires_at,
    )


async def update_upsert_session_attr(
    conn: object,
    *,
    id: str,
    entity_type_id: int,
    entity_id: str,
    attr_def_id: int,
    value: str,
) -> None:
    """Upsert one EAV attribute for an existing session (used on refresh)."""
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."20_dtl_attrs"
            (id, entity_type_id, entity_id, attr_def_id,
             key_text, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (entity_id, attr_def_id)
        DO UPDATE SET key_text  = EXCLUDED.key_text,
                      updated_at = CURRENT_TIMESTAMP
        """,
        id,
        entity_type_id,
        entity_id,
        attr_def_id,
        value,
    )


# ---------------------------------------------------------------------------
# Session reads (for refresh + logout)
# ---------------------------------------------------------------------------

async def fetch_session_by_id(conn: object, session_id: str) -> dict | None:
    """Return session row (from v_sessions) or None."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, user_id, status, token_prefix,
               refresh_token_prefix, refresh_expires_at,
               expires_at, absolute_expires_at, last_seen_at,
               is_deleted, created_at, updated_at
          FROM "03_iam".v_sessions
         WHERE id = $1
        """,
        session_id,
    )
    return dict(row) if row else None


async def fetch_session_with_refresh_hash(conn: object, session_id: str) -> dict | None:
    """Fetch session including the raw refresh_token_hash for verify."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, user_id, status_id, refresh_token_hash,
               refresh_token_prefix, refresh_expires_at,
               expires_at, absolute_expires_at, is_active, deleted_at
          FROM "03_iam"."20_fct_sessions"
         WHERE id = $1
        """,
        session_id,
    )
    return dict(row) if row else None


async def fetch_active_session_by_jti(conn: object, jti: str) -> dict | None:
    """Return the session row for a given JTI (JWT ID), or None if revoked/missing.

    Used by require_auth to reject tokens whose sessions have been revoked.
    The JTI is stored in the EAV table (attr_def_id=4) and updated on every
    token refresh, so it always reflects the latest issued access token.
    """
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT s.id, s.user_id, s.status_id, s.is_active,
               s.deleted_at, s.absolute_expires_at
          FROM "03_iam"."20_fct_sessions" s
          JOIN "03_iam"."20_dtl_attrs" a
                 ON a.entity_id   = s.id
                AND a.attr_def_id = 4
         WHERE a.key_text = $1
           AND s.deleted_at IS NULL
           AND s.is_active  = TRUE
        """,
        jti,
    )
    return dict(row) if row else None


async def revoke_session(conn: object, session_id: str) -> None:
    """Soft-delete + revoke a session (status_id=2 = 'revoked')."""
    await conn.execute(  # type: ignore[union-attr]
        """
        UPDATE "03_iam"."20_fct_sessions"
           SET status_id  = 2,
               deleted_at = CURRENT_TIMESTAMP,
               is_active  = FALSE,
               updated_at = CURRENT_TIMESTAMP
         WHERE id = $1
        """,
        session_id,
    )


async def touch_session(conn: object, session_id: str) -> None:
    """Update last_seen_at for the session."""
    await conn.execute(  # type: ignore[union-attr]
        """
        UPDATE "03_iam"."20_fct_sessions"
           SET last_seen_at = CURRENT_TIMESTAMP,
               updated_at   = CURRENT_TIMESTAMP
         WHERE id = $1
        """,
        session_id,
    )
