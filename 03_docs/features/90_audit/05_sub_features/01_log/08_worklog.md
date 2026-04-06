# 01_log — Worklog

## 2026-04-03

### Built
- Schema `"90_audit"` with 3 shared dimension tables (actions, outcomes, actor_types)
- Per-feature audit table: `"02_iam"."90_fct_iam_audit_events"` + attrs table
- Global UNION ALL view: `"90_audit".v_audit_events`
- Core emit utility: `01_core/audit.py` with `emit()` function + snapshot integration
- Snapshot versioning: `"02_iam"."92_dtl_iam_snapshots"` — full entity JSON at every mutation
- Read-only API: GET /v1/audit-events (list + filter + paginate), /{id} (detail + attrs), /export (CSV/JSON/NDJSON)
- Frontend: /audit dashboard with stats cards, collapsible filter panel, event table, detail panel
- Frontend: audit timeline component embedded in org/user/workspace detail pages
- Entity_id filter: server-side filtering added (was client-side initially)
- Metadata JSONB parsing fix: asyncpg returns JSONB as string, now parsed properly

### Migration
- `20260403_005_audit_bootstrap.sql` — creates schema, dims, tables, view

### Frontend Components (9 files)
- audit-action-badge, audit-outcome-badge, audit-entity-badge (icon+color per type)
- audit-stats (4 stat cards), audit-filters (collapsible panel with presets)
- audit-log-table (7-column table with outcome color borders)
- audit-detail-panel (slide-in right panel with event fields + metadata + attrs)
- audit-timeline (vertical timeline for entity detail pages)
- relative-time (live-updating timestamps)
