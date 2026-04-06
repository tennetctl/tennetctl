# Plan: Rebuild Org Attributes to Per-Row EAV

## Overview

Replace the single `settings` JSONB blob (attr_def_id=12) with proper per-row EAV attributes. Add `description` (id=13, text) and `tags` (id=14, jsonb array) as system attrs. Custom attrs auto-register in `dim_attr_defs` at id>=1000. New sub-resource endpoints `/v1/orgs/{id}/attrs` for per-key CRUD. Frontend switches from bulk PATCH to per-attr PUT/DELETE.

## Phases

---

### Phase 1: Migration + Backend (TDD)

**Risk: Medium** — touches live data, view rebuild, new endpoints.

#### Step 1.1: Write new migration

**File:** `tennetctl/03_docs/features/02_iam/05_sub_features/01_org/09_sql_migrations/02_in_progress/20260403_002_org_eav_per_row.sql`

UP section:
1. Add `is_system` BOOLEAN NOT NULL DEFAULT true column to `dim_attr_defs` (all existing rows are system).
2. INSERT attr_def id=13 (entity_type_id=2, code='description', value_type='text', is_system=true).
3. INSERT attr_def id=14 (entity_type_id=2, code='tags', value_type='jsonb', is_system=true).
4. Migrate the existing settings blob for the one org:
   - Query the settings JSONB from `20_dtl_attrs` where attr_def_id=12.
   - For `__tags__` key: INSERT into `20_dtl_attrs` with attr_def_id=14, key_jsonb = the array.
   - For `region` key: INSERT into `dim_attr_defs` (id=1000, entity_type_id=2, code='region', value_type='text', is_system=false). INSERT into `20_dtl_attrs` with attr_def_id=1000, key_text='us-east-1'.
   - For `limits` key: INSERT into `dim_attr_defs` (id=1001, entity_type_id=2, code='limits', value_type='jsonb', is_system=false). INSERT into `20_dtl_attrs` with attr_def_id=1001, key_jsonb=the limits object.
5. DELETE the settings blob row from `20_dtl_attrs` (attr_def_id=12).
6. Deprecate attr_def id=12: `UPDATE dim_attr_defs SET deprecated_at = CURRENT_TIMESTAMP WHERE id = 12`.
7. Add sequence for custom attr IDs: `CREATE SEQUENCE "02_iam".seq_custom_attr_defs START 1002 INCREMENT 1`.
8. DROP VIEW `v_orgs`, recreate with:
   - Same id, is_active, is_test, status, deleted_at, created_by, updated_by, created_at, updated_at.
   - `slug` (attr_def_id=10, key_text).
   - `display_name` (attr_def_id=11, key_text).
   - `description` (attr_def_id=13, key_text) -- new.
   - `tags` (attr_def_id=14, key_jsonb) -- new, returns JSONB array.
   - `custom_attrs` -- JSONB object aggregating all non-system attr rows: `jsonb_object_agg(ad.code, COALESCE(a.key_text, a.key_jsonb::text))` filtered by `ad.is_system = false`.

DOWN section:
- Reverse all of the above. Recreate the original v_orgs. Remove sequence. Remove is_system column. Restore settings blob row. Delete attr_defs 13, 14, 1000, 1001.

**Dependencies:** None.

#### Step 1.2: Write failing tests for new attr endpoints

**File:** `tennetctl/01_backend/tests/02_iam/01_org/test_org_attrs.py`

Tests (all `@pytest.mark.integration`, async):
1. `test_list_org_attrs` -- GET /v1/orgs/{id}/attrs returns system attrs (slug, display_name) as list.
2. `test_upsert_text_attr` -- PUT /v1/orgs/{id}/attrs/region with `{value: "eu-west-1", value_type: "text"}` creates attr, GET returns it.
3. `test_upsert_jsonb_attr` -- PUT /v1/orgs/{id}/attrs/limits with jsonb value, GET returns it.
4. `test_upsert_description` -- PUT /v1/orgs/{id}/attrs/description with text value (system attr, allowed).
5. `test_upsert_tags` -- PUT /v1/orgs/{id}/attrs/tags with jsonb array value.
6. `test_delete_custom_attr` -- DELETE /v1/orgs/{id}/attrs/region returns 204, attr gone from list.
7. `test_delete_system_attr_forbidden` -- DELETE /v1/orgs/{id}/attrs/slug returns 403/400.
8. `test_get_org_has_new_shape` -- GET /v1/orgs/{id} returns description, tags, custom_attrs; no settings field.

**Dependencies:** Step 1.1 must be applied to test DB.

#### Step 1.3: Update existing tests

**File:** `tennetctl/01_backend/tests/02_iam/01_org/test_org.py`

Changes:
- `test_create_org_with_settings`: REMOVE entirely (settings field no longer exists on create).
- All tests referencing `settings` in assertions: remove those assertions.
- `OrgCreate` and `OrgUpdate` no longer accept `settings` -- tests that pass it will 422. Adjust.
- Add assertion in `test_get_org_by_id` that response has `description`, `tags`, `custom_attrs` keys.

**Dependencies:** Steps 1.1, 1.2.

#### Step 1.4: Update schemas

**File:** `tennetctl/01_backend/02_features/02_iam/01_org/schemas.py`

Changes:
- `OrgCreate`: remove `settings` field.
- `OrgUpdate`: remove `settings` field.
- `OrgResponse`: remove `settings`, add `description: str | None = None`, `tags: list[str] = []`, `custom_attrs: dict[str, Any] = {}`.
- Add new schemas:
  - `OrgAttrResponse(BaseModel)`: key: str, value: Any, value_type: str, is_system: bool.
  - `OrgAttrUpsert(BaseModel)`: value: Any, value_type: str = Field(pattern="^(text|jsonb)$").

**Dependencies:** None (but tests from 1.2/1.3 depend on this).

#### Step 1.5: Update repository

**File:** `tennetctl/01_backend/02_features/02_iam/01_org/repository.py`

Changes:
- Remove `ATTR_SETTINGS = 12` constant.
- Add constants: `ATTR_DESCRIPTION = 13`, `ATTR_TAGS = 14`.
- Add `SYSTEM_ATTR_IDS = {10, 11, 13, 14}` set.
- Add `async def list_attrs(conn, org_id: str) -> list[dict]`:
  ```sql
  SELECT ad.code AS key, ad.value_type, ad.is_system,
         COALESCE(a.key_text, a.key_jsonb::text) AS value
  FROM "02_iam"."20_dtl_attrs" a
  JOIN "02_iam".dim_attr_defs ad ON ad.id = a.attr_def_id
  WHERE a.entity_type_id = 2 AND a.entity_id = $1
  ORDER BY ad.is_system DESC, ad.code
  ```
- Add `async def get_or_create_attr_def(conn, code: str, value_type: str) -> int`:
  - SELECT id FROM dim_attr_defs WHERE entity_type_id=2 AND code=$1.
  - If found, return id.
  - If not found, INSERT with id=nextval('seq_custom_attr_defs'), is_system=false. Return id.
- Add `async def delete_attr_by_code(conn, entity_id: str, code: str) -> bool`:
  - DELETE FROM 20_dtl_attrs WHERE ... AND attr_def_id = (SELECT id FROM dim_attr_defs WHERE entity_type_id=2 AND code=$1). Return True if rowcount > 0.
- Add `async def is_system_attr(conn, code: str) -> bool`:
  - SELECT is_system FROM dim_attr_defs WHERE entity_type_id=2 AND code=$1.
- Update `_row_to_dict`: remove settings JSON parsing. Add handling for `tags` (parse if string), `custom_attrs` (parse if string).

**Dependencies:** Step 1.1 (needs is_system column, new attr_defs, sequence).

#### Step 1.6: Update service

**File:** `tennetctl/01_backend/02_features/02_iam/01_org/service.py`

Changes:
- `create_org`: remove `settings` parameter and `upsert_jsonb_attr` call for settings.
- `update_org`: remove `settings` parameter and `upsert_jsonb_attr` call for settings.
- Add `async def list_org_attrs(conn, org_id: str) -> list[dict]`:
  - Verify org exists (raise NotFoundError). Call `_repo.list_attrs(conn, org_id)`.
- Add `async def upsert_org_attr(conn, org_id: str, *, key: str, value: Any, value_type: str, actor_id: str | None = None) -> dict`:
  - Verify org exists.
  - `attr_def_id = await _repo.get_or_create_attr_def(conn, key, value_type)`.
  - Call `upsert_text_attr` or `upsert_jsonb_attr` based on value_type.
  - Emit audit event (ACTION_UPDATE, metadata={attr_key: key}).
  - Return updated org.
- Add `async def delete_org_attr(conn, org_id: str, *, key: str, actor_id: str | None = None) -> None`:
  - Verify org exists.
  - Check `is_system_attr` -- if true, raise ValidationError("Cannot delete system attribute").
  - Call `_repo.delete_attr_by_code(conn, org_id, key)`.
  - Emit audit event.

**Dependencies:** Step 1.5.

#### Step 1.7: Update routes

**File:** `tennetctl/01_backend/02_features/02_iam/01_org/routes.py`

Changes:
- `create_org`: remove `settings=body.settings` from service call.
- `update_org`: remove `settings=body.settings` from service call.
- Add 3 new routes on the SAME router:
  ```python
  @router.get("/{org_id}/attrs")
  async def list_org_attrs(org_id: str): ...

  @router.put("/{org_id}/attrs/{key}")
  async def upsert_org_attr(org_id: str, key: str, body: _schemas.OrgAttrUpsert): ...

  @router.delete("/{org_id}/attrs/{key}", status_code=204)
  async def delete_org_attr(org_id: str, key: str): ...
  ```
- All follow same pattern: pool.acquire() -> conn -> service call -> _core_resp.ok() or 204.

**Dependencies:** Steps 1.4, 1.6.

#### Step 1.8: Apply migration + run tests

- Apply migration: `psql -d tennetctl -f .../20260403_002_org_eav_per_row.sql`
- Run: `cd tennetctl && .venv/bin/python -m pytest 01_backend/tests/02_iam/01_org/ -v`
- All tests in test_org.py and test_org_attrs.py must pass.

**Dependencies:** All previous steps.

---

### Phase 2: Frontend

**Risk: Low** — UI changes only, no new pages, no breaking list page.

#### Step 2.1: Update types

**File:** `tennetctl/02_frontend/src/types/api.ts`

Changes:
- `Org` type: remove `settings`, add `description: string | null`, `tags: string[]`, `custom_attrs: Record<string, unknown>`.
- `OrgCreatePayload`: remove `settings`.
- `OrgUpdatePayload`: remove `settings`.
- Add `OrgAttr` type: `{ key: string; value: unknown; value_type: "text" | "jsonb"; is_system: boolean }`.
- Add `OrgAttrUpsertPayload`: `{ value: unknown; value_type: "text" | "jsonb" }`.

**Dependencies:** Phase 1 complete.

#### Step 2.2: Update hooks

**File:** `tennetctl/02_frontend/src/features/iam/hooks/use-orgs.ts`

Changes:
- Add `useOrgAttrs(orgId: string)` -- GET /v1/orgs/{orgId}/attrs, queryKey: [...ORGS_KEY, orgId, "attrs"].
- Add `useUpsertOrgAttr(orgId: string)` -- PUT mutation, invalidates ORGS_KEY and attrs key.
- Add `useDeleteOrgAttr(orgId: string)` -- DELETE mutation, invalidates same.

**Dependencies:** Step 2.1.

#### Step 2.3: Update detail page

**File:** `tennetctl/02_frontend/src/app/iam/orgs/[id]/page.tsx`

Changes:
- Remove `settingsToRows`, `rowsToSettings` functions.
- `AttrEditor`: replace bulk settings approach. Now:
  - Calls `useOrgAttrs(id)` to fetch attrs.
  - Each row save calls `useUpsertOrgAttr` with PUT /attrs/{key}.
  - Each row delete calls `useDeleteOrgAttr` with DELETE /attrs/{key}.
  - System attrs (slug, display_name) shown read-only or excluded.
- `TagsEditor`: save calls `useUpsertOrgAttr` with key="tags", value_type="jsonb".
- `handleSaveAttrs` and `handleSaveTags` no longer go through PATCH /v1/orgs/{id}.
- Remove all references to `org.settings`.
- Add description display (simple text, editable inline via PUT /attrs/description).

**Dependencies:** Step 2.2.

---

## Testing Strategy

| Phase | Type | Runner | Target |
|-------|------|--------|--------|
| 1 | Integration (API) | pytest | test_org.py (updated), test_org_attrs.py (new) |
| 2 | Manual verification | Browser | Detail page attr editor, tags, list page unchanged |
| 2 | E2E | Robot Framework | Existing org E2E tests still pass (if any) |

## Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Migration data loss (settings blob deleted before split) | High | Migration does INSERT of split rows BEFORE DELETE of blob row, all in single transaction |
| Custom attr_def ID collisions | Low | Sequence `seq_custom_attr_defs` starts at 1002, well above system range |
| v_orgs view custom_attrs aggregation perf | Low | Only triggered on orgs with custom attrs; low cardinality |
| Frontend breaks if backend not deployed | Medium | Phase 2 depends on Phase 1; deploy backend first |
| Existing E2E tests reference settings | Medium | Update/remove those assertions in Phase 1 step 1.3 |

## File Change Summary

| File | Action |
|------|--------|
| `tennetctl/03_docs/.../20260403_002_org_eav_per_row.sql` | NEW -- migration |
| `tennetctl/01_backend/tests/.../test_org_attrs.py` | NEW -- attr endpoint tests |
| `tennetctl/01_backend/tests/.../test_org.py` | MODIFY -- remove settings refs |
| `tennetctl/01_backend/.../schemas.py` | MODIFY -- remove settings, add new schemas |
| `tennetctl/01_backend/.../repository.py` | MODIFY -- new functions, remove ATTR_SETTINGS |
| `tennetctl/01_backend/.../service.py` | MODIFY -- new attr service functions |
| `tennetctl/01_backend/.../routes.py` | MODIFY -- new attr routes |
| `tennetctl/02_frontend/src/types/api.ts` | MODIFY -- new types |
| `tennetctl/02_frontend/src/features/iam/hooks/use-orgs.ts` | MODIFY -- new hooks |
| `tennetctl/02_frontend/src/app/iam/orgs/[id]/page.tsx` | MODIFY -- per-attr editor |
