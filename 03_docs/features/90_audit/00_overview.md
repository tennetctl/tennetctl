# 90_audit — Overview

The Audit feature provides a global, enterprise-grade audit trail for the entire tennetctl platform. Every state-changing operation across all features emits an immutable audit event.

## Architecture: Hybrid Write-per-Feature / Read-Global

```
WRITE PATH (per-feature, fast):
  "02_iam"."90_fct_iam_audit_events"     ← all IAM sub-features write here
  "07_vault"."90_fct_vault_audit_events"  ← (future) vault writes here

READ PATH (global, cross-feature):
  "90_audit".v_audit_events = UNION ALL of all per-feature audit tables

SHARED DIMS (in "90_audit" schema):
  01_dim_audit_actions       — what was done (create, update, delete, login, ...)
  02_dim_audit_outcomes      — what happened (success, failure, denied, ...)
  03_dim_audit_actor_types   — who type (user, system, api_key, ...)
```

## Key Properties
- **Immutable**: Events are never updated or deleted. Append-only.
- **Per-feature tables**: Each feature schema has its own audit table — prevents single-table bottleneck.
- **Global view**: `v_audit_events` UNION ALL across all feature tables for cross-feature queries.
- **Snapshot versioning**: Every mutation also captures a full entity JSON snapshot in `92_dtl_iam_snapshots`.

## Core Utility
`01_backend/01_core/audit.py` provides `emit()` function used by all services:
```python
await _core_audit.emit(conn, schema="02_iam", action_id=ACTION_CREATE, 
    entity_type_id=2, entity_id=org_id, snapshot=org_dict)
```

## How New Features Onboard
1. Add one line to `_AUDIT_TABLES` dict in `01_core/audit.py`
2. Create `90_fct_{feature}_audit_events` table in their schema (identical columns)
3. Recreate `v_audit_events` with UNION ALL including new table
4. Call `emit()` in service layer — done
