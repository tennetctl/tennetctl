# ADR-013: Product Ops Schema & Architecture Decisions

**Date:** 2026-03-30
**Status:** Accepted
**Phase:** 7 — Product Ops

---

## Context

During implementation of Product Ops (Phase 7), several architectural decisions were made that deviate from the initial planning spec or that required explicit choices between alternatives. This ADR captures those decisions so future sessions don't re-investigate the same ground.

---

## Decision 1: Direct Postgres Write (No NATS V1)

**Decision:** V1 ingest pipeline writes events directly to Postgres. No NATS JetStream consumer in the critical path.

**Rationale:**
- Reduces V1 complexity substantially — no consumer worker, no stream config, no DLQ management
- Postgres can absorb early-stage event volumes without a queue
- The API shape (`POST /track`, `POST /batch`) is identical to what a NATS-backed version would expose — the consumer is an implementation detail
- NATS consumer can be added transparently when volume requires it

**Consequences:**
- No at-least-once delivery guarantee on ingest failures
- No dead-letter queue for malformed events
- Under high write load, the ingest API is latency-coupled to Postgres

**V2 path:** Add NATS JetStream stream `PRODUCT_OPS`, publish from routes, add consumer worker that validates and batch-inserts. Zero API surface change.

---

## Decision 2: `cfg_funnel_steps` as a Separate Table

**Decision:** Funnel steps are stored in `cfg_funnel_steps` (one row per step) rather than as a `steps JSONB` column on `cfg_funnel_definitions`.

**Rationale:**
- Steps are an ordered list — a separate table with `step_index` gives real ordering guarantees without JSONB array manipulation
- Enables future per-step filters (`filters JSONB` column exists on `cfg_funnel_steps`)
- Follows the project convention of keeping fct/cfg tables free of JSONB collections

**Implementation note:**
- Repository reads: two-query pattern — fetch headers, then `WHERE funnel_id = ANY($1::text[])` bulk-fetch steps, group in Python
- Repository writes: insert header first, then loop inserting steps with sequential `step_index`

---

## Decision 3: `cfg_cohort_conditions` with `operator_id` FK

**Decision:** Cohort rules are rows in `cfg_cohort_conditions` with `operator_id FK → dim_cohort_operators`, not a `rules JSONB` array on `cfg_cohort_definitions`.

**Rationale:**
- Operator semantics (does it use `n`? what's the SQL?) are encoded in the dim table, not scattered in application code
- Enables query-time operator joining without parsing JSONB
- 13 operators seeded: `did`, `did_not`, `did_n_times`, `did_at_least_n`, `did_at_most_n`, `property_eq`, `property_neq`, `property_contains`, and 5 reserved slots

**Implementation note:**
- Bidirectional mapping dict in `repository.py`:
  - `_OP_TO_ID`: `(rule_type, frontend_operator)` → `(operator_id, uses_n)`
  - `_ID_TO_OP`: `operator_id` → `(rule_type, frontend_operator)`
- Frontend operators translated on read (norm) and on write (pack)

---

## Decision 4: Alert Rule JSONB Packing with Python Shim

**Decision:** `cfg_product_alert_rules` stores alert configuration as `query_config JSONB` + `condition_config JSONB` rather than flat scalar columns. Python shims handle translation.

**Rationale:**
- Alert rules are a product-level config object, not a hot query target
- JSONB config allows future alert types (anomaly detection, formula-based) without schema migration
- Follows the monitoring module's alert rule pattern

**Shim pattern:**
```python
# On read: _norm_alert() unpacks JSONB to flat fields
event_name = row["query_config"].get("event_name")
condition_type = row["condition_config"].get("type")
threshold_value = row["condition_config"].get("threshold")
window_minutes = row["condition_config"].get("window_minutes")

# On write: pack flat fields into JSONB
query_config = {"event_name": event_name, "type": "trends"}
condition_config = {"type": condition_type, "threshold": threshold_value, "window_minutes": window_minutes}
```

---

## Decision 5: Dashboard `is_pinned` / `layout` Shim

**Decision:** `cfg_product_dashboards` has `is_pinned` (not `is_default`) and no `layout` column. Python shim presents frontend-compatible shape without schema changes.

**Rationale:**
- The frontend `Dashboard` TypeScript type expects `is_default: boolean` and `layout: []`
- Changing the schema would require a new migration and frontend type update
- A read-time shim is lower risk and keeps the schema clean

**Shim:**
```python
def _norm_dashboard(row):
    d = dict(row)
    d["is_default"] = d.pop("is_pinned", False)
    d["layout"] = []
    return d
```

---

## Decision 6: asyncpg JSONB Codec (No Manual `json.dumps`)

**Decision:** Never call `json.dumps()` on dicts before passing to asyncpg. asyncpg registers a codec that serializes automatically.

**Rationale:**
- asyncpg registers a JSONB codec at connection time that calls `json.dumps()` internally
- Manually serializing before passing results in double-encoded strings (`"{\\"key\\": \\"value\\"}"`)
- This was a bug in the agent-written repository code — fixed by removing manual serialization

**Rule:** Pass Python dicts directly to `asyncpg` JSONB parameters.

---

## Decision 7: `uuid7()` not `new_id()` from `backend.01_core.id`

**Decision:** Use `_id_mod.uuid7()` for ID generation. The `new_id()` function does not exist.

**Rationale:**
- `backend.01_core.id` exports `uuid7()` only
- Agent-generated code incorrectly assumed `new_id()` — caused `AttributeError` at runtime
- All product_ops repository files corrected to `str(_id_mod.uuid7())`

---

## Decision 8: Soft-Delete on All Config Tables

**Decision:** `cfg_funnel_definitions`, `cfg_cohort_definitions`, `cfg_product_dashboards`, `cfg_product_alert_rules` all use soft-delete (`deleted_at = CURRENT_TIMESTAMP`), not hard DELETE.

**Rationale:**
- Consistent with project-wide soft-delete convention
- Enables recovery and audit trail
- Hard DELETE was the initial agent-written implementation — corrected

---

## Consequences for Future Sessions

1. **NATS consumer worker** — when adding, the ingest routes need to switch from `_svc.ingest_event()` to `js.publish()`. Repository layer unchanged.
2. **Alert evaluator** — needs to read `cfg_product_alert_rules`, evaluate against `fct_events`, write to `evt_product_alert_fires`, update `last_triggered_at` via JSONB join.
3. **Dashboard panels** — `cfg_product_panels` table exists. Panel execution needs `POST /dashboards/{id}/panels/{panel_id}/execute` wired to the analytics query engine.
4. **Cohort materialization** — SAQ job should populate `lnk_cohort_members` by re-running `evaluate_cohort()` on a schedule and bulk-inserting results.
5. **rrweb SDK integration** — JS SDK needs `rrweb.record()` + `_flushReplay()` plumbing. Replay backend endpoints already exist.
