## Planned: Scope Enforcement (Platform/Org/Workspace Access Guards)

**Severity if unbuilt:** CRITICAL (any authenticated user can read/write any org's data)
**Depends on:** Foundation sprint (`29_categories_and_scopes.md`), memberships (built), RBAC (`16_rbac.md`)

## Problem

Route handlers do not validate that the calling user belongs to the org or
workspace they are accessing. Knowing a UUID is sufficient to read or modify
any resource. Additionally, `scope` is currently a loose concept — there is
no first-class enum, so different parts of the codebase use strings
inconsistently.

## Design

### 1. Promote scope to a first-class enum

Add `06_dim_scopes` (see `29_categories_and_scopes.md`). Exactly three rows:
`platform`, `org`, `workspace`. Every table that needs a scope FKs this
table via `scope_id SMALLINT` — roles, features, feature flags, and future
scopeable entities.

### 2. Scope guards (new file: `04_backend/01_core/scope_guards.py`)

```python
async def require_org_member(
    org_id: str,
    token: dict = Depends(require_auth),
    conn: Connection = Depends(get_conn),
):
    """Raise 403 if calling user has no org-tier role or membership in this org."""
    ...

async def require_workspace_member(
    workspace_id: str,
    token: dict = Depends(require_auth),
    conn: Connection = Depends(get_conn),
):
    """Raise 403 if calling user has no workspace-tier role or membership in this workspace."""
    ...

async def require_platform_role(
    token: dict = Depends(require_auth),
    conn: Connection = Depends(get_conn),
):
    """Raise 403 if calling user holds no platform-tier role."""
    ...
```

### 3. Membership + role resolution

Each guard walks two sources in order:

1. **JWT shortcut** — if `token["oid"]` matches the requested `org_id` (similarly `wid` for workspaces), the scope is already validated at login/scope-switch; skip DB lookup.
2. **DB lookup** — query `40_lnk_user_org_roles` (or `40_lnk_user_workspace_roles`) for an active assignment. Fall back to `40_lnk_user_orgs` / `40_lnk_user_workspaces` membership tables for read-only access if no role is present.

Any user with a `platform_admin` role (from `40_lnk_user_platform_roles`) bypasses all org/workspace checks.

### 4. Route changes

All org-scoped routes inject `Depends(require_org_member)`.
All workspace-scoped routes inject `Depends(require_workspace_member)`.
All platform-admin-only routes inject `Depends(require_platform_role)`.

### 5. Error shape

```json
{ "ok": false, "error": { "code": "FORBIDDEN", "message": "You are not a member of this organisation." } }
```

## Not in scope here

- RBAC permission level checks (read vs write) — see `16_rbac.md`
- Category-based gating (see `29_categories_and_scopes.md`)
- Per-flag scope enforcement (see `26_feature_flags.md`)
