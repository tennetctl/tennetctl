# Building a Feature

End-to-end guide for adding a new feature or sub-feature to tennetctl. Follow every step in order. Do not skip steps.

---

## Before You Start

1. Read [01_database_structure.md](01_database_structure.md) — you must understand the EAV model
2. Check the [roadmap](../03_docs/00_main/04_roadmap.md) — pick a sub-feature not marked `BUILDING` or `DONE`
3. Open an issue: "Working on: {module} / {sub-feature} — {title}"

---

## The 12-Step Workflow

```
 1. Claim the sub-feature
 2. Write the scope doc
    ── GATE: Re-read scope against vision/ethos. Does it belong?
 3. Write the design doc
    ── GATE: Does the design violate any rule (R-001 to R-019)?
 4. Write the database schema
 5. Verify the migration locally
    ── GATE: UP → DOWN → UP round-trips cleanly?
 6. Write the API contract
 7. Check cross-module impact
 8. Write tests first (TDD — RED)
 9. Implement backend (GREEN)
10. Implement frontend
11. Update manifests
12. Open a PR (with rollback plan)
```

> **Docs-first PR (recommended for large features):**
> Steps 1–6 can be a standalone "docs PR" merged before writing code.
> This forces scope/design review before implementation begins —
> no sunk-cost pressure from already-written code.

---

## Step 1: Claim the Sub-Feature

Create the sub-feature directory and manifest:

```bash
mkdir -p 03_docs/features/{module}/05_sub_features/{nn}_{sub_feature}
```

Create `sub_feature.manifest.yaml`:

```yaml
title: "Sub-Feature Name"
status: DRAFT
module: "{module}"
owner: "your-github-username"
created_at: "YYYY-MM-DD"
```

---

## Step 2: Write the Scope Doc

Create `01_scope.md` in the sub-feature directory.

Answer three questions:
1. **What does this sub-feature do?** (2-3 sentences)
2. **What is explicitly out of scope?**
3. **What are the acceptance criteria?** (observable, testable)

Get the scope reviewed before proceeding. A wrong scope means wasted work.

---

## Step 3: Write the Design Doc

Create `02_design.md`. Describe:

- **Data model** — which tables are involved, relationships, EAV attributes
- **Service layer** — key functions, inputs/outputs, business rules
- **API layer** — endpoints at a high level
- **Security** — rate limiting, permissions, audit events
- **Events** — what this sub-feature emits and consumes

---

## Step 4: Write the Database Schema

This is the critical step. Every database change must follow the EAV pattern.

### Decision Tree: Where Does My Data Go?

```
Is it a fixed set of codes/statuses/types?
  → YES → dim_* table (SMALLINT PK, seeded in migration)

Is it a new entity (user, org, project)?
  → YES → fct_* table (UUID PK, FK refs only, NO strings)

Is it a descriptive property (name, email, settings)?
  → YES → dtl_attrs via dim_attr_defs (NO new column, NO ALTER TABLE)

Is it an association between two entities?
  → YES → lnk_* table (immutable, no updated_at)

Is it admin/operator configuration?
  → YES → adm_* table

Is it an event/log entry?
  → YES → evt_* table (append-only, never updated)
```

### For New Properties (Most Common Case)

Do NOT add a column to a `fct_*` table. Instead:

```sql
-- 1. Register the attribute
INSERT INTO "{schema}".07_dim_attr_defs
    (id, entity_type_id, code, label, value_type, is_required, is_unique, description)
VALUES (...);

-- 2. Update the view to materialize it
-- Add to the SELECT in v_{entity}:
MAX(CASE WHEN ad.code = 'new_attr' THEN a.key_text END) AS new_attr,
```

### For New Entities

Write the full `CREATE TABLE` with:
- All standard audit columns (`is_active`, `is_test`, `deleted_at`, `created_by`, `updated_by`, `created_at`, `updated_at`)
- Explicit constraint names (pk_, fk_, uq_, chk_, idx_)
- `COMMENT` on every table and column
- RLS policy if table has `org_id`
- No triggers, functions, procedures, extensions, or ENUMs
- Both UP and DOWN sections in the migration

### Migration File

```
03_docs/features/{module}/09_sql_migrations/02_in_progress/YYYYMMDD_{NNN}_{description}.sql
```

`{NNN}` is a global sequence number. Check existing migrations to find the next available number.

---

## Step 5: Verify the Migration Locally

Before writing any code, prove the migration works:

```bash
# Apply the migration
uv run python -m scripts.migrate up

# Inspect the tables
docker compose exec postgres psql -U tennetctl -d tennetctl \
  -c '\d+ "{schema}".{table_name}'

# Roll back
uv run python -m scripts.migrate down

# Re-apply — confirms UP → DOWN → UP round-trips cleanly
uv run python -m scripts.migrate up
```

**GATE:** If the migration fails on a clean database, fix it before proceeding. If the DOWN doesn't cleanly revert the UP, fix it. If re-applying after rollback fails, fix it.

### Safe Migration Checklist

| Risk | Check |
| ---- | ----- |
| Adding `NOT NULL` column to existing table | Provide a `DEFAULT` or backfill in the same migration |
| Renaming a column | Two-step: add new column → migrate data → drop old column (separate PRs) |
| Dropping a column | Verify no view, query, or application code references it |
| Changing column type | Verify existing data is compatible with the new type |

---

## Step 6: Write the API Contract

Create `05_api_contract.yaml` — minimal OpenAPI fragment:

```yaml
paths:
  /v1/{module}/{entity}:
    get:
      summary: List entities
      responses:
        "200":
          description: Success
          content:
            application/json:
              schema:
                type: object
                properties:
                  ok: { type: boolean }
                  data: { type: array, items: { $ref: "#/..." } }
    post:
      summary: Create entity
      responses:
        "201":
          description: Created
```

Every response uses the envelope: `{ "ok": true, "data": {...} }` or `{ "ok": false, "error": {"code": "...", "message": "..."} }`.

---

## Step 7: Check Cross-Module Impact

Before writing code, check whether this sub-feature affects other modules.

| Question | If YES |
| -------- | ------ |
| Does this emit new events? | Document the event schema in `02_design.md`. List consuming modules. |
| Do existing event consumers need updating? | File an issue against the consuming module. |
| Does this add a new `scope_type` / `scope_id` usage? | Verify all scoped queries across the codebase handle it. |
| Does this add a new `entity_type` to `dim_entity_types`? | Verify `dtl_attrs` queries and views handle the new type. |
| Does this change an existing dim code's meaning? | Check all code that references that code by string. |

If there is cross-module impact, document it in the PR body and consider splitting the work.

---

## Step 8: Write Tests First (TDD)

Create `backend/tests/{module}/{sub_feature}/test_{sub_feature}.py`.

Write the tests BEFORE any implementation. Run them — they must fail (RED).

```python
async def test_create_entity_success(client, seeded_org):
    """Creating an entity returns 201 with the entity data."""
    response = await client.post("/api/v1/{module}/{entity}", json={...})
    assert response.status_code == 201
    data = response.json()
    assert data["ok"] is True

async def test_create_entity_missing_field(client, seeded_org):
    """Missing required field returns 400."""
    response = await client.post("/api/v1/{module}/{entity}", json={})
    assert response.status_code == 400
```

### What to Test

| Layer | What to test |
|-------|-------------|
| API | Status codes, response shape, validation errors |
| Service | Business rules, edge cases, error conditions |
| Repository | Query correctness against real Postgres |

Tests run against a real database. No mocks.

---

## Step 9: Implement Backend

Create the backend module:

```
backend/02_features/{module}/{sub_feature}/
├── __init__.py
├── schemas.py      # Pydantic v2 request/response models
├── repository.py   # Data access — asyncpg raw SQL only
├── service.py      # Business logic
└── routes.py       # FastAPI router
```

### schemas.py
- Pydantic v2 models matching the API contract
- Separate request and response models

### repository.py
- One function per query
- No business logic
- Returns typed dicts or named tuples
- Every function has a docstring
- Every UPDATE includes `updated_at = CURRENT_TIMESTAMP, updated_by = $actor_id`

### service.py
- Business logic
- Calls repository functions
- Calls `emit_event()` for mutating operations
- Raises typed exceptions from `01_core/exceptions.py`
- Never issues raw SQL

### routes.py
- FastAPI router
- Validates with Pydantic
- Calls service layer
- Returns response envelope
- No business logic

Run the tests. They must pass (GREEN).

---

## Step 10: Implement Frontend

```
frontend/src/app/features/{module}/{sub_feature}/
```

- shadcn/ui components
- Server components by default; `"use client"` only when needed
- React Hook Form + Zod for form validation (mirror Pydantic models)
- TanStack Query for data fetching
- TypeScript strict mode — no `any`

---

## Step 11: Update Manifests

Update `sub_feature.manifest.yaml`:

```yaml
status: DONE
completed_at: "YYYY-MM-DD"
```

Update parent `feature.manifest.yaml` if all sub-features are done.

---

## Step 12: Open a PR

PR title: `feat: {short description}`

PR body must include:

```markdown
## What this PR does
{2-3 sentences}

## Sub-feature
Module: {module}
Sub-feature: {nn}_{name}

## Database changes
- [ ] New dim_* tables: {list or "none"}
- [ ] New fct_* tables: {list or "none"}
- [ ] New dtl_attrs attributes: {list attr codes or "none"}
- [ ] New lnk_* tables: {list or "none"}
- [ ] New views: {list or "none"}

## Cross-module impact
- [ ] New events emitted: {list or "none"}
- [ ] Consumer modules affected: {list or "none"}
- [ ] New scope_type/entity_type entries: {list or "none"}

## Rollback plan
- [ ] Migration DOWN tested and confirmed working
- [ ] Rollback steps: {e.g. "revert migration, no data loss" or "requires data backfill — see notes"}
- [ ] Breaking changes: {list or "none — safe to roll back at any point"}

## Testing
- [ ] Unit tests added and passing
- [ ] Integration tests added and passing
- [ ] Robot Framework API tests added
- [ ] Tested manually: {what you tested}

## Screenshots
{Attach before/after screenshots for any UI changes}
{Attach schema diagram screenshots if adding new tables}

## Checklist
- [ ] Scope, design, schema, API contract docs complete
- [ ] Manifest status set to DONE
- [ ] No file exceeds 500 lines
- [ ] Every new function has a docstring
- [ ] Migration has UP and DOWN (round-trip verified)
- [ ] Audit events emitted for all mutating operations
- [ ] Properties stored in dtl_attrs, not fct_* columns
- [ ] No triggers, ENUMs, stored procedures
- [ ] Cross-module impact documented (or confirmed none)
```

---

## Common Mistakes

| Mistake | Correct Approach |
|---------|-----------------|
| Adding a `name` column to `fct_*` | Add to `dim_attr_defs` → store in `dtl_attrs` |
| Using `CREATE TYPE ... AS ENUM` | Create a `dim_*` lookup table |
| Writing a trigger for `updated_at` | Set explicitly in every repository UPDATE |
| Cross-schema JOIN in a view | Use event bus or `01_core/` service interface |
| Skipping the DOWN migration | Always write a complete DOWN that reverts UP |
| Importing another module's service | Emit an event and handle in the receiving module |
| Using `is_deleted BOOLEAN` | Use `deleted_at TIMESTAMP` |
