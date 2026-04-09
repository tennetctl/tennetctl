# Building an Enhancement

Guide for enhancing an already-merged sub-feature. Enhancements modify existing behaviour — they do not create new sub-features from scratch and they do not stand up new top-level features.

> **Vocabulary**
> - **Feature** — a top-level domain (IAM, Vault, …). Adding a new one: [01_building_a_feature.md](01_building_a_feature.md).
> - **Sub-feature** — a unit of work inside a feature (e.g. `02_iam/08_auth`). Building a new one: [01a_building_a_sub_feature.md](01a_building_a_sub_feature.md).
> - **Enhancement** — a change to a sub-feature that's already been merged. **You're here.**

If you're building something entirely new, use [01a_building_a_sub_feature.md](01a_building_a_sub_feature.md) instead.

> **The migration runner does not exist yet.** Step 4 below runs `uv run python -m scripts.migrate up`. There is no `scripts/migrate.py` in the repo today. Until the runner lands, apply migrations by hand: `docker compose exec postgres psql -U tennetctl -d tennetctl -f /path/to/migration.sql`, then run the DOWN section the same way to verify the round-trip manually.

---

## When Is It an Enhancement?

| Scenario | Type |
| -------- | ---- |
| Adding MFA to the auth sub-feature | Enhancement |
| Adding a new filter to an existing list endpoint | Enhancement |
| Adding a new EAV attribute to an existing entity | Enhancement |
| Building an entirely new sub-feature (e.g., API Keys) | Feature -> use [01a_building_a_sub_feature.md](01a_building_a_sub_feature.md) |

---

## The 9-Step Enhancement Workflow

```text
1. Identify the sub-feature being enhanced
2. Document the change (scope delta)
3. Plan database changes
4. Verify migration locally (if DB changes)
   -- GATE: UP -> DOWN -> UP round-trips cleanly?
5. Check cross-module impact
6. Write tests first (TDD -- RED)
7. Implement the change (GREEN)
8. Update documentation
9. Open a PR (with rollback plan)
```

---

## Step 1: Identify the Sub-Feature

Find the existing sub-feature in `03_docs/features/{module}/05_sub_features/{nn}_{sub_feature}/`.

Read the existing docs:

- `01_scope.md` — understand what's in scope
- `02_design.md` — understand the current design
- `03_architecture.md` — understand the current architecture
- `05_api_contract.yaml` — understand the current API

---

## Step 2: Document the Change

Create or update `08_worklog.md` in the sub-feature directory with an entry:

```markdown
## YYYY-MM-DD — Enhancement: {title}

### What changed
{2-3 sentences describing the enhancement}

### Why
{Motivation — bug report, user feedback, new requirement}

### Database changes
- New dim entries: {list or "none"}
- New attr_defs: {list attribute codes or "none"}
- New tables: {list or "none"}
- Modified views: {list or "none"}

### API changes
- New endpoints: {list or "none"}
- Modified endpoints: {list or "none"}
- New request/response fields: {list or "none"}
```

If the enhancement changes the scope significantly, update `01_scope.md` as well.

---

## Step 3: Plan Database Changes

### Adding a New Property to an Existing Entity

This is the most common enhancement. **Do NOT alter the fct_* table.**

```sql
-- 1. Register the new attribute
INSERT INTO "{schema}".07_dim_attr_defs
    (id, entity_type_id, code, label, value_type, is_required, is_unique, description)
VALUES (next_id, entity_type, 'new_attr', 'New Attribute', 'text', false, false, 'Description.');

-- 2. Update the view to materialize it
-- In v_{entity}, add:
MAX(CASE WHEN ad.code = 'new_attr' THEN a.key_text END) AS new_attr,
```

### Adding a New Status or Type

Add a row to the existing `dim_*` table:

```sql
INSERT INTO "{schema}".{nn}_dim_{name} (id, code, label, description)
VALUES (next_id, 'new_code', 'New Label', 'Description.');
```

### Adding a New Lookup Table

Only if you need an entirely new category of codes. Follow the `dim_*` template.

### Adding a New Association

Use a `lnk_*` table. See [03_database_structure.md](03_database_structure.md) for the template.

### Decision Tree

```text
Adding a property (name, label, URL, config)?
  -> dim_attr_defs + dtl_attrs. NO ALTER TABLE.

Adding a new status/type code?
  -> INSERT into existing dim_* table.

Adding a new relationship between entities?
  -> New lnk_* table.

Changing existing column type or constraint?
  -> Migration with UP and DOWN. Get review first.
```

---

## Step 4: Verify Migration Locally

If your enhancement includes database changes, prove the migration works before writing code:

```bash
# Apply the migration
uv run python -m scripts.migrate up

# Inspect the changed tables
docker compose exec postgres psql -U tennetctl -d tennetctl \
  -c '\d+ "{schema}".{table_name}'

# Roll back
uv run python -m scripts.migrate down

# Re-apply — confirms round-trip
uv run python -m scripts.migrate up
```

**GATE:** If the migration fails, or DOWN doesn't cleanly revert UP, fix it before proceeding.

Skip this step only if your enhancement has zero database changes (e.g., adding a validation rule or filter).

---

## Step 5: Check Cross-Module Impact

| Question | If YES |
| -------- | ------ |
| Does this emit new events? | Document the event schema in `02_design.md`. List consuming modules. |
| Do existing event consumers need updating? | File an issue against the consuming module. |
| Does this change an existing dim code's meaning? | Check all code that references that code by string. |
| Does this add a new `entity_type` to `dim_entity_types`? | Verify `dtl_attrs` queries and views handle it. |

If there is cross-module impact, document it in the PR body.

---

## Step 6: Write Tests First (TDD)

Add tests to the existing test file or create a new one:

```text
backend/tests/{module}/{sub_feature}/test_{enhancement}.py
```

```python
async def test_new_property_returned_in_response(client, seeded_entity):
    """The new attribute appears in the GET response."""
    response = await client.get(f"/api/v1/{module}/{entity}/{seeded_entity.id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "new_attr" in data

async def test_new_property_can_be_set(client, seeded_entity):
    """The new attribute can be set via PATCH."""
    response = await client.patch(
        f"/api/v1/{module}/{entity}/{seeded_entity.id}",
        json={"new_attr": "value"}
    )
    assert response.status_code == 200
```

Run tests — they must fail (RED).

---

## Step 7: Implement the Change

### For New EAV Properties

1. **Repository:** Add `set_attr()` / `get_attr()` calls or update existing bulk attribute handlers
2. **Service:** Add business logic for the new property (validation, defaults, events)
3. **Schemas:** Add the field to the Pydantic response/request models
4. **Routes:** No change needed if using existing CRUD endpoints

### For New Endpoints

1. Add route to `routes.py`
2. Add service function to `service.py`
3. Add repository function to `repository.py`
4. Add Pydantic models to `schemas.py`

### For Modified Endpoints

1. Update Pydantic models in `schemas.py`
2. Update service logic in `service.py`
3. Update queries in `repository.py` if needed
4. Emit audit events for any new mutating operations

Run tests — they must pass (GREEN).

---

## Step 8: Update Documentation

Update these files in the sub-feature directory:

| File | Update |
| ---- | ------ |
| `01_scope.md` | If scope changed |
| `02_design.md` | If design changed |
| `05_api_contract.yaml` | If API changed |
| `08_worklog.md` | Always — add the enhancement entry |

If you added new `dim_attr_defs` entries, document them in `02_design.md` under the Data Model section.

If the enhancement is significant, update `sub_feature.manifest.yaml` with a note.

---

## Step 9: Open a PR

PR title: `feat: {enhancement description}` or `fix: {bug description}`

PR body:

```markdown
## What this PR does
{2-3 sentences}

## Sub-feature enhanced
Module: {module}
Sub-feature: {nn}_{name}

## Database changes
- [ ] New dim_* entries: {list or "none"}
- [ ] New attr_defs: {list attr codes or "none"}
- [ ] New tables: {list or "none"}
- [ ] Modified views: {list or "none"}
- [ ] ALTER TABLE changes: {list or "none" — should be rare}

## Cross-module impact
- [ ] New events emitted: {list or "none"}
- [ ] Consumer modules affected: {list or "none"}

## Rollback plan
- [ ] Migration DOWN tested and confirmed working
- [ ] Rollback steps: {e.g. "revert migration, no data loss"}
- [ ] Breaking changes: {list or "none — safe to roll back"}

## Testing
- [ ] New tests added for the enhancement
- [ ] Existing tests still passing
- [ ] Tested manually: {what you tested}

## Screenshots
{Before/after screenshots for any UI changes}

## Checklist
- [ ] worklog.md updated
- [ ] API contract updated (if endpoints changed)
- [ ] No file exceeds 500 lines
- [ ] Audit events emitted for new mutating operations
- [ ] Properties stored in dtl_attrs, not fct_* columns
- [ ] Migration round-trip verified (if DB changes)
- [ ] Cross-module impact documented (or confirmed none)
```

---

## Enhancement vs. Feature — Quick Decision

| Question | If YES -> Enhancement | If YES -> Feature |
| -------- | --------------------- | ----------------- |
| Does it modify an existing sub-feature? | Yes | |
| Does it add a new entity type? | | Yes |
| Does it need a new sub-feature directory? | | Yes |
| Is it a new property on an existing entity? | Yes | |
| Is it a new endpoint on an existing resource? | Yes | |
| Is it an entirely new resource/concept? | | Yes |

---

## Common Enhancement Patterns

### Pattern 1: Add a property to an entity

```text
dim_attr_defs INSERT -> dtl_attrs stores values -> view updated -> schema updated -> test -> done
```

### Pattern 2: Add a status transition

```text
dim_* INSERT -> service logic for transition -> audit event -> test -> done
```

### Pattern 3: Add a filter to a list endpoint

```text
Update repository query -> update route query params -> update schema -> test -> done
```

### Pattern 4: Add a validation rule

```text
Update service logic -> update Pydantic schema -> test -> done
```
