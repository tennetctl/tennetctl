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

AppError = _errors_mod.AppError

# Dim ID constants — verified from live DB against 07_dim_attr_defs:
#   entity_type_id: 1=iam_user, 2=iam_session
#   session attr_def_ids: 4=jti, 5=refresh, 6=user_agent, 7=ip_address, 8=token_hash
_SESSION_ENTITY_TYPE_ID = 2   # iam_session
_STATUS_ACTIVE = 1             # 08_dim_session_statuses.active
_ATTR_TOKEN_HASH = 8           # token_hash
_ATTR_IP_ADDRESS = 7           # ip_address
_ATTR_USER_AGENT = 6           # user_agent
_ATTR_REFRESH = 5              # refresh (JTI of refresh token)
_ATTR_JTI = 4                  # jti (JWT ID of access token)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _access_ttl() -> int:
    return _settings.get_int("03_iam", "jwt_access_ttl_seconds", default=900)


def _refresh_ttl() -> int:
    return _settings.get_int("03_iam", "jwt_refresh_ttl_seconds", default=604800)


def _absolute_ttl() -> int:
    return _settings.get_int("03_iam", "session_absolute_ttl_seconds", default=2592000)


async def login(
    conn: object,
    *,
    username: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    """Authenticate credentials and create a new session.

    TTLs are read from the settings table (seeded by Phase 4). Hardcoded
    defaults are used only if the settings table is not yet populated.

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

    # Issue access token — session_id is embedded as "sid" claim so routes
    # have it without an extra DB lookup.
    access_token = await _jwt.issue_token(user_id, access_ttl, session_id=session_id)
    access_payload = _jwt.verify_token(access_token)
    jti: str = access_payload["jti"]

    # Refresh token = opaque random string, stored as BLAKE2b-256 hash.
    # BLAKE2b is appropriate here because the token is a 40-byte CSPRNG value,
    # not a user password. Argon2id's GPU-hardening is unnecessary overhead.
    raw_refresh = _jwt.generate_refresh_token()
    refresh_hash = _password.hash_token(raw_refresh)

    now = _utcnow()
    import datetime as dt  # noqa: PLC0415
    expires_at = now + dt.timedelta(seconds=access_ttl)
    refresh_expires_at = now + dt.timedelta(seconds=refresh_ttl)
    absolute_expires_at = now + dt.timedelta(seconds=absolute_ttl)
    token_prefix = access_token[:16]
    refresh_prefix = raw_refresh[:16]

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.insert_session(
            conn,
            id=session_id,
            user_id=user_id,
            status_id=_STATUS_ACTIVE,
            token_prefix=token_prefix,
            expires_at=expires_at,
            absolute_expires_at=absolute_expires_at,
            refresh_expires_at=refresh_expires_at,
        )
        # Store refresh hash on fct row
        await _repo.update_session_refresh(
            conn,
            session_id=session_id,
            refresh_token_hash=refresh_hash,
            refresh_token_prefix=refresh_prefix,
            refresh_expires_at=refresh_expires_at,
        )
        # EAV attrs
        for attr_id, value in (
            (_ATTR_JTI, jti),
            (_ATTR_IP_ADDRESS, ip_address or ""),
            (_ATTR_USER_AGENT, user_agent or ""),
        ):
            if value:
                await _repo.insert_session_attr(
                    conn,
                    id=_id_mod.uuid7(),
                    entity_type_id=_SESSION_ENTITY_TYPE_ID,
                    entity_id=session_id,
                    attr_def_id=attr_id,
                    value=value,
                )
        await _audit.emit(
            conn,
            category="iam",
            action="session.login",
            outcome="success",
            user_id=user_id,
            session_id=session_id,
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
    session = await _repo.fetch_session_with_refresh_hash(conn, session_id)
    if session is None or session["deleted_at"] is not None:
        raise AppError("SESSION_NOT_FOUND", "Session not found.", 401)

    if not session["is_active"]:
        raise AppError("SESSION_REVOKED", "Session has been revoked.", 401)

    if not _password.verify_token_hash(session["refresh_token_hash"] or "", refresh_token):
        raise AppError("INVALID_REFRESH_TOKEN", "Refresh token is invalid.", 401)

    now = _utcnow()
    if session["refresh_expires_at"] and session["refresh_expires_at"] < now:
        raise AppError("REFRESH_TOKEN_EXPIRED", "Refresh token has expired.", 401)

    # Enforce absolute session TTL — no rolling refresh beyond this point.
    abs_exp = session.get("absolute_expires_at")
    if abs_exp is not None and abs_exp < now:
        raise AppError("SESSION_EXPIRED", "Session absolute TTL exceeded. Please log in again.", 401)

    user_id: str = session["user_id"]

    access_ttl: int = _access_ttl()
    refresh_ttl: int = _refresh_ttl()

    # Issue new tokens — embed session_id as "sid" claim.
    access_token = await _jwt.issue_token(user_id, access_ttl, session_id=session_id)
    access_payload = _jwt.verify_token(access_token)
    new_jti: str = access_payload["jti"]

    raw_refresh = _jwt.generate_refresh_token()
    new_refresh_hash = _password.hash_token(raw_refresh)
    refresh_prefix = raw_refresh[:16]
    token_prefix = access_token[:16]

    import datetime as dt  # noqa: PLC0415
    new_refresh_expires_at = now + dt.timedelta(seconds=refresh_ttl)

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.update_session_refresh(
            conn,
            session_id=session_id,
            refresh_token_hash=new_refresh_hash,
            refresh_token_prefix=refresh_prefix,
            refresh_expires_at=new_refresh_expires_at,
        )
        # Update token_prefix on the fact row
        await conn.execute(  # type: ignore[union-attr]
            """
            UPDATE "03_iam"."20_fct_sessions"
               SET token_prefix = $2, updated_at = CURRENT_TIMESTAMP
             WHERE id = $1
            """,
            session_id,
            token_prefix,
        )
        # Upsert JTI EAV attr
        await _repo.update_upsert_session_attr(
            conn,
            id=_id_mod.uuid7(),
            entity_type_id=_SESSION_ENTITY_TYPE_ID,
            entity_id=session_id,
            attr_def_id=_ATTR_JTI,
            value=new_jti,
        )
        await _audit.emit(
            conn,
            category="iam",
            action="session.refresh",
            outcome="success",
            user_id=user_id,
            session_id=session_id,
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

    await _repo.revoke_session(conn, session_id)
    await _audit.emit(
        conn,
        category="iam",
        action="session.logout",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        target_id=session_id,
        target_type="iam_session",
    )
