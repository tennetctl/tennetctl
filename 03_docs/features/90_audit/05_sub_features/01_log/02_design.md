# 01_log — Design

## Shared Dimension Tables (in "90_audit" schema)

### 01_dim_audit_actions
| ID | Code | Label |
|----|------|-------|
| 1 | create | Create |
| 2 | update | Update |
| 3 | delete | Delete |
| 4 | read | Read |
| 5 | login | Login |
| 6 | logout | Logout |
| 7 | access | Access |
| 8 | export | Export |
| 9 | enable | Enable |
| 10 | disable | Disable |
| 11 | rotate | Rotate |
| 12 | restore | Restore |

### 02_dim_audit_outcomes
| ID | Code |
|----|------|
| 1 | success |
| 2 | failure |
| 3 | denied |
| 4 | partial |
| 5 | error |

### 03_dim_audit_actor_types
| ID | Code |
|----|------|
| 1 | user |
| 2 | service_account |
| 3 | api_key |
| 4 | system |

## Per-Feature Audit Table (identical columns per feature)

**Example: `"02_iam"."90_fct_iam_audit_events"`**

| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR(36) PK | UUID v7 |
| org_id | VARCHAR(36) | Tenant scope |
| actor_id | VARCHAR(36) | Who did it |
| actor_type_id | SMALLINT FK | → 03_dim_audit_actor_types |
| action_id | SMALLINT FK | → 01_dim_audit_actions |
| entity_type_id | SMALLINT FK | → entity type catalog |
| entity_id | VARCHAR(36) | What was affected |
| outcome_id | SMALLINT FK | → 02_dim_audit_outcomes |
| ip_address | VARCHAR(64) | Client IP |
| metadata | JSONB | Free-form context |
| created_at | TIMESTAMP | Immutable |

**No updated_at, no deleted_at** — append-only by design.

## Per-Feature Audit Attrs Table

**`"02_iam"."91_dtl_iam_audit_attrs"`** — structured key-value pairs per event.

## Global View: `"90_audit".v_audit_events`

UNION ALL across all per-feature tables, joining dims to resolve human-readable codes. Includes `source_schema` literal column to identify which feature emitted the event.

## Snapshot Integration

**`"02_iam"."92_dtl_iam_snapshots"`** — full entity JSON captured at every mutation. Linked to audit events via `audit_event_id`. Enables point-in-time entity reconstruction.
