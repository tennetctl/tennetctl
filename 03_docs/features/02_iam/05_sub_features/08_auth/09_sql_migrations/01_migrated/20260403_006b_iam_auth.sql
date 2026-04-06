-- =============================================================================
-- Migration: 20260403_006b_iam_auth.sql
-- Sub-feature: 08_auth
-- Description: Auth credentials, JWT sessions, and session view.
-- UP
-- =============================================================================

SET search_path TO "02_iam", public;

-- Entity types for auth
INSERT INTO "02_iam"."01_dim_org_entity_types" (id, code, label, description) VALUES
    (6, 'session', 'Session', 'JWT session');

-- Auth providers
CREATE TABLE "02_iam"."04_dim_auth_providers" (
    id              SMALLINT    NOT NULL,
    code            TEXT        NOT NULL,
    label           TEXT        NOT NULL,
    description     TEXT        NOT NULL DEFAULT '',
    deprecated_at   TIMESTAMP,
    CONSTRAINT pk_04_dim_auth_providers      PRIMARY KEY (id),
    CONSTRAINT uq_04_dim_auth_providers_code UNIQUE (code)
);
COMMENT ON TABLE "02_iam"."04_dim_auth_providers" IS 'Authentication provider types.';

INSERT INTO "02_iam"."04_dim_auth_providers" (id, code, label, description) VALUES
    (1, 'email_password', 'Email & Password', 'Email + password login'),
    (2, 'google',         'Google',           'Google OAuth'),
    (3, 'github',         'GitHub',           'GitHub OAuth');

-- Auth credentials (one per user+provider)
CREATE TABLE "02_iam"."18_fct_auth_credentials" (
    id              VARCHAR(36) NOT NULL,
    user_id         VARCHAR(36) NOT NULL,
    provider_id     SMALLINT    NOT NULL DEFAULT 1,
    credential_hash TEXT,
    is_active       BOOLEAN     NOT NULL DEFAULT true,
    created_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_18_fct_auth_credentials           PRIMARY KEY (id),
    CONSTRAINT fk_18_fct_auth_credentials_provider  FOREIGN KEY (provider_id)
        REFERENCES "02_iam"."04_dim_auth_providers"(id),
    CONSTRAINT uq_18_fct_auth_credentials_user_prov UNIQUE (user_id, provider_id)
);
COMMENT ON TABLE "02_iam"."18_fct_auth_credentials" IS 'Auth credentials. credential_hash is argon2 for email/password, NULL for OAuth.';

CREATE TRIGGER trg_18_fct_auth_creds_updated_at BEFORE UPDATE ON "02_iam"."18_fct_auth_credentials"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- JWT sessions (append-only, revoke lifecycle)
CREATE TABLE "02_iam"."40_fct_session_sessions" (
    id          VARCHAR(36) NOT NULL,
    user_id     VARCHAR(36) NOT NULL,
    jti         VARCHAR(36) NOT NULL,
    ip_address  VARCHAR(64),
    user_agent  TEXT,
    expires_at  TIMESTAMP   NOT NULL,
    revoked_at  TIMESTAMP,
    created_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_40_fct_session_sessions     PRIMARY KEY (id),
    CONSTRAINT uq_40_fct_session_sessions_jti UNIQUE (jti)
);
COMMENT ON TABLE "02_iam"."40_fct_session_sessions" IS 'JWT sessions. Append-only — no updated_at, no deleted_at.';

CREATE INDEX idx_40_fct_session_user ON "02_iam"."40_fct_session_sessions" (user_id, created_at DESC);
CREATE INDEX idx_40_fct_session_active ON "02_iam"."40_fct_session_sessions" (jti) WHERE revoked_at IS NULL;

-- Session read view
CREATE VIEW "02_iam"."v_40_sessions" AS
SELECT
    s.id, s.user_id, s.jti, s.ip_address, s.user_agent,
    s.expires_at, s.revoked_at,
    (s.revoked_at IS NOT NULL) AS is_revoked,
    s.created_at
FROM "02_iam"."40_fct_session_sessions" s;
COMMENT ON VIEW "02_iam"."v_40_sessions" IS 'Session read view with derived is_revoked flag.';

-- =============================================================================
-- DOWN
-- =============================================================================

DROP VIEW  IF EXISTS "02_iam"."v_40_sessions";
DROP TABLE IF EXISTS "02_iam"."40_fct_session_sessions";
DROP TABLE IF EXISTS "02_iam"."18_fct_auth_credentials";
DROP TABLE IF EXISTS "02_iam"."04_dim_auth_providers";
DELETE FROM "02_iam"."01_dim_org_entity_types" WHERE id = 6;
