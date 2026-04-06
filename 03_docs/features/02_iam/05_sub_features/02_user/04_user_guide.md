# 02_user — User Guide

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/users` | Create a user |
| GET | `/v1/users` | List users (paginated) |
| GET | `/v1/users/{id}` | Get single user |
| PATCH | `/v1/users/{id}` | Update user (display_name, status, is_active) |
| DELETE | `/v1/users/{id}` | Soft-delete user |
| GET | `/v1/users/{id}/versions` | List snapshot versions |
| GET | `/v1/users/{id}/versions/{n}` | Get snapshot at version N |

## Create User

```bash
curl -X POST http://localhost:18000/v1/users \
  -H "Content-Type: application/json" \
  -d '{"email": "jane@example.com", "display_name": "Jane Doe"}'
```

Response:
```json
{
  "ok": true,
  "data": {
    "id": "019d...",
    "email": "jane@example.com",
    "display_name": "Jane Doe",
    "status": "active",
    "account_type": "human",
    "is_active": true,
    "is_test": false,
    "settings": {},
    "created_at": "2026-04-03T..."
  }
}
```

## Suspend User

```bash
curl -X PATCH http://localhost:18000/v1/users/{id} \
  -H "Content-Type: application/json" \
  -d '{"status": "suspended"}'
```

## View Version History

```bash
curl http://localhost:18000/v1/users/{id}/versions
```

Returns list of `{version, changed_by, audit_event_id, created_at}`.

## Frontend

- **List page**: `/iam/users` — table with email, display_name, status, account_type, created
- **Detail page**: `/iam/users/{id}` — info grid + Suspend/Activate/Disable/Delete buttons + activity timeline
