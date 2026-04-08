-- =============================================================================
-- Migration: 20260408_002_vault_setup.sql
-- Module:    02_vault
-- Sub-feature: 01_setup
-- Description: Vault singleton table and lookup dims for the init/unseal/seal
--              lifecycle with pluggable unseal backends (manual, kms_azure,
--              kms_aws, kms_gcp). Requires 20260408_001_vault_bootstrap.sql
--              to have run first (schema and EAV tables must exist).
-- =============================================================================

-- UP =========================================================================

-- ---------------------------------------------------------------------------
-- 01_dim_vault_statuses
-- Lookup table for vault sealed/unsealed state.
-- ---------------------------------------------------------------------------
CREATE TABLE "02_vault"."01_dim_vault_statuses" (
    id            SMALLINT    NOT NULL,
    code          TEXT        NOT NULL,
    label         TEXT        NOT NULL,
    description   TEXT        NOT NULL DEFAULT '',
    deprecated_at TIMESTAMP,

    CONSTRAINT pk_02vault_dim_vault_statuses      PRIMARY KEY (id),
    CONSTRAINT uq_02vault_dim_vault_statuses_code UNIQUE (code)
);

COMMENT ON TABLE "02_vault"."01_dim_vault_statuses" IS
    'Lookup table for the sealed/unsealed state of the vault singleton. '
    'Seeded at migration time — never mutated by the application.';

COMMENT ON COLUMN "02_vault"."01_dim_vault_statuses".id IS
    'Stable SMALLINT PK. 1 = sealed, 2 = unsealed. Never renumber.';
COMMENT ON COLUMN "02_vault"."01_dim_vault_statuses".code IS
    'Machine-readable status code used in application logic and API responses.';
COMMENT ON COLUMN "02_vault"."01_dim_vault_statuses".label IS
    'Human-readable label for UIs.';
COMMENT ON COLUMN "02_vault"."01_dim_vault_statuses".description IS
    'Plain-English explanation of what this status means.';
COMMENT ON COLUMN "02_vault"."01_dim_vault_statuses".deprecated_at IS
    'NULL = active. SET = retired. Never delete rows.';

INSERT INTO "02_vault"."01_dim_vault_statuses" (id, code, label, description) VALUES
    (1, 'sealed',   'Sealed',   'Vault is locked. MDK is not in memory. No secrets can be read or written.'),
    (2, 'unsealed', 'Unsealed', 'Vault is unlocked. MDK is held in memory. Secrets are accessible.');

GRANT SELECT ON "02_vault"."01_dim_vault_statuses" TO tennetctl_read;
GRANT SELECT ON "02_vault"."01_dim_vault_statuses" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 02_dim_unseal_modes
-- Lookup table for the pluggable UnsealBackend implementations.
-- Selected at install time; cannot be changed without re-encrypting the MDK.
-- ---------------------------------------------------------------------------
CREATE TABLE "02_vault"."02_dim_unseal_modes" (
    id            SMALLINT    NOT NULL,
    code          TEXT        NOT NULL,
    label         TEXT        NOT NULL,
    description   TEXT        NOT NULL DEFAULT '',
    deprecated_at TIMESTAMP,

    CONSTRAINT pk_02vault_dim_unseal_modes      PRIMARY KEY (id),
    CONSTRAINT uq_02vault_dim_unseal_modes_code UNIQUE (code)
);

COMMENT ON TABLE "02_vault"."02_dim_unseal_modes" IS
    'Lookup table for the pluggable UnsealBackend implementations. '
    'The selected mode is stored in 10_fct_vault.unseal_mode_id and read on '
    'every boot to dispatch to the right backend. Mode cannot change after '
    'install without re-encrypting the MDK.';

COMMENT ON COLUMN "02_vault"."02_dim_unseal_modes".id IS
    'Stable SMALLINT PK. Never renumber.';
COMMENT ON COLUMN "02_vault"."02_dim_unseal_modes".code IS
    'Machine-readable code dispatched in application code: manual | kms_azure | kms_aws | kms_gcp.';
COMMENT ON COLUMN "02_vault"."02_dim_unseal_modes".label IS
    'Human-readable label for UIs and install-wizard output.';
COMMENT ON COLUMN "02_vault"."02_dim_unseal_modes".description IS
    'Plain-English explanation of the unseal flow under this mode.';
COMMENT ON COLUMN "02_vault"."02_dim_unseal_modes".deprecated_at IS
    'NULL = active. SET = retired. Never delete rows.';

INSERT INTO "02_vault"."02_dim_unseal_modes" (id, code, label, description) VALUES
    (1, 'manual',    'Manual (operator key)',
        'Operator provides the Root Unseal Key on every process restart. '
        'Used for local dev, single-VM deployments, and the install ceremony. '
        'Not K8s-friendly — no horizontal scaling without human intervention.'),
    (2, 'kms_azure', 'Azure Key Vault',
        'Pod authenticates to Azure Key Vault via Workload Identity (AKS) or '
        'DefaultAzureCredential (local/CI). The MDK is wrapped with an Azure '
        'Key Vault key; the pod calls unwrapKey on boot and auto-unseals.'),
    (3, 'kms_aws',   'AWS KMS',
        'Pod authenticates to AWS KMS via IRSA (EKS). The MDK data key is '
        'wrapped with a KMS key; the pod calls Decrypt on boot and auto-unseals. '
        '(PLANNED — not built in v1.)'),
    (4, 'kms_gcp',   'GCP KMS',
        'Pod authenticates to Cloud KMS via Workload Identity (GKE). The MDK is '
        'wrapped with a KMS key; the pod calls decrypt on boot and auto-unseals. '
        '(PLANNED — not built in v1.)');

GRANT SELECT ON "02_vault"."02_dim_unseal_modes" TO tennetctl_read;
GRANT SELECT ON "02_vault"."02_dim_unseal_modes" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 10_fct_vault
-- Singleton row representing the vault instance.
-- Created once at install time. Never deleted.
--
-- The shape of the "key material" columns depends on unseal_mode_id:
--
--   manual mode:
--     mdk_ciphertext, mdk_nonce           — MDK encrypted with Root Unseal Key
--     unseal_key_hash                     — BLAKE2b of Root Unseal Key (verify on unseal)
--     read_key_hash                       — BLAKE2b of Root Read Key (reserved)
--     wrapped_mdk                         — NULL
--     unseal_config                       — NULL
--
--   kms_azure / kms_aws / kms_gcp modes:
--     wrapped_mdk                         — MDK wrapped by the cloud KMS key
--     unseal_config                       — JSONB with backend-specific metadata
--                                           (key vault URL, key name, key version,
--                                            KMS ARN, workload identity hints, etc.)
--     mdk_ciphertext, mdk_nonce           — NULL
--     unseal_key_hash, read_key_hash      — NULL
--
-- Plaintext of any key is NEVER stored here.
-- ---------------------------------------------------------------------------
CREATE TABLE "02_vault"."10_fct_vault" (
    id               VARCHAR(36) NOT NULL,
    status_id        SMALLINT    NOT NULL,
    unseal_mode_id   SMALLINT    NOT NULL,
    unseal_config    TEXT,
    wrapped_mdk      TEXT,
    mdk_ciphertext   TEXT,
    mdk_nonce        TEXT,
    unseal_key_hash  TEXT,
    read_key_hash    TEXT,
    initialized_at   TIMESTAMP,
    created_at       TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_02vault_fct_vault              PRIMARY KEY (id),
    CONSTRAINT fk_02vault_fct_vault_status       FOREIGN KEY (status_id)
        REFERENCES "02_vault"."01_dim_vault_statuses" (id),
    CONSTRAINT fk_02vault_fct_vault_unseal_mode  FOREIGN KEY (unseal_mode_id)
        REFERENCES "02_vault"."02_dim_unseal_modes" (id),
    CONSTRAINT chk_02vault_fct_vault_init        CHECK (
        -- Either not initialized yet, or initialized with exactly one form of key material
        initialized_at IS NULL OR
        -- manual mode: mdk_ciphertext + mdk_nonce + unseal_key_hash must all be set,
        --              wrapped_mdk must be NULL
        (unseal_mode_id = 1 AND
         mdk_ciphertext IS NOT NULL AND mdk_nonce IS NOT NULL AND
         unseal_key_hash IS NOT NULL AND
         wrapped_mdk IS NULL) OR
        -- kms_* modes: wrapped_mdk + unseal_config must be set,
        --              mdk_ciphertext/mdk_nonce/unseal_key_hash must be NULL
        (unseal_mode_id IN (2, 3, 4) AND
         wrapped_mdk IS NOT NULL AND unseal_config IS NOT NULL AND
         mdk_ciphertext IS NULL AND mdk_nonce IS NULL AND
         unseal_key_hash IS NULL)
    )
);

COMMENT ON TABLE "02_vault"."10_fct_vault" IS
    'Singleton vault instance. Exactly one row exists after initialization. '
    'Holds the encrypted Master Data Key (MDK) in a shape that depends on the '
    'selected unseal mode. Plaintext of any key is never stored. See the CHECK '
    'constraint chk_02vault_fct_vault_init for the per-mode column requirements.';

COMMENT ON COLUMN "02_vault"."10_fct_vault".id IS
    'UUID v7 generated by the application on init.';
COMMENT ON COLUMN "02_vault"."10_fct_vault".status_id IS
    'FK to 01_dim_vault_statuses. 1 = sealed, 2 = unsealed. '
    'Updated on every seal/unseal operation.';
COMMENT ON COLUMN "02_vault"."10_fct_vault".unseal_mode_id IS
    'FK to 02_dim_unseal_modes. Selected at install time, immutable thereafter. '
    'Determines which UnsealBackend the app dispatches to on boot.';
COMMENT ON COLUMN "02_vault"."10_fct_vault".unseal_config IS
    'JSONB (stored as TEXT for portability) containing backend-specific metadata. '
    'kms_azure: { "vault_url": "...", "key_name": "...", "key_version": "..." }. '
    'kms_aws:   { "key_arn": "...", "region": "..." }. '
    'kms_gcp:   { "project": "...", "location": "...", "key_ring": "...", "key": "..." }. '
    'NULL in manual mode.';
COMMENT ON COLUMN "02_vault"."10_fct_vault".wrapped_mdk IS
    'MDK wrapped by the cloud KMS key. base64url-encoded. '
    'Used only in kms_azure / kms_aws / kms_gcp modes. NULL in manual mode.';
COMMENT ON COLUMN "02_vault"."10_fct_vault".mdk_ciphertext IS
    'AES-256-GCM ciphertext of the 32-byte Master Data Key, base64url-encoded. '
    'Encrypted with the Root Unseal Key. Used only in manual mode. NULL in KMS modes.';
COMMENT ON COLUMN "02_vault"."10_fct_vault".mdk_nonce IS
    'AES-256-GCM 12-byte nonce used when encrypting mdk_ciphertext, base64url-encoded. '
    'Used only in manual mode. NULL in KMS modes.';
COMMENT ON COLUMN "02_vault"."10_fct_vault".unseal_key_hash IS
    'BLAKE2b-256 hex digest of the Root Unseal Key. '
    'Used to verify the key on unseal. Used only in manual mode. NULL in KMS modes.';
COMMENT ON COLUMN "02_vault"."10_fct_vault".read_key_hash IS
    'BLAKE2b-256 hex digest of the Root Read Key. '
    'Reserved for future root-read operations. Used only in manual mode. NULL in KMS modes.';
COMMENT ON COLUMN "02_vault"."10_fct_vault".initialized_at IS
    'Timestamp of the first successful init. NULL = not yet initialized.';
COMMENT ON COLUMN "02_vault"."10_fct_vault".created_at IS
    'Row creation timestamp. Set once, never updated.';
COMMENT ON COLUMN "02_vault"."10_fct_vault".updated_at IS
    'Updated on every seal/unseal operation.';

-- Only the write role needs INSERT/UPDATE; this table is never deleted.
GRANT SELECT ON "02_vault"."10_fct_vault" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE ON "02_vault"."10_fct_vault" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- v_vault
-- Read view for the vault singleton. Excludes all key material.
-- Returns status, unseal mode, and timestamps — safe to include in API responses.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW "02_vault"."v_vault" AS
SELECT
    v.id,
    s.code          AS status,
    m.code          AS unseal_mode,
    v.initialized_at,
    v.updated_at
FROM "02_vault"."10_fct_vault" v
JOIN "02_vault"."01_dim_vault_statuses" s ON v.status_id = s.id
JOIN "02_vault"."02_dim_unseal_modes"  m ON v.unseal_mode_id = m.id;

COMMENT ON VIEW "02_vault"."v_vault" IS
    'Read-safe view of the vault singleton. '
    'Excludes mdk_ciphertext, mdk_nonce, unseal_key_hash, read_key_hash, '
    'wrapped_mdk, and unseal_config. The only view safe to include in API responses.';

GRANT SELECT ON "02_vault"."v_vault" TO tennetctl_read;
GRANT SELECT ON "02_vault"."v_vault" TO tennetctl_write;

-- DOWN =======================================================================

DROP VIEW IF EXISTS "02_vault"."v_vault";
DROP TABLE IF EXISTS "02_vault"."10_fct_vault";
DROP TABLE IF EXISTS "02_vault"."02_dim_unseal_modes";
DROP TABLE IF EXISTS "02_vault"."01_dim_vault_statuses";
