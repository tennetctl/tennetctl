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
-- Singleton row representing the vault instance. Pure EAV — no key-material
-- columns on the fct row. All cryptographic material (mdk_ciphertext, nonce,
-- unseal_key_hash, wrapped_mdk, unseal_config, initialized_at) lives in
-- 20_dtl_attrs via the 'vault' entity attr_defs seeded in migration 001.
--
-- Only the two FK columns (status_id, unseal_mode_id) plus standard fct
-- housekeeping stay on this table — exactly what the database.md rule allows.
-- ---------------------------------------------------------------------------
CREATE TABLE "02_vault"."10_fct_vault" (
    id              VARCHAR(36) NOT NULL,
    status_id       SMALLINT    NOT NULL,
    unseal_mode_id  SMALLINT    NOT NULL,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    is_test         BOOLEAN     NOT NULL DEFAULT FALSE,
    deleted_at      TIMESTAMP,
    created_by      VARCHAR(36),
    updated_by      VARCHAR(36),
    created_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_02vault_fct_vault              PRIMARY KEY (id),
    CONSTRAINT fk_02vault_fct_vault_status       FOREIGN KEY (status_id)
        REFERENCES "02_vault"."01_dim_vault_statuses" (id),
    CONSTRAINT fk_02vault_fct_vault_unseal_mode  FOREIGN KEY (unseal_mode_id)
        REFERENCES "02_vault"."02_dim_unseal_modes" (id)
);

-- Enforce the singleton: at most one live (non-deleted) vault row.
-- A second vault initialisation is a bug, not a feature.
CREATE UNIQUE INDEX uq_02vault_fct_vault_singleton
    ON "02_vault"."10_fct_vault" ((TRUE))
    WHERE deleted_at IS NULL;

COMMENT ON TABLE "02_vault"."10_fct_vault" IS
    'Singleton vault instance. Exactly one row exists after initialization. '
    'Pure-EAV: no key-material columns on this table. All cryptographic data '
    '(mdk_ciphertext, mdk_nonce, unseal_key_hash, wrapped_mdk, unseal_config, '
    'initialized_at) lives in 20_dtl_attrs under the vault entity attr_defs '
    'seeded in migration 001. status_id and unseal_mode_id are FK IDs only — '
    'allowed on fct_* rows per database.md.';

COMMENT ON COLUMN "02_vault"."10_fct_vault".id IS
    'UUID v7 generated by the application on init.';
COMMENT ON COLUMN "02_vault"."10_fct_vault".status_id IS
    'FK to 01_dim_vault_statuses. 1 = sealed, 2 = unsealed. '
    'Updated on every seal/unseal operation.';
COMMENT ON COLUMN "02_vault"."10_fct_vault".unseal_mode_id IS
    'FK to 02_dim_unseal_modes. Selected at install time, immutable thereafter.';

-- Only the write role needs INSERT/UPDATE; this table is never deleted.
GRANT SELECT ON "02_vault"."10_fct_vault" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE ON "02_vault"."10_fct_vault" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- v_vault
-- Read view that pivots EAV attrs back alongside the two dim columns.
-- Excludes all key material — safe to include in API responses.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW "02_vault"."v_vault" AS
SELECT
    v.id,
    s.code  AS status,
    m.code  AS unseal_mode,
    (
        SELECT a.key_text
          FROM "02_vault"."20_dtl_attrs" a
         WHERE a.entity_type_id = (SELECT id FROM "02_vault"."06_dim_entity_types" WHERE code = 'vault')
           AND a.entity_id = v.id
           AND a.attr_def_id = (SELECT id FROM "02_vault"."07_dim_attr_defs"
                                 WHERE entity_type_id = (SELECT id FROM "02_vault"."06_dim_entity_types" WHERE code = 'vault')
                                   AND code = 'initialized_at')
         LIMIT 1
    )::timestamp  AS initialized_at,
    v.updated_at
FROM "02_vault"."10_fct_vault" v
JOIN "02_vault"."01_dim_vault_statuses" s ON v.status_id = s.id
JOIN "02_vault"."02_dim_unseal_modes"   m ON v.unseal_mode_id = m.id;

COMMENT ON VIEW "02_vault"."v_vault" IS
    'Read-safe view of the vault singleton. Pivots initialized_at from EAV. '
    'Excludes all key material (mdk_ciphertext, mdk_nonce, unseal_key_hash, '
    'read_key_hash, wrapped_mdk, unseal_config). Safe for API responses.';

GRANT SELECT ON "02_vault"."v_vault" TO tennetctl_read;
GRANT SELECT ON "02_vault"."v_vault" TO tennetctl_write;

-- DOWN =======================================================================

DROP VIEW IF EXISTS "02_vault"."v_vault";
DROP INDEX IF EXISTS "02_vault".uq_02vault_fct_vault_singleton;
DROP TABLE IF EXISTS "02_vault"."10_fct_vault";
DROP TABLE IF EXISTS "02_vault"."02_dim_unseal_modes";
DROP TABLE IF EXISTS "02_vault"."01_dim_vault_statuses";
