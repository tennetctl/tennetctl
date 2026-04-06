# 01_log — Scope

The Audit Log sub-feature provides the infrastructure for capturing, storing, and querying audit events across all tennetctl features.

## In Scope
- **Shared Dimensions**: Actions (create/update/delete/login/...), outcomes (success/failure/denied), actor types (user/system/api_key)
- **Per-Feature Audit Tables**: Each feature schema has its own `90_fct_{feature}_audit_events` table
- **Global UNION ALL View**: `90_audit.v_audit_events` queries across all feature tables
- **Read-Only API**: List, filter, paginate, export audit events
- **Snapshot Integration**: Audit events link to entity snapshots via `audit_event_id`

## Out of Scope
- **Real-time streaming**: SSE/WebSocket event stream deferred
- **Retention policies**: Auto-archival/deletion of old events deferred
- **Alerting**: Audit-based alerts deferred to monitoring feature

## Acceptance Criteria
- [x] Every mutation across all IAM sub-features emits an audit event
- [x] Events are immutable (no UPDATE, no DELETE)
- [x] Global view queries across all feature audit tables
- [x] API supports filtering by entity_type, entity_id, action, outcome, org_id, actor_id, date range
- [x] Export supports CSV, JSON, NDJSON formats
