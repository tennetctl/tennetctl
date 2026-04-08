"""Pydantic v2 schemas for IAM orgs endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class OrgCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    owner_id: str


class OrgUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    status_code: str | None = None


class OrgData(BaseModel):
    id: str
    name: str | None
    slug: str | None
    description: str | None
    status: str | None
    is_active: bool
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime
