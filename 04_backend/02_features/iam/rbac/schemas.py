"""Pydantic v2 schemas for RBAC endpoints."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Platform roles
# ---------------------------------------------------------------------------

class CreatePlatformRoleRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    category_code: str = Field(..., description="dim_categories code (category_type='role')")
    is_system: bool = False


class UpdatePlatformRoleRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    is_active: Optional[bool] = None


class AddPermissionRequest(BaseModel):
    permission_id: str = Field(..., min_length=1, max_length=36)


class AssignPlatformRoleRequest(BaseModel):
    platform_role_id: str = Field(..., min_length=1, max_length=36)


# ---------------------------------------------------------------------------
# Org roles
# ---------------------------------------------------------------------------

class CreateOrgRoleRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    category_code: str = Field(..., description="dim_categories code (category_type='role')")
    is_system: bool = False


class UpdateOrgRoleRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    is_active: Optional[bool] = None


class AssignOrgRoleRequest(BaseModel):
    org_id: str = Field(..., min_length=1, max_length=36)
    org_role_id: str = Field(..., min_length=1, max_length=36)


# ---------------------------------------------------------------------------
# Workspace roles
# ---------------------------------------------------------------------------

class CreateWorkspaceRoleRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    category_code: str = Field(..., description="dim_categories code (category_type='role')")
    org_id: str = Field(..., min_length=1, max_length=36)
    is_system: bool = False


class UpdateWorkspaceRoleRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    is_active: Optional[bool] = None


class AssignWorkspaceRoleRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=36)
    workspace_role_id: str = Field(..., min_length=1, max_length=36)


# ---------------------------------------------------------------------------
# Runtime check
# ---------------------------------------------------------------------------

class RbacCheckRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=36)
    resource: str = Field(..., min_length=1, max_length=64)
    action: str = Field(..., min_length=1, max_length=32)
    org_id: Optional[str] = None
    workspace_id: Optional[str] = None
