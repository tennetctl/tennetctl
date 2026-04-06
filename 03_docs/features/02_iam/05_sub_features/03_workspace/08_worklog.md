# 03_workspace — Worklog

## 2026-04-03

### Built
- Workspace CRUD backend (5 files)
- Tables: `12_fct_ws_workspaces`, `21_dtl_ws_attrs`, `06_dim_ws_attr_defs`
- View: `v_12_ws_workspaces` (pivots slug + display_name from EAV)
- Org validation: workspace creation validates org exists
- Slug uniqueness: service-layer check within org scope
- Snapshot versioning: every mutation captures full workspace JSON
- Audit integration: all mutations emit to `90_fct_iam_audit_events`
- Frontend: workspace list page (/iam/workspaces) + detail page (/iam/workspaces/[id])
- Detail page: info grid, delete button with confirmation dialog, activity timeline
- Version endpoints: GET /v1/orgs/{org_id}/workspaces/{id}/versions

### Migration
- Part of combined migration `20260403_006_iam_users_auth_workspaces.sql`
