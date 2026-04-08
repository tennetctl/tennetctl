# IAM Auth — Scope

## What it does

Implements the four HTTP endpoints that make up v1 authentication:
`POST /v1/auth/login`, `POST /v1/auth/logout`, `POST /v1/auth/refresh`,
`GET /v1/auth/me`. Owns the JWT middleware that every other feature's
routes depend on — if IAM is not running, nothing else works.

The auth model: username + Argon2id-hashed password issues a **JWT access
token** (15 min, HS256, signed with a key from Vault) and an **opaque
refresh token** (7 days, Argon2id hash in DB, rotated on every use). No
MFA, no OAuth, no RBAC — those are future sub-features.

See `03_iam/04_architecture/01_architecture.md` for full flow diagrams and
the security properties table.

## The four endpoints

### `POST /v1/auth/login`

Request: `{ "username": "...", "password": "..." }`

Response on success (200):
```json
{
  "ok": true,
  "data": {
    "access_token": "<jwt>",
    "token_type": "bearer",
    "user": { "id": "...", "username": "...", "email": "..." }
  }
}
```

Plus `Set-Cookie: tcc_refresh=<opaque>; HttpOnly; Secure; SameSite=Strict; Path=/v1/auth; Max-Age=604800`.

The access token is returned in the response body only — never in a cookie.
The frontend must store it in memory (not `localStorage` or `sessionStorage`)
to prevent XSS theft.

Response on failure (401):
```json
{ "ok": false, "error": { "code": "INVALID_CREDENTIALS", "message": "Invalid username or password" } }
```

Identical error shape and latency for wrong password and unknown username
(Argon2id dummy hash equalises timing).

### `POST /v1/auth/refresh`

Request: empty body; `tcc_refresh` cookie required.

Response on success (200):
```json
{
  "ok": true,
  "data": { "access_token": "<new_jwt>", "token_type": "bearer" }
}
```

Plus a new `Set-Cookie: tcc_refresh=<new_opaque>` replacing the old one.
The old refresh token is invalidated atomically on the same DB write that
persists the new hash.

Response on failure (401): `REFRESH_TOKEN_REQUIRED`, `INVALID_REFRESH_TOKEN`,
`REFRESH_TOKEN_EXPIRED`, or `SESSION_EXPIRED` (past `absolute_expires_at`).

### `POST /v1/auth/logout`

Request: empty body; `Authorization: Bearer <jwt>` required.

Response (204): empty, with `Set-Cookie: tcc_refresh=; Max-Age=0`.

The session row is soft-deleted (`deleted_at = now()`, `status = revoked`)
so the audit trail survives. The refresh cookie is cleared. In-flight access
tokens expire within 15 minutes naturally.

### `GET /v1/auth/me`

Request: `Authorization: Bearer <jwt>` required.

Response (200):

```json
{
  "ok": true,
  "data": {
    "user": { "id": "...", "username": "...", "email": "...", "account_type": "default_admin" },
    "session": { "id": "...", "refresh_expires_at": "...", "absolute_expires_at": "..." }
  }
}
```

## JWT middleware

Installed on the top-level FastAPI app as an `@app.middleware("http")`
function. Runs before any route handler. Exempt paths:

```text
EXEMPT_PATHS = {
    "/healthz",
    "/v1/auth/login",
    "/v1/auth/refresh",
    "/v1/vault/status",
    "/v1/vault/unseal",
    "/v1/vault/seal",
}
```

For any non-exempt request:

1. Read `Authorization: Bearer <token>`. Missing → 401 `TOKEN_REQUIRED`.
2. Verify JWT signature with the key loaded from Vault at startup.
   Invalid signature → 401 `INVALID_TOKEN`.
3. Check `exp`, `nbf` claims. Expired → 401 `TOKEN_EXPIRED`.
4. Single PK lookup on `20_fct_sessions` by `sid` claim. Check
   `deleted_at IS NULL` and `status = active`. Revoked → 401 `SESSION_REVOKED`.
5. Attach `user_id` and `session_id` to `request.state`.
6. Call the next handler.

## JWT signing key

Loaded from Vault path `iam/jwt_signing_key` at process startup.
If Vault is sealed, the backend refuses to start.

Env overrides for development / testing:

```text
TENNETCTL_JWT_SECRET          override signing key (hex string)
TENNETCTL_JWT_EXPIRY_SECONDS  override access token TTL (default 900)
```

These overrides are ignored if `ENV=prod`.

## Password + token hashing

`hash_password` and `verify_password` live in `backend/01_core/password.py`.
Used for user passwords (login) and refresh token hashes (login, refresh).
Same Argon2id parameters for both — a compromised DB gives no shortcut on
tokens vs. passwords.

## In scope

- `POST /v1/auth/login` — credential verify, JWT + refresh token issue
- `POST /v1/auth/refresh` — refresh token rotate, new JWT issue
- `POST /v1/auth/logout` — session soft-delete, cookie clear
- `GET /v1/auth/me` — current user + session summary
- JWT middleware with exempt path list
- Refresh token rotation (atomic hash replace on each /refresh call)
- Absolute expiry enforcement (`refresh_expires_at`, `absolute_expires_at`)
- Argon2id timing equalisation on "user not found" login path
- Repository: `get_user_by_username`, `get_password_hash`, `create_session`,
  `find_session_by_refresh_prefix`, `rotate_refresh_token`, `revoke_session`,
  `get_session_summary`
- Pydantic v2 schemas for login request/response, refresh response, me response
- Cookie builder: `HttpOnly; Secure; SameSite=Strict` in prod, drops `Secure`
  in dev
- `TENNETCTL_JWT_SECRET` / `TENNETCTL_JWT_EXPIRY_SECONDS` env overrides
  (dev/test only)

## Out of scope (deferred)

- Rate limiting on login — `06_planned/01_rate_limiting.md`
- Account lockout — `06_planned/02_account_lockout.md`
- Password change endpoint — `06_planned/03_password_change.md`
- Revoke-all sessions — `06_planned/04_revoke_sessions.md`
- Refresh token family ID / replay detection — `06_planned/07_refresh_family_id.md`
- Lazy Argon2id re-hash on login — `06_planned/08_argon2_rehash.md`
- Session type dim (web/mobile/cli) — `06_planned/11_session_type.md`
- Max sessions per user — `06_planned/12_max_sessions.md`
- MFA, OAuth, SSO — future `03_iam` sub-features
- User CRUD — future `03_iam.02_users` sub-feature
- Scoped API keys — `02_vault.08_api_key`

## Acceptance criteria

### Login

- [ ] Valid credentials → 200 with `access_token` (JWT) + `tcc_refresh` cookie
- [ ] Access token is a valid HS256 JWT with `sub`, `sid`, `jti`, `exp`, `nbf`, `iat`
- [ ] `exp - iat = 900` seconds (or `TENNETCTL_JWT_EXPIRY_SECONDS` override)
- [ ] `tcc_refresh` cookie has `HttpOnly; Secure; SameSite=Strict; Path=/v1/auth; Max-Age=604800` in prod
- [ ] `Secure` flag dropped in dev mode (`ENV=dev`)
- [ ] Invalid username → 401 `INVALID_CREDENTIALS` (same shape as wrong password)
- [ ] Invalid password → 401 `INVALID_CREDENTIALS`
- [ ] Login latency for "user not found" within 10% of "wrong password" over 50 trials
- [ ] Session row created with `status = active`, `refresh_token_hash` set,
      `refresh_expires_at = now() + 7d`, `absolute_expires_at = now() + 30d`
- [ ] `iam.user.logged_in` event emitted on success
- [ ] `iam.login.failed` event emitted on failure (no password material)

### Refresh

- [ ] Valid `tcc_refresh` cookie → 200 with new `access_token` + new `tcc_refresh` cookie
- [ ] Old refresh token no longer accepted after rotation
- [ ] `refresh_token_hash` and `refresh_token_prefix` updated atomically in DB
- [ ] Missing cookie → 401 `REFRESH_TOKEN_REQUIRED`
- [ ] Invalid/unknown cookie → 401 `INVALID_REFRESH_TOKEN`
- [ ] Past `refresh_expires_at` → 401 `REFRESH_TOKEN_EXPIRED`
- [ ] Past `absolute_expires_at` → 401 `SESSION_EXPIRED`

### Middleware behaviour

- [ ] Non-exempt request without `Authorization` header → 401 `TOKEN_REQUIRED`
- [ ] Invalid JWT signature → 401 `INVALID_TOKEN`
- [ ] Expired JWT (`exp < now()`) → 401 `TOKEN_EXPIRED`
- [ ] JWT for a revoked session → 401 `SESSION_REVOKED`
- [ ] Valid JWT → handler runs, `user_id` + `session_id` in `request.state`
- [ ] Exempt paths bypass the middleware entirely

### Logout

- [ ] Valid JWT → 204, session row revoked, `tcc_refresh` cookie cleared
- [ ] Subsequent request with same JWT returns 401 `SESSION_REVOKED` (within 15 min TTL)
- [ ] Subsequent refresh with same `tcc_refresh` cookie returns 401
- [ ] `iam.user.logged_out` event emitted

### /me

- [ ] Valid JWT → 200 with user + session summary
- [ ] `password_hash` not present at any nesting level
- [ ] Missing JWT → 401 from middleware, not the handler

### Security

- [ ] No route logs raw password, raw access token, or raw refresh token
- [ ] Error responses contain only `{ code, message }` — no stack trace, SQL, internals
- [ ] `verify_password` is the only password/token comparison path (no `==` on secret bytes)
- [ ] JWT signing key loaded from Vault; env override refused in prod

## Dependencies

- Depends on: `03_iam.00_bootstrap` (all IAM tables and dim seeds)
- Depends on: `02_vault` (JWT signing key at `iam/jwt_signing_key`)
- Depends on: `backend/01_core/password.py` (Argon2id wrapper)
- Depends on: `backend/01_core/response.py` (response envelope helpers)
- Depends on: `backend/01_core/events.py` (audit event bus)
- Depended on by: every non-auth HTTP route in every feature (via JWT middleware)
