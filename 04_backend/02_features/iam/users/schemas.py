"""Pydantic v2 schemas for IAM user endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class UserData(BaseModel):
    id: str
    account_type: str
    auth_type: str
    username: str | None
    email: str | None
    is_active: bool
    is_deleted: bool
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime


class UserListData(BaseModel):
    items: list[UserData]
    total: int


class PatchUserRequest(BaseModel):
    email: str | None = None
    is_active: bool | None = None

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str | None) -> str | None:
        if v is not None and "@" not in v:
            raise ValueError("Invalid email address.")
        return v
