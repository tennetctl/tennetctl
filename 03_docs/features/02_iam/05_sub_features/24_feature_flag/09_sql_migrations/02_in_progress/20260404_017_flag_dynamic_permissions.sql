-- =============================================================================
-- Migration: 20260404_017_flag_dynamic_permissions.sql
-- Sub-feature: 24_feature_flag
-- Description: Dynamic per-flag permissions. Each flag defines which actions
--   are available on it (enable/disable, view/edit/create/delete, approve, etc.)
--   via dim_permission_actions + lnk_flag_permission_actions.
--   Roles are then granted specific actions on specific flags.
-- UP
-- =============================================================================

SET search_path TO "02_iam", public;

-- ---------------------------------------------------------------------------
-- Dimension: permission actions (the universe of possible actions)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."dim_permission_actions" (
    id          SMALLINT    NOT NULL,
    code        TEXT        NOT NULL,
    label       TEXT        NOT NULL,
    description TEXT,
    category    TEXT        NOT NULL DEFAULT 'general',
    deprecated_at TIMESTAMP,

    CONSTRAINT pk_dim_permission_actions PRIMARY KEY (id),
    CONSTRAINT uq_dim_permission_actions_code UNIQUE (code)
);
COMMENT ON TABLE "02_iam"."dim_permission_actions" IS
    'Universe of permission actions. Each feature/flag picks which actions apply to it.';

INSERT INTO "02_iam"."dim_permission_actions" (id, code, label, description, category) VALUES
    -- Standard CRUD
    (1,  'view',         'View',          'Read/view the resource',               'crud'),
    (2,  'create',       'Create',        'Create new instances',                 'crud'),
    (3,  'edit',         'Edit',          'Modify existing instances',            'crud'),
    (4,  'delete',       'Delete',        'Remove instances (soft-delete)',       'crud'),
    -- Toggle / State
    (5,  'enable',       'Enable',        'Activate / turn on',                  'state'),
    (6,  'disable',      'Disable',       'Deactivate / turn off',               'state'),
    (7,  'toggle',       'Toggle',        'Switch between on and off',           'state'),
    -- Lifecycle
    (8,  'publish',      'Publish',       'Move from draft to active',           'lifecycle'),
    (9,  'deprecate',    'Deprecate',     'Mark as deprecated',                  'lifecycle'),
    (10, 'archive',      'Archive',       'Move to archived state',              'lifecycle'),
    -- Governance
    (11, 'approve',      'Approve',       'Approve a change request',            'governance'),
    (12, 'reject',       'Reject',        'Reject a change request',             'governance'),
    (13, 'review',       'Review',        'Review before publishing',            'governance'),
    -- Data
    (14, 'export',       'Export',        'Export data (CSV, JSON)',              'data'),
    (15, 'import',       'Import',        'Import data in bulk',                 'data'),
    (16, 'bulk_update',  'Bulk Update',   'Update multiple items at once',       'data'),
    -- Operational
    (17, 'evaluate',     'Evaluate',      'Evaluate flag value (SDK)',            'operational'),
    (18, 'override',     'Override',      'Set per-org/user override values',    'operational'),
    (19, 'promote',      'Promote',       'Promote config across environments',  'operational'),
    (20, 'kill_switch',  'Kill Switch',   'Emergency disable',                   'operational'),
    -- Metering
    (21, 'meter',        'Meter',         'Increment usage counter',             'metering'),
    (22, 'set_quota',    'Set Quota',     'Configure usage quotas',              'metering'),
    -- Admin
    (23, 'manage_rules', 'Manage Rules',  'Add/remove targeting rules',          'admin'),
    (24, 'manage_variants', 'Manage Variants', 'Add/remove A/B variants',       'admin'),
    (25, 'manage_targets',  'Manage Targets',  'Add/remove identity targets',   'admin'),
    (26, 'manage_envs',  'Manage Envs',   'Configure per-environment settings',  'admin'),
    (27, 'manage_tags',  'Manage Tags',   'Assign/remove tags',                  'admin'),
    (28, 'manage_prereqs', 'Manage Prerequisites', 'Set flag dependencies',     'admin'),
    (29, 'assign',       'Assign',        'Assign to org/user/group',            'admin'),
    (30, 'configure',    'Configure',     'Modify settings/config',              'admin');

-- Sequence for custom actions
CREATE SEQUENCE "02_iam".seq_permission_action_id START 100;

-- ---------------------------------------------------------------------------
-- Link: which actions are available on each flag
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."63_lnk_flag_permission_actions" (
    id              VARCHAR(36)  NOT NULL,
    flag_id         VARCHAR(36)  NOT NULL,
    action_id       SMALLINT     NOT NULL,
    is_required     BOOLEAN      NOT NULL DEFAULT false,
    created_by      VARCHAR(36),
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_lnk_flag_permission_actions PRIMARY KEY (id),
    CONSTRAINT fk_lnk_flag_perm_actions_flag FOREIGN KEY (flag_id)
        REFERENCES "02_iam"."22_fct_feature_flags"(id) ON DELETE CASCADE,
    CONSTRAINT fk_lnk_flag_perm_actions_action FOREIGN KEY (action_id)
        REFERENCES "02_iam"."dim_permission_actions"(id),
    CONSTRAINT uq_lnk_flag_permission_actions UNIQUE (flag_id, action_id)
);
COMMENT ON TABLE "02_iam"."63_lnk_flag_permission_actions" IS
    'Which permission actions are available on each specific flag. '
    'A boolean flag might only have [view, toggle]. '
    'A metered flag might have [view, edit, toggle, meter, set_quota, export].';
COMMENT ON COLUMN "02_iam"."63_lnk_flag_permission_actions".is_required IS
    'If true, the action MUST be explicitly granted — no default allow.';

CREATE INDEX idx_lnk_flag_perm_actions_flag ON "02_iam"."63_lnk_flag_permission_actions" (flag_id);

-- ---------------------------------------------------------------------------
-- Link: role → flag → action grants (who can do what on which flag)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."64_lnk_role_flag_grants" (
    id              VARCHAR(36)  NOT NULL,
    role_id         VARCHAR(36)  NOT NULL,
    flag_id         VARCHAR(36)  NOT NULL,
    action_id       SMALLINT     NOT NULL,
    created_by      VARCHAR(36),
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_lnk_role_flag_grants PRIMARY KEY (id),
    CONSTRAINT fk_lnk_role_flag_grants_role FOREIGN KEY (role_id)
        REFERENCES "02_iam"."23_fct_roles"(id) ON DELETE CASCADE,
    CONSTRAINT fk_lnk_role_flag_grants_flag FOREIGN KEY (flag_id)
        REFERENCES "02_iam"."22_fct_feature_flags"(id) ON DELETE CASCADE,
    CONSTRAINT fk_lnk_role_flag_grants_action FOREIGN KEY (action_id)
        REFERENCES "02_iam"."dim_permission_actions"(id),
    CONSTRAINT uq_lnk_role_flag_grants UNIQUE (role_id, flag_id, action_id)
);
COMMENT ON TABLE "02_iam"."64_lnk_role_flag_grants" IS
    'Granular: which role can perform which action on which specific flag. '
    'Super admin bypasses this — gets all actions on all flags.';

CREATE INDEX idx_lnk_role_flag_grants_role ON "02_iam"."64_lnk_role_flag_grants" (role_id);
CREATE INDEX idx_lnk_role_flag_grants_flag ON "02_iam"."64_lnk_role_flag_grants" (flag_id);

-- ---------------------------------------------------------------------------
-- View: flag permissions with resolved action labels
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW "02_iam".v_flag_permission_actions AS
SELECT
    fpa.id,
    fpa.flag_id,
    f.key       AS flag_key,
    f.name      AS flag_name,
    fpa.action_id,
    a.code      AS action_code,
    a.label     AS action_label,
    a.category  AS action_category,
    fpa.is_required,
    fpa.created_at
FROM "02_iam"."63_lnk_flag_permission_actions" fpa
JOIN "02_iam"."22_fct_feature_flags" f ON f.id = fpa.flag_id
JOIN "02_iam"."dim_permission_actions" a ON a.id = fpa.action_id;

-- ---------------------------------------------------------------------------
-- View: role flag grants with resolved names
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW "02_iam".v_role_flag_grants AS
SELECT
    g.id,
    g.role_id,
    r.key       AS role_key,
    r.name      AS role_name,
    g.flag_id,
    f.key       AS flag_key,
    f.name      AS flag_name,
    g.action_id,
    a.code      AS action_code,
    a.label     AS action_label,
    g.created_at
FROM "02_iam"."64_lnk_role_flag_grants" g
JOIN "02_iam"."23_fct_roles" r ON r.id = g.role_id
JOIN "02_iam"."22_fct_feature_flags" f ON f.id = g.flag_id
JOIN "02_iam"."dim_permission_actions" a ON a.id = g.action_id;

-- =============================================================================
-- DOWN
-- =============================================================================

DROP VIEW  IF EXISTS "02_iam".v_role_flag_grants;
DROP VIEW  IF EXISTS "02_iam".v_flag_permission_actions;
DROP TABLE IF EXISTS "02_iam"."64_lnk_role_flag_grants" CASCADE;
DROP TABLE IF EXISTS "02_iam"."63_lnk_flag_permission_actions" CASCADE;
DROP SEQUENCE IF EXISTS "02_iam".seq_permission_action_id;
DROP TABLE IF EXISTS "02_iam"."dim_permission_actions" CASCADE;
