-- ============================================================================
-- Migration 009: Group Members (junction table)
-- Feature:  02_iam / 06_group_member
-- Depends:  07_fct_groups (04_group sub-feature), 10_fct_users
-- ============================================================================

-- UP =========================================================================

-- Junction: links users to groups
CREATE TABLE "02_iam"."09_lnk_group_members" (
    id          VARCHAR(36)   NOT NULL,
    group_id    VARCHAR(36)   NOT NULL,
    user_id     VARCHAR(36)   NOT NULL,
    added_by    VARCHAR(36),
    created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at  TIMESTAMP,

    CONSTRAINT pk_09_lnk_group_members
        PRIMARY KEY (id),

    CONSTRAINT fk_09_lnk_group_members_group
        FOREIGN KEY (group_id)
        REFERENCES "02_iam"."07_fct_groups" (id),

    CONSTRAINT fk_09_lnk_group_members_user
        FOREIGN KEY (user_id)
        REFERENCES "02_iam"."10_fct_users" (id)
);

COMMENT ON TABLE  "02_iam"."09_lnk_group_members"           IS 'Junction: links users to groups within an org.';
COMMENT ON COLUMN "02_iam"."09_lnk_group_members".id        IS 'UUID v7 primary key.';
COMMENT ON COLUMN "02_iam"."09_lnk_group_members".group_id  IS 'FK to 07_fct_groups.';
COMMENT ON COLUMN "02_iam"."09_lnk_group_members".user_id   IS 'FK to 10_fct_users.';
COMMENT ON COLUMN "02_iam"."09_lnk_group_members".added_by  IS 'UUID of the actor who added this member.';
COMMENT ON COLUMN "02_iam"."09_lnk_group_members".created_at IS 'When the membership was created.';
COMMENT ON COLUMN "02_iam"."09_lnk_group_members".deleted_at IS 'Soft-delete timestamp (NULL = active).';

-- Partial unique: a user can only be an active member of a group once
CREATE UNIQUE INDEX uq_09_lnk_group_members_active
    ON "02_iam"."09_lnk_group_members" (group_id, user_id)
    WHERE deleted_at IS NULL;

-- Lookup indexes
CREATE INDEX idx_09_lnk_group_members_group
    ON "02_iam"."09_lnk_group_members" (group_id)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_09_lnk_group_members_user
    ON "02_iam"."09_lnk_group_members" (user_id)
    WHERE deleted_at IS NULL;

-- View: joins user and group info for read queries
CREATE OR REPLACE VIEW "02_iam"."v_group_members" AS
SELECT
    gm.id,
    gm.group_id,
    gm.user_id,
    gm.added_by,
    gm.created_at,
    gm.deleted_at
FROM "02_iam"."09_lnk_group_members" gm;

-- DOWN =======================================================================

DROP VIEW  IF EXISTS "02_iam"."v_group_members";
DROP INDEX IF EXISTS "02_iam"."idx_09_lnk_group_members_user";
DROP INDEX IF EXISTS "02_iam"."idx_09_lnk_group_members_group";
DROP INDEX IF EXISTS "02_iam"."uq_09_lnk_group_members_active";
DROP TABLE IF EXISTS "02_iam"."09_lnk_group_members";
