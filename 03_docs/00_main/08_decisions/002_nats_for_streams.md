# ADR-002: NATS JetStream for Monitoring Ingestion and Internal Event Streaming

**Status:** Accepted
**Date:** 2026-03-29

---

## Context

tennetctl's monitoring module needs to ingest metrics, traces, and logs from many applications simultaneously. These are high-volume, write-heavy, time-ordered streams.

At moderate scale (10 applications each emitting 100 metric scrapes per minute, plus continuous trace and log data), the ingest rate can exceed what Postgres can absorb through direct INSERT without connection pooling overhead and write contention.

Additionally, the Postgres LISTEN/NOTIFY pattern used for internal module-to-module events has a payload size limit of 8KB and does not persist events across process restarts. For high-volume monitoring ingestion, these limitations are a reliability risk.

---

## Decision

NATS 2.10 with JetStream enabled is a required dependency alongside Postgres. It is used exclusively for high-volume ingestion pipelines in the monitoring module:

- Metrics ingestion (Prometheus push and scrape results)
- Distributed trace ingestion (OTLP/HTTP)
- Structured log ingestion

Internal module-to-module events (IAM → Notifications, Monitoring → Alerting, etc.) continue to use the Postgres LISTEN/NOTIFY + transactional outbox pattern. NATS is not used for internal eventing.

Consumer workers subscribe to NATS JetStream subjects, batch-process messages, and write to Postgres. NATS acts as a durable buffer between the ingest API and the Postgres writers.

---

## Consequences

**Positive:**
- NATS absorbs ingestion spikes without blocking the API or pressuring Postgres
- JetStream provides durable, persistent message storage — no data loss if a consumer worker restarts
- NATS is extremely lightweight: single binary, ~10MB RAM at idle, trivial to run in Docker
- Consumer worker can apply backpressure, batching, and retry without the ingest API being aware
- NATS subjects map cleanly to data types (`monitoring.metrics`, `monitoring.traces`, `monitoring.logs`)

**Negative:**
- tennetctl now requires two external services instead of one (Postgres + NATS)
- Operators must understand NATS enough to monitor it and recover it
- Monitoring data has an eventual consistency lag (NATS → Postgres consumer latency, typically < 1 second)

**Mitigations:**
- NATS is included in the default `docker-compose.yml` — zero additional setup for local development
- NATS JetStream configuration is managed by tennetctl at startup (stream creation, subject bindings) — operators do not need to configure NATS manually
- Consumer worker status is exposed at `/health/workers` — operators can see whether consumers are running and what their lag is
- The monitoring module README documents the NATS architecture clearly

---

## Alternatives Considered

**Postgres LISTEN/NOTIFY for monitoring ingest:** Rejected. NOTIFY has an 8KB payload limit, does not persist events across restarts, and does not support consumer groups (multiple workers processing in parallel). At monitoring ingestion volumes, NOTIFY is not suitable.

**Kafka for all events:** Rejected. Kafka is operationally heavy — Zookeeper (or KRaft), topic management, consumer group coordination. The overhead is not justified for tennetctl's target scale. NATS JetStream provides similar guarantees at a fraction of the operational cost.

**Redis Streams:** Rejected. Redis adds a third required dependency (after Postgres and a queue). NATS serves the streaming use case without needing Redis elsewhere in the stack. Redis Streams also has weaker durability guarantees than NATS JetStream.

**Direct Postgres INSERT from ingest API:** Acceptable at small scale but rejected as the default. It creates tight coupling between ingest rate and Postgres write capacity, and makes it impossible to add ClickHouse as a backend later without changing the ingest API.

---

## Boundary: What NATS Is and Is Not Used For

| Use case | Technology | Why |
|----------|-----------|-----|
| Metrics ingest | NATS JetStream | High volume, streaming |
| Trace ingest | NATS JetStream | High volume, streaming |
| Log ingest | NATS JetStream | High volume, streaming |
| IAM → Notification events | Postgres outbox | Low volume, transactional guarantee needed |
| Alert firing → On-call routing | Postgres outbox | Transactional, durable |
| Feature flag changes | Postgres outbox | Transactional |
| Any cross-module event | Postgres outbox | Transactional, low volume |

The rule: NATS is for external ingest pipelines where volume is high and eventual consistency is acceptable. Postgres outbox is for internal module events where transactional consistency is required.

---

## JetStream Stream Definitions

tennetctl creates and manages its own JetStream streams at startup. Operators do not configure NATS subjects manually. The stream definitions live in `01_core/nats_client.py`:

| Stream name | Subjects | Retention | Max age | Purpose |
|-------------|----------|-----------|---------|---------|
| `SC_METRICS` | `monitoring.metrics.>` | Limits | 1 hour | Metric samples buffer |
| `SC_TRACES` | `monitoring.traces.>` | Limits | 1 hour | Distributed trace spans |
| `SC_LOGS` | `monitoring.logs.>` | Limits | 1 hour | Structured log entries |
| `SC_EVENTS` | `ops.events.>` | Limits | 1 hour | Product ops event ingest |

Retention is `Limits` (not `WorkQueue`) so that consumer failures can replay from the stream. Max age of 1 hour means data is available for replay/retry but does not grow unboundedly — Postgres is the durable store.

Consumer workers use **durable pull consumers** with explicit acknowledgement. A message is only removed from the stream after the consumer writes it to Postgres and ACKs it. A consumer crash causes JetStream to redeliver unACKed messages after the `ack_wait` timeout (default: 30 seconds).

---

## Subject Naming

```
monitoring.metrics.{org_id}        # Metric samples from a specific org
monitoring.traces.{org_id}         # Trace spans from a specific org
monitoring.logs.{org_id}           # Log entries from a specific org
ops.events.{org_id}                # Product analytics events from a specific org
```

The `org_id` suffix allows per-tenant consumer configuration in the future (e.g., different retention per org tier) without changing the stream structure.

---

## Consumer Worker Pattern

Each stream has one consumer worker implemented as a long-running asyncio task in the FastAPI lifespan:

```python
async def metrics_consumer_worker(js: nats.js.JetStreamContext):
    """
    Consume metric samples from SC_METRICS stream and write to Postgres.

    Runs as a background asyncio task. Fetches messages in batches of 100,
    writes to Postgres in a single transaction, then ACKs all messages.
    On any error, NACKs messages for redelivery.
    """
    consumer = await js.pull_subscribe("monitoring.metrics.>", durable="metrics-writer")
    while running:
        try:
            messages = await consumer.fetch(100, timeout=1.0)
            async with platform_transaction(pool) as conn:
                await metrics_repository.bulk_insert(conn, [parse(m.data) for m in messages])
            for m in messages:
                await m.ack()
        except nats.errors.TimeoutError:
            continue  # no messages, loop again
        except Exception as e:
            logger.error("metrics_consumer_error", error=str(e))
            for m in messages:
                await m.nak(delay=5)  # redeliver after 5s
```

Worker health is tracked in `01_core/worker_registry.py` and exposed at `GET /health/workers`.
