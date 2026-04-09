## IAM — Identity & Access Management

## What this feature does

`03_iam` is tennetctl's identity layer. It owns the `users` and `sessions`
tables, the username+password login flow, and the session-cookie-based
access model that every other feature's HTTP routes will enforce. It is
the **second foundational feature** — every non-install HTTP request
passes through IAM's session middleware before reaching any other route.

V1 scope is deliberately small: one authentication method
(username+password), opaque session tokens stored as cookies, no OAuth,
no MFA, no magic links, no SSO. The goal is to get a production-viable
auth flow with minimum surface area. Everything else is future work,
gated behind the explicit "we need this now" threshold.

## Why it exists

Every runtime HTTP endpoint needs to know who is calling it. Without
IAM, tennetctl can boot, unseal the vault, and stare at the network —
but any API call gets a 401 because there is no user to attribute the
call to. Phase 3 of `00_setup` creates exactly one user (the first
admin); after install, that user logs in via this feature, and IAM
issues them a session they can use to create more users through the
IAM HTTP API.

## V1 scope — username + password only

The authentication model is the simplest thing that could possibly
work for a CLI + admin UI deployment:

```text
POST /v1/auth/login
    → verify username + Argon2id password hash
    → issue opaque session token (32 random bytes, base64url)
    → store Argon2id hash of token + metadata in 20_fct_sessions
    → set httpOnly + Secure cookie

GET /v1/auth/me
    → read cookie
    → look up session by token hash
    → return current user

POST /v1/auth/logout
    → soft-delete the session row
    → clear the cookie
```

No JWT. No refresh tokens. No OAuth. The session lives in the database
and is invalidated by deleting the row — which means revoking a
compromised session is a single `UPDATE` instead of a token-blacklist
dance. The opaque token pattern is strictly less complex than JWTs
and strictly more secure against token-replay after revocation.

### Why not JWT

JWTs are a reasonable choice for stateless microservice fleets where
DB round-trips on every request are a bottleneck. tennetctl is not
that: every request is going to hit Postgres anyway (for the actual
work), so adding one more indexed SELECT for session lookup costs
nothing measurable. In exchange we get:

- Immediate revocation (delete the row)
- No token signing key to rotate
- No key management story
- No "did we remember to validate the expiry?" footgun
- No "how long is a valid JWT?" trade-off — sessions have DB-enforced
  sliding and absolute lifetimes

When tennetctl grows an API for external integrations that need
stateless auth, the answer will be scoped API keys (already planned
in `02_vault.08_api_key`), not JWT.

## Session lifecycle

| Parameter              | Value         | Notes                                                  |
| ---------------------- | ------------- | ------------------------------------------------------ |
| Token length           | 32 bytes      | `secrets.token_urlsafe(32)` — ~43 url-safe chars       |
| Storage format in DB   | Argon2id hash | Same params as password hashing                        |
| Cookie name            | `tcc_session` | "Tennetctl cookie session"                             |
| Cookie flags           | `HttpOnly; Secure; SameSite=Strict; Path=/` | Production; dev may drop Secure |
| Sliding lifetime       | 24 hours      | Each request resets `expires_at = now + 24h`          |
| Absolute lifetime      | 30 days       | `created_at + 30d` — no extension past this           |
| Max concurrent per user| Unlimited v1  | Future: configurable per account type                 |

A session is valid if and only if:

1. The row exists with `deleted_at IS NULL`
2. `expires_at > now()` (sliding window)
3. `created_at + '30 days' > now()` (absolute window)

Any request on a valid session updates `last_seen_at` and extends
`expires_at` to `now() + 24h`. The absolute cap prevents indefinite
session extension.

## Scope boundaries

### In scope

- `users` table with `username`, `email`, `password_hash` in EAV
- `sessions` table with opaque token hashes
- `POST /v1/auth/login` — verify credentials, issue session
- `POST /v1/auth/logout` — revoke session
- `GET /v1/auth/me` — current-user endpoint
- Session cookie middleware that authenticates every non-auth route
- Argon2id password hashing (shared module with `00_setup.03_first_admin`)
- Password verification with timing-safe comparison
- Session cleanup job (periodic delete of expired rows) — future phase,
  v1 relies on the absolute 30d cap and accepts row bloat
- Full audit trail for login, logout, and login failures

### Out of scope for v1

- **OAuth / OIDC / SSO** — no Google login, no GitHub login, no SAML.
  The IAM schema is designed to extend to these via new `auth_types`
  dim rows, but v1 ships only `username_password`.
- **MFA** (TOTP, WebAuthn, SMS) — future. The `auth_types` pattern
  allows adding `totp` and `webauthn` as first-class methods.
- **Magic links / email-token login** — future. Requires an email
  delivery sub-feature that doesn't exist yet.
- **Password reset flow** — future. V1 password reset requires
  operator intervention (delete the password_hash attr via SQL, have
  the user log in with a new one via direct DB update, or re-run
  `tennetctl setup --resume` for the first admin).
- **Role-based permissions / RBAC** — future. V1 has one account
  type (`default_admin`) that can do everything, and a `default_user`
  stub that exists in the dim table but is not used yet.
- **Session concurrency limits** — future. V1 allows unlimited
  concurrent sessions per user.
- **JWT access tokens** — explicitly not on the roadmap. Scoped API
  keys (planned in `02_vault.08_api_key`) will serve the stateless
  auth use case.
- **Authlib / any OAuth library** — not imported. V1 is argon2-cffi
  + asyncpg + secrets module. No Authlib.

## Dependencies

- Depends on: `00_bootstrap` (its own schema, users table, sessions
  table, dim tables — all land in one bootstrap migration)
- Depends on: `02_vault.01_setup` (the vault must be unsealed before
  IAM can serve any requests, because IAM reads its own config from
  the vault at startup; there is no direct data dependency, only a
  "vault must be up" lifecycle dependency)
- Depends on: `backend/01_core/password.py` (the shared Argon2id
  wrapper, also used by `00_setup.03_first_admin`)
- Depended on by: every runtime HTTP route in every feature — the
  session middleware is installed on the FastAPI app in `01_core`
  and every non-auth route requires a valid session

## Relationship with 00_setup

`00_setup.03_first_admin` creates the very first row in
`03_iam.10_fct_users`. It runs the Argon2id hash using the same
`backend/01_core/password.py` module that IAM's login route uses to
verify passwords. The two features share:

- The Argon2id parameter constants (`TIME_COST`, `MEMORY_COST`, ...)
- The `hash_password` / `verify_password` functions
- The DB schema (IAM owns it, setup writes to it once)

IAM is built after `00_setup`'s bootstrap schema migration lands but
before the install wizard runs in anger: the wizard's Phase 3 inserts
into IAM tables, so the tables must exist first, but IAM's HTTP
routes don't run during install (install is pure CLI).
