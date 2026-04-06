-- =============================================================================
-- Migration: 20260404_016_multi_tenant_scoping.sql
-- Sub-feature: 01_org (core infrastructure)
-- Description: Multi-tenant scoping model — dim_scope_types, scope columns on
--   all scoped entities, fct_projects (org-scoped), dim_org_types, backfill.
-- UP
-- =============================================================================

SET search_path TO "02_iam", public;

-- ---------------------------------------------------------------------------
-- Dimension: scope types
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."dim_scope_types" (
    id          SMALLINT    NOT NULL,
    code        TEXT        NOT NULL,
    label       TEXT        NOT NULL,
    description TEXT,

    CONSTRAINT pk_dim_scope_types PRIMARY KEY (id),
    CONSTRAINT uq_dim_scope_types_code UNIQUE (code)
);
COMMENT ON TABLE "02_iam"."dim_scope_types" IS 'Hierarchy scope levels: platform → org → project.';

INSERT INTO "02_iam"."dim_scope_types" (id, code, label, description) VALUES
    (1, 'platform', 'Platform', 'Super admin managed. Inherited by all orgs.'),
    (2, 'org',      'Organisation', 'Org admin managed. Visible to org members only.'),
    (3, 'project',  'Project', 'Project-scoped within an org.');

-- ---------------------------------------------------------------------------
-- Dimension: org types (B2B customer, partner, internal, trial, sandbox)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."dim_org_types" (
    id          SMALLINT    NOT NULL,
    code        TEXT        NOT NULL,
    label       TEXT        NOT NULL,
    description TEXT,
    deprecated_at TIMESTAMP,

    CONSTRAINT pk_dim_org_types PRIMARY KEY (id),
    CONSTRAINT uq_dim_org_types_code UNIQUE (code)
);
COMMENT ON TABLE "02_iam"."dim_org_types" IS 'Classification of organisations. Affects license auto-assignment and available features.';

INSERT INTO "02_iam"."dim_org_types" (id, code, label, description) VALUES
    (1, 'customer',  'Customer',  'Paying B2B customer'),
    (2, 'trial',     'Trial',     'Free trial — converts to customer or expires'),
    (3, 'partner',   'Partner',   'Integration or reseller partner'),
    (4, 'internal',  'Internal',  'Internal team or dogfooding org'),
    (5, 'sandbox',   'Sandbox',   'Test/demo org — can be wiped');

-- ---------------------------------------------------------------------------
-- Alter: fct_org_orgs — add org_type_id
-- ---------------------------------------------------------------------------
ALTER TABLE "02_iam"."01_fct_org_orgs"
    ADD COLUMN org_type_id SMALLINT NOT NULL DEFAULT 1;

ALTER TABLE "02_iam"."01_fct_org_orgs"
    ADD CONSTRAINT fk_fct_org_orgs_type FOREIGN KEY (org_type_id)
        REFERENCES "02_iam"."dim_org_types"(id);

COMMENT ON COLUMN "02_iam"."01_fct_org_orgs".org_type_id IS 'FK → dim_org_types. Determines feature availability and license defaults.';

-- ---------------------------------------------------------------------------
-- Fact: projects (org-scoped — what the org is building)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."62_fct_projects" (
    id              VARCHAR(36)  NOT NULL,
    org_id          VARCHAR(36)  NOT NULL,
    key             TEXT         NOT NULL,
    name            TEXT         NOT NULL,
    description     TEXT,
    is_active       BOOLEAN      NOT NULL DEFAULT true,
    is_test         BOOLEAN      NOT NULL DEFAULT false,
    deleted_at      TIMESTAMP,
    created_by      VARCHAR(36),
    updated_by      VARCHAR(36),
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_fct_projects PRIMARY KEY (id)
);
COMMENT ON TABLE "02_iam"."62_fct_projects" IS 'Org-scoped projects — what the org is building. Flags, envs, SDK tokens live under projects.';

CREATE UNIQUE INDEX idx_uq_fct_projects_key
    ON "02_iam"."62_fct_projects" (org_id, key)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_fct_projects_org ON "02_iam"."62_fct_projects" (org_id)
    WHERE deleted_at IS NULL;

CREATE TRIGGER trg_fct_projects_updated_at
    BEFORE UPDATE ON "02_iam"."62_fct_projects"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- View for projects
CREATE OR REPLACE VIEW "02_iam".v_projects AS
SELECT
    p.id, p.org_id, p.key, p.name, p.description,
    p.is_active, p.is_test,
    p.deleted_at, p.deleted_at IS NOT NULL AS is_deleted,
    p.created_by, p.updated_by, p.created_at, p.updated_at
FROM "02_iam"."62_fct_projects" p;

-- ---------------------------------------------------------------------------
-- Alter: fct_feature_flags — add scope columns
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS "02_iam".v_feature_flags;

ALTER TABLE "02_iam"."22_fct_feature_flags"
    ADD COLUMN scope_type_id SMALLINT NOT NULL DEFAULT 1,
    ADD COLUMN scope_id      VARCHAR(36);

ALTER TABLE "02_iam"."22_fct_feature_flags"
    ADD CONSTRAINT fk_fct_feature_flags_scope_type FOREIGN KEY (scope_type_id)
        REFERENCES "02_iam"."dim_scope_types"(id);

COMMENT ON COLUMN "02_iam"."22_fct_feature_flags".scope_type_id IS 'FK → dim_scope_types. 1=platform (all orgs), 2=org, 3=project.';
COMMENT ON COLUMN "02_iam"."22_fct_feature_flags".scope_id IS 'NULL for platform. org UUID for org-scoped. project UUID for project-scoped.';

-- Backfill: org_id set → org-scoped; org_id NULL → platform
UPDATE "02_iam"."22_fct_feature_flags"
SET scope_type_id = 2, scope_id = org_id
WHERE org_id IS NOT NULL;

-- Unique key per scope (platform keys globally unique, org keys unique within org)
DROP INDEX IF EXISTS "02_iam".idx_uq_fct_feature_flags_key;
CREATE UNIQUE INDEX idx_uq_fct_feature_flags_key_platform
    ON "02_iam"."22_fct_feature_flags" (key)
    WHERE scope_type_id = 1 AND deleted_at IS NULL;
CREATE UNIQUE INDEX idx_uq_fct_feature_flags_key_scoped
    ON "02_iam"."22_fct_feature_flags" (scope_type_id, scope_id, key)
    WHERE scope_type_id > 1 AND deleted_at IS NULL;

-- Recreate view with scope columns
CREATE OR REPLACE VIEW "02_iam".v_feature_flags AS
SELECT
    f.id, f.org_id, f.key, f.name, f.description,
    f.value_type_id,
    vt.code  AS value_type_code,
    vt.label AS value_type_label,
    f.default_value, f.rollout_percentage,
    f.is_active, f.is_test,
    f.scope_type_id,
    st.code  AS scope_type,
    st.label AS scope_type_label,
    f.scope_id,
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
    f.created_by, f.updated_by, f.created_at, f.updated_at
FROM "02_iam"."22_fct_feature_flags" f
LEFT JOIN "02_iam"."01_dim_flag_value_types" vt ON vt.id = f.value_type_id
LEFT JOIN "02_iam"."dim_scope_types" st ON st.id = f.scope_type_id
LEFT JOIN "02_iam"."05_dim_flag_lifecycle_states" ls ON ls.id = f.lifecycle_state_id
LEFT JOIN "02_iam"."06_dim_flag_access_modes" am ON am.id = f.access_mode_id
LEFT JOIN "02_iam"."52_fct_flag_projects" fp ON fp.id = f.project_id;

-- ---------------------------------------------------------------------------
-- Alter: fct_roles — add scope columns
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS "02_iam".v_roles;

ALTER TABLE "02_iam"."23_fct_roles"
    ADD COLUMN scope_type_id SMALLINT NOT NULL DEFAULT 1,
    ADD COLUMN scope_id      VARCHAR(36);

ALTER TABLE "02_iam"."23_fct_roles"
    ADD CONSTRAINT fk_fct_roles_scope_type FOREIGN KEY (scope_type_id)
        REFERENCES "02_iam"."dim_scope_types"(id);

-- Backfill: is_system=true → platform; org_id set → org
UPDATE "02_iam"."23_fct_roles"
SET scope_type_id = 2, scope_id = org_id
WHERE org_id IS NOT NULL AND is_system = false;

-- Unique key per scope
DROP INDEX IF EXISTS "02_iam".idx_uq_fct_roles_key;
CREATE UNIQUE INDEX idx_uq_fct_roles_key_platform
    ON "02_iam"."23_fct_roles" (key)
    WHERE scope_type_id = 1 AND deleted_at IS NULL;
CREATE UNIQUE INDEX idx_uq_fct_roles_key_scoped
    ON "02_iam"."23_fct_roles" (scope_type_id, scope_id, key)
    WHERE scope_type_id > 1 AND deleted_at IS NULL;

CREATE OR REPLACE VIEW "02_iam".v_roles AS
SELECT
    r.id, r.org_id, r.key, r.name, r.description,
    r.is_system, r.is_active,
    r.scope_type_id,
    st.code  AS scope_type,
    st.label AS scope_type_label,
    r.scope_id,
    r.deleted_at, r.deleted_at IS NOT NULL AS is_deleted,
    r.created_by, r.updated_by, r.created_at, r.updated_at,
    COALESCE(pc.cnt, 0) AS permission_count
FROM "02_iam"."23_fct_roles" r
LEFT JOIN "02_iam"."dim_scope_types" st ON st.id = r.scope_type_id
LEFT JOIN (
    SELECT role_id, COUNT(*) AS cnt
    FROM "02_iam"."33_lnk_role_permissions"
    GROUP BY role_id
) pc ON pc.role_id = r.id;

-- ---------------------------------------------------------------------------
-- Alter: fct_groups — add scope columns, make org_id nullable
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS "02_iam".v_groups;

ALTER TABLE "02_iam"."07_fct_groups"
    ALTER COLUMN org_id DROP NOT NULL,
    ADD COLUMN scope_type_id SMALLINT NOT NULL DEFAULT 2,
    ADD COLUMN scope_id      VARCHAR(36);

ALTER TABLE "02_iam"."07_fct_groups"
    ADD CONSTRAINT fk_fct_groups_scope_type FOREIGN KEY (scope_type_id)
        REFERENCES "02_iam"."dim_scope_types"(id);

-- Backfill: is_system=true → platform; else org-scoped
UPDATE "02_iam"."07_fct_groups"
SET scope_type_id = 1, scope_id = NULL
WHERE is_system = true;

UPDATE "02_iam"."07_fct_groups"
SET scope_id = org_id
WHERE scope_type_id = 2;

-- Unique slug per scope
DROP INDEX IF EXISTS "02_iam".idx_uq_07_fct_groups_slug;
CREATE UNIQUE INDEX idx_uq_fct_groups_slug_platform
    ON "02_iam"."07_fct_groups" (slug)
    WHERE scope_type_id = 1 AND deleted_at IS NULL;
CREATE UNIQUE INDEX idx_uq_fct_groups_slug_scoped
    ON "02_iam"."07_fct_groups" (scope_type_id, scope_id, slug)
    WHERE scope_type_id > 1 AND deleted_at IS NULL;

CREATE OR REPLACE VIEW "02_iam".v_groups AS
SELECT
    g.id, g.org_id, g.name, g.slug, g.description,
    g.is_system,
    g.scope_type_id,
    st.code  AS scope_type,
    st.label AS scope_type_label,
    g.scope_id,
    g.deleted_at, g.deleted_at IS NOT NULL AS is_deleted,
    g.created_at, g.updated_at
FROM "02_iam"."07_fct_groups" g
LEFT JOIN "02_iam"."dim_scope_types" st ON st.id = g.scope_type_id;

-- ---------------------------------------------------------------------------
-- Alter: fct_flag_segments — add scope columns
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS "02_iam".v_flag_segments;

ALTER TABLE "02_iam"."40_fct_flag_segments"
    ADD COLUMN scope_type_id SMALLINT NOT NULL DEFAULT 1,
    ADD COLUMN scope_id      VARCHAR(36);

ALTER TABLE "02_iam"."40_fct_flag_segments"
    ADD CONSTRAINT fk_fct_flag_segments_scope_type FOREIGN KEY (scope_type_id)
        REFERENCES "02_iam"."dim_scope_types"(id);

UPDATE "02_iam"."40_fct_flag_segments"
SET scope_type_id = 2, scope_id = org_id
WHERE org_id IS NOT NULL;

CREATE OR REPLACE VIEW "02_iam".v_flag_segments AS
SELECT
    s.id, s.org_id, s.name, s.description, s.match_type,
    s.is_active,
    s.scope_type_id,
    st.code  AS scope_type,
    s.scope_id,
    s.deleted_at, s.deleted_at IS NOT NULL AS is_deleted,
    s.created_by, s.updated_by, s.created_at, s.updated_at,
    COALESCE(c.cnt, 0) AS condition_count
FROM "02_iam"."40_fct_flag_segments" s
LEFT JOIN "02_iam"."dim_scope_types" st ON st.id = s.scope_type_id
LEFT JOIN (
    SELECT segment_id, COUNT(*) AS cnt
    FROM "02_iam"."41_lnk_segment_conditions"
    GROUP BY segment_id
) c ON c.segment_id = s.id;

-- ---------------------------------------------------------------------------
-- Add entity type for project
-- ---------------------------------------------------------------------------
INSERT INTO "02_iam"."01_dim_org_entity_types" (id, code, label, description) VALUES
    (13, 'project', 'Project', 'Org-scoped project')
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- DOWN
-- =============================================================================

DELETE FROM "02_iam"."01_dim_org_entity_types" WHERE id = 13;

-- Restore segments view
DROP VIEW IF EXISTS "02_iam".v_flag_segments;
ALTER TABLE "02_iam"."40_fct_flag_segments"
    DROP CONSTRAINT IF EXISTS fk_fct_flag_segments_scope_type,
    DROP COLUMN IF EXISTS scope_type_id,
    DROP COLUMN IF EXISTS scope_id;
CREATE OR REPLACE VIEW "02_iam".v_flag_segments AS
SELECT s.*, COALESCE(c.cnt, 0) AS condition_count, s.deleted_at IS NOT NULL AS is_deleted
FROM "02_iam"."40_fct_flag_segments" s
LEFT JOIN (SELECT segment_id, COUNT(*) cnt FROM "02_iam"."41_lnk_segment_conditions" GROUP BY segment_id) c ON c.segment_id = s.id;

-- Restore groups
DROP VIEW IF EXISTS "02_iam".v_groups;
ALTER TABLE "02_iam"."07_fct_groups"
    DROP CONSTRAINT IF EXISTS fk_fct_groups_scope_type,
    DROP COLUMN IF EXISTS scope_type_id,
    DROP COLUMN IF EXISTS scope_id;
ALTER TABLE "02_iam"."07_fct_groups" ALTER COLUMN org_id SET NOT NULL;
CREATE OR REPLACE VIEW "02_iam".v_groups AS
SELECT g.*, g.deleted_at IS NOT NULL AS is_deleted FROM "02_iam"."07_fct_groups" g;

-- Restore roles
DROP VIEW IF EXISTS "02_iam".v_roles;
ALTER TABLE "02_iam"."23_fct_roles"
    DROP CONSTRAINT IF EXISTS fk_fct_roles_scope_type,
    DROP COLUMN IF EXISTS scope_type_id,
    DROP COLUMN IF EXISTS scope_id;
CREATE OR REPLACE VIEW "02_iam".v_roles AS
SELECT r.*, r.deleted_at IS NOT NULL AS is_deleted,
    COALESCE(pc.cnt, 0) AS permission_count
FROM "02_iam"."23_fct_roles" r
LEFT JOIN (SELECT role_id, COUNT(*) cnt FROM "02_iam"."33_lnk_role_permissions" GROUP BY role_id) pc ON pc.role_id = r.id;

-- Restore feature flags
DROP VIEW IF EXISTS "02_iam".v_feature_flags;
ALTER TABLE "02_iam"."22_fct_feature_flags"
    DROP CONSTRAINT IF EXISTS fk_fct_feature_flags_scope_type,
    DROP COLUMN IF EXISTS scope_type_id,
    DROP COLUMN IF EXISTS scope_id;

-- Restore orgs
ALTER TABLE "02_iam"."01_fct_org_orgs"
    DROP CONSTRAINT IF EXISTS fk_fct_org_orgs_type,
    DROP COLUMN IF EXISTS org_type_id;

DROP VIEW IF EXISTS "02_iam".v_projects;
DROP TABLE IF EXISTS "02_iam"."62_fct_projects" CASCADE;
DROP TABLE IF EXISTS "02_iam"."dim_org_types" CASCADE;
DROP TABLE IF EXISTS "02_iam"."dim_scope_types" CASCADE;
