# Backend API Standards

Standards for building backend APIs in tennetctl. Every API endpoint follows these patterns exactly.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI |
| Validation | Pydantic v2 |
| Database driver | asyncpg (raw SQL) |
| ORM | None — raw SQL only (R-001) |
| Package manager | uv |
| Python version | 3.12+ |

---

## Response Envelope

Every API response uses this envelope. No exceptions.

### Success

```json
{
  "ok": true,
  "data": { ... }
}
```

### Error

```json
{
  "ok": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Organisation not found."
  }
}
```

### List Response

```json
{
  "ok": true,
  "data": [
    { ... },
    { ... }
  ],
  "meta": {
    "total": 42,
    "page": 1,
    "per_page": 20
  }
}
```

### Error Codes

Use uppercase snake_case error codes. Common codes:

| Code | HTTP Status | Meaning |
|------|-------------|---------|
| `VALIDATION_ERROR` | 400 | Request body/params failed validation |
| `UNAUTHORIZED` | 401 | Missing or invalid auth token |
| `FORBIDDEN` | 403 | Authenticated but lacks permission |
| `NOT_FOUND` | 404 | Resource does not exist |
| `CONFLICT` | 409 | Duplicate or conflicting state |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## Module Structure (5 Files)

Every sub-feature's backend has exactly 5 files:

```
backend/02_features/{module}/{sub_feature}/
├── __init__.py       # Empty or re-exports router
├── schemas.py        # Pydantic models
├── repository.py     # Database queries
├── service.py        # Business logic
└── routes.py         # FastAPI endpoints
```

### schemas.py — Pydantic v2 Models

```python
from pydantic import BaseModel, Field

class CreateOrgRequest(BaseModel):
    """Request body for creating an organisation."""
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(pattern=r'^[a-z0-9-]+$', min_length=2, max_length=50)

class OrgResponse(BaseModel):
    """Organisation response — mirrors v_orgs view output."""
    id: str
    name: str
    slug: str
    status: str
    is_active: bool
    created_at: str
```

Rules:
- Separate request and response models
- Field validation with Pydantic validators
- Models match the API contract in `05_api_contract.yaml`
- No `Any` types

### repository.py — Data Access

```python
async def get_org_by_id(conn, org_id: str) -> dict | None:
    """Fetch an organisation by ID from v_orgs view. Returns None if not found."""
    return await conn.fetchrow(
        'SELECT * FROM "02_iam".v_orgs WHERE id = $1 AND is_deleted = FALSE',
        org_id
    )

async def create_org(conn, *, org_id: str, status_id: int, actor_id: str) -> None:
    """Insert a new org record into fct_orgs."""
    await conn.execute(
        '''INSERT INTO "02_iam"."11_fct_orgs"
           (id, status_id, created_by, updated_by)
           VALUES ($1, $2, $3, $3)''',
        org_id, status_id, actor_id
    )

async def update_org_status(conn, *, org_id: str, status_id: int, actor_id: str) -> None:
    """Update org status. Sets updated_at and updated_by."""
    await conn.execute(
        '''UPDATE "02_iam"."11_fct_orgs"
           SET status_id = $1,
               updated_by = $2,
               updated_at = CURRENT_TIMESTAMP
           WHERE id = $3''',
        status_id, actor_id, org_id
    )
```

Rules:
- One function per query
- No business logic
- Every function has a docstring
- GET queries read from views (`v_*`)
- Write queries go directly to tables
- Every UPDATE includes `updated_at = CURRENT_TIMESTAMP, updated_by = $actor_id`
- Raw SQL only — no ORM, no query builder
- `conn` (not pool) is passed as first argument

### service.py — Business Logic

```python
from app.core.exceptions import NotFoundError, ConflictError
from app.core.events import emit_event

async def create_org(conn, *, request: CreateOrgRequest, actor_id: str) -> dict:
    """Create a new organisation. Emits org.created event."""
    # Check for duplicate slug
    existing = await repo.get_org_by_slug(conn, request.slug)
    if existing:
        raise ConflictError("ORG_SLUG_EXISTS", f"Slug '{request.slug}' already taken.")

    org_id = generate_uuid7()

    # Create identity record
    await repo.create_org(conn, org_id=org_id, status_id=1, actor_id=actor_id)

    # Store descriptive attributes in EAV
    await repo.set_org_attrs(conn, org_id=org_id, attrs={
        "name": request.name,
        "slug": request.slug,
    }, actor_id=actor_id)

    # Emit audit event
    await emit_event(conn, event_type="org.created", org_id=org_id, actor_id=actor_id)

    return await repo.get_org_by_id(conn, org_id)
```

Rules:
- All business logic lives here
- Calls repository functions (never writes raw SQL)
- Calls `emit_event()` for every mutating operation
- Raises typed exceptions from `01_core/exceptions.py`
- Returns dict (fetched from view after write)
- Receives `conn` not `pool`

### routes.py — FastAPI Router

```python
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/v1/orgs", tags=["organisations"])

@router.post("", status_code=201)
async def create_org(
    request: CreateOrgRequest,
    conn=Depends(get_connection),
    actor=Depends(get_current_user),
):
    """Create a new organisation."""
    org = await service.create_org(conn, request=request, actor_id=actor.id)
    return {"ok": True, "data": org}

@router.get("/{org_id}")
async def get_org(
    org_id: str,
    conn=Depends(get_connection),
    actor=Depends(get_current_user),
):
    """Get an organisation by ID."""
    org = await service.get_org(conn, org_id=org_id)
    return {"ok": True, "data": org}
```

Rules:
- No business logic — only calls service layer
- Every route has a docstring
- Uses Pydantic for request validation
- Returns response envelope
- Uses dependency injection for `conn` and `actor`

---

## URL Conventions

```
GET    /v1/{module}/{entity}            # List
POST   /v1/{module}/{entity}            # Create
GET    /v1/{module}/{entity}/{id}       # Get by ID
PATCH  /v1/{module}/{entity}/{id}       # Update
DELETE /v1/{module}/{entity}/{id}       # Soft-delete
```

- Always `/v1/` prefix
- Plural entity names
- UUID in path for single-resource operations
- Query params for filtering: `?status=active&page=1&per_page=20`

---

## Scoping Pattern

Every list endpoint supports scope filtering:

```
GET /v1/feature-flags?scope=platform
GET /v1/feature-flags?scope=org&scope_id=<org_id>
GET /v1/feature-flags?scope=project&scope_id=<project_id>
```

The `scope` parameter defaults based on the caller's role.

---

## Error Handling

```python
# In 01_core/exceptions.py
class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code

class NotFoundError(AppError):
    def __init__(self, code: str, message: str):
        super().__init__(code, message, status_code=404)

class ConflictError(AppError):
    def __init__(self, code: str, message: str):
        super().__init__(code, message, status_code=409)
```

- Never swallow errors silently (R-007)
- Always use typed exceptions
- Error responses use the standard envelope

---

## Audit Events

Every mutating operation (POST, PATCH, DELETE) must emit an audit event:

```python
await emit_event(
    conn,
    event_type="org.created",     # {entity}.{action}
    org_id=org_id,
    actor_id=actor_id,
    metadata={"name": request.name}
)
```

The event is committed in the same transaction as the data change.

---

## Configuration

No hardcoded values. Everything in `01_core/config.py`:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    nats_url: str
    access_token_ttl_seconds: int = 900
    # ...

    class Config:
        env_prefix = "APP_"
```

---

## Checklist — Before Every Backend PR

- [ ] Response envelope on every endpoint
- [ ] Pydantic validation on all request bodies
- [ ] Every function has a docstring
- [ ] Every UPDATE includes `updated_at` and `updated_by`
- [ ] Audit events emitted for all mutating operations
- [ ] No business logic in routes.py
- [ ] No raw SQL in service.py
- [ ] No ORM usage anywhere
- [ ] No hardcoded values
- [ ] No silent error swallowing
- [ ] No file exceeds 500 lines
- [ ] GET queries read from views, writes go to tables
