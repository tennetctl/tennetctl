-- =============================================================================
-- Migration: 20260404_013_feature_flag_enhancements.sql
-- Sub-feature: 24_feature_flag
-- Description: PostHog/Unleash/LaunchDarkly parity — lifecycle states, flag
--              projects, owner, kill switch, change history, EAV attrs,
--              flag-scoped permissions, SDK tokens, webhooks.
-- UP
-- =============================================================================

SET search_path TO "02_iam", public;

-- ---------------------------------------------------------------------------
-- Dimension: flag lifecycle states
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."05_dim_flag_lifecycle_states" (
    id          SMALLINT    NOT NULL,
    code        TEXT        NOT NULL,
    label       TEXT        NOT NULL,
    description TEXT,
    sort_order  SMALLINT    NOT NULL DEFAULT 0,
    deprecated_at TIMESTAMP,

    CONSTRAINT pk_dim_flag_lifecycle_states PRIMARY KEY (id),
    CONSTRAINT uq_dim_flag_lifecycle_states_code UNIQUE (code)
);
COMMENT ON TABLE "02_iam"."05_dim_flag_lifecycle_states" IS 'Flag lifecycle: draft → active → deprecated → archived.';

INSERT INTO "02_iam"."05_dim_flag_lifecycle_states" (id, code, label, description, sort_order) VALUES
    (1, 'draft',      'Draft',      'Not yet serving. Safe to experiment.', 1),
    (2, 'active',     'Active',     'Serving in evaluation. Production-ready.', 2),
    (3, 'deprecated', 'Deprecated', 'Marked for removal. Still serving but generates warnings.', 3),
    (4, 'archived',   'Archived',   'No longer serving. Preserved for history.', 4);

-- ---------------------------------------------------------------------------
-- Dimension: flag access modes
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."06_dim_flag_access_modes" (
    id          SMALLINT    NOT NULL,
    code        TEXT        NOT NULL,
    label       TEXT        NOT NULL,
    deprecated_at TIMESTAMP,

    CONSTRAINT pk_dim_flag_access_modes PRIMARY KEY (id),
    CONSTRAINT uq_dim_flag_access_modes_code UNIQUE (code)
);
COMMENT ON TABLE "02_iam"."06_dim_flag_access_modes" IS 'Who can see/use the flag: public (SDK), private (server-side only), internal.';

INSERT INTO "02_iam"."06_dim_flag_access_modes" (id, code, label) VALUES
    (1, 'public',   'Public — visible to client SDKs'),
    (2, 'private',  'Private — server-side SDKs only'),
    (3, 'internal', 'Internal — platform team only');

-- ---------------------------------------------------------------------------
-- Fact: flag projects (namespace isolation)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."52_fct_flag_projects" (
    id          VARCHAR(36)  NOT NULL,
    org_id      VARCHAR(36),
    key         TEXT         NOT NULL,
    name        TEXT         NOT NULL,
    description TEXT,
    is_active   BOOLEAN      NOT NULL DEFAULT true,
    is_test     BOOLEAN      NOT NULL DEFAULT false,
    deleted_at  TIMESTAMP,
    created_by  VARCHAR(36),
    updated_by  VARCHAR(36),
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_fct_flag_projects PRIMARY KEY (id)
);
COMMENT ON TABLE "02_iam"."52_fct_flag_projects" IS 'Flag project namespaces. Flags belong to a project for team isolation.';

CREATE UNIQUE INDEX idx_uq_fct_flag_projects_key
    ON "02_iam"."52_fct_flag_projects" (key)
    WHERE deleted_at IS NULL;

CREATE TRIGGER trg_fct_flag_projects_updated_at
    BEFORE UPDATE ON "02_iam"."52_fct_flag_projects"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- Seed default project
INSERT INTO "02_iam"."52_fct_flag_projects" (id, key, name, description) VALUES
    ('00000000-0000-0000-0000-000000000200', 'default', 'Default', 'Default flag project');

-- ---------------------------------------------------------------------------
-- Fact: SDK tokens (server-side vs client-side, per-project per-env)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."53_fct_flag_sdk_tokens" (
    id              VARCHAR(36)  NOT NULL,
    project_id      VARCHAR(36)  NOT NULL,
    env_id          SMALLINT     NOT NULL,
    name            TEXT         NOT NULL,
    token_hash      TEXT         NOT NULL,
    token_prefix    VARCHAR(12)  NOT NULL,
    token_type      TEXT         NOT NULL DEFAULT 'server',
    expires_at      TIMESTAMP,
    last_used_at    TIMESTAMP,
    is_active       BOOLEAN      NOT NULL DEFAULT true,
    created_by      VARCHAR(36),
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_fct_flag_sdk_tokens PRIMARY KEY (id),
    CONSTRAINT fk_fct_flag_sdk_tokens_project FOREIGN KEY (project_id)
        REFERENCES "02_iam"."52_fct_flag_projects"(id) ON DELETE CASCADE,
    CONSTRAINT fk_fct_flag_sdk_tokens_env FOREIGN KEY (env_id)
        REFERENCES "02_iam"."03_dim_environments"(id),
    CONSTRAINT chk_fct_flag_sdk_tokens_type CHECK (token_type IN ('server', 'client', 'mobile'))
);
COMMENT ON TABLE "02_iam"."53_fct_flag_sdk_tokens" IS 'SDK tokens for flag evaluation. SHA-256 hash stored, raw returned once on create.';
COMMENT ON COLUMN "02_iam"."53_fct_flag_sdk_tokens".token_hash IS 'SHA-256(raw_token). Raw is only shown once at creation.';
COMMENT ON COLUMN "02_iam"."53_fct_flag_sdk_tokens".token_prefix IS 'First 8 chars of raw token for identification.';

CREATE INDEX idx_fct_flag_sdk_tokens_hash ON "02_iam"."53_fct_flag_sdk_tokens" (token_hash) WHERE is_active = true;

-- ---------------------------------------------------------------------------
-- Alter: add lifecycle, owner, project, kill switch to fct_feature_flags
-- ---------------------------------------------------------------------------

-- Drop the view first (depends on the table)
DROP VIEW IF EXISTS "02_iam".v_feature_flags;

ALTER TABLE "02_iam"."22_fct_feature_flags"
    ADD COLUMN lifecycle_state_id SMALLINT NOT NULL DEFAULT 2,
    ADD COLUMN access_mode_id     SMALLINT NOT NULL DEFAULT 1,
    ADD COLUMN project_id         VARCHAR(36) DEFAULT '00000000-0000-0000-0000-000000000200',
    ADD COLUMN owner_id           VARCHAR(36),
    ADD COLUMN is_kill_switch     BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN permanently_on     BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE "02_iam"."22_fct_feature_flags"
    ADD CONSTRAINT fk_fct_feature_flags_lifecycle FOREIGN KEY (lifecycle_state_id)
        REFERENCES "02_iam"."05_dim_flag_lifecycle_states"(id),
    ADD CONSTRAINT fk_fct_feature_flags_access_mode FOREIGN KEY (access_mode_id)
        REFERENCES "02_iam"."06_dim_flag_access_modes"(id),
    ADD CONSTRAINT fk_fct_feature_flags_project FOREIGN KEY (project_id)
        REFERENCES "02_iam"."52_fct_flag_projects"(id);

COMMENT ON COLUMN "02_iam"."22_fct_feature_flags".lifecycle_state_id IS 'FK → dim_flag_lifecycle_states. Controls evaluation behaviour.';
COMMENT ON COLUMN "02_iam"."22_fct_feature_flags".access_mode_id IS 'FK → dim_flag_access_modes. Controls SDK visibility.';
COMMENT ON COLUMN "02_iam"."22_fct_feature_flags".project_id IS 'FK → fct_flag_projects. Namespace isolation.';
COMMENT ON COLUMN "02_iam"."22_fct_feature_flags".owner_id IS 'User who owns this flag. Receives stale notifications.';
COMMENT ON COLUMN "02_iam"."22_fct_feature_flags".is_kill_switch IS 'Emergency disable — bypasses all rules, returns default.';
COMMENT ON COLUMN "02_iam"."22_fct_feature_flags".permanently_on IS 'Flag is permanently enabled — skip evaluation, always returns default_value as true.';

CREATE INDEX idx_fct_feature_flags_project ON "02_iam"."22_fct_feature_flags" (project_id)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_fct_feature_flags_owner ON "02_iam"."22_fct_feature_flags" (owner_id)
    WHERE deleted_at IS NULL;

-- Recreate view with new columns
CREATE OR REPLACE VIEW "02_iam".v_feature_flags AS
SELECT
    f.id,
    f.org_id,
    f.key,
    f.name,
    f.description,
    f.value_type_id,
    vt.code  AS value_type_code,
    vt.label AS value_type_label,
    f.default_value,
    f.rollout_percentage,
    f.is_active,
    f.is_test,
    f.lifecycle_state_id,
    ls.code  AS lifecycle_state,
    ls.label AS lifecycle_state_label,
    f.access_mode_id,
    am.code  AS access_mode,
    am.label AS access_mode_label,
    f.project_id,
    fp.key   AS project_key,
    fp.name  AS project_name,
    f.owner_id,
    f.is_kill_switch,
    f.permanently_on,
    f.deleted_at,
    f.deleted_at IS NOT NULL AS is_deleted,
    f.created_by,
    f.updated_by,
    f.created_at,
    f.updated_at
FROM "02_iam"."22_fct_feature_flags" f
LEFT JOIN "02_iam"."01_dim_flag_value_types" vt ON vt.id = f.value_type_id
LEFT JOIN "02_iam"."05_dim_flag_lifecycle_states" ls ON ls.id = f.lifecycle_state_id
LEFT JOIN "02_iam"."06_dim_flag_access_modes" am ON am.id = f.access_mode_id
LEFT JOIN "02_iam"."52_fct_flag_projects" fp ON fp.id = f.project_id;

-- ---------------------------------------------------------------------------
-- Fact: flag change history (detailed diffs)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."54_fct_flag_change_history" (
    id              VARCHAR(36)  NOT NULL,
    flag_id         VARCHAR(36)  NOT NULL,
    change_type     TEXT         NOT NULL,
    field_name      TEXT,
    old_value       JSONB,
    new_value       JSONB,
    changed_by      VARCHAR(36),
    change_reason   TEXT,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_fct_flag_change_history PRIMARY KEY (id),
    CONSTRAINT fk_fct_flag_change_history_flag FOREIGN KEY (flag_id)
        REFERENCES "02_iam"."22_fct_feature_flags"(id) ON DELETE CASCADE,
    CONSTRAINT chk_fct_flag_change_history_type CHECK (
        change_type IN ('created', 'updated', 'deleted', 'activated', 'deactivated',
                        'kill_switched', 'lifecycle_changed', 'rule_added', 'rule_removed',
                        'variant_added', 'variant_removed', 'env_config_changed',
                        'override_set', 'override_removed', 'target_added', 'target_removed',
                        'prerequisite_added', 'prerequisite_removed', 'promoted')
    )
);
COMMENT ON TABLE "02_iam"."54_fct_flag_change_history" IS 'Detailed change log per flag with old/new value diffs.';

CREATE INDEX idx_fct_flag_change_history_flag ON "02_iam"."54_fct_flag_change_history" (flag_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Link: flag-scoped permissions (per-project, per-env RBAC)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."55_lnk_flag_project_members" (
    id              VARCHAR(36)  NOT NULL,
    project_id      VARCHAR(36)  NOT NULL,
    user_id         VARCHAR(36)  NOT NULL,
    role            TEXT         NOT NULL DEFAULT 'viewer',
    created_by      VARCHAR(36),
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_lnk_flag_project_members PRIMARY KEY (id),
    CONSTRAINT fk_lnk_flag_project_members_project FOREIGN KEY (project_id)
        REFERENCES "02_iam"."52_fct_flag_projects"(id) ON DELETE CASCADE,
    CONSTRAINT uq_lnk_flag_project_members UNIQUE (project_id, user_id),
    CONSTRAINT chk_lnk_flag_project_members_role CHECK (role IN ('admin', 'editor', 'viewer'))
);
COMMENT ON TABLE "02_iam"."55_lnk_flag_project_members" IS 'Per-project flag access. admin=full, editor=toggle+rules, viewer=read-only.';

-- ---------------------------------------------------------------------------
-- Fact: flag webhooks (outbound HTTP on flag changes)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."56_fct_flag_webhooks" (
    id              VARCHAR(36)  NOT NULL,
    project_id      VARCHAR(36)  NOT NULL,
    url             TEXT         NOT NULL,
    secret          TEXT,
    events          TEXT[]       NOT NULL DEFAULT '{}',
    is_active       BOOLEAN      NOT NULL DEFAULT true,
    deleted_at      TIMESTAMP,
    created_by      VARCHAR(36),
    updated_by      VARCHAR(36),
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_fct_flag_webhooks PRIMARY KEY (id),
    CONSTRAINT fk_fct_flag_webhooks_project FOREIGN KEY (project_id)
        REFERENCES "02_iam"."52_fct_flag_projects"(id) ON DELETE CASCADE
);
COMMENT ON TABLE "02_iam"."56_fct_flag_webhooks" IS 'Outbound webhooks triggered on flag changes.';
COMMENT ON COLUMN "02_iam"."56_fct_flag_webhooks".events IS 'Array of event types to subscribe to (e.g. flag.updated, flag.toggled).';
COMMENT ON COLUMN "02_iam"."56_fct_flag_webhooks".secret IS 'HMAC-SHA256 signing secret for payload verification.';

CREATE TRIGGER trg_fct_flag_webhooks_updated_at
    BEFORE UPDATE ON "02_iam"."56_fct_flag_webhooks"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- ---------------------------------------------------------------------------
-- Add flag-specific RBAC permissions
-- ---------------------------------------------------------------------------
INSERT INTO "02_iam"."26_fct_permissions" (id, resource, action, description, is_system) VALUES
    ('00000000-0000-0000-0000-000000000126', 'flag',         'toggle',  'Toggle feature flags on/off', true),
    ('00000000-0000-0000-0000-000000000127', 'flag',         'evaluate','Evaluate feature flags via SDK', true),
    ('00000000-0000-0000-0000-000000000128', 'flag-project', 'create',  'Create flag projects', true),
    ('00000000-0000-0000-0000-000000000129', 'flag-project', 'read',    'View flag projects', true),
    ('00000000-0000-0000-0000-000000000130', 'flag-project', 'update',  'Update flag projects', true),
    ('00000000-0000-0000-0000-000000000131', 'flag-project', 'delete',  'Delete flag projects', true),
    ('00000000-0000-0000-0000-000000000132', 'flag-token',   'create',  'Create SDK tokens', true),
    ('00000000-0000-0000-0000-000000000133', 'flag-token',   'read',    'View SDK tokens', true),
    ('00000000-0000-0000-0000-000000000134', 'flag-token',   'delete',  'Revoke SDK tokens', true),
    ('00000000-0000-0000-0000-000000000135', 'flag',         'promote', 'Promote flag config across environments', true),
    ('00000000-0000-0000-0000-000000000136', 'flag-webhook',  'create', 'Create flag webhooks', true),
    ('00000000-0000-0000-0000-000000000137', 'flag-webhook',  'read',   'View flag webhooks', true),
    ('00000000-0000-0000-0000-000000000138', 'flag-webhook',  'delete', 'Delete flag webhooks', true);

-- =============================================================================
-- DOWN
-- =============================================================================

DELETE FROM "02_iam"."26_fct_permissions" WHERE id IN (
    '00000000-0000-0000-0000-000000000126', '00000000-0000-0000-0000-000000000127',
    '00000000-0000-0000-0000-000000000128', '00000000-0000-0000-0000-000000000129',
    '00000000-0000-0000-0000-000000000130', '00000000-0000-0000-0000-000000000131',
    '00000000-0000-0000-0000-000000000132', '00000000-0000-0000-0000-000000000133',
    '00000000-0000-0000-0000-000000000134', '00000000-0000-0000-0000-000000000135',
    '00000000-0000-0000-0000-000000000136', '00000000-0000-0000-0000-000000000137',
    '00000000-0000-0000-0000-000000000138'
);
DROP TABLE IF EXISTS "02_iam"."56_fct_flag_webhooks" CASCADE;
DROP TABLE IF EXISTS "02_iam"."55_lnk_flag_project_members" CASCADE;
DROP TABLE IF EXISTS "02_iam"."54_fct_flag_change_history" CASCADE;
DROP TABLE IF EXISTS "02_iam"."53_fct_flag_sdk_tokens" CASCADE;

-- Restore original view
DROP VIEW IF EXISTS "02_iam".v_feature_flags;
ALTER TABLE "02_iam"."22_fct_feature_flags"
    DROP COLUMN IF EXISTS lifecycle_state_id,
    DROP COLUMN IF EXISTS access_mode_id,
    DROP COLUMN IF EXISTS project_id,
    DROP COLUMN IF EXISTS owner_id,
    DROP COLUMN IF EXISTS is_kill_switch,
    DROP COLUMN IF EXISTS permanently_on;

CREATE OR REPLACE VIEW "02_iam".v_feature_flags AS
SELECT f.id, f.org_id, f.key, f.name, f.description,
    f.value_type_id, vt.code AS value_type_code, vt.label AS value_type_label,
    f.default_value, f.rollout_percentage, f.is_active, f.is_test,
    f.deleted_at, f.deleted_at IS NOT NULL AS is_deleted,
    f.created_by, f.updated_by, f.created_at, f.updated_at
FROM "02_iam"."22_fct_feature_flags" f
LEFT JOIN "02_iam"."01_dim_flag_value_types" vt ON vt.id = f.value_type_id;

DROP TABLE IF EXISTS "02_iam"."52_fct_flag_projects" CASCADE;
DROP TABLE IF EXISTS "02_iam"."06_dim_flag_access_modes" CASCADE;
DROP TABLE IF EXISTS "02_iam"."05_dim_flag_lifecycle_states" CASCADE;
