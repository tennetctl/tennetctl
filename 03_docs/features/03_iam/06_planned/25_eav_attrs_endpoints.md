## Planned: EAV Attrs REST Endpoints

**Severity if unbuilt:** MEDIUM (frontend cannot read/write profile/settings fields)
**Depends on:** users, workspaces, orgs sub-features (built); groups (17_groups.md)

## Problem

All entities (users, orgs, workspaces, groups) store their attributes in
EAV `dtl_attrs` tables, but no entity currently exposes a generic attrs REST
API. The frontend has no way to read profile fields (display name, avatar
URL, preferences) or write workspace settings without hardcoded internal
service calls.

## Scope when built

### Endpoint shape (same for all entities)

```
GET    /v1/{entity}/{id}/attrs          — list all user-visible attrs
PUT    /v1/{entity}/{id}/attrs/{key}    — upsert attr value
DELETE /v1/{entity}/{id}/attrs/{key}    — delete attr
```

Where `{entity}` ∈ `users`, `orgs`, `workspaces`, `groups`.

### Design decisions to resolve before building

1. **Writable vs system-only attrs**: `dim_attr_defs` needs a new column
   `is_user_writable BOOLEAN DEFAULT false`. System attrs (`password_hash`,
   `token_hash`, `last_seen_at`) are never writable or readable via this API.
   Only attrs with `is_user_writable = true` are exposed.

2. **Permission model**: Who can write?
   - User's own attrs: user themselves (requires scope check `user_id == token.sub`)
   - Workspace attrs: workspace admin or org admin
   - Org attrs: org admin or platform admin
   - Use RBAC dependency once 16_rbac.md is built; stub with is-owner check initially.

3. **Type validation**: Infer from `attr_def.value_column`:
   - `key_text`: accept any string, max 2000 chars
   - `key_jsonb`: must be valid JSON
   - `key_smallint`: must resolve to a valid dim table FK (validate against
     a `dim_table` column on `dim_attr_defs`)

4. **GET filter**: Never return attrs where `is_user_writable = false` AND
   caller is not platform admin. Prevents leaking internal system fields.

### Repository (shared utility, not per-entity)

```python
# 04_backend/01_core/attrs_repo.py

async def list_attrs(conn, *, entity_type: str, entity_id: str) -> list[dict]: ...
async def upsert_attr(conn, *, entity_type: str, entity_id: str, key: str, value: Any) -> dict: ...
async def delete_attr(conn, *, entity_type: str, entity_id: str, key: str) -> None: ...
```

Routes for each entity call the shared repo with their entity_type string.

## Not in scope here

- Bulk attr update (patch multiple keys in one request)
- Attr history / versioning
- Attr access logging in audit (add when RBAC is in place)
