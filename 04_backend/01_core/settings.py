"""Runtime settings loader.

Reads key/value pairs from ``00_schema_migrations.10_fct_settings`` at boot
and caches them for the process lifetime. All hardcoded defaults in service
code are replaced by calls to ``get_setting(scope, key, default=...)``.

Call ``load_settings_from_db(pool)`` once during the FastAPI lifespan startup
(after the vault is unsealed, because the DB pool requires DATABASE_URL).

Seeded keys (scope="03_iam"):
  jwt_access_ttl_seconds       default: 900
  jwt_refresh_ttl_seconds      default: 604800
  session_absolute_ttl_seconds default: 2592000
  password_min_length          default: 12
"""

from __future__ import annotations

import asyncio
from typing import Any

# Cache: {(scope, key): value_str}
_cache: dict[tuple[str, str], str] = {}
_loaded = False
_load_lock = asyncio.Lock()


async def load_settings_from_db(pool: object) -> None:
    """Populate the in-memory cache from the settings table.

    Idempotent — safe to call multiple times; re-reads only on first call.
    """
    global _loaded
    if _loaded:
        return

    async with _load_lock:
        if _loaded:
            return

        async with pool.acquire() as conn:  # type: ignore[union-attr]
            rows = await conn.fetch(
                """
                SELECT scope, key, value
                  FROM "00_schema_migrations"."10_fct_settings"
                """
            )
        for row in rows:
            _cache[(row["scope"], row["key"])] = row["value"]

        _loaded = True


def get_setting(scope: str, key: str, *, default: Any = None) -> Any:
    """Return the cached setting value, or *default* if not found.

    All values are stored as TEXT. Callers should cast as needed:
        ttl = int(get_setting("03_iam", "jwt_access_ttl_seconds", default=900))
    """
    return _cache.get((scope, key), default)


def get_int(scope: str, key: str, *, default: int) -> int:
    """Convenience: return an int setting with a typed default."""
    raw = _cache.get((scope, key))
    if raw is None:
        return default
    try:
        return int(raw)
    except (ValueError, TypeError):
        return default
