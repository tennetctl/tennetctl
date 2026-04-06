# ADR-007: Valkey as an Optional Caching and Rate-Limiting Backend

**Status:** Accepted
**Date:** 2026-03-29

---

## Context

tennetctl's default deployment uses only Postgres and NATS. However, several workloads benefit from a fast in-memory store:

**Rate limiting:** The default Postgres-based rate limiter uses counter tables with `SELECT ... FOR UPDATE`. This works correctly but adds 1–3ms of Postgres round-trips per request. At high API traffic (>1k requests/second), these lock contention patterns can become a bottleneck.

**Session and permission caching:** On every authenticated request, tennetctl resolves the current user's permissions via a recursive CTE in Postgres. This query is fast (~1ms) but runs on every single API call. At high traffic, it creates read load on Postgres that doesn't contain new information — permission structures change infrequently.

**Idempotency keys:** Some operations (payment processing, notification sends) need idempotency key storage with a short TTL. Postgres works but requires periodic cleanup jobs. An in-memory TTL-based store is cleaner.

Redis has historically been the standard solution for these use cases. However, Redis changed its license in 2024 to SSPL, which is incompatible with open-source projects and many commercial deployments. Valkey is the community-maintained fork of Redis 7.2, released under the BSD 3-Clause license, with identical wire protocol and API.

---

## Decision

Valkey is supported as an optional caching and rate-limiting backend. It is never required. The system functions correctly without it using Postgres-based fallbacks.

When Valkey is configured:
- Rate limiting uses Valkey sliding window counters (Lua scripts, atomic operations)
- Permission resolution results are cached in Valkey with a configurable TTL (default: 60 seconds)
- Idempotency keys use Valkey `SET NX EX` (set-if-not-exists with TTL)

When Valkey is not configured:
- Rate limiting uses Postgres counter tables
- Permission resolution queries Postgres on every request
- Idempotency keys use a Postgres table with a cleanup job

The system interface for each use case is abstract — the implementation switches based on configuration. Application code never checks whether Valkey is available; it calls `rate_limiter.check()` and `cache.get()` and the underlying implementation is selected at startup.

---

## Why Valkey and Not Redis

| Criterion | Redis | Valkey |
|-----------|-------|--------|
| License | SSPL (2024+) | BSD 3-Clause |
| Open-source compatible | No | Yes |
| Wire protocol | Redis RESP | Redis RESP (identical) |
| Client library compatibility | redis-py | redis-py (drop-in) |
| Maintenance | Redis Ltd | Linux Foundation |
| Feature parity (v7.2) | Reference | Full parity |

Valkey is a drop-in replacement at the protocol level. Existing `redis-py` clients connect to Valkey unchanged. The decision to use Valkey over Redis is purely about license compliance for an open-source project.

---

## What Valkey Is and Is Not Used For

| Use case | With Valkey | Without Valkey | Notes |
|----------|-------------|----------------|-------|
| API rate limiting | Valkey sliding window | Postgres counter table | Valkey recommended at >500 req/s |
| Permission cache | Valkey with TTL | No cache (query every time) | Cache invalidated on role change event |
| Session token lookup | Not cached (always DB) | Not cached (always DB) | Sessions must always be verified against DB |
| Idempotency keys | Valkey `SET NX EX` | Postgres table + cleanup job | |
| NATS replacement | Never | Never | Valkey pub/sub is not a substitute for JetStream |
| Durable state | Never | Never | Valkey is cache only. Loss of Valkey data must be safe. |

**Critical rule:** No durable state lives in Valkey. If Valkey data is lost entirely (OOM eviction, restart without persistence), the system must be fully functional within one request — either by falling back to Postgres or by recomputing the cached value.

---

## Cache Invalidation Strategy

Permission cache entries are invalidated on these events:
- `iam.role.assigned` — a user's role changed
- `iam.permission.updated` — a permission's definition changed
- `iam.group.membership.changed` — a user joined or left a group

The event bus handler for these events calls `cache.invalidate(user_id)`.

Cache entries also expire via TTL (default 60 seconds) as a safety net. A stale permission cache entry can at most persist for one TTL period after the underlying permission changed.

---

## Configuration

```python
# 01_core/config.py
VALKEY_URL: str = ""               # Empty = Valkey disabled, use Postgres fallbacks
VALKEY_POOL_SIZE: int = 10
CACHE_PERMISSION_TTL_SECONDS: int = 60
RATE_LIMIT_BACKEND: Literal["postgres", "valkey"] = "postgres"  # auto-set based on VALKEY_URL
```

When `VALKEY_URL` is set, `RATE_LIMIT_BACKEND` automatically switches to `"valkey"`.

---

## Interface Design

```python
# 01_core/cache.py

class CacheBackend(Protocol):
    """Abstract cache interface. Implemented by PostgresCache and ValkeyCache."""

    async def get(self, key: str) -> str | None:
        """Get a cached value. Returns None if not found or expired."""
        ...

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Set a cached value with TTL."""
        ...

    async def delete(self, key: str) -> None:
        """Delete a cached value."""
        ...

    async def set_if_not_exists(self, key: str, value: str, ttl_seconds: int) -> bool:
        """Set only if key does not exist. Returns True if set, False if already existed."""
        ...


# 01_core/rate_limit.py

class RateLimiter(Protocol):
    """Abstract rate limiter. Implemented by PostgresRateLimiter and ValkeyRateLimiter."""

    async def check_and_increment(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> tuple[bool, int]:
        """
        Check rate limit and increment counter.

        Returns:
            (allowed, current_count) — allowed=False if limit exceeded
        """
        ...
```

The active implementation is selected in `01_core/dependencies.py` at application startup based on `settings.VALKEY_URL`.

---

## Local Development

Valkey is not in the default `docker-compose.yml`. It is an optional service:

```yaml
# docker-compose.yml — optional services section
profiles:
  - full

services:
  valkey:
    image: valkey/valkey:7.2-alpine
    profiles: [full]
    ports: ["6379:6379"]
    command: valkey-server --save "" --appendonly no  # dev: no persistence
```

To run with Valkey:
```bash
docker compose --profile full up
# Set VALKEY_URL=redis://localhost:6379 in .env
```

To run without Valkey (default):
```bash
docker compose up
# VALKEY_URL is empty — Postgres fallbacks are used
```

---

## Scale Guidance

| Traffic level | Rate limiting backend | Permission caching |
|---------------|----------------------|-------------------|
| < 100 req/s | Postgres (default) | No cache (default) |
| 100–1000 req/s | Postgres (adequate) | Valkey recommended |
| > 1000 req/s | Valkey required | Valkey required |

These are guidelines. Monitor Postgres connection pool utilization and query latency in production to determine when Valkey is needed.
