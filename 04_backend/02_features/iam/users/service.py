"""IAM users service — list, get, patch."""

from __future__ import annotations

import importlib

_repo = importlib.import_module("04_backend.02_features.iam.users.repository")
_id_mod = importlib.import_module("scripts.00_core._id")
_errors_mod = importlib.import_module("04_backend.01_core.errors")

AppError = _errors_mod.AppError


async def list_users(conn: object, *, limit: int = 50, offset: int = 0) -> dict:
    items, total = await _repo.fetch_users(conn, limit=limit, offset=offset)
    return {"items": items, "total": total}


async def get_user(conn: object, user_id: str) -> dict:
    user = await _repo.fetch_user_by_id(conn, user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", f"User '{user_id}' not found.", 404)
    return user


async def patch_user(
    conn: object,
    user_id: str,
    *,
    email: str | None = None,
    is_active: bool | None = None,
    actor_id: str,
) -> dict:
    """Apply partial updates to a user record.

    Returns the updated user.
    Raises AppError(404) if user not found.
    """
    user = await _repo.fetch_user_by_id(conn, user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", f"User '{user_id}' not found.", 404)

    async with conn.transaction():  # type: ignore[union-attr]
        if is_active is not None:
            await _repo.update_user_is_active(
                conn, user_id=user_id, is_active=is_active, actor_id=actor_id
            )
        if email is not None:
            await _repo.upsert_user_email(
                conn, attr_id=_id_mod.uuid7(), user_id=user_id, email=email
            )

    return await _repo.fetch_user_by_id(conn, user_id)
