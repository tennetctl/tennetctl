-- =============================================================================
-- Migration: 20260403_004_org_constraint_naming_slug_index_dtl_trigger.sql
-- Module:    02_iam / sub-feature: 01_org
-- Description:
--   1. Rename FK and CHK constraints to include the 01_ sub-feature prefix,
--      completing the naming convention across all DB objects.
--   2. Add a partial unique index on slug to enforce uniqueness at the DB level
--      (currently only enforced in service layer).
--   3. Add updated_at trigger on 01_dtl_org_attrs for consistent timestamp
--      management (01_fct_org_orgs already has this trigger).
-- =============================================================================

-- UP ==========================================================================

-- 1. Rename FK constraints to include 01_ prefix
ALTER TABLE "02_iam"."01_fct_org_orgs"
    RENAME CONSTRAINT fk_fct_org_orgs_status TO fk_01_fct_org_orgs_status;

ALTER TABLE "02_iam"."01_dtl_org_attrs"
    RENAME CONSTRAINT fk_dtl_org_attrs_attr_def TO fk_01_dtl_org_attrs_attr_def;

ALTER TABLE "02_iam"."01_dtl_org_attrs"
    RENAME CONSTRAINT fk_dtl_org_attrs_entity_type TO fk_01_dtl_org_attrs_entity_type;

-- 2. Rename CHK constraints to include 01_ prefix
ALTER TABLE "02_iam"."01_dim_org_attr_defs"
    RENAME CONSTRAINT chk_dim_org_attr_defs_value_type TO chk_01_dim_org_attr_defs_value_type;

ALTER TABLE "02_iam"."01_dtl_org_attrs"
    RENAME CONSTRAINT chk_dtl_org_attrs_value TO chk_01_dtl_org_attrs_value;

-- 3. Partial unique index on slug (attr_def_id=10) for active orgs only
--    Prevents duplicate slugs at DB level for non-deleted orgs.
--    Deleted orgs (soft-deleted fct rows) are not excluded here intentionally:
--    slug re-use after delete is handled in service.py (deletes the slug attr row).
CREATE UNIQUE INDEX uq_01_dtl_org_slug
    ON "02_iam"."01_dtl_org_attrs" (key_text)
    WHERE attr_def_id = 10 AND key_text IS NOT NULL;

COMMENT ON INDEX "02_iam".uq_01_dtl_org_slug
    IS 'Enforces slug uniqueness across all orgs at the DB level. attr_def_id=10 is the slug system attribute.';

-- 4. updated_at trigger on 01_dtl_org_attrs
CREATE OR REPLACE FUNCTION "02_iam".trg_fn_01_dtl_org_attrs_updated_at()
    RETURNS TRIGGER
    LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_01_dtl_org_attrs_updated_at
    BEFORE UPDATE ON "02_iam"."01_dtl_org_attrs"
    FOR EACH ROW
    EXECUTE FUNCTION "02_iam".trg_fn_01_dtl_org_attrs_updated_at();

COMMENT ON TRIGGER trg_01_dtl_org_attrs_updated_at ON "02_iam"."01_dtl_org_attrs"
    IS 'Auto-sets updated_at on every row update. App code must not set this column.';

-- DOWN ========================================================================

DROP TRIGGER IF EXISTS trg_01_dtl_org_attrs_updated_at ON "02_iam"."01_dtl_org_attrs";
DROP FUNCTION IF EXISTS "02_iam".trg_fn_01_dtl_org_attrs_updated_at();

DROP INDEX IF EXISTS "02_iam".uq_01_dtl_org_slug;

ALTER TABLE "02_iam"."01_dtl_org_attrs"
    RENAME CONSTRAINT chk_01_dtl_org_attrs_value TO chk_dtl_org_attrs_value;

ALTER TABLE "02_iam"."01_dim_org_attr_defs"
    RENAME CONSTRAINT chk_01_dim_org_attr_defs_value_type TO chk_dim_org_attr_defs_value_type;

ALTER TABLE "02_iam"."01_dtl_org_attrs"
    RENAME CONSTRAINT fk_01_dtl_org_attrs_entity_type TO fk_dtl_org_attrs_entity_type;

ALTER TABLE "02_iam"."01_dtl_org_attrs"
    RENAME CONSTRAINT fk_01_dtl_org_attrs_attr_def TO fk_dtl_org_attrs_attr_def;

ALTER TABLE "02_iam"."01_fct_org_orgs"
    RENAME CONSTRAINT fk_01_fct_org_orgs_status TO fk_fct_org_orgs_status;
