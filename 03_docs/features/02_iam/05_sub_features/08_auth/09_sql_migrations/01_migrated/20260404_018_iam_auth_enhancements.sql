-- =============================================================================
-- Migration: 20260404_018_iam_auth_enhancements.sql
-- Sub-feature: 08_auth
-- Description: Social OAuth providers, magic links, OTP, password reset,
--              email verification, account types.
-- =============================================================================

-- UP =========================================================================

SET search_path TO "02_iam", public;

-- ---------------------------------------------------------------------------
-- Add Apple, Microsoft, Apple, magic_link, otp providers
-- ---------------------------------------------------------------------------

INSERT INTO "02_iam"."04_dim_auth_providers" (id, code, label, description) VALUES
    (4,  'apple',         'Apple',          'Sign in with Apple'),
    (5,  'microsoft',     'Microsoft',      'Microsoft OAuth / Azure AD'),
    (6,  'gitlab',        'GitLab',         'GitLab OAuth'),
    (7,  'discord',       'Discord',        'Discord OAuth'),
    (8,  'slack',         'Slack',          'Slack OAuth'),
    (9,  'magic_link',    'Magic Link',     'Passwordless email magic link'),
    (10, 'otp_email',     'Email OTP',      'One-time password via email')
ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE "02_iam"."04_dim_auth_providers" IS 'Authentication provider types (email/password, OAuth, magic link, OTP).';

-- ---------------------------------------------------------------------------
-- OAuth identity records (stores provider_user_id + access token info)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "02_iam"."19_fct_oauth_identities" (
    id                  VARCHAR(36)  NOT NULL,
    user_id             VARCHAR(36)  NOT NULL,
    provider_id         SMALLINT     NOT NULL,
    provider_user_id    TEXT         NOT NULL,
    email               TEXT,
    display_name        TEXT,
    avatar_url          TEXT,
    raw_profile         JSONB,
    access_token        TEXT,
    refresh_token_enc   TEXT,                  -- encrypted refresh token
    token_expires_at    TIMESTAMP,
    is_active           BOOLEAN      NOT NULL  DEFAULT true,
    created_at          TIMESTAMP    NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP    NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_19_fct_oauth_identities              PRIMARY KEY (id),
    CONSTRAINT fk_19_fct_oauth_identities_user         FOREIGN KEY (user_id)
        REFERENCES "02_iam"."10_fct_user_users"(id) ON DELETE CASCADE,
    CONSTRAINT fk_19_fct_oauth_identities_provider     FOREIGN KEY (provider_id)
        REFERENCES "02_iam"."04_dim_auth_providers"(id),
    CONSTRAINT uq_19_fct_oauth_identities_prov_uid     UNIQUE (provider_id, provider_user_id)
);
COMMENT ON TABLE  "02_iam"."19_fct_oauth_identities"              IS 'OAuth identity linkage per user per provider.';
COMMENT ON COLUMN "02_iam"."19_fct_oauth_identities".provider_user_id IS 'The user ID from the external provider (sub claim, GitHub id, etc).';
COMMENT ON COLUMN "02_iam"."19_fct_oauth_identities".raw_profile       IS 'Full profile JSONB from provider for audit.';
COMMENT ON COLUMN "02_iam"."19_fct_oauth_identities".refresh_token_enc IS 'AES-encrypted provider refresh token.';

CREATE INDEX idx_19_fct_oauth_user     ON "02_iam"."19_fct_oauth_identities" (user_id);
CREATE INDEX idx_19_fct_oauth_provider ON "02_iam"."19_fct_oauth_identities" (provider_id, provider_user_id);

CREATE TRIGGER trg_19_fct_oauth_updated_at BEFORE UPDATE ON "02_iam"."19_fct_oauth_identities"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- ---------------------------------------------------------------------------
-- Email verification tokens (stored in Redis, but table tracks state)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "02_iam"."41_evt_email_verifications" (
    id          VARCHAR(36) NOT NULL,
    user_id     VARCHAR(36) NOT NULL,
    email       TEXT        NOT NULL,
    verified_at TIMESTAMP,
    created_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_41_evt_email_verifications        PRIMARY KEY (id),
    CONSTRAINT fk_41_evt_email_verifications_user   FOREIGN KEY (user_id)
        REFERENCES "02_iam"."10_fct_user_users"(id) ON DELETE CASCADE
);
COMMENT ON TABLE "02_iam"."41_evt_email_verifications" IS 'Email verification event log. Tokens are in Redis; this tracks audit.';

CREATE INDEX idx_41_evt_email_ver_user ON "02_iam"."41_evt_email_verifications" (user_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Password reset event log (tokens in Redis)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "02_iam"."42_evt_password_resets" (
    id              VARCHAR(36) NOT NULL,
    user_id         VARCHAR(36) NOT NULL,
    ip_address      VARCHAR(64),
    completed_at    TIMESTAMP,
    created_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_42_evt_password_resets        PRIMARY KEY (id),
    CONSTRAINT fk_42_evt_password_resets_user   FOREIGN KEY (user_id)
        REFERENCES "02_iam"."10_fct_user_users"(id) ON DELETE CASCADE
);
COMMENT ON TABLE "02_iam"."42_evt_password_resets" IS 'Password reset request audit log. Tokens in Redis with 1-hour TTL.';

CREATE INDEX idx_42_evt_pwreset_user ON "02_iam"."42_evt_password_resets" (user_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Add email_verified + account_type columns to users table
-- ---------------------------------------------------------------------------

ALTER TABLE "02_iam"."10_fct_user_users"
    ADD COLUMN IF NOT EXISTS email_verified    BOOLEAN   NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS account_type      SMALLINT  NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS avatar_url        TEXT,
    ADD COLUMN IF NOT EXISTS locale            VARCHAR(10) NOT NULL DEFAULT 'en';

COMMENT ON COLUMN "02_iam"."10_fct_user_users".email_verified IS 'Whether email has been verified via OTP/magic link.';
COMMENT ON COLUMN "02_iam"."10_fct_user_users".account_type   IS 'FK to dim_account_types (1=standard, 2=admin, 3=service, 4=bot).';
COMMENT ON COLUMN "02_iam"."10_fct_user_users".avatar_url     IS 'Profile picture URL (from OAuth or manual upload).';
COMMENT ON COLUMN "02_iam"."10_fct_user_users".locale         IS 'User locale preference, e.g. en, fr, de.';

-- Account types dim
CREATE TABLE IF NOT EXISTS "02_iam"."05_dim_account_types" (
    id              SMALLINT    NOT NULL,
    code            TEXT        NOT NULL,
    label           TEXT        NOT NULL,
    description     TEXT        NOT NULL DEFAULT '',
    deprecated_at   TIMESTAMP,
    CONSTRAINT pk_05_dim_account_types      PRIMARY KEY (id),
    CONSTRAINT uq_05_dim_account_types_code UNIQUE (code)
);
COMMENT ON TABLE "02_iam"."05_dim_account_types" IS 'User account type classification.';

INSERT INTO "02_iam"."05_dim_account_types" (id, code, label, description) VALUES
    (1, 'standard',  'Standard',      'Regular human user account'),
    (2, 'admin',     'Admin',         'Platform administrator'),
    (3, 'service',   'Service',       'Machine/API service account'),
    (4, 'bot',       'Bot',           'Automated bot account'),
    (5, 'guest',     'Guest',         'Limited-access guest user')
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- OAuth state tokens table (CSRF protection for OAuth flows)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "02_iam"."43_evt_oauth_state" (
    id          VARCHAR(36)  NOT NULL,
    state       VARCHAR(128) NOT NULL,
    provider_id SMALLINT     NOT NULL,
    redirect_to TEXT,
    used_at     TIMESTAMP,
    expires_at  TIMESTAMP    NOT NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_43_evt_oauth_state PRIMARY KEY (id),
    CONSTRAINT uq_43_evt_oauth_state UNIQUE (state)
);
COMMENT ON TABLE "02_iam"."43_evt_oauth_state" IS 'Short-lived OAuth state tokens for CSRF protection. Expire in 10 minutes.';

CREATE INDEX idx_43_evt_oauth_state_expires ON "02_iam"."43_evt_oauth_state" (expires_at);

-- ---------------------------------------------------------------------------
-- Update v_40_sessions to include user info
-- ---------------------------------------------------------------------------

DROP VIEW IF EXISTS "02_iam"."v_40_sessions";
CREATE VIEW "02_iam"."v_40_sessions" AS
SELECT
    s.id,
    s.user_id,
    s.jti,
    s.ip_address,
    s.user_agent,
    s.expires_at,
    s.revoked_at,
    (s.revoked_at IS NOT NULL) AS is_revoked,
    s.created_at,
    u.email          AS user_email,
    u.display_name   AS user_display_name
FROM "02_iam"."40_fct_session_sessions" s
LEFT JOIN "02_iam"."10_fct_user_users" u ON u.id = s.user_id;
COMMENT ON VIEW "02_iam"."v_40_sessions" IS 'Sessions with user info. is_revoked derived.';

-- =============================================================================
-- DOWN
-- =============================================================================

DROP VIEW  IF EXISTS "02_iam"."v_40_sessions";
DROP TABLE IF EXISTS "02_iam"."43_evt_oauth_state";
ALTER TABLE "02_iam"."10_fct_user_users"
    DROP COLUMN IF EXISTS email_verified,
    DROP COLUMN IF EXISTS account_type,
    DROP COLUMN IF EXISTS avatar_url,
    DROP COLUMN IF EXISTS locale;
DROP TABLE IF EXISTS "02_iam"."05_dim_account_types";
DROP TABLE IF EXISTS "02_iam"."42_evt_password_resets";
DROP TABLE IF EXISTS "02_iam"."41_evt_email_verifications";
DROP TABLE IF EXISTS "02_iam"."19_fct_oauth_identities";
DELETE FROM "02_iam"."04_dim_auth_providers" WHERE id IN (4,5,6,7,8,9,10);

-- Recreate original v_40_sessions view
CREATE VIEW "02_iam"."v_40_sessions" AS
SELECT
    s.id, s.user_id, s.jti, s.ip_address, s.user_agent,
    s.expires_at, s.revoked_at,
    (s.revoked_at IS NOT NULL) AS is_revoked,
    s.created_at
FROM "02_iam"."40_fct_session_sessions" s;
