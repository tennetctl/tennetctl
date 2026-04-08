"""Response envelope — every API response is { ok: bool, data | error }."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorBody(BaseModel):
    code: str
    message: str


class OkResponse(BaseModel, Generic[T]):
    ok: bool = True
    data: T


class ErrResponse(BaseModel):
    ok: bool = False
    error: ErrorBody


def ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data}


def err(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}
