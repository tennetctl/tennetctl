# 08_auth — Architecture

## Table Relationships

```
04_dim_auth_providers ←FK── 18_fct_auth_credentials
                                     │ user_id
                                     ▼
                              10_fct_user_users (cross-module)

40_fct_session_sessions
  │ user_id → 10_fct_user_users (cross-module, no FK)
  │ jti → unique, used for JWT revocation lookup
```

## Indexes

| Index | Columns | Purpose |
|-------|---------|---------|
| `pk_18_fct_auth_credentials` | (id) | PK |
| `uq_18_fct_auth_credentials_user_prov` | (user_id, provider_id) | One credential per provider |
| `pk_40_fct_session_sessions` | (id) | PK |
| `uq_40_fct_session_sessions_jti` | (jti) | JWT ID uniqueness |
| `idx_40_fct_session_user` | (user_id, created_at DESC) | User session listing |
| `idx_40_fct_session_active` | (jti) WHERE revoked_at IS NULL | Fast active session lookup |

## Backend Files

```
01_backend/02_features/02_iam/08_auth/
├── __init__.py
├── schemas.py      — RegisterRequest, LoginRequest, TokenResponse, RefreshRequest, MeResponse
├── repository.py   — Credential + session CRUD
├── service.py      — Auth flows (register, login, refresh, logout, get_me, decode_token)
└── routes.py       — FastAPI router at /v1/auth
```

## Auth Flow Diagram

```
Register: POST /v1/auth/register
  → create_user (02_user service)
  → hash password (argon2id)
  → insert credential (18_fct_auth_credentials)
  → create session (40_fct_session_sessions)
  → generate JWT pair
  → emit audit event
  → return {access_token, refresh_token}

Login: POST /v1/auth/login
  → lookup user by email
  → verify argon2 hash
  → create session
  → generate JWT pair
  → emit audit event (success or failure)
  → return {access_token, refresh_token}

Refresh: POST /v1/auth/refresh
  → decode refresh JWT
  → verify session not revoked
  → revoke old session
  → create new session
  → generate new JWT pair
  → return {access_token, refresh_token}
```
