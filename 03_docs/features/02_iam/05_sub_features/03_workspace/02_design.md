# 03_workspace — Design

## Data Model

### Fact Table: `12_fct_ws_workspaces`

| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR(36) PK | UUID v7 |
| org_id | VARCHAR(36) | Owning org (cross-module, no enforced FK) |
| is_active | BOOLEAN | Operational toggle (default true) |
| is_test | BOOLEAN | Exclude from billing (default false) |
| deleted_at | TIMESTAMP | Soft-delete |
| created_by | VARCHAR(36) | |
| updated_by | VARCHAR(36) | |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | Auto via trigger |

### EAV Table: `21_dtl_ws_attrs`
Composite PK: `(entity_type_id=3, entity_id, attr_def_id)`.

### Attribute Definitions: `06_dim_ws_attr_defs`

| ID | Code | Type | Description |
|----|------|------|-------------|
| 20 | slug | text | URL-safe workspace identifier |
| 21 | display_name | text | Human-readable name |
| 22 | settings | jsonb | Workspace configuration blob |

### View: `v_12_ws_workspaces`
Pivots slug, display_name, settings from EAV. Includes org_id for scoped queries.

## Key Design Decisions

1. **Org-scoped routes**: All workspace endpoints are nested under `/v1/orgs/{org_id}/workspaces`.
2. **Slug uniqueness within org**: Enforced in service layer (not DB index, since org_id is on fct table but slug is in dtl table).
3. **No workspace status dim**: Workspaces use `is_active` toggle only. No lifecycle states like orgs/users.
