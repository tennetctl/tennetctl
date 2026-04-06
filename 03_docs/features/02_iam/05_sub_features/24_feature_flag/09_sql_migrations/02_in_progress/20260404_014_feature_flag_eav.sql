-- =============================================================================
-- Migration: 20260404_014_feature_flag_eav.sql
-- Sub-feature: 24_feature_flag
-- Description: EAV layer for feature flags — extensible attributes without DDL.
--   Add any metadata to flags via INSERT into dim_flag_attr_defs + dtl_flag_attrs.
-- UP
-- =============================================================================

SET search_path TO "02_iam", public;

-- ---------------------------------------------------------------------------
-- Dimension: flag attribute definitions (the registry)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."07_dim_flag_attr_defs" (
    id              SMALLINT    NOT NULL,
    code            TEXT        NOT NULL,
    label           TEXT        NOT NULL,
    value_type      TEXT        NOT NULL,
    description     TEXT        NOT NULL DEFAULT '',
    is_system       BOOLEAN     NOT NULL DEFAULT false,
    deprecated_at   TIMESTAMP,

    CONSTRAINT pk_dim_flag_attr_defs PRIMARY KEY (id),
    CONSTRAINT uq_dim_flag_attr_defs_code UNIQUE (code),
    CONSTRAINT chk_dim_flag_attr_defs_vtype CHECK (value_type IN ('text', 'jsonb', 'smallint'))
);
COMMENT ON TABLE "02_iam"."07_dim_flag_attr_defs" IS
    'Flag EAV attribute registry. INSERT to extend — no DDL needed.';
COMMENT ON COLUMN "02_iam"."07_dim_flag_attr_defs".value_type IS
    'text = key_text, jsonb = key_jsonb, smallint = key_smallint (FK to dim tables).';

-- Seed system attributes (IDs 1–29 reserved for system, >=1000 for custom)
INSERT INTO "02_iam"."07_dim_flag_attr_defs" (id, code, label, value_type, is_system, description) VALUES
    -- Lifecycle & Status
    (1,  'lifecycle_state',   'Lifecycle State',    'smallint', true,  'FK to dim_flag_lifecycle_states'),
    (2,  'access_mode',       'Access Mode',        'smallint', true,  'FK to dim_flag_access_modes'),
    -- Ownership
    (3,  'owner_id',          'Owner',              'text',     true,  'UUID of flag owner'),
    (4,  'owner_email',       'Owner Email',        'text',     false, 'Email for stale notifications'),
    (5,  'team_id',           'Team',               'text',     false, 'UUID of owning team'),
    (6,  'project_id',        'Project',            'text',     true,  'UUID FK to fct_flag_projects'),
    -- Operational
    (7,  'is_kill_switch',    'Kill Switch',        'smallint', true,  '1 = emergency disabled'),
    (8,  'permanently_on',    'Permanently On',     'smallint', true,  '1 = skip evaluation, always default'),
    -- Cleanup
    (9,  'stale_after_days',  'Stale After Days',   'smallint', false, 'Days without eval before auto-stale'),
    (10, 'removal_date',      'Removal Date',       'text',     false, 'ISO-8601 cleanup deadline'),
    (11, 'last_evaluated_at', 'Last Evaluated',     'text',     false, 'ISO-8601 of last evaluation'),
    -- Traceability
    (12, 'jira_ticket',       'Jira Ticket',        'text',     false, 'Linked ticket key'),
    (13, 'initial_audience',  'Initial Audience',   'text',     false, 'First rollout group description'),
    (14, 'purpose',           'Purpose',            'text',     false, 'Why this flag exists'),
    (15, 'change_reason',     'Last Change Reason', 'text',     false, 'Justification for last change'),
    -- Governance
    (16, 'require_approval',  'Require Approval',   'smallint', false, '1 = changes need approval'),
    (17, 'require_comment',   'Require Comment',    'smallint', false, '1 = changes need a comment'),
    -- Client hints
    (18, 'impression_data',   'Impression Data',    'smallint', false, '1 = emit impression events on eval'),
    (19, 'sdk_filter_tags',   'SDK Filter Tags',    'jsonb',    false, 'Array of tags for SDK filtering'),
    -- Experimentation
    (20, 'experiment_id',     'Experiment',         'text',     false, 'UUID linking to A/B experiment'),
    (21, 'hypothesis',        'Hypothesis',         'text',     false, 'Experiment hypothesis'),
    (22, 'metric_keys',       'Metric Keys',        'jsonb',    false, 'Array of metric keys to track'),
    (23, 'success_criteria',  'Success Criteria',   'jsonb',    false, 'JSON defining success metrics'),
    (24, 'rollout_strategy',  'Rollout Strategy',   'text',     false, 'percentage|gradual|ring|canary'),
    -- Integration
    (25, 'webhook_url',       'Webhook URL',        'text',     false, 'Per-flag webhook override'),
    (26, 'slack_channel',     'Slack Channel',      'text',     false, 'Notification channel'),
    (27, 'custom_properties', 'Custom Properties',  'jsonb',    false, 'Arbitrary key-value bag'),
    -- Licensing & Entitlements
    (28, 'required_permission', 'Required Permission', 'text',  true,  'RBAC permission code required to toggle (e.g. flag:update)'),
    (29, 'required_license',   'Required License',    'smallint', true, 'FK to dim_license_tiers. Flag hidden below this tier'),
    (30, 'license_tier',       'License Tier',        'smallint', true, 'FK to dim_license_tiers. Tier this flag belongs to'),
    -- Metered / Usage-Based
    (31, 'is_metered',         'Is Metered',          'smallint', true, '1 = usage-counted flag for licensing quotas'),
    (32, 'quota_limit',        'Quota Limit',         'smallint', false, 'Max usage count per org per billing period'),
    (33, 'quota_period',       'Quota Period',        'text',    false, 'monthly|daily|yearly — billing reset period'),
    (34, 'quota_scope',        'Quota Scope',         'text',    false, 'org|user|workspace — who the quota applies to'),
    (35, 'overage_action',     'Overage Action',      'text',    false, 'block|warn|log — what happens at limit');

-- ---------------------------------------------------------------------------
-- Dimension: license tiers (for entitlement gating)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."08_dim_license_tiers" (
    id          SMALLINT    NOT NULL,
    code        TEXT        NOT NULL,
    label       TEXT        NOT NULL,
    sort_order  SMALLINT    NOT NULL DEFAULT 0,
    description TEXT,
    deprecated_at TIMESTAMP,

    CONSTRAINT pk_dim_license_tiers PRIMARY KEY (id),
    CONSTRAINT uq_dim_license_tiers_code UNIQUE (code)
);
COMMENT ON TABLE "02_iam"."08_dim_license_tiers" IS 'License tiers for feature entitlement. Flags can require a minimum tier.';

INSERT INTO "02_iam"."08_dim_license_tiers" (id, code, label, sort_order) VALUES
    (1, 'free',       'Free',       1),
    (2, 'starter',    'Starter',    2),
    (3, 'pro',        'Pro',        3),
    (4, 'enterprise', 'Enterprise', 4),
    (5, 'internal',   'Internal',   5);

-- Add metered value type to existing dim
INSERT INTO "02_iam"."01_dim_flag_value_types" (id, code, label) VALUES
    (5, 'metered', 'Metered')
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Fact: usage counters for metered flags
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."57_fct_flag_usage_counters" (
    id              VARCHAR(36)  NOT NULL,
    flag_id         VARCHAR(36)  NOT NULL,
    scope_type      TEXT         NOT NULL DEFAULT 'org',
    scope_id        VARCHAR(36)  NOT NULL,
    period_start    DATE         NOT NULL,
    period_end      DATE         NOT NULL,
    usage_count     BIGINT       NOT NULL DEFAULT 0,
    quota_limit     INT,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_fct_flag_usage_counters PRIMARY KEY (id),
    CONSTRAINT fk_fct_flag_usage_counters_flag FOREIGN KEY (flag_id)
        REFERENCES "02_iam"."22_fct_feature_flags"(id) ON DELETE CASCADE,
    CONSTRAINT uq_fct_flag_usage_counters UNIQUE (flag_id, scope_type, scope_id, period_start),
    CONSTRAINT chk_fct_flag_usage_counters_scope CHECK (scope_type IN ('org', 'user', 'workspace'))
);
COMMENT ON TABLE "02_iam"."57_fct_flag_usage_counters" IS 'Usage counters for metered flags. Tracks consumption per scope per billing period.';
COMMENT ON COLUMN "02_iam"."57_fct_flag_usage_counters".scope_type IS 'org|user|workspace — who the counter tracks.';
COMMENT ON COLUMN "02_iam"."57_fct_flag_usage_counters".usage_count IS 'Atomic increment via ON CONFLICT DO UPDATE.';

CREATE INDEX idx_fct_flag_usage_counters_flag ON "02_iam"."57_fct_flag_usage_counters" (flag_id, scope_id, period_start);

CREATE TRIGGER trg_fct_flag_usage_counters_updated_at
    BEFORE UPDATE ON "02_iam"."57_fct_flag_usage_counters"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- Add metered flag permissions to RBAC
INSERT INTO "02_iam"."26_fct_permissions" (id, resource, action, description, is_system) VALUES
    ('00000000-0000-0000-0000-000000000139', 'flag',     'meter',     'Increment metered flag usage', true),
    ('00000000-0000-0000-0000-000000000140', 'flag',     'quota',     'View and manage flag quotas', true),
    ('00000000-0000-0000-0000-000000000141', 'license',  'read',      'View license tier information', true),
    ('00000000-0000-0000-0000-000000000142', 'license',  'update',    'Change org license tier', true)
ON CONFLICT (resource, action) DO NOTHING;

-- Sequence for custom attrs (start at 1000)
CREATE SEQUENCE "02_iam".seq_flag_attr_def_id START 1000;

-- ---------------------------------------------------------------------------
-- Detail: flag EAV value store
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."47_dtl_flag_attrs" (
    id              VARCHAR(36) NOT NULL,
    flag_id         VARCHAR(36) NOT NULL,
    attr_def_id     SMALLINT    NOT NULL,
    key_text        TEXT,
    key_jsonb       JSONB,
    key_smallint    SMALLINT,
    created_by      VARCHAR(36),
    updated_by      VARCHAR(36),
    created_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_dtl_flag_attrs PRIMARY KEY (id),
    CONSTRAINT fk_dtl_flag_attrs_flag FOREIGN KEY (flag_id)
        REFERENCES "02_iam"."22_fct_feature_flags"(id) ON DELETE CASCADE,
    CONSTRAINT fk_dtl_flag_attrs_def FOREIGN KEY (attr_def_id)
        REFERENCES "02_iam"."07_dim_flag_attr_defs"(id),
    CONSTRAINT uq_dtl_flag_attrs UNIQUE (flag_id, attr_def_id),
    CONSTRAINT chk_dtl_flag_attrs_one_value CHECK (
        (key_text IS NOT NULL)::int +
        (key_jsonb IS NOT NULL)::int +
        (key_smallint IS NOT NULL)::int = 1
    )
);
COMMENT ON TABLE "02_iam"."47_dtl_flag_attrs" IS
    'Flag EAV value store. One row per (flag, attribute). Exactly one value column non-NULL.';

CREATE INDEX idx_dtl_flag_attrs_flag ON "02_iam"."47_dtl_flag_attrs" (flag_id);

CREATE TRIGGER trg_dtl_flag_attrs_updated_at
    BEFORE UPDATE ON "02_iam"."47_dtl_flag_attrs"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- ---------------------------------------------------------------------------
-- View: flag attrs resolved with labels
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW "02_iam".v_flag_attrs AS
SELECT
    a.id,
    a.flag_id,
    a.attr_def_id,
    d.code      AS attr_code,
    d.label     AS attr_label,
    d.value_type,
    d.is_system,
    a.key_text,
    a.key_jsonb,
    a.key_smallint,
    -- Resolve lifecycle_state FK
    CASE WHEN d.code = 'lifecycle_state' THEN ls.label ELSE NULL END AS resolved_label,
    -- Resolve access_mode FK
    CASE WHEN d.code = 'access_mode' THEN am.label ELSE NULL END AS resolved_access_label,
    a.created_by,
    a.updated_by,
    a.created_at,
    a.updated_at
FROM "02_iam"."47_dtl_flag_attrs" a
JOIN "02_iam"."07_dim_flag_attr_defs" d ON d.id = a.attr_def_id
LEFT JOIN "02_iam"."05_dim_flag_lifecycle_states" ls ON d.code = 'lifecycle_state' AND ls.id = a.key_smallint
LEFT JOIN "02_iam"."06_dim_flag_access_modes" am ON d.code = 'access_mode' AND am.id = a.key_smallint;

-- =============================================================================
-- DOWN
-- =============================================================================

DELETE FROM "02_iam"."26_fct_permissions" WHERE id IN (
    '00000000-0000-0000-0000-000000000139', '00000000-0000-0000-0000-000000000140',
    '00000000-0000-0000-0000-000000000141', '00000000-0000-0000-0000-000000000142'
);
DROP TABLE IF EXISTS "02_iam"."57_fct_flag_usage_counters" CASCADE;
DROP VIEW  IF EXISTS "02_iam".v_flag_attrs;
DROP TABLE IF EXISTS "02_iam"."47_dtl_flag_attrs" CASCADE;
DROP SEQUENCE IF EXISTS "02_iam".seq_flag_attr_def_id;
DROP TABLE IF EXISTS "02_iam"."07_dim_flag_attr_defs" CASCADE;
DELETE FROM "02_iam"."01_dim_flag_value_types" WHERE id = 5;
DROP TABLE IF EXISTS "02_iam"."08_dim_license_tiers" CASCADE;
