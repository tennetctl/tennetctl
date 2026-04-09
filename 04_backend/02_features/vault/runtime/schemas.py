"""Pydantic v2 schemas for the vault runtime API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class VaultStatusData(BaseModel):
    initialized: bool
    status: str          # "sealed" | "unsealed"
    unseal_mode: str     # "manual" | "kms_azure"
    initialized_at: datetime | None


class VaultStatusResponse(BaseModel):
    ok: bool = True
    data: VaultStatusData


class UnsealRequest(BaseModel):
    # For manual mode: not required if DATABASE_URL is set.
    # For future KMS modes: kms parameters go here.
    pass
