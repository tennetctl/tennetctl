# Multi-Tenant Control Plane — Scoping Model

## What tennetctl Is

A multi-tenant SaaS control plane. Super admins manage the platform. Each org (tenant) gets autonomy to create their own roles, groups, flags, and projects — but platform-level entities are inherited, never duplicated.

## Hierarchy

```
Platform (Super Admin)
  └── Org (Tenant)
        └── Project (within org)
              └── Environment (dev / staging / prod per project)
```

Workspaces are an org-internal grouping tool, not a scoping boundary.

## Scoping Rules

### The scope_type + scope_id Pattern

Every scoped entity carries two columns:

```sql
scope_type_id  SMALLINT NOT NULL  -- FK → dim_scope_types (1=platform, 2=org, 3=project)
scope_id       VARCHAR(36)        -- NULL for platform, org UUID for org, project UUID for project
```

**No duplication.** A platform role is ONE row with `scope_type_id=1, scope_id=NULL`. Every org sees it via inheritance — we never copy the row into each org.

### dim_scope_types

| id | code | label | Description |
|----|------|-------|-------------|
| 1  | platform | Platform | Super admin managed. Inherited by all orgs. |
| 2  | org | Organisation | Org admin managed. Visible only to org members. |
| 3  | project | Project | Project-scoped. Within an org's project. |

## Entity Scoping Matrix

### Feature Flags

| Scope | Who creates | Who sees | Examples |
|-------|-------------|----------|----------|
| platform | Super admin | All orgs (inherited) | `sso-enabled`, `max-users`, `beta-feature` |
| org | Org admin | Org members only | `org-dark-mode`, `org-custom-branding` |
| project | Project member | Project members | `new-checkout-flow`, `redesigned-nav` |

**Inheritance:** When evaluating a flag for an org, the engine checks:
1. Project-scoped flags (if project context given)
2. Org-scoped flags for this org
3. Platform-scoped flags

Most specific scope wins. Org admins can **override the value** of a platform flag for their org (via `lnk_org_flag_overrides`) but cannot delete or modify the platform flag itself.

### Roles

| Scope | Who creates | Immutable from below? | Examples |
|-------|-------------|----------------------|----------|
| platform | Super admin | Yes — orgs inherit, cannot modify | `super-admin`, `org-admin`, `org-member`, `org-viewer` |
| org | Org admin | No — org owns it | `billing-manager`, `custom-editor`, `compliance-officer` |

**No org_id on platform roles.** Platform roles have `scope_type_id=1, scope_id=NULL`. When listing roles for an org:

```sql
-- Returns platform roles + this org's custom roles
WHERE (scope_type_id = 1) OR (scope_type_id = 2 AND scope_id = $org_id)
```

**Permission resolution for a user in an org:**
1. Get user's org membership role → find matching `fct_roles` row → get permissions
2. Get user's group memberships → groups' assigned roles → get permissions
3. Union all permissions (platform + org-scoped)

### Groups

| Scope | Who creates | Members from | Examples |
|-------|-------------|-------------|----------|
| platform | Super admin | Any user (platform-wide) | `all-users`, `beta-testers`, `platform-engineers` |
| org | Org admin | Org members only | `engineering`, `sales`, `qa-team` |

**Platform groups are NOT duplicated per org.** They exist once. Users are added to them directly via `lnk_group_members`. When listing groups for an org:

```sql
-- Platform groups + this org's groups
WHERE (scope_type_id = 1) OR (scope_type_id = 2 AND scope_id = $org_id)
```

**Org admins can:**
- Create org-scoped groups
- Add their org's users to org-scoped groups
- See platform groups (but cannot modify them)
- Map their org's users to platform groups? → **No.** Only super admins manage platform group membership.

### Users

Users are **always platform-scoped**. One user identity across all orgs. No scope columns on `fct_users`.

Membership is via:
- `lnk_org_members` — user ↔ org (with role)
- `lnk_workspace_members` — user ↔ workspace (with role)
- `lnk_group_members` — user ↔ group

An org admin can:
- Invite users to their org
- Assign org-scoped roles
- Add users to org-scoped groups
- Remove users from their org

An org admin CANNOT:
- Delete a user from the platform
- Modify another org's membership
- Add users to platform groups

### Projects

Projects are **always org-scoped**. They represent what the org is building.

```sql
CREATE TABLE "02_iam"."fct_projects" (
    id              VARCHAR(36) NOT NULL,
    org_id          VARCHAR(36) NOT NULL,
    key             TEXT NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    -- standard columns...
);
```

Projects contain:
- Feature flags (project-scoped flags for this specific app/service)
- Environments (dev/staging/prod per project — inherits from dim_environments but can have project-specific ones)
- SDK tokens (per project per environment)
- Webhooks (per project)

**This is the "what are we building" entity.** An org building a checkout service, a mobile app, and an internal tool would have 3 projects.

### License Profiles

Profiles are **platform-scoped** (defined by super admin). Assignment is per-org.

Org admins see their current license but cannot change it. Super admins assign profiles to orgs.

### Audit Events

Events carry `org_id` for tenant attribution. Platform-level events (super admin actions) have `org_id=NULL`.

## API Scoping Pattern

Every list endpoint accepts scope filters:

```
# Super admin: all platform flags
GET /v1/feature-flags?scope=platform

# Org admin: org flags + inherited platform flags
GET /v1/feature-flags?scope=org&scope_id=<org_id>

# Same but excluding inherited
GET /v1/feature-flags?scope=org&scope_id=<org_id>&inherited=false

# Project-level
GET /v1/feature-flags?scope=project&scope_id=<project_id>
```

The `scope` parameter defaults based on the caller's role:
- Super admin → `scope=platform` (sees everything)
- Org admin → `scope=org&scope_id=<their_org_id>` (sees org + inherited)
- Member → same as org admin but read-only

## Navigation Model

### Super Admin Dashboard

```
tennetctl
├── Dashboard ─────────── Platform stats, org count, user count
├── Organisations ─────── List/create/manage all orgs
├── Users ─────────────── Platform user registry
├── Feature Flags ─────── Platform flags (inherited by all orgs)
│   ├── All Flags
│   ├── Segments
│   └── Stale Flags
├── Roles ─────────────── System roles
├── Groups ────────────── System groups
├── Licensing ─────────── Tiers, profiles, entitlements
│   ├── Tiers
│   ├── Profiles
│   └── Org Assignments
└── Audit Log ─────────── Platform-wide events
```

### Org Admin View (org switcher selects which org)

```
{Org Name}
├── Dashboard ─────────── Org stats
├── Members ───────────── Org members + role assignment
├── Projects ──────────── What the org is building
│   └── {Project}
│       ├── Feature Flags (project-scoped)
│       ├── Environments
│       ├── SDK Tokens
│       └── Webhooks
├── Feature Flags ─────── Org-scoped flags
│   ├── Org Flags (created by this org)
│   ├── Inherited (platform flags — override values here)
│   └── Overrides
├── Groups ────────────── Org groups (create, manage, assign users)
├── Roles ─────────────── Org custom roles + inherited system roles (read-only)
├── Workspaces ────────── Org internal grouping
├── License ───────────── Current tier, limits, entitlements (read-only)
└── Audit Log ─────────── Org-scoped events
```

## Database Changes Required

### New: dim_scope_types
```sql
(1, 'platform', 'Platform')
(2, 'org', 'Organisation')
(3, 'project', 'Project')
```

### Alter: fct_feature_flags
```sql
ADD COLUMN scope_type_id SMALLINT NOT NULL DEFAULT 1  -- platform
ADD COLUMN scope_id VARCHAR(36)  -- NULL for platform
-- Backfill: existing rows with org_id set → scope_type_id=2, scope_id=org_id
-- org_id column kept as denormalised shortcut for queries
```

### Alter: fct_roles
```sql
ADD COLUMN scope_type_id SMALLINT NOT NULL DEFAULT 1
ADD COLUMN scope_id VARCHAR(36)
-- Backfill: is_system=true → scope_type_id=1; org_id set → scope_type_id=2, scope_id=org_id
```

### Alter: fct_groups
```sql
ADD COLUMN scope_type_id SMALLINT NOT NULL DEFAULT 1
ADD COLUMN scope_id VARCHAR(36)
-- Backfill: is_system=true → scope_type_id=1; org_id set → scope_type_id=2, scope_id=org_id
```

### Alter: fct_flag_segments
```sql
ADD COLUMN scope_type_id SMALLINT NOT NULL DEFAULT 1
ADD COLUMN scope_id VARCHAR(36)
```

### New: fct_projects
```sql
CREATE TABLE fct_projects (
    id, org_id, key, name, description,
    is_active, deleted_at, created_by, updated_by, created_at, updated_at
);
```

### Alter: fct_flag_projects → remove (replaced by fct_projects)
The separate `fct_flag_projects` table is unnecessary. Projects are org-level entities that own flags, environments, SDK tokens, etc.

### Alter: fct_flag_sdk_tokens
```sql
-- project_id now references fct_projects instead of fct_flag_projects
```

## Key Principles

1. **One row, many viewers.** Platform entities exist once. Orgs see them via inheritance, never duplication.
2. **Scope is explicit.** `scope_type_id + scope_id` on every scoped entity. No `NULL means platform` ambiguity.
3. **Org autonomy.** Orgs create their own roles, groups, flags, projects. They manage their own users.
4. **Platform immutability from below.** Org admins cannot modify platform entities. They can only override flag values.
5. **Additive permissions.** User permissions = union of (platform roles + org roles + group roles).
6. **Projects are the work unit.** What the org is building. Flags, SDKs, webhooks live under projects.
7. **No workspace scoping for flags/roles.** Workspaces are org-internal teams, not a scoping boundary for the control plane. Projects are the scoping boundary.
