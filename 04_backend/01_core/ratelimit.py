"""Sliding-window rate limiter backed by Valkey (Redis-compatible).

Uses a sorted-set approach: each request adds a member with score=timestamp.
Members older than the window are pruned atomically via a pipeline.

Configuration (from environment):
  VALKEY_URL  default: redis://localhost:6379/0

Rate limits (fixed, not configurable via settings table yet):
  login:  10 attempts per 60 seconds per username+IP pair.

If Valkey is unavailable, the check is skipped and the request is allowed
through. This fail-open policy is intentional: a cache outage must not
cause a full auth outage. The error is logged to stderr.
"""

from __future__ import annotations

import hashlib
import os
import sys
import time


def _valkey_url() -> str:
    return os.environ.get("VALKEY_URL", "redis://localhost:6379/0")


# Lazy singleton — created once on first use.
_client: object | None = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        import redis.asyncio as aioredis  # noqa: PLC0415
        _client = aioredis.from_url(_valkey_url(), decode_responses=True)
    except Exception as exc:
        sys.stderr.write(f"[ratelimit] Failed to create Valkey client: {exc}\n")
        _client = None
    return _client


async def check_login_rate_limit(*, username: str, ip_address: str | None) -> None:
    """Raise AppError(429) if the login rate limit is exceeded.

    Limit: 10 attempts per 60-second window per (username, ip) pair.
    Falls through silently if Valkey is unreachable.
    """
    import importlib  # noqa: PLC0415
    _errors_mod = importlib.import_module("04_backend.01_core.errors")
    AppError = _errors_mod.AppError

    client = _get_client()
    if client is None:
        return  # fail-open

    window_seconds = 60
    max_attempts = 10
    # Hash the username component so a username containing ':' cannot
    # collide with other rate-limit keys.
    uname_hash = hashlib.sha256(username.encode("utf-8")).hexdigest()[:16]
    key = f"rl:login:{uname_hash}:{ip_address or 'no-ip'}"
    now = time.time()
    window_start = now - window_seconds

    try:
        pipe = client.pipeline(transaction=True)  # type: ignore[union-attr]
        # Remove attempts outside the window
        pipe.zremrangebyscore(key, "-inf", window_start)
        # Add this attempt
        pipe.zadd(key, {str(now): now})
        # Count remaining
        pipe.zcard(key)
        # Set TTL so keys auto-expire
        pipe.expire(key, window_seconds * 2)
        results = await pipe.execute()  # type: ignore[union-attr]
        count = results[2]  # zcard result

        if count > max_attempts:
            raise AppError(
                "RATE_LIMITED",
                f"Too many login attempts. Try again in {window_seconds} seconds.",
                429,
            )
    except AppError:
        raise
    except Exception as exc:
        # Valkey error — fail open, log to stderr.
        sys.stderr.write(f"[ratelimit] check_login_rate_limit error: {exc}\n")


async def close() -> None:
    """Close the Valkey connection. Called during FastAPI lifespan shutdown."""
    global _client
    if _client is not None:
        try:
            await _client.aclose()  # type: ignore[union-attr]
        except Exception:
            pass
        _client = None
