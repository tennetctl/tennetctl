-- ============================================================================
-- Migration 008: Org Members (junction table with roles)
-- Feature:  02_iam / 05_org_member
-- Depends:  01_fct_orgs, 10_fct_users
-- ============================================================================

-- UP =========================================================================

-- Lookup: organisation member roles (never mutate, only INSERT + deprecate)
CREATE TABLE "02_iam"."dim_org_roles" (
    id              SERIAL        NOT NULL,
    name            TEXT          NOT NULL,
    description     TEXT,
    deprecated_at   TIMESTAMP,

    CONSTRAINT pk_dim_org_roles
        PRIMARY KEY (id),

    CONSTRAINT uq_dim_org_roles_name
        UNIQUE (name)
);

COMMENT ON TABLE  "02_iam"."dim_org_roles"                IS 'Lookup: valid roles for org memberships.';
COMMENT ON COLUMN "02_iam"."dim_org_roles".id             IS 'Auto-incrementing PK.';
COMMENT ON COLUMN "02_iam"."dim_org_roles".name           IS 'Role code (owner, admin, member, viewer).';
COMMENT ON COLUMN "02_iam"."dim_org_roles".description    IS 'Human-readable description.';
COMMENT ON COLUMN "02_iam"."dim_org_roles".deprecated_at  IS 'Set to deprecate a role without deleting.';

-- Seed data
INSERT INTO "02_iam"."dim_org_roles" (id, name, description) VALUES
    (1, 'owner',  'Full control over the organisation'),
    (2, 'admin',  'Administrative access'),
    (3, 'member', 'Standard member access'),
    (4, 'viewer', 'Read-only access');

-- Junction: links users to organisations with roles
CREATE TABLE "02_iam"."08_lnk_org_members" (
    id          VARCHAR(36)   NOT NULL,
    org_id      VARCHAR(36)   NOT NULL,
    user_id     VARCHAR(36)   NOT NULL,
    role_id     INTEGER       NOT NULL,
    invited_by  VARCHAR(36),
    joined_at   TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by  VARCHAR(36),
    updated_by  VARCHAR(36),
    created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at  TIMESTAMP,

    CONSTRAINT pk_08_lnk_org_members
        PRIMARY KEY (id),

    CONSTRAINT fk_08_lnk_org_members_org
        FOREIGN KEY (org_id)
        REFERENCES "02_iam"."01_fct_orgs" (id),

    CONSTRAINT fk_08_lnk_org_members_user
        FOREIGN KEY (user_id)
        REFERENCES "02_iam"."10_fct_users" (id),

    CONSTRAINT fk_08_lnk_org_members_role
        FOREIGN KEY (role_id)
        REFERENCES "02_iam"."dim_org_roles" (id)
);

COMMENT ON TABLE  "02_iam"."08_lnk_org_members"              IS 'Junction: links users to organisations with roles.';
COMMENT ON COLUMN "02_iam"."08_lnk_org_members".id           IS 'UUID v7 primary key.';
COMMENT ON COLUMN "02_iam"."08_lnk_org_members".org_id       IS 'FK to 01_fct_orgs.';
COMMENT ON COLUMN "02_iam"."08_lnk_org_members".user_id      IS 'FK to 10_fct_users.';
COMMENT ON COLUMN "02_iam"."08_lnk_org_members".role_id      IS 'FK to dim_org_roles.';
COMMENT ON COLUMN "02_iam"."08_lnk_org_members".invited_by   IS 'UUID of the actor who invited this member (nullable).';
COMMENT ON COLUMN "02_iam"."08_lnk_org_members".joined_at    IS 'When the user joined the organisation.';
COMMENT ON COLUMN "02_iam"."08_lnk_org_members".created_by   IS 'UUID of the actor who created this record.';
COMMENT ON COLUMN "02_iam"."08_lnk_org_members".updated_by   IS 'UUID of the last modifier.';
COMMENT ON COLUMN "02_iam"."08_lnk_org_members".created_at   IS 'Row creation timestamp.';
COMMENT ON COLUMN "02_iam"."08_lnk_org_members".updated_at   IS 'Last modification timestamp.';
COMMENT ON COLUMN "02_iam"."08_lnk_org_members".deleted_at   IS 'Soft-delete timestamp (NULL = active).';

-- Partial unique: a user can only be an active member of an org once
CREATE UNIQUE INDEX uq_08_lnk_org_members_active
    ON "02_iam"."08_lnk_org_members" (org_id, user_id)
    WHERE deleted_at IS NULL;

-- Lookup indexes
CREATE INDEX idx_08_lnk_org_members_org
    ON "02_iam"."08_lnk_org_members" (org_id)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_08_lnk_org_members_user
    ON "02_iam"."08_lnk_org_members" (user_id)
    WHERE deleted_at IS NULL;

-- Auto-update updated_at on row modification
CREATE OR REPLACE FUNCTION "02_iam".trg_08_lnk_org_members_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_08_lnk_org_members_updated_at
    BEFORE UPDATE ON "02_iam"."08_lnk_org_members"
    FOR EACH ROW
    EXECUTE FUNCTION "02_iam".trg_08_lnk_org_members_updated_at();

-- View: joins user display_name, email, and role name for read queries
CREATE OR REPLACE VIEW "02_iam"."v_org_members" AS
SELECT
    om.id,
    om.org_id,
    om.user_id,
    om.role_id,
    r.name           AS role,
    INITCAP(r.name)  AS role_label,
    om.invited_by,
    om.joined_at,
    om.created_by,
    om.updated_by,
    om.created_at,
    om.updated_at,
    om.deleted_at,
    (om.deleted_at IS NOT NULL) AS is_deleted
FROM "02_iam"."08_lnk_org_members" om
JOIN "02_iam"."dim_org_roles" r ON r.id = om.role_id;

-- DOWN =======================================================================

DROP VIEW    IF EXISTS "02_iam"."v_org_members";
DROP TRIGGER IF EXISTS trg_08_lnk_org_members_updated_at ON "02_iam"."08_lnk_org_members";
DROP FUNCTION IF EXISTS "02_iam".trg_08_lnk_org_members_updated_at();
DROP INDEX   IF EXISTS "02_iam"."idx_08_lnk_org_members_user";
DROP INDEX   IF EXISTS "02_iam"."idx_08_lnk_org_members_org";
DROP INDEX   IF EXISTS "02_iam"."uq_08_lnk_org_members_active";
DROP TABLE   IF EXISTS "02_iam"."08_lnk_org_members";
DROP TABLE   IF EXISTS "02_iam"."dim_org_roles";
