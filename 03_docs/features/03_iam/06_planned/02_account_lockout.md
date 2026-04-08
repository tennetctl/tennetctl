## Planned: Account Lockout

**Severity if unbuilt:** MEDIUM
**Depends on:** rate limiting (#01), settings table

## Problem

Rate limiting throttles attempts per IP/username. Account lockout is a
harder ceiling: after N failed attempts in M minutes for the *same user*,
lock the account until the window passes or an admin unlocks it manually.
Without this, a distributed attacker (many IPs) bypasses per-IP rate limits.

## Scope when built

- Add `login_failed_count INT DEFAULT 0` and `locked_until TIMESTAMP` to
  `10_fct_users` (or as EAV if the no-columns-on-fct rule is strict —
  prefer EAV to keep the fct table clean).
- On each failed login: increment `login_failed_count`. If count >= N
  within M minutes, set `locked_until = now() + M minutes`.
- On successful login: reset `login_failed_count = 0`, clear `locked_until`.
- Login check: if `locked_until > now()`, return 401 `ACCOUNT_LOCKED`
  with `Retry-After` header. Do NOT run Argon2id (no point, save CPU).
- Emit `iam.login.account_locked` audit event.
- Admin endpoint: `POST /v1/users/{id}/unlock` (future users sub-feature).

## Settings keys

```
iam.lockout_max_attempts    default: 10
iam.lockout_window_minutes  default: 15
iam.lockout_duration_minutes default: 30
```
