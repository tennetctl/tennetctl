# ADR 012: IAM Architecture — God-Tier Feature Scope

**Date:** 2026-03-30
**Status:** Accepted
**Feature:** IAM (Identity & Access Management)

---

## Context

tennetctl needed a production-grade IAM layer comparable to Auth0 / WorkOS / Clerk / Stytch — but self-hosted, fully auditable, and integrated with the existing FastAPI + asyncpg + PostgreSQL stack.

## Decision

Implement a comprehensive IAM system across 36 migrations, 24 backend modules, and 24 frontend pages covering:

### Authentication
- Email/password with bcrypt
- JWT (access + refresh tokens) via authlib
- Magic links (token-based passwordless)
- OAuth2 Social (Google, GitHub) — extensible to any provider
- SAML 2.0 SSO — IdP-initiated and SP-initiated, SLO (POST + GET)
- SMS OTP — pluggable SMS provider (log/Twilio/SNS)
- TOTP (authenticator app) — backup codes, TOTP setup/verify/disable
- WebAuthn/FIDO2 — migration scaffold exists, full flow TBD

### Authorization
- RBAC — roles, permissions, role-permission matrix
- Group-based role inheritance
- Workspace-level membership scoping
- Conditional Access Policies (IP, MFA required, time window, device, location)
- Temporary grants + impersonation with audit trail

### Identity
- Multi-tenant orgs with slug-based routing
- SCIM 2.0 (RFC 7644) — User + Group provisioning
- Account linking (multiple social providers per user)
- Invitation flow (email-based org onboarding)
- Bulk CSV user import
- Portal views — role-based page visibility via CTE resolution

### Developer Surface
- M2M OAuth2 clients (client credentials flow)
- API keys with last-used tracking
- Webhooks — CRUD + delivery log + replay
- Log streams — Datadog, Splunk, Elastic, generic webhook
- Email templates — 5 built-in types, variable substitution, preview

### Security Operations
- IP allowlist / blocklist — CIDR subnet matching (`<<= cidr`)
- Password policy — org-level configurable (min length, complexity, history)
- Session policy — max sessions, idle/absolute timeout
- MFA enforcement — per-org configurable
- JWT claims configuration — org-level custom claims
- Audit log — all mutations captured with actor_id, org_id, entity

### Infrastructure
- `JWTAuthMiddleware` — Bearer + sc_access_token cookie, populates `request.state.*`
- Public paths bypass token requirement but still parse token if present
- SCIM uses separate Bearer token auth (SHA-256 stored, never raw)

## Consequences

- **+** Feature-complete IAM removes dependency on external auth providers
- **+** Full audit trail on every mutation via `emit_audit_event`
- **+** 36 migrations all have UP + DOWN for clean rollback
- **-** WebAuthn and adaptive auth still need full implementation
- **-** actor_id still None on ~8 remaining route files (session/webhook/oauth2/scim)

## Remaining Gaps (ordered by priority)

1. **WebAuthn/FIDO2** — passkey registration + assertion (migration 024 is a placeholder)
2. **Adaptive Authentication** — risk scoring, device fingerprinting, geo anomaly detection
3. **Complete actor_id propagation** — session, webhook, oauth2, scim routes
4. **ABAC engine** — access_policy conditions have schema/DB; evaluation engine not built
5. **Directory Sync** — LDAP/Active Directory real-time sync beyond SCIM
