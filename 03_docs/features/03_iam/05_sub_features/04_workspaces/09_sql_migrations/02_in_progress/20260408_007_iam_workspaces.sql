-- =============================================================================
-- Migration:   20260408_007_iam_workspaces.sql
-- Module:      03_iam / Sub-feature: 04_workspaces / Sequence: 007
-- Depends on:  006 (orgs)
-- =============================================================================

-- UP ====

CREATE TABLE "03_iam"."02_dim_workspace_statuses" (
    id            SMALLINT    GENERATED ALWAYS AS IDENTITY,
    code          TEXT        NOT NULL,
    label         TEXT        NOT NULL,
    description   TEXT,
    deprecated_at TIMESTAMP,
    CONSTRAINT pk_iam_dim_workspace_statuses      PRIMARY KEY (id),
    CONSTRAINT uq_iam_dim_workspace_statuses_code UNIQUE (code)
);
INSERT INTO "03_iam"."02_dim_workspace_statuses" (code, label, description) VALUES
    ('active',   'Active',   'Workspace is live and usable.'),
    ('archived', 'Archived', 'Workspace has been archived. Read-only.');
GRANT SELECT ON "03_iam"."02_dim_workspace_statuses" TO tennetctl_read;
GRANT SELECT ON "03_iam"."02_dim_workspace_statuses" TO tennetctl_write;

CREATE TABLE "03_iam"."10_fct_workspaces" (
    id          VARCHAR(36) NOT NULL,
    org_id      VARCHAR(36) NOT NULL,
    status_id   SMALLINT    NOT NULL,
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    is_test     BOOLEAN     NOT NULL DEFAULT FALSE,
    created_by  VARCHAR(36) NOT NULL,
    updated_by  VARCHAR(36) NOT NULL,
    created_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_iam_fct_workspaces             PRIMARY KEY (id),
    CONSTRAINT fk_iam_fct_workspaces_org         FOREIGN KEY (org_id)
        REFERENCES "03_iam"."10_fct_orgs" (id),
    CONSTRAINT fk_iam_fct_workspaces_status      FOREIGN KEY (status_id)
        REFERENCES "03_iam"."02_dim_workspace_statuses" (id),
    CONSTRAINT fk_iam_fct_workspaces_created_by  FOREIGN KEY (created_by)
        REFERENCES "03_iam"."10_fct_users" (id) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT fk_iam_fct_workspaces_updated_by  FOREIGN KEY (updated_by)
        REFERENCES "03_iam"."10_fct_users" (id) DEFERRABLE INITIALLY DEFERRED
);
COMMENT ON TABLE "03_iam"."10_fct_workspaces" IS 'Workspace identity. A department inside an org. Pure-EAV. No deleted_at: archive via is_active=false.';
CREATE INDEX idx_iam_fct_workspaces_org_id     ON "03_iam"."10_fct_workspaces" (org_id);
CREATE INDEX idx_iam_fct_workspaces_is_active  ON "03_iam"."10_fct_workspaces" (is_active);
CREATE INDEX idx_iam_fct_workspaces_created_at ON "03_iam"."10_fct_workspaces" (created_at DESC);
GRANT SELECT, INSERT, UPDATE ON "03_iam"."10_fct_workspaces" TO tennetctl_write;
GRANT SELECT ON "03_iam"."10_fct_workspaces" TO tennetctl_read;

-- Slug lookup index (per-org uniqueness enforced at app layer)
DO $$
DECLARE slug_attr_id SMALLINT;
BEGIN
    SELECT d.id INTO slug_attr_id
      FROM "03_iam"."07_dim_attr_defs" d
      JOIN "03_iam"."06_dim_entity_types" et ON d.entity_type_id = et.id
     WHERE et.code = 'iam_workspace' AND d.code = 'slug';
    EXECUTE format(
      'CREATE INDEX idx_iam_dtl_attrs_workspace_slug ON "03_iam"."20_dtl_attrs" (key_text) WHERE attr_def_id = %s',
      slug_attr_id);
END $$;

-- v_workspaces
CREATE VIEW "03_iam".v_workspaces AS
SELECT
    w.id,
    w.org_id,
    s.code AS status,
    MAX(CASE WHEN ad.code = 'name'        THEN a.key_text END) AS name,
    MAX(CASE WHEN ad.code = 'slug'        THEN a.key_text END) AS slug,
    MAX(CASE WHEN ad.code = 'description' THEN a.key_text END) AS description,
    MAX(CASE WHEN ad.code = 'icon'        THEN a.key_text END) AS icon,
    w.is_active,
    w.is_test,
    w.created_by,
    w.updated_by,
    w.created_at,
    w.updated_at
FROM "03_iam"."10_fct_workspaces" w
JOIN "03_iam"."02_dim_workspace_statuses" s ON w.status_id = s.id
LEFT JOIN "03_iam"."20_dtl_attrs" a
       ON a.entity_type_id = (SELECT id FROM "03_iam"."06_dim_entity_types" WHERE code = 'iam_workspace')
      AND a.entity_id = w.id
LEFT JOIN "03_iam"."07_dim_attr_defs" ad ON ad.id = a.attr_def_id
GROUP BY w.id, w.org_id, s.code, w.is_active, w.is_test, w.created_by, w.updated_by, w.created_at, w.updated_at;

GRANT SELECT ON "03_iam".v_workspaces TO tennetctl_read;
GRANT SELECT ON "03_iam".v_workspaces TO tennetctl_write;

-- DOWN ====
DROP VIEW  IF EXISTS "03_iam".v_workspaces;
DROP INDEX IF EXISTS "03_iam".idx_iam_dtl_attrs_workspace_slug;
DROP TABLE IF EXISTS "03_iam"."10_fct_workspaces";
DROP TABLE IF EXISTS "03_iam"."02_dim_workspace_statuses";
