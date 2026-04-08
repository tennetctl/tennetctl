-- =============================================================================
-- Migration:   20260409_010_iam_foundation_primitives.sql
-- Module:      03_iam
-- Sub-feature: 00_bootstrap (Foundation Primitives)
-- Sequence:    010
-- Depends on:  003 (iam_bootstrap), 009 (iam_groups)
-- Description: Sprint 2 "Foundation" — four cross-cutting primitive tables
--              that every downstream sprint (RBAC, Feature Flags) depends on.
--
--              1. dim_scopes         — platform | org | workspace
--              2. dim_categories     — shared category table (role/feature/flag/product)
--              3. dim_environments   — dev | staging | prod
--              4. fct_products       — platform product catalog + EAV
--                 40_lnk_workspace_products — workspace ↔ product M2M
--              5. fct_features       — feature registry + EAV
-- =============================================================================

-- UP =========================================================================

-- ---------------------------------------------------------------------------
-- 1. dim_scopes — three rows, forever
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."06_dim_scopes" (
    id             SMALLINT    GENERATED ALWAYS AS IDENTITY,
    code           TEXT        NOT NULL,
    label          TEXT        NOT NULL,
    description    TEXT,
    deprecated_at  TIMESTAMP,

    CONSTRAINT pk_iam_dim_scopes       PRIMARY KEY (id),
    CONSTRAINT uq_iam_dim_scopes_code  UNIQUE (code)
);

COMMENT ON TABLE  "03_iam"."06_dim_scopes" IS
    'Scope hierarchy for roles, features, and flags. Three permanent rows: '
    'platform (system-wide), org (per-tenant), workspace (per-department).';
COMMENT ON COLUMN "03_iam"."06_dim_scopes".id           IS 'Auto-assigned PK. Permanent.';
COMMENT ON COLUMN "03_iam"."06_dim_scopes".code         IS 'Stable machine-readable identifier.';
COMMENT ON COLUMN "03_iam"."06_dim_scopes".label        IS 'Human-readable name.';
COMMENT ON COLUMN "03_iam"."06_dim_scopes".description  IS 'Optional description.';
COMMENT ON COLUMN "03_iam"."06_dim_scopes".deprecated_at IS 'Set when phasing out a row.';

INSERT INTO "03_iam"."06_dim_scopes" (code, label, description) VALUES
    ('platform',  'Platform',  'System-wide scope. Applies across all orgs and workspaces.'),
    ('org',       'Org',       'Per-tenant scope. Applies within a single organisation.'),
    ('workspace', 'Workspace', 'Per-department scope. Applies within a single workspace.');

GRANT SELECT ON "03_iam"."06_dim_scopes" TO tennetctl_read;
GRANT SELECT ON "03_iam"."06_dim_scopes" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 2. dim_categories — shared discriminated lookup table
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."06_dim_categories" (
    id             SMALLINT    GENERATED ALWAYS AS IDENTITY,
    category_type  TEXT        NOT NULL,
    code           TEXT        NOT NULL,
    label          TEXT        NOT NULL,
    description    TEXT,
    deprecated_at  TIMESTAMP,

    CONSTRAINT pk_iam_dim_categories            PRIMARY KEY (id),
    CONSTRAINT uq_iam_dim_categories_type_code  UNIQUE (category_type, code),
    CONSTRAINT chk_iam_dim_categories_type
        CHECK (category_type IN ('role', 'feature', 'flag', 'product'))
);

CREATE INDEX idx_iam_dim_categories_type
    ON "03_iam"."06_dim_categories" (category_type);

COMMENT ON TABLE  "03_iam"."06_dim_categories" IS
    'Shared category lookup table with category_type discriminator. '
    'Used by roles (RBAC), feature registry, feature flags, and products.';
COMMENT ON COLUMN "03_iam"."06_dim_categories".id            IS 'Auto-assigned PK. Permanent.';
COMMENT ON COLUMN "03_iam"."06_dim_categories".category_type IS 'Discriminator: role | feature | flag | product.';
COMMENT ON COLUMN "03_iam"."06_dim_categories".code          IS 'Machine-readable identifier, unique within category_type.';
COMMENT ON COLUMN "03_iam"."06_dim_categories".label         IS 'Human-readable name.';
COMMENT ON COLUMN "03_iam"."06_dim_categories".description   IS 'Optional description.';
COMMENT ON COLUMN "03_iam"."06_dim_categories".deprecated_at IS 'Set when phasing out a row.';

INSERT INTO "03_iam"."06_dim_categories" (category_type, code, label, description) VALUES
    -- role categories
    ('role', 'system',   'System',   'Platform-level system roles.'),
    ('role', 'security', 'Security', 'Security and compliance roles.'),
    ('role', 'billing',  'Billing',  'Billing and payments roles.'),
    ('role', 'content',  'Content',  'Content management roles.'),
    ('role', 'support',  'Support',  'Customer support roles.'),
    ('role', 'ops',      'Ops',      'Operations and DevOps roles.'),
    -- feature categories
    ('feature', 'iam',            'IAM',            'Identity and access management features.'),
    ('feature', 'vault',          'Vault',          'Secret storage and encryption features.'),
    ('feature', 'audit',          'Audit',          'Audit logging features.'),
    ('feature', 'billing',        'Billing',        'Billing and subscription features.'),
    ('feature', 'observability',  'Observability',  'Monitoring, metrics, and tracing features.'),
    ('feature', 'maps',           'Maps',           'Geographic and mapping features.'),
    ('feature', 'rbac',           'RBAC',           'Role-based access control features.'),
    ('feature', 'sessions',       'Sessions',       'Session management features.'),
    ('feature', 'platform_ops',   'Platform Ops',   'Platform operations features.'),
    -- flag categories
    ('flag', 'kill_switch',     'Kill Switch',     'Emergency off switches for features.'),
    ('flag', 'rollout',         'Rollout',         'Gradual feature rollout flags.'),
    ('flag', 'experiment',      'Experiment',      'A/B testing and experiments.'),
    ('flag', 'ops',             'Ops',             'Operational control flags.'),
    ('flag', 'permission_gate', 'Permission Gate', 'Permission-controlled feature flags.'),
    -- product categories
    ('product', 'core_platform',   'Core Platform',   'The foundational platform product.'),
    ('product', 'saas_app',        'SaaS App',        'Software-as-a-service application product.'),
    ('product', 'internal_tool',   'Internal Tool',   'Internal tooling product.'),
    ('product', 'library',         'Library',         'Reusable library or SDK product.');

GRANT SELECT ON "03_iam"."06_dim_categories" TO tennetctl_read;
GRANT SELECT ON "03_iam"."06_dim_categories" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 3. dim_environments — three rows
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."06_dim_environments" (
    id             SMALLINT    GENERATED ALWAYS AS IDENTITY,
    code           TEXT        NOT NULL,
    label          TEXT        NOT NULL,
    description    TEXT,
    deprecated_at  TIMESTAMP,

    CONSTRAINT pk_iam_dim_environments       PRIMARY KEY (id),
    CONSTRAINT uq_iam_dim_environments_code  UNIQUE (code)
);

COMMENT ON TABLE  "03_iam"."06_dim_environments" IS
    'Deployment environment registry. Three permanent rows: dev, staging, prod.';
COMMENT ON COLUMN "03_iam"."06_dim_environments".id           IS 'Auto-assigned PK. Permanent.';
COMMENT ON COLUMN "03_iam"."06_dim_environments".code         IS 'Stable machine-readable identifier.';
COMMENT ON COLUMN "03_iam"."06_dim_environments".label        IS 'Human-readable name.';
COMMENT ON COLUMN "03_iam"."06_dim_environments".description  IS 'Optional description.';
COMMENT ON COLUMN "03_iam"."06_dim_environments".deprecated_at IS 'Set when phasing out a row.';

INSERT INTO "03_iam"."06_dim_environments" (code, label, description) VALUES
    ('dev',     'Development', 'Local development environment.'),
    ('staging', 'Staging',     'Pre-production staging environment.'),
    ('prod',    'Production',  'Live production environment.');

GRANT SELECT ON "03_iam"."06_dim_environments" TO tennetctl_read;
GRANT SELECT ON "03_iam"."06_dim_environments" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 4. Register entity types for EAV
-- ---------------------------------------------------------------------------
INSERT INTO "03_iam"."06_dim_entity_types" (code, label, description) VALUES
    ('platform_product', 'Platform Product', 'A product in the platform product catalog.'),
    ('platform_feature', 'Platform Feature', 'A feature in the platform feature registry.');

-- ---------------------------------------------------------------------------
-- 5. Register attr_defs for platform_product
-- ---------------------------------------------------------------------------
INSERT INTO "03_iam"."07_dim_attr_defs"
    (entity_type_id, code, label, description, value_column)
SELECT et.id, x.code, x.label, x.description, x.value_column
FROM (VALUES
    ('platform_product', 'description',    'Description',    'Long-form product description.',              'key_text'),
    ('platform_product', 'slug',           'Slug',           'URL-safe unique identifier for the product.', 'key_text'),
    ('platform_product', 'status',         'Status',         'Current lifecycle status of the product.',    'key_text'),
    ('platform_product', 'pricing_tier',   'Pricing Tier',   'Pricing tier code for the product.',          'key_text'),
    ('platform_product', 'owner_user_id',  'Owner User ID',  'UUID of the user who owns this product.',     'key_text')
) AS x(entity_code, code, label, description, value_column)
JOIN "03_iam"."06_dim_entity_types" et ON et.code = x.entity_code;

-- ---------------------------------------------------------------------------
-- 6. Register attr_defs for platform_feature
-- ---------------------------------------------------------------------------
INSERT INTO "03_iam"."07_dim_attr_defs"
    (entity_type_id, code, label, description, value_column)
SELECT et.id, x.code, x.label, x.description, x.value_column
FROM (VALUES
    ('platform_feature', 'description',         'Description',          'Long-form feature description.',                    'key_text'),
    ('platform_feature', 'status',              'Status',               'Current lifecycle status of the feature.',           'key_text'),
    ('platform_feature', 'doc_url',             'Doc URL',              'URL to the feature documentation.',                  'key_text'),
    ('platform_feature', 'owner_user_id',       'Owner User ID',        'UUID of the user who owns this feature.',            'key_text'),
    ('platform_feature', 'version_introduced',  'Version Introduced',   'Platform version when this feature was introduced.', 'key_text')
) AS x(entity_code, code, label, description, value_column)
JOIN "03_iam"."06_dim_entity_types" et ON et.code = x.entity_code;

-- ---------------------------------------------------------------------------
-- 7. fct_products — platform product catalog
--    Pure-EAV: no string business columns except id and FK ids.
--    category_id FK enforced at app level (must be category_type='product').
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."10_fct_products" (
    id            VARCHAR(36)  NOT NULL,
    code          VARCHAR(96)  NOT NULL,
    name          VARCHAR(255) NOT NULL,
    category_id   SMALLINT     NOT NULL,
    is_sellable   BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    is_test       BOOLEAN      NOT NULL DEFAULT FALSE,
    deleted_at    TIMESTAMP,
    created_by    VARCHAR(36)  NOT NULL,
    updated_by    VARCHAR(36)  NOT NULL,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_iam_fct_products              PRIMARY KEY (id),
    CONSTRAINT uq_iam_fct_products_code         UNIQUE (code),
    CONSTRAINT fk_iam_fct_products_category     FOREIGN KEY (category_id)
        REFERENCES "03_iam"."06_dim_categories" (id),
    CONSTRAINT fk_iam_fct_products_created_by   FOREIGN KEY (created_by)
        REFERENCES "03_iam"."10_fct_users" (id) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT fk_iam_fct_products_updated_by   FOREIGN KEY (updated_by)
        REFERENCES "03_iam"."10_fct_users" (id) DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX idx_iam_fct_products_category_id  ON "03_iam"."10_fct_products" (category_id);
CREATE INDEX idx_iam_fct_products_is_active    ON "03_iam"."10_fct_products" (is_active)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_iam_fct_products_created_at   ON "03_iam"."10_fct_products" (created_at DESC);

COMMENT ON TABLE  "03_iam"."10_fct_products" IS
    'Platform product catalog. code and name are identity columns here '
    '(exception to pure-EAV for catalog lookups). All extended attributes '
    '(description, slug, status, pricing_tier, owner_user_id) live in 20_dtl_attrs.';
COMMENT ON COLUMN "03_iam"."10_fct_products".id          IS 'UUID v7 primary key.';
COMMENT ON COLUMN "03_iam"."10_fct_products".code        IS 'Unique machine-readable product code.';
COMMENT ON COLUMN "03_iam"."10_fct_products".name        IS 'Human-readable product name.';
COMMENT ON COLUMN "03_iam"."10_fct_products".category_id IS 'FK to 06_dim_categories (category_type=product).';
COMMENT ON COLUMN "03_iam"."10_fct_products".is_sellable IS 'TRUE if the product can be sold/subscribed to.';
COMMENT ON COLUMN "03_iam"."10_fct_products".is_active   IS 'FALSE to disable without deleting.';
COMMENT ON COLUMN "03_iam"."10_fct_products".is_test     IS 'TRUE for test/fixture rows.';
COMMENT ON COLUMN "03_iam"."10_fct_products".deleted_at  IS 'Soft-delete timestamp.';
COMMENT ON COLUMN "03_iam"."10_fct_products".created_by  IS 'Actor that created the product.';
COMMENT ON COLUMN "03_iam"."10_fct_products".updated_by  IS 'Actor that last updated the product.';
COMMENT ON COLUMN "03_iam"."10_fct_products".created_at  IS 'Row creation timestamp (UTC).';
COMMENT ON COLUMN "03_iam"."10_fct_products".updated_at  IS 'Last update timestamp (UTC).';

GRANT SELECT ON "03_iam"."10_fct_products" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE, DELETE ON "03_iam"."10_fct_products" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 8. Seed tennetctl_core product
--    Uses the first admin user as created_by/updated_by.
-- ---------------------------------------------------------------------------
INSERT INTO "03_iam"."10_fct_products"
    (id, code, name, category_id, is_sellable, is_active, created_by, updated_by)
SELECT
    '01900000-0000-7000-8000-000000000001',
    'tennetctl_core',
    'tennetctl Core Platform',
    (SELECT id FROM "03_iam"."06_dim_categories"
      WHERE category_type = 'product' AND code = 'core_platform'),
    FALSE,
    TRUE,
    u.id,
    u.id
FROM "03_iam"."10_fct_users" u
ORDER BY u.created_at ASC
LIMIT 1;

-- ---------------------------------------------------------------------------
-- 9. 40_lnk_workspace_products — workspace ↔ product subscriptions
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."40_lnk_workspace_products" (
    id             VARCHAR(36)  NOT NULL,
    workspace_id   VARCHAR(36)  NOT NULL,
    product_id     VARCHAR(36)  NOT NULL,
    subscribed_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    subscribed_by  VARCHAR(36)  NOT NULL,
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,

    CONSTRAINT pk_iam_lnk_workspace_products               PRIMARY KEY (id),
    CONSTRAINT uq_iam_lnk_workspace_products_ws_prod       UNIQUE (workspace_id, product_id),
    CONSTRAINT fk_iam_lnk_workspace_products_workspace     FOREIGN KEY (workspace_id)
        REFERENCES "03_iam"."10_fct_workspaces" (id),
    CONSTRAINT fk_iam_lnk_workspace_products_product       FOREIGN KEY (product_id)
        REFERENCES "03_iam"."10_fct_products" (id),
    CONSTRAINT fk_iam_lnk_workspace_products_subscribed_by FOREIGN KEY (subscribed_by)
        REFERENCES "03_iam"."10_fct_users" (id) DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX idx_iam_lnk_workspace_products_ws   ON "03_iam"."40_lnk_workspace_products" (workspace_id);
CREATE INDEX idx_iam_lnk_workspace_products_prod ON "03_iam"."40_lnk_workspace_products" (product_id);

COMMENT ON TABLE  "03_iam"."40_lnk_workspace_products" IS
    'M2M link between workspaces and platform products. Tracks which workspace '
    'has subscribed to which product.';
COMMENT ON COLUMN "03_iam"."40_lnk_workspace_products".id            IS 'UUID v7 primary key.';
COMMENT ON COLUMN "03_iam"."40_lnk_workspace_products".workspace_id  IS 'FK to 10_fct_workspaces.';
COMMENT ON COLUMN "03_iam"."40_lnk_workspace_products".product_id    IS 'FK to 10_fct_products.';
COMMENT ON COLUMN "03_iam"."40_lnk_workspace_products".subscribed_at IS 'When the workspace subscribed.';
COMMENT ON COLUMN "03_iam"."40_lnk_workspace_products".subscribed_by IS 'Actor that created the subscription.';
COMMENT ON COLUMN "03_iam"."40_lnk_workspace_products".is_active     IS 'FALSE when subscription is cancelled.';

GRANT SELECT ON "03_iam"."40_lnk_workspace_products" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE ON "03_iam"."40_lnk_workspace_products" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 10. fct_features — feature registry
--     Pure-EAV: all string attrs in 20_dtl_attrs.
--     Exception: code+name stored on fct for lookup performance.
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."10_fct_features" (
    id          VARCHAR(36)  NOT NULL,
    product_id  VARCHAR(36)  NOT NULL,
    parent_id   VARCHAR(36),
    code        VARCHAR(96)  NOT NULL,
    name        VARCHAR(255) NOT NULL,
    scope_id    SMALLINT     NOT NULL,
    category_id SMALLINT     NOT NULL,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    is_test     BOOLEAN      NOT NULL DEFAULT FALSE,
    deleted_at  TIMESTAMP,
    created_by  VARCHAR(36)  NOT NULL,
    updated_by  VARCHAR(36)  NOT NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_iam_fct_features              PRIMARY KEY (id),
    CONSTRAINT uq_iam_fct_features_product_code UNIQUE (product_id, code),
    CONSTRAINT fk_iam_fct_features_product      FOREIGN KEY (product_id)
        REFERENCES "03_iam"."10_fct_products" (id),
    CONSTRAINT fk_iam_fct_features_parent       FOREIGN KEY (parent_id)
        REFERENCES "03_iam"."10_fct_features" (id),
    CONSTRAINT fk_iam_fct_features_scope        FOREIGN KEY (scope_id)
        REFERENCES "03_iam"."06_dim_scopes" (id),
    CONSTRAINT fk_iam_fct_features_category     FOREIGN KEY (category_id)
        REFERENCES "03_iam"."06_dim_categories" (id),
    CONSTRAINT fk_iam_fct_features_created_by   FOREIGN KEY (created_by)
        REFERENCES "03_iam"."10_fct_users" (id) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT fk_iam_fct_features_updated_by   FOREIGN KEY (updated_by)
        REFERENCES "03_iam"."10_fct_users" (id) DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX idx_iam_fct_features_product_id  ON "03_iam"."10_fct_features" (product_id);
CREATE INDEX idx_iam_fct_features_parent_id   ON "03_iam"."10_fct_features" (parent_id)
    WHERE parent_id IS NOT NULL;
CREATE INDEX idx_iam_fct_features_scope_id    ON "03_iam"."10_fct_features" (scope_id);
CREATE INDEX idx_iam_fct_features_category_id ON "03_iam"."10_fct_features" (category_id);
CREATE INDEX idx_iam_fct_features_is_active   ON "03_iam"."10_fct_features" (is_active)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_iam_fct_features_created_at  ON "03_iam"."10_fct_features" (created_at DESC);

COMMENT ON TABLE  "03_iam"."10_fct_features" IS
    'Feature registry. Tracks every platform feature: which product it belongs '
    'to, its scope (platform/org/workspace), category, and optional parent for '
    'hierarchical features. Extended attrs (description, status, doc_url, '
    'owner_user_id, version_introduced) live in 20_dtl_attrs.';
COMMENT ON COLUMN "03_iam"."10_fct_features".id          IS 'UUID v7 primary key.';
COMMENT ON COLUMN "03_iam"."10_fct_features".product_id  IS 'FK to 10_fct_products. The owning product.';
COMMENT ON COLUMN "03_iam"."10_fct_features".parent_id   IS 'Optional FK to self for hierarchical features.';
COMMENT ON COLUMN "03_iam"."10_fct_features".code        IS 'Machine-readable code, unique within a product.';
COMMENT ON COLUMN "03_iam"."10_fct_features".name        IS 'Human-readable feature name.';
COMMENT ON COLUMN "03_iam"."10_fct_features".scope_id    IS 'FK to 06_dim_scopes. platform | org | workspace.';
COMMENT ON COLUMN "03_iam"."10_fct_features".category_id IS 'FK to 06_dim_categories (category_type=feature).';
COMMENT ON COLUMN "03_iam"."10_fct_features".is_active   IS 'FALSE to disable without deleting.';
COMMENT ON COLUMN "03_iam"."10_fct_features".is_test     IS 'TRUE for test/fixture rows.';
COMMENT ON COLUMN "03_iam"."10_fct_features".deleted_at  IS 'Soft-delete timestamp.';
COMMENT ON COLUMN "03_iam"."10_fct_features".created_by  IS 'Actor that created the feature.';
COMMENT ON COLUMN "03_iam"."10_fct_features".updated_by  IS 'Actor that last updated the feature.';
COMMENT ON COLUMN "03_iam"."10_fct_features".created_at  IS 'Row creation timestamp (UTC).';
COMMENT ON COLUMN "03_iam"."10_fct_features".updated_at  IS 'Last update timestamp (UTC).';

GRANT SELECT ON "03_iam"."10_fct_features" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE, DELETE ON "03_iam"."10_fct_features" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 11. v_products — pivoted view for product reads
-- ---------------------------------------------------------------------------
CREATE VIEW "03_iam".v_products AS
SELECT
    p.id,
    p.code,
    p.name,
    p.category_id,
    c.code                                                               AS category_code,
    c.label                                                              AS category_label,
    p.is_sellable,
    p.is_active,
    (p.deleted_at IS NOT NULL)                                           AS is_deleted,
    MAX(CASE WHEN ad.code = 'description'   THEN a.key_text END)        AS description,
    MAX(CASE WHEN ad.code = 'slug'          THEN a.key_text END)        AS slug,
    MAX(CASE WHEN ad.code = 'status'        THEN a.key_text END)        AS status,
    MAX(CASE WHEN ad.code = 'pricing_tier'  THEN a.key_text END)        AS pricing_tier,
    MAX(CASE WHEN ad.code = 'owner_user_id' THEN a.key_text END)        AS owner_user_id,
    p.created_by,
    p.updated_by,
    p.created_at,
    p.updated_at
FROM "03_iam"."10_fct_products" p
LEFT JOIN "03_iam"."06_dim_categories" c ON c.id = p.category_id
LEFT JOIN "03_iam"."20_dtl_attrs" a
       ON a.entity_type_id = (SELECT id FROM "03_iam"."06_dim_entity_types" WHERE code = 'platform_product')
      AND a.entity_id = p.id
LEFT JOIN "03_iam"."07_dim_attr_defs" ad ON ad.id = a.attr_def_id
GROUP BY p.id, p.code, p.name, p.category_id, c.code, c.label,
         p.is_sellable, p.is_active, p.deleted_at,
         p.created_by, p.updated_by, p.created_at, p.updated_at;

COMMENT ON VIEW "03_iam".v_products IS
    'Products with EAV attrs pivoted and category code/label resolved.';

GRANT SELECT ON "03_iam".v_products TO tennetctl_read;
GRANT SELECT ON "03_iam".v_products TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 12. v_features — pivoted view for feature reads
-- ---------------------------------------------------------------------------
CREATE VIEW "03_iam".v_features AS
SELECT
    f.id,
    f.product_id,
    f.parent_id,
    f.code,
    f.name,
    f.scope_id,
    s.code                                                                   AS scope_code,
    s.label                                                                  AS scope_label,
    f.category_id,
    c.code                                                                   AS category_code,
    c.label                                                                  AS category_label,
    f.is_active,
    (f.deleted_at IS NOT NULL)                                               AS is_deleted,
    MAX(CASE WHEN ad.code = 'description'        THEN a.key_text END)        AS description,
    MAX(CASE WHEN ad.code = 'status'             THEN a.key_text END)        AS status,
    MAX(CASE WHEN ad.code = 'doc_url'            THEN a.key_text END)        AS doc_url,
    MAX(CASE WHEN ad.code = 'owner_user_id'      THEN a.key_text END)        AS owner_user_id,
    MAX(CASE WHEN ad.code = 'version_introduced' THEN a.key_text END)        AS version_introduced,
    f.created_by,
    f.updated_by,
    f.created_at,
    f.updated_at
FROM "03_iam"."10_fct_features" f
LEFT JOIN "03_iam"."06_dim_scopes" s ON s.id = f.scope_id
LEFT JOIN "03_iam"."06_dim_categories" c ON c.id = f.category_id
LEFT JOIN "03_iam"."20_dtl_attrs" a
       ON a.entity_type_id = (SELECT id FROM "03_iam"."06_dim_entity_types" WHERE code = 'platform_feature')
      AND a.entity_id = f.id
LEFT JOIN "03_iam"."07_dim_attr_defs" ad ON ad.id = a.attr_def_id
GROUP BY f.id, f.product_id, f.parent_id, f.code, f.name,
         f.scope_id, s.code, s.label,
         f.category_id, c.code, c.label,
         f.is_active, f.deleted_at,
         f.created_by, f.updated_by, f.created_at, f.updated_at;

COMMENT ON VIEW "03_iam".v_features IS
    'Features with EAV attrs pivoted and scope/category code+label resolved.';

GRANT SELECT ON "03_iam".v_features TO tennetctl_read;
GRANT SELECT ON "03_iam".v_features TO tennetctl_write;

-- DOWN =======================================================================

DROP VIEW  IF EXISTS "03_iam".v_features;
DROP VIEW  IF EXISTS "03_iam".v_products;
DROP TABLE IF EXISTS "03_iam"."10_fct_features";
DROP TABLE IF EXISTS "03_iam"."40_lnk_workspace_products";
DROP TABLE IF EXISTS "03_iam"."10_fct_products";

-- Remove EAV registrations for platform_feature and platform_product
DELETE FROM "03_iam"."07_dim_attr_defs"
 WHERE entity_type_id IN (
     SELECT id FROM "03_iam"."06_dim_entity_types"
      WHERE code IN ('platform_product', 'platform_feature')
 );

DELETE FROM "03_iam"."06_dim_entity_types"
 WHERE code IN ('platform_product', 'platform_feature');

DROP TABLE IF EXISTS "03_iam"."06_dim_environments";
DROP TABLE IF EXISTS "03_iam"."06_dim_categories";
DROP TABLE IF EXISTS "03_iam"."06_dim_scopes";
