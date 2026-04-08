"""Pydantic v2 schemas for IAM feature registry endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class CreateFeatureRequest(BaseModel):
    product_id: str
    code: str
    name: str
    scope_id: int
    category_id: int
    parent_id: str | None = None
    description: str | None = None
    status: str | None = None
    doc_url: str | None = None
    owner_user_id: str | None = None
    version_introduced: str | None = None

    @field_validator("product_id", "code", "name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Must not be empty.")
        return v


class UpdateFeatureRequest(BaseModel):
    name: str | None = None
    scope_id: int | None = None
    category_id: int | None = None
    is_active: bool | None = None
    description: str | None = None
    status: str | None = None
    doc_url: str | None = None
    owner_user_id: str | None = None
    version_introduced: str | None = None


class FeatureData(BaseModel):
    id: str
    product_id: str
    parent_id: str | None
    code: str
    name: str
    scope_id: int
    scope_code: str | None
    scope_label: str | None
    category_id: int
    category_code: str | None
    category_label: str | None
    is_active: bool
    is_deleted: bool
    description: str | None
    status: str | None
    doc_url: str | None
    owner_user_id: str | None
    version_introduced: str | None
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime
