"""Audit query routes — read-only access to the event log.

GET  /v1/audit/events       — list events (filterable by org, user, session, category, action, outcome)
GET  /v1/audit/events/{id}  — get single event
"""

from __future__ import annotations

import importlib

from fastapi import APIRouter, Depends, Query

_db = importlib.import_module("04_backend.01_core.db")
_service = importlib.import_module("04_backend.02_features.audit.query_service")
_resp = importlib.import_module("04_backend.01_core.response")
_auth = importlib.import_module("04_backend.01_core.auth")

router = APIRouter(prefix="/v1/audit", tags=["audit"])


@router.get("/events")
async def list_events(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    org_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    category: str | None = Query(default=None),
    action: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    _token: dict = Depends(_auth.require_auth),
) -> dict:
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.list_events(
            conn,
            limit=limit,
            offset=offset,
            org_id=org_id,
            user_id=user_id,
            session_id=session_id,
            category=category,
            action=action,
            outcome=outcome,
        )
    return _resp.ok(result)


@router.get("/events/{event_id}")
async def get_event(
    event_id: str,
    _token: dict = Depends(_auth.require_auth),
) -> dict:
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        event = await _service.get_event(conn, event_id)
    return _resp.ok(event)
