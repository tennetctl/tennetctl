# ADR-003: Raw SQL with asyncpg — No ORM

**Status:** Accepted
**Date:** 2026-03-29

---

## Context

The backend is Python with FastAPI. Python has several mature ORM options: SQLAlchemy (sync and async), Tortoise ORM, and others. ORMs abstract the SQL layer behind Python objects, reducing the amount of SQL developers need to write and providing type safety through model definitions.

tennetctl's database layer has specific requirements:
- Tables use a non-standard naming convention: `{nn}_{type}_{name}` (e.g., `02_fct_users`)
- Every query must be auditable by reading the SQL directly
- Queries must be optimizable without fighting an ORM's query generation
- The database uses Postgres-specific features: RLS, advisory locks, LISTEN/NOTIFY, `gen_random_uuid()`, CTEs
- Contributors must be able to read and understand queries without ORM knowledge

---

## Decision

All database access uses raw SQL with asyncpg. No ORM is used anywhere in the codebase.

The repository pattern provides the abstraction layer: repository functions encapsulate queries and return typed dicts. Service layers call repository functions and never write SQL directly. This achieves the separation of concerns that an ORM provides, without the abstraction overhead.

---

## Consequences

**Positive:**
- Every query in the codebase is explicit, readable SQL that can be copied into a Postgres client and inspected
- No ORM-generated query surprises (N+1 queries, unexpected JOINs, missing indexes)
- Postgres-specific features work naturally: CTEs, window functions, advisory locks, `RETURNING`, `ON CONFLICT`
- The non-standard table naming convention works without fighting ORM model class naming rules
- Contributors who know SQL can read and write queries immediately — no ORM-specific knowledge required
- asyncpg is the fastest Python Postgres driver (no overhead layer)

**Negative:**
- More SQL to write manually compared to ORM model definition
- Type safety on query results requires explicit typing in repository return types
- No automatic migration generation from model changes (migrations must be written manually)

**Mitigations:**
- The repository pattern keeps SQL in one place (repository functions) and out of service and route layers
- Pydantic models provide type safety for data passed between layers — repository returns typed dicts, service converts to Pydantic models
- Manual migrations are a feature, not a bug: explicit migrations are easier to review, easier to roll back, and easier to reason about than auto-generated ones

---

## Alternatives Considered

**SQLAlchemy async:** The most mature Python ORM with async support. Rejected because (1) the `{nn}_{type}_{name}` table naming convention requires manual table name overrides on every model, negating ORM convenience; (2) SQLAlchemy adds a significant learning curve for contributors; (3) the ORM query layer hides Postgres-specific optimizations; (4) adding asyncpg under SQLAlchemy adds both the ORM overhead and the driver overhead.

**Tortoise ORM:** Lighter than SQLAlchemy but less mature and less widely understood. Rejected for the same reasons: naming convention conflicts, Postgres-specific feature limitations.

**SQLModel:** A thin wrapper around SQLAlchemy + Pydantic. Rejected — it inherits SQLAlchemy's limitations while adding another abstraction layer.

---

## Repository Pattern Convention

Every feature module has a `repository.py` file with functions following this pattern:

```python
async def get_user_by_id(conn: asyncpg.Connection, user_id: UUID) -> dict | None:
    """
    Fetch a single user by primary key.

    Args:
        conn: Active database connection (from tenant_transaction or platform_transaction)
        user_id: UUID v7 primary key of the user

    Returns:
        User record as a dict, or None if not found
    """
    return await conn.fetchrow(
        """
        SELECT id, email, status_id, created_at
        FROM "02_iam".fct_users
        WHERE id = $1
        """,
        user_id
    )
```

Rules:
- One function per logical query
- No business logic in repository functions
- Every function has a complete docstring
- Parameters use `$1`, `$2` placeholders (never f-strings or string concatenation)
- Functions return `asyncpg.Record`, `list[asyncpg.Record]`, or `None` — never ORM objects
