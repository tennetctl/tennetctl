# 06_group_member

Links users to groups within an organisation.

## Tables

| Table | Type | Purpose |
|---|---|---|
| `09_lnk_group_members` | `lnk_*` | Junction: user-to-group membership |
| `v_group_members` | view | Read-optimised view |

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/v1/groups/{group_id}/members` | List members |
| POST | `/v1/groups/{group_id}/members` | Add member |
| GET | `/v1/groups/{group_id}/members/{id}` | Get one |
| DELETE | `/v1/groups/{group_id}/members/{id}` | Remove (soft delete) |

## Dependencies

- `04_group` (07_fct_groups table)
- `02_user` (10_fct_users table)

## Design Decisions

- No PATCH endpoint: memberships have no mutable fields.
- Soft delete via `deleted_at`: allows audit trail and re-adding after removal.
- Partial unique index on `(group_id, user_id) WHERE deleted_at IS NULL` prevents duplicate active memberships.
