# ADR-001: Postgres as the Primary and Only Required Database

**Status:** Accepted
**Date:** 2026-03-29

---

## Context

tennetctl needs persistent storage for multiple categories of data: user accounts, sessions, audit events, metrics, traces, logs, secrets, notification queues, and product analytics events.

The common pattern in the industry is to use purpose-built databases for each category: Postgres for transactional data, InfluxDB or VictoriaMetrics for time-series metrics, ClickHouse for analytics, Redis for queues and caching, Elasticsearch for log search.

Each of these databases is genuinely better at its specific category than Postgres. But each is also an additional deployment to manage, an additional failure mode, an additional system to learn, and an additional dependency that blocks a developer from running tennetctl locally.

---

## Decision

Postgres 16 is the only required external database. tennetctl will not require Redis, InfluxDB, ClickHouse, Elasticsearch, or any other database to function.

All data — transactional, time-series, event streams, queues, secrets — is stored in Postgres by default. Optional storage backends (ClickHouse for high-cardinality metrics, Redis for caching) are supported via pluggable backend interfaces but are never required.

---

## Consequences

**Positive:**
- A developer can start tennetctl with a single `docker compose up` and one Postgres instance
- Operators need to manage, back up, and monitor only one database system
- All data is queryable from a single connection using SQL
- Postgres is the most understood and trusted relational database — operators know how to recover it
- Cross-module queries and joins are possible (within module schemas) without network calls

**Negative:**
- Postgres is not the best choice for high-cardinality time-series metrics at scale (>10k unique metric series, >1M samples/day)
- Full-text log search in Postgres is significantly slower than Elasticsearch at high log volumes
- Without Redis, rate limiting is implemented via Postgres counter tables, which are slower (but sufficient for most workloads)

**Mitigations:**
- Time-series tables use monthly partitioning and aggressive retention policies to manage size
- Monitoring data flows through NATS JetStream (a streaming buffer) before writing to Postgres, decoupling the ingestion rate from the write rate
- The `MetricStore` and `LogStore` interfaces are abstract from day one; ClickHouse can be enabled via a configuration flag without changing application code
- Scale limits are documented clearly in the monitoring module README so operators know when they need to consider the ClickHouse backend

---

## Alternatives Considered

**Redis as a required cache and queue:** Rejected. Redis adds operational complexity that is not justified for most deployments. Postgres advisory locks, counter tables, and the LISTEN/NOTIFY outbox pattern cover the use cases Redis would address at the scale tennetctl targets.

**InfluxDB or VictoriaMetrics for metrics:** Rejected as a required dependency. These are excellent at their job but add another deployment. The ClickHouse optional backend addresses the case where Postgres metric storage is insufficient.

**SQLite for development:** Rejected. SQLite does not support the Postgres-specific features tennetctl uses (RLS, LISTEN/NOTIFY, schemas, uuid_generate_v7, advisory locks). Running a different database in development would hide production-only issues.
