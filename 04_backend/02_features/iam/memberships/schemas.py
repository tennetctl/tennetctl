"""Pydantic v2 schemas for IAM memberships endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class OrgMembershipCreate(BaseModel):
    user_id: str
    org_id: str


class WorkspaceMembershipCreate(BaseModel):
    user_id: str
    workspace_id: str
    org_id: str


class OrgMembershipData(BaseModel):
    id: str
    user_id: str
    org_id: str
    org_slug: str | None
    org_name: str | None
    org_status: str | None
    org_is_active: bool | None
    created_by: str
    created_at: datetime


class WorkspaceMembershipData(BaseModel):
    id: str
    user_id: str
    workspace_id: str
    org_id: str
    workspace_slug: str | None
    workspace_name: str | None
    workspace_status: str | None
    workspace_is_active: bool | None
    created_by: str
    created_at: datetime
