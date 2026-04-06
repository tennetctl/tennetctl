# 07 — Workspace Member

Links users to workspaces with roles (admin, member, viewer).

## Tables
- `dim_workspace_roles` — lookup: admin, member, viewer
- `11_lnk_workspace_members` — junction with role_id FK, soft-delete
- `v_workspace_members` — view resolving role name

## API
- `GET /v1/workspaces/{id}/members` — list
- `POST /v1/workspaces/{id}/members` — add
- `GET /v1/workspaces/{id}/members/{mid}` — get
- `PATCH /v1/workspaces/{id}/members/{mid}` — change role
- `DELETE /v1/workspaces/{id}/members/{mid}` — remove (soft-delete)

## Migration
`20260404_012_iam_workspace_members.sql`
