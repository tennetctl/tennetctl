# 02_user — Architecture

## Table Relationships

```
02_dim_user_statuses ←FK── 10_fct_user_users ──FK→ 03_dim_account_types
                                  │
                                  │ entity_id
                                  ▼
                          20_dtl_user_attrs ──FK→ 05_dim_user_attr_defs
                                  │
                                  │ entity_id
                                  ▼
                          92_dtl_iam_snapshots (versioned state)
                                  │
                          90_fct_iam_audit_events (audit trail)
```

## Indexes

| Index | Columns | Purpose |
|-------|---------|---------|
| `pk_10_fct_user_users` | (id) | Primary key |
| `idx_10_fct_user_users_live` | (created_at DESC) WHERE deleted_at IS NULL | Fast live-user queries |
| `pk_20_dtl_user_attrs` | (entity_type_id, entity_id, attr_def_id) | EAV composite PK |
| `idx_20_dtl_user_attrs_entity` | (entity_id) | Fetch all attrs for one user |
| `uq_20_dtl_user_attrs_email` | (key_text) WHERE attr_def_id=1 | Global email uniqueness |

## Triggers
- `trg_10_fct_user_users_updated_at`: Auto-sets `updated_at` on every UPDATE.
- `trg_20_dtl_user_attrs_updated_at`: Auto-sets `updated_at` on attr row updates.

## Backend Files

```
01_backend/02_features/02_iam/02_user/
├── __init__.py
├── schemas.py      — UserCreate, UserUpdate, UserResponse
├── repository.py   — SQL queries (reads v_10_user_users, writes fct+dtl)
├── service.py      — Business logic + audit emission + snapshot capture
└── routes.py       — FastAPI router at /v1/users
```
