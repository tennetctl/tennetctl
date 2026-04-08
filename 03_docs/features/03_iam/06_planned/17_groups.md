## Planned: Groups Sub-feature

**Severity if unbuilt:** HIGH (RBAC roles can't be assigned to sets of users without groups)
**Depends on:** org membership (currently in memberships sub-feature)
**Prerequisite for:** RBAC group-role assignment (16_rbac.md)

## Problem

Users can belong to orgs and workspaces, but there is no way to group users
within an org for access-control purposes. Assigning roles to 50 users one
by one is unusable.

## Scope when built

### DB tables

New sub-feature `04_group` under `03_iam`:

- `10_fct_groups` — id, org_id, is_system, is_active, deleted_at, ...
- `20_dtl_attrs` — name, slug, description (EAV, reuses iam_group entity type)
- `40_lnk_group_members` — id, group_id, user_id, added_by, created_at (immutable)

### Endpoints

```
POST   /v1/groups                        — create group (org_id, name, slug)
GET    /v1/groups                        — list groups (org_id filter, paginated)
GET    /v1/groups/{id}                   — get group
PATCH  /v1/groups/{id}                   — update (name, slug, description, is_active)
DELETE /v1/groups/{id}                   — soft-delete

GET    /v1/groups/{id}/members           — list members (paginated)
POST   /v1/groups/{id}/members           — add member (user_id)
GET    /v1/groups/{id}/members/{mid}     — get membership
DELETE /v1/groups/{id}/members/{mid}     — remove member
```

### Rules

- Slugs unique within org.
- `is_system = true` groups (e.g. `everyone`) are seeded and cannot be deleted.
- Membership rows are immutable (`lnk_*` convention — no updated_at).
- Every mutation emits an audit event.

## Not in scope here

- Dynamic groups (rule-based membership)
- Group nesting
- Group-role assignment routes (belong in 16_rbac.md once RBAC exists)
