# ADR-008: Monitoring Scope and Feature Boundary

**Status:** Accepted
**Date:** 2026-03-29

---

## Context

tennetctl Phase 5 is called "Monitoring" in the roadmap. During planning, the question arose whether to rename this to "Operations" and absorb Product Ops (Phase 7) and LLM Ops (Phase 8) into a single broad feature — a unified observability platform covering infrastructure traces/logs/metrics, web analytics, product funnels/cohorts, and LLM call tracing.

The reference implementation (`99_forref/`) contains all three layers already implemented together, which made the boundary question concrete rather than hypothetical.

---

## Decision

**Keep `monitoring` as the Phase 5 feature name. Keep `product_ops` (Phase 7) and `llmops` (Phase 8) as separate features on the roadmap.**

The three features share infrastructure (NATS JetStream, Postgres) but serve different audiences, have different data models, and are independently shippable.

---

## Boundary Definitions

### Phase 5: Monitoring

**Audience:** Engineers and operators.
**Replaces:** Prometheus + Grafana + Loki + Jaeger + PagerDuty + StatusPage.io.
**Signal types:** OTLP traces, OTLP logs, OTLP metrics.
**Ingest protocol:** OpenTelemetry (OTLP/HTTP JSON) only. No Prometheus remote-write. No proprietary format.

Sub-features in scope:
- OTEL ingest pipeline (NATS consumer workers → Postgres)
- Trace explorer, log explorer, metrics explorer
- Service map and RED metrics
- Custom dashboards (panel engine replaces Grafana)
- Unified alerting engine (replaces Prometheus Alertmanager + PagerDuty alerts)
- Status page (public incident management, replaces StatusPage.io)

### Phase 7: Product Ops

**Audience:** Product managers and growth engineers.
**Replaces:** Mixpanel, Amplitude, PostHog, Plausible, LaunchDarkly.
**Signal types:** Product events (track/identify), web vitals, session events, page views.
**Ingest protocol:** Segment-compatible event API + browser SDK.

Sub-features: event ingest, analytics, funnels, cohorts, paths, retention, web analytics, feature flags.

### Phase 8: LLM Ops

**Audience:** ML engineers and AI product teams.
**Replaces:** Langfuse, Langsmith, Helicone.
**Signal types:** LLM call traces, prompt versions, eval runs, token cost attribution.
**Ingest protocol:** Native SDK (Python/Node) or HTTP proxy gateway.

Sub-features: LLM trace CRUD, prompt versioning, eval runs, cost attribution, gateway.

---

## Why Not One Unified "Operations" Module

**Different data models.** OTEL spans/logs/metrics have a fundamentally different schema than product events (track/identify/session) or LLM call traces (prompt/completion/tokens/cost). Forcing them into one module creates a schema that is correct for none.

**Different delivery timelines.** Each is a full product on its own. Combining them delays all three — you cannot ship monitoring until analytics is done, and vice versa. The sequential build model (one module fully complete before the next begins) is already the right approach.

**Different open-source positioning.** Monitoring, Product Ops, and LLM Ops can each be open-sourced independently. A combined module is harder to understand, harder to contribute to, and harder to adopt incrementally.

**"Operations" is the wrong word.** "Operations" implies DevOps tooling — pipelines, deployments, runbooks. It would confuse users familiar with the standard terminology (observability, product analytics, LLM observability).

---

## What They Share

All three features share and must remain compatible with:

| Shared layer | Owned by |
|---|---|
| NATS JetStream ingest transport | `01_core/nats_client.py` |
| Postgres primary store | `01_core/database.py` |
| IAM auth middleware | `02_features/iam/` |
| Audit event emission | `02_features/audit/` |
| Response envelope + error format | `01_core/response.py` |

No feature may create its own transport or auth system. All three route through the same middleware stack.

---

## Consequences

- Phase 5 (Monitoring) ships with OTEL traces/logs/metrics + dashboards + alerting + status page.
- Phase 7 (Product Ops) ships separately with Segment-compatible event API + analytics.
- Phase 8 (LLM Ops) ships separately with LLM trace CRUD + prompt versioning + evals.
- The frontend sidebar will have three distinct navigation sections when all three phases are built.
- Session replay (a Product Ops concept) is NOT in Phase 5. Phase 5 has auth session monitoring only (already in IAM).
- RUM browser SDK is NOT in Phase 5. It belongs to Phase 7 Product Ops.

---

## Alternatives Considered

**Rename to `telemetry` or `signals`:** Rejected. "Monitoring" is the most understood word for the Prometheus/Grafana replacement space. Engineers know exactly what it means.

**Move dashboards and alerting to separate phases:** Rejected. Dashboards and alerting are core to making monitoring useful. Shipping traces/logs/metrics without dashboards or alerting would be incomplete and not dog-foodable.

**Include status page in a later "ops tools" phase:** Rejected. The status page is fed directly by monitoring data (component health from traces/metrics). Building it in Phase 5 alongside the data source is the correct order. It is also low-complexity relative to the other sub-features.
