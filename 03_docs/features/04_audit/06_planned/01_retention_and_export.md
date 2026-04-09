## Planned: Audit Log Retention + Compliance Export

**Severity if unbuilt:** MEDIUM (events accumulate forever; no compliance export path)
**Depends on:** audit sub-feature (built), vault (for S3/MinIO credentials)

## Problem

Audit events are append-only and never pruned. On a busy system this
table grows indefinitely. Compliance frameworks (SOC 2, GDPR) require both
retention policies (keep for N years) and export capabilities.

## Scope when built

### Retention

- New settings key: `audit.retention_days` (default: 365).
- Scheduled job (`audit_retention_worker.py`) runs nightly:
  - Soft-delete events older than `retention_days` by setting `deleted_at`.
  - Hard-delete soft-deleted events older than `retention_days + 30` (grace period).
  - Emit one meta-audit event per run: `{ "deleted_count": N, "cutoff_date": "..." }`.
- Worker registered as a Postgres `pg_cron` job or NATS scheduled message.

### Archival (optional)

Before hard-delete, optionally archive to cold storage:
- Serialize events + attrs to newline-delimited JSON.
- Upload to MinIO at `audit/{year}/{month}/{day}.ndjson.gz`.
- Requires vault secret `tennetctl/storage/minio_dsn`.

### Compliance export

```
GET /v1/audit/events/export
  Query params: from, to (ISO timestamps), format=json|csv, org_id, category
  Effect: Stream response with Content-Disposition: attachment
  Auth: platform_admin only
```

- JSON export: newline-delimited JSON (ndjson).
- CSV export: flat rows with all standard columns + attrs joined.
- Large exports streamed in chunks — no buffering full result in memory.
- Export action itself emits an audit event (`audit.export.requested`).

### Settings keys

```
audit.retention_days          default: 365
audit.archive_to_storage      default: false
audit.archive_storage_path    default: audit/
```

## Not in scope here

- Real-time audit streaming (SSE/WebSocket live feed) — separate planned item
- External log shipping (Datadog, Splunk, Elastic) — monitoring module concern
- SIEM integration
