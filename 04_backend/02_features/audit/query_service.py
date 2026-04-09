"""Audit query service — read-only access to the event log."""

from __future__ import annotations

import importlib

_repo = importlib.import_module("04_backend.02_features.audit.repository")
_errors_mod = importlib.import_module("04_backend.01_core.errors")

AppError = _errors_mod.AppError


async def list_events(
    conn: object,
    *,
    limit: int = 50,
    offset: int = 0,
    org_id: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    category: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
) -> dict:
    items, total = await _repo.list_events(
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
    return {"items": items, "total": total, "limit": limit, "offset": offset}


async def get_event(conn: object, event_id: str) -> dict:
    event = await _repo.get_event(conn, event_id)
    if event is None:
        raise AppError("AUDIT_EVENT_NOT_FOUND", f"Audit event '{event_id}' not found.", 404)
    return event
