-- UP ====
-- Migration 019: notify org config table and masked view.
-- Creates 22_fct_notify_config (per-org branding + SMTP overrides) and
-- v_notify_config (masks smtp_password as has_smtp_password boolean).
-- Depends on: 018 (schema 05_notify, 02_dim_channels, set_updated_at function).

SET search_path TO "05_notify";

-- ---------------------------------------------------------------------------
-- 22_fct_notify_config
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "05_notify"."22_fct_notify_config" (
    org_id          VARCHAR(36)   NOT NULL,
    from_email      VARCHAR(320)  NULL,
    from_name       VARCHAR(200)  NULL,
    reply_to        VARCHAR(320)  NULL,
    unsubscribe_url VARCHAR(2000) NULL,
    logo_url        VARCHAR(2000) NULL,
    footer_html     TEXT          NULL,
    smtp_host       VARCHAR(500)  NULL,
    smtp_port       SMALLINT      NULL,
    smtp_user       VARCHAR(500)  NULL,
    smtp_password   TEXT          NULL,
    smtp_use_ssl    BOOLEAN       NULL,
    smtp_timeout    SMALLINT      NULL,
    is_active       BOOLEAN       NOT NULL DEFAULT TRUE,
    is_test         BOOLEAN       NOT NULL DEFAULT FALSE,
    deleted_at      TIMESTAMP     NULL,
    created_by      VARCHAR(36)   NOT NULL DEFAULT 'system',
    updated_by      VARCHAR(36)   NOT NULL DEFAULT 'system',
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fct_notify_config      PRIMARY KEY (org_id),
    CONSTRAINT fk_fct_notify_config_org  FOREIGN KEY (org_id) REFERENCES "02_iam"."01_fct_org_orgs" (id),
    CONSTRAINT chk_fct_notify_config_port CHECK (smtp_port IS NULL OR (smtp_port >= 1 AND smtp_port <= 65535)),
    CONSTRAINT chk_fct_notify_config_timeout CHECK (smtp_timeout IS NULL OR (smtp_timeout >= 1 AND smtp_timeout <= 300))
);

CREATE TRIGGER trg_fct_notify_config_updated_at
BEFORE UPDATE ON "05_notify"."22_fct_notify_config"
FOR EACH ROW EXECUTE FUNCTION "05_notify".set_updated_at();

COMMENT ON TABLE  "05_notify"."22_fct_notify_config"               IS 'Per-organisation notification branding and optional custom SMTP overrides. One row per org; created on first PATCH.';
COMMENT ON COLUMN "05_notify"."22_fct_notify_config".org_id        IS 'PK and FK to 02_iam.11_fct_orgs. Org this config belongs to.';
COMMENT ON COLUMN "05_notify"."22_fct_notify_config".from_email    IS 'Default From address for emails sent on behalf of this org. Overrides provider default.';
COMMENT ON COLUMN "05_notify"."22_fct_notify_config".from_name     IS 'Default display name for the From address.';
COMMENT ON COLUMN "05_notify"."22_fct_notify_config".reply_to      IS 'Reply-To address. Injected as Reply-To header on all outbound emails.';
COMMENT ON COLUMN "05_notify"."22_fct_notify_config".unsubscribe_url IS 'Custom unsubscribe URL for List-Unsubscribe headers. Falls back to platform default if NULL.';
COMMENT ON COLUMN "05_notify"."22_fct_notify_config".logo_url      IS 'Org logo URL injected into HTML email templates for branding.';
COMMENT ON COLUMN "05_notify"."22_fct_notify_config".footer_html   IS 'HTML fragment appended to the footer of all HTML emails for this org.';
COMMENT ON COLUMN "05_notify"."22_fct_notify_config".smtp_host     IS 'Custom SMTP host. When set, all email for this org routes through this server instead of the platform provider.';
COMMENT ON COLUMN "05_notify"."22_fct_notify_config".smtp_port     IS 'SMTP port. Common values: 25, 465 (SSL), 587 (STARTTLS).';
COMMENT ON COLUMN "05_notify"."22_fct_notify_config".smtp_user     IS 'SMTP authentication username.';
COMMENT ON COLUMN "05_notify"."22_fct_notify_config".smtp_password IS 'SMTP authentication password. NEVER exposed via API — read v_notify_config which replaces this with has_smtp_password.';
COMMENT ON COLUMN "05_notify"."22_fct_notify_config".smtp_use_ssl  IS 'TRUE = use SSL/TLS on connect (port 465). FALSE = STARTTLS or plaintext.';
COMMENT ON COLUMN "05_notify"."22_fct_notify_config".smtp_timeout  IS 'SMTP connection timeout in seconds. Range 1-300.';
COMMENT ON COLUMN "05_notify"."22_fct_notify_config".is_active     IS 'FALSE = config disabled, falls back to platform defaults.';
COMMENT ON COLUMN "05_notify"."22_fct_notify_config".is_test       IS 'TRUE = test/seed record.';
COMMENT ON COLUMN "05_notify"."22_fct_notify_config".deleted_at    IS 'NULL = active. SET = soft-deleted (config cleared).';
COMMENT ON COLUMN "05_notify"."22_fct_notify_config".created_by    IS 'User ID or system that created this config row.';
COMMENT ON COLUMN "05_notify"."22_fct_notify_config".updated_by    IS 'User ID or system that last modified this config.';
COMMENT ON COLUMN "05_notify"."22_fct_notify_config".created_at    IS 'Creation timestamp (UTC).';
COMMENT ON COLUMN "05_notify"."22_fct_notify_config".updated_at    IS 'Last modification timestamp. Set automatically by trigger.';

-- ---------------------------------------------------------------------------
-- v_notify_config — masks smtp_password as has_smtp_password boolean
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW "05_notify"."v_notify_config" AS
SELECT
    org_id,
    from_email,
    from_name,
    reply_to,
    unsubscribe_url,
    logo_url,
    footer_html,
    smtp_host,
    smtp_port,
    smtp_user,
    (smtp_password IS NOT NULL AND smtp_password <> '') AS has_smtp_password,
    smtp_use_ssl,
    smtp_timeout,
    is_active,
    is_test,
    (deleted_at IS NOT NULL) AS is_deleted,
    created_by,
    updated_by,
    created_at,
    updated_at,
    deleted_at
FROM "05_notify"."22_fct_notify_config";

COMMENT ON VIEW "05_notify"."v_notify_config" IS 'Read view for org notify config. Replaces smtp_password with has_smtp_password boolean so credentials are never exposed via API.';

-- ---------------------------------------------------------------------------
-- DOWN ====
-- ---------------------------------------------------------------------------

-- DROP VIEW IF EXISTS "05_notify"."v_notify_config";
-- DROP TABLE IF EXISTS "05_notify"."22_fct_notify_config";
