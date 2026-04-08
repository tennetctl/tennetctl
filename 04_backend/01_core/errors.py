"""Application error classes and FastAPI exception handlers.

All HTTP errors go through AppError so every response follows the
{ok: false, error: {code, message}} envelope.

Usage in routes:
    raise AppError("NOT_FOUND", f"User '{user_id}' not found.", 404)

Usage in services:
    raise AppError("INVALID_CREDENTIALS", "Username or password incorrect.", 401)
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Raised anywhere in the stack; caught by the exception handler."""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def register_error_handlers(app: FastAPI) -> None:
    """Register the AppError → JSON envelope handler on *app*."""

    @app.exception_handler(AppError)
    async def _app_error_handler(_req: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content={"ok": False, "error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(_req: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."}},
        )
