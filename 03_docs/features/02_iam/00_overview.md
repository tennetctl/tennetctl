# IAM: Identity & Access Management

## What is this feature?

IAM is the security and identity backbone of tennetctl. Every user, organisation, authentication credential, access token, role assignment, and feature flag passes through this module. Nothing in the platform operates without first being verified by IAM.

## Why it exists

tennetctl is a multi-tenant B2B platform. Every customer is an **Organisation**. Within an org, users join as **Members** with specific **Roles**. Access to APIs, UI pages, and platform features is gated by:

1. Valid authentication (JWT access tokens, rotated refresh tokens)
2. Role-based permissions (RBAC)
3. Org-level feature flags (god-tier feature flag engine)
4. IP policies, API keys, and temporary grants

## Strategic Context

### User Personas
- **Security Admin**: Needs centralized control over users, orgs, and access policies. Requires MFA enforcement and audit visibility.
- **Platform Developer**: Needs easy-to-use APIs for authentication, authorization, and feature gating. Wants "invisible" security.
- **End User**: Expects seamless login experiences (SSO, Passkeys) and self-service profile management.

### Competitor Analysis
| Competitor | Strength | Gap vs tennetctl |
|------------|----------|-----------------|
| **Auth0 / Okta** | Mature, wide integrations | Extremely high cost; logic siloed in third-party cloud. |
| **Clerk** | Dev-friendly UI components | Limited multi-tenancy depth; hard to customize core B2B logic. |
| **Keycloak** | Open source, powerful | High maintenance overhead; UI/UX feels dated and complex. |

### Gap Analysis
tennetctl bridges the gap between "easy but expensive" (Auth0) and "powerful but painful" (Keycloak). 
- **Local First**: Identity logic lives co-located with your business data, minimizing latency and vendor lock-in.
- **B2B Native**: Designed from the ground up for complex multi-tenant hierarchies, not just single-user apps.
- **Integrated Gating**: Feature flags are a first-class citizen of IAM, not an afterthought.

## Scope Boundaries

**In scope:**
- Multi-tenant org and user management
- Email/password authentication with Argon2 hashing
- OAuth2 social login (Google, GitHub)
- SSO via SAML 2.0 and OIDC
- SCIM 2.0 provisioning
- JWT access/refresh token issuance and rotation
- MFA (TOTP, backup codes)
- RBAC with granular permissions
- Feature flags with rule engine and segmentation
- API key management with scopes
- Webhooks for identity events
- Invitations, email templates, portal customisation
- User import (CSV/JSON bulk upload)
- IP allowlist/blocklist policies
- Temporary elevated grants
- Passkeys (WebAuthn)
- LDAP integration
- Service accounts for machine-to-machine auth

**Out of scope (handled by other modules):**
- Billing (→ `06_billing`)
- Notifications (→ `05_notify`)
- Audit log storage (→ `03_audit`; IAM emits events but does not store them)

## Sub-feature Groups

| Group | Sub-features |
|-------|-------------|
| **Core Identity** | org, user, workspace, group, org_member, group_member, workspace_member |
| **Authentication** | auth, session, auth_config, mfa, oauth2, sso, scim, account_linking, password_policy, session_policy, impersonation |
| **Access Control** | rbac, api_key, temp_grant, access_policies, ip_policy |
| **Feature Flags** | feature_flag, flag_env_config, flag_attr, flag_segment, flag_tag, flag_variant, flag_identity_target, flag_prerequisite, flag_rule_engine |
| **Lifecycle** | invitation, webhook, email_template, log_stream, portal_view, user_import |
| **Compliance** | audit |

## Roadmap

### Delivered (Did)
- Multi-tenant Core Identity (Org/User/Workspace)
- Standard Auth (Email/Password, JWT rotation)
- Feature Flag Rule Engine

### In Progress (Doing)
- Passkey (WebAuthn) support
- SCIM 2.0 provisioning

### Planned (Will Do)
- LDAP integration
- Fine-grained IP policies with Geo-fencing

## Status

- **Status:** DONE
- **Migrations applied:** 21
- **E2E tests:** 11/11 passing
- **Frontend pages:** 25 pages at `/iam/*`
