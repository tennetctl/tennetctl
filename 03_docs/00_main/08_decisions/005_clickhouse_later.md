# ADR-005: ClickHouse as an Optional Later Addition for High-Volume Analytics

**Status:** Accepted
**Date:** 2026-03-29

---

## Context

tennetctl's monitoring and product ops modules store time-series and analytics data. At high cardinality and high ingest volume, Postgres will eventually hit performance limits for these workloads:

- **Monitoring metrics:** Postgres with monthly partitioning handles ~1M metric samples/day comfortably. Beyond ~10M samples/day with high cardinality (>100k unique label combinations), query performance degrades.
- **Product ops events:** Postgres with Postgres aggregations handles ~10M events/month well. Beyond that, complex funnel and cohort queries become slow.

ClickHouse is purpose-built for columnar analytics storage at high volume. It is materially faster than Postgres for aggregation queries over large time-series datasets.

However, ClickHouse adds significant operational complexity: separate deployment, replication configuration, different SQL dialect, different backup strategy. For the majority of tennetctl's target users (small to mid-scale), ClickHouse is unnecessary.

---

## Decision

Postgres is the default and only required storage backend for monitoring and analytics data. ClickHouse support will be added later as an optional backend, enabled via configuration.

The implementation approach:
- The monitoring module's query layer is built against an abstract `MetricStore` interface from day one
- The product ops module's query layer is built against an abstract `EventStore` interface from day one
- The default implementations use Postgres
- ClickHouse implementations of these interfaces are added in a later phase
- Switching backends requires changing one configuration variable and running a backfill migration — no application code changes

---

## Consequences

**Positive:**
- tennetctl has zero required dependencies beyond Postgres and NATS
- Small teams running tennetctl on modest infrastructure are not forced to operate ClickHouse
- The abstract interface design means ClickHouse can be added without restructuring the codebase
- The Postgres implementations are simpler and easier to understand and contribute to

**Negative:**
- Large deployments (>10M monitoring samples/day) will hit Postgres performance limits before ClickHouse is available
- The abstract interface adds a layer of indirection to the query layer
- ClickHouse's SQL dialect differs from Postgres SQL — the same query cannot be used for both backends

**Mitigations:**
- The monitoring module README documents the approximate scale limits for the Postgres backend clearly
- Partitioning strategy and retention policies are aggressive by default to extend Postgres viability
- ClickHouse is in the roadmap as a named phase — it is not "maybe someday," it is "definitely, later"

---

## Interface Design

The `MetricStore` interface in `01_core/` defines the contract both backends must implement:

```python
class MetricStore(Protocol):
    """Storage backend for time-series metric data."""

    async def write_samples(self, samples: list[MetricSample]) -> None:
        """Write a batch of metric samples to storage."""
        ...

    async def query_range(
        self,
        metric_name: str,
        labels: dict[str, str],
        start: datetime,
        end: datetime,
        step: timedelta
    ) -> list[MetricPoint]:
        """Query metric values over a time range."""
        ...

    async def query_instant(
        self,
        metric_name: str,
        labels: dict[str, str],
        at: datetime
    ) -> MetricPoint | None:
        """Query a single metric value at a point in time."""
        ...
```

The Postgres implementation is in `04_monitoring/01_metrics/postgres_store.py`.
The ClickHouse implementation (when built) will be in `04_monitoring/01_metrics/clickhouse_store.py`.

The active backend is selected in `01_core/config.py`:

```python
METRIC_STORE_BACKEND: Literal["postgres", "clickhouse"] = "postgres"
CLICKHOUSE_URL: str = ""  # Required if backend is "clickhouse"
```

---

## Scale Guidance

| Scale | Recommended backend |
|-------|---------------------|
| < 1M metric samples/day | Postgres (default) |
| 1M – 50M metric samples/day | Postgres with TimescaleDB extension (optional) |
| > 50M metric samples/day | ClickHouse backend |
| < 10M product events/month | Postgres (default) |
| > 10M product events/month | ClickHouse backend |

These are guidelines, not hard limits. Query performance depends on cardinality, retention window, and hardware. Monitor query latency in production and switch backends when needed.
