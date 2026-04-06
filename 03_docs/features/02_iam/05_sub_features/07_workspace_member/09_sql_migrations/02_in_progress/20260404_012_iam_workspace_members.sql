-- =============================================================================
-- Migration: 20260404_012_iam_workspace_members.sql
-- Description: Workspace membership — link users to workspaces with roles
-- UP
-- =============================================================================

SET search_path TO "02_iam", public;

CREATE TABLE "02_iam"."dim_workspace_roles" (
    id    SMALLINT NOT NULL,
    name  TEXT     NOT NULL,

    CONSTRAINT pk_dim_workspace_roles PRIMARY KEY (id),
    CONSTRAINT uq_dim_workspace_roles_name UNIQUE (name)
);
COMMENT ON TABLE "02_iam"."dim_workspace_roles" IS 'Lookup: workspace membership roles.';

INSERT INTO "02_iam"."dim_workspace_roles" (id, name) VALUES
    (1, 'admin'),
    (2, 'member'),
    (3, 'viewer');

CREATE TABLE "02_iam"."11_lnk_workspace_members" (
    id              VARCHAR(36)  NOT NULL,
    workspace_id    VARCHAR(36)  NOT NULL,
    user_id         VARCHAR(36)  NOT NULL,
    role_id         SMALLINT     NOT NULL DEFAULT 2,
    invited_by      VARCHAR(36),
    created_by      VARCHAR(36),
    updated_by      VARCHAR(36),
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TIMESTAMP,

    CONSTRAINT pk_lnk_workspace_members PRIMARY KEY (id),
    CONSTRAINT fk_lnk_workspace_members_role FOREIGN KEY (role_id)
        REFERENCES "02_iam"."dim_workspace_roles"(id)
);
COMMENT ON TABLE "02_iam"."11_lnk_workspace_members" IS 'Links users to workspaces with roles.';

CREATE UNIQUE INDEX idx_uq_lnk_workspace_members
    ON "02_iam"."11_lnk_workspace_members" (workspace_id, user_id)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_lnk_workspace_members_ws ON "02_iam"."11_lnk_workspace_members" (workspace_id)
    WHERE deleted_at IS NULL;

CREATE TRIGGER trg_lnk_workspace_members_updated_at
    BEFORE UPDATE ON "02_iam"."11_lnk_workspace_members"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

CREATE OR REPLACE VIEW "02_iam".v_workspace_members AS
SELECT
    wm.id, wm.workspace_id, wm.user_id, wm.role_id,
    wr.name AS role_name,
    wm.invited_by, wm.created_by, wm.updated_by,
    wm.created_at, wm.updated_at, wm.deleted_at,
    wm.deleted_at IS NOT NULL AS is_deleted
FROM "02_iam"."11_lnk_workspace_members" wm
JOIN "02_iam"."dim_workspace_roles" wr ON wr.id = wm.role_id;

-- =============================================================================
-- DOWN
-- =============================================================================

DROP VIEW  IF EXISTS "02_iam".v_workspace_members;
DROP TABLE IF EXISTS "02_iam"."11_lnk_workspace_members" CASCADE;
DROP TABLE IF EXISTS "02_iam"."dim_workspace_roles" CASCADE;
