# 08_auth — Worklog

## 2026-04-03

### Built
- Auth backend (5 files: schemas, repository, service, routes, __init__)
- Tables: `18_fct_auth_credentials`, `40_fct_session_sessions`, `04_dim_auth_providers`
- Views: `v_40_sessions` (derived is_revoked flag)
- Registration flow: email uniqueness check → create user → hash password → create credential → create session → JWT pair
- Login flow: email lookup → argon2 verify → create session → JWT pair → audit event (success/failure)
- Token refresh: decode refresh JWT → verify not revoked → revoke old → create new → new JWT pair
- Logout: revoke session by JTI
- /me endpoint: decode access JWT → return user profile
- First-run setup: POST /v1/auth/setup (locked after first user)
- Setup status: GET /v1/auth/setup-status
- Frontend: /login page (polished, auto-redirect to /setup), /setup page (welcome wizard with shield icon)
- Auth layout: (auth) route group with no sidebar/topbar
- JWT config: JWT_SECRET, JWT_ACCESS_TTL_MINUTES, JWT_REFRESH_TTL_DAYS in .env

### Dependencies Added
- argon2-cffi (password hashing)
- PyJWT (JWT generation/validation)

### Security
- argon2id hashing, HS256 JWT, no open registration
- Setup endpoint returns 403 after first user
- Failed login attempts audited with outcome=failure
