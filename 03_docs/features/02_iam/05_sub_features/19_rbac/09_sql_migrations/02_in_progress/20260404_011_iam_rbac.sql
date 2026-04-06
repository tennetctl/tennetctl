-- =============================================================================
-- Migration: 20260404_011_iam_rbac.sql
-- Description: RBAC — roles, permissions, role-permission assignments, group-role links
-- UP
-- =============================================================================

SET search_path TO "02_iam", public;

-- ---------------------------------------------------------------------------
-- Fact: roles
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."23_fct_roles" (
    id          VARCHAR(36)  NOT NULL,
    org_id      VARCHAR(36),
    key         TEXT         NOT NULL,
    name        TEXT         NOT NULL,
    description TEXT,
    is_system   BOOLEAN      NOT NULL DEFAULT false,
    is_active   BOOLEAN      NOT NULL DEFAULT true,
    is_test     BOOLEAN      NOT NULL DEFAULT false,
    deleted_at  TIMESTAMP,
    created_by  VARCHAR(36),
    updated_by  VARCHAR(36),
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_fct_roles PRIMARY KEY (id)
);
COMMENT ON TABLE "02_iam"."23_fct_roles" IS 'RBAC role definitions. org_id=NULL means platform-wide.';
COMMENT ON COLUMN "02_iam"."23_fct_roles".key IS 'Unique slug for API reference. Lowercase, hyphens, underscores.';
COMMENT ON COLUMN "02_iam"."23_fct_roles".is_system IS 'System roles cannot be deleted.';

CREATE UNIQUE INDEX idx_uq_fct_roles_key
    ON "02_iam"."23_fct_roles" (key)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_fct_roles_org ON "02_iam"."23_fct_roles" (org_id)
    WHERE deleted_at IS NULL;

CREATE TRIGGER trg_fct_roles_updated_at
    BEFORE UPDATE ON "02_iam"."23_fct_roles"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- Seed system roles
INSERT INTO "02_iam"."23_fct_roles" (id, key, name, description, is_system) VALUES
    ('00000000-0000-0000-0000-000000000001', 'super-admin',  'Super Admin',  'Full platform access', true),
    ('00000000-0000-0000-0000-000000000002', 'org-admin',    'Org Admin',    'Full access within an organisation', true),
    ('00000000-0000-0000-0000-000000000003', 'org-member',   'Org Member',   'Standard member access', true),
    ('00000000-0000-0000-0000-000000000004', 'org-viewer',   'Org Viewer',   'Read-only access', true);

-- ---------------------------------------------------------------------------
-- Fact: permissions
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."26_fct_permissions" (
    id          VARCHAR(36)  NOT NULL,
    resource    TEXT         NOT NULL,
    action      TEXT         NOT NULL,
    description TEXT,
    is_system   BOOLEAN      NOT NULL DEFAULT false,
    is_active   BOOLEAN      NOT NULL DEFAULT true,
    is_test     BOOLEAN      NOT NULL DEFAULT false,
    deleted_at  TIMESTAMP,
    created_by  VARCHAR(36),
    updated_by  VARCHAR(36),
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_fct_permissions PRIMARY KEY (id),
    CONSTRAINT uq_fct_permissions_resource_action UNIQUE (resource, action)
);
COMMENT ON TABLE "02_iam"."26_fct_permissions" IS 'Permission catalogue. resource:action pairs (e.g. org:read, user:delete).';

CREATE TRIGGER trg_fct_permissions_updated_at
    BEFORE UPDATE ON "02_iam"."26_fct_permissions"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- Seed core permissions
INSERT INTO "02_iam"."26_fct_permissions" (id, resource, action, description, is_system) VALUES
    ('00000000-0000-0000-0000-000000000101', 'org',       'create', 'Create organisations', true),
    ('00000000-0000-0000-0000-000000000102', 'org',       'read',   'View organisations', true),
    ('00000000-0000-0000-0000-000000000103', 'org',       'update', 'Update organisations', true),
    ('00000000-0000-0000-0000-000000000104', 'org',       'delete', 'Delete organisations', true),
    ('00000000-0000-0000-0000-000000000105', 'user',      'create', 'Create users', true),
    ('00000000-0000-0000-0000-000000000106', 'user',      'read',   'View users', true),
    ('00000000-0000-0000-0000-000000000107', 'user',      'update', 'Update users', true),
    ('00000000-0000-0000-0000-000000000108', 'user',      'delete', 'Delete users', true),
    ('00000000-0000-0000-0000-000000000109', 'workspace', 'create', 'Create workspaces', true),
    ('00000000-0000-0000-0000-000000000110', 'workspace', 'read',   'View workspaces', true),
    ('00000000-0000-0000-0000-000000000111', 'workspace', 'update', 'Update workspaces', true),
    ('00000000-0000-0000-0000-000000000112', 'workspace', 'delete', 'Delete workspaces', true),
    ('00000000-0000-0000-0000-000000000113', 'group',     'create', 'Create groups', true),
    ('00000000-0000-0000-0000-000000000114', 'group',     'read',   'View groups', true),
    ('00000000-0000-0000-0000-000000000115', 'group',     'update', 'Update groups', true),
    ('00000000-0000-0000-0000-000000000116', 'group',     'delete', 'Delete groups', true),
    ('00000000-0000-0000-0000-000000000117', 'role',      'create', 'Create roles', true),
    ('00000000-0000-0000-0000-000000000118', 'role',      'read',   'View roles', true),
    ('00000000-0000-0000-0000-000000000119', 'role',      'update', 'Update roles', true),
    ('00000000-0000-0000-0000-000000000120', 'role',      'delete', 'Delete roles', true),
    ('00000000-0000-0000-0000-000000000121', 'flag',      'create', 'Create feature flags', true),
    ('00000000-0000-0000-0000-000000000122', 'flag',      'read',   'View feature flags', true),
    ('00000000-0000-0000-0000-000000000123', 'flag',      'update', 'Update feature flags', true),
    ('00000000-0000-0000-0000-000000000124', 'flag',      'delete', 'Delete feature flags', true),
    ('00000000-0000-0000-0000-000000000125', 'audit',     'read',   'View audit logs', true);

-- ---------------------------------------------------------------------------
-- Link: role ↔ permission assignments
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."33_lnk_role_permissions" (
    id              VARCHAR(36)  NOT NULL,
    role_id         VARCHAR(36)  NOT NULL,
    permission_id   VARCHAR(36)  NOT NULL,
    created_by      VARCHAR(36),
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_lnk_role_permissions PRIMARY KEY (id),
    CONSTRAINT fk_lnk_role_permissions_role FOREIGN KEY (role_id)
        REFERENCES "02_iam"."23_fct_roles"(id) ON DELETE CASCADE,
    CONSTRAINT fk_lnk_role_permissions_perm FOREIGN KEY (permission_id)
        REFERENCES "02_iam"."26_fct_permissions"(id) ON DELETE CASCADE,
    CONSTRAINT uq_lnk_role_permissions UNIQUE (role_id, permission_id)
);
COMMENT ON TABLE "02_iam"."33_lnk_role_permissions" IS 'Many-to-many: which permissions each role grants.';

-- Seed super-admin with all permissions
INSERT INTO "02_iam"."33_lnk_role_permissions" (id, role_id, permission_id)
SELECT
    '00000000-0000-0000-0001-' || LPAD(ROW_NUMBER() OVER ()::text, 12, '0'),
    '00000000-0000-0000-0000-000000000001',
    p.id
FROM "02_iam"."26_fct_permissions" p;

-- ---------------------------------------------------------------------------
-- Link: group ↔ role assignments
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."36_lnk_group_roles" (
    id          VARCHAR(36)  NOT NULL,
    group_id    VARCHAR(36)  NOT NULL,
    role_id     VARCHAR(36)  NOT NULL,
    created_by  VARCHAR(36),
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_lnk_group_roles PRIMARY KEY (id),
    CONSTRAINT fk_lnk_group_roles_group FOREIGN KEY (group_id)
        REFERENCES "02_iam"."07_fct_groups"(id) ON DELETE CASCADE,
    CONSTRAINT fk_lnk_group_roles_role FOREIGN KEY (role_id)
        REFERENCES "02_iam"."23_fct_roles"(id) ON DELETE CASCADE,
    CONSTRAINT uq_lnk_group_roles UNIQUE (group_id, role_id)
);
COMMENT ON TABLE "02_iam"."36_lnk_group_roles" IS 'Many-to-many: roles assigned to groups. Users inherit permissions via group membership.';

-- ---------------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW "02_iam".v_roles AS
SELECT
    r.id, r.org_id, r.key, r.name, r.description,
    r.is_system, r.is_active,
    r.deleted_at, r.deleted_at IS NOT NULL AS is_deleted,
    r.created_by, r.updated_by, r.created_at, r.updated_at,
    COALESCE(pc.cnt, 0) AS permission_count
FROM "02_iam"."23_fct_roles" r
LEFT JOIN (
    SELECT role_id, COUNT(*) AS cnt
    FROM "02_iam"."33_lnk_role_permissions"
    GROUP BY role_id
) pc ON pc.role_id = r.id;

CREATE OR REPLACE VIEW "02_iam".v_permissions AS
SELECT
    p.id, p.resource, p.action, p.description,
    p.is_system, p.is_active,
    p.deleted_at, p.deleted_at IS NOT NULL AS is_deleted,
    p.created_at, p.updated_at
FROM "02_iam"."26_fct_permissions" p;

-- =============================================================================
-- DOWN
-- =============================================================================

DROP VIEW  IF EXISTS "02_iam".v_permissions;
DROP VIEW  IF EXISTS "02_iam".v_roles;
DROP TABLE IF EXISTS "02_iam"."36_lnk_group_roles" CASCADE;
DROP TABLE IF EXISTS "02_iam"."33_lnk_role_permissions" CASCADE;
DROP TABLE IF EXISTS "02_iam"."26_fct_permissions" CASCADE;
DROP TABLE IF EXISTS "02_iam"."23_fct_roles" CASCADE;
