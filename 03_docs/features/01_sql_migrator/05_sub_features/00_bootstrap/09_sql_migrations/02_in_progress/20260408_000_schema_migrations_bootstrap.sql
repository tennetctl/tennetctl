-- =============================================================================
-- Migration: 20260408_000_schema_migrations_bootstrap.sql
-- Module:    01_sql_migrator
-- Sub-feature: 00_bootstrap
-- Sequence:  000  (special — applied by hand on fresh DB, before runner exists)
-- Description: Bootstrap the 00_schema_migrations schema and applied_migrations
--              tracking table. This is the only migration that is NOT applied
--              by the Python runner — it must be run manually first.
--
-- Apply (UP):
--   docker compose exec postgres psql -U tennetctl_admin -d tennetctl \
--     -f /path/to/20260408_000_schema_migrations_bootstrap.sql
--
-- Revert (DOWN): extract and run the DOWN section manually.
-- =============================================================================

-- UP =========================================================================

-- The 00_ prefix ensures this schema sorts first alphabetically,
-- before all feature schemas (01_sql_migrator, 02_vault, etc.).
CREATE SCHEMA IF NOT EXISTS "00_schema_migrations";

GRANT USAGE ON SCHEMA "00_schema_migrations" TO tennetctl_read;
GRANT USAGE ON SCHEMA "00_schema_migrations" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- applied_migrations
-- One row per SQL migration file that has been successfully applied.
-- The runner inserts here after each successful UP execution.
-- The checksum catches post-apply file modifications.
-- ---------------------------------------------------------------------------
CREATE TABLE "00_schema_migrations"."applied_migrations" (
    sequence      SMALLINT    NOT NULL,
    filename      TEXT        NOT NULL,
    feature       TEXT        NOT NULL,
    sub_feature   TEXT        NOT NULL,
    checksum      TEXT        NOT NULL,
    applied_at    TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    applied_by    TEXT        NOT NULL DEFAULT current_user,
    execution_ms  INTEGER,

    CONSTRAINT pk_applied_migrations      PRIMARY KEY (sequence),
    CONSTRAINT uq_applied_migrations_file UNIQUE (filename),
    CONSTRAINT chk_applied_migrations_seq CHECK (sequence >= 0)
);

CREATE INDEX idx_applied_migrations_feature
    ON "00_schema_migrations"."applied_migrations" (feature);

CREATE INDEX idx_applied_migrations_applied_at
    ON "00_schema_migrations"."applied_migrations" (applied_at DESC);

COMMENT ON TABLE "00_schema_migrations"."applied_migrations" IS
    'Tracks every SQL migration that has been successfully applied to this database. '
    'One row per migration file. The runner inserts here atomically after each UP execution. '
    'The sequence column is the global NNN from the filename and must be unique.';

COMMENT ON COLUMN "00_schema_migrations"."applied_migrations".sequence IS
    'The three-digit NNN from the migration filename (e.g. 002 from 20260408_002_vault_setup.sql). '
    'Globally unique across ALL features and sub-features. Primary key.';
COMMENT ON COLUMN "00_schema_migrations"."applied_migrations".filename IS
    'The migration filename without path (e.g. 20260408_002_vault_setup.sql). '
    'Unique — same file can never be applied twice.';
COMMENT ON COLUMN "00_schema_migrations"."applied_migrations".feature IS
    'Feature that owns this migration (e.g. 02_vault). From migration.yaml.';
COMMENT ON COLUMN "00_schema_migrations"."applied_migrations".sub_feature IS
    'Sub-feature that owns this migration (e.g. 01_setup). From migration.yaml.';
COMMENT ON COLUMN "00_schema_migrations"."applied_migrations".checksum IS
    'SHA-256 hex digest of the migration file contents at time of application. '
    'Runner warns if this does not match the current file on disk.';
COMMENT ON COLUMN "00_schema_migrations"."applied_migrations".applied_at IS
    'Timestamp when this migration was successfully applied.';
COMMENT ON COLUMN "00_schema_migrations"."applied_migrations".applied_by IS
    'Postgres role that applied this migration. Defaults to current_user.';
COMMENT ON COLUMN "00_schema_migrations"."applied_migrations".execution_ms IS
    'Wall-clock milliseconds the UP section took to execute. NULL if not measured.';

-- Grant access
GRANT SELECT ON "00_schema_migrations"."applied_migrations" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE, DELETE ON "00_schema_migrations"."applied_migrations" TO tennetctl_write;

-- Record this bootstrap migration as the very first applied entry.
-- sequence=0 is the special value reserved for this self-referential row.
INSERT INTO "00_schema_migrations"."applied_migrations"
    (sequence, filename, feature, sub_feature, checksum, applied_by, execution_ms)
VALUES
    (0,
     '20260408_000_schema_migrations_bootstrap.sql',
     '01_sql_migrator',
     '00_bootstrap',
     'bootstrapped-by-hand',   -- real checksum populated by runner on subsequent validation
     current_user,
     NULL);

-- ---------------------------------------------------------------------------
-- system_meta
-- Install-state singleton. Exactly one row, enforced by CHECK (id = 1).
-- Populated by the 00_setup install wizard in its final step.
-- Read on every app boot as the single DB-side install marker; there is
-- no filesystem counterpart to cross-check against.
-- ---------------------------------------------------------------------------
CREATE TABLE "00_schema_migrations"."system_meta" (
    id                      SMALLINT    NOT NULL,
    install_id              TEXT,
    installed_at            TIMESTAMP,
    installer_version       TEXT,
    first_admin_username    TEXT,
    first_admin_created_at  TIMESTAMP,
    vault_initialized_at    TIMESTAMP,
    unseal_mode             TEXT,
    unseal_salt             TEXT,
    last_migration_at       TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at              TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_system_meta          PRIMARY KEY (id),
    CONSTRAINT chk_system_meta_singleton CHECK (id = 1),
    CONSTRAINT chk_system_meta_unseal_mode CHECK (
        unseal_mode IS NULL OR unseal_mode IN ('manual', 'kms_azure', 'kms_aws', 'kms_gcp')
    )
);

COMMENT ON TABLE "00_schema_migrations"."system_meta" IS
    'Install-state singleton. Exactly one row, enforced by CHECK (id = 1). '
    'Populated by the 00_setup install wizard. Read on every boot as the '
    'single DB-side install marker — there is no filesystem counterpart. '
    'NULL columns indicate the install has not reached that phase yet.';

COMMENT ON COLUMN "00_schema_migrations"."system_meta".id IS
    'Always 1. Enforced by CHECK constraint. No second row can ever exist.';
COMMENT ON COLUMN "00_schema_migrations"."system_meta".install_id IS
    'ULID generated once in Phase 0 of the install wizard. Retained as an '
    'identity marker for audit logs and support tickets; not cross-checked '
    'against any off-DB state.';
COMMENT ON COLUMN "00_schema_migrations"."system_meta".installed_at IS
    'Timestamp of the first successful install completion. NULL until the '
    '00_setup wizard finishes all phases.';
COMMENT ON COLUMN "00_schema_migrations"."system_meta".installer_version IS
    'Version string of the installer that ran the install (e.g. "0.1.0").';
COMMENT ON COLUMN "00_schema_migrations"."system_meta".first_admin_username IS
    'Username of the first admin user created during install. Informational only.';
COMMENT ON COLUMN "00_schema_migrations"."system_meta".first_admin_created_at IS
    'Timestamp when the first admin user row was inserted into 03_iam.10_fct_users.';
COMMENT ON COLUMN "00_schema_migrations"."system_meta".vault_initialized_at IS
    'Timestamp when the vault singleton was initialized (MDK generated and persisted).';
COMMENT ON COLUMN "00_schema_migrations"."system_meta".unseal_mode IS
    'Which unseal backend this deployment uses: manual, kms_azure, kms_aws, kms_gcp. '
    'Cannot change without re-encrypting the MDK. Read on every boot to pick the '
    'right UnsealBackend implementation.';
COMMENT ON COLUMN "00_schema_migrations"."system_meta".unseal_salt IS
    'Base64url-encoded 16-byte random salt used by the vault KDF. '
    'Set once during Phase 2 of the install wizard. Together with the '
    'password portion of $DATABASE_URL this allows the runtime to derive '
    'the MDK-wrapping key without any additional operator input. '
    'NULL before vault initialisation.';
COMMENT ON COLUMN "00_schema_migrations"."system_meta".last_migration_at IS
    'Timestamp of the most recent successful migrate up run. Updated by the runner.';

-- Seed the singleton row. All install-related columns start NULL; the wizard
-- fills them in. last_migration_at defaults to now so the column is never NULL.
INSERT INTO "00_schema_migrations"."system_meta" (id) VALUES (1);

GRANT SELECT ON "00_schema_migrations"."system_meta" TO tennetctl_read;
GRANT SELECT, UPDATE ON "00_schema_migrations"."system_meta" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 10_fct_settings
-- Mutable runtime configuration stored as rows in the database. Replaces
-- config.toml as the source of truth for anything that can change after
-- install without redeployment. Only DATABASE_URL and TENNETCTL_ENV come
-- from the environment; everything else lives here.
--
-- Owned by 00_setup (feature 00). Lives in the 00_schema_migrations schema
-- so it is available before any feature schema is created. The install
-- wizard's Phase 4 seeds the mandatory rows via ON CONFLICT DO NOTHING,
-- making re-runs idempotent and never clobbering operator edits.
--
-- DDL here is schema-only; no data rows are seeded in this migration.
-- ---------------------------------------------------------------------------
CREATE TABLE "00_schema_migrations"."10_fct_settings" (
    id           VARCHAR(36) NOT NULL,
    scope        TEXT        NOT NULL,
    key          TEXT        NOT NULL,
    value        TEXT,
    value_type   TEXT        NOT NULL DEFAULT 'text',
    value_secret BOOLEAN     NOT NULL DEFAULT FALSE,
    description  TEXT,
    created_at   TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_settings           PRIMARY KEY (id),
    CONSTRAINT uq_settings_scope_key UNIQUE (scope, key),
    CONSTRAINT chk_settings_scope    CHECK (scope ~ '^[0-9a-z_]+$'),
    CONSTRAINT chk_settings_value_type CHECK (
        value_type IN ('text', 'int', 'bool', 'json', 'duration')
    )
);

CREATE INDEX idx_settings_scope
    ON "00_schema_migrations"."10_fct_settings" (scope);

COMMENT ON TABLE "00_schema_migrations"."10_fct_settings" IS
    'Mutable runtime configuration. One row per (scope, key). Scope is '
    '"global" or a feature code like "03_iam". Seeded by the 00_setup '
    'wizard Phase 4 (no rows here in the bootstrap migration itself). '
    'Read on app startup into app.state.settings. Live-reload is not '
    'supported in v1 — changes require a restart.';

COMMENT ON COLUMN "00_schema_migrations"."10_fct_settings".id IS
    'UUID v7 primary key. Generated by the writer (wizard or admin API).';
COMMENT ON COLUMN "00_schema_migrations"."10_fct_settings".scope IS
    'Namespace for the setting. Either "global" for cross-feature settings '
    'or a feature code like "03_iam" / "02_vault". Constrained by '
    'chk_settings_scope to ^[0-9a-z_]+$ so it always matches our feature '
    'directory naming.';
COMMENT ON COLUMN "00_schema_migrations"."10_fct_settings".key IS
    'Setting name within its scope (e.g. jwt_expiry_seconds). Unique per '
    'scope via uq_settings_scope_key.';
COMMENT ON COLUMN "00_schema_migrations"."10_fct_settings".value IS
    'Setting value as TEXT. NULL means "fall back to the code default". '
    'Parsing to the concrete type is the reading code''s responsibility.';
COMMENT ON COLUMN "00_schema_migrations"."10_fct_settings".value_type IS
    'Hint for parsers: text | int | bool | json | duration. Constrained '
    'by chk_settings_value_type. Does not affect storage — value is '
    'always TEXT.';
COMMENT ON COLUMN "00_schema_migrations"."10_fct_settings".value_secret IS
    'Redaction hint. TRUE means the value must be masked in logs and API '
    'responses. This does NOT encrypt at rest — truly sensitive values '
    '(DSNs, API keys) belong in the vault, not here.';
COMMENT ON COLUMN "00_schema_migrations"."10_fct_settings".description IS
    'Human-readable explanation of what the setting controls.';
COMMENT ON COLUMN "00_schema_migrations"."10_fct_settings".created_at IS
    'Row creation timestamp (UTC).';
COMMENT ON COLUMN "00_schema_migrations"."10_fct_settings".updated_at IS
    'Last update timestamp (UTC). Set by trigger in later migrations; '
    'defaults to creation time at insert.';

GRANT SELECT ON "00_schema_migrations"."10_fct_settings" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE, DELETE ON "00_schema_migrations"."10_fct_settings" TO tennetctl_write;

-- DOWN =======================================================================

DROP TABLE IF EXISTS "00_schema_migrations"."10_fct_settings";
DROP TABLE IF EXISTS "00_schema_migrations"."system_meta";
DROP TABLE IF EXISTS "00_schema_migrations"."applied_migrations";
DROP SCHEMA IF EXISTS "00_schema_migrations";
