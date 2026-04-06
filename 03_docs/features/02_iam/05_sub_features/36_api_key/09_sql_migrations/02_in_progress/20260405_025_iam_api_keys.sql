-- ============================================================================
-- Migration 025: Org-Scoped API Keys
-- ============================================================================
-- Publishable keys (pk_live_*) for client-side SDKs and secret keys (sk_live_*)
-- for server-to-server auth. Used by external services like kbio (s-forensics).
-- ============================================================================

-- UP ====

CREATE TABLE IF NOT EXISTS "02_iam"."57_fct_api_keys" (
    id              VARCHAR(36) NOT NULL,
    org_id          VARCHAR(36) NOT NULL,
    workspace_id    VARCHAR(36),
    label           VARCHAR(255) NOT NULL,
    publishable_key VARCHAR(64) NOT NULL,
    key_prefix      VARCHAR(12) NOT NULL,
    secret_hash     VARCHAR(64) NOT NULL,
    scopes          JSONB NOT NULL DEFAULT '["*"]'::jsonb,
    last_used_at    TIMESTAMP,
    expires_at      TIMESTAMP,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_test         BOOLEAN NOT NULL DEFAULT FALSE,
    created_by      VARCHAR(36) NOT NULL,
    updated_by      VARCHAR(36) NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at      TIMESTAMP,
    deleted_at      TIMESTAMP,

    CONSTRAINT pk_57_fct_api_keys PRIMARY KEY (id),
    CONSTRAINT fk_57_api_keys_org FOREIGN KEY (org_id)
        REFERENCES "02_iam"."11_fct_orgs" (id),
    CONSTRAINT uq_57_api_keys_publishable UNIQUE (publishable_key),
    CONSTRAINT uq_57_api_keys_secret_hash UNIQUE (secret_hash)
);

COMMENT ON TABLE "02_iam"."57_fct_api_keys" IS 'Org-scoped API keys — publishable (pk_live_*) and secret (sk_live_*) for external service auth.';
COMMENT ON COLUMN "02_iam"."57_fct_api_keys".publishable_key IS 'Client-safe key for SDK identification (pk_live_*). Stored in plaintext.';
COMMENT ON COLUMN "02_iam"."57_fct_api_keys".secret_hash IS 'SHA-256 hash of the secret key (sk_live_*). Never stored in plaintext.';
COMMENT ON COLUMN "02_iam"."57_fct_api_keys".key_prefix IS 'First 12 chars of secret key for display identification.';
COMMENT ON COLUMN "02_iam"."57_fct_api_keys".scopes IS 'JSON array of permission scopes (e.g. ["*"], ["read:devices"]).';

CREATE INDEX idx_57_api_keys_org ON "02_iam"."57_fct_api_keys" (org_id)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_57_api_keys_publishable ON "02_iam"."57_fct_api_keys" (publishable_key)
    WHERE revoked_at IS NULL AND deleted_at IS NULL;

CREATE INDEX idx_57_api_keys_secret_hash ON "02_iam"."57_fct_api_keys" (secret_hash)
    WHERE revoked_at IS NULL AND deleted_at IS NULL;

-- updated_at trigger
CREATE TRIGGER trg_57_fct_api_keys_updated_at
    BEFORE UPDATE ON "02_iam"."57_fct_api_keys"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- DOWN ====

DROP TRIGGER IF EXISTS trg_57_fct_api_keys_updated_at ON "02_iam"."57_fct_api_keys";
DROP INDEX IF EXISTS "02_iam".idx_57_api_keys_secret_hash;
DROP INDEX IF EXISTS "02_iam".idx_57_api_keys_publishable;
DROP INDEX IF EXISTS "02_iam".idx_57_api_keys_org;
DROP TABLE IF EXISTS "02_iam"."57_fct_api_keys";
