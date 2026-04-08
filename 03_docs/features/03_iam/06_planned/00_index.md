## IAM — Planned (Post-v1)

V1 IAM scope is deliberately narrow: the minimum needed for the first admin
to log in, use the product, and log out. Full IAM (user management, RBAC,
MFA, audit completeness, rate limiting, etc.) is a later module.

Each file here is a named, scoped backlog item. When a planned item is
promoted to active work, move it into `05_sub_features/` and create the
standard scope/design/sql/api files there.

## Revised Sprint Order (2026-04-09)

Sprints are now: (1) Groups — approved, unchanged; (2) Foundation — scopes, categories, products, feature registry (new); (3) RBAC three-tier; (4) Feature Flags; (5) Planning module. The Foundation sprint was inserted because RBAC, Flags, and future products all depend on shared scope/category/product/feature primitives that did not exist.

## Index

Items marked ✅ have been implemented. Items marked 🔒 are security-critical.

### Security & Auth Hardening

| File | Item | Severity | Status |
| ---- | ---- | -------- | ------ |
| [01_rate_limiting.md](01_rate_limiting.md) | Extend rate limiting beyond login (refresh endpoint, per-IP, configurable) | HIGH | pending |
| [02_account_lockout.md](02_account_lockout.md) | Account lockout after N failed logins | MEDIUM | pending |
| [03_password_change.md](03_password_change.md) | `PATCH /v1/auth/password` — change own password | CRITICAL 🔒 | pending |
| [04_revoke_sessions.md](04_revoke_sessions.md) | Revoke all other sessions | CRITICAL 🔒 | ✅ implemented as `DELETE /v1/sessions` |
| [05_shell_history.md](05_shell_history.md) | Block secrets from being passed as CLI flags | CRITICAL 🔒 | pending |
| [06_raw_token_leak.md](06_raw_token_leak.md) | Zero raw token in memory after cookie is set | CRITICAL 🔒 | pending |
| [07_refresh_family_id.md](07_refresh_family_id.md) | Refresh token family ID for replay/compromise detection | HIGH | pending |
| [08_argon2_rehash.md](08_argon2_rehash.md) | Lazy re-hash on login when Argon2id params change | HIGH | pending |
| [09_password_policy.md](09_password_policy.md) | Stronger password policy (16 chars, zxcvbn check) | MEDIUM | pending |
| [10_email_verification.md](10_email_verification.md) | Email verification flow | MEDIUM | pending |
| [11_session_type.md](11_session_type.md) | `session_type` dim (web / mobile / cli / api_key) | MEDIUM | pending |
| [12_max_sessions.md](12_max_sessions.md) | `max_sessions_per_user` setting + oldest-evict policy | MEDIUM | pending |
| [13_audit_completeness.md](13_audit_completeness.md) | Full audit event coverage (revoke, expire, password change) | HIGH | pending |
| [14_security_headers.md](14_security_headers.md) | Security response headers (CSP, HSTS, X-Frame-Options, etc.) | LOW | ✅ implemented (`SecurityHeadersMiddleware`) |
| [15_csrf_secondary.md](15_csrf_secondary.md) | Enforce `Content-Type: application/json` on mutations | LOW | pending |
| [19_jwt_rs256.md](19_jwt_rs256.md) | JWT RS256 + JWKS endpoint (`/.well-known/jwks.json`) | MEDIUM | pending |
| [20_password_reset.md](20_password_reset.md) | Password reset flow (forgot + reset endpoints) | CRITICAL 🔒 | pending |
| [21_mfa_totp.md](21_mfa_totp.md) | MFA / TOTP (enroll, verify, backup codes) | HIGH | pending |
| [23_frontend_auth.md](23_frontend_auth.md) | httpOnly cookie auth + CSRF protection (frontend + backend) | HIGH 🔒 | pending |

### Access Control

| File | Item | Severity | Status |
| ---- | ---- | -------- | ------ |
| [16_rbac.md](16_rbac.md) | RBAC — roles, permissions, user-role assignment, runtime check | CRITICAL 🔒 | pending |
| [17_groups.md](17_groups.md) | Groups sub-feature (CRUD + membership) — prerequisite for RBAC | HIGH | pending |
| [18_scope_enforcement.md](18_scope_enforcement.md) | Org/workspace access guards on all routes | CRITICAL 🔒 | pending |

### User & Org Management

| File | Item | Severity | Status |
| ---- | ---- | -------- | ------ |
| [22_org_invitations.md](22_org_invitations.md) | Org invitation flow (invite-by-email, pending/accept/expire) | HIGH | pending |
| [24_user_search.md](24_user_search.md) | User search and filtering (q, status, date range) | MEDIUM | pending |
| [25_eav_attrs_endpoints.md](25_eav_attrs_endpoints.md) | Generic EAV attrs REST API for all entities | MEDIUM | pending |

### Future Features

| File | Item | Severity | Status |
| ---- | ---- | -------- | ------ |
| [26_feature_flags.md](26_feature_flags.md) | Feature flags sub-feature (targeted rollouts, kill switch) | LOW | pending |

### Foundation — Platform Primitives

| File | Item | Severity | Status |
| ---- | ---- | -------- | ------ |
| [27_products_catalog.md](27_products_catalog.md) | Platform product catalog + workspace-product subscriptions | HIGH | pending |
| [28_feature_registry.md](28_feature_registry.md) | Queryable feature registry (dim_features) | MEDIUM | pending |
| [29_categories_and_scopes.md](29_categories_and_scopes.md) | Shared dim_scopes + dim_categories enums | HIGH | pending |
