# Org — Architecture

## Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│  API Layer (routes.py)                                   │
│  GET /v1/orgs  POST /v1/orgs  GET|PATCH|DELETE /orgs/:id │
└───────────────────────┬─────────────────────────────────┘
                        │ calls
┌───────────────────────▼─────────────────────────────────┐
│  Service Layer (service.py)                              │
│  create_org / get_org / list_orgs / update_org /         │
│  delete_org                                              │
│  • Slug-uniqueness guard                                 │
│  • Slug release on re-create after delete               │
│  • Emits audit event (action 1/2/3)                      │
└───────────┬───────────────────────┬─────────────────────┘
            │                       │
┌───────────▼──────┐   ┌────────────▼────────────────────┐
│ Repository       │   │ Audit Repository                 │
│ (repository.py)  │   │ emit_audit_event(...)            │
│                  │   └─────────────────────────────────┘
│ Reads:           │
│  v_orgs (view)   │
│ Writes:          │
│  11_fct_orgs     │
│  20_dtl_attrs    │
└──────────────────┘
```

## Database Tables

| Table | Purpose |
|-------|---------|
| `"02_iam".11_fct_orgs` | Identity skeleton — UUID PK, status FK, audit columns |
| `"02_iam".20_dtl_attrs` | EAV attributes: `slug` (text), `display_name` (text), `settings` (jsonb) |
| `"02_iam".dim_org_statuses` | Lookup: `active`, `suspended`, `trialing`, `archived` |
| `"02_iam".v_orgs` | Read view — resolves status code, pivots EAV attrs |

## Key Attribute IDs

| Attr | `attr_def_id` | Type |
|------|--------------|------|
| `slug` | `_ATTR_SLUG` | `key_text` |
| `display_name` | `_ATTR_DISPLAY_NAME` | `key_text` |
| `settings` | `_ATTR_SETTINGS` | `key_jsonb` |

## Audit Events

| Action | `action_id` | `entity_type_id` |
|--------|------------|-----------------|
| Create | 1 | 2 (org) |
| Update | 2 | 2 (org) |
| Delete | 3 | 2 (org) |

## Important Invariants

1. **Slug immutability** — slug cannot be changed after creation (no PATCH field).
2. **Slug recycling** — if a deleted org held the slug, its EAV attr is removed before the new insert, freeing the unique index.
3. **Soft delete only** — `deleted_at` is set; hard purge is a background job.
4. **`updated_at` via trigger** — the app never sets `updated_at`; a DB trigger does.
