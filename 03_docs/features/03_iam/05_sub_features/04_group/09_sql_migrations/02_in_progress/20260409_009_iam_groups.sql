-- =============================================================================
-- Migration:   20260409_009_iam_groups.sql
-- Module:      03_iam / Sub-feature: 04_group / Sequence: 009
-- Depends on:  003 (iam_bootstrap — 06_dim_entity_types, 07_dim_attr_defs,
--                   20_dtl_attrs, 10_fct_users),
--              006 (iam_orgs — 10_fct_orgs)
-- Description: Groups sub-feature. A group is a named collection of users
--              within an org. CRUD + member management + auto-create an
--              "everyone" system group when an org is created.
-- =============================================================================

-- UP =========================================================================

-- ---------------------------------------------------------------------------
-- 1. Register iam_group in 06_dim_entity_types
-- ---------------------------------------------------------------------------
INSERT INTO "03_iam"."06_dim_entity_types" (code, label, description)
VALUES ('iam_group', 'IAM Group', 'A named collection of users within an org.');

COMMENT ON TABLE "03_iam"."06_dim_entity_types" IS
    'Entity-type registry for IAM EAV attributes. One row per kind of '
    'entity that can own attributes in 20_dtl_attrs.';

-- ---------------------------------------------------------------------------
-- 2. Register attr_defs for iam_group (name, slug, description)
-- ---------------------------------------------------------------------------
INSERT INTO "03_iam"."07_dim_attr_defs"
    (entity_type_id, code, label, description, value_column)
SELECT et.id, x.code, x.label, x.description, x.value_column
FROM (VALUES
    ('iam_group', 'name',        'Name',        'Display name of the group.',                             'key_text'),
    ('iam_group', 'slug',        'Slug',        'URL-safe unique identifier for the group within an org.', 'key_text'),
    ('iam_group', 'description', 'Description', 'Optional description of the group.',                     'key_text')
) AS x(entity_code, code, label, description, value_column)
JOIN "03_iam"."06_dim_entity_types" et ON et.code = x.entity_code;

-- ---------------------------------------------------------------------------
-- 3. Create 10_fct_groups
--    Pure-EAV: name, slug, description live in 20_dtl_attrs.
--    org_id is the only business column (groups must belong to an org).
--    is_system = TRUE marks auto-created groups (e.g. "everyone").
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."10_fct_groups" (
    id          VARCHAR(36)  NOT NULL,
    org_id      VARCHAR(36)  NOT NULL,
    is_system   BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    deleted_at  TIMESTAMP,
    created_by  VARCHAR(36)  NOT NULL,
    updated_by  VARCHAR(36)  NOT NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_iam_fct_groups             PRIMARY KEY (id),
    CONSTRAINT fk_iam_fct_groups_org         FOREIGN KEY (org_id)
        REFERENCES "03_iam"."10_fct_orgs" (id),
    CONSTRAINT fk_iam_fct_groups_created_by  FOREIGN KEY (created_by)
        REFERENCES "03_iam"."10_fct_users" (id) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT fk_iam_fct_groups_updated_by  FOREIGN KEY (updated_by)
        REFERENCES "03_iam"."10_fct_users" (id) DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX idx_iam_fct_groups_org_id     ON "03_iam"."10_fct_groups" (org_id);
CREATE INDEX idx_iam_fct_groups_is_active  ON "03_iam"."10_fct_groups" (is_active)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_iam_fct_groups_created_at ON "03_iam"."10_fct_groups" (created_at DESC);

COMMENT ON TABLE  "03_iam"."10_fct_groups" IS
    'Group identity. Pure-EAV — name, slug, description live in 20_dtl_attrs. '
    'org_id is the owning organisation. is_system = TRUE for auto-created groups '
    '(e.g. the "everyone" group auto-created on org creation).';
COMMENT ON COLUMN "03_iam"."10_fct_groups".id         IS 'UUID v7 primary key.';
COMMENT ON COLUMN "03_iam"."10_fct_groups".org_id     IS 'FK to 10_fct_orgs. Every group belongs to exactly one org.';
COMMENT ON COLUMN "03_iam"."10_fct_groups".is_system  IS 'TRUE for groups managed by the system (e.g. "everyone").';
COMMENT ON COLUMN "03_iam"."10_fct_groups".is_active  IS 'FALSE to disable without deleting.';
COMMENT ON COLUMN "03_iam"."10_fct_groups".deleted_at IS 'Soft-delete timestamp.';
COMMENT ON COLUMN "03_iam"."10_fct_groups".created_by IS 'Actor that created the group.';
COMMENT ON COLUMN "03_iam"."10_fct_groups".updated_by IS 'Actor that last updated the group.';
COMMENT ON COLUMN "03_iam"."10_fct_groups".created_at IS 'Row creation timestamp (UTC).';
COMMENT ON COLUMN "03_iam"."10_fct_groups".updated_at IS 'Last update timestamp (UTC).';

GRANT SELECT ON "03_iam"."10_fct_groups" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE, DELETE ON "03_iam"."10_fct_groups" TO tennetctl_write;

-- Slug uniqueness within an org via partial unique index
-- (slug is stored as EAV key_text; uniqueness is (org_id, slug) — enforced
--  at the app level because the EAV row has no org_id column. A unique index
--  on key_text + attr_def_id alone would be global; per-org uniqueness is
--  enforced by the service INSERT check + a partial index on fct_groups for perf.)

-- ---------------------------------------------------------------------------
-- 4. Create 40_lnk_group_members
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."40_lnk_group_members" (
    id          VARCHAR(36)  NOT NULL,
    group_id    VARCHAR(36)  NOT NULL,
    user_id     VARCHAR(36)  NOT NULL,
    added_by    VARCHAR(36)  NOT NULL,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    added_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_iam_lnk_group_members             PRIMARY KEY (id),
    CONSTRAINT uq_iam_lnk_group_members_grp_user    UNIQUE (group_id, user_id),
    CONSTRAINT fk_iam_lnk_group_members_group       FOREIGN KEY (group_id)
        REFERENCES "03_iam"."10_fct_groups" (id),
    CONSTRAINT fk_iam_lnk_group_members_user        FOREIGN KEY (user_id)
        REFERENCES "03_iam"."10_fct_users" (id),
    CONSTRAINT fk_iam_lnk_group_members_added_by    FOREIGN KEY (added_by)
        REFERENCES "03_iam"."10_fct_users" (id) DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX idx_iam_lnk_group_members_group   ON "03_iam"."40_lnk_group_members" (group_id);
CREATE INDEX idx_iam_lnk_group_members_user    ON "03_iam"."40_lnk_group_members" (user_id);

COMMENT ON TABLE  "03_iam"."40_lnk_group_members" IS
    'Membership link between a group and a user. Immutable rows — soft '
    'removal is done by is_active = FALSE. UNIQUE(group_id, user_id) '
    'prevents double-adds.';
COMMENT ON COLUMN "03_iam"."40_lnk_group_members".id        IS 'UUID v7 primary key.';
COMMENT ON COLUMN "03_iam"."40_lnk_group_members".group_id  IS 'FK to 10_fct_groups.';
COMMENT ON COLUMN "03_iam"."40_lnk_group_members".user_id   IS 'FK to 10_fct_users.';
COMMENT ON COLUMN "03_iam"."40_lnk_group_members".added_by  IS 'Actor that added the user to the group.';
COMMENT ON COLUMN "03_iam"."40_lnk_group_members".is_active IS 'FALSE when member has been removed (soft removal).';
COMMENT ON COLUMN "03_iam"."40_lnk_group_members".added_at  IS 'Timestamp when the user was added.';

GRANT SELECT ON "03_iam"."40_lnk_group_members" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE ON "03_iam"."40_lnk_group_members" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 5. Create v_groups view (joins fct_groups + dtl_attrs + member_count)
-- ---------------------------------------------------------------------------
CREATE VIEW "03_iam".v_groups AS
SELECT
    g.id,
    g.org_id,
    g.is_system,
    g.is_active,
    (g.deleted_at IS NOT NULL)                                        AS is_deleted,
    MAX(CASE WHEN ad.code = 'name'        THEN a.key_text END)        AS name,
    MAX(CASE WHEN ad.code = 'slug'        THEN a.key_text END)        AS slug,
    MAX(CASE WHEN ad.code = 'description' THEN a.key_text END)        AS description,
    COUNT(DISTINCT m.user_id) FILTER (WHERE m.is_active = TRUE)       AS member_count,
    g.created_by,
    g.updated_by,
    g.created_at,
    g.updated_at
FROM "03_iam"."10_fct_groups" g
LEFT JOIN "03_iam"."20_dtl_attrs" a
       ON a.entity_type_id = (SELECT id FROM "03_iam"."06_dim_entity_types" WHERE code = 'iam_group')
      AND a.entity_id = g.id
LEFT JOIN "03_iam"."07_dim_attr_defs" ad ON ad.id = a.attr_def_id
LEFT JOIN "03_iam"."40_lnk_group_members" m ON m.group_id = g.id
GROUP BY g.id, g.org_id, g.is_system, g.is_active, g.deleted_at,
         g.created_by, g.updated_by, g.created_at, g.updated_at;

COMMENT ON VIEW "03_iam".v_groups IS
    'Groups with EAV attrs (name, slug, description) pivoted and member_count '
    'computed from 40_lnk_group_members (active members only).';

GRANT SELECT ON "03_iam".v_groups TO tennetctl_read;
GRANT SELECT ON "03_iam".v_groups TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 6. Create v_group_members view
-- ---------------------------------------------------------------------------
CREATE VIEW "03_iam".v_group_members AS
SELECT
    m.id,
    m.group_id,
    m.user_id,
    m.added_by,
    m.is_active,
    m.added_at,
    MAX(CASE WHEN ad.code = 'username' THEN a.key_text END) AS username,
    MAX(CASE WHEN ad.code = 'email'    THEN a.key_text END) AS email
FROM "03_iam"."40_lnk_group_members" m
LEFT JOIN "03_iam"."20_dtl_attrs" a
       ON a.entity_type_id = (SELECT id FROM "03_iam"."06_dim_entity_types" WHERE code = 'iam_user')
      AND a.entity_id = m.user_id
LEFT JOIN "03_iam"."07_dim_attr_defs" ad ON ad.id = a.attr_def_id
GROUP BY m.id, m.group_id, m.user_id, m.added_by, m.is_active, m.added_at;

COMMENT ON VIEW "03_iam".v_group_members IS
    'Group membership rows with user username and email resolved from EAV.';

GRANT SELECT ON "03_iam".v_group_members TO tennetctl_read;
GRANT SELECT ON "03_iam".v_group_members TO tennetctl_write;

-- DOWN =======================================================================

DROP VIEW  IF EXISTS "03_iam".v_group_members;
DROP VIEW  IF EXISTS "03_iam".v_groups;
DROP TABLE IF EXISTS "03_iam"."40_lnk_group_members";
DROP TABLE IF EXISTS "03_iam"."10_fct_groups";

-- Remove iam_group attr_defs
DELETE FROM "03_iam"."07_dim_attr_defs"
 WHERE entity_type_id = (
     SELECT id FROM "03_iam"."06_dim_entity_types" WHERE code = 'iam_group'
 );

-- Remove iam_group entity type
DELETE FROM "03_iam"."06_dim_entity_types" WHERE code = 'iam_group';
