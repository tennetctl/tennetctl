# 04_group -- IAM Groups

Org-scoped groups for organising users within an organisation.

## Tables

| Table | Type | Schema | Description |
|-------|------|--------|-------------|
| `07_fct_groups` | Entity | `02_iam` | Group identity with org FK, name, slug, description |
| `v_groups` | View | `02_iam` | Read view with derived `is_deleted` flag |

## API Endpoints

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| POST | `/v1/groups` | 201 | Create group |
| GET | `/v1/groups` | 200 | List groups (paginated, optional `org_id` filter) |
| GET | `/v1/groups/{id}` | 200 | Get single group |
| PATCH | `/v1/groups/{id}` | 200 | Update group name/slug/description |
| DELETE | `/v1/groups/{id}` | 204 | Soft-delete group |

## Backend Files

- `01_backend/02_features/02_iam/04_group/__init__.py`
- `01_backend/02_features/02_iam/04_group/schemas.py`
- `01_backend/02_features/02_iam/04_group/repository.py`
- `01_backend/02_features/02_iam/04_group/service.py`
- `01_backend/02_features/02_iam/04_group/routes.py`

## Frontend Files

- `02_frontend/src/features/iam/hooks/use-groups.ts`
- `02_frontend/src/app/(dashboard)/iam/groups/page.tsx`
- `02_frontend/src/app/(dashboard)/iam/groups/[id]/page.tsx`

## Migration

`03_docs/features/02_iam/09_sql_migrations/02_in_progress/20260404_007_iam_groups.sql`
