-- =============================================================================
-- Migration: 20260403_006c_iam_workspaces.sql
-- Sub-feature: 03_workspace
-- Description: Workspace identity — fct, dtl (EAV), and read view.
-- UP
-- =============================================================================

SET search_path TO "02_iam", public;

-- Entity type
INSERT INTO "02_iam"."01_dim_org_entity_types" (id, code, label, description) VALUES
    (3, 'workspace', 'Workspace', 'Org-scoped workspace');

-- Workspace EAV attribute definitions
CREATE TABLE "02_iam"."06_dim_ws_attr_defs" (
    id              SMALLINT    NOT NULL,
    entity_type_id  SMALLINT    NOT NULL DEFAULT 3,
    code            TEXT        NOT NULL,
    label           TEXT        NOT NULL,
    value_type      TEXT        NOT NULL,
    is_system       BOOLEAN     NOT NULL DEFAULT true,
    description     TEXT        NOT NULL DEFAULT '',
    deprecated_at   TIMESTAMP,
    CONSTRAINT pk_06_dim_ws_attr_defs         PRIMARY KEY (id),
    CONSTRAINT uq_06_dim_ws_attr_defs_code    UNIQUE (entity_type_id, code),
    CONSTRAINT chk_06_dim_ws_attr_defs_vtype  CHECK (value_type IN ('text', 'jsonb')),
    CONSTRAINT fk_06_dim_ws_attr_defs_etype   FOREIGN KEY (entity_type_id)
        REFERENCES "02_iam"."01_dim_org_entity_types"(id)
);
COMMENT ON TABLE "02_iam"."06_dim_ws_attr_defs" IS 'Workspace EAV attribute definitions.';

INSERT INTO "02_iam"."06_dim_ws_attr_defs" (id, entity_type_id, code, label, value_type, description) VALUES
    (20, 3, 'slug',         'Slug',         'text',  'URL-safe workspace identifier'),
    (21, 3, 'display_name', 'Display Name', 'text',  'Human-readable name'),
    (22, 3, 'settings',     'Settings',     'jsonb', 'Workspace config');

-- Workspace identity table
CREATE TABLE "02_iam"."12_fct_ws_workspaces" (
    id          VARCHAR(36) NOT NULL,
    org_id      VARCHAR(36) NOT NULL,
    is_active   BOOLEAN     NOT NULL DEFAULT true,
    is_test     BOOLEAN     NOT NULL DEFAULT false,
    deleted_at  TIMESTAMP,
    created_by  VARCHAR(36),
    updated_by  VARCHAR(36),
    created_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_12_fct_ws_workspaces PRIMARY KEY (id)
);
COMMENT ON TABLE "02_iam"."12_fct_ws_workspaces" IS 'Workspace identity. Org-scoped.';

CREATE INDEX idx_12_fct_ws_live ON "02_iam"."12_fct_ws_workspaces" (org_id, created_at DESC) WHERE deleted_at IS NULL;

CREATE TRIGGER trg_12_fct_ws_updated_at BEFORE UPDATE ON "02_iam"."12_fct_ws_workspaces"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- Workspace EAV attributes
CREATE TABLE "02_iam"."21_dtl_ws_attrs" (
    entity_type_id  SMALLINT    NOT NULL DEFAULT 3,
    entity_id       VARCHAR(36) NOT NULL,
    attr_def_id     SMALLINT    NOT NULL,
    key_text        TEXT,
    key_jsonb       JSONB,
    created_by      VARCHAR(36),
    updated_by      VARCHAR(36),
    created_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_21_dtl_ws_attrs             PRIMARY KEY (entity_type_id, entity_id, attr_def_id),
    CONSTRAINT fk_21_dtl_ws_attrs_entity_type FOREIGN KEY (entity_type_id)
        REFERENCES "02_iam"."01_dim_org_entity_types"(id),
    CONSTRAINT fk_21_dtl_ws_attrs_attr_def    FOREIGN KEY (attr_def_id)
        REFERENCES "02_iam"."06_dim_ws_attr_defs"(id)
);
COMMENT ON TABLE "02_iam"."21_dtl_ws_attrs" IS 'Workspace EAV attributes.';

CREATE INDEX idx_21_dtl_ws_attrs_entity ON "02_iam"."21_dtl_ws_attrs" (entity_id);

CREATE TRIGGER trg_21_dtl_ws_attrs_updated_at BEFORE UPDATE ON "02_iam"."21_dtl_ws_attrs"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- Workspace read view
CREATE VIEW "02_iam"."v_12_ws_workspaces" AS
SELECT
    w.id, w.org_id, w.is_active, w.is_test,
    w.deleted_at, w.created_by, w.updated_by, w.created_at, w.updated_at,
    MAX(CASE WHEN a.attr_def_id = 20 THEN a.key_text END) AS slug,
    MAX(CASE WHEN a.attr_def_id = 21 THEN a.key_text END) AS display_name,
    COALESCE(MAX(CASE WHEN a.attr_def_id = 22 THEN a.key_jsonb::text END)::jsonb, '{}'::jsonb) AS settings
FROM "02_iam"."12_fct_ws_workspaces" w
LEFT JOIN "02_iam"."21_dtl_ws_attrs" a ON a.entity_id = w.id AND a.entity_type_id = 3
GROUP BY w.id;
COMMENT ON VIEW "02_iam"."v_12_ws_workspaces" IS 'Workspace read view. Pivots slug + display_name from EAV.';

-- =============================================================================
-- DOWN
-- =============================================================================

DROP VIEW  IF EXISTS "02_iam"."v_12_ws_workspaces";
DROP TABLE IF EXISTS "02_iam"."21_dtl_ws_attrs";
DROP TABLE IF EXISTS "02_iam"."12_fct_ws_workspaces";
DROP TABLE IF EXISTS "02_iam"."06_dim_ws_attr_defs";
DELETE FROM "02_iam"."01_dim_org_entity_types" WHERE id = 3;
