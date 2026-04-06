-- =============================================================================
-- Migration: 20260403_003_org_prefix_tables.sql
-- Module:    02_iam / sub-feature: 01_org
-- Description: Prefix all org sub-feature tables, views, and sequences with
--   "01_" so each sub-feature is self-contained and namespaced.
--   Pattern: {nn}_{type}_{name}  →  {sf}_{nn}_{type}_{name}
--            dim_{name}           →  01_dim_{name}
--            v_{name}             →  01_v_{name}
--            seq_{name}           →  01_seq_{name}
-- =============================================================================

-- UP ==========================================================================

-- 1. Drop view (must drop before renaming tables it depends on)
DROP VIEW IF EXISTS "02_iam".v_orgs;

-- 2. Rename tables
ALTER TABLE "02_iam"."11_fct_orgs"      RENAME TO "01_11_fct_orgs";
ALTER TABLE "02_iam"."20_dtl_attrs"     RENAME TO "01_20_dtl_attrs";
ALTER TABLE "02_iam"."60_evt_audit_log" RENAME TO "01_60_evt_audit_log";
ALTER TABLE "02_iam".dim_attr_defs      RENAME TO "01_dim_attr_defs";
ALTER TABLE "02_iam".dim_entity_types   RENAME TO "01_dim_entity_types";
ALTER TABLE "02_iam".dim_org_statuses   RENAME TO "01_dim_org_statuses";

-- 3. Rename sequence
ALTER SEQUENCE "02_iam".seq_custom_attr_def_id RENAME TO "01_seq_custom_attr_def_id";

-- 4. Recreate v_orgs as 01_v_orgs with updated table references
CREATE VIEW "02_iam"."v_01_orgs" AS
SELECT
    o.id,
    o.is_active,
    o.is_test,
    s.code                                                                         AS status,
    o.deleted_at,
    o.created_by,
    o.updated_by,
    o.created_at,
    o.updated_at,
    MAX(CASE WHEN a.attr_def_id = 10 THEN a.key_text END)                         AS slug,
    MAX(CASE WHEN a.attr_def_id = 11 THEN a.key_text END)                         AS display_name,
    MAX(CASE WHEN a.attr_def_id = 13 THEN a.key_text END)                         AS description,
    COALESCE(
        MAX(CASE WHEN a.attr_def_id = 14 THEN a.key_jsonb::text END)::jsonb,
        '[]'::jsonb
    )                                                                              AS tags,
    COALESCE(
        jsonb_object_agg(d.code, COALESCE(a.key_jsonb, to_jsonb(a.key_text)))
            FILTER (WHERE d.id >= 1000 AND d.id IS NOT NULL),
        '{}'::jsonb
    )                                                                              AS custom_attrs
FROM "02_iam"."01_11_fct_orgs"      o
JOIN "02_iam"."01_dim_org_statuses"  s  ON s.id = o.org_status_id
LEFT JOIN "02_iam"."01_20_dtl_attrs" a  ON a.entity_id = o.id AND a.entity_type_id = 2
LEFT JOIN "02_iam"."01_dim_attr_defs" d ON d.id = a.attr_def_id
GROUP BY o.id, s.code;

COMMENT ON VIEW "02_iam"."v_01_orgs"
    IS 'Read-only org view. System attrs pivoted; custom attrs aggregated into custom_attrs JSONB.';

-- DOWN ========================================================================

DROP VIEW IF EXISTS "02_iam"."v_01_orgs";

ALTER SEQUENCE "02_iam"."01_seq_custom_attr_def_id" RENAME TO seq_custom_attr_def_id;

ALTER TABLE "02_iam"."01_dim_org_statuses"   RENAME TO dim_org_statuses;
ALTER TABLE "02_iam"."01_dim_entity_types"   RENAME TO dim_entity_types;
ALTER TABLE "02_iam"."01_dim_attr_defs"      RENAME TO dim_attr_defs;
ALTER TABLE "02_iam"."01_11_fct_orgs"        RENAME TO "11_fct_orgs";
ALTER TABLE "02_iam"."01_20_dtl_attrs"       RENAME TO "20_dtl_attrs";
ALTER TABLE "02_iam"."01_60_evt_audit_log"   RENAME TO "60_evt_audit_log";

CREATE VIEW "02_iam".v_orgs AS
SELECT
    o.id, o.is_active, o.is_test, s.code AS status,
    o.deleted_at, o.created_by, o.updated_by, o.created_at, o.updated_at,
    MAX(CASE WHEN a.attr_def_id = 10 THEN a.key_text END) AS slug,
    MAX(CASE WHEN a.attr_def_id = 11 THEN a.key_text END) AS display_name,
    MAX(CASE WHEN a.attr_def_id = 13 THEN a.key_text END) AS description,
    COALESCE(MAX(CASE WHEN a.attr_def_id = 14 THEN a.key_jsonb::text END)::jsonb, '[]'::jsonb) AS tags,
    COALESCE(jsonb_object_agg(d.code, COALESCE(a.key_jsonb, to_jsonb(a.key_text)))
        FILTER (WHERE d.id >= 1000 AND d.id IS NOT NULL), '{}'::jsonb) AS custom_attrs
FROM "02_iam"."11_fct_orgs" o
JOIN "02_iam".dim_org_statuses s ON s.id = o.org_status_id
LEFT JOIN "02_iam"."20_dtl_attrs" a ON a.entity_id = o.id AND a.entity_type_id = 2
LEFT JOIN "02_iam".dim_attr_defs d ON d.id = a.attr_def_id
GROUP BY o.id, s.code;
