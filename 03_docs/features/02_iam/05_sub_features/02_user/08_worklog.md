# 02_user — Worklog

## 2026-04-03

### Built
- User CRUD backend (5 files: schemas, repository, service, routes, __init__)
- Tables: `10_fct_user_users`, `20_dtl_user_attrs`, `05_dim_user_attr_defs`, `02_dim_user_statuses`, `03_dim_account_types`
- View: `v_10_user_users` (pivots EAV attrs into named columns)
- Email uniqueness: partial unique index on dtl_user_attrs
- Snapshot versioning: every create/update/delete captures full user JSON
- Audit integration: all mutations emit to `90_fct_iam_audit_events`
- Frontend: user list page (/iam/users) + user detail page (/iam/users/[id])
- User detail: info grid, status badge, Suspend/Activate/Disable/Enable/Delete actions, activity timeline
- Version endpoints: GET /v1/users/{id}/versions, GET /v1/users/{id}/versions/{n}

### Migration
- `20260403_006_iam_users_auth_workspaces.sql` — combined migration for users + auth + workspaces

### Tests
- Backend verified via Python asyncio test (register → login → me → list users → snapshots)
- Frontend verified via Playwright MCP (create user, view detail, action buttons)
