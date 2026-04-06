# Notification System (05_notify) Gap Analysis

Comprehensive comparison of every built notification sub-feature against best-in-class competitors.
Generated: 2026-04-04.

**Competitors:**
- **SendGrid** — email delivery, templates, analytics, webhook events, suppressions, sender authentication
- **Mailchimp/Mandrill** — templates, merge tags, A/B testing, analytics, audiences, automations
- **Novu** — multi-channel notifications, workflows, digest/batching, preferences, in-app feed
- **Knock.io** — workflows, conditions, batching, preferences, in-app feed, Slack/email/push
- **Twilio** — email (SendGrid), SMS, voice, WhatsApp, verify

---

## 01_channel — Channel & Category Lookups

**Compared against:** Novu Channel Types, Knock.io Channel Types, Twilio Channels

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `GET /v1/notify/channels` | List notification channels (email, sms, slack, in_app, web_push) |
| 2 | `GET /v1/notify/categories` | List notification categories (transactional, security, marketing, etc.) |
| 3 | `GET /v1/notify/provider-types` | List provider types (SMTP, SendGrid, SES, Postmark, Resend) |
| 4 | `GET /v1/notify/recipient-strategies` | List recipient strategies (actor, entity_owner, org_members, etc.) |
| 5 | `GET /v1/notify/variable-types` | List variable types (static, dynamic_attr, query) |

**Key strengths:** Lookup-driven architecture means channels, categories, and strategies are extensible without code changes. Clean separation of concerns.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **SMS channel** (channel exists in lookups but no SMS provider integration) | Twilio SMS; Novu SMS channel; Knock.io SMS | P0 |
| **WhatsApp channel** | Twilio WhatsApp Business API; Novu WhatsApp | P1 |
| **Voice/phone call channel** | Twilio Programmable Voice | P2 |
| **Discord channel** | Novu Discord integration; Knock.io Discord | P2 |
| **Microsoft Teams channel** | Novu Teams integration; Knock.io Teams | P2 |
| **Webhook/HTTP channel** (notify external systems via outbound HTTP) | Novu webhook channel; Knock.io webhook channel type | P1 |
| **Chat channel** (generic chat adapters beyond Slack) | Novu chat channel (Slack, Discord, Teams unified) | P2 |
| **Channel health/status dashboard** (is this channel operational?) | SendGrid status page; Twilio channel health | P2 |
| **Channel-level rate limits** (max sends per channel per time window) | SendGrid rate limits; Twilio rate limiting | P1 |

---

## 02_provider — Channel Provider Management

**Compared against:** SendGrid API Keys, Novu Integrations, Knock.io Channel Integrations

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `POST /v1/notify/providers` | Create provider (channel, type, encrypted config, priority) |
| 2 | `GET /v1/notify/providers` | List providers (channel filter, org filter) |
| 3 | `GET /v1/notify/providers/{id}` | Get provider |
| 4 | `PATCH /v1/notify/providers/{id}` | Update provider |
| 5 | `DELETE /v1/notify/providers/{id}` | Soft-delete provider |

**Key strengths:** Encrypted config storage, priority-based failover, is_default flag, multi-provider per channel, org-scoped providers.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Provider health check/test** endpoint (send a test message to verify config) | Novu integration test; SendGrid "Send Test Email" | P0 |
| **Provider connection validation** on create/update (verify credentials before saving) | Novu validates on integration setup; Knock.io connection test | P0 |
| **Provider-level analytics** (delivery rate, bounce rate, latency per provider) | SendGrid stats per API key; Novu integration analytics | P1 |
| **Automatic failover with circuit breaker** (not just priority order, but detect failures and auto-switch) | Novu automatic failover; Knock.io provider fallback chains | P1 |
| **Provider cost tracking** (estimate cost per send per provider) | Twilio billing per message; SendGrid usage reports | P2 |
| **Provider quota/limit tracking** (how many sends remaining this month) | SendGrid account limits; Twilio usage records | P1 |
| **Warm-up/throttling support** for new email providers | SendGrid IP warm-up; Postmark sending velocity | P2 |
| **Provider conditions** (route to specific provider based on message attributes) | Novu conditional routing; Knock.io channel conditions | P1 |
| **Shared provider library** (pre-configured templates for common providers) | Novu integration store; Knock.io channel catalog | P2 |

---

## 03_template — Template Management & Versioning

**Compared against:** SendGrid Dynamic Templates, Mandrill Templates, Novu Notification Templates, Knock.io Message Templates

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `POST /v1/notify/templates` | Create template (name, code, channel, category, org_id) |
| 2 | `GET /v1/notify/templates` | List templates (channel, category, org_id filters) |
| 3 | `GET /v1/notify/templates/{id}` | Get template with current version |
| 4 | `PATCH /v1/notify/templates/{id}` | Update template |
| 5 | `DELETE /v1/notify/templates/{id}` | Soft-delete |
| 6 | `GET /v1/notify/templates/{id}/versions` | List version history |
| 7 | `POST /v1/notify/templates/{id}/versions` | Create new version (subject, body_html, body_text, body_short) |
| 8 | `GET /v1/notify/templates/{id}/versions/{v}` | Get specific version |

**Key strengths:** Full version history, template codes (machine-readable identifiers), multi-format bodies (HTML, text, short), channel-aware, category-tagged.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Template preview/render** endpoint (render with sample data, return HTML) | SendGrid template preview; Mandrill render API; Novu preview | P0 |
| **Template editor UI support** — MJML or drag-and-drop JSON schema | SendGrid Design Editor; Mailchimp template builder; Novu template editor | P1 |
| **Template localization/i18n** (multiple language variants per template) | Novu i18n per template; Knock.io template translations | P1 |
| **A/B testing** (multiple versions with traffic split, measure open/click rates) | Mandrill A/B testing; SendGrid A/B templates | P1 |
| **Template inheritance/layouts** (base layout + content blocks) | SendGrid design library modules; Mandrill merge tags with layouts | P1 |
| **Template categories/tags** for organization beyond the single category field | SendGrid template categories; Mandrill template labels | P2 |
| **Template duplication** (clone a template as starting point) | SendGrid duplicate template; Novu clone workflow | P2 |
| **Template approval workflow** (draft → review → approved → active) | Knock.io commit model; enterprise SendGrid approval | P1 |
| **Active version promotion** (explicitly set which version is "live") | SendGrid active version; Mandrill publish | P0 |
| **Template testing with real data** (send test to specific email with real variables) | SendGrid send test email; Mandrill send test | P0 |
| **Unsubscribe link injection** (auto-insert unsubscribe footer per CAN-SPAM/GDPR) | SendGrid automatic unsubscribe; Mandrill merge tags for unsubscribe | P0 |
| **Template syntax validation** (validate {{variables}} match bound variables) | Novu variable validation; Knock.io schema check | P1 |

---

## 04_variable_query — Dynamic Variable SQL Queries (UNIQUE DIFFERENTIATOR)

**Compared against:** No direct competitor equivalent. Partial analogs: Novu Custom Data, Knock.io Object Data, SendGrid Dynamic Data

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `POST /v1/notify/variable-queries` | Create reusable SQL SELECT query |
| 2 | `GET /v1/notify/variable-queries` | List queries |
| 3 | `GET /v1/notify/variable-queries/{id}` | Get query |
| 4 | `PATCH /v1/notify/variable-queries/{id}` | Update query |
| 5 | `DELETE /v1/notify/variable-queries/{id}` | Soft-delete |
| 6 | `POST /v1/notify/variable-queries/{id}/test` | Dry-run with params |

**Key strengths:** This is a genuine differentiator. 3-pass variable resolution (static values → dynamic EAV attributes → custom SQL queries) gives zero-code extensibility. SELECT-only validation + statement_timeout prevents abuse. No competitor offers this level of dynamic data binding.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Query result caching** (cache SQL results with TTL to avoid per-send DB hits) | General best practice; Novu caches data lookups | P1 |
| **Query parameterization UI** (define named parameters, not raw SQL injection) | Novu step controls; general parameterized query patterns | P1 |
| **Query execution audit log** (track which queries ran, duration, row count) | General observability best practice | P2 |
| **Query versioning** (version control for SQL queries like templates) | Consistent with 03_template pattern | P2 |
| **External data source support** (HTTP/REST API calls as data source, not just SQL) | Novu custom data webhooks; Knock.io fetch step | P1 |
| **Query composition** (chain queries, use output of one as input to another) | Novu workflow steps; Knock.io fetch chaining | P2 |
| **Row limit enforcement** (cap result rows to prevent memory issues) | General safety best practice | P1 |
| **Query performance monitoring** (alert on slow queries) | General observability | P2 |

---

## 05_template_variable — Variable Bindings Per Template

**Compared against:** SendGrid Dynamic Template Data, Mandrill Merge Tags, Novu Step Controls, Knock.io Template Variables

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `POST /v1/notify/templates/{id}/variables` | Bind variable (name, type, default, required, query_id) |
| 2 | `GET /v1/notify/templates/{id}/variables` | List bound variables |
| 3 | `GET /v1/notify/templates/{id}/variables/{var_id}` | Get variable binding |
| 4 | `PATCH /v1/notify/templates/{id}/variables/{var_id}` | Update binding |
| 5 | `DELETE /v1/notify/templates/{id}/variables/{var_id}` | Remove binding |

**Key strengths:** Three-type system (static, dynamic_attr, query), default values, required flags, links to 04_variable_query for SQL-backed resolution.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Variable type validation** (email, URL, date, number — not just "exists") | SendGrid handlebars type helpers; Novu schema validation | P1 |
| **Variable schema/contract** (JSON Schema defining shape of expected data) | Knock.io data schema; Novu workflow input schema | P1 |
| **Fallback chains** (try dynamic_attr → query → static default, configurable order) | Novu fallback values; general resilience pattern | P2 — partially covered by 3-pass resolution |
| **Conditional content blocks** (show/hide template sections based on variable values) | SendGrid handlebars conditionals; Mandrill merge tag conditionals; Novu conditional blocks | P1 |
| **Variable preview** (show sample values alongside template preview) | SendGrid test data preview; Mandrill test merge tags | P1 |
| **Bulk variable import** (define many variables at once from JSON/CSV) | General UX improvement | P2 |
| **Variable usage tracking** (which templates use this variable? unused variables?) | General maintainability | P2 |

---

## 06_rule — Event-to-Notification Dispatch Rules

**Compared against:** Novu Workflows, Knock.io Workflows, SendGrid Event Webhook Routing

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `POST /v1/notify/rules` | Create rule (event_type → template + channel + recipient_strategy) |
| 2 | `GET /v1/notify/rules` | List rules (event_type filter, channel filter) |
| 3 | `GET /v1/notify/rules/{id}` | Get rule |
| 4 | `PATCH /v1/notify/rules/{id}` | Update rule |
| 5 | `DELETE /v1/notify/rules/{id}` | Soft-delete |

**Key strengths:** Event-driven dispatch, recipient strategies, delay seconds, category-based routing. Clean single-table rule engine.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Multi-step workflows** (send email → wait 1hr → if not opened → send SMS) | Novu workflow engine; Knock.io workflow builder; Mandrill automations | P0 |
| **Workflow visual builder** (drag-and-drop workflow creation) | Novu workflow editor UI; Knock.io workflow canvas | P1 |
| **Conditional branching** (if user.plan == 'pro' → use template A, else → template B) | Novu workflow conditions; Knock.io step conditions | P0 |
| **Digest/batching** (aggregate multiple events into a single notification) | Novu digest step; Knock.io batch step | P0 |
| **Throttling/rate limiting per rule** (max 1 notification per user per hour for this rule) | Novu throttle step; Knock.io frequency capping | P0 |
| **Multi-channel fan-out** (one rule sends to email AND push AND in-app simultaneously) | Novu multi-channel workflow; Knock.io multi-channel steps | P0 |
| **Delay with cancel** (schedule a delayed send, cancel if user takes action before delay expires) | Novu delay + cancel; Knock.io delay with cancellation key | P1 |
| **Rule priority/ordering** (when multiple rules match, which fires first?) | Novu workflow priority; Knock.io workflow ordering | P1 |
| **Rule versioning** (draft → active, rollback) | Novu workflow versioning; Knock.io commit model | P1 |
| **Scheduling** (send at user's local time, send at specific time) | Novu schedule step; Knock.io schedule; SendGrid send_at | P1 |
| **Rule testing/simulation** (dry-run a rule with sample event data) | Novu workflow test; Knock.io test run | P1 |
| **Event schema validation** (validate incoming event payload matches expected shape) | Novu event schema; Knock.io workflow trigger schema | P1 |

---

## 07_preference — User Notification Preferences

**Compared against:** Novu Preferences, Knock.io Preferences, SendGrid Suppressions

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `GET /v1/notify/preferences` | List user preferences (user_id, channel, category filters) |
| 2 | `PUT /v1/notify/preferences` | Upsert preference (user_id, channel, category, opted_in) |
| 3 | `DELETE /v1/notify/preferences/{id}` | Remove preference |

**Key strengths:** Opt-in/opt-out per channel and/or category, mandatory categories (transactional, security) enforced server-side, partial unique indexes for NULL scope handling.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Preference center UI component** (embeddable React component for end users) | Novu `<NotificationCenter>` component; Knock.io `<PreferenceCenter>` | P1 |
| **Topic-based preferences** (subscribe/unsubscribe to specific topics, not just categories) | Novu topics; Knock.io preference sets per workflow | P1 |
| **Default preferences** per org/workspace (org-wide defaults that users can override) | Novu workflow-level defaults; Knock.io default preferences | P1 |
| **Preference inheritance** (user pref overrides org pref overrides platform default) | Knock.io preference hierarchy; Novu subscriber preference merge | P1 |
| **Bulk preference update** (set multiple preferences in one call) | Novu bulk preference update; Knock.io set all preferences | P1 |
| **Preference history/audit** (when did user change this preference?) | General audit pattern | P2 |
| **Quiet hours/DND** (do not send between 10pm-8am in user's timezone) | Knock.io quiet hours; general best practice | P1 |
| **Channel-specific delivery timing** (email digest: daily at 9am; push: immediate) | Novu digest scheduling; Knock.io batch timing | P2 |
| **Preference API for current user** (GET /me/preferences without passing user_id) | Novu subscriber preferences; Knock.io /me/preferences | P1 |
| **GDPR consent tracking** (record when/how consent was given) | SendGrid consent management; GDPR compliance pattern | P1 |

---

## 08_send — Core Send Engine

**Compared against:** SendGrid Mail Send, Mandrill Send, Novu Trigger, Knock.io Trigger, Twilio Messages

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `POST /v1/notify/send` | Send notification (template_code, recipients, variables, channel) |
| 2 | `GET /v1/notify/send/log` | List send log (filters: template, channel, status, date range) |
| 3 | `GET /v1/notify/send/log/{id}` | Get send log entry |

**Key strengths:** 3-pass variable resolution pipeline, template rendering via `string.Template`, provider selection + failover, email open tracking (1x1 pixel), email click tracking (link wrapping + redirect), full audit trail per send, suppression list checking.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Async/queue-based sending** (queue the send, process in background worker) | SendGrid async sending; Novu queue-based; Knock.io async triggers | P0 |
| **Batch/bulk send** (send to thousands of recipients efficiently) | SendGrid batch API (1000 recipients); Mandrill send-template batch; Twilio bulk | P0 |
| **Send scheduling** (send_at timestamp for future delivery) | SendGrid send_at; Mandrill send_at; Knock.io scheduled triggers | P1 |
| **Idempotency key** (prevent duplicate sends on retry) | SendGrid idempotency; Knock.io idempotency key | P0 |
| **Cancel scheduled send** | SendGrid cancel scheduled; Knock.io cancel workflow | P1 |
| **Recipient group/segment support** (send to a saved audience/segment) | SendGrid segments; Mandrill tags for sending; Novu topics | P1 |
| **Template overrides on send** (override subject/body at send time without creating a version) | SendGrid dynamic template data overrides; Mandrill merge vars + global merge vars | P1 |
| **Attachments** (send email with file attachments) | SendGrid attachments; Mandrill attachments; Twilio email attachments | P0 |
| **Reply-to address** configuration per send | SendGrid reply_to; Mandrill reply_to | P1 |
| **CC/BCC support** for email sends | SendGrid cc/bcc; standard email pattern | P1 |
| **Custom headers** on email sends | SendGrid custom_args/headers; Mandrill headers | P2 |
| **Send rate limiting** (global and per-recipient rate limits) | SendGrid rate limits; Twilio rate limiting | P1 |
| **Retry with exponential backoff** on provider failure | SendGrid automatic retry; Novu retry policies; Knock.io retry | P1 |
| **Webhook/callback on send completion** (notify calling system when send completes) | SendGrid Event Webhook; Twilio status callbacks | P1 |
| **Send analytics** (aggregate stats: sent, delivered, opened, clicked, bounced) | SendGrid Stats API; Mandrill sending stats | P0 |
| **Template rendering engine upgrade** (Jinja2/Handlebars instead of string.Template) | SendGrid Handlebars; Mandrill merge language; Novu Handlebars | P1 |

---

## 09_delivery_event — Provider Webhook Processing

**Compared against:** SendGrid Event Webhook, Postmark Webhooks, Mandrill Webhooks, Twilio Status Callbacks, Novu Activity Feed

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `POST /v1/notify/webhooks/sendgrid` | Process SendGrid delivery events |
| 2 | `POST /v1/notify/webhooks/postmark` | Process Postmark delivery events |
| 3 | `GET /v1/notify/delivery-events` | List delivery events (send_id, status filters) |
| 4 | `GET /v1/notify/delivery-events/{id}` | Get delivery event |

**Key strengths:** Multi-provider webhook ingestion, full status lifecycle (queued → sent → delivered → opened → clicked → bounced → complained), linked to send log entries.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **SES webhook integration** (SNS notifications for bounces/complaints) | Amazon SES notifications via SNS; standard for SES users | P0 |
| **Resend webhook integration** | Resend webhooks API | P1 |
| **SMTP webhook integration** (DSN bounce processing) | Standard SMTP DSN/bounce parsing | P2 |
| **Webhook signature verification** (validate SendGrid/Postmark signatures to prevent spoofing) | SendGrid Event Webhook signature verification; Postmark webhook auth | P0 |
| **Webhook retry/replay** (re-process failed webhook events) | SendGrid webhook retry; general webhook resilience | P1 |
| **Delivery analytics dashboard data** (aggregate delivery rates, bounce rates, complaint rates over time) | SendGrid Stats API; Mandrill sending stats; Postmark stats | P0 |
| **Bounce classification** (hard bounce vs soft bounce, reason codes) | SendGrid bounce classification; Postmark bounce types; Mandrill bounce detail | P1 |
| **Automatic suppression on hard bounce** (auto-add to suppression list) | SendGrid automatic suppression; Postmark automatic suppression | P0 |
| **Complaint feedback loop** (process ISP feedback loop reports) | SendGrid FBL; standard email deliverability | P1 |
| **Webhook event deduplication** (prevent processing same event twice) | General webhook idempotency pattern | P1 |
| **Real-time event streaming** (SSE/WebSocket for live delivery monitoring) | SendGrid real-time event streaming; Novu activity feed live updates | P2 |
| **Event retention policy** (auto-purge old events after N days) | SendGrid 3-day event retention; configurable retention | P1 |

---

## 10_in_app — In-App Notification Feed

**Compared against:** Novu Notification Center, Knock.io In-App Feed, MagicBell

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `GET /v1/notify/in-app` | List user's notifications (paginated, unread filter) |
| 2 | `PATCH /v1/notify/in-app/{id}/read` | Mark as read |
| 3 | `PATCH /v1/notify/in-app/{id}/archive` | Archive notification |
| 4 | `POST /v1/notify/in-app/mark-all-read` | Mark all as read |
| 5 | `GET /v1/notify/in-app/unread-count` | Get unread count |

**Key strengths:** Clean inbox model, read/archive state management, unread count endpoint, paginated feed.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Real-time delivery** (WebSocket/SSE for instant notification push to frontend) | Novu WebSocket real-time; Knock.io real-time feed; MagicBell real-time | P0 |
| **Embeddable UI component** (React `<NotificationBell>` + `<NotificationFeed>` drop-in) | Novu `<NotificationCenterComponent>`; Knock.io `<NotificationFeed>`; MagicBell React SDK | P0 |
| **Notification actions** (CTA buttons: "Accept Invite", "View Report" with action URLs) | Novu action buttons; Knock.io action buttons; MagicBell actions | P0 |
| **Rich content** (markdown body, avatar/icon per notification, category icon) | Novu rich notification content; Knock.io blocks; MagicBell rich content | P1 |
| **Notification grouping** (group by category, source, or topic) | Knock.io feed filtering; MagicBell categories | P1 |
| **Bulk actions** (mark selected as read, bulk archive, bulk delete) | Novu bulk operations; Knock.io bulk status update | P1 |
| **Notification routing** (clicking notification navigates to relevant page) | Novu onNotificationClick redirect; Knock.io redirect_url | P1 |
| **Seen vs Read** distinction (notification appeared in feed vs user clicked it) | Novu seen/read distinction; Knock.io seen/read/interacted | P1 |
| **Unseen count** (separate from unread — "new since last opened feed") | Novu unseen count; Knock.io unseen count | P1 |
| **Feed pagination** with cursor-based pagination (not just offset) | Novu cursor-based; Knock.io cursor pagination | P1 |
| **Delete notification** (currently only archive, not permanent delete) | MagicBell delete; general UX pattern | P2 |
| **Notification snooze** (snooze for 1hr, remind later) | MagicBell snooze; iOS notification snooze pattern | P2 |
| **Multi-tab badge sync** (unread count syncs across browser tabs) | Novu real-time sync; general UX pattern | P2 |

---

## 11_web_push — Web Push Subscriptions

**Compared against:** Novu Web Push, Knock.io Push, OneSignal, Firebase Cloud Messaging (FCM)

### What We HAVE

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `POST /v1/notify/web-push/subscribe` | Register VAPID subscription (user_id, endpoint, keys) |
| 2 | `DELETE /v1/notify/web-push/subscribe` | Unsubscribe |
| 3 | `GET /v1/notify/web-push/subscriptions` | List user's subscriptions |

**Key strengths:** VAPID protocol support, upsert on (user_id, endpoint), auto-deactivation on 410 Gone response.

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Mobile push (APNs/FCM)** — native mobile push via Firebase or Apple Push | FCM; APNs; Novu push channel; Knock.io push; OneSignal | P1 |
| **Push notification payload customization** (icon, badge, image, actions, data payload) | Web Push API spec; OneSignal rich push; FCM notification payload | P0 |
| **Push analytics** (delivered, clicked, dismissed per push notification) | OneSignal analytics; FCM analytics; Novu push stats | P1 |
| **Silent push / data-only push** (update app state without showing notification) | FCM data messages; APNs silent push | P2 |
| **Push scheduling** (send push at specific time or user's local time) | OneSignal scheduling; FCM send_at | P1 |
| **Push segmentation** (send to user segments, not just individual users) | OneSignal segments; FCM topics | P1 |
| **Subscription management UI** (user can see/manage their push subscriptions) | OneSignal subscription management | P2 |
| **Push permission prompt best practices** (soft-ask before hard browser prompt) | OneSignal permission prompt; web push UX patterns | P2 |
| **Multi-device push** (send to all user's devices, handle device limits) | OneSignal multi-device; FCM device groups | P1 |
| **Push TTL** (time-to-live: expire push if not delivered within window) | Web Push TTL header; FCM time_to_live; APNs expiry | P1 |
| **Topic-based push subscriptions** (subscribe to topics, not just user-level) | FCM topic messaging; OneSignal tags | P2 |

---

## Cross-Feature: Suppression List

**Compared against:** SendGrid Suppressions, Postmark Suppressions, Mandrill Rejects

### What We HAVE

- Suppression list table with bounce/complaint/manual reasons
- Checked during send pipeline
- Auto-suppress on bounce/complaint (via delivery events)

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Suppression list CRUD API** (list, add, remove suppressions via API) | SendGrid Suppressions API; Postmark Suppressions API | P0 |
| **Suppression categories** (bounces, spam reports, unsubscribes, invalid emails — separate lists) | SendGrid separate suppression groups; Postmark bounce/spam/manual lists | P1 |
| **Suppression group management** (let users unsubscribe from categories, not all email) | SendGrid Suppression Groups; Mandrill rejection management | P1 |
| **Suppression import/export** (bulk upload/download suppression list) | SendGrid CSV import/export; Postmark bulk suppression | P1 |
| **Suppression search** (search by email, reason, date range) | SendGrid suppression search; Postmark filters | P1 |
| **Automatic revalidation** (periodically re-check soft-bounced addresses) | SendGrid automatic re-engagement; general deliverability pattern | P2 |

---

## Cross-Feature: Org-Level Configuration

**Compared against:** SendGrid Subusers, Mandrill Subaccounts, Novu Environments, Knock.io Environments

### What We HAVE

- Org-scoped providers (org can use own SMTP/SendGrid)
- Org-scoped templates
- Org-level branding config

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Org-level sender identity** (from name, from email, reply-to per org) | SendGrid Sender Identity; Mandrill sender domains; Novu sender config | P0 |
| **Sender domain authentication** (SPF, DKIM, DMARC setup per org) | SendGrid Sender Authentication; Postmark domain verification; Mandrill sending domains | P0 |
| **Org-level sending limits** (cap sends per org per day/month) | SendGrid subuser limits; Twilio usage limits | P1 |
| **Org-level analytics** (delivery metrics per org) | SendGrid subuser stats; Mandrill subaccount stats | P1 |
| **White-label sending** (notification appears to come from org's domain, not platform) | SendGrid white-label; Mandrill sending domains; Postmark sender signatures | P1 |
| **Environment support** (dev/staging/prod per org, separate configs and templates) | Novu environments; Knock.io environments; general multi-env pattern | P1 |

---

## Cross-Feature: Email Deliverability

**Compared against:** SendGrid Deliverability, Postmark Deliverability, Mailchimp Deliverability

### What We HAVE

- Open tracking (1x1 pixel)
- Click tracking (link wrapping + redirect)
- Delivery event lifecycle tracking

### What Competitors Have That We're MISSING

| Gap | Competitor Reference | Priority |
|-----|---------------------|----------|
| **Sender reputation monitoring** | SendGrid Sender Reputation; Postmark Sender Score | P1 |
| **Email validation** (validate email address syntax + deliverability before sending) | SendGrid Email Validation API; Twilio Lookup; ZeroBounce | P1 |
| **Dedicated IP management** (for high-volume senders needing reputation isolation) | SendGrid Dedicated IP; Postmark dedicated IPs | P2 |
| **Link branding** (track links via custom domain, not provider domain) | SendGrid Link Branding; Postmark custom tracking domain | P1 |
| **Open/click tracking opt-out** per send (privacy-conscious sends) | SendGrid tracking settings per message; Postmark tracking per message | P1 |
| **Spam score check** (test message against spam filters before sending) | Postmark spam check API; Mailchimp inbox preview | P1 |
| **Inbox placement testing** (test across Gmail, Outlook, Yahoo) | SendGrid Inbox Placement; Mailchimp inbox preview | P2 |
| **BIMI support** (Brand Indicators for Message Identification) | SendGrid BIMI; general email standard | P2 |
| **AMP for Email support** (interactive email content) | SendGrid AMP; Mandrill AMP; Google AMP for Email | P2 |

---

## Summary: P0 Gaps (Must Fix for Production)

These are blocking gaps that any production notification system must address:

| # | Sub-feature | Gap | Effort |
|---|-------------|-----|--------|
| 1 | 01_channel | SMS channel provider integration (Twilio/Vonage) | M |
| 2 | 02_provider | Provider health check/test endpoint | S |
| 3 | 02_provider | Provider connection validation on create/update | S |
| 4 | 03_template | Template preview/render endpoint | S |
| 5 | 03_template | Active version promotion (set which version is "live") | S |
| 6 | 03_template | Template testing with real data | S |
| 7 | 03_template | Unsubscribe link injection (CAN-SPAM/GDPR compliance) | M |
| 8 | 06_rule | Multi-step workflows (send → wait → check → send) | L |
| 9 | 06_rule | Conditional branching in rules | M |
| 10 | 06_rule | Digest/batching (aggregate events into single notification) | M |
| 11 | 06_rule | Throttling/rate limiting per rule | S |
| 12 | 06_rule | Multi-channel fan-out (one event → email + push + in-app) | M |
| 13 | 08_send | Async/queue-based sending (background worker) | L |
| 14 | 08_send | Batch/bulk send support | M |
| 15 | 08_send | Idempotency key on send | S |
| 16 | 08_send | File attachments for email | S |
| 17 | 08_send | Send analytics (aggregate delivery stats) | M |
| 18 | 09_delivery_event | Webhook signature verification | S |
| 19 | 09_delivery_event | SES webhook integration (SNS bounce/complaint) | M |
| 20 | 09_delivery_event | Delivery analytics (aggregate rates over time) | M |
| 21 | 09_delivery_event | Automatic suppression on hard bounce | S |
| 22 | 10_in_app | Real-time delivery (WebSocket/SSE) | M |
| 23 | 10_in_app | Embeddable UI component (`<NotificationBell>`) | M |
| 24 | 10_in_app | Notification actions (CTA buttons with action URLs) | S |
| 25 | 11_web_push | Push payload customization (icon, badge, image, actions) | S |
| 26 | Cross: Suppression | Suppression list CRUD API | S |
| 27 | Cross: Org Config | Org-level sender identity (from name, from email) | S |
| 28 | Cross: Org Config | Sender domain authentication (SPF, DKIM, DMARC) | M |

**Effort key:** XS = <1hr, S = 1-4hr, M = 4-16hr, L = 2-5 days

---

## Summary: P1 Gaps (Should Have)

| # | Sub-feature | Gap |
|---|-------------|-----|
| 1 | 01_channel | WhatsApp channel, webhook/HTTP channel, channel-level rate limits |
| 2 | 02_provider | Provider analytics, circuit breaker failover, quota tracking, conditional routing |
| 3 | 03_template | Template localization/i18n, A/B testing, layouts/inheritance, approval workflow, syntax validation |
| 4 | 03_template | Template editor UI support (MJML or drag-and-drop) |
| 5 | 04_variable_query | Result caching with TTL, parameterization UI, external data sources, row limit enforcement |
| 6 | 05_template_variable | Type validation, JSON Schema contract, conditional content blocks, variable preview |
| 7 | 06_rule | Delay with cancel, rule priority/ordering, rule versioning, scheduling, simulation/testing, event schema |
| 8 | 07_preference | Preference center UI component, topic-based preferences, default preferences, inheritance, quiet hours/DND, GDPR consent |
| 9 | 08_send | Send scheduling, recipient segments, template overrides, CC/BCC, reply-to, rate limiting, retry with backoff, webhook callback, Handlebars/Jinja2 upgrade |
| 10 | 09_delivery_event | Resend webhook, bounce classification, complaint FBL, event deduplication, retention policy |
| 11 | 10_in_app | Rich content, notification grouping, bulk actions, routing/navigation, seen vs read, unseen count, cursor pagination |
| 12 | 11_web_push | Mobile push (APNs/FCM), push analytics, scheduling, segmentation, multi-device, push TTL |
| 13 | Cross: Suppression | Suppression categories, group management, import/export, search |
| 14 | Cross: Org Config | Sending limits per org, org analytics, white-label, environment support |
| 15 | Cross: Deliverability | Sender reputation, email validation, link branding, open/click tracking opt-out, spam score check |

---

## Cross-Cutting Observations

1. **Workflow engine is the single biggest architectural gap.** Our 06_rule sub-feature is a flat event → notification mapping. Novu and Knock.io are built around multi-step workflow engines with conditional branching, delays, digests, and channel fan-out. This is the core value proposition of modern notification infrastructure and represents the largest competitive gap.

2. **No async/queue architecture.** All sends are synchronous in the request path. Production systems require a message queue (Redis/RabbitMQ/SQS) with background workers for reliability, retry, and throughput. SendGrid, Novu, Knock.io, and Twilio all process sends asynchronously.

3. **Real-time delivery is missing for in-app.** The in-app feed is poll-only. Every competitor (Novu, Knock.io, MagicBell) provides WebSocket/SSE for instant notification delivery to the frontend. Without this, users must refresh to see new notifications.

4. **No embeddable UI components.** Novu and Knock.io ship React SDKs with `<NotificationBell>`, `<NotificationFeed>`, and `<PreferenceCenter>` components. These are major adoption drivers and reduce integration time from days to minutes.

5. **Email deliverability is minimal.** We have open/click tracking but lack sender authentication (SPF/DKIM/DMARC), suppression management APIs, bounce classification, email validation, and sender reputation monitoring. SendGrid and Postmark consider these table-stakes.

6. **SMS channel is configured but not connected.** The channel lookup includes SMS, but there's no SMS provider integration (Twilio, Vonage, etc.). This is a common expectation for any multi-channel notification system.

7. **Template engine is basic.** `string.Template` only supports `${variable}` substitution. No conditionals, loops, partials, or filters. Upgrading to Handlebars or Jinja2 would unlock conditional content blocks, iteration over lists, and helper functions — all standard in SendGrid, Mandrill, and Novu.

8. **Variable query system is a genuine competitive advantage.** No competitor offers SQL-backed dynamic variable resolution. The 3-pass pipeline (static → EAV → SQL query) is unique and powerful. Invest in hardening it (caching, row limits, parameterization) rather than replacing it.

9. **Digest/batching is conspicuously absent.** Users receiving 50 notifications about "new comment on your post" is a classic problem. Novu and Knock.io both have first-class digest steps that aggregate multiple events into a single notification. This is P0 for any system that emits high-frequency events.

10. **CAN-SPAM/GDPR compliance gaps.** No automatic unsubscribe link injection, no GDPR consent tracking on preferences, and no suppression management API. These are legal requirements for commercial email in the US and EU.
