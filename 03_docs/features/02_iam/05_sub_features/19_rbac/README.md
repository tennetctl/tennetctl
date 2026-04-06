# 19 — RBAC (Role-Based Access Control)

Roles, permissions, role-permission assignments, group-role links, and runtime permission checks.

## Tables
- `23_fct_roles` — role definitions (org-scoped or platform-wide, system flag)
- `26_fct_permissions` — permission catalogue (resource:action pairs)
- `33_lnk_role_permissions` — many-to-many role↔permission
- `36_lnk_group_roles` — many-to-many group↔role (users inherit via group membership)
- `v_roles` — view with permission_count
- `v_permissions` — permission catalogue view

## Seeded Data
- 4 system roles: super-admin, org-admin, org-member, org-viewer
- 25 permissions across org, user, workspace, group, role, flag, audit
- super-admin seeded with all permissions

## API
- `GET/POST /v1/roles` — list/create
- `GET/PATCH/DELETE /v1/roles/{id}` — get/update/soft-delete
- `GET/POST /v1/roles/{id}/permissions` — list/assign permissions
- `DELETE /v1/roles/{id}/permissions/{pid}` — revoke permission
- `GET /v1/permissions` — list all permissions
- `POST /v1/rbac/check` — runtime check: {user_id, resource, action, org_id} → {allowed, reason}

## Permission Check Resolution
1. org_members → dim_org_roles → fct_roles → role_permissions → check
2. group_members → group_roles → fct_roles → role_permissions → check

## Migration
`20260404_011_iam_rbac.sql`
