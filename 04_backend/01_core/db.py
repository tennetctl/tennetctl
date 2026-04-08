"""asyncpg connection pool lifecycle."""

from __future__ import annotations

import json

import asyncpg


_pool: asyncpg.Pool | None = None


async def register_jsonb_codec(conn: asyncpg.Connection) -> None:
    """Register a JSONB codec so Python dicts / lists are automatically
    serialised on INSERT and deserialised as Python objects on SELECT.

    Called on every new pool connection (via ``init`` callback) and on bare
    connections in tests. Without this asyncpg rejects dict arguments as
    "expected str, got dict" for JSONB columns.
    """
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def _init_conn(conn: asyncpg.Connection) -> None:
    await register_jsonb_codec(conn)


async def init_pool(dsn: str) -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=dsn, min_size=1, max_size=10, init=_init_conn
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("db pool not initialised")
    return _pool
