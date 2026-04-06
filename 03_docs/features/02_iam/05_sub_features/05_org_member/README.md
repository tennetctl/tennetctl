# 05_org_member

Links users to organisations with roles.

## Tables

| Table | Type | Purpose |
|-------|------|---------|
| `dim_org_roles` | Lookup | Role definitions (owner, admin, member, viewer) |
| `08_lnk_org_members` | Junction | User-to-org membership with role FK |
| `v_org_members` | View | Read-optimized join with role name/label |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/orgs/{org_id}/members` | List org members (paginated) |
| POST | `/v1/orgs/{org_id}/members` | Add a user to an org |
| GET | `/v1/orgs/{org_id}/members/{id}` | Get single membership |
| PATCH | `/v1/orgs/{org_id}/members/{id}` | Change member role |
| DELETE | `/v1/orgs/{org_id}/members/{id}` | Remove member (soft-delete) |

## Backend Files

- `__init__.py`
- `schemas.py` — OrgMemberCreate, OrgMemberUpdate, OrgMemberRead, OrgMemberList
- `repository.py` — CRUD via v_org_members (reads) and 08_lnk_org_members (writes)
- `service.py` — Business logic with org validation, duplicate check, audit
- `routes.py` — FastAPI router mounted at `/v1/orgs/{org_id}/members`

## Frontend

- Hook: `use-org-members.ts` — useOrgMembers, useAddOrgMember, useUpdateOrgMember, useRemoveOrgMember
- Members section embedded in org detail page (`/iam/orgs/[id]`)

## Migration

`20260404_008_iam_org_members.sql` in `09_sql_migrations/02_in_progress/`
