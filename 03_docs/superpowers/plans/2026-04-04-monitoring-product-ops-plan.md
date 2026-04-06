# Monitoring & Product Ops — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete built-in observability and product analytics system — metrics/traces/logs/alerting (`04_monitoring`) and PostHog-style product analytics (`12_product_ops`) — using NATS JetStream for ingest and Postgres for storage, replacing external tools entirely.

**Architecture:** Two independent FastAPI modules under `01_backend/02_features/`. Each uses a NATS JetStream worker (pull consumer, batch processing, explicit ACK after Postgres commit) for high-volume ingest and standard 5-file sub-feature routes for queries. Frontend gets two new nav sections: `/monitoring` and `/product-ops`.

**Tech Stack:** Python/FastAPI, asyncpg, NATS JetStream (nats-py), Next.js 14 App Router, Postgres 16, EAV table naming (`fct_*`, `dim_*`, `lnk_*`). Reference: `99_forref/tennetctl-v2/01_backend/02_features/04_monitoring/` and `12_product_ops/`.

---

## Critical Patterns (read before every task)

### Import pattern (numeric dirs require importlib)
```python
import importlib
_db = importlib.import_module("01_backend.01_core.database")
_resp = importlib.import_module("01_backend.01_core.response")
_svc = importlib.import_module("01_backend.02_features.04_monitoring.01_ingest.service")
```

### Route connection pattern
```python
pool = await _db.get_pool()
async with pool.acquire() as conn:
    result = await _svc.some_fn(conn, ...)
return _resp.ok(result)
```

### Response envelope
```python
_resp.ok(data)           # {"ok": true, "data": ...}
_resp.error("CODE", "message")  # {"ok": false, "error": {"code": ..., "message": ...}}
```

### NATS worker base class pattern
```python
class MyWorker(ConsumerWorker):
    STREAM = "MONITORING"
    SUBJECT = "monitoring.metrics"
    DURABLE = "monitoring-metrics-worker"
    MAX_DELIVER = 5
    ACK_WAIT = 30

    async def process_batch(self, msgs: list[Msg]) -> None:
        rows = [self._parse(m) for m in msgs]
        async with self.pool.acquire() as conn:
            await repo.bulk_insert(conn, rows)
        for m in msgs: await m.ack()  # ACK only after commit
```

### Migration naming
`YYYYMMDD_description.sql` — place in `01_backend/01_sql_migrations/`

### Test runner commands
```bash
cd tennetctl && .venv/bin/python -m pytest 01_backend/tests/ -v
```

---

## PHASE 1: `04_monitoring` (7 sub-features)

### Task 1: `04_monitoring/01_ingest` — NATS Metrics/Traces/Logs Worker

**Ref:** `99_forref/tennetctl-v2/01_backend/02_features/04_monitoring/01_ingest/`

**Files:**
- Create: `01_backend/02_features/04_monitoring/__init__.py`
- Create: `01_backend/02_features/04_monitoring/01_ingest/__init__.py`
- Create: `01_backend/02_features/04_monitoring/01_ingest/schemas.py`
- Create: `01_backend/02_features/04_monitoring/01_ingest/repository.py`
- Create: `01_backend/02_features/04_monitoring/01_ingest/service.py`
- Create: `01_backend/02_features/04_monitoring/01_ingest/worker.py`
- Create: `01_backend/02_features/04_monitoring/01_ingest/routes.py`
- Create: `01_backend/01_sql_migrations/20260404_monitoring_ingest.sql`
- Create: `01_backend/tests/04_monitoring/test_01_ingest.py`

- [ ] **Step 1: Write the migration**

```sql
-- 20260404_monitoring_ingest.sql
CREATE TABLE IF NOT EXISTS fct_metric_sample (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    metric_name  TEXT NOT NULL,
    labels       JSONB NOT NULL DEFAULT '{}',
    value        DOUBLE PRECISION NOT NULL,
    ts           TIMESTAMPTZ NOT NULL,
    ingested_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_metric_sample_ws_name_ts ON fct_metric_sample (workspace_id, metric_name, ts DESC);
CREATE INDEX idx_metric_sample_labels ON fct_metric_sample USING GIN (labels);

CREATE TABLE IF NOT EXISTS fct_trace_span (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    trace_id     TEXT NOT NULL,
    span_id      TEXT NOT NULL,
    parent_span_id TEXT,
    name         TEXT NOT NULL,
    start_ts     TIMESTAMPTZ NOT NULL,
    end_ts       TIMESTAMPTZ NOT NULL,
    duration_ms  INTEGER GENERATED ALWAYS AS (EXTRACT(EPOCH FROM (end_ts - start_ts)) * 1000)::INTEGER STORED,
    attributes   JSONB NOT NULL DEFAULT '{}',
    status       TEXT NOT NULL DEFAULT 'ok',
    ingested_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_trace_span_ws_trace ON fct_trace_span (workspace_id, trace_id);
CREATE INDEX idx_trace_span_ws_ts ON fct_trace_span (workspace_id, start_ts DESC);

CREATE TABLE IF NOT EXISTS fct_log_entry (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    level        TEXT NOT NULL DEFAULT 'info',
    body         TEXT NOT NULL,
    resource     JSONB NOT NULL DEFAULT '{}',
    attributes   JSONB NOT NULL DEFAULT '{}',
    ts           TIMESTAMPTZ NOT NULL,
    ingested_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_log_entry_ws_ts ON fct_log_entry (workspace_id, ts DESC);
CREATE INDEX idx_log_entry_level ON fct_log_entry (workspace_id, level, ts DESC);
```

Run: `psql $DATABASE_URL < 01_backend/01_sql_migrations/20260404_monitoring_ingest.sql`

- [ ] **Step 2: Write the failing test**

```python
# 01_backend/tests/04_monitoring/test_01_ingest.py
import pytest
import importlib

@pytest.fixture
async def pool(pg_pool):  # pg_pool from conftest
    return pg_pool

async def test_bulk_insert_metrics(pool):
    repo = importlib.import_module("01_backend.02_features.04_monitoring.01_ingest.repository")
    rows = [
        {"workspace_id": "00000000-0000-0000-0000-000000000001",
         "metric_name": "cpu_usage", "labels": {"host": "web-01"},
         "value": 72.5, "ts": "2026-04-04T00:00:00Z"}
    ]
    async with pool.acquire() as conn:
        count = await repo.bulk_insert_metrics(conn, rows)
    assert count == 1

async def test_bulk_insert_spans(pool):
    repo = importlib.import_module("01_backend.02_features.04_monitoring.01_ingest.repository")
    rows = [
        {"workspace_id": "00000000-0000-0000-0000-000000000001",
         "trace_id": "abc123", "span_id": "span001", "parent_span_id": None,
         "name": "GET /api/users", "start_ts": "2026-04-04T00:00:00Z",
         "end_ts": "2026-04-04T00:00:00.050Z", "attributes": {}, "status": "ok"}
    ]
    async with pool.acquire() as conn:
        count = await repo.bulk_insert_spans(conn, rows)
    assert count == 1

async def test_bulk_insert_logs(pool):
    repo = importlib.import_module("01_backend.02_features.04_monitoring.01_ingest.repository")
    rows = [
        {"workspace_id": "00000000-0000-0000-0000-000000000001",
         "level": "error", "body": "connection refused",
         "resource": {"service": "api"}, "attributes": {}, "ts": "2026-04-04T00:00:00Z"}
    ]
    async with pool.acquire() as conn:
        count = await repo.bulk_insert_logs(conn, rows)
    assert count == 1
```

Run: `cd tennetctl && .venv/bin/python -m pytest 01_backend/tests/04_monitoring/test_01_ingest.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Write schemas.py**

```python
# 01_backend/02_features/04_monitoring/01_ingest/schemas.py
from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Any

class MetricSample(BaseModel):
    workspace_id: str
    metric_name: str
    labels: dict[str, Any] = {}
    value: float
    ts: datetime

class TraceSpan(BaseModel):
    workspace_id: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    name: str
    start_ts: datetime
    end_ts: datetime
    attributes: dict[str, Any] = {}
    status: str = "ok"

class LogEntry(BaseModel):
    workspace_id: str
    level: str = "info"
    body: str
    resource: dict[str, Any] = {}
    attributes: dict[str, Any] = {}
    ts: datetime

class IngestMetricsRequest(BaseModel):
    samples: list[MetricSample]

class IngestTracesRequest(BaseModel):
    spans: list[TraceSpan]

class IngestLogsRequest(BaseModel):
    entries: list[LogEntry]
```

- [ ] **Step 4: Write repository.py**

```python
# 01_backend/02_features/04_monitoring/01_ingest/repository.py
import json

async def bulk_insert_metrics(conn, rows: list[dict]) -> int:
    await conn.executemany(
        """INSERT INTO fct_metric_sample
           (workspace_id, metric_name, labels, value, ts)
           VALUES ($1, $2, $3::jsonb, $4, $5)""",
        [(r["workspace_id"], r["metric_name"], json.dumps(r["labels"]),
          r["value"], r["ts"]) for r in rows]
    )
    return len(rows)

async def bulk_insert_spans(conn, rows: list[dict]) -> int:
    await conn.executemany(
        """INSERT INTO fct_trace_span
           (workspace_id, trace_id, span_id, parent_span_id, name, start_ts, end_ts, attributes, status)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9)""",
        [(r["workspace_id"], r["trace_id"], r["span_id"], r.get("parent_span_id"),
          r["name"], r["start_ts"], r["end_ts"], json.dumps(r.get("attributes", {})),
          r.get("status", "ok")) for r in rows]
    )
    return len(rows)

async def bulk_insert_logs(conn, rows: list[dict]) -> int:
    await conn.executemany(
        """INSERT INTO fct_log_entry
           (workspace_id, level, body, resource, attributes, ts)
           VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6)""",
        [(r["workspace_id"], r.get("level", "info"), r["body"],
          json.dumps(r.get("resource", {})), json.dumps(r.get("attributes", {})),
          r["ts"]) for r in rows]
    )
    return len(rows)
```

- [ ] **Step 5: Write service.py**

```python
# 01_backend/02_features/04_monitoring/01_ingest/service.py
import importlib
_repo = importlib.import_module("01_backend.02_features.04_monitoring.01_ingest.repository")

async def ingest_metrics(conn, samples: list[dict]) -> dict:
    count = await _repo.bulk_insert_metrics(conn, samples)
    return {"ingested": count}

async def ingest_spans(conn, spans: list[dict]) -> dict:
    count = await _repo.bulk_insert_spans(conn, spans)
    return {"ingested": count}

async def ingest_logs(conn, entries: list[dict]) -> dict:
    count = await _repo.bulk_insert_logs(conn, entries)
    return {"ingested": count}
```

- [ ] **Step 6: Write routes.py**

```python
# 01_backend/02_features/04_monitoring/01_ingest/routes.py
import importlib
from fastapi import APIRouter

_db   = importlib.import_module("01_backend.01_core.database")
_resp = importlib.import_module("01_backend.01_core.response")
_svc  = importlib.import_module("01_backend.02_features.04_monitoring.01_ingest.service")
_sch  = importlib.import_module("01_backend.02_features.04_monitoring.01_ingest.schemas")

router = APIRouter(prefix="/v1/monitoring", tags=["monitoring-ingest"])

@router.post("/ingest/metrics")
async def ingest_metrics(body: _sch.IngestMetricsRequest):
    pool = await _db.get_pool()
    async with pool.acquire() as conn:
        result = await _svc.ingest_metrics(conn, [s.model_dump() for s in body.samples])
    return _resp.ok(result)

@router.post("/ingest/traces")
async def ingest_traces(body: _sch.IngestTracesRequest):
    pool = await _db.get_pool()
    async with pool.acquire() as conn:
        result = await _svc.ingest_spans(conn, [s.model_dump() for s in body.spans])
    return _resp.ok(result)

@router.post("/ingest/logs")
async def ingest_logs(body: _sch.IngestLogsRequest):
    pool = await _db.get_pool()
    async with pool.acquire() as conn:
        result = await _svc.ingest_logs(conn, [e.model_dump() for e in body.entries])
    return _resp.ok(result)
```

- [ ] **Step 7: Write worker.py (NATS JetStream consumer)**

```python
# 01_backend/02_features/04_monitoring/01_ingest/worker.py
import asyncio, json, importlib, logging
import nats
from nats.js.api import ConsumerConfig, AckPolicy, DeliverPolicy

logger = logging.getLogger(__name__)
_repo = importlib.import_module("01_backend.02_features.04_monitoring.01_ingest.repository")
_db   = importlib.import_module("01_backend.01_core.database")

BATCH_SIZE = 100

async def _ensure_stream(js):
    try:
        await js.find_stream("MONITORING")
    except Exception:
        await js.add_stream(name="MONITORING",
                            subjects=["monitoring.metrics", "monitoring.traces", "monitoring.logs"])

async def run_monitoring_worker():
    pool = await _db.get_pool()
    nc = await nats.connect(servers=["nats://localhost:4222"])
    js = nc.jetstream()
    await _ensure_stream(js)

    for subject, table_fn in [
        ("monitoring.metrics", _repo.bulk_insert_metrics),
        ("monitoring.traces",  _repo.bulk_insert_spans),
        ("monitoring.logs",    _repo.bulk_insert_logs),
    ]:
        durable = subject.replace(".", "-") + "-worker"
        sub = await js.pull_subscribe(subject, durable=durable,
            config=ConsumerConfig(ack_policy=AckPolicy.EXPLICIT,
                                  max_deliver=5, ack_wait=30))
        asyncio.create_task(_consume_loop(sub, pool, table_fn))

    logger.info("Monitoring NATS workers started")

async def _consume_loop(sub, pool, insert_fn):
    while True:
        try:
            msgs = await sub.fetch(BATCH_SIZE, timeout=5)
            if not msgs:
                continue
            rows = [json.loads(m.data) for m in msgs]
            async with pool.acquire() as conn:
                await insert_fn(conn, rows)
            for m in msgs:
                await m.ack()
        except Exception as e:
            logger.error(f"Worker error: {e}")
            await asyncio.sleep(1)
```

- [ ] **Step 8: Register router in main.py**

In `01_backend/main.py`, add inside the `monitoring` feature block:
```python
_mon_ingest = importlib.import_module("01_backend.02_features.04_monitoring.01_ingest.routes")
app.include_router(_mon_ingest.router)
```

- [ ] **Step 9: Run tests**

```bash
cd tennetctl && .venv/bin/python -m pytest 01_backend/tests/04_monitoring/test_01_ingest.py -v
```
Expected: 3 tests PASS

- [ ] **Step 10: Commit**

```bash
git add 01_backend/02_features/04_monitoring/ 01_backend/01_sql_migrations/20260404_monitoring_ingest.sql 01_backend/tests/04_monitoring/
git commit -m "feat(monitoring): 04_monitoring/01_ingest — NATS worker + metrics/traces/logs ingest routes"
```

---

### Task 2: `04_monitoring/02_query` — Query API

**Ref:** `99_forref/tennetctl-v2/01_backend/02_features/04_monitoring/02_query/`

**Files:**
- Create: `01_backend/02_features/04_monitoring/02_query/__init__.py`
- Create: `01_backend/02_features/04_monitoring/02_query/schemas.py`
- Create: `01_backend/02_features/04_monitoring/02_query/repository.py`
- Create: `01_backend/02_features/04_monitoring/02_query/service.py`
- Create: `01_backend/02_features/04_monitoring/02_query/routes.py`
- Create: `01_backend/tests/04_monitoring/test_02_query.py`

- [ ] **Step 1: Write failing test**

```python
# 01_backend/tests/04_monitoring/test_02_query.py
import pytest, importlib
from datetime import datetime, timezone

async def _seed_metric(conn):
    repo = importlib.import_module("01_backend.02_features.04_monitoring.01_ingest.repository")
    await repo.bulk_insert_metrics(conn, [{
        "workspace_id": "00000000-0000-0000-0000-000000000001",
        "metric_name": "cpu_usage", "labels": {"host": "web-01"},
        "value": 72.5, "ts": datetime.now(timezone.utc)
    }])

async def test_query_metrics_returns_results(pool):
    async with pool.acquire() as conn:
        await _seed_metric(conn)
        repo = importlib.import_module("01_backend.02_features.04_monitoring.02_query.repository")
        rows = await repo.query_metrics(conn,
            workspace_id="00000000-0000-0000-0000-000000000001",
            metric_name="cpu_usage", start=None, end=None, labels={}, limit=50)
    assert len(rows) >= 1
    assert rows[0]["metric_name"] == "cpu_usage"

async def test_query_logs_returns_results(pool):
    ingest = importlib.import_module("01_backend.02_features.04_monitoring.01_ingest.repository")
    query  = importlib.import_module("01_backend.02_features.04_monitoring.02_query.repository")
    async with pool.acquire() as conn:
        await ingest.bulk_insert_logs(conn, [{
            "workspace_id": "00000000-0000-0000-0000-000000000001",
            "level": "error", "body": "db timeout",
            "resource": {}, "attributes": {}, "ts": datetime.now(timezone.utc)
        }])
        rows = await query.query_logs(conn,
            workspace_id="00000000-0000-0000-0000-000000000001",
            level="error", search=None, start=None, end=None, limit=50)
    assert len(rows) >= 1
```

Run: `cd tennetctl && .venv/bin/python -m pytest 01_backend/tests/04_monitoring/test_02_query.py -v`
Expected: FAIL

- [ ] **Step 2: Write repository.py**

```python
# 01_backend/02_features/04_monitoring/02_query/repository.py
from datetime import datetime

async def query_metrics(conn, workspace_id: str, metric_name: str | None,
                        start: datetime | None, end: datetime | None,
                        labels: dict, limit: int = 500) -> list[dict]:
    where = ["workspace_id = $1"]
    params: list = [workspace_id]
    i = 2
    if metric_name:
        where.append(f"metric_name = ${i}"); params.append(metric_name); i += 1
    if start:
        where.append(f"ts >= ${i}"); params.append(start); i += 1
    if end:
        where.append(f"ts <= ${i}"); params.append(end); i += 1
    for k, v in labels.items():
        where.append(f"labels->>'${i}' = ${i+1}"); params.extend([k, v]); i += 2
    sql = f"""SELECT id, metric_name, labels, value, ts
              FROM fct_metric_sample
              WHERE {' AND '.join(where)}
              ORDER BY ts DESC LIMIT {limit}"""
    rows = await conn.fetch(sql, *params)
    return [dict(r) for r in rows]

async def query_traces(conn, workspace_id: str, trace_id: str | None,
                       start: datetime | None, end: datetime | None, limit: int = 200) -> list[dict]:
    where = ["workspace_id = $1"]
    params: list = [workspace_id]
    i = 2
    if trace_id:
        where.append(f"trace_id = ${i}"); params.append(trace_id); i += 1
    if start:
        where.append(f"start_ts >= ${i}"); params.append(start); i += 1
    if end:
        where.append(f"start_ts <= ${i}"); params.append(end); i += 1
    sql = f"""SELECT id, trace_id, span_id, parent_span_id, name,
                     start_ts, end_ts, duration_ms, attributes, status
              FROM fct_trace_span
              WHERE {' AND '.join(where)}
              ORDER BY start_ts DESC LIMIT {limit}"""
    rows = await conn.fetch(sql, *params)
    return [dict(r) for r in rows]

async def query_logs(conn, workspace_id: str, level: str | None, search: str | None,
                     start: datetime | None, end: datetime | None, limit: int = 500) -> list[dict]:
    where = ["workspace_id = $1"]
    params: list = [workspace_id]
    i = 2
    if level:
        where.append(f"level = ${i}"); params.append(level); i += 1
    if search:
        where.append(f"body ILIKE ${i}"); params.append(f"%{search}%"); i += 1
    if start:
        where.append(f"ts >= ${i}"); params.append(start); i += 1
    if end:
        where.append(f"ts <= ${i}"); params.append(end); i += 1
    sql = f"""SELECT id, level, body, resource, attributes, ts
              FROM fct_log_entry
              WHERE {' AND '.join(where)}
              ORDER BY ts DESC LIMIT {limit}"""
    rows = await conn.fetch(sql, *params)
    return [dict(r) for r in rows]
```

- [ ] **Step 3: Write schemas.py**

```python
# 01_backend/02_features/04_monitoring/02_query/schemas.py
from pydantic import BaseModel
from datetime import datetime
from typing import Any

class MetricQueryRequest(BaseModel):
    workspace_id: str
    metric_name: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    labels: dict[str, str] = {}
    limit: int = 500

class TraceQueryRequest(BaseModel):
    workspace_id: str
    trace_id: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    limit: int = 200

class LogQueryRequest(BaseModel):
    workspace_id: str
    level: str | None = None
    search: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    limit: int = 500
```

- [ ] **Step 4: Write service.py**

```python
# 01_backend/02_features/04_monitoring/02_query/service.py
import importlib
_repo = importlib.import_module("01_backend.02_features.04_monitoring.02_query.repository")

async def query_metrics(conn, req: dict) -> list[dict]:
    return await _repo.query_metrics(conn, **req)

async def query_traces(conn, req: dict) -> list[dict]:
    return await _repo.query_traces(conn, **req)

async def query_logs(conn, req: dict) -> list[dict]:
    return await _repo.query_logs(conn, **req)
```

- [ ] **Step 5: Write routes.py**

```python
# 01_backend/02_features/04_monitoring/02_query/routes.py
import importlib
from fastapi import APIRouter

_db   = importlib.import_module("01_backend.01_core.database")
_resp = importlib.import_module("01_backend.01_core.response")
_svc  = importlib.import_module("01_backend.02_features.04_monitoring.02_query.service")
_sch  = importlib.import_module("01_backend.02_features.04_monitoring.02_query.schemas")

router = APIRouter(prefix="/v1/monitoring", tags=["monitoring-query"])

@router.post("/query/metrics")
async def query_metrics(body: _sch.MetricQueryRequest):
    pool = await _db.get_pool()
    async with pool.acquire() as conn:
        result = await _svc.query_metrics(conn, body.model_dump())
    return _resp.ok(result)

@router.post("/query/traces")
async def query_traces(body: _sch.TraceQueryRequest):
    pool = await _db.get_pool()
    async with pool.acquire() as conn:
        result = await _svc.query_traces(conn, body.model_dump())
    return _resp.ok(result)

@router.post("/query/logs")
async def query_logs(body: _sch.LogQueryRequest):
    pool = await _db.get_pool()
    async with pool.acquire() as conn:
        result = await _svc.query_logs(conn, body.model_dump())
    return _resp.ok(result)
```

- [ ] **Step 6: Register router in main.py, run tests, commit**

```bash
# Register:
# _mon_query = importlib.import_module("01_backend.02_features.04_monitoring.02_query.routes")
# app.include_router(_mon_query.router)

cd tennetctl && .venv/bin/python -m pytest 01_backend/tests/04_monitoring/test_02_query.py -v
git add 01_backend/02_features/04_monitoring/02_query/ 01_backend/tests/04_monitoring/test_02_query.py
git commit -m "feat(monitoring): 04_monitoring/02_query — metrics/traces/logs query API"
```

---

### Task 3: `04_monitoring/03_dashboards` — Dashboard + Panel Executor

**Ref:** `99_forref/tennetctl-v2/01_backend/02_features/04_monitoring/03_dashboards/`

**Files:**
- Create: `01_backend/02_features/04_monitoring/03_dashboards/__init__.py`
- Create: `01_backend/02_features/04_monitoring/03_dashboards/schemas.py`
- Create: `01_backend/02_features/04_monitoring/03_dashboards/repository.py`
- Create: `01_backend/02_features/04_monitoring/03_dashboards/service.py`
- Create: `01_backend/02_features/04_monitoring/03_dashboards/panel_executor.py`
- Create: `01_backend/02_features/04_monitoring/03_dashboards/routes.py`
- Create: `01_backend/01_sql_migrations/20260404_monitoring_dashboards.sql`
- Create: `01_backend/tests/04_monitoring/test_03_dashboards.py`

- [ ] **Step 1: Write migration**

```sql
-- 20260404_monitoring_dashboards.sql
CREATE TABLE IF NOT EXISTS dim_dashboard (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    title        TEXT NOT NULL,
    description  TEXT,
    is_deleted   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dim_dashboard_panel (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dashboard_id UUID NOT NULL REFERENCES dim_dashboard(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    type         TEXT NOT NULL DEFAULT 'timeseries',
    query        JSONB NOT NULL DEFAULT '{}',
    position     JSONB NOT NULL DEFAULT '{"x":0,"y":0,"w":6,"h":4}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

- [ ] **Step 2: Write failing test**

```python
# 01_backend/tests/04_monitoring/test_03_dashboards.py
import pytest, importlib

async def test_create_and_get_dashboard(pool):
    repo = importlib.import_module("01_backend.02_features.04_monitoring.03_dashboards.repository")
    async with pool.acquire() as conn:
        d = await repo.create_dashboard(conn, {
            "workspace_id": "00000000-0000-0000-0000-000000000001",
            "title": "Infra Overview", "description": None
        })
        assert d["title"] == "Infra Overview"
        fetched = await repo.get_dashboard(conn, str(d["id"]))
    assert fetched["id"] == d["id"]

async def test_add_panel_to_dashboard(pool):
    repo = importlib.import_module("01_backend.02_features.04_monitoring.03_dashboards.repository")
    async with pool.acquire() as conn:
        d = await repo.create_dashboard(conn, {
            "workspace_id": "00000000-0000-0000-0000-000000000001",
            "title": "Test", "description": None
        })
        p = await repo.add_panel(conn, {
            "dashboard_id": str(d["id"]), "title": "CPU",
            "type": "timeseries",
            "query": {"type": "metric", "metric_name": "cpu_usage"},
            "position": {"x": 0, "y": 0, "w": 6, "h": 4}
        })
    assert p["title"] == "CPU"
```

Run: `cd tennetctl && .venv/bin/python -m pytest 01_backend/tests/04_monitoring/test_03_dashboards.py -v`
Expected: FAIL

- [ ] **Step 3: Write schemas.py, repository.py, service.py, panel_executor.py, routes.py**

Follow the exact same 5-file pattern as Task 1/2. Reference `99_forref/tennetctl-v2/01_backend/02_features/04_monitoring/03_dashboards/` for the full implementation. Key items:

`panel_executor.py` — routes panel `query` JSONB to the right query function:
```python
async def execute_panel(conn, panel: dict) -> dict:
    q = panel.get("query", {})
    if q.get("type") == "metric":
        repo = importlib.import_module("01_backend.02_features.04_monitoring.02_query.repository")
        return await repo.query_metrics(conn, workspace_id=panel["workspace_id"],
                                        metric_name=q.get("metric_name"), ...)
    elif q.get("type") == "log":
        ...
    elif q.get("type") == "trace":
        ...
```

Routes: `GET/POST /v1/monitoring/dashboards`, `GET/PATCH/DELETE /v1/monitoring/dashboards/{id}`, `POST /v1/monitoring/dashboards/{id}/panels`, `GET /v1/monitoring/dashboards/{id}/data` (executes all panels).

- [ ] **Step 4: Run tests, register router, commit**

```bash
cd tennetctl && .venv/bin/python -m pytest 01_backend/tests/04_monitoring/test_03_dashboards.py -v
git add 01_backend/02_features/04_monitoring/03_dashboards/ 01_backend/01_sql_migrations/20260404_monitoring_dashboards.sql 01_backend/tests/04_monitoring/test_03_dashboards.py
git commit -m "feat(monitoring): 04_monitoring/03_dashboards — dashboard CRUD + panel executor"
```

---

### Task 4: `04_monitoring/04_alerting` — Full Alert Engine

**Ref:** `99_forref/tennetctl-v2/01_backend/02_features/04_monitoring/04_alerting/`

**Files:**
- Create: `01_backend/02_features/04_monitoring/04_alerting/__init__.py`
- Create: `01_backend/02_features/04_monitoring/04_alerting/schemas.py`
- Create: `01_backend/02_features/04_monitoring/04_alerting/repository.py`
- Create: `01_backend/02_features/04_monitoring/04_alerting/service.py`
- Create: `01_backend/02_features/04_monitoring/04_alerting/routes.py`
- Create: `01_backend/02_features/04_monitoring/04_alerting/engine/__init__.py`
- Create: `01_backend/02_features/04_monitoring/04_alerting/engine/evaluator.py`
- Create: `01_backend/02_features/04_monitoring/04_alerting/engine/router.py`
- Create: `01_backend/02_features/04_monitoring/04_alerting/engine/fingerprint.py`
- Create: `01_backend/02_features/04_monitoring/04_alerting/engine/silencer.py`
- Create: `01_backend/02_features/04_monitoring/04_alerting/engine/inhibitor.py`
- Create: `01_backend/02_features/04_monitoring/04_alerting/engine/matchers.py`
- Create: `01_backend/02_features/04_monitoring/04_alerting/engine/conditions.py`
- Create: `01_backend/01_sql_migrations/20260404_monitoring_alerting.sql`
- Create: `01_backend/tests/04_monitoring/test_04_alerting.py`

- [ ] **Step 1: Write migration**

```sql
-- 20260404_monitoring_alerting.sql
CREATE TABLE IF NOT EXISTS dim_alert_receiver (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    name         TEXT NOT NULL,
    type         TEXT NOT NULL,  -- 'webhook' | 'email' | 'slack'
    config       JSONB NOT NULL DEFAULT '{}',
    is_deleted   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fct_alert_rule (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    name         TEXT NOT NULL,
    expr         JSONB NOT NULL,  -- condition expression
    for_duration INTERVAL NOT NULL DEFAULT '0',
    labels       JSONB NOT NULL DEFAULT '{}',
    annotations  JSONB NOT NULL DEFAULT '{}',
    receiver_id  UUID REFERENCES dim_alert_receiver(id),
    state        TEXT NOT NULL DEFAULT 'inactive',  -- inactive|pending|firing|resolved
    is_deleted   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fct_alert_instance (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id      UUID NOT NULL REFERENCES fct_alert_rule(id),
    fingerprint  TEXT NOT NULL,
    labels       JSONB NOT NULL DEFAULT '{}',
    annotations  JSONB NOT NULL DEFAULT '{}',
    state        TEXT NOT NULL DEFAULT 'pending',
    fired_at     TIMESTAMPTZ,
    resolved_at  TIMESTAMPTZ,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_alert_instance_fp ON fct_alert_instance (rule_id, fingerprint)
    WHERE state != 'resolved';

CREATE TABLE IF NOT EXISTS fct_alert_silence (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    matchers     JSONB NOT NULL,
    starts_at    TIMESTAMPTZ NOT NULL,
    ends_at      TIMESTAMPTZ NOT NULL,
    created_by   UUID,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fct_alert_inhibition (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id     UUID NOT NULL,
    source_matchers  JSONB NOT NULL,
    target_matchers  JSONB NOT NULL,
    equal            JSONB NOT NULL DEFAULT '[]',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

- [ ] **Step 2: Write failing test**

```python
# 01_backend/tests/04_monitoring/test_04_alerting.py
import pytest, importlib

async def test_matchers_equality():
    matchers = importlib.import_module("01_backend.02_features.04_monitoring.04_alerting.engine.matchers")
    result = matchers.matches({"env": "prod", "host": "web-01"},
                              [{"name": "env", "op": "=", "value": "prod"}])
    assert result is True

async def test_matchers_not_equal():
    matchers = importlib.import_module("01_backend.02_features.04_monitoring.04_alerting.engine.matchers")
    result = matchers.matches({"env": "staging"},
                              [{"name": "env", "op": "=", "value": "prod"}])
    assert result is False

async def test_fingerprint_stable():
    fingerprint = importlib.import_module("01_backend.02_features.04_monitoring.04_alerting.engine.fingerprint")
    labels = {"alertname": "HighCPU", "host": "web-01"}
    fp1 = fingerprint.compute(labels)
    fp2 = fingerprint.compute(labels)
    assert fp1 == fp2

async def test_fingerprint_different_labels():
    fingerprint = importlib.import_module("01_backend.02_features.04_monitoring.04_alerting.engine.fingerprint")
    fp1 = fingerprint.compute({"host": "web-01"})
    fp2 = fingerprint.compute({"host": "web-02"})
    assert fp1 != fp2

async def test_create_alert_rule(pool):
    repo = importlib.import_module("01_backend.02_features.04_monitoring.04_alerting.repository")
    async with pool.acquire() as conn:
        rule = await repo.create_rule(conn, {
            "workspace_id": "00000000-0000-0000-0000-000000000001",
            "name": "High CPU", "expr": {"metric": "cpu_usage", "op": ">", "threshold": 90},
            "for_duration": "5 minutes", "labels": {}, "annotations": {}, "receiver_id": None
        })
    assert rule["name"] == "High CPU"
    assert rule["state"] == "inactive"
```

Run: `cd tennetctl && .venv/bin/python -m pytest 01_backend/tests/04_monitoring/test_04_alerting.py -v`
Expected: FAIL

- [ ] **Step 3: Write engine/matchers.py**

```python
# 01_backend/02_features/04_monitoring/04_alerting/engine/matchers.py
import re

def matches(labels: dict, matchers: list[dict]) -> bool:
    """All matchers must match (AND logic)."""
    for m in matchers:
        name, op, value = m["name"], m["op"], m["value"]
        label_val = labels.get(name, "")
        if op == "=":
            if label_val != value: return False
        elif op == "!=":
            if label_val == value: return False
        elif op == "=~":
            if not re.fullmatch(value, label_val): return False
        elif op == "!~":
            if re.fullmatch(value, label_val): return False
    return True
```

- [ ] **Step 4: Write engine/fingerprint.py**

```python
# 01_backend/02_features/04_monitoring/04_alerting/engine/fingerprint.py
import hashlib, json

def compute(labels: dict) -> str:
    """Stable fingerprint from sorted label key-value pairs."""
    canonical = json.dumps(dict(sorted(labels.items())), separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
```

- [ ] **Step 5: Write engine/conditions.py**

```python
# 01_backend/02_features/04_monitoring/04_alerting/engine/conditions.py

def evaluate(expr: dict, current_value: float | None) -> bool:
    """Evaluate a threshold condition expression.
    expr: {"metric": "cpu_usage", "op": ">", "threshold": 90.0}
    """
    if current_value is None:
        return False
    op = expr.get("op", ">")
    threshold = float(expr.get("threshold", 0))
    return {
        ">":  lambda v: v > threshold,
        ">=": lambda v: v >= threshold,
        "<":  lambda v: v < threshold,
        "<=": lambda v: v <= threshold,
        "==": lambda v: v == threshold,
    }.get(op, lambda v: False)(current_value)
```

- [ ] **Step 6: Write engine/silencer.py and engine/inhibitor.py**

```python
# engine/silencer.py
from datetime import datetime, timezone
import importlib
_matchers = importlib.import_module("01_backend.02_features.04_monitoring.04_alerting.engine.matchers")

def is_silenced(labels: dict, silences: list[dict]) -> bool:
    now = datetime.now(timezone.utc)
    for s in silences:
        if s["starts_at"] <= now <= s["ends_at"]:
            if _matchers.matches(labels, s["matchers"]):
                return True
    return False

# engine/inhibitor.py
import importlib
_matchers = importlib.import_module("01_backend.02_features.04_monitoring.04_alerting.engine.matchers")

def is_inhibited(target_labels: dict, source_labels: dict, inhibitions: list[dict]) -> bool:
    for inh in inhibitions:
        if (_matchers.matches(source_labels, inh["source_matchers"]) and
                _matchers.matches(target_labels, inh["target_matchers"])):
            equal_keys = inh.get("equal", [])
            if all(source_labels.get(k) == target_labels.get(k) for k in equal_keys):
                return True
    return False
```

- [ ] **Step 7: Write engine/router.py and engine/evaluator.py**

Port directly from `99_forref/tennetctl-v2/01_backend/02_features/04_monitoring/04_alerting/engine/`. Key signatures:

```python
# engine/router.py
async def route_alert(instance: dict, receiver: dict) -> None:
    """Send alert to receiver based on type (webhook/email/slack)."""
    ...

# engine/evaluator.py
async def evaluate_all_rules(pool) -> None:
    """Background loop: for each active rule, query latest metric value,
    evaluate condition, update fct_alert_instance state."""
    ...
```

- [ ] **Step 8: Write repository.py, service.py, routes.py**

Routes: `GET/POST /v1/monitoring/alert-rules`, `PATCH/DELETE /v1/monitoring/alert-rules/{id}`, `GET /v1/monitoring/alert-instances`, `POST/DELETE /v1/monitoring/silences`, `GET /v1/monitoring/silences`, `POST/DELETE /v1/monitoring/inhibitions`.

- [ ] **Step 9: Run tests, register router, commit**

```bash
cd tennetctl && .venv/bin/python -m pytest 01_backend/tests/04_monitoring/test_04_alerting.py -v
git add 01_backend/02_features/04_monitoring/04_alerting/ 01_backend/01_sql_migrations/20260404_monitoring_alerting.sql 01_backend/tests/04_monitoring/test_04_alerting.py
git commit -m "feat(monitoring): 04_monitoring/04_alerting — full engine (evaluator, router, fingerprint, silencer, inhibitor, matchers, conditions)"
```

---

### Task 5: `04_monitoring/05_alert_receivers` — Receiver CRUD

**Ref:** `99_forref/tennetctl-v2/01_backend/02_features/04_monitoring/04_alerting/` (receivers section)

Standard 5-file sub-feature. Routes: `GET/POST /v1/monitoring/receivers`, `GET/PATCH/DELETE /v1/monitoring/receivers/{id}`.

Table `dim_alert_receiver` already created in Task 4 migration.

Test: create receiver, fetch it, update config, delete it.

```bash
git commit -m "feat(monitoring): 04_monitoring/05_alert_receivers — receiver CRUD"
```

---

### Task 6: `04_monitoring/06_alert_rules` — Rule CRUD + Scheduler

Standard 5-file sub-feature. Table `fct_alert_rule` already created.

Add a background `asyncio.create_task` in lifespan that calls `engine/evaluator.py::evaluate_all_rules()` on a 60-second interval.

Test: create rule → verify state=inactive → trigger evaluation with seeded metric above threshold → verify state transitions to firing.

```bash
git commit -m "feat(monitoring): 04_monitoring/06_alert_rules — rule CRUD + evaluation scheduler"
```

---

### Task 7: `04_monitoring/07_slos` — SLO Definitions + Burn Rate

**Files:**
- Create: `01_backend/02_features/04_monitoring/07_slos/` (5 files)
- Create: `01_backend/01_sql_migrations/20260404_monitoring_slos.sql`

Migration:
```sql
CREATE TABLE IF NOT EXISTS fct_slo_definition (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  UUID NOT NULL,
    name          TEXT NOT NULL,
    target_ratio  DOUBLE PRECISION NOT NULL,  -- e.g. 0.999
    window_days   INTEGER NOT NULL DEFAULT 30,
    metric_expr   JSONB NOT NULL,
    is_deleted    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fct_slo_burn_event (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slo_id          UUID NOT NULL REFERENCES fct_slo_definition(id),
    burn_rate       DOUBLE PRECISION NOT NULL,
    error_budget_remaining DOUBLE PRECISION NOT NULL,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Service: `calculate_burn_rate(slo, metric_rows) -> float` — ratio of failures to total requests in window.

Routes: `GET/POST /v1/monitoring/slos`, `GET/PATCH/DELETE /v1/monitoring/slos/{id}`, `GET /v1/monitoring/slos/{id}/burn-rate`.

```bash
git commit -m "feat(monitoring): 04_monitoring/07_slos — SLO definitions + burn rate calculation"
```

---

## PHASE 2: `12_product_ops` (11 sub-features)

### Task 8: `12_product_ops/01_ingest` — NATS Event Worker

**Ref:** `99_forref/tennetctl-v2/01_backend/02_features/12_product_ops/01_ingest/`

**Files:**
- Create: `01_backend/02_features/12_product_ops/__init__.py`
- Create: `01_backend/02_features/12_product_ops/01_ingest/__init__.py`
- Create: `01_backend/02_features/12_product_ops/01_ingest/schemas.py`
- Create: `01_backend/02_features/12_product_ops/01_ingest/enricher.py`
- Create: `01_backend/02_features/12_product_ops/01_ingest/repository.py`
- Create: `01_backend/02_features/12_product_ops/01_ingest/service.py`
- Create: `01_backend/02_features/12_product_ops/01_ingest/worker.py`
- Create: `01_backend/02_features/12_product_ops/01_ingest/routes.py`
- Create: `01_backend/01_sql_migrations/20260404_product_ops_ingest.sql`
- Create: `01_backend/tests/12_product_ops/test_01_ingest.py`

- [ ] **Step 1: Write migration**

```sql
-- 20260404_product_ops_ingest.sql
CREATE TABLE IF NOT EXISTS dim_project (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    name         TEXT NOT NULL,
    api_key      TEXT NOT NULL UNIQUE DEFAULT gen_random_uuid()::TEXT,
    is_deleted   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fct_event (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID NOT NULL REFERENCES dim_project(id),
    event_name   TEXT NOT NULL,
    anonymous_id TEXT,
    user_id      TEXT,
    session_id   TEXT,
    event_time   TIMESTAMPTZ NOT NULL,
    properties   JSONB NOT NULL DEFAULT '{}',
    context      JSONB NOT NULL DEFAULT '{}',
    ingested_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_event_project_name_time ON fct_event (project_id, event_name, event_time DESC);
CREATE INDEX idx_event_project_user ON fct_event (project_id, user_id, event_time DESC);
CREATE INDEX idx_event_session ON fct_event (project_id, session_id);
```

- [ ] **Step 2: Write failing test**

```python
# 01_backend/tests/12_product_ops/test_01_ingest.py
import pytest, importlib
from datetime import datetime, timezone

async def _create_project(conn):
    repo = importlib.import_module("01_backend.02_features.12_product_ops.01_ingest.repository")
    return await repo.create_project(conn, {
        "workspace_id": "00000000-0000-0000-0000-000000000001",
        "name": "Test App"
    })

async def test_bulk_insert_events(pool):
    repo = importlib.import_module("01_backend.02_features.12_product_ops.01_ingest.repository")
    async with pool.acquire() as conn:
        proj = await _create_project(conn)
        rows = [{
            "project_id": str(proj["id"]), "event_name": "page_view",
            "anonymous_id": "anon-001", "user_id": None, "session_id": "sess-001",
            "event_time": datetime.now(timezone.utc), "properties": {"url": "/home"},
            "context": {"user_agent": "Mozilla/5.0"}
        }]
        count = await repo.bulk_insert_events(conn, rows)
    assert count == 1

async def test_enricher_adds_server_timestamp():
    enricher = importlib.import_module("01_backend.02_features.12_product_ops.01_ingest.enricher")
    raw = {"event_name": "click", "anonymous_id": "a1", "event_time": None,
           "properties": {}, "context": {"user_agent": "Mozilla/5.0 (iPhone)"}}
    enriched = enricher.enrich(raw)
    assert enriched["event_time"] is not None
    assert enriched["context"].get("device_type") is not None  # UA parsed
```

Run: `cd tennetctl && .venv/bin/python -m pytest 01_backend/tests/12_product_ops/test_01_ingest.py -v`
Expected: FAIL

- [ ] **Step 3: Write enricher.py**

```python
# 01_backend/02_features/12_product_ops/01_ingest/enricher.py
from datetime import datetime, timezone
from user_agents import parse as parse_ua  # pip install user-agents

def enrich(event: dict) -> dict:
    """Stateless enrichment. Returns new dict, never mutates input."""
    result = {**event}
    # Server timestamp if client didn't provide one
    if not result.get("event_time"):
        result["event_time"] = datetime.now(timezone.utc)
    # UA parsing
    ctx = {**result.get("context", {})}
    ua_string = ctx.get("user_agent", "")
    if ua_string:
        ua = parse_ua(ua_string)
        ctx["browser"]     = ua.browser.family
        ctx["os"]          = ua.os.family
        ctx["device_type"] = ("mobile" if ua.is_mobile else
                               "tablet" if ua.is_tablet else "desktop")
    result["context"] = ctx
    return result
```

- [ ] **Step 4: Write repository.py**

```python
# 01_backend/02_features/12_product_ops/01_ingest/repository.py
import json

async def create_project(conn, data: dict) -> dict:
    row = await conn.fetchrow(
        """INSERT INTO dim_project (workspace_id, name)
           VALUES ($1, $2) RETURNING *""",
        data["workspace_id"], data["name"]
    )
    return dict(row)

async def bulk_insert_events(conn, rows: list[dict]) -> int:
    await conn.executemany(
        """INSERT INTO fct_event
           (project_id, event_name, anonymous_id, user_id, session_id,
            event_time, properties, context)
           VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb)""",
        [(r["project_id"], r["event_name"], r.get("anonymous_id"),
          r.get("user_id"), r.get("session_id"), r["event_time"],
          json.dumps(r.get("properties", {})),
          json.dumps(r.get("context", {}))) for r in rows]
    )
    return len(rows)
```

- [ ] **Step 5: Write worker.py (PRODUCT_OPS stream, batch=250)**

```python
# 01_backend/02_features/12_product_ops/01_ingest/worker.py
import asyncio, json, importlib, logging
import nats
from nats.js.api import ConsumerConfig, AckPolicy

logger = logging.getLogger(__name__)
_repo    = importlib.import_module("01_backend.02_features.12_product_ops.01_ingest.repository")
_enricher = importlib.import_module("01_backend.02_features.12_product_ops.01_ingest.enricher")
_db      = importlib.import_module("01_backend.01_core.database")

BATCH_SIZE = 250

async def _ensure_stream(js):
    try:
        await js.find_stream("PRODUCT_OPS")
    except Exception:
        await js.add_stream(name="PRODUCT_OPS", subjects=["product_ops.events.*"])

async def run_product_ops_worker():
    pool = await _db.get_pool()
    nc = await nats.connect(servers=["nats://localhost:4222"])
    js = nc.jetstream()
    await _ensure_stream(js)

    sub = await js.pull_subscribe("product_ops.events.*", durable="product-ops-events-worker",
        config=ConsumerConfig(ack_policy=AckPolicy.EXPLICIT, max_deliver=5, ack_wait=30))
    asyncio.create_task(_consume_loop(sub, pool))
    logger.info("ProductOps NATS worker started")

async def _consume_loop(sub, pool):
    while True:
        try:
            msgs = await sub.fetch(BATCH_SIZE, timeout=5)
            if not msgs: continue
            rows = [_enricher.enrich(json.loads(m.data)) for m in msgs]
            async with pool.acquire() as conn:
                await _repo.bulk_insert_events(conn, rows)
            for m in msgs: await m.ack()
        except Exception as e:
            logger.error(f"ProductOps worker error: {e}")
            await asyncio.sleep(1)
```

- [ ] **Step 6: Write service.py and routes.py, run tests, commit**

Routes: `POST /v1/product-ops/ingest/track`, `POST /v1/product-ops/ingest/identify`, `POST /v1/product-ops/ingest/page`, `POST /v1/product-ops/ingest/batch`.

```bash
cd tennetctl && .venv/bin/python -m pytest 01_backend/tests/12_product_ops/test_01_ingest.py -v
git add 01_backend/02_features/12_product_ops/ 01_backend/01_sql_migrations/20260404_product_ops_ingest.sql 01_backend/tests/12_product_ops/
git commit -m "feat(product-ops): 12_product_ops/01_ingest — NATS worker (batch=250) + event ingest routes + UA enricher"
```

---

### Task 9: `12_product_ops/02_projects` — Project CRUD

Standard 5-file sub-feature. `dim_project` table already created in Task 8 migration.

Routes: `GET/POST /v1/product-ops/projects`, `GET/PATCH/DELETE /v1/product-ops/projects/{id}`.

Test: create project, list it, update name, soft-delete.

```bash
git commit -m "feat(product-ops): 12_product_ops/02_projects — project CRUD"
```

---

### Task 10: `12_product_ops/03_analytics` — Insights Query Engine

**Ref:** `99_forref/tennetctl-v2/01_backend/02_features/12_product_ops/03_analytics/`

Key query patterns:
```sql
-- Event count by name + time bucket
SELECT date_trunc('hour', event_time) AS bucket, COUNT(*) AS count
FROM fct_event
WHERE project_id = $1 AND event_name = $2
  AND event_time BETWEEN $3 AND $4
GROUP BY bucket ORDER BY bucket;

-- Breakdown by property
SELECT properties->>'plan' AS dimension, COUNT(*) AS count
FROM fct_event
WHERE project_id = $1 AND event_name = $2
GROUP BY dimension ORDER BY count DESC LIMIT 20;
```

Routes: `POST /v1/product-ops/analytics/timeseries`, `POST /v1/product-ops/analytics/breakdown`, `POST /v1/product-ops/analytics/totals`.

Test: seed 10 events → timeseries returns bucketed counts → breakdown returns property distribution.

```bash
git commit -m "feat(product-ops): 12_product_ops/03_analytics — insights timeseries + breakdown queries"
```

---

### Task 11: `12_product_ops/04_funnels` — Funnel Analysis

**Ref:** `99_forref/tennetctl-v2/01_backend/02_features/12_product_ops/04_funnels/`

Migration:
```sql
CREATE TABLE IF NOT EXISTS fct_funnel_definition (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES dim_project(id),
    name        TEXT NOT NULL,
    steps       JSONB NOT NULL,  -- [{"event": "signup"}, {"event": "onboard"}, ...]
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Core query: window function tracking ordered event completion per user:
```sql
-- For each step, count users who completed steps 1..N in order within window
WITH step_N AS (
    SELECT DISTINCT user_id FROM fct_event
    WHERE project_id = $1 AND event_name = $2
    AND event_time BETWEEN $3 AND $4
) ...
```

Routes: `GET/POST /v1/product-ops/funnels`, `GET /v1/product-ops/funnels/{id}/results`.

```bash
git commit -m "feat(product-ops): 12_product_ops/04_funnels — funnel definition + conversion analysis"
```

---

### Task 12: `12_product_ops/05_retention` — Cohort Retention

**Ref:** `99_forref/tennetctl-v2/01_backend/02_features/12_product_ops/05_retention/`

Migration:
```sql
CREATE TABLE IF NOT EXISTS fct_retention_definition (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID NOT NULL REFERENCES dim_project(id),
    name         TEXT NOT NULL,
    start_event  TEXT NOT NULL,   -- first-touch event
    return_event TEXT NOT NULL,   -- recurring event
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Core query: users who did `start_event` in week 0 who also did `return_event` in week N.

Routes: `GET/POST /v1/product-ops/retention`, `GET /v1/product-ops/retention/{id}/results`.
Result shape: `{"rows": [{"cohort_date": "...", "day_0": 100, "day_1": 62, "day_7": 41, "day_30": 28}]}`

```bash
git commit -m "feat(product-ops): 12_product_ops/05_retention — cohort retention grid"
```

---

### Task 13: `12_product_ops/06_paths` — User Journey Paths

**Ref:** `99_forref/tennetctl-v2/01_backend/02_features/12_product_ops/06_paths/`

Core query: top N sequential event pairs per user session, returned as `{"source": "homepage", "target": "signup", "count": 342}` for Sankey rendering.

Routes: `POST /v1/product-ops/paths/top-paths` (params: project_id, start_event, end_event, depth, limit).

```bash
git commit -m "feat(product-ops): 12_product_ops/06_paths — user journey path analysis"
```

---

### Task 14: `12_product_ops/07_cohorts` — Cohort Management

Migration:
```sql
CREATE TABLE IF NOT EXISTS dim_cohort (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES dim_project(id),
    name        TEXT NOT NULL,
    filters     JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS lnk_cohort_member (
    cohort_id   UUID NOT NULL REFERENCES dim_cohort(id),
    user_id     TEXT NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (cohort_id, user_id)
);
```

Routes: `GET/POST /v1/product-ops/cohorts`, `GET/PATCH/DELETE /v1/product-ops/cohorts/{id}`, `GET /v1/product-ops/cohorts/{id}/members`, `POST /v1/product-ops/cohorts/{id}/compute`.

`compute` endpoint: evaluate `filters` JSONB against `fct_event`, insert matching `user_id`s into `lnk_cohort_member`.

```bash
git commit -m "feat(product-ops): 12_product_ops/07_cohorts — cohort definition + membership computation"
```

---

### Task 15: `12_product_ops/08_sessions` — Session Tracking

Migration:
```sql
CREATE TABLE IF NOT EXISTS fct_session (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id     UUID NOT NULL REFERENCES dim_project(id),
    anonymous_id   TEXT,
    user_id        TEXT,
    started_at     TIMESTAMPTZ NOT NULL,
    ended_at       TIMESTAMPTZ,
    duration_s     INTEGER,
    page_view_count INTEGER NOT NULL DEFAULT 0,
    entry_url      TEXT,
    exit_url       TEXT,
    context        JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_session_project_user ON fct_session (project_id, user_id, started_at DESC);
```

Service: session start triggered on first event with `session_id`; session end + duration computed when `$session_end` event received or timeout.

Routes: `GET /v1/product-ops/sessions`, `GET /v1/product-ops/sessions/{id}`.

```bash
git commit -m "feat(product-ops): 12_product_ops/08_sessions — session lifecycle tracking"
```

---

### Task 16: `12_product_ops/09_replay` — Session Replay

Migration:
```sql
CREATE TABLE IF NOT EXISTS fct_session_replay_chunk (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   UUID NOT NULL REFERENCES fct_session(id),
    chunk_index  INTEGER NOT NULL,
    events       JSONB NOT NULL,  -- rrweb event array
    recorded_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (session_id, chunk_index)
);
```

Routes:
- `POST /v1/product-ops/sessions/{id}/replay/chunk` — append a chunk
- `GET /v1/product-ops/sessions/{id}/replay` — return all chunks ordered by chunk_index

Test: POST 3 chunks → GET returns them in order → total event count correct.

```bash
git commit -m "feat(product-ops): 12_product_ops/09_replay — session replay JSONB chunk storage"
```

---

### Task 17: `12_product_ops/10_dashboards` — Product Dashboards

Standard 5-file sub-feature (separate from monitoring dashboards).

Migration:
```sql
CREATE TABLE IF NOT EXISTS dim_product_dashboard (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES dim_project(id),
    title       TEXT NOT NULL,
    is_deleted  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS dim_product_panel (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dashboard_id UUID NOT NULL REFERENCES dim_product_dashboard(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    type         TEXT NOT NULL,  -- 'timeseries' | 'breakdown' | 'funnel' | 'retention'
    query        JSONB NOT NULL DEFAULT '{}',
    position     JSONB NOT NULL DEFAULT '{"x":0,"y":0,"w":6,"h":4}'
);
```

Routes: `GET/POST /v1/product-ops/dashboards`, `GET/PATCH/DELETE /v1/product-ops/dashboards/{id}`, panel CRUD.

```bash
git commit -m "feat(product-ops): 12_product_ops/10_dashboards — product analytics dashboards"
```

---

### Task 18: `12_product_ops/11_feature_flags` — Flag Evaluation + Exposure Tracking

**Note:** This is a lightweight product-ops flag tracker (project-scoped, simple rollout%), separate from the full IAM `24_feature_flag` engine.

Migration:
```sql
CREATE TABLE IF NOT EXISTS dim_feature_flag_po (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID NOT NULL REFERENCES dim_project(id),
    key          TEXT NOT NULL,
    name         TEXT NOT NULL,
    enabled      BOOLEAN NOT NULL DEFAULT FALSE,
    rollout_pct  INTEGER NOT NULL DEFAULT 0,  -- 0-100
    rules        JSONB NOT NULL DEFAULT '[]',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, key)
);
CREATE TABLE IF NOT EXISTS fct_flag_exposure (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flag_id      UUID NOT NULL REFERENCES dim_feature_flag_po(id),
    user_id      TEXT,
    anonymous_id TEXT,
    variant      TEXT NOT NULL DEFAULT 'control',
    exposed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Eval logic:
```python
def evaluate_flag(flag: dict, user_id: str) -> str:
    if not flag["enabled"]: return "off"
    # Deterministic bucketing: hash(flag_key + user_id) % 100 < rollout_pct
    import hashlib
    bucket = int(hashlib.md5(f"{flag['key']}{user_id}".encode()).hexdigest(), 16) % 100
    return "on" if bucket < flag["rollout_pct"] else "off"
```

Routes: `GET/POST /v1/product-ops/flags`, `GET/PATCH/DELETE /v1/product-ops/flags/{id}`, `POST /v1/product-ops/flags/evaluate` (records exposure), `GET /v1/product-ops/flags/{id}/exposures`.

Test: create flag at 50% rollout → evaluate for 100 different user_ids → ~50 get "on" → all recorded in `fct_flag_exposure`.

```bash
git commit -m "feat(product-ops): 12_product_ops/11_feature_flags — flag eval + exposure tracking"
```

---

## Frontend Tasks (per sub-feature, after backend)

Each backend task above should be followed by its frontend page before the commit. Pages go in `02_frontend/src/app/`:

| Backend task | Frontend path | Key components |
|---|---|---|
| 04_monitoring/01_ingest | N/A (worker, no UI) | — |
| 04_monitoring/02_query | `monitoring/metrics/page.tsx`, `monitoring/traces/page.tsx`, `monitoring/logs/page.tsx` | Time-range picker, label filter, data table |
| 04_monitoring/03_dashboards | `monitoring/dashboards/[id]/page.tsx` | Panel grid, panel executor |
| 04_monitoring/04_alerting | `monitoring/alerting/rules/page.tsx`, `monitoring/alerting/instances/page.tsx` | Rule list, state badges |
| 04_monitoring/05_alert_receivers | `monitoring/alerting/receivers/page.tsx` | Receiver form |
| 04_monitoring/06_alert_rules | (merged with alerting UI) | — |
| 04_monitoring/07_slos | `monitoring/slos/page.tsx` | Burn rate gauge, error budget bar |
| 12_product_ops/01_ingest | N/A | — |
| 12_product_ops/02_projects | `product-ops/projects/page.tsx` | Project list + create |
| 12_product_ops/03_analytics | `product-ops/insights/page.tsx` | Time-series chart, breakdown table |
| 12_product_ops/04_funnels | `product-ops/funnels/page.tsx` | Step conversion bars |
| 12_product_ops/05_retention | `product-ops/retention/page.tsx` | Heatmap grid |
| 12_product_ops/06_paths | `product-ops/paths/page.tsx` | Sankey diagram |
| 12_product_ops/07_cohorts | `product-ops/cohorts/page.tsx` | Cohort list + compute |
| 12_product_ops/08_sessions | `product-ops/sessions/page.tsx` | Session list + timeline |
| 12_product_ops/09_replay | `product-ops/replay/[id]/page.tsx` | Replay player (rrweb) |
| 12_product_ops/10_dashboards | `product-ops/dashboards/page.tsx`, `product-ops/dashboards/[id]/page.tsx` | Dashboard grid |
| 12_product_ops/11_feature_flags | `product-ops/feature-flags/page.tsx` | Flag list + toggle + rollout slider |

All pages follow Palantir-inspired monochrome enterprise style per project conventions.

---

## E2E Tests (Robot Framework)

Location: `02_frontend/tests/e2e/{feature}/`

Key flows per feature:
```
monitoring/01_query.robot     — POST metric → query endpoint returns it
monitoring/02_alerts.robot    — Create rule → breach threshold → instance visible in UI
product_ops/01_events.robot   — POST event → appears in insights analytics page
product_ops/02_funnel.robot   — Create funnel → seed events → conversion shows in UI
product_ops/03_replay.robot   — POST replay chunks → load replay page → playback renders
```

---

## Verification Checklist

- [ ] `docker compose up` — Postgres + NATS healthy, no errors
- [ ] POST to `/v1/monitoring/ingest/metrics` → row in `fct_metric_sample`
- [ ] POST to `/v1/monitoring/query/metrics` → returns seeded row
- [ ] NATS worker: publish to `monitoring.metrics` → worker inserts row
- [ ] Create alert rule → seed metric above threshold → `fct_alert_instance` row in state=firing
- [ ] POST to `/v1/product-ops/ingest/track` → row in `fct_event` with enriched context
- [ ] NATS worker: publish to `product_ops.events.track` → batch insert of 250 events
- [ ] Create funnel → POST step events → `/funnels/{id}/results` returns conversion rates
- [ ] POST 3 replay chunks → GET replay → chunks in order
- [ ] Create flag at 50% → POST evaluate for 100 user_ids → ~50 get "on"
- [ ] All 18 frontend pages render without console errors
- [ ] `pytest 01_backend/tests/` — 80%+ coverage across both modules
