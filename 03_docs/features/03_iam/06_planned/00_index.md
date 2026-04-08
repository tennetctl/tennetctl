## IAM — Planned (Post-v1)

V1 IAM scope is deliberately narrow: the minimum needed for the first admin
to log in, use the product, and log out. Full IAM (user management, RBAC,
MFA, audit completeness, rate limiting, etc.) is a later module.

Each file here is a named, scoped backlog item. When a planned item is
promoted to active work, move it into `05_sub_features/` and create the
standard scope/design/sql/api files there.

## Index

| File | Item | Severity if unbuilt |
| ---- | ---- | ------------------- |
| [01_rate_limiting.md](01_rate_limiting.md) | Login rate limiting (per-IP + per-username) | HIGH |
| [02_account_lockout.md](02_account_lockout.md) | Account lockout after N failed logins | MEDIUM |
| [03_password_change.md](03_password_change.md) | `PATCH /v1/auth/password` — change own password | CRITICAL |
| [04_revoke_sessions.md](04_revoke_sessions.md) | `POST /v1/auth/revoke-all` — revoke all other sessions | CRITICAL |
| [05_shell_history.md](05_shell_history.md) | Block secrets from being passed as CLI flags | CRITICAL |
| [06_raw_token_leak.md](06_raw_token_leak.md) | Zero raw token in memory after cookie is set | CRITICAL |
| [07_refresh_family_id.md](07_refresh_family_id.md) | Refresh token family ID for replay/compromise detection | HIGH |
| [08_argon2_rehash.md](08_argon2_rehash.md) | Lazy re-hash on login when Argon2id params change | HIGH |
| [09_password_policy.md](09_password_policy.md) | Stronger password policy (16 chars, zxcvbn check) | MEDIUM |
| [10_email_verification.md](10_email_verification.md) | Verify first admin email at install time | MEDIUM |
| [11_session_type.md](11_session_type.md) | `session_type` dim (web / mobile / cli / api_key) | MEDIUM |
| [12_max_sessions.md](12_max_sessions.md) | `max_sessions_per_user` setting + oldest-evict policy | MEDIUM |
| [13_audit_completeness.md](13_audit_completeness.md) | Full audit event coverage (revoke, expire, password change) | HIGH |
| [14_security_headers.md](14_security_headers.md) | Cache-Control, Vary, X-Frame-Options, CSP headers | LOW |
| [15_csrf_secondary.md](15_csrf_secondary.md) | Enforce `Content-Type: application/json` on mutations | LOW |
