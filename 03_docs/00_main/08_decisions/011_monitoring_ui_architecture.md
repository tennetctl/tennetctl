# ADR-011: Monitoring Frontend Architecture

**Status:** Accepted
**Date:** 2026-03-29

---

## Context

With the monitoring backend (ingest, query, dashboards, alerting) complete, the frontend needed a clear set of pages, navigation structure, and component patterns. Decisions were needed on: how to organize the sidebar, which pages are needed, how to handle the observability vs alerting distinction, and what patterns to use for data-heavy pages (trace explorer, log viewer, metrics browser).

---

## Decision

**Monitoring frontend is organized into two sidebar sections: Observability and Alerting. Each has dedicated pages. All pages use the same TanStack Query + TanStack Table + shadcn/ui pattern as the IAM module.**

---

## Pages

### Observability section

| Route | Purpose |
|-------|---------|
| `/monitoring/services` | Service list with RED metrics (rate, errors, duration) |
| `/monitoring/traces` | Trace span list with filter bar; links to span detail |
| `/monitoring/traces/[trace_id]` | Full trace detail: attributes, resource attrs, events |
| `/monitoring/logs` | Structured log list with severity + service filters |
| `/monitoring/metrics` | Metric name browser + series data table for selected metric |
| `/monitoring/dashboards` | Dashboard card grid with create dialog |
| `/monitoring/dashboards/[id]` | Panel list + Execute tab (runs backend panel evaluator) |
| `/monitoring/retention` | Per-signal retention policy table with inline edit |

### Alerting section

| Route | Purpose |
|-------|---------|
| `/monitoring/alerting/rules` | Alert rule CRUD with inline active toggle + manual evaluate |
| `/monitoring/alerting/instances` | Read-only live instance view with state filter |
| `/monitoring/alerting/silences` | Silence CRUD with repeatable matcher fields + time window |
| `/monitoring/alerting/receivers` | Receiver CRUD with type badge + JSON config editor |
| `/monitoring/alerting/routing` | Routing tree node management |
| `/monitoring/alerting/inhibitions` | Inhibition rule CRUD with dual matcher lists |

---

## Navigation Structure

The sidebar uses distinct group labels rather than nested dropdowns:

```
Platform
  Dashboard | Audit | Settings

Identity & Access
  Orgs | Users | Workspaces | Groups | Roles | ...

Vault
  Projects | Rotation

Observability
  Services | Traces | Logs | Metrics | Dashboards | Retention

Alerting
  Rules | Instances | Silences | Receivers | Routing | Inhibitions
```

**Why not a single "Monitoring" group?** The Observability and Alerting concerns are distinct enough that developers and operators navigate them differently. Observability is exploratory (what is happening?); Alerting is administrative (what rules are configured?). Collapsing them into one section obscures this distinction.

---

## Data Fetching Pattern

All monitoring hooks follow the same pattern as IAM hooks:

```typescript
export function useAlertRules(params?: { limit?: number; offset?: number; is_active?: boolean }) {
  return useQuery({
    queryKey: ["alert-rules", params],
    queryFn: () => apiClient.get<AlertRuleListResponse>(`/monitoring/alerting/rules${qs}`),
    staleTime: 30_000,
  })
}
```

Hook files:
- `src/features/monitoring/query/hooks/use-monitoring-query.ts` — observability hooks
- `src/features/monitoring/alerting/hooks/use-alerting.ts` — alerting hooks
- `src/features/monitoring/dashboards/hooks/use-dashboards.ts` — dashboard hooks

---

## State Badge Color Convention

Alert instance state is color-coded consistently across all pages:

| State | Badge variant | Semantic color |
|-------|--------------|----------------|
| `firing` | `destructive` | Red |
| `pending` | `secondary` | Yellow/muted |
| `inactive` | `outline` | Gray |
| `resolved` | `default` | Green/primary |

---

## Dashboard Execute Tab

The dashboard detail page has an Execute tab that calls `POST /monitoring/dashboards/{id}/execute`. This runs all panels against the backend panel executor (which dispatches to query adapters per panel type). Results are displayed as cards showing: panel title, status badge (ok/error/timeout), raw data, and execution duration.

This design allows dashboards to be tested directly from the UI without requiring a separate chart rendering library. Chart rendering will be added in a future iteration when a suitable library is chosen.

---

## What Was Explicitly Deferred

| Feature | Reason deferred |
|---------|----------------|
| Real-time chart rendering | Requires choosing a chart library; deferring until Phase 5 is fully validated |
| Log stream (SSE) viewer | Backend supports it (`GET /monitoring/logs/stream`); UI deferred for iteration 2 |
| Service map graph visualization | Requires a graph/node layout library; deferred |
| Trace waterfall view | Requires span nesting visualization; deferred |
| Dashboard drag-and-drop panel layout | Requires a grid layout library; deferred |

These are not architectural decisions — they are scope decisions for the current iteration. The backend APIs for all of these are implemented and ready.

---

## Consequences

- 14 new pages added under `/monitoring/` and `/monitoring/alerting/`
- 3 hook files covering all monitoring API endpoints
- Sidebar updated with Observability and Alerting sections
- TypeScript types for all monitoring API shapes in `src/types/api.ts`
- Zero new dependencies — builds on existing TanStack Query/Table + shadcn/ui stack
