-- ============================================================
-- Migration: 20260409_012_iam_feature_flags
-- Description: Feature flags — scoped, categorized, product-linked
--              with environment overrides + targeting tables
-- Schema: 03_iam
-- ============================================================

-- UP ====

-- ---------------------------------------------------------------------------
-- 1. Register entity type for feature flags (EAV)
-- ---------------------------------------------------------------------------

INSERT INTO "03_iam"."06_dim_entity_types" (code, label, description)
VALUES ('platform_feature_flag', 'Platform Feature Flag', 'Feature flag entity for EAV attributes')
ON CONFLICT (code) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 2. Register EAV attr defs for platform_feature_flag
-- ---------------------------------------------------------------------------

INSERT INTO "03_iam"."07_dim_attr_defs" (entity_type_id, code, label, value_column, description)
SELECT
    et.id,
    a.code,
    a.label,
    a.value_column,
    a.description
FROM "03_iam"."06_dim_entity_types" et,
(VALUES
    ('description',        'Description',        'key_text', 'Human-readable description of this flag'),
    ('owner_user_id',      'Owner User ID',      'key_text', 'User responsible for this flag'),
    ('jira_ticket',        'Jira Ticket',        'key_text', 'Jira issue tracking this flag'),
    ('rollout_percentage', 'Rollout Percentage', 'key_text', 'Percentage (0-100) for gradual rollout'),
    ('launch_date',        'Launch Date',        'key_text', 'ISO date when flag goes live'),
    ('sunset_date',        'Sunset Date',        'key_text', 'ISO date when flag should be removed')
) AS a(code, label, value_column, description)
WHERE et.code = 'platform_feature_flag'
ON CONFLICT (entity_type_id, code) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 3. Core flag table: 10_fct_feature_flags
-- ---------------------------------------------------------------------------

CREATE TABLE "03_iam"."10_fct_feature_flags" (
    id           VARCHAR(36)  NOT NULL,
    code         VARCHAR(96)  NOT NULL,
    name         VARCHAR(128) NOT NULL,
    product_id   VARCHAR(36)  NOT NULL,
    feature_id   VARCHAR(36)  NULL,
    scope_id     SMALLINT     NOT NULL,
    category_id  SMALLINT     NOT NULL,
    flag_type    VARCHAR(24)  NOT NULL,
    status       VARCHAR(16)  NOT NULL DEFAULT 'draft',
    default_value JSONB       NULL,
    is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
    is_test      BOOLEAN      NOT NULL DEFAULT FALSE,
    deleted_at   TIMESTAMP    NULL,
    created_by   VARCHAR(36)  NOT NULL,
    updated_by   VARCHAR(36)  NOT NULL,
    created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fct_feature_flags PRIMARY KEY (id),
    CONSTRAINT uq_fct_feature_flags_code UNIQUE (code),
    CONSTRAINT fk_fct_feature_flags_product
        FOREIGN KEY (product_id) REFERENCES "03_iam"."10_fct_products" (id),
    CONSTRAINT fk_fct_feature_flags_feature
        FOREIGN KEY (feature_id) REFERENCES "03_iam"."10_fct_features" (id),
    CONSTRAINT fk_fct_feature_flags_scope
        FOREIGN KEY (scope_id) REFERENCES "03_iam"."06_dim_scopes" (id),
    CONSTRAINT fk_fct_feature_flags_category
        FOREIGN KEY (category_id) REFERENCES "03_iam"."06_dim_categories" (id),
    CONSTRAINT chk_fct_feature_flags_flag_type
        CHECK (flag_type IN ('boolean', 'percentage', 'variant', 'kill_switch', 'experiment')),
    CONSTRAINT chk_fct_feature_flags_status
        CHECK (status IN ('draft', 'active', 'deprecated', 'archived'))
);

COMMENT ON TABLE "03_iam"."10_fct_feature_flags" IS 'Platform feature flags — scoped, categorized, product-linked';
COMMENT ON COLUMN "03_iam"."10_fct_feature_flags".id IS 'UUID v7 primary key';
COMMENT ON COLUMN "03_iam"."10_fct_feature_flags".code IS 'Machine-readable code, e.g. vault.new_cipher_ui';
COMMENT ON COLUMN "03_iam"."10_fct_feature_flags".name IS 'Human-readable name';
COMMENT ON COLUMN "03_iam"."10_fct_feature_flags".product_id IS 'FK to 10_fct_products — which product owns this flag';
COMMENT ON COLUMN "03_iam"."10_fct_feature_flags".feature_id IS 'Optional FK to 10_fct_features — which feature this flag gates';
COMMENT ON COLUMN "03_iam"."10_fct_feature_flags".scope_id IS 'FK to 06_dim_scopes — platform/org/workspace';
COMMENT ON COLUMN "03_iam"."10_fct_feature_flags".category_id IS 'FK to 06_dim_categories — kill_switch/rollout/experiment/etc';
COMMENT ON COLUMN "03_iam"."10_fct_feature_flags".flag_type IS 'boolean|percentage|variant|kill_switch|experiment';
COMMENT ON COLUMN "03_iam"."10_fct_feature_flags".status IS 'draft|active|deprecated|archived';
COMMENT ON COLUMN "03_iam"."10_fct_feature_flags".default_value IS 'Default value returned if no override/target matches';
COMMENT ON COLUMN "03_iam"."10_fct_feature_flags".is_active IS 'If false, flag is disabled — always returns default_value';

CREATE INDEX idx_fct_feature_flags_product_id ON "03_iam"."10_fct_feature_flags" (product_id);
CREATE INDEX idx_fct_feature_flags_scope_id   ON "03_iam"."10_fct_feature_flags" (scope_id);
CREATE INDEX idx_fct_feature_flags_status     ON "03_iam"."10_fct_feature_flags" (status) WHERE deleted_at IS NULL;

-- ---------------------------------------------------------------------------
-- 4. Environment overrides: 40_lnk_flag_environments
-- ---------------------------------------------------------------------------

CREATE TABLE "03_iam"."40_lnk_flag_environments" (
    id             VARCHAR(36) NOT NULL,
    flag_id        VARCHAR(36) NOT NULL,
    environment_id SMALLINT    NOT NULL,
    enabled        BOOLEAN     NOT NULL DEFAULT TRUE,
    value          JSONB       NULL,
    created_at     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_lnk_flag_environments PRIMARY KEY (id),
    CONSTRAINT uq_lnk_flag_environments UNIQUE (flag_id, environment_id),
    CONSTRAINT fk_lnk_flag_environments_flag
        FOREIGN KEY (flag_id) REFERENCES "03_iam"."10_fct_feature_flags" (id),
    CONSTRAINT fk_lnk_flag_environments_env
        FOREIGN KEY (environment_id) REFERENCES "03_iam"."06_dim_environments" (id)
);

COMMENT ON TABLE "03_iam"."40_lnk_flag_environments" IS 'Per-environment overrides for feature flags';
COMMENT ON COLUMN "03_iam"."40_lnk_flag_environments".flag_id IS 'FK to 10_fct_feature_flags';
COMMENT ON COLUMN "03_iam"."40_lnk_flag_environments".environment_id IS 'FK to 06_dim_environments (dev/staging/prod)';
COMMENT ON COLUMN "03_iam"."40_lnk_flag_environments".enabled IS 'Whether the flag is enabled in this environment';
COMMENT ON COLUMN "03_iam"."40_lnk_flag_environments".value IS 'Override value (NULL = use default_value)';

-- ---------------------------------------------------------------------------
-- 5. Platform-scope targets: 40_lnk_flag_platform_targets
-- ---------------------------------------------------------------------------

CREATE TABLE "03_iam"."40_lnk_flag_platform_targets" (
    id         VARCHAR(36) NOT NULL,
    flag_id    VARCHAR(36) NOT NULL,
    value      JSONB       NULL,
    created_at TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_lnk_flag_platform_targets PRIMARY KEY (id),
    CONSTRAINT fk_lnk_flag_platform_targets_flag
        FOREIGN KEY (flag_id) REFERENCES "03_iam"."10_fct_feature_flags" (id)
);

COMMENT ON TABLE "03_iam"."40_lnk_flag_platform_targets" IS 'Targeting overrides for platform-scoped flags';

-- ---------------------------------------------------------------------------
-- 6. Org-scope targets: 40_lnk_flag_org_targets
-- ---------------------------------------------------------------------------

CREATE TABLE "03_iam"."40_lnk_flag_org_targets" (
    id         VARCHAR(36) NOT NULL,
    flag_id    VARCHAR(36) NOT NULL,
    org_id     VARCHAR(36) NOT NULL,
    value      JSONB       NULL,
    created_at TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_lnk_flag_org_targets PRIMARY KEY (id),
    CONSTRAINT uq_lnk_flag_org_targets UNIQUE (flag_id, org_id),
    CONSTRAINT fk_lnk_flag_org_targets_flag
        FOREIGN KEY (flag_id) REFERENCES "03_iam"."10_fct_feature_flags" (id)
);

COMMENT ON TABLE "03_iam"."40_lnk_flag_org_targets" IS 'Targeting overrides for org-scoped flags';
COMMENT ON COLUMN "03_iam"."40_lnk_flag_org_targets".org_id IS 'Org ID this targeting rule applies to';

-- ---------------------------------------------------------------------------
-- 7. Workspace-scope targets: 40_lnk_flag_workspace_targets
-- ---------------------------------------------------------------------------

CREATE TABLE "03_iam"."40_lnk_flag_workspace_targets" (
    id           VARCHAR(36) NOT NULL,
    flag_id      VARCHAR(36) NOT NULL,
    workspace_id VARCHAR(36) NOT NULL,
    value        JSONB       NULL,
    created_at   TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_lnk_flag_workspace_targets PRIMARY KEY (id),
    CONSTRAINT uq_lnk_flag_workspace_targets UNIQUE (flag_id, workspace_id),
    CONSTRAINT fk_lnk_flag_workspace_targets_flag
        FOREIGN KEY (flag_id) REFERENCES "03_iam"."10_fct_feature_flags" (id)
);

COMMENT ON TABLE "03_iam"."40_lnk_flag_workspace_targets" IS 'Targeting overrides for workspace-scoped flags';
COMMENT ON COLUMN "03_iam"."40_lnk_flag_workspace_targets".workspace_id IS 'Workspace ID this targeting rule applies to';

-- ---------------------------------------------------------------------------
-- 8. View: v_feature_flags
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW "03_iam".v_feature_flags AS
SELECT
    ff.id,
    ff.code,
    ff.name,
    ff.product_id,
    p.name        AS product_name,
    p.code        AS product_code,
    ff.feature_id,
    ff.scope_id,
    sc.code       AS scope_code,
    sc.label      AS scope_label,
    ff.category_id,
    cat.code      AS category_code,
    cat.label     AS category_label,
    ff.flag_type,
    ff.status,
    ff.default_value,
    ff.is_active,
    ff.is_test,
    ff.deleted_at,
    (ff.deleted_at IS NOT NULL) AS is_deleted,
    ff.created_by,
    ff.updated_by,
    ff.created_at,
    ff.updated_at
FROM "03_iam"."10_fct_feature_flags" ff
JOIN "03_iam"."10_fct_products"  p   ON p.id   = ff.product_id
JOIN "03_iam"."06_dim_scopes"    sc  ON sc.id  = ff.scope_id
JOIN "03_iam"."06_dim_categories" cat ON cat.id = ff.category_id;

COMMENT ON VIEW "03_iam".v_feature_flags IS 'Denormalized view of feature flags with scope, category, and product names';

-- ---------------------------------------------------------------------------
-- 9. Permissions
-- ---------------------------------------------------------------------------

GRANT SELECT, INSERT, UPDATE, DELETE ON "03_iam"."10_fct_feature_flags"        TO tennetctl_write;
GRANT SELECT, INSERT, UPDATE, DELETE ON "03_iam"."40_lnk_flag_environments"     TO tennetctl_write;
GRANT SELECT, INSERT, UPDATE, DELETE ON "03_iam"."40_lnk_flag_platform_targets" TO tennetctl_write;
GRANT SELECT, INSERT, UPDATE, DELETE ON "03_iam"."40_lnk_flag_org_targets"      TO tennetctl_write;
GRANT SELECT, INSERT, UPDATE, DELETE ON "03_iam"."40_lnk_flag_workspace_targets" TO tennetctl_write;
GRANT SELECT ON "03_iam".v_feature_flags TO tennetctl_write;
GRANT SELECT ON "03_iam".v_feature_flags TO tennetctl_read;

-- DOWN ====

-- DROP VIEW "03_iam".v_feature_flags;
-- DROP TABLE "03_iam"."40_lnk_flag_workspace_targets";
-- DROP TABLE "03_iam"."40_lnk_flag_org_targets";
-- DROP TABLE "03_iam"."40_lnk_flag_platform_targets";
-- DROP TABLE "03_iam"."40_lnk_flag_environments";
-- DROP TABLE "03_iam"."10_fct_feature_flags";
-- DELETE FROM "03_iam"."07_dim_attr_defs" WHERE entity_type_id = (SELECT id FROM "03_iam"."06_dim_entity_types" WHERE code = 'platform_feature_flag');
-- DELETE FROM "03_iam"."06_dim_entity_types" WHERE code = 'platform_feature_flag';
