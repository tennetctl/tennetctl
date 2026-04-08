---
paths:
  - "**/*.py"
  - "**/*.pyi"
---

# Python — Project-Specific Rules

Claude knows PEP 8, type hints, Pydantic, asyncio. This file covers OUR deviations.

## importlib (CRITICAL)

Python cannot import from directories with numeric prefixes. Use `importlib` everywhere:

```python
from importlib import import_module
_db      = import_module("backend.01_core.database")
_core_id = import_module("backend.01_core.id")
_errors  = import_module("backend.01_core.errors")
_resp    = import_module("backend.01_core.response")
```

Never use relative imports with numeric dirs.

## UUID = uuid7() always

```python
_core_id = import_module("backend.01_core.id")
new_uuid = _core_id.uuid7()   # NOT uuid4(), NOT new_id()
```

## conn not pool (CRITICAL)

Pass `conn` (connection) to service and repo functions. Never `pool`.

Pool lifecycle: pool → route acquires conn → passes to service → passes to repo.

`pool.acquire()` belongs in routes only. Never in service or repo.

## Repository Pattern

- Reads query `v_{entity}` views. Writes go to raw `fct_*`/`dtl_*` tables.
- One function per query. No business logic in repo.
- asyncpg handles Python dicts as JSONB automatically — never call `json.dumps()`.

## Response Helpers

```python
return _resp.success_response(data)
return _resp.success_list_response(data, total=total, limit=limit, offset=offset)
raise _errors.AppError("NOT_FOUND", f"Org '{org_id}' not found.", 404)
```

Route status codes: `@router.post(..., status_code=201)`, `@router.delete(..., status_code=204)`.

## Audit Events (every mutation)

Every create/update/delete emits an audit event via `_audit.emit_audit_event(conn, ...)`.

## Start command

```bash
cd tennetctl && .venv/bin/python -m uvicorn backend.main:app --port 18000 --host 0.0.0.0 --reload
```

Never use `.venv/bin/uvicorn` directly — it picks up system Python.
