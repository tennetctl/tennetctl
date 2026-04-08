"""IAM session routes — login, me, refresh, switch_scope, logout.

POST   /v1/sessions              — login (creates session, returns token pair)
GET    /v1/sessions/me           — current user from Bearer token
PATCH  /v1/sessions/{id}         — refresh token rotation
PATCH  /v1/sessions/{id}/scope   — switch active org/workspace scope
DELETE /v1/sessions/{id}         — logout (soft-delete / revoke)
"""

from __future__ import annotations

import importlib

from fastapi import APIRouter, Depends, Request

_db = importlib.import_module("04_backend.01_core.db")
_service = importlib.import_module("04_backend.02_features.iam.sessions.service")
_resp = importlib.import_module("04_backend.01_core.response")
_auth = importlib.import_module("04_backend.01_core.auth")
_schemas = importlib.import_module("04_backend.02_features.iam.sessions.schemas")
_errors_mod = importlib.import_module("04_backend.01_core.errors")
_ratelimit = importlib.import_module("04_backend.01_core.ratelimit")

AppError = _errors_mod.AppError

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


@router.post("", status_code=201)
async def login(body: _schemas.LoginRequest, request: Request) -> dict:  # type: ignore[name-defined]
    """Authenticate credentials and issue a token pair."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    # Rate limit: 10 attempts / 60s per (username, ip)
    await _ratelimit.check_login_rate_limit(username=body.username, ip_address=ip)

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.login(
            conn,
            username=body.username,
            password=body.password,
            ip_address=ip,
            user_agent=ua,
        )
    return _resp.ok(result)


@router.get("/me")
async def get_me(token: dict = Depends(_auth.require_auth)) -> dict:
    """Return profile of the authenticated user."""
    user_id: str = token["sub"]
    session_id: str = token.get("sid", "")

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        me = await _service.get_me(conn, user_id=user_id, session_id=session_id)
    return _resp.ok(me)


@router.patch("/{session_id}")
async def refresh(session_id: str, body: _schemas.RefreshRequest) -> dict:  # type: ignore[name-defined]
    """Rotate refresh token and issue a new access token."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.refresh(
            conn,
            session_id=session_id,
            refresh_token=body.refresh_token,
        )
    return _resp.ok(result)


@router.patch("/{session_id}/scope")
async def switch_scope(
    session_id: str,
    body: _schemas.SwitchScopeRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Switch the active org/workspace scope for the session."""
    user_id: str = token["sub"]
    token_session_id: str = token.get("sid", "")
    if token_session_id != session_id:
        raise AppError("FORBIDDEN", "Cannot switch scope of another user's session.", 403)
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.switch_scope(
            conn,
            session_id,
            body.target_org_id,
            body.target_workspace_id,
            user_id=user_id,
            session_id_audit=session_id,
        )
    return _resp.ok({"session_id": session_id, "org_id": body.target_org_id, "workspace_id": body.target_workspace_id})


@router.delete("/{session_id}", status_code=204)
async def logout(
    session_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    """Revoke (soft-delete) the session — logout."""
    actor_id: str = token["sub"]
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.logout(conn, session_id=session_id, actor_id=actor_id)
