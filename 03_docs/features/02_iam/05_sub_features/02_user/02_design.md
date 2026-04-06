# 02_user — Design

## Data Model

### Fact Table: `10_fct_user_users`
Identity-only table. No business data — all descriptive attributes live in EAV.

| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR(36) PK | UUID v7 |
| status_id | SMALLINT FK | → 02_dim_user_statuses |
| account_type_id | SMALLINT FK | → 03_dim_account_types (default 1=human) |
| is_active | BOOLEAN | Operational toggle (default true) |
| is_test | BOOLEAN | Exclude from billing/metrics (default false) |
| deleted_at | TIMESTAMP | NULL = live, SET = soft-deleted |
| created_by | VARCHAR(36) | Actor UUID |
| updated_by | VARCHAR(36) | Actor UUID |
| created_at | TIMESTAMP | Auto via DEFAULT |
| updated_at | TIMESTAMP | Auto via trigger |

### EAV Table: `20_dtl_user_attrs`
One row per (user, attribute). Composite PK: `(entity_type_id, entity_id, attr_def_id)`.

### Attribute Definitions: `05_dim_user_attr_defs`

| ID | Code | Type | PII | Description |
|----|------|------|-----|-------------|
| 1 | email | text | yes | Primary email (globally unique) |
| 2 | display_name | text | no | Human-readable name |
| 3 | avatar_url | text | no | Profile picture URL |
| 4 | phone | text | yes | Phone E.164 format |
| 5 | settings | jsonb | no | User preferences blob |

### Dimension Tables

**02_dim_user_statuses**: active(1), inactive(2), suspended(3), pending_verification(4), deleted(5)

**03_dim_account_types**: human(1), service_account(2), bot(3)

### View: `v_10_user_users`
Pivots email, display_name, avatar_url, settings from EAV into named columns. Joins status + account_type dims for human-readable codes.

## Key Design Decisions

1. **EAV over columns**: Adding new user properties = 1 INSERT into dim_attr_defs. Zero schema changes.
2. **Snapshot versioning**: Every mutation captures full entity JSON in `92_dtl_iam_snapshots` for point-in-time reconstruction.
3. **Email uniqueness**: Enforced via partial unique index on `20_dtl_user_attrs` WHERE `attr_def_id=1`.
