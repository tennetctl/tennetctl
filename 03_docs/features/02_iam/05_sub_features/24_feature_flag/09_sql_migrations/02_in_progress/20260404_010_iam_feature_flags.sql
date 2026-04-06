-- =============================================================================
-- Migration: 20260404_010_iam_feature_flags.sql
-- Description: Feature flags — core flags, segments, rules, variants, env configs,
--              overrides, identity targets, prerequisites, eval counts, tags
-- UP
-- =============================================================================

SET search_path TO "02_iam", public;

-- ---------------------------------------------------------------------------
-- Dimension: flag value types (bool, int, string, json)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."01_dim_flag_value_types" (
    id          SMALLINT    NOT NULL,
    code        TEXT        NOT NULL,
    label       TEXT        NOT NULL,
    description TEXT,
    deprecated_at TIMESTAMP,

    CONSTRAINT pk_dim_flag_value_types PRIMARY KEY (id),
    CONSTRAINT uq_dim_flag_value_types_code UNIQUE (code)
);
COMMENT ON TABLE "02_iam"."01_dim_flag_value_types" IS 'Lookup: data type of a feature flag value.';

INSERT INTO "02_iam"."01_dim_flag_value_types" (id, code, label) VALUES
    (1, 'boolean', 'Boolean'),
    (2, 'integer', 'Integer'),
    (3, 'string',  'String'),
    (4, 'json',    'JSON');

-- ---------------------------------------------------------------------------
-- Dimension: rule operators (22 comparison operators)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."02_dim_rule_operators" (
    id          SMALLINT    NOT NULL,
    code        TEXT        NOT NULL,
    label       TEXT        NOT NULL,
    description TEXT,
    deprecated_at TIMESTAMP,

    CONSTRAINT pk_dim_rule_operators PRIMARY KEY (id),
    CONSTRAINT uq_dim_rule_operators_code UNIQUE (code)
);
COMMENT ON TABLE "02_iam"."02_dim_rule_operators" IS 'Lookup: comparison operators for segment conditions and targeting rules.';

INSERT INTO "02_iam"."02_dim_rule_operators" (id, code, label) VALUES
    (1,  'eq',            'Equals'),
    (2,  'neq',           'Not equals'),
    (3,  'contains',      'Contains'),
    (4,  'not_contains',  'Does not contain'),
    (5,  'in',            'In list'),
    (6,  'not_in',        'Not in list'),
    (7,  'gt',            'Greater than'),
    (8,  'lt',            'Less than'),
    (9,  'gte',           'Greater or equal'),
    (10, 'lte',           'Less or equal'),
    (11, 'matches_regex', 'Matches regex'),
    (12, 'exists',        'Exists'),
    (13, 'not_exists',    'Does not exist'),
    (14, 'starts_with',   'Starts with'),
    (15, 'ends_with',     'Ends with'),
    (16, 'is_true',       'Is true'),
    (17, 'is_false',      'Is false'),
    (18, 'semver_eq',     'Semver equals'),
    (19, 'semver_gt',     'Semver greater than'),
    (20, 'semver_gte',    'Semver greater or equal'),
    (21, 'semver_lt',     'Semver less than'),
    (22, 'semver_lte',    'Semver less or equal');

-- ---------------------------------------------------------------------------
-- Dimension: environments (dev, staging, prod)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."03_dim_environments" (
    id          SMALLINT    NOT NULL,
    code        TEXT        NOT NULL,
    label       TEXT        NOT NULL,
    color       TEXT        NOT NULL DEFAULT '#6b7280',
    sort_order  SMALLINT    NOT NULL DEFAULT 0,
    deprecated_at TIMESTAMP,

    CONSTRAINT pk_dim_environments PRIMARY KEY (id),
    CONSTRAINT uq_dim_environments_code UNIQUE (code)
);
COMMENT ON TABLE "02_iam"."03_dim_environments" IS 'Lookup: deployment environments for feature flag targeting.';

INSERT INTO "02_iam"."03_dim_environments" (id, code, label, color, sort_order) VALUES
    (1, 'development', 'Development', '#22c55e', 1),
    (2, 'staging',     'Staging',     '#f59e0b', 2),
    (3, 'production',  'Production',  '#ef4444', 3);

-- ---------------------------------------------------------------------------
-- Dimension: target types (user, org, group)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."04_dim_target_types" (
    id          SMALLINT    NOT NULL,
    code        TEXT        NOT NULL,
    label       TEXT        NOT NULL,
    deprecated_at TIMESTAMP,

    CONSTRAINT pk_dim_target_types PRIMARY KEY (id),
    CONSTRAINT uq_dim_target_types_code UNIQUE (code)
);
COMMENT ON TABLE "02_iam"."04_dim_target_types" IS 'Lookup: entity types that can be individually targeted by a flag rule.';

INSERT INTO "02_iam"."04_dim_target_types" (id, code, label) VALUES
    (1, 'user',  'User'),
    (2, 'org',   'Organisation'),
    (3, 'group', 'Group');

-- ---------------------------------------------------------------------------
-- Fact: feature flags (core identity)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."22_fct_feature_flags" (
    id                  VARCHAR(36)  NOT NULL,
    org_id              VARCHAR(36),
    key                 TEXT         NOT NULL,
    name                TEXT         NOT NULL,
    description         TEXT,
    value_type_id       SMALLINT     NOT NULL DEFAULT 1,
    default_value       JSONB        NOT NULL DEFAULT 'true'::jsonb,
    rollout_percentage  SMALLINT     NOT NULL DEFAULT 100,
    is_active           BOOLEAN      NOT NULL DEFAULT true,
    is_test             BOOLEAN      NOT NULL DEFAULT false,
    deleted_at          TIMESTAMP,
    created_by          VARCHAR(36),
    updated_by          VARCHAR(36),
    created_at          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_fct_feature_flags PRIMARY KEY (id),
    CONSTRAINT fk_fct_feature_flags_value_type FOREIGN KEY (value_type_id)
        REFERENCES "02_iam"."01_dim_flag_value_types"(id),
    CONSTRAINT chk_fct_feature_flags_rollout CHECK (rollout_percentage BETWEEN 0 AND 100)
);
COMMENT ON TABLE "02_iam"."22_fct_feature_flags" IS 'Feature flag identity. One row per flag. Soft-deleted via deleted_at.';
COMMENT ON COLUMN "02_iam"."22_fct_feature_flags".key IS 'Unique slug used in SDK evaluation calls. URL-safe.';
COMMENT ON COLUMN "02_iam"."22_fct_feature_flags".default_value IS 'JSONB default returned when no rules match. Type must match value_type_id.';
COMMENT ON COLUMN "02_iam"."22_fct_feature_flags".rollout_percentage IS 'Global rollout gate (0-100). Applied after all rules are evaluated.';

CREATE UNIQUE INDEX idx_uq_fct_feature_flags_key
    ON "02_iam"."22_fct_feature_flags" (key)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_fct_feature_flags_org ON "02_iam"."22_fct_feature_flags" (org_id)
    WHERE deleted_at IS NULL;

CREATE TRIGGER trg_fct_feature_flags_updated_at
    BEFORE UPDATE ON "02_iam"."22_fct_feature_flags"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- ---------------------------------------------------------------------------
-- View: feature flags (resolves value type)
-- ---------------------------------------------------------------------------
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
    f.deleted_at,
    f.deleted_at IS NOT NULL AS is_deleted,
    f.created_by,
    f.updated_by,
    f.created_at,
    f.updated_at
FROM "02_iam"."22_fct_feature_flags" f
LEFT JOIN "02_iam"."01_dim_flag_value_types" vt ON vt.id = f.value_type_id;

-- ---------------------------------------------------------------------------
-- Fact: segments (reusable audience groups)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."40_fct_flag_segments" (
    id          VARCHAR(36)  NOT NULL,
    org_id      VARCHAR(36),
    name        TEXT         NOT NULL,
    description TEXT,
    match_type  TEXT         NOT NULL DEFAULT 'all',
    is_active   BOOLEAN      NOT NULL DEFAULT true,
    is_test     BOOLEAN      NOT NULL DEFAULT false,
    deleted_at  TIMESTAMP,
    created_by  VARCHAR(36),
    updated_by  VARCHAR(36),
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_fct_flag_segments PRIMARY KEY (id),
    CONSTRAINT chk_fct_flag_segments_match CHECK (match_type IN ('all', 'any'))
);
COMMENT ON TABLE "02_iam"."40_fct_flag_segments" IS 'Reusable audience segment. Conditions are AND (all) or OR (any) joined.';
COMMENT ON COLUMN "02_iam"."40_fct_flag_segments".match_type IS '''all'' = AND all conditions, ''any'' = OR any condition.';

CREATE INDEX idx_fct_flag_segments_org ON "02_iam"."40_fct_flag_segments" (org_id)
    WHERE deleted_at IS NULL;

CREATE TRIGGER trg_fct_flag_segments_updated_at
    BEFORE UPDATE ON "02_iam"."40_fct_flag_segments"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- ---------------------------------------------------------------------------
-- Link: segment conditions
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."41_lnk_segment_conditions" (
    id          VARCHAR(36)  NOT NULL,
    segment_id  VARCHAR(36)  NOT NULL,
    attr_key    TEXT         NOT NULL,
    operator_id SMALLINT     NOT NULL,
    attr_value  JSONB        NOT NULL DEFAULT 'null'::jsonb,
    created_by  VARCHAR(36),
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_lnk_segment_conditions PRIMARY KEY (id),
    CONSTRAINT fk_lnk_segment_conditions_segment FOREIGN KEY (segment_id)
        REFERENCES "02_iam"."40_fct_flag_segments"(id) ON DELETE CASCADE,
    CONSTRAINT fk_lnk_segment_conditions_operator FOREIGN KEY (operator_id)
        REFERENCES "02_iam"."02_dim_rule_operators"(id)
);
COMMENT ON TABLE "02_iam"."41_lnk_segment_conditions" IS 'Individual conditions within a segment. Hard-deleted when removed.';

CREATE INDEX idx_lnk_segment_conditions_segment ON "02_iam"."41_lnk_segment_conditions" (segment_id);

-- ---------------------------------------------------------------------------
-- View: segments with condition count
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW "02_iam".v_flag_segments AS
SELECT
    s.id,
    s.org_id,
    s.name,
    s.description,
    s.match_type,
    s.is_active,
    s.deleted_at,
    s.deleted_at IS NOT NULL AS is_deleted,
    s.created_by,
    s.updated_by,
    s.created_at,
    s.updated_at,
    COALESCE(c.cnt, 0) AS condition_count
FROM "02_iam"."40_fct_flag_segments" s
LEFT JOIN (
    SELECT segment_id, COUNT(*) AS cnt
    FROM "02_iam"."41_lnk_segment_conditions"
    GROUP BY segment_id
) c ON c.segment_id = s.id;

-- ---------------------------------------------------------------------------
-- Link: flag targeting rules
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."42_lnk_flag_rules" (
    id                  VARCHAR(36)  NOT NULL,
    flag_id             VARCHAR(36)  NOT NULL,
    segment_id          VARCHAR(36),
    priority            INT          NOT NULL DEFAULT 0,
    rollout_percentage  SMALLINT     NOT NULL DEFAULT 100,
    return_value        JSONB        NOT NULL DEFAULT 'true'::jsonb,
    description         TEXT,
    is_active           BOOLEAN      NOT NULL DEFAULT true,
    scheduled_on        TIMESTAMP,
    scheduled_off       TIMESTAMP,
    created_by          VARCHAR(36),
    created_at          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_lnk_flag_rules PRIMARY KEY (id),
    CONSTRAINT fk_lnk_flag_rules_flag FOREIGN KEY (flag_id)
        REFERENCES "02_iam"."22_fct_feature_flags"(id) ON DELETE CASCADE,
    CONSTRAINT fk_lnk_flag_rules_segment FOREIGN KEY (segment_id)
        REFERENCES "02_iam"."40_fct_flag_segments"(id),
    CONSTRAINT chk_lnk_flag_rules_rollout CHECK (rollout_percentage BETWEEN 0 AND 100)
);
COMMENT ON TABLE "02_iam"."42_lnk_flag_rules" IS 'Targeting rules per flag. Evaluated in priority order (ASC). First match wins.';
COMMENT ON COLUMN "02_iam"."42_lnk_flag_rules".segment_id IS 'NULL = universal rule (matches all traffic).';
COMMENT ON COLUMN "02_iam"."42_lnk_flag_rules".scheduled_on IS 'Rule activates at this time. NULL = immediately active.';
COMMENT ON COLUMN "02_iam"."42_lnk_flag_rules".scheduled_off IS 'Rule deactivates at this time. NULL = never expires.';

CREATE INDEX idx_lnk_flag_rules_flag ON "02_iam"."42_lnk_flag_rules" (flag_id, priority);

-- ---------------------------------------------------------------------------
-- View: flag rules (resolves segment name)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW "02_iam".v_flag_rules AS
SELECT
    r.id,
    r.flag_id,
    r.segment_id,
    s.name AS segment_name,
    s.match_type AS segment_match_type,
    r.priority,
    r.rollout_percentage,
    r.return_value,
    r.description,
    r.is_active,
    r.scheduled_on,
    r.scheduled_off,
    r.created_by,
    r.created_at
FROM "02_iam"."42_lnk_flag_rules" r
LEFT JOIN "02_iam"."40_fct_flag_segments" s ON s.id = r.segment_id;

-- ---------------------------------------------------------------------------
-- Fact: flag tags
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."43_fct_flag_tags" (
    id          VARCHAR(36)  NOT NULL,
    name        TEXT         NOT NULL,
    color       TEXT         NOT NULL DEFAULT '#6b7280',
    description TEXT,
    deleted_at  TIMESTAMP,
    created_by  VARCHAR(36),
    updated_by  VARCHAR(36),
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_fct_flag_tags PRIMARY KEY (id)
);
COMMENT ON TABLE "02_iam"."43_fct_flag_tags" IS 'Named tags for organising feature flags.';

CREATE UNIQUE INDEX idx_uq_fct_flag_tags_name
    ON "02_iam"."43_fct_flag_tags" (name)
    WHERE deleted_at IS NULL;

CREATE TRIGGER trg_fct_flag_tags_updated_at
    BEFORE UPDATE ON "02_iam"."43_fct_flag_tags"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- ---------------------------------------------------------------------------
-- Link: flag ↔ tag assignments
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."44_lnk_flag_tag_assignments" (
    id          VARCHAR(36)  NOT NULL,
    flag_id     VARCHAR(36)  NOT NULL,
    tag_id      VARCHAR(36)  NOT NULL,
    created_by  VARCHAR(36),
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_lnk_flag_tag_assignments PRIMARY KEY (id),
    CONSTRAINT fk_lnk_flag_tag_assignments_flag FOREIGN KEY (flag_id)
        REFERENCES "02_iam"."22_fct_feature_flags"(id) ON DELETE CASCADE,
    CONSTRAINT fk_lnk_flag_tag_assignments_tag FOREIGN KEY (tag_id)
        REFERENCES "02_iam"."43_fct_flag_tags"(id) ON DELETE CASCADE,
    CONSTRAINT uq_lnk_flag_tag_assignments UNIQUE (flag_id, tag_id)
);
COMMENT ON TABLE "02_iam"."44_lnk_flag_tag_assignments" IS 'Many-to-many between flags and tags. Idempotent insert.';

-- ---------------------------------------------------------------------------
-- Fact: flag variants (A/B/n multivariate)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."45_fct_flag_variants" (
    id          VARCHAR(36)  NOT NULL,
    flag_id     VARCHAR(36)  NOT NULL,
    key         TEXT         NOT NULL,
    name        TEXT         NOT NULL,
    value       JSONB        NOT NULL,
    weight      SMALLINT     NOT NULL DEFAULT 0,
    description TEXT,
    deleted_at  TIMESTAMP,
    created_by  VARCHAR(36),
    updated_by  VARCHAR(36),
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_fct_flag_variants PRIMARY KEY (id),
    CONSTRAINT fk_fct_flag_variants_flag FOREIGN KEY (flag_id)
        REFERENCES "02_iam"."22_fct_feature_flags"(id) ON DELETE CASCADE,
    CONSTRAINT chk_fct_flag_variants_weight CHECK (weight BETWEEN 0 AND 1000)
);
COMMENT ON TABLE "02_iam"."45_fct_flag_variants" IS 'A/B/n multivariate variants. Weights in thousandths (0-1000), total ≤ 1000.';
COMMENT ON COLUMN "02_iam"."45_fct_flag_variants".weight IS 'Traffic weight in basis points (0-1000). Sum of all live variants must not exceed 1000.';

CREATE UNIQUE INDEX idx_uq_fct_flag_variants_key
    ON "02_iam"."45_fct_flag_variants" (flag_id, key)
    WHERE deleted_at IS NULL;

CREATE TRIGGER trg_fct_flag_variants_updated_at
    BEFORE UPDATE ON "02_iam"."45_fct_flag_variants"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- ---------------------------------------------------------------------------
-- Fact: per-environment flag configs
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."46_fct_flag_env_configs" (
    id              VARCHAR(36)  NOT NULL,
    flag_id         VARCHAR(36)  NOT NULL,
    env_id          SMALLINT     NOT NULL,
    is_enabled      BOOLEAN      NOT NULL DEFAULT true,
    override_value  JSONB,
    created_by      VARCHAR(36),
    updated_by      VARCHAR(36),
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_fct_flag_env_configs PRIMARY KEY (id),
    CONSTRAINT fk_fct_flag_env_configs_flag FOREIGN KEY (flag_id)
        REFERENCES "02_iam"."22_fct_feature_flags"(id) ON DELETE CASCADE,
    CONSTRAINT fk_fct_flag_env_configs_env FOREIGN KEY (env_id)
        REFERENCES "02_iam"."03_dim_environments"(id),
    CONSTRAINT uq_fct_flag_env_configs UNIQUE (flag_id, env_id)
);
COMMENT ON TABLE "02_iam"."46_fct_flag_env_configs" IS 'Per-environment enable/override for a flag.';

CREATE TRIGGER trg_fct_flag_env_configs_updated_at
    BEFORE UPDATE ON "02_iam"."46_fct_flag_env_configs"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- ---------------------------------------------------------------------------
-- Link: org-level flag overrides
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."47_lnk_org_flag_overrides" (
    id          VARCHAR(36)  NOT NULL,
    org_id      VARCHAR(36)  NOT NULL,
    flag_id     VARCHAR(36)  NOT NULL,
    value       JSONB        NOT NULL,
    is_enabled  BOOLEAN      NOT NULL DEFAULT true,
    created_by  VARCHAR(36),
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_lnk_org_flag_overrides PRIMARY KEY (id),
    CONSTRAINT fk_lnk_org_flag_overrides_flag FOREIGN KEY (flag_id)
        REFERENCES "02_iam"."22_fct_feature_flags"(id) ON DELETE CASCADE,
    CONSTRAINT uq_lnk_org_flag_overrides UNIQUE (org_id, flag_id)
);
COMMENT ON TABLE "02_iam"."47_lnk_org_flag_overrides" IS 'Per-org value override for a feature flag.';

-- ---------------------------------------------------------------------------
-- Link: user-level flag overrides
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."48_lnk_user_flag_overrides" (
    id          VARCHAR(36)  NOT NULL,
    user_id     VARCHAR(36)  NOT NULL,
    flag_id     VARCHAR(36)  NOT NULL,
    value       JSONB        NOT NULL,
    is_enabled  BOOLEAN      NOT NULL DEFAULT true,
    created_by  VARCHAR(36),
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_lnk_user_flag_overrides PRIMARY KEY (id),
    CONSTRAINT fk_lnk_user_flag_overrides_flag FOREIGN KEY (flag_id)
        REFERENCES "02_iam"."22_fct_feature_flags"(id) ON DELETE CASCADE,
    CONSTRAINT uq_lnk_user_flag_overrides UNIQUE (user_id, flag_id)
);
COMMENT ON TABLE "02_iam"."48_lnk_user_flag_overrides" IS 'Per-user value override for a feature flag.';

-- ---------------------------------------------------------------------------
-- Link: identity targets (include/exclude specific entities)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."49_lnk_flag_identity_targets" (
    id                  VARCHAR(36)  NOT NULL,
    flag_id             VARCHAR(36)  NOT NULL,
    target_type_id      SMALLINT     NOT NULL,
    target_entity_id    VARCHAR(36)  NOT NULL,
    include             BOOLEAN      NOT NULL DEFAULT true,
    return_value        JSONB,
    created_by          VARCHAR(36),
    created_at          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_lnk_flag_identity_targets PRIMARY KEY (id),
    CONSTRAINT fk_lnk_flag_identity_targets_flag FOREIGN KEY (flag_id)
        REFERENCES "02_iam"."22_fct_feature_flags"(id) ON DELETE CASCADE,
    CONSTRAINT fk_lnk_flag_identity_targets_type FOREIGN KEY (target_type_id)
        REFERENCES "02_iam"."04_dim_target_types"(id),
    CONSTRAINT uq_lnk_flag_identity_targets UNIQUE (flag_id, target_type_id, target_entity_id)
);
COMMENT ON TABLE "02_iam"."49_lnk_flag_identity_targets" IS 'Direct entity targeting. Include targets override rules. Exclude targets short-circuit to default.';

-- ---------------------------------------------------------------------------
-- Link: flag prerequisites (dependency chain)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."50_lnk_flag_prerequisites" (
    id                      VARCHAR(36)  NOT NULL,
    flag_id                 VARCHAR(36)  NOT NULL,
    prerequisite_flag_id    VARCHAR(36)  NOT NULL,
    expected_value          JSONB        NOT NULL DEFAULT 'true'::jsonb,
    created_by              VARCHAR(36),
    created_at              TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_lnk_flag_prerequisites PRIMARY KEY (id),
    CONSTRAINT fk_lnk_flag_prerequisites_flag FOREIGN KEY (flag_id)
        REFERENCES "02_iam"."22_fct_feature_flags"(id) ON DELETE CASCADE,
    CONSTRAINT fk_lnk_flag_prerequisites_prereq FOREIGN KEY (prerequisite_flag_id)
        REFERENCES "02_iam"."22_fct_feature_flags"(id) ON DELETE CASCADE,
    CONSTRAINT uq_lnk_flag_prerequisites UNIQUE (flag_id, prerequisite_flag_id),
    CONSTRAINT chk_lnk_flag_prerequisites_no_self CHECK (flag_id != prerequisite_flag_id)
);
COMMENT ON TABLE "02_iam"."50_lnk_flag_prerequisites" IS 'Flags that must evaluate to expected_value before this flag is active. Circular deps prevented at service layer.';

-- ---------------------------------------------------------------------------
-- Fact: daily evaluation counts (analytics)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."51_fct_flag_eval_counts" (
    id          VARCHAR(36)  NOT NULL,
    flag_id     VARCHAR(36)  NOT NULL,
    org_id      VARCHAR(36),
    eval_date   DATE         NOT NULL DEFAULT CURRENT_DATE,
    eval_count  BIGINT       NOT NULL DEFAULT 0,
    true_count  BIGINT       NOT NULL DEFAULT 0,
    false_count BIGINT       NOT NULL DEFAULT 0,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_fct_flag_eval_counts PRIMARY KEY (id),
    CONSTRAINT fk_fct_flag_eval_counts_flag FOREIGN KEY (flag_id)
        REFERENCES "02_iam"."22_fct_feature_flags"(id) ON DELETE CASCADE,
    CONSTRAINT uq_fct_flag_eval_counts UNIQUE (flag_id, org_id, eval_date)
);
COMMENT ON TABLE "02_iam"."51_fct_flag_eval_counts" IS 'Daily aggregated evaluation counts per flag per org. Atomic upsert.';

CREATE INDEX idx_fct_flag_eval_counts_date ON "02_iam"."51_fct_flag_eval_counts" (flag_id, eval_date DESC);

CREATE TRIGGER trg_fct_flag_eval_counts_updated_at
    BEFORE UPDATE ON "02_iam"."51_fct_flag_eval_counts"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- =============================================================================
-- DOWN
-- =============================================================================

DROP TABLE IF EXISTS "02_iam"."51_fct_flag_eval_counts" CASCADE;
DROP TABLE IF EXISTS "02_iam"."50_lnk_flag_prerequisites" CASCADE;
DROP TABLE IF EXISTS "02_iam"."49_lnk_flag_identity_targets" CASCADE;
DROP TABLE IF EXISTS "02_iam"."48_lnk_user_flag_overrides" CASCADE;
DROP TABLE IF EXISTS "02_iam"."47_lnk_org_flag_overrides" CASCADE;
DROP TABLE IF EXISTS "02_iam"."46_fct_flag_env_configs" CASCADE;
DROP TABLE IF EXISTS "02_iam"."45_fct_flag_variants" CASCADE;
DROP TABLE IF EXISTS "02_iam"."44_lnk_flag_tag_assignments" CASCADE;
DROP TABLE IF EXISTS "02_iam"."43_fct_flag_tags" CASCADE;
DROP VIEW  IF EXISTS "02_iam".v_flag_rules;
DROP TABLE IF EXISTS "02_iam"."42_lnk_flag_rules" CASCADE;
DROP VIEW  IF EXISTS "02_iam".v_flag_segments;
DROP TABLE IF EXISTS "02_iam"."41_lnk_segment_conditions" CASCADE;
DROP TABLE IF EXISTS "02_iam"."40_fct_flag_segments" CASCADE;
DROP VIEW  IF EXISTS "02_iam".v_feature_flags;
DROP TABLE IF EXISTS "02_iam"."22_fct_feature_flags" CASCADE;
DROP TABLE IF EXISTS "02_iam"."04_dim_target_types" CASCADE;
DROP TABLE IF EXISTS "02_iam"."03_dim_environments" CASCADE;
DROP TABLE IF EXISTS "02_iam"."02_dim_rule_operators" CASCADE;
DROP TABLE IF EXISTS "02_iam"."01_dim_flag_value_types" CASCADE;
