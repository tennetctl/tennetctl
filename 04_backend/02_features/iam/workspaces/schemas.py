"""Pydantic v2 schemas for IAM workspaces endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class WorkspaceCreate(BaseModel):
    org_id: str
    name: str
    slug: str


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    status_code: str | None = None


class WorkspaceData(BaseModel):
    id: str
    org_id: str
    name: str | None
    slug: str | None
    status: str | None
    is_active: bool
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime
