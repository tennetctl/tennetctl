# Monitoring & Product Ops — Design Spec

**Date:** 2026-04-04  
**Branch:** feat/c-iam (worktrees branched from here)  
**Status:** Approved, ready for implementation

---

## Context

tennetctl needs a built-in observability and product analytics system to replace external tools like PostHog, Prometheus, Grafana, and Signoz. The system uses NATS JetStream (already in docker-compose) as the ingest bus and Postgres (already running) as the storage layer. No new infrastructure services are needed.

Two independent modules are built sequentially:
- `04_monitoring` — infrastructure observability: metrics, traces, logs, dashboards, full alerting engine
- `12_product_ops` — product analytics: events, sessions, session replay, funnels, retention, cohorts, feature flags

Both port directly from `99_forref/tennetctl-v2/`, translated to current project conventions.

---

## Architecture

### Data Flow (both modules)

```
SDK / Agent / App
      ↓
NATS JetStream (stream per module)
      ↓
Worker (consumer, batch processing)
      ↓
Postgres (EAV-named tables)
      ↓
FastAPI query routes
      ↓
Next.js frontend pages
```

### NATS Streams

| Stream | Subjects | Module |
|--------|----------|--------|
| `MONITORING` | `monitoring.metrics`, `monitoring.traces`, `monitoring.logs` | 04_monitoring |
| `PRODUCT_OPS` | `product_ops.events.*` | 12_product_ops |

### Infrastructure

- **Postgres:** existing, port 5432
- **NATS JetStream:** existing in docker-compose, ports 4222/8222
- **No new services** — no Valkey, no MinIO, no additional containers

---

## Module 1: `04_monitoring`

**Location:** `tennetctl/01_backend/02_features/04_monitoring/`

### Sub-features (7, each 5-file pattern)

| Dir | Sub-feature | Description |
|-----|-------------|-------------|
| `01_ingest` | Ingest worker | NATS JetStream consumer for `monitoring.metrics`, `monitoring.traces`, `monitoring.logs`; batch-inserts to Postgres; backpressure + retry |
| `02_query` | Query API | Time-range + label filter queries for metrics, traces, logs; aggregations (sum, avg, rate) |
| `03_dashboards` | Dashboards | Dashboard + panel CRUD; `panel_executor.py` runs arbitrary queries and returns data for frontend rendering |
| `04_alerting` | Alert engine | Full engine ported from ref: evaluator, router, fingerprinter, silencer, inhibitor, matchers, conditions — 7 engine files under `engine/` subdir |
| `05_alert_receivers` | Receivers | Receiver CRUD — webhook, email (via `05_notify` module), extensible |
| `06_alert_rules` | Alert rules | Rule CRUD + background evaluation scheduler; fires instances when conditions breach |
| `07_slos` | SLOs | SLO definition CRUD + burn rate calculation; tracks error budget consumption |

### DB Tables

```
fct_metric_sample      — (id, workspace_id, metric_name, labels JSONB, value, ts)
fct_trace_span         — (id, workspace_id, trace_id, span_id, parent_span_id, name, start_ts, end_ts, attributes JSONB, status)
fct_log_entry          — (id, workspace_id, level, body, resource JSONB, attributes JSONB, ts)
fct_alert_rule         — (id, workspace_id, name, expr, for_duration, labels JSONB, annotations JSONB, receiver_id, state, created_at)
fct_alert_instance     — (id, rule_id, fingerprint, labels JSONB, state, fired_at, resolved_at)
fct_alert_silence      — (id, workspace_id, matchers JSONB, starts_at, ends_at, created_by)
fct_alert_inhibition   — (id, workspace_id, source_matchers JSONB, target_matchers JSONB, equal JSONB)
dim_alert_receiver     — (id, workspace_id, name, type, config JSONB)
dim_dashboard          — (id, workspace_id, title, description, created_at)
dim_dashboard_panel    — (id, dashboard_id, title, type, query JSONB, position JSONB)
fct_slo_definition     — (id, workspace_id, name, target_ratio, window_days, metric_expr, created_at)
fct_slo_burn_event     — (id, slo_id, burn_rate, error_budget_remaining, ts)
```

### Frontend Pages

```
/monitoring/metrics                    — metric time-series browser
/monitoring/traces                     — trace list + span waterfall
/monitoring/logs                       — log stream + search
/monitoring/dashboards/[id]            — custom dashboard with panels
/monitoring/alerting/rules             — alert rule list + create/edit
/monitoring/alerting/silences          — active silences
/monitoring/alerting/instances         — firing alert instances
/monitoring/slos                       — SLO list + burn rate gauges
```

### Alerting Engine Files (inside `04_alerting/engine/`)

Ported directly from `99_forref/tennetctl-v2/01_backend/02_features/04_monitoring/04_alerting/engine/`:
- `evaluator.py` — rule condition evaluation loop
- `router.py` — routes firing alerts to receivers
- `fingerprint.py` — deduplication by label hash
- `silencer.py` — suppresses alerts matching silence matchers
- `inhibitor.py` — inhibits target alerts when source alert fires
- `matchers.py` — label matcher logic (=, !=, =~, !~)
- `conditions.py` — threshold + composite condition parsing

---

## Module 2: `12_product_ops`

**Location:** `tennetctl/01_backend/02_features/12_product_ops/`

### Sub-features (11, each 5-file pattern)

| Dir | Sub-feature | Description |
|-----|-------------|-------------|
| `01_ingest` | Ingest worker | NATS JetStream consumer for `product_ops.events.*`; batch of 250; enriches with UA parsing + server timestamp; bulk-inserts to `fct_event` |
| `02_projects` | Projects | Project CRUD — isolates analytics data per app; required foreign key for all events |
| `03_analytics` | Insights | Event counts, breakdowns, time-series — core query engine for the Insights page |
| `04_funnels` | Funnels | Ordered step conversion analysis; computes drop-off at each step |
| `05_retention` | Retention | Cohort retention grids (day 0/1/7/30); returns matrix for heatmap rendering |
| `06_paths` | Paths | User journey / Sankey path analysis; top N paths from/to events |
| `07_cohorts` | Cohorts | Cohort definition (filter rules) + background membership computation |
| `08_sessions` | Sessions | Session lifecycle — start, activity, end, duration, page view count |
| `09_replay` | Session replay | DOM snapshot chunks stored as Postgres JSONB; ordered playback API |
| `10_dashboards` | Dashboards | Product-ops-specific dashboards (independent of monitoring dashboards) |
| `11_feature_flags` | Feature flags | Flag CRUD + evaluation API + exposure event auto-tracking |

### DB Tables

```
dim_project            — (id, workspace_id, name, api_key, created_at)
fct_event              — (id, project_id, event_name, anonymous_id, user_id, session_id, event_time, properties JSONB, context JSONB, ingested_at)
fct_session            — (id, project_id, anonymous_id, user_id, started_at, ended_at, duration_s, page_view_count, entry_url, exit_url)
fct_session_replay_chunk — (id, session_id, chunk_index, events JSONB, recorded_at)
dim_cohort             — (id, project_id, name, filters JSONB, created_at)
lnk_cohort_member      — (cohort_id, user_id, computed_at)
fct_funnel_definition  — (id, project_id, name, steps JSONB, created_at)
fct_retention_definition — (id, project_id, name, start_event, return_event, created_at)
dim_feature_flag       — (id, project_id, key, name, enabled, rollout_pct, rules JSONB, created_at)
fct_flag_exposure      — (id, flag_id, user_id, anonymous_id, variant, exposed_at)
dim_product_dashboard  — (id, project_id, title, created_at)
dim_product_panel      — (id, dashboard_id, title, type, query JSONB, position JSONB)
```

### Event Schema (ingest)

```python
TrackEvent:
  event_name: str
  anonymous_id: str
  user_id: str | None
  session_id: str | None
  event_time: datetime | None      # client time; server overwrites with ingested_at
  properties: dict
  context: EventContext

EventContext:
  page_url: str | None
  referrer: str | None
  user_agent: str | None           # enricher parses → device/browser/os
  locale: str | None
  screen_width: int | None
  screen_height: int | None
  ip: str | None
```

### Frontend Pages

```
/product-ops/insights              — event analytics + breakdowns
/product-ops/funnels               — funnel builder + conversion view
/product-ops/retention             — cohort retention heatmap
/product-ops/paths                 — user journey Sankey
/product-ops/cohorts               — cohort list + membership
/product-ops/sessions              — session list + timeline
/product-ops/replay/[id]           — session replay player
/product-ops/dashboards            — product dashboard list
/product-ops/dashboards/[id]       — individual dashboard
/product-ops/feature-flags         — flag list + create/edit/toggle
```

---

## Ralph Sequencing (18 runs total)

### Phase 1 — `04_monitoring` (runs 1–7)

```
Run 1:  04_monitoring/01_ingest        NATS worker + migrations
Run 2:  04_monitoring/02_query         query API
Run 3:  04_monitoring/03_dashboards    dashboard + panel executor
Run 4:  04_monitoring/04_alerting      full engine (7 engine files)
Run 5:  04_monitoring/05_alert_receivers  receiver CRUD
Run 6:  04_monitoring/06_alert_rules   rule CRUD + scheduler
Run 7:  04_monitoring/07_slos          SLO + burn rate
```

### Phase 2 — `12_product_ops` (runs 8–18)

```
Run 8:  12_product_ops/01_ingest       NATS worker + migrations
Run 9:  12_product_ops/02_projects     project CRUD
Run 10: 12_product_ops/03_analytics    insights queries
Run 11: 12_product_ops/04_funnels      funnel analysis
Run 12: 12_product_ops/05_retention    cohort retention
Run 13: 12_product_ops/06_paths        journey paths
Run 14: 12_product_ops/07_cohorts      cohort management
Run 15: 12_product_ops/08_sessions     session tracking
Run 16: 12_product_ops/09_replay       session replay (JSONB)
Run 17: 12_product_ops/10_dashboards   product dashboards
Run 18: 12_product_ops/11_feature_flags  feature flags + exposures
```

Each run: ephemeral worktree → TDD (failing test first) → 5-file backend → migration → frontend page(s) → Robot Framework E2E → PR.

---

## Testing Strategy

### Per Sub-feature
- **pytest unit:** service + repository layers, mock nothing internal
- **pytest integration:** real Postgres, real NATS JetStream
- **Robot Framework E2E:** `.robot` files in `02_frontend/tests/e2e/{feature}/`
- **NATS worker tests:** publish → consume → assert DB rows within timeout
- **Coverage target:** 80%+ per CLAUDE.md

### NATS Worker Test Pattern
```python
# 1. Publish N test events to JetStream subject
# 2. Start worker for one batch cycle
# 3. Assert DB row count matches
# 4. Assert enrichment fields populated (ingested_at, parsed_ua)
```

### End-to-End Smoke (after all 18 runs)
1. `docker compose up` — Postgres + NATS healthy
2. Publish metric samples to `monitoring.metrics` → query API returns time-series
3. Publish product events to `product_ops.events.track` → analytics returns counts
4. Create alert rule → breach threshold → assert alert instance fires
5. Load session replay in browser → JSONB chunks render in order
6. Evaluate feature flag → exposure event recorded in `fct_flag_exposure`

---

## Reference Locations

| What | Where in ref |
|------|-------------|
| Monitoring ingest/query/dashboards/alerting | `99_forref/tennetctl-v2/01_backend/02_features/04_monitoring/` |
| Product ops all sub-features | `99_forref/tennetctl-v2/01_backend/02_features/12_product_ops/` |
| Monitoring frontend pages | `99_forref/tennetctl-v2/02_frontend/src/app/monitoring/` |
| Product ops frontend pages | `99_forref/tennetctl-v2/02_frontend/src/app/product-ops/` |
| NATS ADR | `tennetctl/03_docs/00_main/08_decisions/002_nats_for_streams.md` |
| docker-compose | `tennetctl/80_infra/docker-compose.yml` |
