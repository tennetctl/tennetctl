# Building a Sub-Feature

How to build one sub-feature inside an existing feature, end to end. This is the workflow you actually run most days. A sub-feature is a unit of work that ships in one or two PRs.

If the feature itself doesn't exist yet, stop here and read [01_building_a_feature.md](01_building_a_feature.md) first — you need the feature scaffold and bootstrap migration in place before any sub-feature can land.

If you're modifying a sub-feature that's already been merged, read [02_building_an_enhancement.md](02_building_an_enhancement.md) instead.

> **Vocabulary recap**
> - **Feature** — a top-level domain (IAM, Vault, Audit, Monitoring, …). ~8 total. One Postgres schema. One backend module. One folder under `03_docs/features/`.
> - **Sub-feature** — a unit of work *inside* a feature. Lives at `03_docs/features/{nn}_{feature}/05_sub_features/{nn}_{sub_feature}/`. Has its own scope doc, design doc, manifest, migration, backend code, frontend code, tests. Examples inside IAM: `01_org`, `02_user`, `08_auth`, `19_rbac`.
> - **Bootstrap sub-feature** — every feature has a special `00_bootstrap/` sub-feature that owns the schema-creation migration. You don't build that here — it was created during [01_building_a_feature.md](01_building_a_feature.md) Phase 2.

## TL;DR

If you've built a sub-feature before, here's the checklist:

1. **Open issue** using Sub-Feature Build template, fill Scope Lock
2. **Write docs** — 01_scope.md, 02_design.md, 05_api_contract.yaml, sub_feature.manifest.yaml
3. **Write migration** — SQL file in 09_sql_migrations/02_in_progress/, next sequential `{NNN}` number
4. **Verify migration** — `UP → DOWN → UP` round-trip on clean database
5. **Check cross-feature impact** — events, entity types, scope types
6. **Write tests** (RED) — pytest files that fail with no implementation
7. **Implement backend** — schemas, repository, service, routes (5-file structure)
8. **Implement frontend** — page, components, hooks
9. **Write Robot Framework tests** (API + E2E)
10. **Open PR** — self-review, run agents, merge

For first-time builders or larger features, read the full sections below.

---

## Prerequisites and known gaps

> **The migration runner does not exist yet.** This doc tells you to run `uv run python -m scripts.migrate up` in Phase 4. There is no `scripts/migrate.py` in the repo today — the runner is itself a planned early sub-feature. Until it lands, apply migrations by hand: `docker compose exec postgres psql -U tennetctl -d tennetctl -f /path/to/migration.sql`. Extract the DOWN section into a separate file and run it the same way to verify the round-trip. The "GATE: migration round-trips" check is a manual verification for now.

## Before you start

**1. The feature must already exist on `main`.** Verify the manifest:

```bash
ls 03_docs/features/{nn}_{feature}/feature.manifest.yaml
```

If that's missing, build the feature first via [01_building_a_feature.md](01_building_a_feature.md).

**2. The feature's bootstrap migration must already be applied to your local database.** The schema and the shared `dim_entity_types` / `dim_attr_defs` / `dtl_attrs` tables need to exist before any sub-feature can extend them. Verify:

```bash
# Schema exists?
docker compose exec postgres psql -U tennetctl -d tennetctl -c '\dn' | grep {nn}_{feature}

# Shared tables exist?
docker compose exec postgres psql -U tennetctl -d tennetctl \
  -c '\dt "{nn}_{feature}".*' | grep -E 'dim_entity_types|dim_attr_defs|dtl_attrs'
```

The first command should print the feature's schema name. The second should print all three shared tables. If anything is missing, apply the bootstrap migration first — it lives in `03_docs/features/{nn}_{feature}/05_sub_features/00_bootstrap/09_sql_migrations/02_in_progress/`.

**3. Read the feature's `00_overview.md` and `04_architecture/01_architecture.md`** so you understand the boundaries before picking a sub-feature.

**4. Pick a `PLANNED` sub-feature from `feature.manifest.yaml`.** Avoid anything marked `BUILDING` (someone else has it) or `DONE` (already shipped — that's an enhancement, see [02_building_an_enhancement.md](02_building_an_enhancement.md)).

**5. Check no GitHub issue is already open for this sub-feature:**

```bash
gh issue list --search "{feature}/{sub_feature}"
```

If one exists and is assigned to someone else, pick a different sub-feature.

---

## The lifecycle

```
Phase 1: Open issue (optional) — Sub-Feature Build template, Scope Lock filled in
Phase 2: Write the docs        — scope, design, API contract, manifest
Phase 3: Write the migration   — SQL inside this sub-feature's 09_sql_migrations/
Phase 4: Verify the migration  — UP -> DOWN -> UP on a clean database
Phase 5: Cross-feature check   — what events does this emit/consume?
Phase 6: Tests first (RED)     — pytest tests that fail because nothing is built yet
Phase 7: Implement backend     — schemas, repository, service, routes
Phase 8: Implement frontend    — page, components, hooks
Phase 9: Robot Framework tests — API tests, then E2E tests
Phase 10: Open the PR          — self-review, merge, close issue
```

These phases match the **Sub-Feature Build** issue template's checkboxes. Keep the issue open in another tab as you work — tick boxes as you complete them.

For larger sub-features you can split this into two PRs: a docs PR (Phases 2–5) and an implementation PR (Phases 6–10). See [09_maintainer_workflow.md §Docs-First PRs](09_maintainer_workflow.md#docs-first-prs).

---

## Phase 1: Open the issue (recommended)

Opening an issue serves two purposes: it's a **coordination tool** if you're working with others, and it **enforces scope discipline** by making you fill in the Scope Lock before any code. If you're working solo, this is optional — you can skip straight to Phase 2 and fill the Scope Lock in the PR itself. For a team, opening the issue first prevents duplicated work.

If opening an issue, use the `Sub-Feature Build` issue template (`.github/ISSUE_TEMPLATE/sub_feature_build.md`):

```bash
gh issue create \
  --template sub_feature_build.md \
  --title "Build: 02_iam / 01_org — Organisations" \
  --label "feature,sub-feature,module:iam,P0" \
  --assignee @me
```

The template prompts you to fill in the **Scope Lock** (in scope, out of scope, acceptance criteria) before any code. Do not skip this. The Scope Lock is the contract — anything not listed there is not part of this PR. See [09_maintainer_workflow.md §Scope Creep Prevention](09_maintainer_workflow.md#scope-creep-prevention).

If you opened an issue: `gh issue view {N}` should show your issue with the Scope Lock filled in. Note the issue number and reference it in the PR body with `Closes #$ISSUE` to auto-close it on merge.

---

## Phase 2: Write the docs

Create the sub-feature directory and the doc files. The numbered prefixes are mandatory — see [04_folder_naming_standards.md](04_folder_naming_standards.md).

```bash
FEAT=02_iam            # the feature this sub-feature lives in
SUB=01_org             # the sub-feature you're building
SUB_DIR=03_docs/features/$FEAT/05_sub_features/$SUB

mkdir -p $SUB_DIR/09_sql_migrations/01_migrated
mkdir -p $SUB_DIR/09_sql_migrations/02_in_progress
```

**Verify it worked:** `tree $SUB_DIR` should show only the `09_sql_migrations/` subtree. Doc files come next.

### 2.1 Write `sub_feature.manifest.yaml`

```yaml
title: "Organisations"
sub_feature: "01_org"
feature: "02_iam"
status: SCOPED              # PLANNED -> SCOPED -> DESIGNED -> BUILDING -> DONE
owner: "your-github-username"
created_at: "2026-04-07"
issue: 42                   # the issue from Phase 1
description: |
  Top-level tenants in tennetctl. CRUD only — membership, roles, and
  resources are separate sub-features.
```

### 2.2 Write `01_scope.md`

This is the prose version of the issue's Scope Lock. Structure:

```markdown
# Organisations — Scope

## What it does
{2-3 sentences. The smallest possible description.}

## In scope
- {Capability 1 — observable, testable}
- {Capability 2}
- {Capability 3}

## Out of scope
- {Tempting thing that belongs in a different sub-feature — name it}
- {Future enhancement — note where it'll live}

## Acceptance criteria
- [ ] {Observable outcome 1 — should map to a test}
- [ ] {Observable outcome 2}
- [ ] {Observable outcome 3}

## Dependencies
- Depends on: {other sub-features in this or other features}
- Depended on by: {sub-features that will be blocked until this lands}
```

A wrong scope means wasted work. Get it reviewed (or, if you're maintainer, sleep on it) before moving on.

### 2.3 Write `02_design.md`

The design doc describes how the scope will be implemented. Sections:

- **Data model** — exactly which tables exist. New `fct_*` tables (with column list + types). Which `dim_*` codes get added. Which `dim_attr_defs` entries get added (these are EAV attributes — names, slugs, descriptions, settings — that go in `dtl_attrs`, NOT as columns on `fct_*` tables; see [03_database_structure.md](03_database_structure.md)). The view (`v_*`) that materialises everything for read queries.
- **Service layer** — every service function: name, inputs, outputs, business rules, which events it emits.
- **API layer** — every endpoint with method, path, request shape, response shape. Reference `05_api_contract.yaml` for the formal spec.
- **Security** — auth requirements, permission checks, RLS policies, audit events emitted on every mutation.
- **Events** — what this sub-feature emits and consumes. Schema for each event.

Update the manifest: `status: DESIGNED`.

### 2.4 Write `05_api_contract.yaml`

Minimal OpenAPI fragment for the new endpoints. Every response uses the project envelope:

```yaml
paths:
  /v1/orgs:
    get:
      summary: List organisations
      responses:
        "200":
          description: Success
          content:
            application/json:
              schema:
                type: object
                required: [ok, data]
                properties:
                  ok: { type: boolean, enum: [true] }
                  data:
                    type: array
                    items: { $ref: "#/components/schemas/Org" }
    post:
      summary: Create organisation
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/CreateOrgRequest" }
      responses:
        "201":
          description: Created
        "409":
          description: Slug already exists
```

Error envelope: `{ "ok": false, "error": { "code": "SLUG_EXISTS", "message": "..." } }`. Error codes are SCREAMING_SNAKE_CASE.

---

## Phase 3: Write the migration

Create the migration file inside this sub-feature's `09_sql_migrations/02_in_progress/`. The filename is `YYYYMMDD_{NNN}_{description}.sql` where `{NNN}` is the next available global sequence number.

Find the next number:

```bash
ls 03_docs/features/*/05_sub_features/*/09_sql_migrations/01_migrated/ \
   03_docs/features/*/05_sub_features/*/09_sql_migrations/02_in_progress/ \
   2>/dev/null \
  | grep -oE '_[0-9]{3}_' | sort -u | tail -5
```

Use the next number above the highest existing one. Two migrations with the same `{NNN}` is a hard error — the runner refuses to start.

```bash
touch $SUB_DIR/09_sql_migrations/02_in_progress/20260407_042_iam_orgs.sql
```

### What goes in the migration

For most sub-features the migration adds:

- A new `fct_*` table (the entity itself)
- New rows in the feature's existing `dim_*` tables (statuses, types) — never new columns, never `CREATE TYPE ENUM`
- New rows in `dim_attr_defs` for every property the entity has (name, slug, description, settings, etc.) — these get stored in `dtl_attrs`, never as columns on the `fct_*` table
- A `CREATE OR REPLACE VIEW v_{plural}` that materialises the EAV attributes for read queries
- An RLS policy if the table has `org_id`

Every migration must have:
- Both `-- UP =====` and `-- DOWN =====` sections
- `COMMENT ON` for every table and every column ([R-011](../03_docs/00_main/03_rules.md))
- All constraints explicitly named: `pk_*`, `fk_*`, `uq_*`, `chk_*`, `idx_*` ([R-012](../03_docs/00_main/03_rules.md))
- No triggers, no functions, no procedures, no extensions, no `CREATE TYPE ... AS ENUM`

For the exact templates, see [03_database_structure.md](03_database_structure.md).

### Decision tree: where does my data go?

```text
Is it a fixed set of codes/statuses/types?
  -> dim_* table (SMALLINT PK, seeded in migration)

Is it a new entity (org, user, project)?
  -> fct_* table (UUID PK, FK refs only, NO descriptive string columns)

Is it a descriptive property (name, email, settings, slug, description)?
  -> dim_attr_defs + dtl_attrs (NO ALTER TABLE, NO new fct_* column)

Is it an association between two entities?
  -> lnk_* table (immutable, no updated_at)

Is it admin/operator configuration?
  -> adm_* table

Is it an event/log entry?
  -> evt_* table (append-only, never updated)
```

---

## Phase 4: Verify the migration

Hard gate. Do not write any backend code until the migration round-trips cleanly on a clean database.

```bash
# 1. Apply
uv run python -m scripts.migrate up

# 2. Inspect — your new tables should exist with the right columns and comments
docker compose exec postgres psql -U tennetctl -d tennetctl \
  -c '\d+ "02_iam"."11_fct_orgs"'

# 3. Roll back
uv run python -m scripts.migrate down

# 4. Verify the rollback was clean — your new objects should be GONE
docker compose exec postgres psql -U tennetctl -d tennetctl \
  -c '\d "02_iam".*' | grep fct_orgs   # should print nothing

# 5. Re-apply — confirms UP -> DOWN -> UP round-trips cleanly
uv run python -m scripts.migrate up
```

**GATE:** if step 1 fails, fix the SQL. If step 4 shows orphan objects, your DOWN is incomplete — fix it. If step 5 fails after a clean rollback, fix it.

### When to edit in place vs. create a follow-up migration

If you discover a bug in the migration during this round-trip **before opening the PR**:
- **Edit in place** — fix the SQL file in `02_in_progress/`, re-test, and commit the fixed version. There is no "published" state yet.

If the migration is already merged and you discover a bug:
- **Create a follow-up migration** — write a new migration file in `02_in_progress/` with the next `{NNN}` number that fixes the issue. Two migrations are better than editing published history.

### Safe migration checklist

| Risk | Check |
| ---- | ----- |
| Adding `NOT NULL` column to existing table | Provide a `DEFAULT` or backfill in the same migration |
| Renaming a column | Two-step: add new → migrate data → drop old (separate PRs) |
| Dropping a column | Verify no view, no query, no application code references it |
| Changing column type | Verify existing data is compatible |
| Adding a new `entity_type_id` to `dim_entity_types` | Verify all `dtl_attrs` queries handle the new type |

Update the manifest: `status: BUILDING`.

---

## Phase 5: Cross-feature impact check

Before writing code, walk this table:

| Question | If YES |
| -------- | ------ |
| Does this emit new events? | Document the event schema in `02_design.md`. List the consuming features. |
| Do existing event consumers need updating? | File a separate issue against each consuming feature. |
| Does this add a new `entity_type` to `dim_entity_types`? | Verify `dtl_attrs` queries and views handle the new type everywhere |
| Does this add a new `scope_type` / `scope_id` usage? | Verify all scoped queries across the codebase handle it |
| Does this change an existing dim code's meaning? | Grep for the code string everywhere |

If the answer to any of these is "yes and it's complicated," document it in the PR body. Consider splitting into two sub-features.

Cross-feature communication is via events ([R-002](../03_docs/00_main/03_rules.md)). Never import another feature's service. Never JOIN across schemas in a view.

---

## Phase 6: Write tests first (RED)

Create the test directory and write tests **before** any implementation. They must fail when run — that's the RED state and proves the tests actually exercise the new code.

```bash
mkdir -p backend/tests/$FEAT/$SUB
touch backend/tests/$FEAT/__init__.py
touch backend/tests/$FEAT/$SUB/__init__.py
```

Write `backend/tests/$FEAT/$SUB/test_create_org.py`:

```python
import pytest

@pytest.mark.asyncio
async def test_create_org_success(client, auth_headers):
    """POST /v1/orgs with valid data returns 201 and the response envelope."""
    response = await client.post(
        "/api/v1/orgs",
        json={"name": "Acme Corp", "slug": "acme-corp"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["name"] == "Acme Corp"
    assert body["data"]["slug"] == "acme-corp"

@pytest.mark.asyncio
async def test_create_org_duplicate_slug(client, seeded_org, auth_headers):
    """Duplicate slug returns 409 with SLUG_EXISTS error code."""
    response = await client.post(
        "/api/v1/orgs",
        json={"name": "Other", "slug": seeded_org["slug"]},
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SLUG_EXISTS"

@pytest.mark.asyncio
async def test_create_org_missing_name(client, auth_headers):
    """Missing required field returns 400."""
    response = await client.post("/api/v1/orgs", json={"slug": "x"}, headers=auth_headers)
    assert response.status_code == 400
```

Write the rest: `test_get_org.py`, `test_list_orgs.py`, `test_update_org.py`, `test_delete_org.py`. One file per endpoint, one test function per scenario.

Run the tests:

```bash
uv run pytest backend/tests/$FEAT/$SUB/ -v
```

**Expected:** every test fails (probably with `404` or `ImportError`). This is RED. Good.

### What to test at each layer

| Layer | What to test |
| ----- | ------------ |
| API (route) | Status codes, response envelope shape, validation errors, auth required |
| Service | Business rules, edge cases, error conditions, event emission |
| Repository | Query correctness against real Postgres (no mocks) |

Tests run against the real Postgres in `docker compose`. No mocks for the database. See [07_testing_standards.md](07_testing_standards.md).

---

## Phase 7: Implement the backend

Create the 5-file module structure ([05_backend_api_standards.md](05_backend_api_standards.md)):

```bash
mkdir -p backend/02_features/$FEAT/$SUB
touch backend/02_features/$FEAT/__init__.py
touch backend/02_features/$FEAT/$SUB/__init__.py
touch backend/02_features/$FEAT/$SUB/{schemas,repository,service,routes}.py
```

### `schemas.py` — Pydantic v2

Request and response models matching the API contract. Separate models for create/update/response — never reuse one model for both directions.

### `repository.py` — raw SQL only

One function per query. No business logic. Returns typed dicts. Every function has a docstring. Every UPDATE includes `updated_at = CURRENT_TIMESTAMP, updated_by = $actor_id`. No ORM, only `asyncpg` raw SQL ([R-005](../03_docs/00_main/03_rules.md)).

### `service.py` — business logic

Calls `repository.py`. Calls `emit_event()` for every mutating operation ([R-016](../03_docs/00_main/03_rules.md)). Raises typed exceptions from `01_core/exceptions.py`. Never issues raw SQL directly. Never imports another feature's service ([R-002](../03_docs/00_main/03_rules.md)).

### `routes.py` — FastAPI router

Validates with Pydantic. Calls the service layer. Returns the response envelope. No business logic. No SQL.

### Run tests

```bash
uv run pytest backend/tests/$FEAT/$SUB/ -v
```

**Expected:** every test passes. This is GREEN. Update the manifest if you split into a docs PR earlier — `status: BUILDING` should already be set.

If you can't get tests to pass without changing them, the test was probably wrong. Fix the test. But first ask yourself whether the implementation is wrong — usually it is.

---

## Phase 8: Implement the frontend

```bash
mkdir -p frontend/src/app/$FEAT/$SUB
mkdir -p frontend/src/features/$FEAT/$SUB/components
mkdir -p frontend/src/features/$FEAT/$SUB/hooks
```

Build:

- `app/$FEAT/$SUB/page.tsx` — list view (Server Component by default)
- `app/$FEAT/$SUB/[id]/page.tsx` — detail view
- `features/$FEAT/$SUB/components/{Entity}List.tsx`, `{Entity}Form.tsx`, `{Entity}Detail.tsx`
- `features/$FEAT/$SUB/hooks/use{Entity}.ts` — TanStack Query hooks (queries + mutations)

Rules ([06_frontend_standards.md](06_frontend_standards.md)):
- shadcn/ui components, no other UI libraries
- Server components by default, `"use client"` only when needed
- React Hook Form + Zod, Zod schemas mirror the Pydantic models
- TanStack Query for all data fetching
- TypeScript strict mode, never `any`

**Verify it worked:** run `npm run dev` and click through the new pages manually. Create, list, edit, delete — does it round-trip?

---

## Phase 9: Robot Framework tests

API tests live alongside the unit tests. E2E tests live under `tests/e2e/`.

### API tests

```bash
mkdir -p tests/e2e/$FEAT
touch tests/e2e/$FEAT/${SUB}_api.robot
```

```robotframework
*** Settings ***
Library     RequestsLibrary
Suite Setup    Create Session    api    http://localhost:51734

*** Test Cases ***
Create Organisation Successfully
    [Documentation]    POST /v1/orgs creates an org
    ${body}=    Create Dictionary    name=RF Org    slug=rf-org
    ${response}=    POST On Session    api    /api/v1/orgs    json=${body}
    Status Should Be    201    ${response}
    Should Be True    ${response.json()}[ok]
```

### E2E tests

Cover the full user journey through the browser using the Robot Framework Browser library. **Never** use `@playwright/test` directly — see [07_testing_standards.md](07_testing_standards.md).

```bash
touch tests/e2e/$FEAT/${SUB}_e2e.robot
```

Run:
```bash
uv run robot tests/e2e/$FEAT/
```

---

## Phase 10: Open the PR

### Merge conflicts on global migration sequence numbers

If another PR merges to `main` before yours and uses the same migration `{NNN}` number, you'll have a conflict:

1. **Rename your migration** to the next available `{NNN}` above the highest on `main`
2. **Force-push your branch** — `git push -f origin your-branch`
3. **Re-run Phase 4** (verify migration) to ensure it still round-trips with the new number

The migration runner uses global sequence order, so gaps and out-of-order numbers are fine — only duplicates cause errors. If two PRs race for the same number, the one that merges first wins; the second PR must rename.

---

Update the sub-feature manifest one last time:

```yaml
status: DONE
completed_at: "2026-04-07"
```

Update the parent feature manifest (`03_docs/features/$FEAT/feature.manifest.yaml`):

```yaml
sub_features:
  - number: 01
    name: org
    status: DONE          # ← updated from BUILDING
    completed_at: "2026-04-07"
```

Commit and open the PR:

```bash
git checkout -b feat/$FEAT-$SUB
git add .
git commit -m "feat($FEAT): implement $SUB — {short description}"
git push -u origin feat/$FEAT-$SUB

gh pr create \
  --title "feat($FEAT): implement $SUB — {short description}" \
  --body "$(cat <<EOF
## What this PR does
{2-3 sentences}

Closes #$ISSUE

## Sub-feature
Feature: $FEAT
Sub-feature: $SUB

## Database changes
- [ ] New dim_* rows: {list or "none"}
- [ ] New fct_* tables: {list or "none"}
- [ ] New dim_attr_defs entries: {list attr codes or "none"}
- [ ] New lnk_* tables: {list or "none"}
- [ ] New views: {list or "none"}

## Cross-feature impact
- [ ] New events emitted: {list or "none"}
- [ ] Consumer features affected: {list or "none"}
- [ ] New entity_type / scope_type entries: {list or "none"}

## Rollback plan
- [ ] Migration DOWN tested and confirmed working
- [ ] Rollback steps: {e.g. "revert migration, no data loss"}
- [ ] Breaking changes: {list or "none"}

## Testing
- [ ] pytest tests added and passing
- [ ] Robot Framework API tests added and passing
- [ ] Robot Framework E2E tests added (if user-facing)
- [ ] Tested manually: {what you clicked through}

## Checklist
- [ ] Scope, design, manifest, API contract docs complete
- [ ] sub_feature.manifest.yaml status: DONE
- [ ] feature.manifest.yaml updated
- [ ] No file exceeds 500 lines
- [ ] Every new function has a docstring
- [ ] Migration has UP and DOWN (round-trip verified)
- [ ] Audit events emitted for all mutating operations
- [ ] Properties stored in dtl_attrs, not fct_* columns
- [ ] No triggers, ENUMs, stored procedures
- [ ] Cross-feature impact documented (or confirmed none)
EOF
)"
```

### Self-review

Wait at least 30 minutes after opening the PR. Then review your own diff on GitHub (not in your editor — the GitHub diff view shows what reviewers see). Walk the full checklist from [09_maintainer_workflow.md §Self-Review Process](09_maintainer_workflow.md#self-review-process). Run the `code-reviewer` and `security-reviewer` agents.

Merge only after every checklist item is verified. The issue auto-closes via `Closes #$ISSUE`.

Tick the matching box on the parent feature issue.

---

## Common mistakes

| Mistake | Correct approach |
| ------- | ---------------- |
| Adding a `name` column to a `fct_*` table | Register in `dim_attr_defs`, store in `dtl_attrs`, materialise in the view |
| `CREATE TYPE ... AS ENUM` for status | Always a `dim_*` lookup table |
| Trigger for `updated_at` | Set explicitly in every repository UPDATE statement |
| Cross-schema JOIN in a view | Use events or call through `01_core/` |
| Skipping the DOWN migration | DOWN must completely revert UP, verified by round-trip |
| Importing another feature's service | Emit an event; the other feature subscribes |
| `is_deleted BOOLEAN` | Always `deleted_at TIMESTAMP` |
| Starting Phase 7 (backend) before Phase 4 (migration verified) | Migration is a hard gate. A wrong schema means rewriting code later. |
| Building two sub-features in parallel | Finish one completely before starting the next. Migration numbers and scope creep both bite. |
| Adding "while I'm here" cleanups to the PR | Log them in the issue's Scope Creep Log. Open separate issues. Stay on scope. |

---

## Where to go from here

- New top-level feature: [01_building_a_feature.md](01_building_a_feature.md)
- Enhancing an already-merged sub-feature: [02_building_an_enhancement.md](02_building_an_enhancement.md)
- Database conventions: [03_database_structure.md](03_database_structure.md)
- Backend module structure: [05_backend_api_standards.md](05_backend_api_standards.md)
- Frontend conventions: [06_frontend_standards.md](06_frontend_standards.md)
- Testing: [07_testing_standards.md](07_testing_standards.md)
- Self-review and PR discipline: [09_maintainer_workflow.md](09_maintainer_workflow.md)
- Worked example (Vault, hypothetical): [10_day_one_workflow.md](10_day_one_workflow.md)
- Worked example (IAM, real): [11_iam_build_plan.md](11_iam_build_plan.md)
