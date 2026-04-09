-- =============================================================================
-- Migration:   20260409_011_iam_rbac.sql
-- Module:      03_iam
-- Sub-feature: 00_bootstrap (RBAC Three-Tier)
-- Sequence:    011
-- Depends on:  010 (iam_foundation_primitives — dim_categories, fct_orgs,
--              fct_workspaces, fct_users must all exist)
-- Description: Sprint 3 RBAC — three-tier role system.
--              Tier 1: platform_roles    — system-wide roles
--              Tier 2: org_roles         — per-tenant roles
--              Tier 3: workspace_roles   — per-department roles
--              Shared permissions catalog with resource + action pairs.
--              Role-permission links per tier (lnk_*_role_permissions).
--              User-role assignment links per tier (lnk_user_*_roles).
--              Seed: 13 permissions, 3 platform system roles, assign
--                    platform_admin to the first user (setup admin).
-- =============================================================================

-- UP =========================================================================

-- ---------------------------------------------------------------------------
-- 10_fct_permissions — shared permissions catalog
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."10_fct_permissions" (
    id          VARCHAR(36)  NOT NULL,
    resource    VARCHAR(64)  NOT NULL,
    action      VARCHAR(32)  NOT NULL,
    description TEXT,
    is_active   BOOLEAN      NOT NULL DEFAULT true,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_iam_fct_permissions             PRIMARY KEY (id),
    CONSTRAINT uq_iam_fct_permissions_res_action  UNIQUE (resource, action)
);

COMMENT ON TABLE  "03_iam"."10_fct_permissions" IS
    'Shared permissions catalog. One row per (resource, action) pair. '
    'Used by all three role tiers via their respective lnk_ tables.';
COMMENT ON COLUMN "03_iam"."10_fct_permissions".id          IS 'UUID v7 primary key.';
COMMENT ON COLUMN "03_iam"."10_fct_permissions".resource    IS 'Resource name, e.g. ''orgs'', ''users'', ''vault.secrets''.';
COMMENT ON COLUMN "03_iam"."10_fct_permissions".action      IS 'Action name, e.g. ''read'', ''write'', ''admin'', ''delete''.';
COMMENT ON COLUMN "03_iam"."10_fct_permissions".description IS 'Optional human-readable description.';
COMMENT ON COLUMN "03_iam"."10_fct_permissions".is_active   IS 'false = soft-disabled. Never deleted.';
COMMENT ON COLUMN "03_iam"."10_fct_permissions".created_at  IS 'Row creation timestamp (UTC).';
COMMENT ON COLUMN "03_iam"."10_fct_permissions".updated_at  IS 'Last update timestamp (UTC).';

GRANT SELECT ON "03_iam"."10_fct_permissions" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE ON "03_iam"."10_fct_permissions" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 10_fct_platform_roles — system-wide roles
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."10_fct_platform_roles" (
    id          VARCHAR(36)  NOT NULL,
    code        VARCHAR(64)  NOT NULL,
    name        VARCHAR(128) NOT NULL,
    category_id SMALLINT     NOT NULL,
    is_system   BOOLEAN      NOT NULL DEFAULT false,
    is_active   BOOLEAN      NOT NULL DEFAULT true,
    deleted_at  TIMESTAMP,
    created_by  VARCHAR(36),
    updated_by  VARCHAR(36),
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_iam_fct_platform_roles      PRIMARY KEY (id),
    CONSTRAINT uq_iam_fct_platform_roles_code UNIQUE (code),
    CONSTRAINT fk_iam_fct_platform_roles_cat  FOREIGN KEY (category_id)
        REFERENCES "03_iam"."06_dim_categories" (id)
);

COMMENT ON TABLE  "03_iam"."10_fct_platform_roles" IS
    'Platform-scoped roles. system=true rows are seeded and immutable.';
COMMENT ON COLUMN "03_iam"."10_fct_platform_roles".id          IS 'UUID v7 primary key.';
COMMENT ON COLUMN "03_iam"."10_fct_platform_roles".code        IS 'Stable machine-readable identifier. Unique across all platform roles.';
COMMENT ON COLUMN "03_iam"."10_fct_platform_roles".name        IS 'Display name.';
COMMENT ON COLUMN "03_iam"."10_fct_platform_roles".category_id IS 'FK to 06_dim_categories (category_type=''role'').';
COMMENT ON COLUMN "03_iam"."10_fct_platform_roles".is_system   IS 'true = seeded by migration; protected from deletion.';
COMMENT ON COLUMN "03_iam"."10_fct_platform_roles".is_active   IS 'false = disabled. Assignments on inactive roles are ignored.';
COMMENT ON COLUMN "03_iam"."10_fct_platform_roles".deleted_at  IS 'Soft-delete timestamp. NULL = active.';
COMMENT ON COLUMN "03_iam"."10_fct_platform_roles".created_by  IS 'UUID of the user who created this role.';
COMMENT ON COLUMN "03_iam"."10_fct_platform_roles".updated_by  IS 'UUID of the user who last updated this role.';
COMMENT ON COLUMN "03_iam"."10_fct_platform_roles".created_at  IS 'Row creation timestamp (UTC).';
COMMENT ON COLUMN "03_iam"."10_fct_platform_roles".updated_at  IS 'Last update timestamp (UTC).';

GRANT SELECT ON "03_iam"."10_fct_platform_roles" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE ON "03_iam"."10_fct_platform_roles" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 40_lnk_platform_role_permissions
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."40_lnk_platform_role_permissions" (
    id               VARCHAR(36)  NOT NULL,
    platform_role_id VARCHAR(36)  NOT NULL,
    permission_id    VARCHAR(36)  NOT NULL,
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_iam_lnk_platform_role_perms       PRIMARY KEY (id),
    CONSTRAINT uq_iam_lnk_platform_role_perms       UNIQUE (platform_role_id, permission_id),
    CONSTRAINT fk_iam_lnk_prp_platform_role         FOREIGN KEY (platform_role_id)
        REFERENCES "03_iam"."10_fct_platform_roles" (id),
    CONSTRAINT fk_iam_lnk_prp_permission            FOREIGN KEY (permission_id)
        REFERENCES "03_iam"."10_fct_permissions" (id)
);

COMMENT ON TABLE  "03_iam"."40_lnk_platform_role_permissions" IS
    'Many-to-many link: which permissions a platform role grants.';
COMMENT ON COLUMN "03_iam"."40_lnk_platform_role_permissions".id               IS 'UUID v7 PK.';
COMMENT ON COLUMN "03_iam"."40_lnk_platform_role_permissions".platform_role_id IS 'FK to 10_fct_platform_roles.';
COMMENT ON COLUMN "03_iam"."40_lnk_platform_role_permissions".permission_id    IS 'FK to 10_fct_permissions.';
COMMENT ON COLUMN "03_iam"."40_lnk_platform_role_permissions".created_at       IS 'Immutable creation timestamp.';

GRANT SELECT ON "03_iam"."40_lnk_platform_role_permissions" TO tennetctl_read;
GRANT SELECT, INSERT, DELETE ON "03_iam"."40_lnk_platform_role_permissions" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 40_lnk_user_platform_roles
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."40_lnk_user_platform_roles" (
    id               VARCHAR(36)  NOT NULL,
    user_id          VARCHAR(36)  NOT NULL,
    platform_role_id VARCHAR(36)  NOT NULL,
    granted_by       VARCHAR(36),
    granted_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active        BOOLEAN      NOT NULL DEFAULT true,

    CONSTRAINT pk_iam_lnk_user_platform_roles    PRIMARY KEY (id),
    CONSTRAINT uq_iam_lnk_user_platform_roles    UNIQUE (user_id, platform_role_id),
    CONSTRAINT fk_iam_lnk_upr_user              FOREIGN KEY (user_id)
        REFERENCES "03_iam"."10_fct_users" (id),
    CONSTRAINT fk_iam_lnk_upr_platform_role     FOREIGN KEY (platform_role_id)
        REFERENCES "03_iam"."10_fct_platform_roles" (id),
    CONSTRAINT fk_iam_lnk_upr_granted_by        FOREIGN KEY (granted_by)
        REFERENCES "03_iam"."10_fct_users" (id)
);

COMMENT ON TABLE  "03_iam"."40_lnk_user_platform_roles" IS
    'Many-to-many link: which platform roles a user holds.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_platform_roles".id               IS 'UUID v7 PK.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_platform_roles".user_id          IS 'FK to 10_fct_users.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_platform_roles".platform_role_id IS 'FK to 10_fct_platform_roles.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_platform_roles".granted_by       IS 'FK to 10_fct_users — who granted this assignment.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_platform_roles".granted_at       IS 'Immutable grant timestamp.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_platform_roles".is_active        IS 'false = revoked.';

GRANT SELECT ON "03_iam"."40_lnk_user_platform_roles" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE ON "03_iam"."40_lnk_user_platform_roles" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 10_fct_org_roles — per-tenant roles
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."10_fct_org_roles" (
    id          VARCHAR(36)  NOT NULL,
    org_id      VARCHAR(36)  NOT NULL,
    code        VARCHAR(64)  NOT NULL,
    name        VARCHAR(128) NOT NULL,
    category_id SMALLINT     NOT NULL,
    is_system   BOOLEAN      NOT NULL DEFAULT false,
    is_active   BOOLEAN      NOT NULL DEFAULT true,
    deleted_at  TIMESTAMP,
    created_by  VARCHAR(36),
    updated_by  VARCHAR(36),
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_iam_fct_org_roles              PRIMARY KEY (id),
    CONSTRAINT uq_iam_fct_org_roles_org_code     UNIQUE (org_id, code),
    CONSTRAINT fk_iam_fct_org_roles_org          FOREIGN KEY (org_id)
        REFERENCES "03_iam"."10_fct_orgs" (id),
    CONSTRAINT fk_iam_fct_org_roles_cat          FOREIGN KEY (category_id)
        REFERENCES "03_iam"."06_dim_categories" (id)
);

COMMENT ON TABLE  "03_iam"."10_fct_org_roles" IS
    'Per-tenant roles. code is unique within an org. system=true rows are immutable.';
COMMENT ON COLUMN "03_iam"."10_fct_org_roles".id          IS 'UUID v7 primary key.';
COMMENT ON COLUMN "03_iam"."10_fct_org_roles".org_id      IS 'FK to 10_fct_orgs. Determines scope.';
COMMENT ON COLUMN "03_iam"."10_fct_org_roles".code        IS 'Stable identifier, unique within the org.';
COMMENT ON COLUMN "03_iam"."10_fct_org_roles".name        IS 'Display name.';
COMMENT ON COLUMN "03_iam"."10_fct_org_roles".category_id IS 'FK to 06_dim_categories (category_type=''role'').';
COMMENT ON COLUMN "03_iam"."10_fct_org_roles".is_system   IS 'true = seeded; protected from deletion.';
COMMENT ON COLUMN "03_iam"."10_fct_org_roles".is_active   IS 'false = disabled.';
COMMENT ON COLUMN "03_iam"."10_fct_org_roles".deleted_at  IS 'Soft-delete timestamp. NULL = active.';
COMMENT ON COLUMN "03_iam"."10_fct_org_roles".created_by  IS 'UUID of creator.';
COMMENT ON COLUMN "03_iam"."10_fct_org_roles".updated_by  IS 'UUID of last updater.';
COMMENT ON COLUMN "03_iam"."10_fct_org_roles".created_at  IS 'Row creation timestamp (UTC).';
COMMENT ON COLUMN "03_iam"."10_fct_org_roles".updated_at  IS 'Last update timestamp (UTC).';

GRANT SELECT ON "03_iam"."10_fct_org_roles" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE ON "03_iam"."10_fct_org_roles" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 40_lnk_org_role_permissions
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."40_lnk_org_role_permissions" (
    id            VARCHAR(36)  NOT NULL,
    org_role_id   VARCHAR(36)  NOT NULL,
    permission_id VARCHAR(36)  NOT NULL,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_iam_lnk_org_role_perms        PRIMARY KEY (id),
    CONSTRAINT uq_iam_lnk_org_role_perms        UNIQUE (org_role_id, permission_id),
    CONSTRAINT fk_iam_lnk_orp_org_role          FOREIGN KEY (org_role_id)
        REFERENCES "03_iam"."10_fct_org_roles" (id),
    CONSTRAINT fk_iam_lnk_orp_permission        FOREIGN KEY (permission_id)
        REFERENCES "03_iam"."10_fct_permissions" (id)
);

COMMENT ON TABLE  "03_iam"."40_lnk_org_role_permissions" IS
    'Many-to-many link: which permissions an org role grants.';
COMMENT ON COLUMN "03_iam"."40_lnk_org_role_permissions".id            IS 'UUID v7 PK.';
COMMENT ON COLUMN "03_iam"."40_lnk_org_role_permissions".org_role_id   IS 'FK to 10_fct_org_roles.';
COMMENT ON COLUMN "03_iam"."40_lnk_org_role_permissions".permission_id IS 'FK to 10_fct_permissions.';
COMMENT ON COLUMN "03_iam"."40_lnk_org_role_permissions".created_at    IS 'Immutable creation timestamp.';

GRANT SELECT ON "03_iam"."40_lnk_org_role_permissions" TO tennetctl_read;
GRANT SELECT, INSERT, DELETE ON "03_iam"."40_lnk_org_role_permissions" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 40_lnk_user_org_roles
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."40_lnk_user_org_roles" (
    id          VARCHAR(36)  NOT NULL,
    user_id     VARCHAR(36)  NOT NULL,
    org_id      VARCHAR(36)  NOT NULL,
    org_role_id VARCHAR(36)  NOT NULL,
    granted_by  VARCHAR(36),
    granted_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active   BOOLEAN      NOT NULL DEFAULT true,

    CONSTRAINT pk_iam_lnk_user_org_roles         PRIMARY KEY (id),
    CONSTRAINT uq_iam_lnk_user_org_roles         UNIQUE (user_id, org_id, org_role_id),
    CONSTRAINT fk_iam_lnk_uor_user              FOREIGN KEY (user_id)
        REFERENCES "03_iam"."10_fct_users" (id),
    CONSTRAINT fk_iam_lnk_uor_org              FOREIGN KEY (org_id)
        REFERENCES "03_iam"."10_fct_orgs" (id),
    CONSTRAINT fk_iam_lnk_uor_org_role         FOREIGN KEY (org_role_id)
        REFERENCES "03_iam"."10_fct_org_roles" (id),
    CONSTRAINT fk_iam_lnk_uor_granted_by       FOREIGN KEY (granted_by)
        REFERENCES "03_iam"."10_fct_users" (id)
);

COMMENT ON TABLE  "03_iam"."40_lnk_user_org_roles" IS
    'Many-to-many link: which org roles a user holds within a specific org.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_org_roles".id          IS 'UUID v7 PK.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_org_roles".user_id     IS 'FK to 10_fct_users.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_org_roles".org_id      IS 'FK to 10_fct_orgs — scope.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_org_roles".org_role_id IS 'FK to 10_fct_org_roles.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_org_roles".granted_by  IS 'FK to 10_fct_users — who granted this.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_org_roles".granted_at  IS 'Immutable grant timestamp.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_org_roles".is_active   IS 'false = revoked.';

GRANT SELECT ON "03_iam"."40_lnk_user_org_roles" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE ON "03_iam"."40_lnk_user_org_roles" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 10_fct_workspace_roles — per-workspace roles
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."10_fct_workspace_roles" (
    id           VARCHAR(36)  NOT NULL,
    org_id       VARCHAR(36)  NOT NULL,
    workspace_id VARCHAR(36)  NOT NULL,
    code         VARCHAR(64)  NOT NULL,
    name         VARCHAR(128) NOT NULL,
    category_id  SMALLINT     NOT NULL,
    is_system    BOOLEAN      NOT NULL DEFAULT false,
    is_active    BOOLEAN      NOT NULL DEFAULT true,
    deleted_at   TIMESTAMP,
    created_by   VARCHAR(36),
    updated_by   VARCHAR(36),
    created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_iam_fct_workspace_roles            PRIMARY KEY (id),
    CONSTRAINT uq_iam_fct_workspace_roles_ws_code    UNIQUE (workspace_id, code),
    CONSTRAINT fk_iam_fct_workspace_roles_org        FOREIGN KEY (org_id)
        REFERENCES "03_iam"."10_fct_orgs" (id),
    CONSTRAINT fk_iam_fct_workspace_roles_ws         FOREIGN KEY (workspace_id)
        REFERENCES "03_iam"."10_fct_workspaces" (id),
    CONSTRAINT fk_iam_fct_workspace_roles_cat        FOREIGN KEY (category_id)
        REFERENCES "03_iam"."06_dim_categories" (id)
);

COMMENT ON TABLE  "03_iam"."10_fct_workspace_roles" IS
    'Per-workspace roles. code is unique within a workspace. system=true rows are immutable.';
COMMENT ON COLUMN "03_iam"."10_fct_workspace_roles".id           IS 'UUID v7 primary key.';
COMMENT ON COLUMN "03_iam"."10_fct_workspace_roles".org_id       IS 'FK to 10_fct_orgs — denormalized for query convenience.';
COMMENT ON COLUMN "03_iam"."10_fct_workspace_roles".workspace_id IS 'FK to 10_fct_workspaces.';
COMMENT ON COLUMN "03_iam"."10_fct_workspace_roles".code         IS 'Stable identifier, unique within the workspace.';
COMMENT ON COLUMN "03_iam"."10_fct_workspace_roles".name         IS 'Display name.';
COMMENT ON COLUMN "03_iam"."10_fct_workspace_roles".category_id  IS 'FK to 06_dim_categories (category_type=''role'').';
COMMENT ON COLUMN "03_iam"."10_fct_workspace_roles".is_system    IS 'true = seeded; protected from deletion.';
COMMENT ON COLUMN "03_iam"."10_fct_workspace_roles".is_active    IS 'false = disabled.';
COMMENT ON COLUMN "03_iam"."10_fct_workspace_roles".deleted_at   IS 'Soft-delete timestamp. NULL = active.';
COMMENT ON COLUMN "03_iam"."10_fct_workspace_roles".created_by   IS 'UUID of creator.';
COMMENT ON COLUMN "03_iam"."10_fct_workspace_roles".updated_by   IS 'UUID of last updater.';
COMMENT ON COLUMN "03_iam"."10_fct_workspace_roles".created_at   IS 'Row creation timestamp (UTC).';
COMMENT ON COLUMN "03_iam"."10_fct_workspace_roles".updated_at   IS 'Last update timestamp (UTC).';

GRANT SELECT ON "03_iam"."10_fct_workspace_roles" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE ON "03_iam"."10_fct_workspace_roles" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 40_lnk_workspace_role_permissions
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."40_lnk_workspace_role_permissions" (
    id                  VARCHAR(36)  NOT NULL,
    workspace_role_id   VARCHAR(36)  NOT NULL,
    permission_id       VARCHAR(36)  NOT NULL,
    created_at          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_iam_lnk_workspace_role_perms      PRIMARY KEY (id),
    CONSTRAINT uq_iam_lnk_workspace_role_perms      UNIQUE (workspace_role_id, permission_id),
    CONSTRAINT fk_iam_lnk_wrp_workspace_role        FOREIGN KEY (workspace_role_id)
        REFERENCES "03_iam"."10_fct_workspace_roles" (id),
    CONSTRAINT fk_iam_lnk_wrp_permission            FOREIGN KEY (permission_id)
        REFERENCES "03_iam"."10_fct_permissions" (id)
);

COMMENT ON TABLE  "03_iam"."40_lnk_workspace_role_permissions" IS
    'Many-to-many link: which permissions a workspace role grants.';
COMMENT ON COLUMN "03_iam"."40_lnk_workspace_role_permissions".id                IS 'UUID v7 PK.';
COMMENT ON COLUMN "03_iam"."40_lnk_workspace_role_permissions".workspace_role_id IS 'FK to 10_fct_workspace_roles.';
COMMENT ON COLUMN "03_iam"."40_lnk_workspace_role_permissions".permission_id     IS 'FK to 10_fct_permissions.';
COMMENT ON COLUMN "03_iam"."40_lnk_workspace_role_permissions".created_at        IS 'Immutable creation timestamp.';

GRANT SELECT ON "03_iam"."40_lnk_workspace_role_permissions" TO tennetctl_read;
GRANT SELECT, INSERT, DELETE ON "03_iam"."40_lnk_workspace_role_permissions" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 40_lnk_user_workspace_roles
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."40_lnk_user_workspace_roles" (
    id                VARCHAR(36)  NOT NULL,
    user_id           VARCHAR(36)  NOT NULL,
    org_id            VARCHAR(36)  NOT NULL,
    workspace_id      VARCHAR(36)  NOT NULL,
    workspace_role_id VARCHAR(36)  NOT NULL,
    granted_by        VARCHAR(36),
    granted_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active         BOOLEAN      NOT NULL DEFAULT true,

    CONSTRAINT pk_iam_lnk_user_workspace_roles        PRIMARY KEY (id),
    CONSTRAINT uq_iam_lnk_user_workspace_roles        UNIQUE (user_id, workspace_id, workspace_role_id),
    CONSTRAINT fk_iam_lnk_uwr_user                   FOREIGN KEY (user_id)
        REFERENCES "03_iam"."10_fct_users" (id),
    CONSTRAINT fk_iam_lnk_uwr_org                    FOREIGN KEY (org_id)
        REFERENCES "03_iam"."10_fct_orgs" (id),
    CONSTRAINT fk_iam_lnk_uwr_workspace              FOREIGN KEY (workspace_id)
        REFERENCES "03_iam"."10_fct_workspaces" (id),
    CONSTRAINT fk_iam_lnk_uwr_workspace_role         FOREIGN KEY (workspace_role_id)
        REFERENCES "03_iam"."10_fct_workspace_roles" (id),
    CONSTRAINT fk_iam_lnk_uwr_granted_by             FOREIGN KEY (granted_by)
        REFERENCES "03_iam"."10_fct_users" (id)
);

COMMENT ON TABLE  "03_iam"."40_lnk_user_workspace_roles" IS
    'Many-to-many link: which workspace roles a user holds within a specific workspace.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_workspace_roles".id                IS 'UUID v7 PK.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_workspace_roles".user_id           IS 'FK to 10_fct_users.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_workspace_roles".org_id            IS 'FK to 10_fct_orgs — denormalized for query convenience.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_workspace_roles".workspace_id      IS 'FK to 10_fct_workspaces.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_workspace_roles".workspace_role_id IS 'FK to 10_fct_workspace_roles.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_workspace_roles".granted_by        IS 'FK to 10_fct_users — who granted this.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_workspace_roles".granted_at        IS 'Immutable grant timestamp.';
COMMENT ON COLUMN "03_iam"."40_lnk_user_workspace_roles".is_active         IS 'false = revoked.';

GRANT SELECT ON "03_iam"."40_lnk_user_workspace_roles" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE ON "03_iam"."40_lnk_user_workspace_roles" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- VIEWS
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW "03_iam"."v_platform_roles" AS
SELECT
    r.id,
    r.code,
    r.name,
    r.category_id,
    c.label       AS category_label,
    c.code        AS category_code,
    r.is_system,
    r.is_active,
    r.deleted_at,
    r.created_by,
    r.updated_by,
    r.created_at,
    r.updated_at
FROM "03_iam"."10_fct_platform_roles" r
LEFT JOIN "03_iam"."06_dim_categories" c ON c.id = r.category_id;

COMMENT ON VIEW "03_iam"."v_platform_roles" IS
    'Platform roles with category label resolved from dim_categories.';

GRANT SELECT ON "03_iam"."v_platform_roles" TO tennetctl_read;
GRANT SELECT ON "03_iam"."v_platform_roles" TO tennetctl_write;

CREATE OR REPLACE VIEW "03_iam"."v_org_roles" AS
SELECT
    r.id,
    r.org_id,
    o.slug        AS org_slug,
    r.code,
    r.name,
    r.category_id,
    c.label       AS category_label,
    c.code        AS category_code,
    r.is_system,
    r.is_active,
    r.deleted_at,
    r.created_by,
    r.updated_by,
    r.created_at,
    r.updated_at
FROM "03_iam"."10_fct_org_roles" r
LEFT JOIN "03_iam".v_orgs               o ON o.id   = r.org_id
LEFT JOIN "03_iam"."06_dim_categories"  c ON c.id   = r.category_id;

COMMENT ON VIEW "03_iam"."v_org_roles" IS
    'Org roles with org_slug and category label resolved.';

GRANT SELECT ON "03_iam"."v_org_roles" TO tennetctl_read;
GRANT SELECT ON "03_iam"."v_org_roles" TO tennetctl_write;

CREATE OR REPLACE VIEW "03_iam"."v_workspace_roles" AS
SELECT
    r.id,
    r.org_id,
    r.workspace_id,
    r.code,
    r.name,
    r.category_id,
    c.label       AS category_label,
    c.code        AS category_code,
    r.is_system,
    r.is_active,
    r.deleted_at,
    r.created_by,
    r.updated_by,
    r.created_at,
    r.updated_at
FROM "03_iam"."10_fct_workspace_roles" r
LEFT JOIN "03_iam"."06_dim_categories" c ON c.id = r.category_id;

COMMENT ON VIEW "03_iam"."v_workspace_roles" IS
    'Workspace roles with category label resolved.';

GRANT SELECT ON "03_iam"."v_workspace_roles" TO tennetctl_read;
GRANT SELECT ON "03_iam"."v_workspace_roles" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- SEED DATA
-- ---------------------------------------------------------------------------

-- 1. Permissions catalog
INSERT INTO "03_iam"."10_fct_permissions" (id, resource, action, description) VALUES
    (gen_random_uuid()::text, 'orgs',          'read',   'Read organisation data'),
    (gen_random_uuid()::text, 'orgs',          'write',  'Create and update organisations'),
    (gen_random_uuid()::text, 'orgs',          'admin',  'Full organisation administration'),
    (gen_random_uuid()::text, 'users',         'read',   'Read user data'),
    (gen_random_uuid()::text, 'users',         'write',  'Create and update users'),
    (gen_random_uuid()::text, 'users',         'admin',  'Full user administration'),
    (gen_random_uuid()::text, 'vault.secrets', 'read',   'Read vault secrets'),
    (gen_random_uuid()::text, 'vault.secrets', 'write',  'Write vault secrets'),
    (gen_random_uuid()::text, 'groups',        'read',   'Read groups'),
    (gen_random_uuid()::text, 'groups',        'write',  'Create and update groups'),
    (gen_random_uuid()::text, 'feature_flags', 'read',   'Read feature flags'),
    (gen_random_uuid()::text, 'feature_flags', 'write',  'Create and update feature flags'),
    (gen_random_uuid()::text, 'rbac',          'admin',  'Administer roles and permissions');

-- 2. Platform roles (system=true)
INSERT INTO "03_iam"."10_fct_platform_roles" (id, code, name, category_id, is_system, is_active) VALUES
    (
        gen_random_uuid()::text,
        'platform_admin',
        'Platform Administrator',
        (SELECT id FROM "03_iam"."06_dim_categories" WHERE category_type = 'role' AND code = 'system'),
        true,
        true
    ),
    (
        gen_random_uuid()::text,
        'platform_support',
        'Platform Support',
        (SELECT id FROM "03_iam"."06_dim_categories" WHERE category_type = 'role' AND code = 'support'),
        true,
        true
    ),
    (
        gen_random_uuid()::text,
        'platform_readonly',
        'Platform Read-Only',
        (SELECT id FROM "03_iam"."06_dim_categories" WHERE category_type = 'role' AND code = 'support'),
        true,
        true
    );

-- 3. Grant platform_admin all permissions
INSERT INTO "03_iam"."40_lnk_platform_role_permissions" (id, platform_role_id, permission_id)
SELECT
    gen_random_uuid()::text,
    r.id,
    p.id
FROM "03_iam"."10_fct_platform_roles" r
CROSS JOIN "03_iam"."10_fct_permissions" p
WHERE r.code = 'platform_admin';

-- 4. Assign first user (setup admin) the platform_admin role
INSERT INTO "03_iam"."40_lnk_user_platform_roles" (id, user_id, platform_role_id, granted_by, is_active)
SELECT
    gen_random_uuid()::text,
    u.id,
    r.id,
    u.id,
    true
FROM "03_iam"."10_fct_users" u
CROSS JOIN "03_iam"."10_fct_platform_roles" r
WHERE r.code = 'platform_admin'
ORDER BY u.created_at ASC
LIMIT 1;

-- DOWN =======================================================================

DROP TABLE IF EXISTS "03_iam"."40_lnk_user_workspace_roles"     CASCADE;
DROP TABLE IF EXISTS "03_iam"."40_lnk_workspace_role_permissions" CASCADE;
DROP TABLE IF EXISTS "03_iam"."10_fct_workspace_roles"           CASCADE;
DROP TABLE IF EXISTS "03_iam"."40_lnk_user_org_roles"            CASCADE;
DROP TABLE IF EXISTS "03_iam"."40_lnk_org_role_permissions"      CASCADE;
DROP TABLE IF EXISTS "03_iam"."10_fct_org_roles"                 CASCADE;
DROP TABLE IF EXISTS "03_iam"."40_lnk_user_platform_roles"       CASCADE;
DROP TABLE IF EXISTS "03_iam"."40_lnk_platform_role_permissions" CASCADE;
DROP TABLE IF EXISTS "03_iam"."10_fct_platform_roles"            CASCADE;
DROP TABLE IF EXISTS "03_iam"."10_fct_permissions"               CASCADE;
DROP VIEW  IF EXISTS "03_iam"."v_platform_roles";
DROP VIEW  IF EXISTS "03_iam"."v_org_roles";
DROP VIEW  IF EXISTS "03_iam"."v_workspace_roles";
