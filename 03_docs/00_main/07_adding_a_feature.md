# Adding a Feature

This is the end-to-end guide for adding a new sub-feature to tennetctl. Every sub-feature follows the same workflow. This document is the checklist.

Read it once before starting. Follow it every time.

---

## The Workflow

```
1. Claim the sub-feature
2. Write the scope doc
3. Write the design doc
4. Write the database schema
5. Write the API contract
6. Write tests first (TDD)
7. Implement backend
8. Implement frontend
9. Update the manifest
10. Open a PR
```

Do not skip steps. Do not implement before designing. Do not ship without tests.

---

## Step 1: Claim the Sub-Feature

Find the sub-feature you want to build in `docs/features/{module}/05_sub_features/`. If the sub-feature directory doesn't exist yet:

```bash
mkdir -p docs/features/02_iam/05_sub_features/03_auth
```

Create a `sub_feature.manifest.yaml`:

```yaml
title: "Authentication"
status: DRAFT
module: "02_iam"
owner: "your-github-username"
created_at: "2026-03-29"
```

Open a GitHub issue: "Working on: 02_iam / 03_auth — Authentication". This prevents two people building the same thing simultaneously.

Update the manifest status to `SCOPED` when you start writing the scope doc.

---

## Step 2: Write the Scope Doc

Create `docs/features/02_iam/05_sub_features/03_auth/01_scope.md`.

The scope doc answers three questions:
1. What does this sub-feature do?
2. What is explicitly out of scope?
3. What are the acceptance criteria?

**Template:**

```markdown
# {Sub-feature Name} — Scope

## What it does

{2-3 sentence plain English description of what this sub-feature does and why it exists.}

## In scope

- {Specific capability 1}
- {Specific capability 2}
- {Specific capability 3}

## Out of scope

- {Thing that sounds related but isn't being built here}
- {Thing that will be handled by another sub-feature}

## Acceptance criteria

- [ ] {Observable, testable outcome 1}
- [ ] {Observable, testable outcome 2}
- [ ] {Observable, testable outcome 3}

## Dependencies

- Depends on: {sub-features or external services this requires}
- Depended on by: {sub-features that cannot be built without this}
```

Get the scope doc reviewed before writing the design doc. A misunderstood scope means wasted implementation work.

---

## Step 3: Write the Design Doc

Create `docs/features/02_iam/05_sub_features/03_auth/02_design.md`.

The design doc answers: how does it work?

**Template:**

```markdown
# {Sub-feature Name} — Design

## Data Model

{Describe the tables involved. What does each table store?
What are the key relationships? You will write the actual SQL in step 4,
but describe the model here in prose first.}

## Service Layer

{Describe the key service functions. What are the inputs and outputs?
What are the important business rules? What can go wrong?}

Key functions:
- `create_user(email, password) → User` — creates a new user, hashes password with argon2, emits `user.created` event
- `authenticate(email, password) → (AccessToken, RefreshToken)` — verifies credentials, creates session

Business rules:
- {Rule 1}
- {Rule 2}

## API Layer

{Describe the endpoints at a high level. You will write the formal contract in step 5.}

## Security Considerations

{What are the security risks in this sub-feature? How are they mitigated?}

- Rate limiting on: {which endpoints}
- Authentication required on: {which endpoints}
- Permissions required: {what RBAC permission codes}
- Audit events emitted: {list of event types}

## Events

{List all events this sub-feature emits and consumes.}

Emits:
- `user.created` — when a new user registers
- `user.login.success` — on successful authentication
- `user.login.failed` — on failed authentication (rate limit trigger)

Consumes:
- (none for this sub-feature)
```

---

## Step 4: Write the Database Schema

Create `docs/features/02_iam/05_sub_features/03_auth/04_db_schema.sql`.

Write the full `CREATE TABLE` statements for all tables this sub-feature needs.

**Requirements (all are mandatory):**
- Every table and column has a `COMMENT`
- All constraint names are explicit with correct prefixes (`pk_`, `fk_`, `uq_`, `idx_`, `chk_`)
- Table naming follows `{nn}_{type}_{name}` within the module schema
- Every table has `created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP`
- Tables with `org_id` have an RLS policy

**Example:**

```sql
-- =============================================================================
-- Schema: 02_iam
-- Sub-feature: 03_auth
-- Description: User accounts and password credentials
-- =============================================================================

CREATE TABLE "02_iam".fct_users (
    id          UUID        NOT NULL DEFAULT gen_random_uuid(),
    email       TEXT        NOT NULL,
    status_id   SMALLINT    NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_fct_users PRIMARY KEY (id),
    CONSTRAINT fk_fct_users_status FOREIGN KEY (status_id)
        REFERENCES "02_iam".dim_user_statuses(id),
    CONSTRAINT uq_fct_users_email UNIQUE (email),
    CONSTRAINT chk_fct_users_email CHECK (email ~* '^[^@]+@[^@]+\.[^@]+$')
);

COMMENT ON TABLE "02_iam".fct_users IS
    'Platform user accounts. One row per registered user regardless of org membership.';
COMMENT ON COLUMN "02_iam".fct_users.id IS
    'UUID v7 primary key. Time-ordered for efficient indexing.';
COMMENT ON COLUMN "02_iam".fct_users.email IS
    'Unique email address. Used as login identifier. Stored lowercase.';
COMMENT ON COLUMN "02_iam".fct_users.status_id IS
    'References dim_user_statuses. Controls login access.';
```

Once the schema SQL is approved in review, convert it to a migration file in `09_sql_migrations/02_in_progress/`.

---

## Step 5: Write the API Contract

Create `docs/features/02_iam/05_sub_features/03_auth/05_api_contract.yaml`.

Write a minimal OpenAPI fragment for this sub-feature's endpoints.

```yaml
paths:
  /auth/login:
    post:
      summary: Authenticate a user with email and password
      tags: [auth]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [email, password]
              properties:
                email:
                  type: string
                  format: email
                password:
                  type: string
                  minLength: 8
      responses:
        "200":
          description: Authentication successful
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/AuthTokenResponse"
        "401":
          description: Invalid credentials
        "429":
          description: Too many failed attempts
```

This contract is the agreement between frontend and backend. The Pydantic models and FastAPI routes must match it exactly.

---

## Step 6: Write Tests First (TDD)

Before writing any implementation code, write the tests.

Create `backend/tests/{module}/{sub_feature}/test_{sub_feature}.py`.

```python
# backend/tests/02_iam/03_auth/test_login.py

async def test_login_success(client, seeded_user):
    """Successful login returns access and refresh tokens."""
    response = await client.post("/api/v1/auth/login", json={
        "email": seeded_user.email,
        "password": "correct_password"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

async def test_login_wrong_password(client, seeded_user):
    """Wrong password returns 401."""
    response = await client.post("/api/v1/auth/login", json={
        "email": seeded_user.email,
        "password": "wrong_password"
    })
    assert response.status_code == 401

async def test_login_rate_limited(client, seeded_user):
    """Exceeding failed attempt limit returns 429."""
    for _ in range(10):
        await client.post("/api/v1/auth/login", json={
            "email": seeded_user.email,
            "password": "wrong"
        })
    response = await client.post("/api/v1/auth/login", json={
        "email": seeded_user.email,
        "password": "wrong"
    })
    assert response.status_code == 429
```

Run the tests. They should fail (RED). That is correct.

---

## Step 7: Implement the Backend

Create the backend module at `backend/02_features/{module}/{sub_feature}/`.

The module structure is always the same five files:

```
{sub_feature}/
├── __init__.py
├── schemas.py      Pydantic request/response models
├── repository.py   Data access — asyncpg raw SQL only
├── service.py      Business logic
└── routes.py       FastAPI router
```

**`schemas.py`** — Define all Pydantic v2 models for this sub-feature. Models must match the API contract from step 5.

**`repository.py`** — One function per query. No business logic. Returns typed dicts or named tuples. Every function has a docstring.

```python
async def get_user_by_email(conn, email: str) -> dict | None:
    """Fetch a user record by email address. Returns None if not found."""
    return await conn.fetchrow(
        'SELECT id, email, status_id FROM "02_iam".fct_users WHERE email = $1',
        email.lower()
    )
```

**`service.py`** — Business logic. Calls repository functions. Calls `emit_event()`. Raises typed exceptions from `01_core/exceptions.py`. Never issues raw SQL.

**`routes.py`** — FastAPI router. Validates request with Pydantic. Calls service. Returns response. No business logic. Every route has a docstring.

Run the tests. They should pass (GREEN).

---

## Step 8: Implement the Frontend

Create the frontend pages at `frontend/src/app/features/{module}/{sub_feature}/`.

- Use shadcn/ui components
- Server components by default; add `"use client"` only when needed
- Validate forms with React Hook Form + Zod, matching backend Pydantic models
- Use TanStack Query for data fetching and mutations
- TypeScript strict mode — no `any`

---

## Step 9: Update the Manifest

Update `sub_feature.manifest.yaml`:

```yaml
title: "Authentication"
status: DONE
module: "02_iam"
owner: "your-github-username"
created_at: "2026-03-29"
completed_at: "2026-04-05"
```

Also update the parent `feature.manifest.yaml` if all sub-features in the module are done.

---

## Step 10: Open a PR

Your PR description must include:

```markdown
## What this PR does

{2-3 sentences}

## Sub-feature

Module: 02_iam
Sub-feature: 03_auth — Authentication

## Testing

- [ ] Unit tests added and passing
- [ ] Integration tests added and passing
- [ ] Tested manually: {what you tested}

## Checklist

- [ ] Docs updated (scope, design, schema, API contract)
- [ ] Manifest status set to DONE
- [ ] No file exceeds 500 lines
- [ ] Every new function has a docstring
- [ ] Migration has UP and DOWN
- [ ] Audit events emitted for all mutating operations
```

---

## Migration File Naming

When the schema SQL from step 4 is approved and ready to apply:

```
YYYYMMDD_{NNN}_{description}.sql
```

Example: `20260405_007_auth_tables.sql`

Place it in `09_sql_migrations/02_in_progress/`. After applying it in production, move it to `01_migrated/`.

Every migration file must have both UP and DOWN sections clearly marked:

```sql
-- =============================================================================
-- Migration: 20260405_007_auth_tables.sql
-- Description: User accounts and password credential tables for IAM auth
-- UP
-- =============================================================================

CREATE TABLE ...

-- =============================================================================
-- DOWN
-- =============================================================================

DROP TABLE IF EXISTS "02_iam".lnk_user_passwords;
DROP TABLE IF EXISTS "02_iam".fct_users;
```
