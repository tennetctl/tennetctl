## Planned: Login Rate Limiting

**Severity if unbuilt:** HIGH
**Depends on:** settings table (to make limits configurable)

## Problem

`POST /v1/auth/login` has no rate limiting. Argon2id costs ~250ms per
attempt, which is a soft brake but not a hard one. At 4 req/s an attacker
exhausts a 1000-password dictionary in ~5 minutes against a weak password.

## Scope when built

- Per-IP token bucket: 1 attempt per 5 seconds (configurable via settings).
- Per-username token bucket: 1 attempt per 10 seconds (configurable).
- Both buckets use Valkey (Redis-compatible) so they survive restarts and
  work across multiple app instances.
- On rate-limit hit: return 429 `RATE_LIMITED` with `Retry-After` header.
- Emit `iam.login.rate_limited` audit event with IP + attempted username.
- Exempt paths list in `session_middleware.py` does not need updating
  (rate limiting is applied inside the login route, not the middleware).

## Settings keys

```
iam.login_rate_limit_per_ip_seconds     default: 5
iam.login_rate_limit_per_user_seconds   default: 10
```

## Not in scope here

Account lockout (harder limit after N attempts) is a separate planned item:
`02_account_lockout.md`.
