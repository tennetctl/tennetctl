## Planned: Session Type Dim

**Severity if unbuilt:** MEDIUM (operational visibility, not a security gap)
**Depends on:** v1 sessions, settings table

## Problem

All sessions look identical in the DB — there's no way to distinguish a
browser login from a CLI session or an API key session. This makes session
management UI (e.g., "show all active browser sessions") impossible to build.

## Fix when built

### Schema

Add `07_dim_session_types` (new migration):

```sql
INSERT INTO "03_iam"."07_dim_session_types" (code, label) VALUES
    ('web',     'Web Browser'),
    ('mobile',  'Mobile App'),
    ('cli',     'CLI / tennetctl binary'),
    ('api_key', 'API Key (programmatic)');
```

Add `session_type_id SMALLINT FK → 07_dim_session_types` to
`20_fct_sessions`.

### Routing

The login endpoint receives a `session_type` field in the request body
(optional, defaults to `web`). CLI sets it to `cli` by passing
`X-Client-Type: cli` header or a body field. API key auth sets it to
`api_key` automatically.

### max_sessions_per_type

Settings table keys:
```
iam.max_sessions_per_user.web      default: 5
iam.max_sessions_per_user.mobile   default: 10
iam.max_sessions_per_user.cli      default: 3
iam.max_sessions_per_user.api_key  default: null (unlimited, governed by key expiry)
```

See `12_max_sessions.md` for the eviction policy.
