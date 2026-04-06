# 01_log — User Guide

## What Is the Audit Log?

The audit log records every state-changing action in tennetctl as an immutable event. You can use it to answer questions like:

- Who created this org, and when?
- What changed on this user account in the last 7 days?
- Were there any failed login attempts today?
- What did the system look like before this update?

## Viewing Audit Events

Navigate to **Audit → Events** in the sidebar. The log shows all events for your organisation in reverse chronological order.

### Filtering

Use the filter bar to narrow results by:

- **Entity type** — org, user, workspace, session, etc.
- **Entity ID** — filter to a specific object's history
- **Action** — create, update, delete, login, etc.
- **Outcome** — success or failure
- **Actor** — who performed the action
- **Date range** — from/to timestamps

### Viewing a Snapshot

Click any event to see the full entity snapshot captured at the time of the event. For update events, you can compare the before/after state using the snapshot versioning API.

## Exporting

Click **Export** to download the current filtered view as:

- **CSV** — spreadsheet-compatible
- **JSON** — array of event objects
- **NDJSON** — newline-delimited JSON, one event per line (streaming-friendly)

## What Gets Recorded?

Every mutation through the tennetctl API emits an audit event:

| Action | When |
|--------|------|
| `create` | New entity created |
| `update` | Entity fields changed |
| `delete` | Entity soft-deleted |
| `restore` | Soft-deleted entity restored |
| `login` | User login attempt (success or failure) |

Events are **immutable** — they can never be edited or deleted.
