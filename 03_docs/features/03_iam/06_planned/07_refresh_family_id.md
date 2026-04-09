## Planned: Refresh Token Family ID

**Severity if unbuilt:** HIGH (once refresh tokens ship)
**Depends on:** v1 refresh token implementation

## Problem

V1 refresh tokens rotate on each `/auth/refresh` call — the old token is
invalidated and a new one is issued. But if an attacker steals a refresh
token before it is rotated, both the attacker and the legitimate user can
hold valid tokens simultaneously. When the legitimate user next refreshes,
their old token is replayed by the attacker with no detection.

Without family IDs there is no way to know that two concurrent refreshes
came from the same stolen token.

## Fix when built

### Schema change

Add `refresh_family_id VARCHAR(36)` to `20_fct_sessions`. Set to a new
UUID v7 at login. Never changes for the lifetime of the session.

### Rotation logic

On `POST /v1/auth/refresh`:
1. Look up session by `refresh_token_prefix` + Argon2id verify.
2. Check the presented token matches the *current* generation. Store a
   `refresh_generation SMALLINT` counter on the session row, incrementing
   on each rotation.
3. If the prefix matches but the generation is old (a stale token is being
   replayed), treat it as compromise:
   - Revoke all sessions with the same `refresh_family_id`.
   - Emit `iam.session.family_compromised` audit event with the family ID.
   - Return 401 `SESSION_COMPROMISED`.
4. On legitimate refresh: issue new token, increment `refresh_generation`,
   update `refresh_token_hash` + `refresh_token_prefix`.

### Schema additions

```sql
ALTER TABLE "03_iam"."20_fct_sessions"
    ADD COLUMN refresh_family_id  VARCHAR(36),
    ADD COLUMN refresh_generation SMALLINT NOT NULL DEFAULT 0;
```

This is a new migration, not a change to `003_iam_bootstrap.sql`.
