-- =============================================================================
-- Migration: 20260404_023_iam_personal_access_tokens
-- Description: Personal access tokens (PATs) — long-lived API keys scoped to a user.
--              Users can create named tokens with an optional expiry.
--              Token values are stored as SHA-256 hashes; the plain value shown once.
-- Schema: "02_iam"
-- =============================================================================

-- UP ====

CREATE TABLE IF NOT EXISTS "02_iam"."56_fct_personal_access_tokens" (
    id           VARCHAR(36)  NOT NULL,
    user_id      VARCHAR(36)  NOT NULL,
    name         VARCHAR(255) NOT NULL,
    token_hash   TEXT         NOT NULL,    -- SHA-256(token_prefix + secret)
    token_prefix VARCHAR(8)   NOT NULL,    -- first 8 chars, shown in UI for identification
    last_used_at TIMESTAMP,
    expires_at   TIMESTAMP,               -- NULL = never expires
    created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at   TIMESTAMP,               -- NULL = active

    CONSTRAINT pk_56_fct_personal_access_tokens
        PRIMARY KEY (id),
    CONSTRAINT uq_56_fct_personal_access_tokens_hash
        UNIQUE (token_hash),
    CONSTRAINT fk_56_fct_personal_access_tokens_user
        FOREIGN KEY (user_id) REFERENCES "02_iam"."10_fct_user_users"(id)
);

COMMENT ON TABLE  "02_iam"."56_fct_personal_access_tokens"              IS 'Personal access tokens — long-lived API keys for a user.';
COMMENT ON COLUMN "02_iam"."56_fct_personal_access_tokens".id           IS 'UUID v7 primary key.';
COMMENT ON COLUMN "02_iam"."56_fct_personal_access_tokens".user_id      IS 'FK to 10_fct_user_users.';
COMMENT ON COLUMN "02_iam"."56_fct_personal_access_tokens".name         IS 'Human-readable label for this token.';
COMMENT ON COLUMN "02_iam"."56_fct_personal_access_tokens".token_hash   IS 'SHA-256 hash of the full token. Never stored in plain text after creation.';
COMMENT ON COLUMN "02_iam"."56_fct_personal_access_tokens".token_prefix IS 'First 8 chars of the token, shown in UI for identification only.';
COMMENT ON COLUMN "02_iam"."56_fct_personal_access_tokens".last_used_at IS 'When this token was last used for authentication.';
COMMENT ON COLUMN "02_iam"."56_fct_personal_access_tokens".expires_at   IS 'When this token expires. NULL = never.';
COMMENT ON COLUMN "02_iam"."56_fct_personal_access_tokens".revoked_at   IS 'When this token was revoked. NULL = still active.';

CREATE INDEX IF NOT EXISTS idx_56_fct_personal_access_tokens_user_id
    ON "02_iam"."56_fct_personal_access_tokens" (user_id)
    WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_56_fct_personal_access_tokens_hash
    ON "02_iam"."56_fct_personal_access_tokens" (token_hash)
    WHERE revoked_at IS NULL;

-- DOWN ====

-- DROP TABLE IF EXISTS "02_iam"."56_fct_personal_access_tokens";
