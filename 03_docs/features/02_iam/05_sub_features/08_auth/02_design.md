# 08_auth — Design

## Data Model

### Credentials: `18_fct_auth_credentials`
One row per (user, provider) pair. For email/password, stores argon2id hash.

| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR(36) PK | UUID v7 |
| user_id | VARCHAR(36) | FK to user (cross-module, no enforced FK) |
| provider_id | SMALLINT FK | → 04_dim_auth_providers (1=email_password) |
| credential_hash | TEXT | argon2id hash (NULL for OAuth-only) |
| is_active | BOOLEAN | Can disable without deleting |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | Auto via trigger |

Unique constraint: `(user_id, provider_id)` — one credential per provider per user.

### Sessions: `40_fct_session_sessions`
JWT sessions with revoke-not-delete lifecycle. No `updated_at`, no `deleted_at`.

| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR(36) PK | UUID v7 |
| user_id | VARCHAR(36) | Who owns this session |
| jti | VARCHAR(36) UNIQUE | JWT ID claim — lookup key for revocation |
| ip_address | VARCHAR(64) | Client IP at login |
| user_agent | TEXT | Browser/client identifier |
| expires_at | TIMESTAMP | When refresh token expires |
| revoked_at | TIMESTAMP | NULL = active, SET = revoked |
| created_at | TIMESTAMP | Session creation time |

### Providers: `04_dim_auth_providers`
| ID | Code | Label |
|----|------|-------|
| 1 | email_password | Email & Password |
| 2 | google | Google (future) |
| 3 | github | GitHub (future) |

## JWT Structure

```json
{
  "sub": "user_uuid",
  "jti": "session_jti",
  "type": "access|refresh",
  "iat": 1712160000,
  "exp": 1712160900
}
```

- Algorithm: HS256
- Secret: `JWT_SECRET` env var
- Access TTL: 15 min (configurable via `JWT_ACCESS_TTL_MINUTES`)
- Refresh TTL: 30 days (configurable via `JWT_REFRESH_TTL_DAYS`)

## First-Run Setup Flow

1. `GET /v1/auth/setup-status` → `{needs_setup: true}` when zero users exist
2. `POST /v1/auth/setup` → creates admin user + returns JWT (403 if users already exist)
3. Frontend `/login` auto-redirects to `/setup` when `needs_setup=true`
4. Frontend `/setup` auto-redirects to `/login` when setup already complete
