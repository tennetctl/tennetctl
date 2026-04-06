-- UP ====
-- Migration 018: notify core schema, dim tables, and all main entity tables.
-- Creates schema 05_notify and every table except 22_fct_notify_config (see 019).
-- Tables: dims, providers, templates, template versions/variables, rules,
--         variable queries, in-app notifications, web push subscriptions,
--         user preferences, send log, delivery events, lnk tables.

-- ---------------------------------------------------------------------------
-- Schema
-- ---------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS "05_notify";

COMMENT ON SCHEMA "05_notify" IS 'Notification feature: providers, templates, rules, send log, and user preferences.';

-- ---------------------------------------------------------------------------
-- set_updated_at trigger function (idempotent)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION "05_notify".set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION "05_notify".set_updated_at() IS 'Trigger function: auto-sets updated_at to CURRENT_TIMESTAMP on every row update.';

SET search_path TO "05_notify";

-- ---------------------------------------------------------------------------
-- 02_dim_channels
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "05_notify"."02_dim_channels" (
    id            SMALLINT      NOT NULL,
    code          TEXT          NOT NULL,
    label         TEXT          NOT NULL,
    description   TEXT          NULL,
    deprecated_at TIMESTAMP     NULL,
    CONSTRAINT pk_dim_channels PRIMARY KEY (id),
    CONSTRAINT uq_dim_channels_code UNIQUE (code)
);

COMMENT ON TABLE  "05_notify"."02_dim_channels"              IS 'Lookup: notification delivery channels supported by the platform.';
COMMENT ON COLUMN "05_notify"."02_dim_channels".id           IS 'SMALLINT primary key. Stable numeric ID referenced by FK columns.';
COMMENT ON COLUMN "05_notify"."02_dim_channels".code         IS 'Machine-readable code. Values: email, web_push, in_app, mobile_push.';
COMMENT ON COLUMN "05_notify"."02_dim_channels".label        IS 'Human-readable display label.';
COMMENT ON COLUMN "05_notify"."02_dim_channels".description  IS 'Optional description of the channel.';
COMMENT ON COLUMN "05_notify"."02_dim_channels".deprecated_at IS 'NULL = active. SET = no longer available for new configurations.';

INSERT INTO "05_notify"."02_dim_channels" (id, code, label, description) VALUES
    (1, 'email',       'Email',       'SMTP and transactional email providers (SendGrid, SES, Postmark, Resend).'),
    (2, 'web_push',    'Web Push',    'Browser push notifications via VAPID Web Push protocol.'),
    (3, 'in_app',      'In-App',      'In-application notification feed written directly to the database.'),
    (4, 'mobile_push', 'Mobile Push', 'Native mobile push notifications (APNs / FCM). Reserved for future use.')
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 03_dim_provider_types
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "05_notify"."03_dim_provider_types" (
    id            SMALLINT      NOT NULL,
    code          TEXT          NOT NULL,
    label         TEXT          NOT NULL,
    channel_id    SMALLINT      NOT NULL,
    description   TEXT          NULL,
    deprecated_at TIMESTAMP     NULL,
    CONSTRAINT pk_dim_provider_types          PRIMARY KEY (id),
    CONSTRAINT uq_dim_provider_types_code     UNIQUE (code),
    CONSTRAINT fk_dim_provider_types_channel  FOREIGN KEY (channel_id) REFERENCES "05_notify"."02_dim_channels" (id)
);

COMMENT ON TABLE  "05_notify"."03_dim_provider_types"              IS 'Lookup: specific provider integrations available per channel.';
COMMENT ON COLUMN "05_notify"."03_dim_provider_types".id           IS 'SMALLINT primary key.';
COMMENT ON COLUMN "05_notify"."03_dim_provider_types".code         IS 'Machine-readable provider type code. E.g. smtp, sendgrid, ses.';
COMMENT ON COLUMN "05_notify"."03_dim_provider_types".label        IS 'Human-readable provider name.';
COMMENT ON COLUMN "05_notify"."03_dim_provider_types".channel_id   IS 'FK to 02_dim_channels. Which channel this provider type belongs to.';
COMMENT ON COLUMN "05_notify"."03_dim_provider_types".description  IS 'Optional description of the provider and its capabilities.';
COMMENT ON COLUMN "05_notify"."03_dim_provider_types".deprecated_at IS 'NULL = active. SET = deprecated, no new providers of this type.';

INSERT INTO "05_notify"."03_dim_provider_types" (id, code, label, channel_id, description) VALUES
    (1,  'smtp',        'SMTP',            1, 'Generic SMTP relay — any mail server.'),
    (2,  'sendgrid',    'SendGrid',        1, 'SendGrid transactional email API.'),
    (3,  'ses',         'Amazon SES',      1, 'AWS Simple Email Service API.'),
    (4,  'postmark',    'Postmark',        1, 'Postmark transactional email API.'),
    (5,  'resend',      'Resend',          1, 'Resend transactional email API.'),
    (10, 'vapid',       'VAPID Web Push',  2, 'W3C Push API — browser push via VAPID keys.'),
    (20, 'in_app_db',   'In-App DB',       3, 'Internal: write notification directly to fct_in_app_notifications.'),
    (30, 'apns',        'Apple APNs',      4, 'Apple Push Notification service. Reserved for future use.'),
    (31, 'fcm',         'Firebase FCM',    4, 'Google Firebase Cloud Messaging. Reserved for future use.')
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 05_dim_delivery_event_types
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "05_notify"."05_dim_delivery_event_types" (
    id            SMALLINT      NOT NULL,
    code          TEXT          NOT NULL,
    label         TEXT          NOT NULL,
    description   TEXT          NULL,
    deprecated_at TIMESTAMP     NULL,
    CONSTRAINT pk_dim_delivery_event_types      PRIMARY KEY (id),
    CONSTRAINT uq_dim_delivery_event_types_code UNIQUE (code)
);

COMMENT ON TABLE  "05_notify"."05_dim_delivery_event_types"             IS 'Lookup: provider delivery event types recorded in evt_delivery_events.';
COMMENT ON COLUMN "05_notify"."05_dim_delivery_event_types".id          IS 'SMALLINT primary key.';
COMMENT ON COLUMN "05_notify"."05_dim_delivery_event_types".code        IS 'Machine-readable event code. E.g. queued, sent, delivered, opened, bounced.';
COMMENT ON COLUMN "05_notify"."05_dim_delivery_event_types".label       IS 'Human-readable label for UI display.';
COMMENT ON COLUMN "05_notify"."05_dim_delivery_event_types".description IS 'Description of when this event is emitted.';
COMMENT ON COLUMN "05_notify"."05_dim_delivery_event_types".deprecated_at IS 'NULL = active.';

INSERT INTO "05_notify"."05_dim_delivery_event_types" (id, code, label, description) VALUES
    (1,  'queued',      'Queued',       'Message accepted into the queue, not yet dispatched.'),
    (2,  'sent',        'Sent',         'Message submitted to the provider successfully.'),
    (3,  'delivered',   'Delivered',    'Provider confirmed the message reached the recipient mailbox.'),
    (4,  'opened',      'Opened',       'Recipient opened the email (tracking pixel fired).'),
    (5,  'clicked',     'Clicked',      'Recipient clicked a tracked link in the email.'),
    (6,  'bounced',     'Bounced',      'Message was rejected by the recipient mail server.'),
    (7,  'complained',  'Complained',   'Recipient marked the message as spam.'),
    (8,  'unsubscribed','Unsubscribed', 'Recipient clicked the unsubscribe link.'),
    (9,  'failed',      'Failed',       'Internal error or unknown provider failure.')
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 06_dim_notification_categories
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "05_notify"."06_dim_notification_categories" (
    id            SMALLINT      NOT NULL,
    code          TEXT          NOT NULL,
    label         TEXT          NOT NULL,
    description   TEXT          NULL,
    is_mandatory  BOOLEAN       NOT NULL DEFAULT FALSE,
    deprecated_at TIMESTAMP     NULL,
    CONSTRAINT pk_dim_notification_categories      PRIMARY KEY (id),
    CONSTRAINT uq_dim_notification_categories_code UNIQUE (code)
);

COMMENT ON TABLE  "05_notify"."06_dim_notification_categories"               IS 'Lookup: notification categories. Mandatory categories cannot be opted out of.';
COMMENT ON COLUMN "05_notify"."06_dim_notification_categories".id            IS 'SMALLINT primary key.';
COMMENT ON COLUMN "05_notify"."06_dim_notification_categories".code         IS 'Machine-readable category code. E.g. transactional, marketing, security.';
COMMENT ON COLUMN "05_notify"."06_dim_notification_categories".label        IS 'Human-readable label.';
COMMENT ON COLUMN "05_notify"."06_dim_notification_categories".description  IS 'Description of what notifications belong to this category.';
COMMENT ON COLUMN "05_notify"."06_dim_notification_categories".is_mandatory IS 'TRUE = users cannot opt out. Always sent regardless of preferences.';
COMMENT ON COLUMN "05_notify"."06_dim_notification_categories".deprecated_at IS 'NULL = active.';

INSERT INTO "05_notify"."06_dim_notification_categories" (id, code, label, description, is_mandatory) VALUES
    (1, 'transactional', 'Transactional', 'Triggered by user actions: receipts, password resets, OTPs.', TRUE),
    (2, 'security',      'Security',      'Auth events: logins, MFA changes, suspicious activity alerts.', TRUE),
    (3, 'account',       'Account',       'Account lifecycle: invitations, role changes, workspace events.', FALSE),
    (4, 'product',       'Product',       'Feature announcements, usage reports, in-product tips.', FALSE),
    (5, 'marketing',     'Marketing',     'Promotional emails, newsletters, campaign messages.', FALSE),
    (6, 'system',        'System',        'Platform maintenance, downtime notices, SLA alerts.', FALSE)
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 07_dim_recipient_strategies
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "05_notify"."07_dim_recipient_strategies" (
    id            SMALLINT      NOT NULL,
    code          TEXT          NOT NULL,
    label         TEXT          NOT NULL,
    description   TEXT          NULL,
    deprecated_at TIMESTAMP     NULL,
    CONSTRAINT pk_dim_recipient_strategies      PRIMARY KEY (id),
    CONSTRAINT uq_dim_recipient_strategies_code UNIQUE (code)
);

COMMENT ON TABLE  "05_notify"."07_dim_recipient_strategies"             IS 'Lookup: how notification rules resolve the recipient list from an event.';
COMMENT ON COLUMN "05_notify"."07_dim_recipient_strategies".id          IS 'SMALLINT primary key.';
COMMENT ON COLUMN "05_notify"."07_dim_recipient_strategies".code        IS 'Machine-readable strategy code used by dispatch logic.';
COMMENT ON COLUMN "05_notify"."07_dim_recipient_strategies".label       IS 'Human-readable strategy name.';
COMMENT ON COLUMN "05_notify"."07_dim_recipient_strategies".description IS 'How recipients are resolved when this strategy is selected.';
COMMENT ON COLUMN "05_notify"."07_dim_recipient_strategies".deprecated_at IS 'NULL = active.';

INSERT INTO "05_notify"."07_dim_recipient_strategies" (id, code, label, description) VALUES
    (1, 'actor',             'Actor',             'Send to the user who triggered the event.'),
    (2, 'entity_owner',      'Entity Owner',      'Send to the owner of the entity referenced by the event.'),
    (3, 'org_members',       'Org Members',       'Send to all active members of the organisation.'),
    (4, 'workspace_members', 'Workspace Members', 'Send to all active members of a specific workspace (workspace_id in recipient_filter).'),
    (5, 'specific_users',    'Specific Users',    'Send to a static list of user IDs defined in recipient_filter.user_ids.'),
    (6, 'all_users',         'All Users',         'Send to every active user in the organisation.')
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 08_dim_variable_types
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "05_notify"."08_dim_variable_types" (
    id            SMALLINT      NOT NULL,
    code          TEXT          NOT NULL,
    label         TEXT          NOT NULL,
    description   TEXT          NULL,
    deprecated_at TIMESTAMP     NULL,
    CONSTRAINT pk_dim_variable_types      PRIMARY KEY (id),
    CONSTRAINT uq_dim_variable_types_code UNIQUE (code)
);

COMMENT ON TABLE  "05_notify"."08_dim_variable_types"             IS 'Lookup: how a template variable is resolved at render time.';
COMMENT ON COLUMN "05_notify"."08_dim_variable_types".id          IS 'SMALLINT primary key.';
COMMENT ON COLUMN "05_notify"."08_dim_variable_types".code        IS 'Machine-readable type code.';
COMMENT ON COLUMN "05_notify"."08_dim_variable_types".label       IS 'Human-readable variable resolution type.';
COMMENT ON COLUMN "05_notify"."08_dim_variable_types".description IS 'Describes how the variable value is sourced during rendering.';
COMMENT ON COLUMN "05_notify"."08_dim_variable_types".deprecated_at IS 'NULL = active.';

INSERT INTO "05_notify"."08_dim_variable_types" (id, code, label, description) VALUES
    (1, 'static',       'Static',       'Fixed value stored in static_value column. Never changes.'),
    (2, 'dynamic_attr', 'Dynamic Attr', 'Resolved from an EAV attr_def at render time via dynamic_attr_def_id.'),
    (3, 'query',        'Query',        'Resolved by running a saved variable query (query_id) and extracting a column.')
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 10_fct_providers
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "05_notify"."10_fct_providers" (
    id                VARCHAR(36)   NOT NULL,
    org_id            VARCHAR(36)   NULL,
    provider_type_id  SMALLINT      NOT NULL,
    name              TEXT          NOT NULL,
    config_encrypted  TEXT          NOT NULL,
    vault_key_ref     TEXT          NULL,
    is_default        BOOLEAN       NOT NULL DEFAULT FALSE,
    priority          SMALLINT      NOT NULL DEFAULT 10,
    is_active         BOOLEAN       NOT NULL DEFAULT TRUE,
    is_test           BOOLEAN       NOT NULL DEFAULT FALSE,
    deleted_at        TIMESTAMP     NULL,
    created_by        VARCHAR(36)   NOT NULL,
    updated_by        VARCHAR(36)   NOT NULL,
    created_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fct_providers                 PRIMARY KEY (id),
    CONSTRAINT fk_fct_providers_provider_type   FOREIGN KEY (provider_type_id) REFERENCES "05_notify"."03_dim_provider_types" (id),
    CONSTRAINT fk_fct_providers_org             FOREIGN KEY (org_id) REFERENCES "02_iam"."01_fct_org_orgs" (id)
);

CREATE TRIGGER trg_fct_providers_updated_at
BEFORE UPDATE ON "05_notify"."10_fct_providers"
FOR EACH ROW EXECUTE FUNCTION "05_notify".set_updated_at();

CREATE INDEX idx_fct_providers_live
    ON "05_notify"."10_fct_providers" (org_id, created_at DESC)
    WHERE deleted_at IS NULL;

COMMENT ON TABLE  "05_notify"."10_fct_providers"                  IS 'Notification provider configurations. org_id NULL = platform-global fallback provider.';
COMMENT ON COLUMN "05_notify"."10_fct_providers".id               IS 'UUID v7 primary key.';
COMMENT ON COLUMN "05_notify"."10_fct_providers".org_id           IS 'FK to 02_iam.11_fct_orgs. NULL = global platform provider available to all orgs.';
COMMENT ON COLUMN "05_notify"."10_fct_providers".provider_type_id IS 'FK to 03_dim_provider_types. Determines which channel and integration class to use.';
COMMENT ON COLUMN "05_notify"."10_fct_providers".name             IS 'Human-readable name for this provider configuration.';
COMMENT ON COLUMN "05_notify"."10_fct_providers".config_encrypted IS 'AES-256-GCM encrypted JSON blob containing provider credentials and settings.';
COMMENT ON COLUMN "05_notify"."10_fct_providers".vault_key_ref    IS 'Optional reference to the vault key used for encryption. NULL = VAULT_MASTER_KEY.';
COMMENT ON COLUMN "05_notify"."10_fct_providers".is_default       IS 'TRUE = preferred provider for this channel within the org. At most one per channel per org.';
COMMENT ON COLUMN "05_notify"."10_fct_providers".priority         IS 'Lower number = tried first in failover order. Default 10.';
COMMENT ON COLUMN "05_notify"."10_fct_providers".is_active        IS 'FALSE = provider disabled, skipped during dispatch.';
COMMENT ON COLUMN "05_notify"."10_fct_providers".is_test          IS 'TRUE = test/seed record. Excluded from production dispatch.';
COMMENT ON COLUMN "05_notify"."10_fct_providers".deleted_at       IS 'NULL = active. SET = soft-deleted, excluded from all queries.';
COMMENT ON COLUMN "05_notify"."10_fct_providers".created_by       IS 'User ID or system identifier that created this record.';
COMMENT ON COLUMN "05_notify"."10_fct_providers".updated_by       IS 'User ID or system identifier that last modified this record.';
COMMENT ON COLUMN "05_notify"."10_fct_providers".created_at       IS 'Timestamp when the record was created (UTC).';
COMMENT ON COLUMN "05_notify"."10_fct_providers".updated_at       IS 'Timestamp of last modification. Set automatically by trigger.';

-- ---------------------------------------------------------------------------
-- 12_fct_templates
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "05_notify"."12_fct_templates" (
    id                VARCHAR(36)   NOT NULL,
    org_id            VARCHAR(36)   NOT NULL,
    code              TEXT          NOT NULL,
    name              TEXT          NOT NULL,
    channel_id        SMALLINT      NOT NULL,
    category_id       SMALLINT      NOT NULL,
    active_version_id VARCHAR(36)   NULL,
    is_active         BOOLEAN       NOT NULL DEFAULT TRUE,
    is_test           BOOLEAN       NOT NULL DEFAULT FALSE,
    deleted_at        TIMESTAMP     NULL,
    created_by        VARCHAR(36)   NOT NULL,
    updated_by        VARCHAR(36)   NOT NULL,
    created_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fct_templates              PRIMARY KEY (id),
    CONSTRAINT uq_fct_templates_org_code     UNIQUE (org_id, code),
    CONSTRAINT fk_fct_templates_org          FOREIGN KEY (org_id) REFERENCES "02_iam"."01_fct_org_orgs" (id),
    CONSTRAINT fk_fct_templates_channel      FOREIGN KEY (channel_id) REFERENCES "05_notify"."02_dim_channels" (id),
    CONSTRAINT fk_fct_templates_category     FOREIGN KEY (category_id) REFERENCES "05_notify"."06_dim_notification_categories" (id)
);

CREATE TRIGGER trg_fct_templates_updated_at
BEFORE UPDATE ON "05_notify"."12_fct_templates"
FOR EACH ROW EXECUTE FUNCTION "05_notify".set_updated_at();

CREATE INDEX idx_fct_templates_live
    ON "05_notify"."12_fct_templates" (org_id, created_at DESC)
    WHERE deleted_at IS NULL;

COMMENT ON TABLE  "05_notify"."12_fct_templates"                   IS 'Notification templates. Each template is versioned; active_version_id points to the live version.';
COMMENT ON COLUMN "05_notify"."12_fct_templates".id                IS 'UUID v7 primary key.';
COMMENT ON COLUMN "05_notify"."12_fct_templates".org_id            IS 'FK to 02_iam.11_fct_orgs. Template is scoped to this organisation.';
COMMENT ON COLUMN "05_notify"."12_fct_templates".code              IS 'Org-unique machine code. Used to reference the template from rules and API calls.';
COMMENT ON COLUMN "05_notify"."12_fct_templates".name              IS 'Human-readable template name.';
COMMENT ON COLUMN "05_notify"."12_fct_templates".channel_id        IS 'FK to 02_dim_channels. Channel this template is designed for.';
COMMENT ON COLUMN "05_notify"."12_fct_templates".category_id       IS 'FK to 06_dim_notification_categories. Category for opt-out preference checks.';
COMMENT ON COLUMN "05_notify"."12_fct_templates".active_version_id IS 'FK to 30_dtl_template_versions. The currently published version. NULL = no published version yet.';
COMMENT ON COLUMN "05_notify"."12_fct_templates".is_active         IS 'FALSE = template disabled, cannot be dispatched.';
COMMENT ON COLUMN "05_notify"."12_fct_templates".is_test           IS 'TRUE = test/seed record.';
COMMENT ON COLUMN "05_notify"."12_fct_templates".deleted_at        IS 'NULL = active. SET = soft-deleted.';
COMMENT ON COLUMN "05_notify"."12_fct_templates".created_by        IS 'User ID that created this template.';
COMMENT ON COLUMN "05_notify"."12_fct_templates".updated_by        IS 'User ID that last modified this template.';
COMMENT ON COLUMN "05_notify"."12_fct_templates".created_at        IS 'Creation timestamp (UTC).';
COMMENT ON COLUMN "05_notify"."12_fct_templates".updated_at        IS 'Last modification timestamp. Set by trigger.';

-- ---------------------------------------------------------------------------
-- 14_fct_notification_rules
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "05_notify"."14_fct_notification_rules" (
    id                      VARCHAR(36)   NOT NULL,
    org_id                  VARCHAR(36)   NOT NULL,
    code                    TEXT          NOT NULL,
    name                    TEXT          NOT NULL,
    description             TEXT          NOT NULL DEFAULT '',
    source_event_type       TEXT          NOT NULL,
    source_entity_type_id   SMALLINT      NULL,
    category_id             SMALLINT      NOT NULL,
    recipient_strategy_id   SMALLINT      NOT NULL,
    recipient_filter        JSONB         NOT NULL DEFAULT '{}',
    delay_seconds           INTEGER       NOT NULL DEFAULT 0,
    is_active               BOOLEAN       NOT NULL DEFAULT TRUE,
    is_test                 BOOLEAN       NOT NULL DEFAULT FALSE,
    deleted_at              TIMESTAMP     NULL,
    created_by              VARCHAR(36)   NOT NULL,
    updated_by              VARCHAR(36)   NOT NULL,
    created_at              TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fct_notification_rules              PRIMARY KEY (id),
    CONSTRAINT uq_fct_notification_rules_org_code     UNIQUE (org_id, code),
    CONSTRAINT fk_fct_notification_rules_org          FOREIGN KEY (org_id) REFERENCES "02_iam"."01_fct_org_orgs" (id),
    CONSTRAINT fk_fct_notification_rules_category     FOREIGN KEY (category_id) REFERENCES "05_notify"."06_dim_notification_categories" (id),
    CONSTRAINT fk_fct_notification_rules_strategy     FOREIGN KEY (recipient_strategy_id) REFERENCES "05_notify"."07_dim_recipient_strategies" (id)
);

CREATE TRIGGER trg_fct_notification_rules_updated_at
BEFORE UPDATE ON "05_notify"."14_fct_notification_rules"
FOR EACH ROW EXECUTE FUNCTION "05_notify".set_updated_at();

CREATE INDEX idx_fct_notification_rules_live
    ON "05_notify"."14_fct_notification_rules" (org_id, source_event_type)
    WHERE deleted_at IS NULL AND is_active = TRUE;

COMMENT ON TABLE  "05_notify"."14_fct_notification_rules"                        IS 'Notification dispatch rules. Each rule listens for a source event and routes to channels.';
COMMENT ON COLUMN "05_notify"."14_fct_notification_rules".id                     IS 'UUID v7 primary key.';
COMMENT ON COLUMN "05_notify"."14_fct_notification_rules".org_id                 IS 'FK to 02_iam.11_fct_orgs. Rule is scoped to this organisation.';
COMMENT ON COLUMN "05_notify"."14_fct_notification_rules".code                   IS 'Org-unique machine code for this rule.';
COMMENT ON COLUMN "05_notify"."14_fct_notification_rules".name                   IS 'Human-readable rule name.';
COMMENT ON COLUMN "05_notify"."14_fct_notification_rules".description            IS 'Optional description of what this rule does.';
COMMENT ON COLUMN "05_notify"."14_fct_notification_rules".source_event_type      IS 'Event type string that triggers this rule. E.g. user.login, invoice.paid.';
COMMENT ON COLUMN "05_notify"."14_fct_notification_rules".source_entity_type_id  IS 'Optional EAV entity_type_id to further scope event matching.';
COMMENT ON COLUMN "05_notify"."14_fct_notification_rules".category_id            IS 'FK to 06_dim_notification_categories. Category for preference opt-out checks.';
COMMENT ON COLUMN "05_notify"."14_fct_notification_rules".recipient_strategy_id  IS 'FK to 07_dim_recipient_strategies. How to resolve recipients from the event.';
COMMENT ON COLUMN "05_notify"."14_fct_notification_rules".recipient_filter       IS 'JSONB parameters for the recipient strategy. E.g. {"workspace_id": "..."}.';
COMMENT ON COLUMN "05_notify"."14_fct_notification_rules".delay_seconds          IS 'Seconds to delay dispatch after event fires. 0 = immediate.';
COMMENT ON COLUMN "05_notify"."14_fct_notification_rules".is_active              IS 'FALSE = rule disabled, not evaluated during dispatch.';
COMMENT ON COLUMN "05_notify"."14_fct_notification_rules".is_test                IS 'TRUE = test/seed record.';
COMMENT ON COLUMN "05_notify"."14_fct_notification_rules".deleted_at             IS 'NULL = active. SET = soft-deleted.';
COMMENT ON COLUMN "05_notify"."14_fct_notification_rules".created_by             IS 'User ID that created this rule.';
COMMENT ON COLUMN "05_notify"."14_fct_notification_rules".updated_by             IS 'User ID that last modified this rule.';
COMMENT ON COLUMN "05_notify"."14_fct_notification_rules".created_at             IS 'Creation timestamp (UTC).';
COMMENT ON COLUMN "05_notify"."14_fct_notification_rules".updated_at             IS 'Last modification timestamp. Set by trigger.';

-- ---------------------------------------------------------------------------
-- 16_fct_variable_queries
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "05_notify"."16_fct_variable_queries" (
    id              VARCHAR(36)   NOT NULL,
    org_id          VARCHAR(36)   NOT NULL,
    code            TEXT          NOT NULL,
    name            TEXT          NOT NULL,
    description     TEXT          NOT NULL DEFAULT '',
    query_text      TEXT          NOT NULL,
    param_mapping   JSONB         NOT NULL DEFAULT '{}',
    result_columns  JSONB         NOT NULL DEFAULT '[]',
    is_active       BOOLEAN       NOT NULL DEFAULT TRUE,
    is_test         BOOLEAN       NOT NULL DEFAULT FALSE,
    deleted_at      TIMESTAMP     NULL,
    created_by      VARCHAR(36)   NOT NULL,
    updated_by      VARCHAR(36)   NOT NULL,
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fct_variable_queries          PRIMARY KEY (id),
    CONSTRAINT uq_fct_variable_queries_org_code UNIQUE (org_id, code),
    CONSTRAINT fk_fct_variable_queries_org      FOREIGN KEY (org_id) REFERENCES "02_iam"."01_fct_org_orgs" (id)
);

CREATE TRIGGER trg_fct_variable_queries_updated_at
BEFORE UPDATE ON "05_notify"."16_fct_variable_queries"
FOR EACH ROW EXECUTE FUNCTION "05_notify".set_updated_at();

CREATE INDEX idx_fct_variable_queries_live
    ON "05_notify"."16_fct_variable_queries" (org_id, created_at DESC)
    WHERE deleted_at IS NULL;

COMMENT ON TABLE  "05_notify"."16_fct_variable_queries"               IS 'Saved SQL queries used to resolve dynamic template variables at render time.';
COMMENT ON COLUMN "05_notify"."16_fct_variable_queries".id            IS 'UUID v7 primary key.';
COMMENT ON COLUMN "05_notify"."16_fct_variable_queries".org_id        IS 'FK to 02_iam.11_fct_orgs. Query is scoped to this organisation.';
COMMENT ON COLUMN "05_notify"."16_fct_variable_queries".code          IS 'Org-unique machine code for this query.';
COMMENT ON COLUMN "05_notify"."16_fct_variable_queries".name          IS 'Human-readable query name.';
COMMENT ON COLUMN "05_notify"."16_fct_variable_queries".description   IS 'What this query retrieves and when it is used.';
COMMENT ON COLUMN "05_notify"."16_fct_variable_queries".query_text    IS 'Parameterised SQL query text. Parameters reference keys from param_mapping.';
COMMENT ON COLUMN "05_notify"."16_fct_variable_queries".param_mapping IS 'JSONB map of query param name to event context key. E.g. {"user_id": "actor_id"}.';
COMMENT ON COLUMN "05_notify"."16_fct_variable_queries".result_columns IS 'JSONB array of column names the query is expected to return.';
COMMENT ON COLUMN "05_notify"."16_fct_variable_queries".is_active     IS 'FALSE = query disabled.';
COMMENT ON COLUMN "05_notify"."16_fct_variable_queries".is_test       IS 'TRUE = test/seed record.';
COMMENT ON COLUMN "05_notify"."16_fct_variable_queries".deleted_at    IS 'NULL = active. SET = soft-deleted.';
COMMENT ON COLUMN "05_notify"."16_fct_variable_queries".created_by    IS 'User ID that created this record.';
COMMENT ON COLUMN "05_notify"."16_fct_variable_queries".updated_by    IS 'User ID that last modified this record.';
COMMENT ON COLUMN "05_notify"."16_fct_variable_queries".created_at    IS 'Creation timestamp (UTC).';
COMMENT ON COLUMN "05_notify"."16_fct_variable_queries".updated_at    IS 'Last modification timestamp. Set by trigger.';

-- ---------------------------------------------------------------------------
-- 18_fct_in_app_notifications
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "05_notify"."18_fct_in_app_notifications" (
    id           VARCHAR(36)   NOT NULL,
    org_id       VARCHAR(36)   NOT NULL,
    user_id      VARCHAR(36)   NOT NULL,
    title        TEXT          NOT NULL,
    body         TEXT          NOT NULL,
    category_id  SMALLINT      NOT NULL,
    action_url   TEXT          NULL,
    is_read      BOOLEAN       NOT NULL DEFAULT FALSE,
    is_archived  BOOLEAN       NOT NULL DEFAULT FALSE,
    read_at      TIMESTAMP     NULL,
    archived_at  TIMESTAMP     NULL,
    created_at   TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fct_in_app_notifications          PRIMARY KEY (id),
    CONSTRAINT fk_fct_in_app_notifications_org      FOREIGN KEY (org_id) REFERENCES "02_iam"."01_fct_org_orgs" (id),
    CONSTRAINT fk_fct_in_app_notifications_category FOREIGN KEY (category_id) REFERENCES "05_notify"."06_dim_notification_categories" (id)
);

CREATE INDEX idx_fct_in_app_notifications_user
    ON "05_notify"."18_fct_in_app_notifications" (user_id, org_id, created_at DESC)
    WHERE is_archived = FALSE;

CREATE INDEX idx_fct_in_app_notifications_unread
    ON "05_notify"."18_fct_in_app_notifications" (user_id, org_id)
    WHERE is_read = FALSE AND is_archived = FALSE;

COMMENT ON TABLE  "05_notify"."18_fct_in_app_notifications"              IS 'In-app notification feed entries. Append-only insert; state transitions via UPDATE only.';
COMMENT ON COLUMN "05_notify"."18_fct_in_app_notifications".id           IS 'UUID v7 primary key.';
COMMENT ON COLUMN "05_notify"."18_fct_in_app_notifications".org_id       IS 'FK to 02_iam.11_fct_orgs. Organisation scope.';
COMMENT ON COLUMN "05_notify"."18_fct_in_app_notifications".user_id      IS 'FK to 02_iam.10_fct_users. Recipient user.';
COMMENT ON COLUMN "05_notify"."18_fct_in_app_notifications".title        IS 'Short notification title (maps to subject_line at render time).';
COMMENT ON COLUMN "05_notify"."18_fct_in_app_notifications".body         IS 'Notification body text (body_short from rendered template).';
COMMENT ON COLUMN "05_notify"."18_fct_in_app_notifications".category_id  IS 'FK to 06_dim_notification_categories. Category for frontend filtering.';
COMMENT ON COLUMN "05_notify"."18_fct_in_app_notifications".action_url   IS 'Optional deep-link URL the user is taken to when clicking the notification.';
COMMENT ON COLUMN "05_notify"."18_fct_in_app_notifications".is_read      IS 'TRUE = user has seen this notification.';
COMMENT ON COLUMN "05_notify"."18_fct_in_app_notifications".is_archived  IS 'TRUE = user has dismissed/archived this notification.';
COMMENT ON COLUMN "05_notify"."18_fct_in_app_notifications".read_at      IS 'Timestamp when the notification was first read. NULL = unread.';
COMMENT ON COLUMN "05_notify"."18_fct_in_app_notifications".archived_at  IS 'Timestamp when the notification was archived. NULL = not archived.';
COMMENT ON COLUMN "05_notify"."18_fct_in_app_notifications".created_at   IS 'Delivery timestamp (UTC). Immutable after insert.';

-- ---------------------------------------------------------------------------
-- 20_fct_web_push_subscriptions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "05_notify"."20_fct_web_push_subscriptions" (
    id          VARCHAR(36)   NOT NULL,
    org_id      VARCHAR(36)   NOT NULL,
    user_id     VARCHAR(36)   NOT NULL,
    endpoint    TEXT          NOT NULL,
    p256dh_key  TEXT          NOT NULL,
    auth_key    TEXT          NOT NULL,
    user_agent  TEXT          NULL,
    is_active   BOOLEAN       NOT NULL DEFAULT TRUE,
    is_test     BOOLEAN       NOT NULL DEFAULT FALSE,
    deleted_at  TIMESTAMP     NULL,
    created_by  VARCHAR(36)   NOT NULL,
    updated_by  VARCHAR(36)   NULL,
    created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fct_web_push_subscriptions      PRIMARY KEY (id),
    CONSTRAINT uq_fct_web_push_subscriptions_ep   UNIQUE (user_id, endpoint),
    CONSTRAINT fk_fct_web_push_subscriptions_org  FOREIGN KEY (org_id) REFERENCES "02_iam"."01_fct_org_orgs" (id)
);

CREATE TRIGGER trg_fct_web_push_subscriptions_updated_at
BEFORE UPDATE ON "05_notify"."20_fct_web_push_subscriptions"
FOR EACH ROW EXECUTE FUNCTION "05_notify".set_updated_at();

CREATE INDEX idx_fct_web_push_subscriptions_live
    ON "05_notify"."20_fct_web_push_subscriptions" (user_id)
    WHERE is_active = TRUE AND deleted_at IS NULL;

COMMENT ON TABLE  "05_notify"."20_fct_web_push_subscriptions"             IS 'VAPID Web Push endpoint subscriptions for users. Upserted on browser re-registration.';
COMMENT ON COLUMN "05_notify"."20_fct_web_push_subscriptions".id          IS 'UUID v7 primary key.';
COMMENT ON COLUMN "05_notify"."20_fct_web_push_subscriptions".org_id      IS 'FK to 02_iam.11_fct_orgs. Organisation scope.';
COMMENT ON COLUMN "05_notify"."20_fct_web_push_subscriptions".user_id     IS 'User who registered this subscription.';
COMMENT ON COLUMN "05_notify"."20_fct_web_push_subscriptions".endpoint    IS 'Push service URL provided by the browser. Part of the unique key.';
COMMENT ON COLUMN "05_notify"."20_fct_web_push_subscriptions".p256dh_key  IS 'Recipient public key (base64url). Required for encrypting the push payload.';
COMMENT ON COLUMN "05_notify"."20_fct_web_push_subscriptions".auth_key    IS 'Auth secret (base64url). Required for encrypting the push payload.';
COMMENT ON COLUMN "05_notify"."20_fct_web_push_subscriptions".user_agent  IS 'Browser user-agent string at registration time.';
COMMENT ON COLUMN "05_notify"."20_fct_web_push_subscriptions".is_active   IS 'FALSE = subscription expired or user unsubscribed.';
COMMENT ON COLUMN "05_notify"."20_fct_web_push_subscriptions".is_test     IS 'TRUE = test/seed record.';
COMMENT ON COLUMN "05_notify"."20_fct_web_push_subscriptions".deleted_at  IS 'NULL = active. SET = soft-deleted (unsubscribed).';
COMMENT ON COLUMN "05_notify"."20_fct_web_push_subscriptions".created_by  IS 'User ID that registered the subscription.';
COMMENT ON COLUMN "05_notify"."20_fct_web_push_subscriptions".updated_by  IS 'User ID or system that last modified this record.';
COMMENT ON COLUMN "05_notify"."20_fct_web_push_subscriptions".created_at  IS 'Registration timestamp (UTC).';
COMMENT ON COLUMN "05_notify"."20_fct_web_push_subscriptions".updated_at  IS 'Last modification timestamp. Set by trigger.';

-- ---------------------------------------------------------------------------
-- 30_dtl_template_versions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "05_notify"."30_dtl_template_versions" (
    id              VARCHAR(36)   NOT NULL,
    template_id     VARCHAR(36)   NOT NULL,
    version_number  INTEGER       NOT NULL,
    subject_line    TEXT          NOT NULL DEFAULT '',
    body_html       TEXT          NOT NULL DEFAULT '',
    body_text       TEXT          NOT NULL DEFAULT '',
    body_short      TEXT          NOT NULL DEFAULT '',
    metadata        JSONB         NOT NULL DEFAULT '{}',
    change_notes    TEXT          NOT NULL DEFAULT '',
    created_by      VARCHAR(36)   NOT NULL,
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_dtl_template_versions             PRIMARY KEY (id),
    CONSTRAINT uq_dtl_template_versions_num         UNIQUE (template_id, version_number),
    CONSTRAINT fk_dtl_template_versions_template    FOREIGN KEY (template_id) REFERENCES "05_notify"."12_fct_templates" (id)
);

CREATE INDEX idx_dtl_template_versions_template
    ON "05_notify"."30_dtl_template_versions" (template_id, version_number DESC);

COMMENT ON TABLE  "05_notify"."30_dtl_template_versions"               IS 'Immutable version snapshots for notification templates. Each publish creates a new row.';
COMMENT ON COLUMN "05_notify"."30_dtl_template_versions".id            IS 'UUID v7 primary key.';
COMMENT ON COLUMN "05_notify"."30_dtl_template_versions".template_id   IS 'FK to 12_fct_templates. Parent template.';
COMMENT ON COLUMN "05_notify"."30_dtl_template_versions".version_number IS 'Monotonically increasing version counter per template. Starts at 1.';
COMMENT ON COLUMN "05_notify"."30_dtl_template_versions".subject_line  IS 'Email subject line or notification title for this version.';
COMMENT ON COLUMN "05_notify"."30_dtl_template_versions".body_html     IS 'Full HTML email body. May contain {{variable}} placeholders.';
COMMENT ON COLUMN "05_notify"."30_dtl_template_versions".body_text     IS 'Plain-text fallback email body.';
COMMENT ON COLUMN "05_notify"."30_dtl_template_versions".body_short    IS 'Short notification body for in-app and push (max 120 chars recommended).';
COMMENT ON COLUMN "05_notify"."30_dtl_template_versions".metadata      IS 'JSONB: extra rendering hints, preview data, A/B variant info.';
COMMENT ON COLUMN "05_notify"."30_dtl_template_versions".change_notes  IS 'Free-text notes describing what changed in this version.';
COMMENT ON COLUMN "05_notify"."30_dtl_template_versions".created_by    IS 'User ID that published this version.';
COMMENT ON COLUMN "05_notify"."30_dtl_template_versions".created_at    IS 'Publication timestamp (UTC). Immutable.';

-- Add deferred FK from 12_fct_templates.active_version_id to 30_dtl_template_versions.id
ALTER TABLE "05_notify"."12_fct_templates"
    ADD CONSTRAINT fk_fct_templates_active_version
    FOREIGN KEY (active_version_id) REFERENCES "05_notify"."30_dtl_template_versions" (id)
    DEFERRABLE INITIALLY DEFERRED;

-- ---------------------------------------------------------------------------
-- 32_dtl_template_variables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "05_notify"."32_dtl_template_variables" (
    id                   VARCHAR(36)   NOT NULL,
    template_id          VARCHAR(36)   NOT NULL,
    variable_key         TEXT          NOT NULL,
    variable_type_id     SMALLINT      NOT NULL,
    static_value         TEXT          NULL,
    dynamic_attr_def_id  INTEGER       NULL,
    query_id             VARCHAR(36)   NULL,
    query_result_column  TEXT          NULL,
    is_required          BOOLEAN       NOT NULL DEFAULT TRUE,
    default_value        TEXT          NULL,
    CONSTRAINT pk_dtl_template_variables             PRIMARY KEY (id),
    CONSTRAINT uq_dtl_template_variables_key         UNIQUE (template_id, variable_key),
    CONSTRAINT fk_dtl_template_variables_template    FOREIGN KEY (template_id) REFERENCES "05_notify"."12_fct_templates" (id),
    CONSTRAINT fk_dtl_template_variables_type        FOREIGN KEY (variable_type_id) REFERENCES "05_notify"."08_dim_variable_types" (id),
    CONSTRAINT fk_dtl_template_variables_query       FOREIGN KEY (query_id) REFERENCES "05_notify"."16_fct_variable_queries" (id)
);

CREATE INDEX idx_dtl_template_variables_template
    ON "05_notify"."32_dtl_template_variables" (template_id);

COMMENT ON TABLE  "05_notify"."32_dtl_template_variables"                    IS 'Variable definitions for a template. Declares how each {{variable}} placeholder is resolved.';
COMMENT ON COLUMN "05_notify"."32_dtl_template_variables".id                 IS 'UUID v7 primary key.';
COMMENT ON COLUMN "05_notify"."32_dtl_template_variables".template_id        IS 'FK to 12_fct_templates. Parent template.';
COMMENT ON COLUMN "05_notify"."32_dtl_template_variables".variable_key       IS 'The placeholder key. E.g. user_name maps to {{user_name}} in template body.';
COMMENT ON COLUMN "05_notify"."32_dtl_template_variables".variable_type_id   IS 'FK to 08_dim_variable_types. How the value is resolved (static/dynamic_attr/query).';
COMMENT ON COLUMN "05_notify"."32_dtl_template_variables".static_value       IS 'For type=static: the fixed value to inject. NULL for other types.';
COMMENT ON COLUMN "05_notify"."32_dtl_template_variables".dynamic_attr_def_id IS 'For type=dynamic_attr: EAV attr_def_id to resolve from the entity at render time.';
COMMENT ON COLUMN "05_notify"."32_dtl_template_variables".query_id           IS 'For type=query: FK to 16_fct_variable_queries. Query to execute at render time.';
COMMENT ON COLUMN "05_notify"."32_dtl_template_variables".query_result_column IS 'Column name to extract from the query result set.';
COMMENT ON COLUMN "05_notify"."32_dtl_template_variables".is_required        IS 'TRUE = render fails if value cannot be resolved. FALSE = fall back to default_value.';
COMMENT ON COLUMN "05_notify"."32_dtl_template_variables".default_value      IS 'Fallback value when is_required=FALSE and resolution fails.';

-- ---------------------------------------------------------------------------
-- 40_lnk_rule_channels
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "05_notify"."40_lnk_rule_channels" (
    id           VARCHAR(36)   NOT NULL,
    rule_id      VARCHAR(36)   NOT NULL,
    channel_id   SMALLINT      NOT NULL,
    template_id  VARCHAR(36)   NOT NULL,
    created_by   VARCHAR(36)   NOT NULL,
    created_at   TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_lnk_rule_channels            PRIMARY KEY (id),
    CONSTRAINT uq_lnk_rule_channels_rule_ch    UNIQUE (rule_id, channel_id),
    CONSTRAINT fk_lnk_rule_channels_rule       FOREIGN KEY (rule_id) REFERENCES "05_notify"."14_fct_notification_rules" (id),
    CONSTRAINT fk_lnk_rule_channels_channel    FOREIGN KEY (channel_id) REFERENCES "05_notify"."02_dim_channels" (id),
    CONSTRAINT fk_lnk_rule_channels_template   FOREIGN KEY (template_id) REFERENCES "05_notify"."12_fct_templates" (id)
);

CREATE INDEX idx_lnk_rule_channels_rule
    ON "05_notify"."40_lnk_rule_channels" (rule_id);

COMMENT ON TABLE  "05_notify"."40_lnk_rule_channels"              IS 'Links a notification rule to its delivery channels and the template for each channel.';
COMMENT ON COLUMN "05_notify"."40_lnk_rule_channels".id           IS 'UUID v7 primary key.';
COMMENT ON COLUMN "05_notify"."40_lnk_rule_channels".rule_id      IS 'FK to 14_fct_notification_rules. Parent rule.';
COMMENT ON COLUMN "05_notify"."40_lnk_rule_channels".channel_id   IS 'FK to 02_dim_channels. The delivery channel for this rule-channel pair.';
COMMENT ON COLUMN "05_notify"."40_lnk_rule_channels".template_id  IS 'FK to 12_fct_templates. Template to render for this channel.';
COMMENT ON COLUMN "05_notify"."40_lnk_rule_channels".created_by   IS 'User ID that created this assignment.';
COMMENT ON COLUMN "05_notify"."40_lnk_rule_channels".created_at   IS 'Creation timestamp (UTC). Immutable — lnk rows are never updated.';

-- ---------------------------------------------------------------------------
-- 42_lnk_user_preferences
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "05_notify"."42_lnk_user_preferences" (
    id           VARCHAR(36)   NOT NULL,
    org_id       VARCHAR(36)   NOT NULL,
    user_id      VARCHAR(36)   NOT NULL,
    channel_id   SMALLINT      NULL,
    category_id  SMALLINT      NULL,
    is_enabled   BOOLEAN       NOT NULL DEFAULT TRUE,
    created_by   VARCHAR(36)   NOT NULL,
    created_at   TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_lnk_user_preferences         PRIMARY KEY (id),
    CONSTRAINT fk_lnk_user_preferences_org     FOREIGN KEY (org_id) REFERENCES "02_iam"."01_fct_org_orgs" (id),
    CONSTRAINT fk_lnk_user_preferences_channel  FOREIGN KEY (channel_id) REFERENCES "05_notify"."02_dim_channels" (id),
    CONSTRAINT fk_lnk_user_preferences_category FOREIGN KEY (category_id) REFERENCES "05_notify"."06_dim_notification_categories" (id)
);

-- Partial unique indexes enforce one preference per (org, user, channel, category) scope.
-- Four partial indexes cover all NULL combinations because NULLS NOT DISTINCT
-- is not available in PostgreSQL 14.
CREATE UNIQUE INDEX uq_lnk_user_preferences_scope_all
    ON "05_notify"."42_lnk_user_preferences" (org_id, user_id, channel_id, category_id)
    WHERE channel_id IS NOT NULL AND category_id IS NOT NULL;

CREATE UNIQUE INDEX uq_lnk_user_preferences_scope_ch_only
    ON "05_notify"."42_lnk_user_preferences" (org_id, user_id, channel_id)
    WHERE channel_id IS NOT NULL AND category_id IS NULL;

CREATE UNIQUE INDEX uq_lnk_user_preferences_scope_cat_only
    ON "05_notify"."42_lnk_user_preferences" (org_id, user_id, category_id)
    WHERE channel_id IS NULL AND category_id IS NOT NULL;

CREATE UNIQUE INDEX uq_lnk_user_preferences_scope_global
    ON "05_notify"."42_lnk_user_preferences" (org_id, user_id)
    WHERE channel_id IS NULL AND category_id IS NULL;

CREATE TRIGGER trg_lnk_user_preferences_updated_at
BEFORE UPDATE ON "05_notify"."42_lnk_user_preferences"
FOR EACH ROW EXECUTE FUNCTION "05_notify".set_updated_at();

CREATE INDEX idx_lnk_user_preferences_user
    ON "05_notify"."42_lnk_user_preferences" (user_id, org_id);

COMMENT ON TABLE  "05_notify"."42_lnk_user_preferences"             IS 'User notification opt-in/opt-out preferences. Supports global, per-channel, per-category, and per-channel+category scopes.';
COMMENT ON COLUMN "05_notify"."42_lnk_user_preferences".id          IS 'UUID v7 primary key.';
COMMENT ON COLUMN "05_notify"."42_lnk_user_preferences".org_id      IS 'FK to 02_iam.11_fct_orgs. Organisation scope.';
COMMENT ON COLUMN "05_notify"."42_lnk_user_preferences".user_id     IS 'User this preference applies to.';
COMMENT ON COLUMN "05_notify"."42_lnk_user_preferences".channel_id  IS 'FK to 02_dim_channels. NULL = applies to all channels.';
COMMENT ON COLUMN "05_notify"."42_lnk_user_preferences".category_id IS 'FK to 06_dim_notification_categories. NULL = applies to all categories.';
COMMENT ON COLUMN "05_notify"."42_lnk_user_preferences".is_enabled  IS 'FALSE = user has opted out of this scope. Checked during dispatch.';
COMMENT ON COLUMN "05_notify"."42_lnk_user_preferences".created_by  IS 'User ID or system that created this preference.';
COMMENT ON COLUMN "05_notify"."42_lnk_user_preferences".created_at  IS 'Creation timestamp (UTC).';
COMMENT ON COLUMN "05_notify"."42_lnk_user_preferences".updated_at  IS 'Last modification timestamp. Set by trigger on upsert.';

-- ---------------------------------------------------------------------------
-- 60_evt_send_log
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "05_notify"."60_evt_send_log" (
    id                   VARCHAR(36)   NOT NULL,
    org_id               VARCHAR(36)   NOT NULL,
    rule_id              VARCHAR(36)   NULL,
    campaign_id          VARCHAR(36)   NULL,
    template_id          VARCHAR(36)   NOT NULL,
    template_version_id  VARCHAR(36)   NOT NULL,
    channel_id           SMALLINT      NOT NULL,
    provider_id          VARCHAR(36)   NULL,
    recipient_user_id    VARCHAR(36)   NULL,
    recipient_address    TEXT          NOT NULL,
    status_id            SMALLINT      NOT NULL,
    rendered_subject     TEXT          NOT NULL DEFAULT '',
    provider_message_id  TEXT          NULL,
    error_message        TEXT          NULL,
    metadata             JSONB         NOT NULL DEFAULT '{}',
    created_at           TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_evt_send_log                   PRIMARY KEY (id),
    CONSTRAINT fk_evt_send_log_org               FOREIGN KEY (org_id) REFERENCES "02_iam"."01_fct_org_orgs" (id),
    CONSTRAINT fk_evt_send_log_template          FOREIGN KEY (template_id) REFERENCES "05_notify"."12_fct_templates" (id),
    CONSTRAINT fk_evt_send_log_template_version  FOREIGN KEY (template_version_id) REFERENCES "05_notify"."30_dtl_template_versions" (id),
    CONSTRAINT fk_evt_send_log_channel           FOREIGN KEY (channel_id) REFERENCES "05_notify"."02_dim_channels" (id)
);

CREATE INDEX idx_evt_send_log_org
    ON "05_notify"."60_evt_send_log" (org_id, created_at DESC);

CREATE INDEX idx_evt_send_log_provider_msg
    ON "05_notify"."60_evt_send_log" (provider_message_id)
    WHERE provider_message_id IS NOT NULL;

CREATE INDEX idx_evt_send_log_rule
    ON "05_notify"."60_evt_send_log" (rule_id)
    WHERE rule_id IS NOT NULL;

COMMENT ON TABLE  "05_notify"."60_evt_send_log"                      IS 'Append-only send log. One row per dispatch attempt. Background job purges rows older than 90 days.';
COMMENT ON COLUMN "05_notify"."60_evt_send_log".id                   IS 'UUID v7 primary key.';
COMMENT ON COLUMN "05_notify"."60_evt_send_log".org_id               IS 'FK to 02_iam.11_fct_orgs. Organisation that owns this send.';
COMMENT ON COLUMN "05_notify"."60_evt_send_log".rule_id              IS 'FK to 14_fct_notification_rules. Rule that triggered this send (NULL for API-triggered sends).';
COMMENT ON COLUMN "05_notify"."60_evt_send_log".campaign_id          IS 'Optional campaign ID for bulk sends. NULL for transactional sends.';
COMMENT ON COLUMN "05_notify"."60_evt_send_log".template_id          IS 'FK to 12_fct_templates. Template used.';
COMMENT ON COLUMN "05_notify"."60_evt_send_log".template_version_id  IS 'FK to 30_dtl_template_versions. Exact version rendered.';
COMMENT ON COLUMN "05_notify"."60_evt_send_log".channel_id           IS 'FK to 02_dim_channels. Channel used for delivery.';
COMMENT ON COLUMN "05_notify"."60_evt_send_log".provider_id          IS 'FK to 10_fct_providers. Provider selected for this send attempt.';
COMMENT ON COLUMN "05_notify"."60_evt_send_log".recipient_user_id    IS 'Recipient user ID if known. NULL for address-only sends.';
COMMENT ON COLUMN "05_notify"."60_evt_send_log".recipient_address    IS 'Delivery address: email, push endpoint, or user_id for in-app.';
COMMENT ON COLUMN "05_notify"."60_evt_send_log".status_id            IS 'Current delivery status. Values: 1=queued, 2=processing, 3=retrying, 4=sent, 5=delivered, 6=failed, 7=bounced, 8=complained, 9=suppressed.';
COMMENT ON COLUMN "05_notify"."60_evt_send_log".rendered_subject     IS 'Final rendered subject line after variable substitution.';
COMMENT ON COLUMN "05_notify"."60_evt_send_log".provider_message_id  IS 'Message ID returned by the provider (e.g. SendGrid sg_message_id). Used to correlate webhook events.';
COMMENT ON COLUMN "05_notify"."60_evt_send_log".error_message        IS 'Error detail if status is failed/bounced. NULL on success.';
COMMENT ON COLUMN "05_notify"."60_evt_send_log".metadata             IS 'JSONB: rendered variables, event context, provider response snippets.';
COMMENT ON COLUMN "05_notify"."60_evt_send_log".created_at           IS 'Dispatch timestamp (UTC). Immutable.';

-- ---------------------------------------------------------------------------
-- 62_evt_delivery_events
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "05_notify"."62_evt_delivery_events" (
    id                 VARCHAR(36)   NOT NULL,
    send_log_id        VARCHAR(36)   NOT NULL,
    event_type_id      SMALLINT      NOT NULL,
    provider_event_id  TEXT          NULL,
    metadata           JSONB         NOT NULL DEFAULT '{}',
    created_at         TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_evt_delivery_events                 PRIMARY KEY (id),
    CONSTRAINT fk_evt_delivery_events_send_log        FOREIGN KEY (send_log_id) REFERENCES "05_notify"."60_evt_send_log" (id),
    CONSTRAINT fk_evt_delivery_events_event_type      FOREIGN KEY (event_type_id) REFERENCES "05_notify"."05_dim_delivery_event_types" (id)
);

CREATE INDEX idx_evt_delivery_events_send_log
    ON "05_notify"."62_evt_delivery_events" (send_log_id, created_at ASC);

COMMENT ON TABLE  "05_notify"."62_evt_delivery_events"                  IS 'Delivery event callbacks received from providers (opens, clicks, bounces, complaints). Append-only.';
COMMENT ON COLUMN "05_notify"."62_evt_delivery_events".id               IS 'UUID v7 primary key.';
COMMENT ON COLUMN "05_notify"."62_evt_delivery_events".send_log_id      IS 'FK to 60_evt_send_log. The send this event belongs to.';
COMMENT ON COLUMN "05_notify"."62_evt_delivery_events".event_type_id    IS 'FK to 05_dim_delivery_event_types. Type of delivery event (delivered, opened, clicked, etc.).';
COMMENT ON COLUMN "05_notify"."62_evt_delivery_events".provider_event_id IS 'Provider-assigned unique event ID. E.g. SendGrid sg_event_id. Used for deduplication.';
COMMENT ON COLUMN "05_notify"."62_evt_delivery_events".metadata          IS 'Raw provider event payload stored for debugging and audit.';
COMMENT ON COLUMN "05_notify"."62_evt_delivery_events".created_at        IS 'Timestamp when the webhook was received (UTC). Immutable.';

-- ---------------------------------------------------------------------------
-- Views (reads)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW "05_notify"."v_providers" AS
SELECT
    p.id,
    p.org_id,
    p.provider_type_id,
    pt.code    AS provider_type_code,
    pt.label   AS provider_type_label,
    ch.id      AS channel_id,
    ch.code    AS channel_code,
    ch.label   AS channel_label,
    p.name,
    p.is_default,
    p.priority,
    p.is_active,
    p.is_test,
    p.vault_key_ref,
    (p.deleted_at IS NOT NULL) AS is_deleted,
    p.created_by,
    p.updated_by,
    p.created_at,
    p.updated_at,
    p.deleted_at
FROM "05_notify"."10_fct_providers" p
JOIN "05_notify"."03_dim_provider_types" pt ON pt.id = p.provider_type_id
JOIN "05_notify"."02_dim_channels" ch ON ch.id = pt.channel_id;

COMMENT ON VIEW "05_notify"."v_providers" IS 'Read view for providers. Omits config_encrypted — use fct table directly for decryption.';

CREATE OR REPLACE VIEW "05_notify"."v_templates" AS
SELECT
    t.id,
    t.org_id,
    t.code,
    t.name,
    t.channel_id,
    ch.code    AS channel_code,
    t.category_id,
    cat.code   AS category_code,
    cat.label  AS category_label,
    t.active_version_id,
    t.is_active,
    t.is_test,
    (t.deleted_at IS NOT NULL) AS is_deleted,
    t.created_by,
    t.updated_by,
    t.created_at,
    t.updated_at,
    t.deleted_at
FROM "05_notify"."12_fct_templates" t
JOIN "05_notify"."02_dim_channels" ch ON ch.id = t.channel_id
JOIN "05_notify"."06_dim_notification_categories" cat ON cat.id = t.category_id;

COMMENT ON VIEW "05_notify"."v_templates" IS 'Read view for templates. Resolves channel and category codes.';

CREATE OR REPLACE VIEW "05_notify"."v_notification_rules" AS
SELECT
    r.id,
    r.org_id,
    r.code,
    r.name,
    r.description,
    r.source_event_type,
    r.source_entity_type_id,
    r.category_id,
    cat.code   AS category_code,
    r.recipient_strategy_id,
    rs.code    AS recipient_strategy_code,
    rs.label   AS recipient_strategy_label,
    r.recipient_filter,
    r.delay_seconds,
    r.is_active,
    r.is_test,
    (r.deleted_at IS NOT NULL) AS is_deleted,
    r.created_by,
    r.updated_by,
    r.created_at,
    r.updated_at,
    r.deleted_at
FROM "05_notify"."14_fct_notification_rules" r
JOIN "05_notify"."06_dim_notification_categories" cat ON cat.id = r.category_id
JOIN "05_notify"."07_dim_recipient_strategies" rs ON rs.id = r.recipient_strategy_id;

COMMENT ON VIEW "05_notify"."v_notification_rules" IS 'Read view for notification rules. Resolves category and recipient strategy codes.';

CREATE OR REPLACE VIEW "05_notify"."v_in_app_notifications" AS
SELECT
    n.id,
    n.org_id,
    n.user_id,
    n.title,
    n.body,
    n.category_id,
    cat.code   AS category_code,
    n.action_url,
    n.is_read,
    n.is_archived,
    n.read_at,
    n.archived_at,
    n.created_at
FROM "05_notify"."18_fct_in_app_notifications" n
JOIN "05_notify"."06_dim_notification_categories" cat ON cat.id = n.category_id;

COMMENT ON VIEW "05_notify"."v_in_app_notifications" IS 'Read view for in-app notifications. Resolves category code.';

CREATE OR REPLACE VIEW "05_notify"."v_send_log" AS
SELECT
    sl.id,
    sl.org_id,
    sl.rule_id,
    sl.campaign_id,
    sl.template_id,
    sl.template_version_id,
    sl.channel_id,
    ch.code    AS channel_code,
    sl.provider_id,
    sl.recipient_user_id,
    sl.recipient_address,
    sl.status_id,
    sl.rendered_subject,
    sl.provider_message_id,
    sl.error_message,
    sl.metadata,
    sl.created_at
FROM "05_notify"."60_evt_send_log" sl
JOIN "05_notify"."02_dim_channels" ch ON ch.id = sl.channel_id;

COMMENT ON VIEW "05_notify"."v_send_log" IS 'Read view for send log entries. Resolves channel code.';

-- ---------------------------------------------------------------------------
-- Audit tables for 05_notify feature
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "05_notify"."90_fct_notify_audit_events" (
    id              VARCHAR(36)   NOT NULL,
    org_id          VARCHAR(36)   NULL,
    action_id       SMALLINT      NOT NULL,
    entity_type_id  SMALLINT      NOT NULL,
    entity_id       VARCHAR(36)   NOT NULL,
    actor_id        VARCHAR(36)   NULL,
    actor_type_id   SMALLINT      NOT NULL DEFAULT 4,
    outcome_id      SMALLINT      NOT NULL DEFAULT 1,
    ip_address      TEXT          NULL,
    metadata        JSONB         NOT NULL DEFAULT '{}',
    snapshot        JSONB         NULL,
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fct_notify_audit_events PRIMARY KEY (id)
);

CREATE INDEX idx_fct_notify_audit_events_entity
    ON "05_notify"."90_fct_notify_audit_events" (entity_type_id, entity_id, created_at DESC);

CREATE INDEX idx_fct_notify_audit_events_org
    ON "05_notify"."90_fct_notify_audit_events" (org_id, created_at DESC)
    WHERE org_id IS NOT NULL;

COMMENT ON TABLE "05_notify"."90_fct_notify_audit_events" IS 'Audit events for the notify feature. Append-only.';

CREATE TABLE IF NOT EXISTS "05_notify"."91_dtl_notify_audit_attrs" (
    id              VARCHAR(36)   NOT NULL,
    event_id        VARCHAR(36)   NOT NULL,
    attr_key        TEXT          NOT NULL,
    old_value       TEXT          NULL,
    new_value       TEXT          NULL,
    CONSTRAINT pk_dtl_notify_audit_attrs PRIMARY KEY (id),
    CONSTRAINT fk_dtl_notify_audit_attrs_event FOREIGN KEY (event_id) REFERENCES "05_notify"."90_fct_notify_audit_events" (id)
);

CREATE INDEX idx_dtl_notify_audit_attrs_event
    ON "05_notify"."91_dtl_notify_audit_attrs" (event_id);

COMMENT ON TABLE "05_notify"."91_dtl_notify_audit_attrs" IS 'Attribute-level change tracking for notify audit events.';

-- ---------------------------------------------------------------------------
-- DOWN ====
-- ---------------------------------------------------------------------------

-- DROP VIEW IF EXISTS "05_notify"."v_send_log";
-- DROP VIEW IF EXISTS "05_notify"."v_in_app_notifications";
-- DROP VIEW IF EXISTS "05_notify"."v_notification_rules";
-- DROP VIEW IF EXISTS "05_notify"."v_templates";
-- DROP VIEW IF EXISTS "05_notify"."v_providers";
-- DROP TABLE IF EXISTS "05_notify"."91_dtl_notify_audit_attrs";
-- DROP TABLE IF EXISTS "05_notify"."90_fct_notify_audit_events";
-- DROP TABLE IF EXISTS "05_notify"."62_evt_delivery_events";
-- DROP TABLE IF EXISTS "05_notify"."60_evt_send_log";
-- DROP TABLE IF EXISTS "05_notify"."42_lnk_user_preferences";
-- DROP TABLE IF EXISTS "05_notify"."40_lnk_rule_channels";
-- DROP TABLE IF EXISTS "05_notify"."32_dtl_template_variables";
-- ALTER TABLE "05_notify"."12_fct_templates" DROP CONSTRAINT IF EXISTS fk_fct_templates_active_version;
-- DROP TABLE IF EXISTS "05_notify"."30_dtl_template_versions";
-- DROP TABLE IF EXISTS "05_notify"."20_fct_web_push_subscriptions";
-- DROP TABLE IF EXISTS "05_notify"."18_fct_in_app_notifications";
-- DROP TABLE IF EXISTS "05_notify"."16_fct_variable_queries";
-- DROP TABLE IF EXISTS "05_notify"."14_fct_notification_rules";
-- DROP TABLE IF EXISTS "05_notify"."12_fct_templates";
-- DROP TABLE IF EXISTS "05_notify"."10_fct_providers";
-- DROP TABLE IF EXISTS "05_notify"."08_dim_variable_types";
-- DROP TABLE IF EXISTS "05_notify"."07_dim_recipient_strategies";
-- DROP TABLE IF EXISTS "05_notify"."06_dim_notification_categories";
-- DROP TABLE IF EXISTS "05_notify"."05_dim_delivery_event_types";
-- DROP TABLE IF EXISTS "05_notify"."03_dim_provider_types";
-- DROP TABLE IF EXISTS "05_notify"."02_dim_channels";
-- DROP FUNCTION IF EXISTS "05_notify".set_updated_at();
-- DROP SCHEMA IF EXISTS "05_notify";
