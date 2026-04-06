-- =============================================================================
-- Migration: 20260404_022_iam_mfa
-- Description: MFA/TOTP — 44_fct_user_mfa and 45_fct_mfa_recovery_codes tables.
--              These are referenced by the auth service's mfa_* functions.
-- Schema: "02_iam"
-- =============================================================================

-- UP ====

-- ---------------------------------------------------------------------------
-- Fact table: user MFA methods
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "02_iam"."44_fct_user_mfa" (
    id          VARCHAR(36)  NOT NULL,
    user_id     VARCHAR(36)  NOT NULL,
    method      VARCHAR(32)  NOT NULL DEFAULT 'totp',
    totp_secret TEXT,
    is_enabled  BOOLEAN      NOT NULL DEFAULT false,
    verified_at TIMESTAMP,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_44_fct_user_mfa              PRIMARY KEY (id),
    CONSTRAINT uq_44_fct_user_mfa_user_method  UNIQUE (user_id, method),
    CONSTRAINT fk_44_fct_user_mfa_user         FOREIGN KEY (user_id) REFERENCES "02_iam"."10_fct_user_users"(id)
);

COMMENT ON TABLE  "02_iam"."44_fct_user_mfa"             IS 'MFA method records per user — one row per method (currently TOTP only).';
COMMENT ON COLUMN "02_iam"."44_fct_user_mfa".id          IS 'UUID v7 primary key.';
COMMENT ON COLUMN "02_iam"."44_fct_user_mfa".user_id     IS 'FK to 10_fct_user_users.';
COMMENT ON COLUMN "02_iam"."44_fct_user_mfa".method      IS 'MFA method code: totp.';
COMMENT ON COLUMN "02_iam"."44_fct_user_mfa".totp_secret IS 'Base32-encoded TOTP secret. Treat as sensitive.';
COMMENT ON COLUMN "02_iam"."44_fct_user_mfa".is_enabled  IS 'True after the user has verified the TOTP setup.';
COMMENT ON COLUMN "02_iam"."44_fct_user_mfa".verified_at IS 'When the user first verified the TOTP code.';

CREATE INDEX IF NOT EXISTS idx_44_fct_user_mfa_user_id
    ON "02_iam"."44_fct_user_mfa" (user_id);

CREATE OR REPLACE FUNCTION "02_iam".trg_set_updated_at_44_fct_user_mfa()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = CURRENT_TIMESTAMP; RETURN NEW; END;
$$;

CREATE TRIGGER trg_44_fct_user_mfa_updated_at
    BEFORE UPDATE ON "02_iam"."44_fct_user_mfa"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".trg_set_updated_at_44_fct_user_mfa();

-- ---------------------------------------------------------------------------
-- Fact table: MFA recovery codes
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "02_iam"."45_fct_mfa_recovery_codes" (
    id         VARCHAR(36) NOT NULL,
    user_id    VARCHAR(36) NOT NULL,
    code_hash  TEXT        NOT NULL,   -- argon2 hash of the raw recovery code
    used_at    TIMESTAMP,              -- NULL = not yet used
    created_at TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_45_fct_mfa_recovery_codes       PRIMARY KEY (id),
    CONSTRAINT fk_45_fct_mfa_recovery_codes_user  FOREIGN KEY (user_id) REFERENCES "02_iam"."10_fct_user_users"(id)
);

COMMENT ON TABLE  "02_iam"."45_fct_mfa_recovery_codes"          IS 'One-time-use recovery codes for MFA bypass.';
COMMENT ON COLUMN "02_iam"."45_fct_mfa_recovery_codes".id       IS 'UUID v7 primary key.';
COMMENT ON COLUMN "02_iam"."45_fct_mfa_recovery_codes".user_id  IS 'FK to 10_fct_user_users.';
COMMENT ON COLUMN "02_iam"."45_fct_mfa_recovery_codes".code_hash IS 'Argon2 hash of the raw recovery code. Never store plain text.';
COMMENT ON COLUMN "02_iam"."45_fct_mfa_recovery_codes".used_at  IS 'When this code was consumed. NULL = unused.';

CREATE INDEX IF NOT EXISTS idx_45_fct_mfa_recovery_codes_user_id
    ON "02_iam"."45_fct_mfa_recovery_codes" (user_id)
    WHERE used_at IS NULL;

-- DOWN ====

-- DROP TABLE IF EXISTS "02_iam"."45_fct_mfa_recovery_codes";
-- DROP TRIGGER IF EXISTS trg_44_fct_user_mfa_updated_at ON "02_iam"."44_fct_user_mfa";
-- DROP FUNCTION IF EXISTS "02_iam".trg_set_updated_at_44_fct_user_mfa();
-- DROP TABLE IF EXISTS "02_iam"."44_fct_user_mfa";
