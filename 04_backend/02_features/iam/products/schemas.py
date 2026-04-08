"""Pydantic v2 schemas for IAM products endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class CreateProductRequest(BaseModel):
    code: str
    name: str
    category_id: int
    is_sellable: bool = False
    description: str | None = None
    slug: str | None = None
    status: str | None = None
    pricing_tier: str | None = None
    owner_user_id: str | None = None

    @field_validator("code", "name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Must not be empty.")
        return v


class UpdateProductRequest(BaseModel):
    name: str | None = None
    is_sellable: bool | None = None
    is_active: bool | None = None
    description: str | None = None
    slug: str | None = None
    status: str | None = None
    pricing_tier: str | None = None
    owner_user_id: str | None = None


class ProductData(BaseModel):
    id: str
    code: str
    name: str
    category_id: int
    category_code: str | None
    category_label: str | None
    is_sellable: bool
    is_active: bool
    is_deleted: bool
    description: str | None
    slug: str | None
    status: str | None
    pricing_tier: str | None
    owner_user_id: str | None
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime


class SubscribeWorkspaceProductRequest(BaseModel):
    product_id: str

    @field_validator("product_id")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Must not be empty.")
        return v


class WorkspaceProductData(BaseModel):
    id: str
    workspace_id: str
    product_id: str
    subscribed_at: datetime
    subscribed_by: str
    is_active: bool
