"""Pydantic v2 schemas for IAM feature flags."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Flag CRUD
# ---------------------------------------------------------------------------

class CreateFlagRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=96)
    name: str = Field(..., min_length=1, max_length=128)
    product_id: str
    feature_id: str | None = None
    scope_id: int
    category_id: int
    flag_type: str = Field(..., pattern=r'^(boolean|percentage|variant|kill_switch|experiment)$')
    status: str = Field(default='draft', pattern=r'^(draft|active|deprecated|archived)$')
    default_value: Any | None = None
    # EAV attrs
    description: str | None = None
    owner_user_id: str | None = None
    jira_ticket: str | None = None
    rollout_percentage: str | None = None
    launch_date: str | None = None
    sunset_date: str | None = None


class UpdateFlagRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    status: str | None = Field(None, pattern=r'^(draft|active|deprecated|archived)$')
    flag_type: str | None = Field(None, pattern=r'^(boolean|percentage|variant|kill_switch|experiment)$')
    default_value: Any | None = None
    is_active: bool | None = None
    description: str | None = None
    owner_user_id: str | None = None
    jira_ticket: str | None = None
    rollout_percentage: str | None = None
    launch_date: str | None = None
    sunset_date: str | None = None


# ---------------------------------------------------------------------------
# Environment overrides
# ---------------------------------------------------------------------------

class UpsertEnvOverrideRequest(BaseModel):
    enabled: bool = True
    value: Any | None = None


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

class CreateTargetRequest(BaseModel):
    org_id: str | None = None
    workspace_id: str | None = None
    value: Any | None = None


# ---------------------------------------------------------------------------
# Eval
# ---------------------------------------------------------------------------

class EvalContext(BaseModel):
    user_id: str | None = None
    org_id: str | None = None
    workspace_id: str | None = None
    environment: str | None = None


class EvalRequest(BaseModel):
    flag_code: str
    context: EvalContext = Field(default_factory=EvalContext)
