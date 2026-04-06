# IAM System (02_iam) Gap Analysis

Comprehensive comparison against Auth0, Clerk, and Okta. Updated: 2026-04-04.

---

## What We HAVE

| Sub-feature | Status |
|---|---|
| Org CRUD + pagination + search + cache | ✅ Built |
| User CRUD + pagination + EAV attrs + cache | ✅ Built |
| Workspace CRUD + members | ✅ Built |
| Group CRUD + members | ✅ Built |
| Org membership + roles + invitations | ✅ Built |
| Workspace membership | ✅ Built |
| Email+password auth | ✅ Built |
| Social OAuth (Google/GitHub/Apple/Microsoft/GitLab/Discord/Slack) | ✅ Built |
| Magic links (passwordless) | ✅ Built |
| Email OTP (login + verify) | ✅ Built |
| Password reset | ✅ Built |
| Session create/revoke/revoke-all (09_session) | ✅ Built |
| Connected OAuth providers (list/unlink) | ✅ Built |
| Auth config (platform + per-org overrides) | ✅ Built |
| RBAC (roles + permissions + user assignments) | ✅ Built |
| Feature flags + rule engine + segments + variants + targeting | ✅ Built |
| License profiles | ✅ Built |
| Projects | ✅ Built |
| Valkey/Redis cache layer (user, org, flags, roles, sessions, OTP, magic link) | ✅ Built |
| JWT auth middleware + session cache check + `require_auth` / `optional_auth` deps | ✅ Built |
| Account lockout after 5 failed logins (15-min Redis window) | ✅ Built |
| MFA/TOTP (34_mfa) — enroll, verify, disable, backup codes | ✅ Built |
| Invitation system (33_invitation) — invite, accept, revoke | ✅ Built |
| Rate limiting on auth endpoints — per-IP sliding window | ✅ Built |
| Email verification enforcement — config-driven | ✅ Built |
| Personal access tokens (35_personal_access_token) — create, list, revoke | ✅ Built |
| Email domain restrictions per org — config-driven via org_settings | ✅ Built |
| Org user limit enforcement — config-driven via org_settings.max_users | ✅ Built |
| Sessions management UI + MFA settings UI + API tokens UI | ✅ Built |
| Backend tests: auth (12), MFA (6), org (16), group (13), org_member (10), group_member (10) | ✅ 67 tests passing |

---

## P0 Gaps — ALL CLOSED ✅

| Gap | Status |
|---|---|
| Dedicated session management — list sessions, revoke by ID, revoke all | ✅ Done (09_session) |
| MFA/TOTP — authenticator app, TOTP codes, backup recovery codes | ✅ Done (34_mfa) |
| Invitation system — invite users to org by email, accept/decline flow | ✅ Done (33_invitation) |
| Pagination completeness — all list endpoints have offset + total | ✅ Done |
| Email verification enforcement — config-driven | ✅ Done |
| Rate limiting on auth endpoints — per-IP sliding window | ✅ Done |

## P1 Gaps

| Gap | Reference | Status |
|---|---|---|
| **Personal access tokens** — long-lived API keys scoped to a user | GitHub PATs; Clerk API keys | ✅ Done (35_personal_access_token) |
| **Email domain restrictions per org** — only allow users with specific email domains | Clerk allowed email domains; Auth0 database connections | ✅ Done (org_member service, org_settings config) |
| **Org user limit enforcement** — enforce max users per org | Clerk org membership limits; Auth0 quotas | ✅ Done (org_member service, org_settings.max_users) |
| **SAML SSO** — enterprise SSO via SAML 2.0 | Auth0 SAML; Okta SAML IdP | 🔲 Not built (enterprise, out of scope for v1) |
| **SCIM provisioning** — auto-provision/deprovision from HR systems | Okta SCIM 2.0; Auth0 SCIM | 🔲 Not built (enterprise, out of scope for v1) |
| **Full audit log on every IAM mutation** — 100% mutation coverage | Auth0 log stream; Clerk audit | 🔲 Partial (major flows have audit events) |
| **Impersonation** — admin act-as another user with clear audit trail | Auth0 impersonation; Okta impersonation | 🔲 Not built |
| **Account linking** — merge email + OAuth accounts | Auth0 account linking; Clerk identity linking | 🔲 Not built |
| **User avatar/profile photo** — upload + CDN URL | Auth0 user metadata `picture` | 🔲 Not built |

## P2 Gaps (Nice to Have — not in scope for v1)

| Gap | Reference |
|---|---|
| WebAuthn/passkeys — FIDO2 biometric auth | Auth0 WebAuthn; Clerk passkeys |
| Passwordless phone/SMS OTP — login via SMS code | Auth0 SMS passwordless |
| Custom JWT claims — embed org roles, plan tier, feature flags | Auth0 Actions; Clerk session claims |
| Hosted login UI — white-label login page | Auth0 Universal Login |
| B2B org discovery — find org by email domain | Clerk org discovery |
| Social connection health checks | Auth0 connection test endpoint |
| Refresh token rotation policies | Auth0 refresh token rotation |
| Concurrent session limits — max N active sessions | Okta session policies |
| IP allowlist/blocklist per org | Auth0 attack protection; Okta network zones |

---

## Summary

The IAM system is **production-ready** for core auth flows. All P0 gaps are closed. The remaining P1 items (SAML, SCIM, impersonation, account linking) are enterprise-grade features requiring significant infrastructure and are deferred to a future release.

**Test coverage**: 67 backend integration tests passing, covering org, group, org_member, group_member, auth, and MFA sub-features.
