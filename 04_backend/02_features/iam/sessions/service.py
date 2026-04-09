"""IAM session service — login, token refresh, logout, me."""

from __future__ import annotations

import importlib
from datetime import datetime, timezone

_repo = importlib.import_module("04_backend.02_features.iam.sessions.repository")
_user_repo = importlib.import_module("04_backend.02_features.iam.users.repository")
_password = importlib.import_module("04_backend.02_features.iam.auth.password")
_jwt = importlib.import_module("04_backend.01_core.jwt_utils")
_id_mod = importlib.import_module("scripts.00_core._id")
_errors_mod = importlib.import_module("04_backend.01_core.errors")
_settings = importlib.import_module("04_backend.01_core.settings")
_audit = importlib.import_module("04_backend.02_features.audit.service")
_iam_ids = importlib.import_module("04_backend.02_features.iam._iam_attr_ids")

AppError = _errors_mod.AppError


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _access_ttl() -> int:
    return _settings.get_int("03_iam", "jwt_access_ttl_seconds", default=900)


def _refresh_ttl() -> int:
    return _settings.get_int("03_iam", "jwt_refresh_ttl_seconds", default=604800)


def _absolute_ttl() -> int:
    return _settings.get_int("03_iam", "session_absolute_ttl_seconds", default=2592000)


async def _resolve_session_status_id(conn: object, code: str) -> int:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        "SELECT id FROM \"03_iam\".\"08_dim_session_statuses\" WHERE code = $1",
        code,
    )
    if row is None:
        raise ValueError(f"Unknown session status: {code!r}")
    return int(row["id"])


async def _get_first_membership(conn: object, user_id: str) -> tuple[str | None, str | None]:
    """Return (org_id, workspace_id) for the user's first org/workspace membership.

    Returns (None, None) if the user has no memberships yet.
    """
    org_row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT org_id FROM "03_iam"."40_lnk_user_orgs"
         WHERE user_id = $1
         ORDER BY created_at ASC
         LIMIT 1
        """,
        user_id,
    )
    if org_row is None:
        return None, None

    org_id = str(org_row["org_id"])

    ws_row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT workspace_id FROM "03_iam"."40_lnk_user_workspaces"
         WHERE user_id = $1 AND org_id = $2
         ORDER BY created_at ASC
         LIMIT 1
        """,
        user_id,
        org_id,
    )
    workspace_id = str(ws_row["workspace_id"]) if ws_row else None
    return org_id, workspace_id


async def login(
    conn: object,
    *,
    username: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    """Authenticate credentials and create a new session.

    Returns:
        {access_token, refresh_token, expires_in, session_id}

    Raises:
        AppError(401) on bad credentials.
        AppError(403) on inactive or deleted user.
    """
    access_ttl: int = _access_ttl()
    refresh_ttl: int = _refresh_ttl()
    absolute_ttl: int = _absolute_ttl()

    user = await _repo.fetch_user_by_username(conn, username)
    if user is None:
        raise AppError("INVALID_CREDENTIALS", "Username or password incorrect.", 401)

    if user["deleted_at"] is not None or not user["is_active"]:
        raise AppError("ACCOUNT_DISABLED", "Account is disabled.", 403)

    if not _password.verify_password(user["password_hash"] or "", password):
        raise AppError("INVALID_CREDENTIALS", "Username or password incorrect.", 401)

    user_id: str = user["id"]
    session_id = _id_mod.uuid7()

    # Resolve first membership for active scope
    org_id, workspace_id = await _get_first_membership(conn, user_id)

    # Issue access token — embed session_id as "sid", org/workspace scope
    access_token = await _jwt.issue_token(
        user_id,
        access_ttl,
        session_id=session_id,
        org_id=org_id,
        workspace_id=workspace_id,
    )
    access_payload = _jwt.verify_token(access_token)
    jti: str = access_payload["jti"]

    raw_refresh = _jwt.generate_refresh_token()
    refresh_hash = _password.hash_token(raw_refresh)

    now = _utcnow()
    import datetime as dt  # noqa: PLC0415
    expires_at = now + dt.timedelta(seconds=access_ttl)
    refresh_expires_at = now + dt.timedelta(seconds=refresh_ttl)
    absolute_expires_at = now + dt.timedelta(seconds=absolute_ttl)

    # Resolve dim IDs by code
    session_status_active = await _resolve_session_status_id(conn, "active")
    attrs = await _iam_ids.iam_attr_ids(conn, "iam_session")
    entity_type_id = await _iam_ids.iam_entity_type_id(conn, "iam_session")

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.insert_session(
            conn,
            id=session_id,
            user_id=user_id,
            status_id=session_status_active,
        )

        # Store all session attributes via EAV
        token_prefix = access_token[:16]
        refresh_prefix = raw_refresh[:16]

        eav_entries = [
            ("jti", jti),
            ("token_prefix", token_prefix),
            ("refresh_token_hash", refresh_hash),
            ("refresh_token_prefix", refresh_prefix),
            ("refresh_expires_at", refresh_expires_at.isoformat(timespec="seconds")),
            ("expires_at", expires_at.isoformat(timespec="seconds")),
            ("absolute_expires_at", absolute_expires_at.isoformat(timespec="seconds")),
        ]
        if ip_address:
            eav_entries.append(("ip_address", ip_address))
        if user_agent:
            eav_entries.append(("user_agent", user_agent))
        if org_id:
            eav_entries.append(("active_org_id", org_id))
        if workspace_id:
            eav_entries.append(("active_workspace_id", workspace_id))

        for attr_code, value in eav_entries:
            await _repo.upsert_session_attr(
                conn,
                id=_id_mod.uuid7(),
                entity_type_id=entity_type_id,
                entity_id=session_id,
                attr_def_id=attrs[attr_code],
                value=value,
            )

        await _audit.emit(
            conn,
            category="iam",
            action="session.login",
            outcome="success",
            user_id=user_id,
            session_id=session_id,
            org_id=org_id,
            workspace_id=workspace_id,
            target_id=session_id,
            target_type="iam_session",
            ip_address=ip_address,
            user_agent=user_agent,
        )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": raw_refresh,
        "expires_in": access_ttl,
        "session_id": session_id,
    }


async def refresh(
    conn: object,
    *,
    session_id: str,
    refresh_token: str,
) -> dict:
    """Rotate the refresh token and issue a new access token.

    Raises:
        AppError(401) on invalid session or token.
        AppError(403) on expired or revoked session.
    """
    session = await _repo.fetch_session_with_token_data(conn, session_id)
    if session is None or session.get("deleted_at") is not None:
        raise AppError("SESSION_NOT_FOUND", "Session not found.", 401)

    if not session["is_active"]:
        raise AppError("SESSION_REVOKED", "Session has been revoked.", 401)

    if not _password.verify_token_hash(session.get("refresh_token_hash") or "", refresh_token):
        raise AppError("INVALID_REFRESH_TOKEN", "Refresh token is invalid.", 401)

    now = _utcnow()
    ref_exp = session.get("refresh_expires_at")
    if ref_exp is not None and ref_exp < now:
        raise AppError("REFRESH_TOKEN_EXPIRED", "Refresh token has expired.", 401)

    abs_exp = session.get("absolute_expires_at")
    if abs_exp is not None and abs_exp < now:
        raise AppError("SESSION_EXPIRED", "Session absolute TTL exceeded. Please log in again.", 401)

    user_id: str = session["user_id"]

    # Fetch current active scope to embed in new token
    scope = await _repo.get_active_scope(conn, session_id)
    org_id = scope.get("org_id")
    workspace_id = scope.get("workspace_id")

    access_ttl: int = _access_ttl()
    refresh_ttl: int = _refresh_ttl()

    access_token = await _jwt.issue_token(
        user_id,
        access_ttl,
        session_id=session_id,
        org_id=org_id,
        workspace_id=workspace_id,
    )
    access_payload = _jwt.verify_token(access_token)
    new_jti: str = access_payload["jti"]

    raw_refresh = _jwt.generate_refresh_token()
    new_refresh_hash = _password.hash_token(raw_refresh)
    token_prefix = access_token[:16]
    refresh_prefix = raw_refresh[:16]

    import datetime as dt  # noqa: PLC0415
    new_refresh_expires_at = now + dt.timedelta(seconds=refresh_ttl)

    attrs = await _iam_ids.iam_attr_ids(conn, "iam_session")
    entity_type_id = await _iam_ids.iam_entity_type_id(conn, "iam_session")

    async with conn.transaction():  # type: ignore[union-attr]
        # Update fct row updated_at
        await conn.execute(  # type: ignore[union-attr]
            """
            UPDATE "03_iam"."20_fct_sessions"
               SET updated_at = CURRENT_TIMESTAMP
             WHERE id = $1
            """,
            session_id,
        )

        eav_updates = [
            ("jti", new_jti),
            ("token_prefix", token_prefix),
            ("refresh_token_hash", new_refresh_hash),
            ("refresh_token_prefix", refresh_prefix),
            ("refresh_expires_at", new_refresh_expires_at.isoformat(timespec="seconds")),
        ]
        for attr_code, value in eav_updates:
            await _repo.upsert_session_attr(
                conn,
                id=_id_mod.uuid7(),
                entity_type_id=entity_type_id,
                entity_id=session_id,
                attr_def_id=attrs[attr_code],
                value=value,
            )

        await _audit.emit(
            conn,
            category="iam",
            action="session.refresh",
            outcome="success",
            user_id=user_id,
            session_id=session_id,
            org_id=org_id,
            workspace_id=workspace_id,
            target_id=session_id,
            target_type="iam_session",
        )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": raw_refresh,
        "expires_in": access_ttl,
        "session_id": session_id,
    }


async def get_me(conn: object, *, user_id: str, session_id: str) -> dict:
    """Return user profile and session ID from a validated token.

    Raises:
        AppError(404) if the user no longer exists.
    """
    user = await _user_repo.fetch_user_by_id(conn, user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", f"User '{user_id}' not found.", 404)

    await _repo.touch_session(conn, session_id)

    return {
        "user_id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "account_type": user["account_type"],
        "session_id": session_id,
    }


async def logout(conn: object, *, session_id: str, actor_id: str) -> None:
    """Revoke the session (soft-delete).

    Raises:
        AppError(404) if session not found.
        AppError(403) if actor is not the session owner.
    """
    session = await _repo.fetch_session_by_id(conn, session_id)
    if session is None:
        raise AppError("SESSION_NOT_FOUND", "Session not found.", 404)

    if session["user_id"] != actor_id:
        raise AppError("FORBIDDEN", "You cannot revoke another user's session.", 403)

    # Fetch scope for audit
    scope = await _repo.get_active_scope(conn, session_id)

    await _repo.revoke_session(conn, session_id)
    await _audit.emit(
        conn,
        category="iam",
        action="session.logout",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=scope.get("org_id"),
        workspace_id=scope.get("workspace_id"),
        target_id=session_id,
        target_type="iam_session",
    )


async def logout_all(
    conn: object,
    *,
    actor_id: str,
    current_session_id: str,
    keep_current: bool = True,
) -> dict:
    """Revoke every active session belonging to actor_id.

    If keep_current is True, the caller's current session is preserved so they
    don't immediately lock themselves out of the request that is in flight.
    Emits one audit event per revoked session.

    Returns: {"revoked_count": N}
    """
    except_id = current_session_id if keep_current else None
    revoked_ids = await _repo.revoke_all_sessions_for_user(
        conn,
        user_id=actor_id,
        except_session_id=except_id,
    )
    scope = await _repo.get_active_scope(conn, current_session_id)
    for sid in revoked_ids:
        await _audit.emit(
            conn,
            category="iam",
            action="session.logout",
            outcome="success",
            user_id=actor_id,
            session_id=current_session_id,
            org_id=scope.get("org_id"),
            workspace_id=scope.get("workspace_id"),
            target_id=sid,
            target_type="iam_session",
        )
    return {"revoked_count": len(revoked_ids)}


async def switch_scope(
    conn: object,
    session_id: str,
    org_id: str,
    workspace_id: str,
    *,
    user_id: str,
    session_id_audit: str,
) -> None:
    """Switch the active org/workspace scope for a session.

    Args:
        conn:             asyncpg connection.
        session_id:       The session to update.
        org_id:           New active org ID.
        workspace_id:     New active workspace ID.
        user_id:          Actor performing the switch (for audit).
        session_id_audit: Session ID for audit (usually same as session_id).
    """
    await _repo.set_active_scope(conn, session_id, org_id, workspace_id)
    await _audit.emit(
        conn,
        category="iam",
        action="session.switch_scope",
        outcome="success",
        user_id=user_id,
        session_id=session_id_audit,
        org_id=org_id,
        workspace_id=workspace_id,
        target_id=session_id,
        target_type="iam_session",
    )
