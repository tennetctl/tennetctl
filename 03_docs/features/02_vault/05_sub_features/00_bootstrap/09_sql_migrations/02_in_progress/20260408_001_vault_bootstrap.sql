-- =============================================================================
-- Migration: 20260408_001_vault_bootstrap.sql
-- Module:    02_vault
-- Sub-feature: 00_bootstrap
-- Description: Bootstrap the vault schema with the three shared EAV tables.
-- =============================================================================

-- UP =========================================================================

CREATE SCHEMA IF NOT EXISTS "02_vault";

-- Grant schema access to application roles
GRANT USAGE ON SCHEMA "02_vault" TO tennetctl_read;
GRANT USAGE ON SCHEMA "02_vault" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 06_dim_entity_types
-- Entity type registry for the vault module.
-- All entities managed by vault must have a row here before EAV data is stored.
-- ---------------------------------------------------------------------------
CREATE TABLE "02_vault"."06_dim_entity_types" (
    id            SMALLINT    NOT NULL,
    code          TEXT        NOT NULL,
    label         TEXT        NOT NULL,
    description   TEXT        NOT NULL DEFAULT '',
    deprecated_at TIMESTAMP,

    CONSTRAINT pk_02vault_dim_entity_types      PRIMARY KEY (id),
    CONSTRAINT uq_02vault_dim_entity_types_code UNIQUE (code)
);

COMMENT ON TABLE "02_vault"."06_dim_entity_types" IS
    'Entity type registry for the vault module. '
    'Every vault entity (vault, project, environment, secret, api_key) has a row here. '
    'Used by 07_dim_attr_defs and 20_dtl_attrs for EAV attribute scoping.';

COMMENT ON COLUMN "02_vault"."06_dim_entity_types".id IS
    'Stable SMALLINT identifier. Never renumber — used as FK in dtl_attrs.';
COMMENT ON COLUMN "02_vault"."06_dim_entity_types".code IS
    'Machine-readable identifier (snake_case). Used in application code.';
COMMENT ON COLUMN "02_vault"."06_dim_entity_types".label IS
    'Human-readable name shown in UIs and error messages.';
COMMENT ON COLUMN "02_vault"."06_dim_entity_types".description IS
    'Plain-English description of what this entity type represents.';
COMMENT ON COLUMN "02_vault"."06_dim_entity_types".deprecated_at IS
    'NULL = active. SET = retired. Never delete rows — set deprecated_at instead.';

INSERT INTO "02_vault"."06_dim_entity_types" (id, code, label, description) VALUES
    (1, 'vault',       'Vault',       'The singleton vault instance. Holds the sealed/unsealed state and MDK ciphertext.'),
    (2, 'project',     'Project',     'A container that groups secrets by application or service.'),
    (3, 'environment', 'Environment', 'A named environment within a project (e.g. dev, staging, prod).'),
    (4, 'secret',      'Secret',      'An encrypted key-value pair: env var, config value, or arbitrary secret.'),
    (5, 'api_key',     'API Key',     'A scoped programmatic access key bound to a project and optionally an environment.');

-- Grant SELECT on this table to both roles
GRANT SELECT ON "02_vault"."06_dim_entity_types" TO tennetctl_read;
GRANT SELECT ON "02_vault"."06_dim_entity_types" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 07_dim_attr_defs
-- Attribute definitions for all vault entity types.
-- Every EAV property must be registered here before values can be stored.
-- ---------------------------------------------------------------------------
CREATE TABLE "02_vault"."07_dim_attr_defs" (
    id             SMALLINT    NOT NULL,
    entity_type_id SMALLINT    NOT NULL,
    code           TEXT        NOT NULL,
    label          TEXT        NOT NULL,
    value_type     TEXT        NOT NULL DEFAULT 'text',
    is_required    BOOLEAN     NOT NULL DEFAULT FALSE,
    is_unique      BOOLEAN     NOT NULL DEFAULT FALSE,
    description    TEXT        NOT NULL DEFAULT '',
    deprecated_at  TIMESTAMP,

    CONSTRAINT pk_02vault_dim_attr_defs                PRIMARY KEY (id),
    CONSTRAINT uq_02vault_dim_attr_defs_entity_code    UNIQUE (entity_type_id, code),
    CONSTRAINT fk_02vault_dim_attr_defs_entity_type    FOREIGN KEY (entity_type_id)
        REFERENCES "02_vault"."06_dim_entity_types" (id),
    CONSTRAINT chk_02vault_dim_attr_defs_value_type    CHECK (
        value_type IN ('text', 'jsonb')
    )
);

COMMENT ON TABLE "02_vault"."07_dim_attr_defs" IS
    'Attribute definitions for vault EAV. Every property on every vault entity '
    'must be registered here before values can be stored in 20_dtl_attrs. '
    'Adding a new property requires an INSERT here — no ALTER TABLE needed.';

COMMENT ON COLUMN "02_vault"."07_dim_attr_defs".id IS
    'Stable SMALLINT identifier. Never renumber.';
COMMENT ON COLUMN "02_vault"."07_dim_attr_defs".entity_type_id IS
    'FK to 06_dim_entity_types. This attribute belongs to that entity type.';
COMMENT ON COLUMN "02_vault"."07_dim_attr_defs".code IS
    'Machine-readable attribute name (snake_case). Used as the key in application code.';
COMMENT ON COLUMN "02_vault"."07_dim_attr_defs".label IS
    'Human-readable attribute name for UIs and error messages.';
COMMENT ON COLUMN "02_vault"."07_dim_attr_defs".value_type IS
    'Storage type: text (key_text column) or jsonb (key_jsonb column).';
COMMENT ON COLUMN "02_vault"."07_dim_attr_defs".is_required IS
    'TRUE = application must populate this attribute when creating the entity.';
COMMENT ON COLUMN "02_vault"."07_dim_attr_defs".is_unique IS
    'TRUE = application must enforce uniqueness of this attribute within scope.';
COMMENT ON COLUMN "02_vault"."07_dim_attr_defs".description IS
    'Plain-English description of what this attribute holds.';
COMMENT ON COLUMN "02_vault"."07_dim_attr_defs".deprecated_at IS
    'NULL = active. SET = retired. Never delete rows — set deprecated_at instead.';

-- Seed: project attributes
INSERT INTO "02_vault"."07_dim_attr_defs"
    (id, entity_type_id, code, label, value_type, is_required, is_unique, description) VALUES
    (1, 2, 'name',        'Name',        'text', TRUE,  FALSE, 'Project display name.'),
    (2, 2, 'slug',        'Slug',        'text', TRUE,  TRUE,  'URL-safe project identifier. Unique per organisation.'),
    (3, 2, 'description', 'Description', 'text', FALSE, FALSE, 'Optional project description.');

-- Seed: environment attributes
INSERT INTO "02_vault"."07_dim_attr_defs"
    (id, entity_type_id, code, label, value_type, is_required, is_unique, description) VALUES
    (4, 3, 'name', 'Name', 'text', TRUE, TRUE, 'Environment name (e.g. dev, staging, production). Unique per project.');

-- Seed: secret attributes
INSERT INTO "02_vault"."07_dim_attr_defs"
    (id, entity_type_id, code, label, value_type, is_required, is_unique, description) VALUES
    (5, 4, 'key',         'Key',         'text', TRUE,  TRUE,  'Secret key name (e.g. DATABASE_URL). Unique per project+environment.'),
    (6, 4, 'description', 'Description', 'text', FALSE, FALSE, 'Optional description of what this secret is used for.');

-- Seed: api_key attributes
INSERT INTO "02_vault"."07_dim_attr_defs"
    (id, entity_type_id, code, label, value_type, is_required, is_unique, description) VALUES
    (7, 5, 'name',        'Name',        'text', TRUE,  FALSE, 'Human-readable label for this API key (e.g. "CI pipeline key").'),
    (8, 5, 'description', 'Description', 'text', FALSE, FALSE, 'Optional description of what this key is used for.');

GRANT SELECT ON "02_vault"."07_dim_attr_defs" TO tennetctl_read;
GRANT SELECT ON "02_vault"."07_dim_attr_defs" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 20_dtl_attrs
-- EAV attribute values for all vault entities.
-- One row per (entity_type, entity, attribute) triple.
-- Exactly one of key_text or key_jsonb is populated — enforced by CHECK.
-- ---------------------------------------------------------------------------
CREATE TABLE "02_vault"."20_dtl_attrs" (
    entity_type_id SMALLINT    NOT NULL,
    entity_id      VARCHAR(36) NOT NULL,
    attr_def_id    SMALLINT    NOT NULL,
    key_text       TEXT,
    key_jsonb      TEXT,
    created_by     VARCHAR(36),
    updated_by     VARCHAR(36),
    created_at     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_02vault_dtl_attrs               PRIMARY KEY (entity_type_id, entity_id, attr_def_id),
    CONSTRAINT fk_02vault_dtl_attrs_entity_type   FOREIGN KEY (entity_type_id)
        REFERENCES "02_vault"."06_dim_entity_types" (id),
    CONSTRAINT fk_02vault_dtl_attrs_attr_def       FOREIGN KEY (attr_def_id)
        REFERENCES "02_vault"."07_dim_attr_defs" (id),
    CONSTRAINT chk_02vault_dtl_attrs_one_value     CHECK (
        (key_text IS NOT NULL AND key_jsonb IS NULL) OR
        (key_jsonb IS NOT NULL AND key_text IS NULL)
    )
);

CREATE INDEX idx_02vault_dtl_attrs_entity
    ON "02_vault"."20_dtl_attrs" (entity_type_id, entity_id);

COMMENT ON TABLE "02_vault"."20_dtl_attrs" IS
    'EAV attribute values for all vault entities. '
    'One row per (entity_type_id, entity_id, attr_def_id) triple. '
    'Exactly one of key_text or key_jsonb is populated per row (enforced by CHECK). '
    'Join with 07_dim_attr_defs to resolve the attribute code and type.';

COMMENT ON COLUMN "02_vault"."20_dtl_attrs".entity_type_id IS
    'FK to 06_dim_entity_types. Identifies what kind of entity this attribute belongs to.';
COMMENT ON COLUMN "02_vault"."20_dtl_attrs".entity_id IS
    'UUID v7 of the entity. Not FK-enforced — entity lives in its own fct_* table.';
COMMENT ON COLUMN "02_vault"."20_dtl_attrs".attr_def_id IS
    'FK to 07_dim_attr_defs. Identifies which attribute this row stores.';
COMMENT ON COLUMN "02_vault"."20_dtl_attrs".key_text IS
    'Simple string value. Populated when attr_def value_type = text. '
    'NULL when key_jsonb is set.';
COMMENT ON COLUMN "02_vault"."20_dtl_attrs".key_jsonb IS
    'Structured JSON value stored as TEXT for portability. '
    'Parse in application code. NULL when key_text is set.';
COMMENT ON COLUMN "02_vault"."20_dtl_attrs".created_by IS
    'UUID of the actor who created this attribute value. NULL = system.';
COMMENT ON COLUMN "02_vault"."20_dtl_attrs".updated_by IS
    'UUID of the actor who last updated this attribute value. NULL = system.';

GRANT SELECT ON "02_vault"."20_dtl_attrs" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE, DELETE ON "02_vault"."20_dtl_attrs" TO tennetctl_write;

-- Default privileges so future tables in this schema inherit the same grants
ALTER DEFAULT PRIVILEGES IN SCHEMA "02_vault"
    GRANT SELECT ON TABLES TO tennetctl_read;

ALTER DEFAULT PRIVILEGES IN SCHEMA "02_vault"
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO tennetctl_write;

-- DOWN =======================================================================

DROP TABLE IF EXISTS "02_vault"."20_dtl_attrs";
DROP TABLE IF EXISTS "02_vault"."07_dim_attr_defs";
DROP TABLE IF EXISTS "02_vault"."06_dim_entity_types";
DROP SCHEMA IF EXISTS "02_vault";
