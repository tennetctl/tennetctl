# Org — User Guide

## What is an Org?

An **Organisation** (Org) is the top-level tenant in tennetctl. Every workspace, group, user membership, and access policy is scoped under an org. Think of it as a company or team account.

## Creating an Org

```http
POST /v1/orgs
Content-Type: application/json

{
  "slug": "acme-corp",
  "display_name": "Acme Corporation",
  "settings": {}
}
```

- `slug` must be **globally unique**, URL-safe (`[a-z0-9-]+`), 2–64 characters.
- `slug` **cannot be changed** after creation.
- Returns `201 Created` with the full org object.

## Listing Orgs

```http
GET /v1/orgs?limit=20&offset=0&status=active
```

| Query param | Default | Notes |
|-------------|---------|-------|
| `limit` | 20 | 1–100 |
| `offset` | 0 | — |
| `status` | — | `active`, `suspended`, `trialing` |
| `include_deleted` | `false` | Includes soft-deleted orgs |
| `include_test` | `false` | Includes test orgs |

## Getting a Single Org

```http
GET /v1/orgs/{org_id}
```

Returns `404` if not found or soft-deleted.

## Updating an Org

```http
PATCH /v1/orgs/{org_id}
Content-Type: application/json

{
  "display_name": "Acme Corp (Updated)",
  "is_active": false,
  "status": "suspended"
}
```

Only fields present in the request body are written. Omitted fields remain unchanged.

| Field | Mutable? | Notes |
|-------|----------|-------|
| `slug` | ❌ No | Immutable after creation |
| `display_name` | ✅ Yes | — |
| `settings` | ✅ Yes | Full blob replace |
| `is_active` | ✅ Yes | Quick toggle |
| `status` | ✅ Yes | `active`, `suspended`, `trialing` |

## Deleting an Org

```http
DELETE /v1/orgs/{org_id}
```

Soft-deletes the org. Returns `204 No Content`. The org record is retained for auditing. The org cannot be accessed after deletion.

## Error Responses

| HTTP | Code | Scenario |
|------|------|----------|
| 404 | `NOT_FOUND` | Org not found or already deleted |
| 409 | `CONFLICT` | Duplicate slug on create |
| 409 | `CONFLICT` | Unknown status code on update |
