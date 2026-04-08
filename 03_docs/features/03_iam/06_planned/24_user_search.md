## Planned: User Search and Filtering

**Severity if unbuilt:** MEDIUM (admin UX breaks at >50 users without search)
**Depends on:** users sub-feature (built)

## Problem

`GET /v1/users` supports `limit` and `offset` only. There is no way to
search by email or username, or filter by status or date range. Any org with
more than a few dozen users becomes unmanageable in the admin UI.

## Scope when built

### Endpoint changes

`GET /v1/users` gains additional query params:

```
q           — full-text search against username + email (case-insensitive prefix match)
status      — filter by is_active: active | inactive | all (default: active)
created_after   — ISO timestamp
created_before  — ISO timestamp
```

### DB approach

The simplest correct approach (no extra index needed for small-to-medium installs):

```sql
WHERE (
  a_username.key_text ILIKE $1 || '%'
  OR a_email.key_text ILIKE $1 || '%'
)
```

For larger installs (>100k users): add `pg_trgm` GIN index on the two
attr values and switch to `%` + `similarity()`. Document this as a migration
step, not the default.

### Repository function signature

```python
async def search_users(
    conn,
    *,
    q: str | None = None,
    status: str = "active",        # active | inactive | all
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
```

## Not in scope here

- Full-text Postgres `tsvector` search (overkill until user counts justify it)
- Elasticsearch / external search index
- Export to CSV (part of audit/compliance export)
