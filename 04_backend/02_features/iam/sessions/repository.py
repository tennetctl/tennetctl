"""IAM session repository — raw SQL for login, refresh, logout.

All attr_def_ids are resolved dynamically from 07_dim_attr_defs by code.
No hardcoded IDENTITY values anywhere in this file.

20_fct_sessions is pure-EAV: id, user_id, status_id, is_active, is_test,
deleted_at, created_by, updated_by, created_at, updated_at only.
All token/timing data lives in 20_dtl_attrs.
"""

from __future__ import annotations

import importlib

_iam_ids = importlib.import_module("04_backend.02_features.iam._iam_attr_ids")


# ---------------------------------------------------------------------------
# Login lookup
# ---------------------------------------------------------------------------

async def fetch_user_by_username(conn: object, username: str) -> dict | None:
    """Return (id, account_type_id, is_active, deleted_at, password_hash) for login.

    Resolves attr_def_ids by code so no hardcoded IDs are needed.
    password_hash deliberately excluded from v_users; fetched here only.
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
               ON un.entity_id   = u.id
              AND un.attr_def_id = (
                  SELECT d.id
                    FROM "03_iam"."07_dim_attr_defs" d
                    JOIN "03_iam"."06_dim_entity_types" et ON d.entity_type_id = et.id
                   WHERE et.code = 'iam_user' AND d.code = 'username'
              )
        LEFT JOIN "03_iam"."20_dtl_attrs" ph
               ON ph.entity_id   = u.id
              AND ph.attr_def_id = (
                  SELECT d.id
                    FROM "03_iam"."07_dim_attr_defs" d
                    JOIN "03_iam"."06_dim_entity_types" et ON d.entity_type_id = et.id
                   WHERE et.code = 'iam_user' AND d.code = 'password_hash'
              )
        WHERE un.key_text = $1
        """,
        username,
    )
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Session writes
# ---------------------------------------------------------------------------

async def insert_session(
    conn: object,
    *,
    id: str,
    user_id: str,
    status_id: int,
) -> None:
    """Create the session fact row (pure-EAV shape — no token columns)."""
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."20_fct_sessions"
            (id, user_id, status_id,
             created_by, updated_by, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $4,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        id,
        user_id,
        status_id,
        user_id,  # created_by = user_id for normal login
    )


async def upsert_session_attr(
    conn: object,
    *,
    id: str,
    entity_type_id: int,
    entity_id: str,
    attr_def_id: int,
    value: str,
) -> None:
    """Upsert one EAV attribute row for a session."""
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


# Keep old name as alias for backward compat with service.py usage
insert_session_attr = upsert_session_attr
update_upsert_session_attr = upsert_session_attr


# ---------------------------------------------------------------------------
# Session reads (for refresh + logout + auth middleware)
# ---------------------------------------------------------------------------

async def fetch_session_by_id(conn: object, session_id: str) -> dict | None:
    """Return session row (from v_sessions) or None."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, user_id, status,
               token_prefix, refresh_token_prefix,
               refresh_expires_at, expires_at, absolute_expires_at,
               last_seen_at, active_org_id, active_workspace_id,
               is_deleted, created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_sessions
         WHERE id = $1
        """,
        session_id,
    )
    return dict(row) if row else None


async def fetch_session_with_token_data(conn: object, session_id: str) -> dict | None:
    """Fetch session with refresh_token_hash EAV attr for verification."""
    fct_row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT s.id, s.user_id, s.status_id, s.is_active, s.deleted_at
          FROM "03_iam"."20_fct_sessions" s
         WHERE s.id = $1
        """,
        session_id,
    )
    if fct_row is None:
        return None

    result = dict(fct_row)

    # Fetch EAV attrs needed for refresh
    attr_rows = await conn.fetch(  # type: ignore[union-attr]
        """
        SELECT ad.code, a.key_text
          FROM "03_iam"."20_dtl_attrs" a
          JOIN "03_iam"."07_dim_attr_defs" ad ON ad.id = a.attr_def_id
         WHERE a.entity_id = $1
           AND ad.code IN (
               'refresh_token_hash', 'refresh_expires_at', 'absolute_expires_at'
           )
        """,
        session_id,
    )
    for r in attr_rows:
        result[r["code"]] = r["key_text"]

    # Parse timestamps
    import datetime as dt  # noqa: PLC0415
    for col in ("refresh_expires_at", "absolute_expires_at"):
        val = result.get(col)
        if val and isinstance(val, str):
            result[col] = dt.datetime.fromisoformat(val)

    return result


# Keep old name for backward compat
async def fetch_session_with_refresh_hash(conn: object, session_id: str) -> dict | None:
    return await fetch_session_with_token_data(conn, session_id)


async def fetch_active_session_by_jti(conn: object, jti: str) -> dict | None:
    """Return the session row for a given JTI (JWT ID), or None if revoked/missing.

    Used by require_auth to reject tokens whose sessions have been revoked.
    Resolves the jti attr_def_id by code — no hardcoded ID.
    """
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT s.id, s.user_id, s.status_id, s.is_active,
               s.deleted_at,
               abs_exp.key_text::timestamp AS absolute_expires_at
          FROM "03_iam"."20_fct_sessions" s
          JOIN "03_iam"."20_dtl_attrs" jti_attr
                 ON jti_attr.entity_id   = s.id
                AND jti_attr.attr_def_id = (
                    SELECT d.id
                      FROM "03_iam"."07_dim_attr_defs" d
                      JOIN "03_iam"."06_dim_entity_types" et ON d.entity_type_id = et.id
                     WHERE et.code = 'iam_session' AND d.code = 'jti'
                )
          LEFT JOIN "03_iam"."20_dtl_attrs" abs_exp
                 ON abs_exp.entity_id   = s.id
                AND abs_exp.attr_def_id = (
                    SELECT d.id
                      FROM "03_iam"."07_dim_attr_defs" d
                      JOIN "03_iam"."06_dim_entity_types" et ON d.entity_type_id = et.id
                     WHERE et.code = 'iam_session' AND d.code = 'absolute_expires_at'
                )
         WHERE jti_attr.key_text = $1
           AND s.deleted_at IS NULL
           AND s.is_active  = TRUE
        """,
        jti,
    )
    return dict(row) if row else None


async def revoke_session(conn: object, session_id: str) -> None:
    """Soft-delete + revoke a session (status_id resolved by code)."""
    await conn.execute(  # type: ignore[union-attr]
        """
        UPDATE "03_iam"."20_fct_sessions"
           SET status_id  = (
               SELECT id FROM "03_iam"."08_dim_session_statuses" WHERE code = 'revoked'
           ),
               deleted_at = CURRENT_TIMESTAMP,
               is_active  = FALSE,
               updated_at = CURRENT_TIMESTAMP
         WHERE id = $1
        """,
        session_id,
    )


async def revoke_all_sessions_for_user(
    conn: object,
    *,
    user_id: str,
    except_session_id: str | None = None,
) -> list[str]:
    """Revoke every active session belonging to the given user.

    If except_session_id is set, that session is left alone (useful when the
    user is calling this endpoint and wants to keep their current session).

    Returns the list of session IDs that were revoked (for audit emission).
    """
    if except_session_id is None:
        rows = await conn.fetch(  # type: ignore[union-attr]
            """
            UPDATE "03_iam"."20_fct_sessions"
               SET status_id  = (
                   SELECT id FROM "03_iam"."08_dim_session_statuses" WHERE code = 'revoked'
               ),
                   deleted_at = CURRENT_TIMESTAMP,
                   is_active  = FALSE,
                   updated_at = CURRENT_TIMESTAMP
             WHERE user_id   = $1
               AND is_active = TRUE
               AND deleted_at IS NULL
            RETURNING id
            """,
            user_id,
        )
    else:
        rows = await conn.fetch(  # type: ignore[union-attr]
            """
            UPDATE "03_iam"."20_fct_sessions"
               SET status_id  = (
                   SELECT id FROM "03_iam"."08_dim_session_statuses" WHERE code = 'revoked'
               ),
                   deleted_at = CURRENT_TIMESTAMP,
                   is_active  = FALSE,
                   updated_at = CURRENT_TIMESTAMP
             WHERE user_id   = $1
               AND id       <> $2
               AND is_active = TRUE
               AND deleted_at IS NULL
            RETURNING id
            """,
            user_id,
            except_session_id,
        )
    return [r["id"] for r in rows]


async def touch_session(conn: object, session_id: str) -> None:
    """Update last_seen_at EAV attr for the session."""
    import datetime as dt  # noqa: PLC0415
    _id_mod = importlib.import_module("scripts.00_core._id")
    attrs = await _iam_ids.iam_attr_ids(conn, "iam_session")
    entity_type_id = await _iam_ids.iam_entity_type_id(conn, "iam_session")

    attr_def_id = attrs["last_seen_at"]
    now_str = dt.datetime.utcnow().isoformat(timespec="seconds")

    await upsert_session_attr(
        conn,
        id=_id_mod.uuid7(),
        entity_type_id=entity_type_id,
        entity_id=session_id,
        attr_def_id=attr_def_id,
        value=now_str,
    )


async def set_active_scope(
    conn: object,
    session_id: str,
    org_id: str,
    workspace_id: str,
) -> None:
    """Set active_org_id and active_workspace_id EAV attrs on a session."""
    _id_mod = importlib.import_module("scripts.00_core._id")
    attrs = await _iam_ids.iam_attr_ids(conn, "iam_session")
    entity_type_id = await _iam_ids.iam_entity_type_id(conn, "iam_session")

    for attr_code, value in (
        ("active_org_id", org_id),
        ("active_workspace_id", workspace_id),
    ):
        await upsert_session_attr(
            conn,
            id=_id_mod.uuid7(),
            entity_type_id=entity_type_id,
            entity_id=session_id,
            attr_def_id=attrs[attr_code],
            value=value,
        )


async def get_active_scope(conn: object, session_id: str) -> dict:
    """Return {org_id, workspace_id} for the session's current active scope."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT
            MAX(CASE WHEN ad.code = 'active_org_id'       THEN a.key_text END) AS org_id,
            MAX(CASE WHEN ad.code = 'active_workspace_id' THEN a.key_text END) AS workspace_id
          FROM "03_iam"."20_dtl_attrs" a
          JOIN "03_iam"."07_dim_attr_defs" ad ON ad.id = a.attr_def_id
         WHERE a.entity_id = $1
           AND ad.code IN ('active_org_id', 'active_workspace_id')
        """,
        session_id,
    )
    if row is None:
        return {"org_id": None, "workspace_id": None}
    return {"org_id": row["org_id"], "workspace_id": row["workspace_id"]}
