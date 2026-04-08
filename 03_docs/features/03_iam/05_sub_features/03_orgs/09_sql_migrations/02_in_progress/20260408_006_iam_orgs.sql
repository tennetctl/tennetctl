-- =============================================================================
-- Migration:   20260408_006_iam_orgs.sql
-- Module:      03_iam / Sub-feature: 03_orgs / Sequence: 006
-- Depends on:  005 (audit), 003 (iam_bootstrap with iam_org entity type + attr_defs)
-- =============================================================================

-- UP ====

CREATE TABLE "03_iam"."01_dim_org_statuses" (
    id            SMALLINT    GENERATED ALWAYS AS IDENTITY,
    code          TEXT        NOT NULL,
    label         TEXT        NOT NULL,
    description   TEXT,
    deprecated_at TIMESTAMP,
    CONSTRAINT pk_iam_dim_org_statuses      PRIMARY KEY (id),
    CONSTRAINT uq_iam_dim_org_statuses_code UNIQUE (code)
);
INSERT INTO "03_iam"."01_dim_org_statuses" (code, label, description) VALUES
    ('active',   'Active',   'Org is live and usable.'),
    ('archived', 'Archived', 'Org has been archived. Read-only.');
GRANT SELECT ON "03_iam"."01_dim_org_statuses" TO tennetctl_read;
GRANT SELECT ON "03_iam"."01_dim_org_statuses" TO tennetctl_write;

CREATE TABLE "03_iam"."10_fct_orgs" (
    id          VARCHAR(36) NOT NULL,
    status_id   SMALLINT    NOT NULL,
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    is_test     BOOLEAN     NOT NULL DEFAULT FALSE,
    created_by  VARCHAR(36) NOT NULL,
    updated_by  VARCHAR(36) NOT NULL,
    created_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_iam_fct_orgs             PRIMARY KEY (id),
    CONSTRAINT fk_iam_fct_orgs_status      FOREIGN KEY (status_id)
        REFERENCES "03_iam"."01_dim_org_statuses" (id),
    CONSTRAINT fk_iam_fct_orgs_created_by  FOREIGN KEY (created_by)
        REFERENCES "03_iam"."10_fct_users" (id) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT fk_iam_fct_orgs_updated_by  FOREIGN KEY (updated_by)
        REFERENCES "03_iam"."10_fct_users" (id) DEFERRABLE INITIALLY DEFERRED
);
COMMENT ON TABLE "03_iam"."10_fct_orgs" IS 'Org identity. Pure-EAV — name, slug, description live in 20_dtl_attrs. Orgs have NO deleted_at: archival via is_active=false.';
CREATE INDEX idx_iam_fct_orgs_is_active  ON "03_iam"."10_fct_orgs" (is_active);
CREATE INDEX idx_iam_fct_orgs_created_at ON "03_iam"."10_fct_orgs" (created_at DESC);
GRANT SELECT, INSERT, UPDATE ON "03_iam"."10_fct_orgs" TO tennetctl_write;
GRANT SELECT ON "03_iam"."10_fct_orgs" TO tennetctl_read;

-- Global slug uniqueness via DO block (resolves attr_def_id by code)
DO $$
DECLARE slug_attr_id SMALLINT;
BEGIN
    SELECT d.id INTO slug_attr_id
      FROM "03_iam"."07_dim_attr_defs" d
      JOIN "03_iam"."06_dim_entity_types" et ON d.entity_type_id = et.id
     WHERE et.code = 'iam_org' AND d.code = 'slug';
    EXECUTE format(
      'CREATE UNIQUE INDEX uq_iam_dtl_attrs_org_slug ON "03_iam"."20_dtl_attrs" (key_text) WHERE attr_def_id = %s AND key_text IS NOT NULL',
      slug_attr_id);
END $$;

-- v_orgs pivots EAV attrs
CREATE VIEW "03_iam".v_orgs AS
SELECT
    o.id,
    s.code AS status,
    MAX(CASE WHEN ad.code = 'name'          THEN a.key_text END) AS name,
    MAX(CASE WHEN ad.code = 'slug'          THEN a.key_text END) AS slug,
    MAX(CASE WHEN ad.code = 'description'   THEN a.key_text END) AS description,
    MAX(CASE WHEN ad.code = 'logo_url'      THEN a.key_text END) AS logo_url,
    MAX(CASE WHEN ad.code = 'billing_email' THEN a.key_text END) AS billing_email,
    o.is_active,
    o.is_test,
    o.created_by,
    o.updated_by,
    o.created_at,
    o.updated_at
FROM "03_iam"."10_fct_orgs" o
JOIN "03_iam"."01_dim_org_statuses" s ON o.status_id = s.id
LEFT JOIN "03_iam"."20_dtl_attrs" a
       ON a.entity_type_id = (SELECT id FROM "03_iam"."06_dim_entity_types" WHERE code = 'iam_org')
      AND a.entity_id = o.id
LEFT JOIN "03_iam"."07_dim_attr_defs" ad ON ad.id = a.attr_def_id
GROUP BY o.id, s.code, o.is_active, o.is_test, o.created_by, o.updated_by, o.created_at, o.updated_at;

GRANT SELECT ON "03_iam".v_orgs TO tennetctl_read;
GRANT SELECT ON "03_iam".v_orgs TO tennetctl_write;

-- DOWN ====
DROP VIEW  IF EXISTS "03_iam".v_orgs;
DROP INDEX IF EXISTS "03_iam".uq_iam_dtl_attrs_org_slug;
DROP TABLE IF EXISTS "03_iam"."10_fct_orgs";
DROP TABLE IF EXISTS "03_iam"."01_dim_org_statuses";
