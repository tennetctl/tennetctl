# Roadmap

tennetctl is built module by module. Each module is fully complete — documented, tested, and production-ready — before the next module begins. No half-built features ship.

## Module Overview

| # | Module | Status | Purpose |
|---|--------|--------|---------|
| 01 | Foundation | DONE | Core infrastructure: database, events, encryption, RBAC |
| 02 | IAM | DONE | Identity & Access Management — auth, users, orgs, RBAC, feature flags, sessions, invitations |
| 03 | Audit | DONE | Append-only audit trail and compliance reporting |
| 04 | Vault | BUILDING | Secrets management and rotation — projects, environments, secrets, configs, rotation |
| 05 | Monitoring | BUILDING | Metrics, traces, logs, alerting, dashboards, on-call, SLOs, synthetics, RUM, profiling |
| 06 | Notifications | BUILDING | Email, SMS, push, webhook, campaigns |
| 07 | Product Ops | BUILDING | Analytics, funnels, feature flags, web analytics |
| 08 | LLM Ops | PLANNED | LLM observability, prompt versioning, evals |

---

## Build Sequence and Rationale

### Phase 1: Foundation

**Goal:** A running application with no features. Just the scaffolding, shared infrastructure, and database setup.

Deliverables:
- Project structure with numbered module directories
- `01_core`: database, encryption, event bus, RBAC, rate limiting, auth middleware
- `docker-compose.yml` with Postgres + NATS only
- Migration runner and first three migrations (schemas, audit events table, outbox table)
- Frontend shell (Next.js, shadcn/ui, auth layout)
- CI pipeline: lint, type-check, test

**Why first:** Everything else builds on this. Getting the foundation right means not refactoring it later.

---

### Phase 2: IAM

**Goal:** A complete, standalone identity system. Any application can use tennetctl as its authentication and authorization provider.

Sub-features (in order):
1. Users and organisations — the identity foundation
2. Authentication — login, signup, password, magic links
3. Sessions — refresh token families, device trust, reuse detection
4. MFA — TOTP, passkeys (WebAuthn), backup codes
5. Social login — Google, GitHub, GitLab (OAuth2 callback)
6. RBAC — roles, permissions, groups, enforcement
7. API keys and service accounts
8. OAuth2/OIDC provider — auth code + PKCE, JWKS, discovery endpoint
9. SSO — SAML 2.0, OIDC enterprise SSO, SCIM 2.0 provisioning
10. Invitations and invite campaigns
11. Impersonation (platform admin only)
12. Admin UI — manage users, orgs, roles from dashboard

**Why second:** Every other module needs authentication. IAM must exist before anything else can have a meaningful UI.

---

### Phase 3: Audit

**Goal:** A queryable audit trail UI on top of the audit events table that was created in Phase 1.

Sub-features:
1. Query API — keyset pagination, filters by event type, actor, resource, time range
2. Live feed — Server-Sent Events stream of recent activity
3. Audit UI — timeline view, filter panel, event detail
4. Retention policies — configurable retention, archival to cold storage
5. Compliance export — CSV and JSON export for compliance reporting

**Why third:** The audit table already exists from Phase 1. Phase 3 is building the visibility layer on top of it. Low effort, high trust value.

---

### Phase 4: Vault

**Goal:** A secrets manager. Applications fetch their secrets from tennetctl at runtime. No more secrets in environment files or CI variables.

Sub-features:
1. Secrets CRUD — AES-256-GCM envelope encryption, Postgres storage
2. Projects and environments — namespace hierarchy (project → environment → key)
3. Version history — every secret change creates a new version, old versions are retained
4. Rotation policies — scheduled rotation with expiry alerts
5. Runtime inject — `GET /vault/inject/{project}/{env}` returns all secrets for an environment as a JSON blob
6. Audit integration — every secret access is audited

**Why fourth:** Before running monitoring in production, you need secure secrets management for the monitoring credentials, NATS credentials, and SMTP passwords. Vault enables all subsequent modules to store their configuration securely.

---

### Phase 5: Monitoring

**Goal:** Full observability. Replaces the Prometheus + Grafana + Loki + Jaeger stack.

Sub-features:
1. Metrics ingest — Prometheus-compatible scrape endpoint and push API; NATS JetStream consumer writes to Postgres (partitioned by month)
2. Distributed traces — OTLP/HTTP ingest via NATS; spans stored in Postgres
3. Log aggregation — structured log ingest via NATS; full-text search in Postgres
4. Alert rules — threshold and anomaly detection; rule evaluation worker runs every 10 seconds
5. On-call management — schedules, escalation policies, alert routing (replaces PagerDuty)
6. Dashboards — panel-based dashboard engine; dashboard definitions stored as JSONB; chart data from parameterized SQL queries
7. ClickHouse backend — optional storage backend for high-cardinality metrics (plug-in via config)

**Why fifth:** Monitoring needs secrets (from Vault) and authentication (from IAM). With both in place, the full observability stack can be built and dog-fooded immediately.

---

### Phase 6: Notifications

**Goal:** A full notification platform. Replaces Mailchimp, SendGrid, and PagerDuty alerting.

Sub-features:
1. Channels — email (SMTP), SMS (Twilio/SNS), web push, webhooks
2. Templates — Liquid-based template engine, version history, i18n
3. Transactional — event-driven dispatch (IAM events → welcome email, password reset, etc.)
4. Campaigns — audience builder, scheduling, A/B variants, send analytics
5. Delivery queue — Postgres-backed queue with exponential backoff retry
6. Tracking — open/click/bounce tracking, global suppression list, unsubscribe handling

**Why sixth:** Monitoring alerts need a notification channel (Phase 5 depends on Phase 6 for delivery). Notifications also need IAM (user lookup, org preferences) and Vault (SMTP credentials).

---

### Phase 7: Product Ops

**Goal:** Product analytics and feature flags. Replaces Mixpanel, Plausible, and LaunchDarkly.

Sub-features:
1. Event ingest — browser SDK (script tag) and server SDK (Python, Node); NATS JetStream consumer writes to Postgres
2. Analytics — event counts, unique users, pageviews, time-bucketed aggregations
3. Funnels — multi-step funnel analysis with drop-off rates
4. Retention cohorts — D1/D7/D28 retention curves
5. Feature flags — targeting by user, org, percentage rollout; environment-specific state
6. Web analytics — sessions, bounce rate, top pages, referrers (replaces Plausible)

---

### Phase 8: LLM Ops

**Goal:** Observability for AI features. Replaces Langfuse and Helicone.

Sub-features:
1. LLM call traces — prompt, completion, model, tokens, latency, cost per call
2. Prompt versioning — version history, A/B assignment, rollout percentage
3. Eval runs — datasets, scoring functions, pass/fail thresholds, run history
4. Cost attribution — token usage aggregated by project, user, model, and time
5. Gateway — optional HTTP proxy that auto-instruments any OpenAI-compatible API call

---

## What "Complete" Means for Each Phase

A module is complete when:

- [ ] All sub-features are built and working
- [ ] All sub-features have tests (unit + integration, 80% coverage minimum)
- [ ] API documentation is generated and committed
- [ ] Feature docs in `docs/features/{module}/` are up to date
- [ ] `feature.manifest.yaml` status is `DONE`
- [ ] A basic E2E test covers the primary user flow
- [ ] The module is documented in `docs/00_main/06_setup.md` if it requires configuration

---

## Things Not on This Roadmap (Yet)

These are acknowledged gaps that will be addressed in future phases:

- **Billing and metering** — usage-based billing engine for tennetctl itself (not needed until tennetctl is offered as a hosted service)
- **Multi-region replication** — Postgres streaming replication setup guide and configuration
- **Kubernetes operator** — Helm chart and K8s operator for deploying tennetctl in a cluster
- **LDAP / Active Directory** — enterprise directory integration beyond SAML
- **Mobile SDKs** — iOS and Android event tracking SDKs for Product Ops

These are not on the roadmap because the core platform must be solid before these are valuable. They will be added as numbered phases when the time is right.

---

## Where We Are (as of 2026-03-30)

### Fully Done

- **01 Foundation** — database, encryption, event bus, RBAC, rate limiting, auth middleware
- **02 IAM** — all 21 migrations applied, all backend routes live, all frontend pages built, 11/11 E2E tests passing
- **03 Audit** — append-only audit trail, query API, live feed, UI page at `/audit`

### Building Now

- **04 Vault** — frontend pages live (`/vault/projects`, `/vault/rotation`); backend in progress
- **05 Monitoring** — 95%+ of backend routes live (ingest, query, dashboards, alerting, SLOs, synthetics, status page, on-call, profiling, RUM); all frontend pages built; migrations 022–023 applied, migrations 024–031 have `.skip` files (not yet run), migration 032 pending
- **06 Notifications** — backend modules live (providers, templates, rules, send-log, suppressions, config); frontend pages built
- **07 Product Ops** — **V1 complete**: 10/10 sub-features built, 507 routes live, 6 migrations applied (030–035), 11 frontend pages, JS + Python SDKs shipped. V2 gaps documented in `docs/features/08_product_ops/00_overview.md`

### Pending (Monitoring)

Migrations 024–032 need to be applied. ClickHouse storage backend deferred (ADR-005). See [ADR-012](08_decisions/012_monitoring_pending_work.md) for the full list of 15 deferred high-effort items.
