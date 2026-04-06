-- ==========================================================================
-- Migration: 20260404_007_iam_groups
-- Description: Create group tables for IAM org-scoped groups
-- Schema: 02_iam
-- ==========================================================================

-- UP ====

-- --------------------------------------------------------------------------
-- 07_fct_groups — org-scoped groups
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "02_iam"."07_fct_groups" (
    id          VARCHAR(36) PRIMARY KEY,
    org_id      VARCHAR(36) NOT NULL,
    name        VARCHAR(255) NOT NULL,
    slug        VARCHAR(100) NOT NULL,
    description TEXT,
    is_system   BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at  TIMESTAMPTZ,

    CONSTRAINT fk_07_fct_groups_org_id
        FOREIGN KEY (org_id) REFERENCES "02_iam"."01_fct_org_orgs" (id)
);

COMMENT ON TABLE "02_iam"."07_fct_groups" IS 'Org-scoped groups for IAM';
COMMENT ON COLUMN "02_iam"."07_fct_groups".id IS 'Group UUID v7 primary key';
COMMENT ON COLUMN "02_iam"."07_fct_groups".org_id IS 'FK to owning organisation';
COMMENT ON COLUMN "02_iam"."07_fct_groups".name IS 'Human-readable group name';
COMMENT ON COLUMN "02_iam"."07_fct_groups".slug IS 'URL-safe unique identifier within org';
COMMENT ON COLUMN "02_iam"."07_fct_groups".description IS 'Optional group description';
COMMENT ON COLUMN "02_iam"."07_fct_groups".is_system IS 'System-managed group flag';
COMMENT ON COLUMN "02_iam"."07_fct_groups".created_at IS 'Row creation timestamp';
COMMENT ON COLUMN "02_iam"."07_fct_groups".updated_at IS 'Last modification timestamp';
COMMENT ON COLUMN "02_iam"."07_fct_groups".deleted_at IS 'Soft-delete timestamp';

-- Indexes
CREATE INDEX idx_07_fct_groups_org_id
    ON "02_iam"."07_fct_groups" (org_id);

CREATE INDEX idx_07_fct_groups_slug
    ON "02_iam"."07_fct_groups" (slug);

-- Partial unique: (org_id, slug) only for non-deleted rows
CREATE UNIQUE INDEX uq_07_fct_groups_org_slug
    ON "02_iam"."07_fct_groups" (org_id, slug)
    WHERE deleted_at IS NULL;

-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION "02_iam".trg_07_fct_groups_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_07_fct_groups_updated_at
    BEFORE UPDATE ON "02_iam"."07_fct_groups"
    FOR EACH ROW
    EXECUTE FUNCTION "02_iam".trg_07_fct_groups_updated_at();

-- --------------------------------------------------------------------------
-- v_groups — read view
-- --------------------------------------------------------------------------

CREATE OR REPLACE VIEW "02_iam"."v_groups" AS
SELECT
    g.id,
    g.org_id,
    g.name,
    g.slug,
    g.description,
    g.is_system,
    g.deleted_at IS NOT NULL AS is_deleted,
    g.deleted_at,
    g.created_at,
    g.updated_at
FROM "02_iam"."07_fct_groups" g;

COMMENT ON VIEW "02_iam"."v_groups" IS 'Read view for groups with derived is_deleted flag';


-- DOWN ====

DROP VIEW IF EXISTS "02_iam"."v_groups";
DROP TRIGGER IF EXISTS trg_07_fct_groups_updated_at ON "02_iam"."07_fct_groups";
DROP FUNCTION IF EXISTS "02_iam".trg_07_fct_groups_updated_at();
DROP TABLE IF EXISTS "02_iam"."07_fct_groups";
