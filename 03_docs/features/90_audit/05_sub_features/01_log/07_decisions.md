# 01_log — Decisions

## ADR-L001: Per-Feature Audit Tables, Not a Single Central Table

**Decision:** Each feature schema owns its own `90_fct_{feature}_audit_events` table. A `UNION ALL` view in the `90_audit` schema provides the global read interface.

**Rationale:** A single central table would require all features to share one schema and create lock contention on high-write workloads. Per-feature tables isolate blast radius, allow schema-specific indexes, and let features be deployed independently. The UNION ALL view provides the unified read interface with no runtime cost beyond query planning.

**Consequence:** Adding a new feature requires extending `v_audit_events`. This is documented in the feature blueprint.

---

## ADR-L002: Write Path Lives in `01_core/audit.py`, Not in `90_audit`

**Decision:** The `emit()` function that writes audit events is in `01_core/audit.py`. The `90_audit` feature is read-only.

**Rationale:** Features need to emit audit events as part of their own transaction. If the write path lived in `90_audit`, features would have a circular import dependency (`02_iam` → `90_audit` → ... → `02_iam`). Keeping the write path in `01_core` breaks this cycle.

---

## ADR-L003: Snapshots Stored in `02_iam.92_dtl_iam_snapshots`

**Decision:** Entity snapshots are stored in a single EAV table in the IAM schema rather than per-feature snapshot tables.

**Rationale:** Snapshots are linked to audit events by `audit_event_id`. Since IAM entities (org, user, workspace) are the primary entities across all features, co-locating snapshots avoids duplicating the snapshot infrastructure in every feature schema. Non-IAM features can adopt their own snapshot tables if needed.

---

## ADR-L004: No Soft-Delete or Update on Audit Events

**Decision:** `evt_*` audit event tables have no `deleted_at` or `updated_at` columns. Events are immutable.

**Rationale:** Audit logs lose their integrity if events can be modified or deleted. Immutability is enforced at the schema level (no UPDATE/DELETE triggers or app paths). Retention/archival is a separate concern deferred to a future policy feature.
