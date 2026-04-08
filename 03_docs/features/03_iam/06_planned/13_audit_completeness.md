## Planned: Full Audit Event Coverage

**Severity if unbuilt:** HIGH (security monitoring is blind)
**Depends on:** password change (#03), revoke-all (#04), rate limiting (#01)

## Problem

The architecture doc lists 5 audit events. The service code only emits 3 of
them. Several important security events have no audit trail at all.

## Full target event set

| Subject | Emitted when | Payload (no secret material) |
| ------- | ------------ | ----------------------------- |
| `iam.user.logged_in` | Successful login | user_id, session_id, ip, user_agent |
| `iam.user.logged_out` | Successful logout | user_id, session_id |
| `iam.login.failed` | Wrong password or unknown user | attempted_username, reason, ip |
| `iam.login.rate_limited` | Rate limit hit on login | ip, attempted_username |
| `iam.login.account_locked` | Account locked after N failures | user_id, ip |
| `iam.session.expired` | Middleware rejects expired session | session_id, reason (sliding\|absolute) |
| `iam.session.revoked` | Logout or admin revocation | session_id, user_id, revoked_by |
| `iam.session.evicted` | Oldest session evicted at login | session_id, user_id |
| `iam.session.family_compromised` | Stale refresh token replayed | family_id, user_id |
| `iam.user.password_changed` | User changes own password | user_id, session_id |
| `iam.user.sessions_revoked_all` | revoke-all endpoint called | user_id, count, include_current |

## Implementation note

Each event is a NATS JetStream publish to subject `iam.*`. The audit module
consumes all `iam.*` subjects and persists to `04_audit` schema. No event
should contain password bytes, raw tokens, or PII beyond what's listed above.
