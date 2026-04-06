-- =============================================================================
-- Migration: 20260404_019_auth_config.sql
-- Sub-feature: 08_auth
-- Description: Platform-level auth config store + per-org auth config overrides.
--              Supports configuring OAuth providers, SMTP, magic links, OTP
--              at platform level, with per-org overrides.
-- =============================================================================

-- UP =========================================================================

SET search_path TO "02_iam", public;

-- ---------------------------------------------------------------------------
-- Platform auth config (singleton: id=1 is the global config)
-- Stores encrypted secrets as JSONB. One row per config key.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "02_iam"."08_dim_auth_config" (
    id              SMALLINT    NOT NULL,
    config_key      TEXT        NOT NULL,
    config_value    JSONB       NOT NULL DEFAULT '{}',
    description     TEXT        NOT NULL DEFAULT '',
    is_secret       BOOLEAN     NOT NULL DEFAULT false,
    updated_by      VARCHAR(36),
    updated_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_08_dim_auth_config          PRIMARY KEY (id),
    CONSTRAINT uq_08_dim_auth_config_key      UNIQUE (config_key)
);
COMMENT ON TABLE  "02_iam"."08_dim_auth_config"              IS 'Platform-level authentication configuration. Secrets stored as encrypted JSONB.';
COMMENT ON COLUMN "02_iam"."08_dim_auth_config".config_key   IS 'Config key, e.g. google_oauth, smtp, magic_link_settings.';
COMMENT ON COLUMN "02_iam"."08_dim_auth_config".config_value IS 'JSONB config blob. Secrets are AES-encrypted before storage.';
COMMENT ON COLUMN "02_iam"."08_dim_auth_config".is_secret    IS 'Whether value contains encrypted secrets (mask in API responses).';

CREATE TRIGGER trg_08_dim_auth_config_updated_at BEFORE UPDATE ON "02_iam"."08_dim_auth_config"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- Seed default config entries
INSERT INTO "02_iam"."08_dim_auth_config" (id, config_key, config_value, description, is_secret) VALUES
    (1,  'password_login',  '{"enabled": true}',                                    'Email + password login settings', false),
    (2,  'magic_link',      '{"enabled": false, "ttl_minutes": 15}',                'Magic link (passwordless) settings', false),
    (3,  'otp_email',       '{"enabled": false, "ttl_minutes": 10, "length": 6}',   'Email OTP settings', false),
    (4,  'google_oauth',    '{"enabled": false, "client_id": "", "client_secret": ""}', 'Google OAuth 2.0', true),
    (5,  'github_oauth',    '{"enabled": false, "client_id": "", "client_secret": ""}', 'GitHub OAuth', true),
    (6,  'apple_oauth',     '{"enabled": false, "client_id": "", "key_id": "", "team_id": "", "private_key": ""}', 'Sign in with Apple', true),
    (7,  'microsoft_oauth', '{"enabled": false, "client_id": "", "client_secret": "", "tenant_id": "common"}', 'Microsoft/Azure AD OAuth', true),
    (8,  'gitlab_oauth',    '{"enabled": false, "client_id": "", "client_secret": ""}', 'GitLab OAuth', true),
    (9,  'discord_oauth',   '{"enabled": false, "client_id": "", "client_secret": ""}', 'Discord OAuth', true),
    (10, 'slack_oauth',     '{"enabled": false, "client_id": "", "client_secret": ""}', 'Slack OAuth', true),
    (11, 'smtp',            '{"host": "", "port": 587, "username": "", "password": "", "use_tls": true, "from_email": "noreply@example.com", "from_name": "tennetctl"}', 'SMTP email settings', true),
    (12, 'session_policy',  '{"max_sessions_per_user": 10, "access_ttl_minutes": 15, "refresh_ttl_days": 30}', 'Session limits and TTLs', false),
    (13, 'registration',    '{"allow_public_registration": true, "require_email_verification": false, "allowed_email_domains": []}', 'Registration settings', false)
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Per-org auth config overrides
-- Each org can override which providers are enabled + use their own OAuth app
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "02_iam"."20_dtl_org_auth_config" (
    id              VARCHAR(36) NOT NULL,
    org_id          VARCHAR(36) NOT NULL,
    config_key      TEXT        NOT NULL,
    config_value    JSONB       NOT NULL DEFAULT '{}',
    is_secret       BOOLEAN     NOT NULL DEFAULT false,
    updated_by      VARCHAR(36),
    created_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_20_dtl_org_auth_config           PRIMARY KEY (id),
    CONSTRAINT uq_20_dtl_org_auth_config_org_key   UNIQUE (org_id, config_key),
    CONSTRAINT fk_20_dtl_org_auth_config_org       FOREIGN KEY (org_id)
        REFERENCES "02_iam"."11_fct_org_orgs"(id) ON DELETE CASCADE
);
COMMENT ON TABLE  "02_iam"."20_dtl_org_auth_config"             IS 'Per-org auth config overrides. Inherits platform config when absent.';
COMMENT ON COLUMN "02_iam"."20_dtl_org_auth_config".config_key  IS 'Same key namespace as 08_dim_auth_config.';
COMMENT ON COLUMN "02_iam"."20_dtl_org_auth_config".is_secret   IS 'Whether JSONB contains encrypted secrets.';

CREATE INDEX idx_20_dtl_org_auth_config_org ON "02_iam"."20_dtl_org_auth_config" (org_id);
CREATE TRIGGER trg_20_dtl_org_auth_config_updated_at BEFORE UPDATE ON "02_iam"."20_dtl_org_auth_config"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- ---------------------------------------------------------------------------
-- View: resolved auth config per org (org override OR platform default)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW "02_iam"."v_auth_config" AS
SELECT
    p.config_key,
    COALESCE(o.config_value, p.config_value)  AS config_value,
    p.is_secret,
    o.org_id,
    o.updated_at  AS org_updated_at,
    p.updated_at  AS platform_updated_at
FROM "02_iam"."08_dim_auth_config" p
LEFT JOIN "02_iam"."20_dtl_org_auth_config" o ON o.config_key = p.config_key;
COMMENT ON VIEW "02_iam"."v_auth_config" IS 'Resolved auth config: org override takes precedence over platform default.';

-- =============================================================================
-- DOWN
-- =============================================================================

DROP VIEW  IF EXISTS "02_iam"."v_auth_config";
DROP TABLE IF EXISTS "02_iam"."20_dtl_org_auth_config";
DROP TABLE IF EXISTS "02_iam"."08_dim_auth_config";
