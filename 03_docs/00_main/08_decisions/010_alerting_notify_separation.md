# ADR-010: Alerting Engine Separated from Notification Delivery

**Status:** Accepted
**Date:** 2026-03-29

---

## Context

When building the monitoring alerting module (Phase 5), a key design question arose: should the alert evaluation engine directly send notifications (HTTP calls to webhooks, SMTP, Slack), or should it write notification records that a separate notify module picks up and delivers?

The alerting engine was being built before the Notifications module (Phase 6). Any direct delivery code written here would be duplicated or abandoned when the full Notifications module ships.

---

## Decision

**The alerting evaluator writes `status=pending` notification records to `62_evt_alert_notifications`. A future notify module polls this table and handles actual delivery.**

The alerting engine does NOT make any outbound HTTP calls, send email, or contact external services. Its only output is database rows.

---

## The Boundary

**Alerting engine owns:**
- Alert rule CRUD (`34_adm_alert_rules`)
- State machine evaluation: inactive → pending → firing → resolved
- Silence and inhibition checking
- Routing tree resolution (which receivers should be notified)
- Writing `61_evt_alert_events` (state transitions)
- Writing `62_evt_alert_notifications` with `status=pending`

**Notify module owns (future Phase 6):**
- Polling `62_evt_alert_notifications WHERE status = 'pending'`
- Building notification payloads from alert context
- Dispatching to channels: webhook, email, Slack, PagerDuty, OpsGenie
- Retry logic with exponential backoff
- Updating notification status to `sent`, `failed`, or `suppressed`

---

## Rationale

**Avoid premature delivery code.** Writing Slack/email/webhook dispatch code inside the alerting module would duplicate work that the Notifications module (Phase 6) will do properly. The notify module will have templates, retry policies, channel management, and delivery tracking. A quick version here would be abandoned.

**The outbox pattern is the right abstraction.** Writing `status=pending` rows is the standard transactional outbox pattern. It decouples "decide to notify" from "actually notify", which is the correct separation regardless of architecture. The evaluator succeeds atomically when it writes the row — it does not need the delivery to succeed to complete its job.

**Separation of concerns.** The alerting engine's concern is: "given the current metric value, what state is this alert in, and who needs to know?" The notification engine's concern is: "given that someone needs to know, how do I reach them reliably?" These are different problems with different failure modes.

**Testability.** The alerting engine can be fully tested by asserting on database rows. No mocking of HTTP clients or email servers required.

---

## Database Contract

The `62_evt_alert_notifications` table is the interface between the two modules.

Schema (simplified):
```sql
CREATE TABLE "04_monitoring"."62_evt_alert_notifications" (
    id              VARCHAR(36) PRIMARY KEY,
    org_id          VARCHAR(36) NOT NULL,
    instance_id     VARCHAR(36) NOT NULL,
    receiver_id     VARCHAR(36),          -- NULL = suppressed
    status          TEXT NOT NULL,        -- pending | sent | failed | suppressed
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Index for the notify module's polling query
CREATE INDEX idx_evt_alert_notifications_pending
    ON "04_monitoring"."62_evt_alert_notifications" (org_id, created_at ASC)
    WHERE status = 'pending';
```

The notify module queries:
```sql
SELECT * FROM "04_monitoring"."62_evt_alert_notifications"
WHERE status = 'pending'
ORDER BY created_at ASC
LIMIT 100;
```

---

## Known Gaps (to be addressed in Phase 6 migration)

The current `62_evt_alert_notifications` table is missing fields the notify module will need:

| Column | Purpose |
|--------|---------|
| `payload JSONB` | Snapshot of alert state at time of notification (avoids re-querying) |
| `alert_event_id VARCHAR(36)` | FK to the triggering state transition event |
| `retry_count SMALLINT` | Delivery attempt counter |
| `max_retries SMALLINT` | Max delivery attempts before marking failed |
| `next_retry_at TIMESTAMP` | When to next attempt delivery |
| `last_error TEXT` | Last delivery error message |

These will be added in a Phase 6 migration (`02x_notify_notification_enhancements.sql`) when the notify module is built.

---

## Consequences

- Alerting module ships without any outbound notification delivery.
- `GET /monitoring/alerting/notifications` exposes the notification log for observability.
- The notify module can be built and deployed independently — it only needs the `62_evt_alert_notifications` table to exist.
- Until the notify module is built, `status=pending` rows accumulate but nothing is delivered. This is the correct state — alerts fire, routing is resolved, records are written. Delivery waits for the delivery system.
