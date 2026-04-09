## Planned: Max Sessions Per User

**Severity if unbuilt:** MEDIUM
**Depends on:** settings table, session_type dim (#11)

## Problem

A user (or attacker with the password) can create unlimited concurrent
sessions. There's no cap and no eviction policy.

## Fix when built

### At login

Before inserting a new session row, check active session count per user
(optionally per session_type):

```sql
SELECT COUNT(*) FROM "03_iam"."20_fct_sessions"
WHERE user_id = $1
  AND session_type_id = $2   -- optional, if per-type limits enabled
  AND deleted_at IS NULL
  AND status_id = (SELECT id FROM "03_iam"."08_dim_session_statuses"
                   WHERE code = 'active')
```

### Eviction policy (configurable via settings)

`iam.session_overflow_policy`: `reject` | `evict_oldest`

- `reject` — return 409 `SESSION_LIMIT_REACHED`. User must manually log
  out from another device.
- `evict_oldest` — soft-delete the session with the oldest `last_seen_at`
  before inserting the new one. Emit `iam.session.evicted` audit event.

Default: `evict_oldest` (better UX for single-admin deployments).

### Settings keys

```
iam.max_sessions_per_user           default: 10   (global cap, all types combined)
iam.session_overflow_policy         default: evict_oldest
```

Per-type limits are specified in `11_session_type.md`.
