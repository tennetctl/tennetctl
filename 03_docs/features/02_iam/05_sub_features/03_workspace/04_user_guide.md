# 03_workspace — User Guide

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/orgs/{org_id}/workspaces` | Create workspace |
| GET | `/v1/orgs/{org_id}/workspaces` | List workspaces in org |
| GET | `/v1/orgs/{org_id}/workspaces/{id}` | Get workspace |
| PATCH | `/v1/orgs/{org_id}/workspaces/{id}` | Update workspace |
| DELETE | `/v1/orgs/{org_id}/workspaces/{id}` | Soft-delete workspace |
| GET | `/v1/orgs/{org_id}/workspaces/{id}/versions` | List snapshot versions |
| GET | `/v1/orgs/{org_id}/workspaces/{id}/versions/{n}` | Get snapshot at version N |

## Create Workspace

```bash
curl -X POST http://localhost:18000/v1/orgs/{org_id}/workspaces \
  -H "Content-Type: application/json" \
  -d '{"slug": "production", "display_name": "Production Environment"}'
```

## Frontend

- **List page**: `/iam/workspaces` — org-scoped table (reads active org from localStorage)
- **Detail page**: `/iam/workspaces/{id}?org_id={org_id}` — info grid + delete button + activity timeline
