"""JWT Bearer token authentication dependency.

FastAPI dependency that:
1. Extracts Bearer token from Authorization header.
2. Verifies the JWT signature + expiry (cryptographic check — stateless).
3. Looks up the session in the DB by JTI to detect revoked sessions.
4. Enforces absolute_expires_at so long-lived refresh cycles can't extend
   a session beyond its absolute TTL.
5. Returns the decoded payload for use in routes.

Usage in routes:
    @router.get("/protected")
    async def protected(token: dict = Depends(require_auth)):
        user_id = token["sub"]
"""

from __future__ import annotations

import importlib
from datetime import datetime, timezone

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_jwt_mod = importlib.import_module("04_backend.01_core.jwt_utils")
_errors_mod = importlib.import_module("04_backend.01_core.errors")
_db_mod = importlib.import_module("04_backend.01_core.db")
_sessions_repo = importlib.import_module(
    "04_backend.02_features.iam.sessions.repository"
)

AppError = _errors_mod.AppError

_bearer = HTTPBearer(auto_error=False)


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def require_auth(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Validate Bearer token, verify session is active, return decoded payload.

    Raises AppError(401) if:
    - Token is missing, malformed, or cryptographically invalid.
    - Token is expired (JWT exp claim).
    - Session has been revoked or deleted (DB lookup by JTI).
    - Session has exceeded its absolute_expires_at.
    """
    if creds is None or not creds.credentials:
        raise AppError("UNAUTHORIZED", "Bearer token required.", 401)

    token = creds.credentials
    try:
        payload = _jwt_mod.verify_token(token)
    except ValueError:
        raise AppError("INVALID_TOKEN", "Token is invalid or expired.", 401)

    jti: str | None = payload.get("jti")
    if not jti:
        raise AppError("INVALID_TOKEN", "Token missing jti claim.", 401)

    # Session revocation check — look up the JTI in the DB.
    pool = _db_mod.get_pool()
    async with pool.acquire() as conn:
        session = await _sessions_repo.fetch_active_session_by_jti(conn, jti)

    if session is None:
        raise AppError("SESSION_REVOKED", "Session has been revoked or does not exist.", 401)

    # Enforce absolute TTL (prevents indefinite refresh token rolling).
    abs_exp = session.get("absolute_expires_at")
    if abs_exp is not None and abs_exp < _utcnow_naive():
        raise AppError("SESSION_EXPIRED", "Session absolute TTL exceeded.", 401)

    return payload
