## Planned: Revoke All Sessions

**Severity if unbuilt:** CRITICAL (no recovery path if account is compromised)
**Depends on:** v1 auth (session middleware)

## Problem

`POST /v1/auth/logout` revokes only the current session. If an attacker has
created multiple sessions (or if the user wants to log out all other
devices), there is no endpoint to do so. The only recovery is manual DB row
deletion.

## Scope when built

### Endpoints

`POST /v1/auth/revoke-all`
Revokes all sessions for the calling user **except** the current one.
Returns 200 with a count of sessions revoked.

Response:
```json
{ "ok": true, "data": { "revoked": 4 } }
```

`POST /v1/auth/revoke-all-including-current`
Revokes every session including the current one. Useful for "I think my
account was compromised — log me out everywhere". Returns 204.

### Rules

- Both endpoints require a valid session (middleware enforces).
- Each revoked session gets `status = revoked`, `deleted_at = now()`.
- Emit one `iam.user.sessions_revoked` event with `{ user_id, count,
  include_current: bool }`.

### Admin revocation (future)

Admin-forced revocation of another user's sessions lives in the future
`03_iam.02_users` sub-feature.
