"""Pydantic v2 schemas for IAM groups endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class CreateGroupRequest(BaseModel):
    name: str
    slug: str
    org_id: str
    description: str | None = None

    @field_validator("name", "slug", "org_id")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Must not be empty.")
        return v


class UpdateGroupRequest(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None


class GroupData(BaseModel):
    id: str
    org_id: str
    name: str | None
    slug: str | None
    description: str | None
    is_system: bool
    is_active: bool
    is_deleted: bool
    member_count: int
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime


class AddMemberRequest(BaseModel):
    user_id: str

    @field_validator("user_id")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Must not be empty.")
        return v


class MemberData(BaseModel):
    id: str
    group_id: str
    user_id: str
    added_by: str
    is_active: bool
    added_at: datetime
    username: str | None = None
    email: str | None = None
