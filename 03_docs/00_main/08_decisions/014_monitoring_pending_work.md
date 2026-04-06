# ADR-012 — Monitoring: Pending High-Effort Work

**Date:** 2026-03-30
**Status:** Accepted
**Context:** Monitoring module (Phase 5) is substantially complete. Backend routes and frontend pages are all built. However, a set of high-effort items was deliberately deferred to keep the build moving. This document records what was deferred, why, and when each item should be tackled.

---

## What Was Deferred and Why

### 1. Apply Pending Migrations 024–031 (+ 032)

**What:** Migrations 024–031 have `.skip` files — the SQL schema files exist but have not been run against the database. Migration 032 (synthetics assertions) is also pending.

**Why deferred:** Migrations depend on running infrastructure. The schemas were written speculatively during the backend build session. They need to be run, tested, and any column mismatches between the SQL and the repository layer fixed.

**When to tackle:** Next dedicated monitoring session, before any end-to-end testing of SLOs, synthetics, on-call, profiling, or RUM features.

---

### 2. ClickHouse Storage Backend

**What:** A pluggable `MetricStore` Protocol interface that routes high-volume metric writes to ClickHouse instead of Postgres.

**Why deferred:** Not on critical path. Postgres with monthly partitioning is sufficient for current scale. The interface design is documented in ADR-005. ClickHouse adds operational complexity (another service to run, another deployment dependency).

**When to tackle:** After the platform handles >10M metric data points/day, or when query latency on `fct_otel_metrics` exceeds acceptable thresholds. See [ADR-005](005_clickhouse_later.md).

---

### 3. Session Replay (rrweb)

**What:** Browser-side session recording using rrweb, stored alongside RUM session data. Allows replaying a user session frame-by-frame for debugging.

**Why deferred:** High storage cost (recording blobs), complex frontend replay player, privacy implications (PII in recordings). RUM works well without it.

**When to tackle:** After RUM is validated in production with real traffic. Requires a separate storage decision (object store vs. Postgres BYTEA).

---

### 4. Composite Alert Rules (AND/OR Across Multiple Rules)

**What:** Alert rules that fire only when multiple conditions are simultaneously true — e.g., "error rate > 5% AND p95 latency > 2000ms".

**Why deferred:** Requires a DAG evaluation engine on top of the existing single-rule evaluator. Current single-condition rules cover 90% of use cases.

**When to tackle:** When users report needing correlated alerting. Can be added as a new `composite` condition type in `cfg_alert_rules` without schema changes.

---

### 5. Dashboard Template Variables ($service, $env substitution)

**What:** Dashboard-level variable definitions (e.g., `$service = dropdown of ref_services`) with substitution in panel query configs at execution time.

**Why deferred:** The `variables JSONB` column already exists in `cfg_dashboards`. The panel executor has a stub for variable substitution. Full implementation requires a variable resolver that runs before panel execution.

**When to tackle:** Next dashboard session. The data model is in place; only the resolver logic is missing.

---

### 6. Panel Annotations (Event Markers on Time Series)

**What:** Vertical line markers on time-series panels showing when deployments, incidents, or alert firings occurred.

**Why deferred:** Cosmetic / UX enhancement. Requires an annotation data source (audit events or alert events) and recharts `ReferenceLine` rendering.

**When to tackle:** After dashboards are in regular use. Low effort to add once the base dashboard is stable.

---

### 7. Dashboard Public Embed (Signed URL)

**What:** A signed URL that allows embedding a dashboard panel in an external site without authentication.

**Why deferred:** Security-sensitive feature (signed URL generation, expiry, org isolation). Requires careful review. Not needed until dashboards are in production.

**When to tackle:** After core dashboard functionality is validated. Requires security review.

---

### 8. Profile Diff (Flamegraph Comparison)

**What:** Compare two profiling time windows side-by-side as a differential flamegraph — shows which functions got slower or faster between two deployments.

**Why deferred:** Complex frontend rendering (differential flamegraph coloring). The raw data is already captured in `fct_profiling_samples`.

**When to tackle:** After profiling is in regular use and users request diff analysis.

---

### 9. Multi-Step Synthetics (Chained HTTP Requests)

**What:** A synthetic check that executes a sequence of HTTP requests, passing values from response N to request N+1 (e.g., login → get token → call authenticated endpoint).

**Why deferred:** Requires a scripting model (JSON DSL or YAML) for chaining steps. Single-step checks cover most monitoring use cases.

**When to tackle:** After single-step synthetics are validated. The `cfg_synthetics_checks` schema can be extended with a `steps JSONB[]` column.

---

### 10. RBAC on Monitoring Resources (Per-Org Dashboard/Alert Access Control)

**What:** Fine-grained access control on monitoring resources — e.g., only certain roles can edit alert rules or view specific dashboards.

**Why deferred:** Current implementation uses org membership as the only access gate. Per-resource RBAC requires a `lnk_resource_roles` table and enforcement at the repository layer.

**When to tackle:** When multiple teams within an org need isolated monitoring views. Pairs with the Phase 2 RBAC system already built in IAM.

---

### 11. Org-Level Monitoring Quotas (Ingest Rate Limits)

**What:** Per-org limits on ingest volume — e.g., max 10M spans/day, max 1GB logs/day. Over-quota requests return 429.

**Why deferred:** Requires a metering layer (count writes per org per day) and a quota enforcement check in the ingest API. Not needed until multi-tenant usage.

**When to tackle:** Before opening ingest to untrusted tenants. Pairs with the Billing module (future phase).

---

### 12. Metric Rollups (Downsampling for Long Retention)

**What:** A background job that aggregates raw `fct_otel_metrics` rows into hourly and daily rollup tables, then drops raw data older than the retention window.

**Why deferred:** Not needed until high-volume data accumulates. Postgres partitioned table drops (by month) handle retention for now.

**When to tackle:** When `fct_otel_metrics` grows beyond 100M rows. Rollup table schema should be designed alongside the ClickHouse migration decision.

---

### 13. Error Budget Policies (Auto-Actions on SLO Burn)

**What:** When an SLO's error budget burns below a threshold (e.g., <10% remaining), automatically trigger an action: freeze deployments, page on-call, create an incident.

**Why deferred:** Requires integration with on-call (already built), incident management (already built), and deployment freeze (future CI/CD integration). High coordination cost.

**When to tackle:** After SLOs are in active use and burn rates are being monitored. Can be implemented as a new alert rule type that reads from SLO burn rate data.

---

### 14. PagerDuty / OpsGenie Bi-Directional Sync

**What:** Sync on-call schedules and alert instances with PagerDuty or OpsGenie — inbound (PD acknowledges → update alert instance) and outbound (alert fires → create PD incident).

**Why deferred:** External dependency on third-party APIs. The on-call and alerting systems are built as self-contained replacements. Sync is only needed for teams that run both systems in parallel during migration.

**When to tackle:** When a customer explicitly requests PD/OpsGenie parity during a migration window.

---

### 15. NATS Dead-Letter Queue Handling

**What:** When a consumer worker (trace/log/metric) fails to process a message after N retries, publish it to a dead-letter subject for inspection and manual replay.

**Why deferred:** The `aud_ingestion_rejections` table captures validation failures. Infrastructure-level retries (NATS redelivery) cover transient failures. A full DLQ requires additional NATS stream config and an admin UI.

**When to tackle:** After the NATS consumer workers are deployed in production and message loss is observed. The existing `ConsumerWorker` base class can be extended to publish to `monitoring.dlq.>` on max redelivery.

---

## Priority Order for Next Monitoring Session

1. Apply migrations 024–032 (unblocks all E2E testing)
2. Dashboard template variables (high user value, low effort)
3. Composite alert rules (next most-requested alerting feature)
4. Panel annotations (low effort, high dashboard UX value)
5. Metric rollups (operational necessity at scale)
6. Everything else in order of user demand
