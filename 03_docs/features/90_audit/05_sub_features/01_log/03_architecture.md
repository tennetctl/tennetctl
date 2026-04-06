# 01_log — Architecture

## Overview

The audit log follows the project's standard 5-file backend pattern but is unusual in that it is **read-only at the API layer** — events are written exclusively through `01_core/audit.py`, never directly from `90_audit` routes.

## Data Flow

```
Any feature service
    → _core_audit.emit(conn, schema=..., action_id=..., ...)
        → INSERT into {schema}.90_fct_{feature}_audit_events
        → INSERT attrs into {schema}.91_dtl_{feature}_audit_attrs
        → INSERT snapshot into 02_iam.92_dtl_iam_snapshots (if snapshot provided)

90_audit API (read-only)
    → list/filter via 90_audit.v_audit_events (UNION ALL across all feature tables)
    → export via StreamingResponse (CSV, JSON, NDJSON)
```

## Key Components

### `01_core/audit.py`
The shared write path. All features use `_core_audit.emit()`. This function:
- Generates a UUID v7 event ID
- Resolves action/outcome codes to dim IDs
- Inserts the event row into the per-feature `fct_*_audit_events` table
- Inserts optional attribute rows into the per-feature `dtl_*_audit_attrs` table
- Inserts optional snapshot JSON into `02_iam.92_dtl_iam_snapshots`

### `90_audit.v_audit_events`
A `UNION ALL` view that queries every feature's audit event table and presents a unified schema. Adding a new feature requires extending this view.

### `90_audit/repository.py`
Dynamic WHERE clause building using parameterised queries (no ORM). Supports 8 filter dimensions plus date range.

## Table Layout

| Table | Schema | Purpose |
|-------|--------|---------|
| `90_fct_{feature}_audit_events` | per-feature | One row per event |
| `91_dtl_{feature}_audit_attrs` | per-feature | Key-value metadata attributes |
| `92_dtl_iam_snapshots` | `02_iam` | Entity state snapshots linked to events |
| `v_audit_events` | `90_audit` | UNION ALL read view |

## Numbering Convention

Audit tables within each feature schema use the `90–99` range to avoid collision with the feature's own tables.
