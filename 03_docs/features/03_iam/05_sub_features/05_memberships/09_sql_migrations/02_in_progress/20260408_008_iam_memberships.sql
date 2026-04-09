-- =============================================================================
-- Migration:   20260408_008_iam_memberships.sql
-- Module:      03_iam / Sub-feature: 05_memberships / Sequence: 008
-- Depends on:  007 (workspaces)
-- =============================================================================

-- UP ====

CREATE TABLE "03_iam"."40_lnk_user_orgs" (
    id          VARCHAR(36) NOT NULL,
    org_id      VARCHAR(36) NOT NULL,
    user_id     VARCHAR(36) NOT NULL,
    created_by  VARCHAR(36) NOT NULL,
    created_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_iam_lnk_user_orgs            PRIMARY KEY (id),
    CONSTRAINT fk_iam_lnk_user_orgs_org        FOREIGN KEY (org_id)
        REFERENCES "03_iam"."10_fct_orgs" (id),
    CONSTRAINT fk_iam_lnk_user_orgs_user       FOREIGN KEY (user_id)
        REFERENCES "03_iam"."10_fct_users" (id),
    CONSTRAINT fk_iam_lnk_user_orgs_created_by FOREIGN KEY (created_by)
        REFERENCES "03_iam"."10_fct_users" (id) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT uq_iam_lnk_user_orgs_pair       UNIQUE (org_id, user_id)
);
CREATE INDEX idx_iam_lnk_user_orgs_user_id ON "03_iam"."40_lnk_user_orgs" (user_id);
CREATE INDEX idx_iam_lnk_user_orgs_org_id  ON "03_iam"."40_lnk_user_orgs" (org_id);

CREATE TABLE "03_iam"."40_lnk_user_workspaces" (
    id            VARCHAR(36) NOT NULL,
    org_id        VARCHAR(36) NOT NULL,
    workspace_id  VARCHAR(36) NOT NULL,
    user_id       VARCHAR(36) NOT NULL,
    created_by    VARCHAR(36) NOT NULL,
    created_at    TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_iam_lnk_user_workspaces             PRIMARY KEY (id),
    CONSTRAINT fk_iam_lnk_user_workspaces_org         FOREIGN KEY (org_id)
        REFERENCES "03_iam"."10_fct_orgs" (id),
    CONSTRAINT fk_iam_lnk_user_workspaces_workspace   FOREIGN KEY (workspace_id)
        REFERENCES "03_iam"."10_fct_workspaces" (id),
    CONSTRAINT fk_iam_lnk_user_workspaces_user        FOREIGN KEY (user_id)
        REFERENCES "03_iam"."10_fct_users" (id),
    CONSTRAINT fk_iam_lnk_user_workspaces_created_by  FOREIGN KEY (created_by)
        REFERENCES "03_iam"."10_fct_users" (id) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT uq_iam_lnk_user_workspaces_pair        UNIQUE (workspace_id, user_id)
);
CREATE INDEX idx_iam_lnk_user_workspaces_user_id      ON "03_iam"."40_lnk_user_workspaces" (user_id);
CREATE INDEX idx_iam_lnk_user_workspaces_workspace_id ON "03_iam"."40_lnk_user_workspaces" (workspace_id);
CREATE INDEX idx_iam_lnk_user_workspaces_org_id       ON "03_iam"."40_lnk_user_workspaces" (org_id);

GRANT SELECT, INSERT, DELETE ON "03_iam"."40_lnk_user_orgs"       TO tennetctl_write;
GRANT SELECT, INSERT, DELETE ON "03_iam"."40_lnk_user_workspaces" TO tennetctl_write;
GRANT SELECT ON "03_iam"."40_lnk_user_orgs"       TO tennetctl_read;
GRANT SELECT ON "03_iam"."40_lnk_user_workspaces" TO tennetctl_read;

-- v_user_orgs
CREATE VIEW "03_iam".v_user_orgs AS
SELECT
    l.id,
    l.user_id,
    l.org_id,
    o.slug        AS org_slug,
    o.name        AS org_name,
    o.status      AS org_status,
    o.is_active   AS org_is_active,
    l.created_by,
    l.created_at
FROM "03_iam"."40_lnk_user_orgs" l
JOIN "03_iam".v_orgs o ON o.id = l.org_id;

-- v_user_workspaces
CREATE VIEW "03_iam".v_user_workspaces AS
SELECT
    l.id,
    l.user_id,
    l.org_id,
    l.workspace_id,
    w.slug        AS workspace_slug,
    w.name        AS workspace_name,
    w.status      AS workspace_status,
    w.is_active   AS workspace_is_active,
    l.created_by,
    l.created_at
FROM "03_iam"."40_lnk_user_workspaces" l
JOIN "03_iam".v_workspaces w ON w.id = l.workspace_id;

GRANT SELECT ON "03_iam".v_user_orgs       TO tennetctl_read;
GRANT SELECT ON "03_iam".v_user_orgs       TO tennetctl_write;
GRANT SELECT ON "03_iam".v_user_workspaces TO tennetctl_read;
GRANT SELECT ON "03_iam".v_user_workspaces TO tennetctl_write;

-- DOWN ====
DROP VIEW  IF EXISTS "03_iam".v_user_workspaces;
DROP VIEW  IF EXISTS "03_iam".v_user_orgs;
DROP TABLE IF EXISTS "03_iam"."40_lnk_user_workspaces";
DROP TABLE IF EXISTS "03_iam"."40_lnk_user_orgs";
