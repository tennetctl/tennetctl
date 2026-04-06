# IAM Sub-Feature Gap Analysis

Comprehensive comparison of every built IAM sub-feature against best-in-class competitors.
Generated: 2026-04-04.

---

## 01_org — Organisation (Tenant) Management

**Compared against:** Auth0 Organizations, WorkOS Organizations, Clerk Organizations

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `POST /v1/orgs` | Create org (slug, display_name, description) |
| 2 | `GET /v1/orgs` | List orgs (include_deleted, limit) |
| 3 | `GET /v1/orgs/{id}` | Get single org |
| 4 | `PATCH /v1/orgs/{id}` | Update (display_name, description, status, is_active, restore) |
| 5 | `DELETE /v1/orgs/{id}` | Soft-delete |
| 6 | `GET /v1/orgs/{id}/attrs` | List EAV attributes |
| 7 | `PUT /v1/orgs/{id}/attrs/{key}` | Upsert EAV attribute |
| 8 | `DELETE /v1/orgs/{id}/attrs/{key}` | Delete EAV attribute |
| 9 | `GET /v1/orgs/{id}/audit` | Audit log for org |
| 10 | `GET /v1/orgs/{id}/versions` | Snapshot version history |
| 11 | `GET /v1/orgs/{id}/versions/{v}` | Get specific snapshot |

**Key strengths:** EAV extensibility, audit log, snapshot versioning, soft-delete with restore.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Org branding** (logo URL, colors, custom login page theme) | Auth0 orgs have branding per-org; Clerk has org logo/favicon | P1 |
| **Org-level connection/SSO config** (which IdP an org uses) | Auth0 "enabled connections per org"; WorkOS SSO per org | P0 |
| **Org invitations** — generate invite links/tokens for onboarding | Auth0 Org Invitations API; Clerk org invitations | P0 |
| **Org metadata** split into `public_metadata` vs `private_metadata` | Clerk distinguishes public (client-safe) vs private (server-only) | P1 |
| **Org creation quotas/limits** (max orgs per user) | WorkOS enforces via org policies | P2 |
| **Org-level feature toggles inline** (which features this org sees) | Auth0 organizations + feature flags integration | P2 — already handled via 24_feature_flag overrides |
| **Search/filter** by status, slug, display_name, date range | Auth0 list orgs supports `name` filter, `page`/`per_page` | P1 |
| **Pagination** (offset param missing on list) | All competitors paginate | P0 |
| **Domain verification** — verify org owns a domain for auto-join | WorkOS Organization Domains; Clerk verified domains | P1 |

---

## 02_user — User Account Management

**Compared against:** Auth0 Users, Clerk Users, Supabase Auth

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `POST /v1/users` | Create user (email, display_name) |
| 2 | `GET /v1/users` | List users (include_deleted, limit) |
| 3 | `GET /v1/users/{id}` | Get user |
| 4 | `PATCH /v1/users/{id}` | Update (display_name, status, is_active) |
| 5 | `DELETE /v1/users/{id}` | Soft-delete |
| 6 | `GET /v1/users/{id}/versions` | Snapshot versions |
| 7 | `GET /v1/users/{id}/versions/{v}` | Get specific snapshot |

**Key strengths:** Snapshot versioning, account_type system, EAV settings via dtl.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Email verification flow** (send link, verify, resend) | Auth0 email verification; Clerk email verification | P0 |
| **Password reset flow** (forgot password, reset token, confirm) | Auth0 password change/reset; Supabase auth.resetPasswordForEmail | P0 |
| **User search** — full-text search by email, name; filter by status, created_at | Auth0 Users Search API (Lucene queries); Clerk user search | P0 |
| **Pagination** (offset param missing on list) | All competitors paginate | P0 |
| **User blocking/banning** (distinct from deactivation) | Auth0 `blocked` flag; Clerk `ban_user` | P1 |
| **User impersonation** (admin acting as user) | Auth0 impersonation; Clerk has impersonation tokens | P1 |
| **Avatar upload** (presigned URL or direct upload) | Clerk avatar management; Auth0 user picture | P2 |
| **User metadata** split (public_metadata, private_metadata, unsafe_metadata) | Clerk's 3-tier metadata model | P1 |
| **Linked accounts** — list/manage OAuth identities per user | Auth0 user identities (link/unlink accounts) | P1 |
| **Last login timestamp, login count** visible on user profile | Auth0 user stats; Supabase last_sign_in_at | P1 |
| **User EAV attributes endpoint** like orgs have | Consistent with 01_org pattern | P1 |
| **Bulk user operations** (import CSV, bulk delete, bulk status change) | Auth0 bulk user import/export | P2 |
| **SCIM provisioning endpoint** for external IdP user sync | WorkOS SCIM; Auth0 SCIM | P2 |

---

## 03_workspace — Workspace Management

**Compared against:** Notion Workspaces, Slack Workspaces, Linear Workspaces

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `POST /v1/orgs/{org_id}/workspaces` | Create workspace (slug, display_name) |
| 2 | `GET /v1/orgs/{org_id}/workspaces` | List workspaces |
| 3 | `GET /v1/orgs/{org_id}/workspaces/{id}` | Get workspace |
| 4 | `PATCH /v1/orgs/{org_id}/workspaces/{id}` | Update (display_name, is_active) |
| 5 | `DELETE /v1/orgs/{org_id}/workspaces/{id}` | Soft-delete |
| 6 | `GET /v1/orgs/{org_id}/workspaces/{id}/versions` | Snapshot versions |
| 7 | `GET /v1/orgs/{org_id}/workspaces/{id}/versions/{v}` | Get specific snapshot |

**Key strengths:** Org-scoped, snapshot versioning, settings via EAV.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Workspace settings/preferences** (timezone, locale, default role) | Notion workspace settings; Linear workspace preferences | P1 |
| **Workspace icon/branding** | Notion workspace icon; Slack workspace icon | P2 |
| **Workspace-level permissions/visibility** (public vs private workspace) | Slack channel visibility model; Linear team visibility | P1 |
| **Workspace transfer** (move workspace between orgs) | Slack workspace transfer | P2 |
| **Workspace description** field in create/update | Notion workspace description | P1 |
| **Workspace usage stats** (member count, resource counts) | Linear workspace analytics | P2 |
| **Workspace EAV attributes endpoint** like orgs have | Consistent with 01_org pattern | P1 |
| **Workspace audit log** like orgs have | Consistent with 01_org pattern | P1 |

---

## 04_group — User Groups

**Compared against:** Azure AD Groups, Okta Groups, Auth0 Organizations

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `POST /v1/groups` | Create group (org_id, name, slug, description) |
| 2 | `GET /v1/groups` | List groups (org_id filter, pagination) |
| 3 | `GET /v1/groups/{id}` | Get group |
| 4 | `PATCH /v1/groups/{id}` | Update (name, slug, description) |
| 5 | `DELETE /v1/groups/{id}` | Soft-delete |

**Key strengths:** Org-scoped, slug uniqueness, is_system flag, proper pagination.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Dynamic groups** (membership via rules/conditions, not manual add) | Azure AD dynamic groups with membership rules | P1 |
| **Group nesting** (groups within groups) | Azure AD nested groups; Okta group hierarchy | P2 |
| **Group type** (security group, team, distribution list) | Azure AD groupTypes (security, M365, unified) | P1 |
| **Group member count** returned on list/get | Azure AD returns member count; Okta group profile | P1 |
| **Group-level RBAC role assignment** visible on group detail | Integration with 19_rbac group-role links | P1 |
| **Group audit log** | Consistent with 01_org pattern | P2 |

---

## 05_org_member — Organisation Membership

**Compared against:** Auth0 Org Memberships, WorkOS Memberships

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `GET /v1/orgs/{org_id}/members` | List members (paginated, include_deleted) |
| 2 | `POST /v1/orgs/{org_id}/members` | Add member (user_id, role: owner/admin/member/viewer) |
| 3 | `GET /v1/orgs/{org_id}/members/{id}` | Get single membership |
| 4 | `PATCH /v1/orgs/{org_id}/members/{id}` | Update role |
| 5 | `DELETE /v1/orgs/{org_id}/members/{id}` | Remove member (soft-delete) |

**Key strengths:** 4-level role system, invited_by tracking, proper pagination.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Invitation flow** — invite by email (pending/accepted states, expiry) | Auth0 org invitations; WorkOS Invitations API | P0 |
| **Bulk add/remove members** | Auth0 bulk org member management | P1 |
| **Member search/filter** by role, status, email, joined_at range | Auth0 list org members with filters | P1 |
| **Last active timestamp** per member | WorkOS membership last_active_at | P2 |
| **RBAC roles per org** — assign custom RBAC roles (not just owner/admin/member/viewer) | Auth0 org members get org-scoped roles | P1 |
| **Owner transfer** — explicit endpoint to transfer org ownership | Auth0 org ownership transfer | P1 |
| **Self-removal** (member leaves org) | Auth0/WorkOS allow self-leave | P2 |

---

## 06_group_member — Group Membership

**Compared against:** Azure AD Group Members

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `GET /v1/groups/{group_id}/members` | List members |
| 2 | `POST /v1/groups/{group_id}/members` | Add member (user_id) |
| 3 | `GET /v1/groups/{group_id}/members/{id}` | Get member |
| 4 | `DELETE /v1/groups/{group_id}/members/{id}` | Remove member (soft-delete) |

**Key strengths:** Clean 4-endpoint shape, added_by tracking.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Bulk add/remove** (batch endpoint for multiple user_ids) | Azure AD batch member operations | P1 |
| **Member role within group** (owner, member) — currently flat | Azure AD group owners vs members distinction | P1 |
| **Pagination** (no offset/total on list endpoint) | Azure AD paginates with `$top`/`$skip` | P0 |
| **Check membership** — `GET /v1/groups/{id}/members/{user_id}/check` | Azure AD checkMemberGroups/checkMemberObjects | P1 |
| **Transitive membership** — list all groups a user belongs to | Azure AD getMemberOf (with transitive) | P2 |

---

## 07_workspace_member — Workspace Membership

**Compared against:** Notion Workspace Members, Slack Members

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `GET /v1/workspaces/{id}/members` | List members (paginated) |
| 2 | `POST /v1/workspaces/{id}/members` | Add member (user_id, role: admin/member/viewer) |
| 3 | `GET /v1/workspaces/{id}/members/{id}` | Get member |
| 4 | `PATCH /v1/workspaces/{id}/members/{id}` | Update role |
| 5 | `DELETE /v1/workspaces/{id}/members/{id}` | Remove member |

**Key strengths:** 3-level role system, proper pagination, full CRUD.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Invitation flow** (invite by email, pending state) | Notion workspace invitations; Slack invitations | P1 |
| **Bulk operations** | Slack bulk member management | P2 |
| **Guest access** (external user with limited access, not full member) | Notion guest access; Slack guest accounts | P1 |
| **Member search/filter** by role, status | Notion member filters | P1 |
| **Default role on workspace** (what role new members get) | Slack default channel join settings | P2 |

---

## 08_auth — Authentication

**Compared against:** Auth0 Auth, Clerk Auth, Supabase Auth, Keycloak

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `GET /v1/auth/setup-status` | Check if initial setup needed |
| 2 | `POST /v1/auth/setup` | First-run admin setup |
| 3 | `POST /v1/auth/register` | Email/password registration |
| 4 | `POST /v1/auth/login` | Email/password login |
| 5 | `POST /v1/auth/refresh` | Rotate JWT pair |
| 6 | `POST /v1/auth/logout` | Revoke session |
| 7 | `GET /v1/auth/me` | Current user from JWT |

**Key strengths:** argon2id hashing, JWT with jti tracking, session revocation, token rotation, IP/UA tracking, audit events on login/register, failed login auditing.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Password reset** (POST /forgot-password, POST /reset-password) | Auth0 password change; Supabase resetPasswordForEmail; Clerk password reset | P0 |
| **Email verification** (POST /verify-email, POST /resend-verification) | Auth0 email verify; Clerk email verification; Supabase | P0 |
| **OAuth2/Social login** (Google, GitHub, SAML) | Auth0 connections; Clerk SSO; Supabase OAuth; Keycloak IdP | P0 |
| **MFA/2FA** (TOTP setup, verify, recovery codes) | Auth0 MFA; Clerk MFA; Keycloak OTP | P0 |
| **Session management** — list active sessions, revoke specific session | Auth0 session list; Clerk session management | P1 |
| **Logout all devices** endpoint (already in service but not routed) | `logout_all` exists in service.py but has no route | P0 |
| **Change password** (authenticated user changes own password) | Auth0 password change; Clerk updateUser password | P1 |
| **Passwordless/magic link** login | Auth0 passwordless; Clerk magic links; Supabase magic link | P1 |
| **Rate limiting on auth endpoints** (brute-force protection) | Auth0 brute-force protection; Keycloak brute force detection | P0 |
| **Account lockout** after N failed attempts | Auth0 anomaly detection; Keycloak lockout policy | P1 |
| **JWT signing with RS256** (asymmetric, so clients can verify without secret) | Auth0 uses RS256 by default; Keycloak RS256 | P1 |
| **JWKS endpoint** (/.well-known/jwks.json) | Auth0 JWKS; Keycloak JWKS | P1 |
| **Auth middleware** (currently manual Bearer check in each route) | All competitors have middleware/guards; should be a FastAPI dependency | P0 |
| **Org-scoped login** (login to a specific org context) | Auth0 org login; Clerk org switching | P1 |
| **Token claims enrichment** (roles, permissions, org_id in JWT) | Auth0 Actions/Rules to add claims; Clerk JWT templates | P1 |

---

## 19_rbac — Role-Based Access Control

**Compared against:** Auth0 RBAC, Permit.io, Cerbos, Casbin, SpiceDB

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `POST /v1/roles` | Create role (scoped: platform/org) |
| 2 | `GET /v1/roles` | List roles (scope filter, inherited, paginated) |
| 3 | `GET /v1/roles/{id}` | Get role |
| 4 | `PATCH /v1/roles/{id}` | Update role |
| 5 | `DELETE /v1/roles/{id}` | Soft-delete role |
| 6 | `GET /v1/roles/{id}/permissions` | List role's permissions |
| 7 | `POST /v1/roles/{id}/permissions` | Assign permission to role |
| 8 | `DELETE /v1/roles/{id}/permissions/{perm_id}` | Revoke permission |
| 9 | `GET /v1/permissions` | List all permissions |
| 10 | `POST /v1/rbac/check` | Runtime permission check (user_id, resource, action, org_id) |

**Key strengths:** Scoped roles (platform vs org), permission inheritance, runtime check endpoint.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **User-role assignment API** (assign/revoke roles to users) | Auth0 user roles API; Permit.io user-role assignment | P0 |
| **Group-role assignment API** (assign roles to groups) — may exist in DB but no route | Okta group-role assignment; Azure AD group-role | P0 |
| **Permission CRUD** (create/update/delete permissions, not just list) | Auth0 permission management; Permit.io resource actions | P1 |
| **Resource-based permissions** (define resources, then actions per resource) | Permit.io resources + actions model; Cerbos resource policies | P1 |
| **Policy engine** (if/then rules, not just flat permission checks) | Cerbos policy rules; Casbin policy model (RBAC/ABAC); SpiceDB Zanzibar | P1 |
| **Relationship-based access control (ReBAC)** | SpiceDB (Zanzibar model); Permit.io ReBAC | P2 |
| **Attribute-based access control (ABAC)** conditions on checks | Cerbos ABAC conditions; Permit.io ABAC | P2 |
| **Bulk permission check** (check multiple resources/actions in one call) | Auth0 check multiple permissions; Permit.io bulk check | P1 |
| **List user's effective permissions** (resolved from all roles/groups) | Auth0 user permissions; Permit.io user permissions | P0 |
| **Role hierarchy** (senior role inherits junior role's permissions) | Keycloak composite roles; NIST RBAC role hierarchy | P1 |
| **Wildcard permissions** (e.g., `orgs:*` grants all org actions) | Casbin wildcard matching; Permit.io wildcard resources | P2 |
| **Audit log for RBAC changes** | All enterprise competitors audit RBAC changes | P1 |
| **Condition-based access** (time-of-day, IP range, device context) | Cerbos conditions; conditional access policies | P2 |

---

## 24_feature_flag — Feature Flags

**Compared against:** LaunchDarkly, PostHog, Unleash, Flagsmith, Statsig

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `POST /v1/feature-flags` | Create flag (rich: key, value_type, rollout%, lifecycle, access_mode, scope, kill_switch) |
| 2 | `GET /v1/feature-flags` | List flags (scope filter, inherited, paginated) |
| 3 | `GET /v1/feature-flags/{id}` | Get flag |
| 4 | `PATCH /v1/feature-flags/{id}` | Update flag (including permanently_on, change_reason) |
| 5 | `DELETE /v1/feature-flags/{id}` | Soft-delete |
| 6 | `GET /v1/feature-flags/stale` | List stale flags (configurable days) |
| 7 | `POST /v1/feature-flags/eval` | Evaluate flags (with context, debug mode, env) |
| 8 | `GET /v1/feature-flags/bootstrap` | Bootstrap all flag values for client SDK |
| 9-11 | Rules CRUD + reorder | Targeting rules with segments, scheduling |
| 12-15 | Variants CRUD + reweight | Multivariate flags with weight-based distribution |
| 16-18 | Env configs CRUD | Per-environment overrides |
| 19-21 | Identity targets CRUD | User/org/group-level targeting |
| 22-24 | Prerequisites CRUD | Flag dependencies |
| 25-27 | Tag assignment | Organizational tagging |
| 28 | `GET /v1/feature-flags/{id}/history` | Change history |
| 29 | `POST /v1/feature-flags/{id}/promote` | Env-to-env promotion |
| 30 | `POST /v1/feature-flags/kill-switch` | Emergency disable multiple flags |
| 31-34 | EAV attributes | Extensible metadata |
| 35-36 | Metered usage (increment + list) | Usage-based feature gating |
| 37-40 | Flag permissions (actions per flag) | Fine-grained flag access |
| 41-44 | Role-flag grants (RBAC on flags) | Who can do what on which flag |
| 45-47 | Segments CRUD + conditions | Reusable audience segments |
| 48-51 | Tags CRUD | Tag management |
| 52 | `GET /v1/flag-attr-defs` | List attribute definitions |
| 53 | `GET /v1/license-tiers` | List tiers |
| 54 | `GET /v1/environments` | List environments |
| 55-57 | Org-level overrides | Per-org flag overrides |
| 58-60 | User-level overrides | Per-user flag overrides |
| 61-65 | Flag projects CRUD + members | Project scoping |
| 66-68 | SDK tokens CRUD | API key management per project/env |
| 69-72 | Webhooks CRUD | Event-driven integrations |
| 73-76 | Permission actions | Manage available actions |
| 77 | `POST /v1/role-flag-grants/check` | Check user's flag-level permission |
| 78 | `GET /v1/feature-flags/{id}/eval-counts` | Evaluation analytics |

**Key strengths:** Extremely comprehensive. Rivals LaunchDarkly's feature set. Rules engine, segments, variants, env configs, scheduling, prerequisites, kill switch, promotion, stale flag detection, metered/usage flags, SDK tokens, webhooks, flag-level RBAC, EAV extensibility, change history, eval analytics.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Streaming/SSE/WebSocket endpoint** for real-time flag updates | LaunchDarkly streaming API; Unleash SSE; Flagsmith real-time | P1 |
| **A/B experiment integration** (define experiment, assign variants, measure impact) | LaunchDarkly Experimentation; Statsig experiments; PostHog experiments | P1 |
| **Flag approvals workflow** (require approval before flag changes go live) | LaunchDarkly approval workflows; Unleash change requests | P1 |
| **Scheduled flag toggles** (schedule on/off at specific time) — rules have scheduled_on/off but no top-level scheduler | LaunchDarkly scheduled flag changes; Unleash scheduled toggles | P2 — partially covered by rule scheduling |
| **Flag comparison across environments** (diff view) | LaunchDarkly env comparison; Unleash env diff | P2 |
| **Percentage rollout with sticky bucketing** (consistent user assignment) | LaunchDarkly sticky targeting; Statsig sticky bucketing | P1 |
| **Client-side SDK support** (JavaScript/React SDK npm package) | LaunchDarkly SDKs; PostHog JS SDK; Unleash client SDKs | P1 |
| **Webhook delivery logs** (success/failure tracking) | Flagsmith webhook logs; LaunchDarkly webhook retry/logs | P2 |
| **Flag dependencies visualization** (prerequisite chain graph) | LaunchDarkly prerequisite visualization | P2 |
| **Segment reuse across flags** — segments exist but unclear if shared | LaunchDarkly shared segments; PostHog cohorts | P2 — likely already working |

---

## 25_license_profile — License/Entitlement Management

**Compared against:** Stigg, Schematiq, Lago

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `GET /v1/license-profiles` | List profiles (tier filter, paginated) |
| 2 | `POST /v1/license-profiles` | Create profile (tier_id, name, feature_limits JSONB) |
| 3 | `GET /v1/license-profiles/{id}` | Get profile |
| 4 | `PATCH /v1/license-profiles/{id}` | Update profile |
| 5 | `DELETE /v1/license-profiles/{id}` | Soft-delete |
| 6 | `GET /v1/orgs/{org_id}/license` | Get org's license assignment |
| 7 | `PUT /v1/orgs/{org_id}/license` | Assign license to org |
| 8 | `DELETE /v1/orgs/{org_id}/license` | Remove org license |
| 9 | `GET /v1/orgs/{org_id}/license/entitlements` | Get org's resolved entitlements |
| 10 | `GET /v1/workspaces/{ws_id}/license` | Get workspace license |
| 11 | `PUT /v1/workspaces/{ws_id}/license` | Assign workspace license |
| 12 | `DELETE /v1/workspaces/{ws_id}/license` | Remove workspace license |
| 13 | `GET /v1/license-tiers/{tier_id}/flags` | List tier entitlements |
| 14 | `POST /v1/license-tiers/{tier_id}/flags` | Upsert entitlement |
| 15 | `DELETE /v1/license-tiers/{tier_id}/flags/{flag_id}` | Remove entitlement |

**Key strengths:** Tier-based model, JSONB feature limits, org + workspace scoping, flag-based entitlements.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Tier CRUD** (create/update tiers, not just list) | Stigg plan management; Schematiq plan builder | P1 |
| **Trial period support** (start_date, trial_end_date, auto-downgrade) | Stigg trial periods; Lago trial management | P1 |
| **Usage metering integration** (connect to 24_feature_flag usage for limit enforcement) | Stigg metered features; Lago metered billing | P1 |
| **Entitlement check endpoint** (boolean: "does this org have access to X?") | Stigg entitlement check API; Schematiq access check | P0 |
| **Upgrade/downgrade flow** (tier change with proration logic) | Stigg plan changes; Lago subscription update | P1 |
| **License history/changelog** (when tier changed, who changed it) | Stigg subscription events; audit trail | P1 |
| **Seat-based licensing** (max users per tier, enforce on member add) | Stigg seat-based pricing; Schematiq seat management | P1 |
| **Grace period on expiry** (soft enforcement window after expires_at) | Stigg grace periods | P2 |
| **Customer portal** — self-service tier/plan view for end users | Stigg customer portal widget | P2 |
| **Billing integration hooks** (Stripe, payment provider webhooks) | Stigg Stripe integration; Lago payment processors | P2 |

---

## 26_project — Org-Scoped Projects

**Compared against:** LaunchDarkly Projects, Unleash Projects

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `GET /v1/projects` | List projects (org_id filter, paginated) |
| 2 | `POST /v1/projects` | Create project (org_id, key, name, description) |
| 3 | `GET /v1/projects/{id}` | Get project |
| 4 | `PATCH /v1/projects/{id}` | Update project |
| 5 | `DELETE /v1/projects/{id}` | Soft-delete |

**Key strengths:** Org-scoped, key-based identification, clean CRUD.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Project environments** (dev/staging/prod per project) | LaunchDarkly environments per project; Unleash project environments | P0 — environments exist globally but not project-scoped |
| **Project-level flags** (list flags belonging to this project) | LaunchDarkly flags per project; Unleash project features | P1 |
| **Project members/access control** | LaunchDarkly project-level access; Unleash project roles | P1 — exists in flag-projects but not in 26_project |
| **Project settings** (default flag state, default env, etc.) | LaunchDarkly project settings | P2 |
| **Project API tokens/SDK keys** | LaunchDarkly project access tokens | P1 — exists in flag-projects but not in 26_project |
| **Project audit log** | LaunchDarkly audit log per project | P2 |

---

## Summary: P0 Gaps (Must Fix for Production)

These are blocking gaps that any production multi-tenant SaaS control plane must have:

| # | Sub-feature | Gap | Effort |
|---|-------------|-----|--------|
| 1 | 08_auth | Password reset flow | M |
| 2 | 08_auth | Email verification flow | M |
| 3 | 08_auth | OAuth2/Social login (Google, GitHub) | L |
| 4 | 08_auth | MFA/TOTP (already PLANNED as 11_mfa) | L |
| 5 | 08_auth | Auth middleware (FastAPI dependency, not manual Bearer check) | S |
| 6 | 08_auth | Rate limiting on auth endpoints | S |
| 7 | 08_auth | Route the existing `logout_all` function | XS |
| 8 | 01_org | Org invitations API | M |
| 9 | 01_org | Pagination (add offset param to list) | XS |
| 10 | 02_user | Pagination (add offset param to list) | XS |
| 11 | 02_user | Password reset flow (shared with 08_auth) | — |
| 12 | 02_user | Email verification (shared with 08_auth) | — |
| 13 | 02_user | User search (full-text by email/name) | S |
| 14 | 05_org_member | Invitation flow (invite by email) | M |
| 15 | 06_group_member | Pagination | XS |
| 16 | 19_rbac | User-role assignment API | S |
| 17 | 19_rbac | Group-role assignment API | S |
| 18 | 19_rbac | List user's effective permissions | S |
| 19 | 25_license | Entitlement check endpoint | S |
| 20 | 26_project | Project-scoped environments | M |
| 21 | 01_org | Org-level SSO/connection config | L |

**Effort key:** XS = <1hr, S = 1-4hr, M = 4-16hr, L = 2-5 days

## Summary: P1 Gaps (Should Have)

| # | Sub-feature | Gap |
|---|-------------|-----|
| 1 | 08_auth | Session management (list/revoke), change password, passwordless/magic link |
| 2 | 08_auth | RS256 JWT signing, JWKS endpoint, token claims enrichment, org-scoped login |
| 3 | 08_auth | Account lockout after N failed attempts |
| 4 | 01_org | Org branding, search/filter, domain verification, metadata split |
| 5 | 02_user | User blocking, impersonation, metadata split, linked accounts, last login, EAV attrs endpoint |
| 6 | 03_workspace | Settings/preferences, visibility (public/private), description field, EAV attrs, audit log |
| 7 | 04_group | Dynamic groups, group types, member count, group-level RBAC visibility |
| 8 | 05_org_member | Bulk ops, member search/filter, custom RBAC roles per org, owner transfer |
| 9 | 06_group_member | Bulk ops, member role within group, check membership |
| 10 | 07_workspace_member | Invitations, guest access, member search/filter |
| 11 | 19_rbac | Permission CRUD, resource-based permissions, policy engine, bulk check, role hierarchy, audit |
| 12 | 24_feature_flag | Streaming updates, experiments/A/B, approval workflows, sticky bucketing, client SDK |
| 13 | 25_license | Tier CRUD, trial periods, usage metering, upgrade/downgrade, seat-based licensing, changelog |
| 14 | 26_project | Project-level flags list, members, SDK keys (consolidate with flag-projects) |

## Cross-Cutting Observations

1. **Auth middleware is the single biggest structural gap.** Every route that needs authentication currently does manual Bearer header parsing. A proper FastAPI `Depends(current_user)` dependency would fix this and enable org-scoped auth context propagation.

2. **Pagination inconsistency.** 01_org and 02_user lack `offset` on list. 06_group_member lacks pagination entirely. Other sub-features have it. Should be uniform.

3. **EAV consistency.** 01_org has a full attrs sub-resource API. 02_user, 03_workspace, 04_group do not, despite all having EAV in the database. Should expose the same pattern everywhere.

4. **Audit consistency.** 01_org has `/{id}/audit`. No other sub-feature exposes this, despite audit events being emitted in services. Should add audit endpoints to all entities.

5. **Invitation system is architecturally absent.** Org membership and workspace membership have no invite-by-email flow. This is table-stakes for multi-tenant SaaS.

6. **Flag-projects vs 26_project overlap.** The 24_feature_flag routes have their own `/v1/flag-projects` with members, SDK tokens, and webhooks. The 26_project sub-feature has a simpler `/v1/projects`. These should be consolidated or clearly delineated.
