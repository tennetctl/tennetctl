-- =============================================================================
-- Migration: 20260403_002_org_eav_per_row.sql
-- Module:    02_iam
-- Description: Replace single settings JSONB blob with proper per-row EAV.
--   - Adds is_system flag to dim_attr_defs
--   - Registers description (13) and tags (14) as system attrs
--   - Creates sequence for user-defined custom attr IDs (starts at 1000)
--   - Migrates any existing settings blobs into individual EAV rows
--   - Deprecates settings attr_def (12) and removes its EAV rows
--   - Rebuilds v_orgs: adds description, tags, and custom_attrs columns
-- =============================================================================

-- UP ==========================================================================

-- 1. Add is_system column to dim_attr_defs
ALTER TABLE "02_iam".dim_attr_defs
    ADD COLUMN is_system BOOLEAN NOT NULL DEFAULT false;
COMMENT ON COLUMN "02_iam".dim_attr_defs.is_system
    IS 'True for built-in attrs (slug, display_name, description, tags). Cannot be deleted via API.';

UPDATE "02_iam".dim_attr_defs SET is_system = true WHERE id IN (10, 11);

-- 2. Register new system attr_defs
INSERT INTO "02_iam".dim_attr_defs (id, entity_type_id, code, label, value_type, is_pii, is_system, description) VALUES
    (13, 2, 'description', 'Description', 'text',  false, true,  'Human-readable description of the org'),
    (14, 2, 'tags',        'Tags',        'jsonb', false, true,  'Array of string tags for classification');

-- 3. Sequence for user-defined custom attr_defs (org-scoped, entity_type_id=2)
CREATE SEQUENCE "02_iam".seq_custom_attr_def_id
    START WITH 1000
    INCREMENT BY 1
    NO CYCLE;
COMMENT ON SEQUENCE "02_iam".seq_custom_attr_def_id
    IS 'Auto-incremented IDs for user-defined org attribute definitions. IDs >= 1000 are custom.';

-- 4. Migrate existing settings blobs into individual EAV rows
--    For each org with a settings blob, split top-level keys into separate rows.
--    Scalar strings  → key_text
--    Objects/arrays  → key_jsonb
--    __tags__ key    → attr_def 14 (jsonb array)
DO $$
DECLARE
    rec      RECORD;
    kv       RECORD;
    attr_id  SMALLINT;
    existing SMALLINT;
BEGIN
    FOR rec IN
        SELECT entity_id, key_jsonb
        FROM "02_iam"."20_dtl_attrs"
        WHERE attr_def_id = 12 AND entity_type_id = 2
    LOOP
        FOR kv IN
            SELECT key, value
            FROM jsonb_each(rec.key_jsonb)
        LOOP
            IF kv.key = '__tags__' THEN
                -- Migrate to tags attr_def 14
                INSERT INTO "02_iam"."20_dtl_attrs"
                    (entity_type_id, entity_id, attr_def_id, key_jsonb)
                VALUES (2, rec.entity_id, 14, kv.value)
                ON CONFLICT (entity_type_id, entity_id, attr_def_id)
                DO UPDATE SET key_jsonb = EXCLUDED.key_jsonb;

            ELSIF jsonb_typeof(kv.value) = 'string' THEN
                -- Register or find custom attr_def for this key
                SELECT id INTO existing
                FROM "02_iam".dim_attr_defs
                WHERE entity_type_id = 2 AND code = kv.key;

                IF existing IS NULL THEN
                    attr_id := nextval('"02_iam".seq_custom_attr_def_id');
                    INSERT INTO "02_iam".dim_attr_defs
                        (id, entity_type_id, code, label, value_type, is_system)
                    VALUES (attr_id, 2, kv.key, kv.key, 'text', false);
                ELSE
                    attr_id := existing;
                END IF;

                INSERT INTO "02_iam"."20_dtl_attrs"
                    (entity_type_id, entity_id, attr_def_id, key_text)
                VALUES (2, rec.entity_id, attr_id, kv.value #>> '{}')
                ON CONFLICT (entity_type_id, entity_id, attr_def_id)
                DO UPDATE SET key_text = EXCLUDED.key_text;

            ELSE
                -- Object or array → jsonb custom attr
                SELECT id INTO existing
                FROM "02_iam".dim_attr_defs
                WHERE entity_type_id = 2 AND code = kv.key;

                IF existing IS NULL THEN
                    attr_id := nextval('"02_iam".seq_custom_attr_def_id');
                    INSERT INTO "02_iam".dim_attr_defs
                        (id, entity_type_id, code, label, value_type, is_system)
                    VALUES (attr_id, 2, kv.key, kv.key, 'jsonb', false);
                ELSE
                    attr_id := existing;
                END IF;

                INSERT INTO "02_iam"."20_dtl_attrs"
                    (entity_type_id, entity_id, attr_def_id, key_jsonb)
                VALUES (2, rec.entity_id, attr_id, kv.value)
                ON CONFLICT (entity_type_id, entity_id, attr_def_id)
                DO UPDATE SET key_jsonb = EXCLUDED.key_jsonb;
            END IF;
        END LOOP;
    END LOOP;
END;
$$;

-- 5. Remove old settings blob rows and deprecate the attr_def
DELETE FROM "02_iam"."20_dtl_attrs" WHERE attr_def_id = 12;
UPDATE "02_iam".dim_attr_defs SET deprecated_at = CURRENT_TIMESTAMP WHERE id = 12;

-- 6. Rebuild v_orgs: add description, tags, custom_attrs; remove settings
DROP VIEW "02_iam".v_orgs;

CREATE OR REPLACE VIEW "02_iam".v_orgs AS
SELECT
    o.id,
    o.is_active,
    o.is_test,
    s.code                                  AS status,
    o.deleted_at,
    o.created_by,
    o.updated_by,
    o.created_at,
    o.updated_at,
    MAX(CASE WHEN a.attr_def_id = 10 THEN a.key_text END)                       AS slug,
    MAX(CASE WHEN a.attr_def_id = 11 THEN a.key_text END)                       AS display_name,
    MAX(CASE WHEN a.attr_def_id = 13 THEN a.key_text END)                       AS description,
    COALESCE(
        MAX(CASE WHEN a.attr_def_id = 14 THEN a.key_jsonb END),
        '[]'::jsonb
    )                                                                            AS tags,
    COALESCE(
        jsonb_object_agg(d.code, COALESCE(a.key_jsonb, to_jsonb(a.key_text)))
            FILTER (WHERE a.attr_def_id >= 1000 AND a.attr_def_id IS NOT NULL),
        '{}'::jsonb
    )                                                                            AS custom_attrs
FROM "02_iam"."11_fct_orgs"     o
JOIN "02_iam".dim_org_statuses  s ON s.id = o.org_status_id
LEFT JOIN "02_iam"."20_dtl_attrs" a  ON a.entity_id = o.id AND a.entity_type_id = 2
LEFT JOIN "02_iam".dim_attr_defs  d  ON d.id = a.attr_def_id
GROUP BY o.id, s.code;

COMMENT ON VIEW "02_iam".v_orgs IS 'Read-only org view. System attrs pivoted; custom attrs aggregated into custom_attrs JSONB map.';

-- DOWN ========================================================================

DROP VIEW IF EXISTS "02_iam".v_orgs;

-- Restore v_orgs with settings blob column
CREATE OR REPLACE VIEW "02_iam".v_orgs AS
SELECT
    o.id,
    o.is_active,
    o.is_test,
    s.code   AS status,
    o.deleted_at,
    o.created_by,
    o.updated_by,
    o.created_at,
    o.updated_at,
    MAX(CASE WHEN a.attr_def_id = 10 THEN a.key_text END) AS slug,
    MAX(CASE WHEN a.attr_def_id = 11 THEN a.key_text END) AS display_name,
    COALESCE(MAX(CASE WHEN a.attr_def_id = 12 THEN a.key_jsonb::text END)::jsonb, '{}'::jsonb) AS settings
FROM "02_iam"."11_fct_orgs" o
JOIN "02_iam".dim_org_statuses s ON s.id = o.org_status_id
LEFT JOIN "02_iam"."20_dtl_attrs" a ON a.entity_id = o.id AND a.entity_type_id = 2
GROUP BY o.id, s.code;

DROP SEQUENCE IF EXISTS "02_iam".seq_custom_attr_def_id;

DELETE FROM "02_iam".dim_attr_defs WHERE id IN (13, 14);
UPDATE "02_iam".dim_attr_defs SET deprecated_at = NULL WHERE id = 12;
ALTER TABLE "02_iam".dim_attr_defs DROP COLUMN IF EXISTS is_system;
