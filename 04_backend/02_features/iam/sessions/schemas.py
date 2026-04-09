"""Pydantic v2 schemas for IAM session (auth) endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class LoginRequest(BaseModel):
    username: str
    password: str

    @field_validator("username", "password")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Must not be empty.")
        return v


class TokenPair(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str
    expires_in: int      # seconds until access token expires
    session_id: str


class SessionData(BaseModel):
    id: str
    user_id: str
    status: str
    token_prefix: str | None
    refresh_token_prefix: str | None
    refresh_expires_at: datetime | None
    expires_at: datetime
    absolute_expires_at: datetime
    last_seen_at: datetime | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


class MeData(BaseModel):
    user_id: str
    username: str | None
    email: str | None
    account_type: str
    session_id: str


class RefreshRequest(BaseModel):
    refresh_token: str


class SwitchScopeRequest(BaseModel):
    target_org_id: str
    target_workspace_id: str


class LogoutResponse(BaseModel):
    ok: bool = True
    data: dict = {"message": "Session revoked."}
