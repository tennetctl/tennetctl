# 03_workspace — Architecture

## Table Relationships

```
01_fct_org_orgs (cross-module)
      │ org_id
      ▼
12_fct_ws_workspaces ──entity_id──▶ 21_dtl_ws_attrs ──FK──▶ 06_dim_ws_attr_defs
      │                                                      │
      │ entity_id                                            │ entity_type_id=3
      ▼                                                      ▼
92_dtl_iam_snapshots                              01_dim_org_entity_types
90_fct_iam_audit_events
```

## Indexes

| Index | Columns | Purpose |
|-------|---------|---------|
| `pk_12_fct_ws_workspaces` | (id) | PK |
| `idx_12_fct_ws_live` | (org_id, created_at DESC) WHERE deleted_at IS NULL | Org-scoped live workspace listing |
| `pk_21_dtl_ws_attrs` | (entity_type_id, entity_id, attr_def_id) | EAV composite PK |
| `idx_21_dtl_ws_attrs_entity` | (entity_id) | Fetch all attrs for one workspace |

## Backend Files

```
01_backend/02_features/02_iam/03_workspace/
├── __init__.py
├── schemas.py      — WorkspaceCreate, WorkspaceUpdate, WorkspaceResponse
├── repository.py   — SQL queries (reads v_12_ws_workspaces, writes fct+dtl)
├── service.py      — Business logic, validates org exists, slug uniqueness
└── routes.py       — FastAPI router at /v1/orgs/{org_id}/workspaces
```
