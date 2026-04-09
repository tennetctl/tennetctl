## Planned: RBAC — Three-Tier Roles, Permissions, Enforcement

**Severity if unbuilt:** CRITICAL (nothing in the system is access-controlled today)
**Depends on:** Foundation sprint (scopes + categories — see `29_categories_and_scopes.md`), groups (`17_groups.md`), scope enforcement (`18_scope_enforcement.md`)

## Problem

Every authenticated user has full access to every endpoint. There are no
permission checks. Additionally, the original single-tier role model cannot
express roles that are specific to an organization or workspace without
nullable FKs — a user is either "admin" everywhere or nowhere.

## Design: three-tier role hierarchy

Roles are scoped to exactly one of three levels, mirroring the platform
scope hierarchy (`platform` → `org` → `workspace`). Each tier has its own
`fct_*` table and its own `lnk_user_*_roles` assignment table, so every
composite key is clean and no foreign key is nullable.

### Scope semantics

- **Platform roles** — grant across the entire control plane (e.g. `platform_admin`). Not tied to any org.
- **Org roles** — grant within one org only (e.g. `org_owner` for org X). Tied to `(user_id, org_id)`.
- **Workspace roles** — grant within one workspace only (e.g. `workspace_editor` for workspace Y). Tied to `(user_id, org_id, workspace_id)`.

A user may hold any combination across all three tiers.

## Scope when built

### DB tables

New sub-feature `19_rbac` under `03_iam`:

#### Shared

- `10_fct_permissions` — `id, resource (e.g. 'orgs'), action (e.g. 'read'), description, is_active, audit`
- `40_lnk_role_permissions` — `role_scope_id (FK dim_scopes), role_id, permission_id` (single link table with `role_scope_id` discriminator so one permission can be granted to platform/org/workspace roles uniformly)

#### Platform tier

- `10_fct_platform_roles`
  - `id, code UNIQUE, name, category_id (FK dim_categories type=role), is_system, is_active, deleted_at, audit`
- `40_lnk_user_platform_roles`
  - `id, user_id, platform_role_id, granted_by, granted_at, is_active`
  - UNIQUE `(user_id, platform_role_id)`

#### Org tier

- `10_fct_org_roles`
  - `id, org_id FK fct_orgs, code, name, category_id, is_system, is_active, deleted_at, audit`
  - UNIQUE `(org_id, code)`
- `40_lnk_user_org_roles`
  - `id, user_id, org_id, org_role_id, granted_by, granted_at, is_active`
  - UNIQUE `(user_id, org_id, org_role_id)`

#### Workspace tier

- `10_fct_workspace_roles`
  - `id, org_id FK, workspace_id FK, code, name, category_id, is_system, is_active, deleted_at, audit`
  - UNIQUE `(workspace_id, code)`
- `40_lnk_user_workspace_roles`
  - `id, user_id, org_id, workspace_id, workspace_role_id, granted_by, granted_at, is_active`
  - UNIQUE `(user_id, workspace_id, workspace_role_id)`

### Views

- `v_platform_roles`, `v_org_roles`, `v_workspace_roles` — role metadata with category label joined.
- `v_user_effective_permissions` — union across all three tiers, resolving permissions for a `(user_id, org_id?, workspace_id?)` context.

### Endpoints

```
# Platform roles
POST   /v1/platform-roles
GET    /v1/platform-roles
GET    /v1/platform-roles/{id}
PATCH  /v1/platform-roles/{id}
DELETE /v1/platform-roles/{id}
POST   /v1/platform-roles/{id}/permissions
DELETE /v1/platform-roles/{id}/permissions/{perm_id}

# Org roles
POST   /v1/orgs/{org_id}/roles
GET    /v1/orgs/{org_id}/roles
PATCH  /v1/orgs/{org_id}/roles/{id}
DELETE /v1/orgs/{org_id}/roles/{id}
POST   /v1/orgs/{org_id}/roles/{id}/permissions
DELETE /v1/orgs/{org_id}/roles/{id}/permissions/{perm_id}

# Workspace roles
POST   /v1/workspaces/{ws_id}/roles
GET    /v1/workspaces/{ws_id}/roles
PATCH  /v1/workspaces/{ws_id}/roles/{id}
DELETE /v1/workspaces/{ws_id}/roles/{id}
POST   /v1/workspaces/{ws_id}/roles/{id}/permissions
DELETE /v1/workspaces/{ws_id}/roles/{id}/permissions/{perm_id}

# Permissions catalog
GET    /v1/permissions

# Assignment
POST   /v1/users/{id}/platform-roles             — assign platform role
DELETE /v1/users/{id}/platform-roles/{role_id}
POST   /v1/users/{id}/org-roles                  — body: { org_id, org_role_id }
DELETE /v1/users/{id}/org-roles/{assignment_id}
POST   /v1/users/{id}/workspace-roles            — body: { workspace_id, workspace_role_id }
DELETE /v1/users/{id}/workspace-roles/{assignment_id}

# Runtime check
POST   /v1/rbac/check
    body: { user_id, resource, action, org_id?, workspace_id? }
GET    /v1/users/{id}/permissions/effective?org_id=...&workspace_id=...
```

### FastAPI dependency

```python
# Protected routes declare their required permission.
# The dependency walks platform → org → workspace tiers in order and
# short-circuits on the first match.
require_permission("orgs", "read")
require_permission("vault.secrets", "rotate")
require_permission("users", "admin")
```

### Seeded system roles

**Platform** — `platform_admin` (all), `platform_support` (read + impersonate), `platform_readonly`
**Org** — `org_owner`, `org_admin`, `org_member`, `org_billing`
**Workspace** — `workspace_admin`, `workspace_editor`, `workspace_viewer`

Every seeded role declares a `category_id` from `dim_categories` where
`category_type='role'` (e.g. `system`, `security`, `billing`, `support`).

Default admin user receives `platform_admin` at setup.

## Not in scope here

- Attribute-based access control (ABAC) conditions
- ReBAC (relationship-based)
- Group-role assignment (covered in `17_groups.md`, extended to three-tier)
- Per-flag RBAC (`26_feature_flags.md` handles its own category/scope gating)
