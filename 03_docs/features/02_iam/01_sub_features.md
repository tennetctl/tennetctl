# IAM Sub-Features

## Core Identity

### 01 — `org`
The root tenant entity. Every resource in tennetctl belongs to an org. Orgs have a URL-safe slug, display name, lifecycle status (`active / suspended / trialing / deleted`), and a JSONB settings blob. Soft-delete only — data is never purged. Supports test org flag for seed data exclusion from billing and metrics.

### 02 — `user`
Global user accounts, independent of any org. A user can be a member of multiple orgs. Stores email, password hash (Argon2), display name, avatar, MFA seed, and preferences. Email verification flow built in.

### 03 — `workspace`
A named workspace within an org for grouping resources (projects, environments, etc.). Orgs can have multiple workspaces. Workspace membership is separate from org membership.

### 04 — `group`
Named user groups within an org for bulk permission assignment. A group has RBAC roles attached; members of the group inherit those roles.

### 05 — `org_member`
The join between a user and an org. Tracks membership status, roles, join method (invite / SSO / SCIM), and the acting user who added them.

### 06 — `group_member`
Join table between users and org groups. Membership grants all roles assigned to the group.

### 07 — `workspace_member`
Join table between users/groups and workspaces. Controls which users have access to which workspace and with what roles.

---

## Authentication

### 08 — `auth`
Core authentication flow: register, login, logout, logout-all, token refresh, and OAuth2 social login. Issues HS256 JWT access tokens (15-min TTL) and opaque refresh tokens (30-day TTL with rotation). Argon2 password hashing. Rate-limited registration and login endpoints.

### 09 — `session`
Tracks all active and revoked sessions per user. Records device fingerprint (user-agent + IP), creation time, last-used time, and revocation reason. Used for `/iam/sessions` management UI.

### 10 — `auth_config`
Per-org authentication configuration: enabled auth methods, allowed email domains, enforced MFA policy, self-registration toggle, OAuth provider credentials.

### 11 — `mfa`
TOTP-based multi-factor authentication. Stores TOTP seed (encrypted), backup codes, and MFA enrolment status per user. Supports MFA recovery flow via one-time backup codes.

### 12 — `oauth2`
OAuth2 provider client registration. Allows orgs to register custom OAuth2 clients for user login. Also handles the server-side OAuth2 state/CSRF storage for social login flows.

### 13 — `sso`
SAML 2.0 and OIDC Single Sign-On configuration per org. Stores IdP metadata URL, entity ID, certificate, and attribute mapping. Supports SP-initiated and IdP-initiated flows.

### 14 — `scim`
SCIM 2.0 provisioning endpoint. Allows directory providers (Okta, Azure AD, etc.) to push user and group changes into tennetctl automatically. Supports user create, update, deactivate, and group sync.

### 15 — `account_linking`
Links a user's email/password account to one or more OAuth2 or SSO identities. Prevents duplicate accounts when the same email signs in via different providers.

### 16 — `password_policy`
Per-org password complexity rules: minimum length, require uppercase/numbers/symbols, password history depth, and expiry period. Applied at registration and password change endpoints.

### 17 — `session_policy`
Configures session lifetime and rotation rules per org: access token TTL, refresh token TTL, idle timeout, and forced re-authentication period.

### 18 — `impersonation`
Allows platform admins (tennetctl staff) to impersonate any user for support purposes. Issues a short-lived impersonation token with a tamper-evident audit trail. Requires two-person authorisation.

---

## Access Control

### 19 — `rbac`
Role-Based Access Control. Defines roles (e.g. `org:admin`, `workspace:editor`, `billing:viewer`) and their permission sets. Roles are assigned to users, groups, and API keys. Permission checks are performed via a PostgreSQL view.

### 20 — `api_key`
Long-lived opaque API keys for machine-to-machine authentication. Keys have scopes (a subset of RBAC permissions), an optional expiry, an optional IP allowlist, and usage tracking. The raw key is shown only once at creation; only the hash is stored.

### 21 — `temp_grant`
Temporary elevation of a user's permissions beyond their normal role. Time-bounded grants with mandatory reason, audit trail, and automatic expiry enforcement via a scheduled job.

### 22 — `access_policies`
Attribute-based access control (ABAC) policy expressions evaluated at request time. Policies can reference user attributes, org settings, and request context to produce allow/deny decisions layered on top of RBAC.

### 23 — `ip_policy`
Per-org IP allowlist/blocklist. Blocks or restricts access from outside allowed CIDR ranges. Checked at the middleware layer for all authenticated requests.

---

## Feature Flags

### 24 — `feature_flag`
Core feature flag entity. Each flag has a key, name, description, type (`boolean / string / number / json`), and a default value. Flags exist at the platform level and are configured per-environment per-org.

### 25 — `flag_env_config`
Per-org, per-environment flag configuration. Overrides the flag's default value for a specific org/environment combination. This is the main toggle for enabling/disabling features per customer.

### 26 — `flag_attr`
EAV (Entity-Attribute-Value) metadata on flags. Stores arbitrary key-value pairs for UI rendering hints, documentation links, owner teams, and alert thresholds.

### 27 — `flag_segment`
Named user segments based on rule expressions (e.g., "users in the US on a paid plan"). Segments are evaluated at flag resolution time to enable targeted rollouts.

### 28 — `flag_tag`
Organisational tags for grouping flags by domain, team, or lifecycle stage. Used for filtering in the flag management UI.

### 29 — `flag_variant`
Multivariate flag variants. Instead of boolean on/off, a flag can serve different values to different segments (A/B/C testing support).

### 30 — `flag_identity_target`
Direct per-identity flag targeting. Override flag value for a specific user UUID, org UUID, or workspace UUID regardless of segment rules.

### 31 — `flag_prerequisite`
Flag dependency rules. A flag can require another flag to be enabled before it activates. Used to model rollout dependency graphs.

### 32 — `flag_rule_engine`
Evaluates targeting rules and segments for a flag at request time. Produces the resolved flag value given a user's identity context. The core evaluation logic for all flag resolution.

---

## Lifecycle

### 33 — `invitation`
Email-based invitation flow. Org admins invite users by email; the invitee receives a magic link, completes registration or login, and is automatically added as an org member with the assigned role.

### 34 — `webhook`
Outbound webhooks for identity events (`user.created`, `user.updated`, `org.member.added`, etc.). Stores endpoint URL, secret, event subscriptions, and delivery retry state.

### 35 — `email_template`
Per-org custom email templates for system emails (invitation, verification, password reset). Supports Handlebars-style variable substitution. Falls back to platform default templates.

### 36 — `log_stream`
Per-org log streaming configuration. Ships IAM audit events to an external destination (HTTP endpoint, S3, Datadog). Configures event types, format, and delivery credentials.

### 37 — `portal_view`
White-label customisation of the self-service login/signup portal. Stores logo URL, primary colour, background, and custom domain routing per org.

### 38 — `user_import`
Bulk user import from CSV or JSON. Supports dry-run mode for validation, real-time progress streaming, and detailed error reporting per row. Triggers invite emails or sets temporary passwords.

---

## Compliance

### 39 — `audit`
IAM emits structured audit events for all mutations (create, update, delete, login, logout, permission change). These events are forwarded to the `03_audit` module for storage and querying. IAM itself does not store audit logs.
