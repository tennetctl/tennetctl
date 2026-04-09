"""Pydantic v2 schemas for audit query endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AuditEvent(BaseModel):
    id: str
    org_id: str | None
    workspace_id: str | None
    user_id: str | None
    session_id: str | None
    category: str
    action: str
    outcome: str
    actor_id: str | None
    target_id: str | None
    target_type: str | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
