# tennetctl — Core Documentation

This directory contains the foundational documents for tennetctl. Start here before reading anything else.

## Documents

| File | What it answers |
|------|----------------|
| [01_vision.md](01_vision.md) | Why tennetctl exists. What it is, who it is for, what it will never become. |
| [02_ethos.md](02_ethos.md) | The principles behind every decision. When a call is hard, this is the tiebreaker. |
| [03_rules.md](03_rules.md) | Hard rules. Every PR is checked against these. Non-negotiable. |
| [04_roadmap.md](04_roadmap.md) | What gets built, in what order, and why. |
| [05_contributing.md](05_contributing.md) | How to contribute: bugs, features, reviews, PRs, commit format. |
| [06_setup.md](06_setup.md) | Local development setup. Running in under 10 minutes. |
| [07_adding_a_feature.md](07_adding_a_feature.md) | Step-by-step: how to add a new sub-feature from scratch. |
| [08_decisions/](08_decisions/) | Architecture Decision Records. Why the system is built the way it is. |

## Architecture Decision Records

| ADR | Decision |
|-----|----------|
| [001](08_decisions/001_postgres_primary.md) | Postgres is the only required database |
| [002](08_decisions/002_nats_for_streams.md) | NATS JetStream for monitoring ingest — streams, subjects, consumer pattern |
| [003](08_decisions/003_raw_sql_no_orm.md) | Raw SQL with asyncpg — no ORM |
| [004](08_decisions/004_uuid7.md) | UUID v7 as primary keys |
| [005](08_decisions/005_clickhouse_later.md) | ClickHouse as an optional later backend |
| [006](08_decisions/006_database_conventions.md) | Database schema structure and naming conventions |
| [007](08_decisions/007_valkey_optional_cache.md) | Valkey as optional caching and rate-limiting backend |
| [008](08_decisions/008_monitoring_scope.md) | Monitoring vs Product Ops vs LLM Ops — module boundary definitions |
| [009](08_decisions/009_open_source_mit.md) | Open source under MIT license — rationale and sustainability model |
| [010](08_decisions/010_alerting_notify_separation.md) | Alerting engine writes pending rows; notify module delivers — outbox pattern |
| [011](08_decisions/011_monitoring_ui_architecture.md) | Monitoring frontend pages, navigation structure, and deferred features |
| [012](08_decisions/012_iam_architecture.md) | IAM module architecture — auth providers, session management, RBAC |
| [013](08_decisions/013_product_ops_schema_decisions.md) | Product Ops schema — event ingest, analytics, feature flags |
| [014](08_decisions/014_monitoring_pending_work.md) | Monitoring pending work — 15 deferred high-effort items |
| [015](08_decisions/015_feature_gating.md) | Feature module gating — single container, selective activation via env var |

## Reading Order

If you are new to the project:
1. `01_vision.md` — understand why this exists
2. `02_ethos.md` — understand the values
3. `06_setup.md` — get it running locally
4. `03_rules.md` — understand what you must not do
5. `07_adding_a_feature.md` — start building

If you want to understand a design decision, read the relevant ADR in `08_decisions/`.
