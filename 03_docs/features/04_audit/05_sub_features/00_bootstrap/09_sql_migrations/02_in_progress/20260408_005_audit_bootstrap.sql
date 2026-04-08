-- Migration: 20260408_005_audit_bootstrap
-- Creates the 04_audit schema with a pure-EAV append-only audit log.
-- Sequence: 5
-- Depends on: 0 (schema_migrations bootstrap), 3 (IAM bootstrap — we reference
--             iam users/sessions/orgs/workspaces conceptually; FKs are NOT
--             enforced because audit rows must outlive soft-deletes).
--
-- Design rules enforced here:
--   * No business columns on fct-style tables (Sri's "no perf exception" rule).
--   * Every audit row carries FOUR scope columns: org_id, workspace_id,
--     user_id, session_id. These are FK-like scope columns — the one
--     documented exception to the no-business-columns rule, justified by
--     .claude/rules/common/database.md which mandates org_id on evt_* tables.
--   * A CHECK constraint enforces that user_id and session_id are mandatory
--     for every authenticated event, with two encoded exceptions:
--       1. category = 'setup' — wizard events have no user/session yet.
--       2. outcome  = 'failure' — session_id NULL allowed for failed logins.
--     The CHECK is created inside a DO block because subqueries are illegal
--     in CHECK constraints; the dim IDs are resolved at migration time and
--     interpolated as SMALLINT literals.
--   * All non-scope context (target_id, target_type, ip_address, user_agent,
--     metadata) lives in 20_dtl_attrs via 05_dim_attr_defs.

-- UP ====

CREATE SCHEMA IF NOT EXISTS "04_audit";

COMMENT ON SCHEMA "04_audit" IS
  'Audit trail. Append-only — no UPDATE or DELETE ever touches this schema. '
  '60_evt_events carries org_id, workspace_id, user_id, session_id as '
  'mandatory scope columns. All other context lives in 20_dtl_attrs.';

-- ---------------------------------------------------------------------------
-- 01_dim_event_categories
-- ---------------------------------------------------------------------------
CREATE TABLE "04_audit"."01_dim_event_categories" (
    id            SMALLINT    GENERATED ALWAYS AS IDENTITY,
    code          TEXT        NOT NULL,
    label         TEXT        NOT NULL,
    description   TEXT,
    deprecated_at TIMESTAMP,
    --
    CONSTRAINT pk_audit_event_categories      PRIMARY KEY (id),
    CONSTRAINT uq_audit_event_categories_code UNIQUE (code)
);

COMMENT ON TABLE "04_audit"."01_dim_event_categories" IS
  'Coarse grouping for audit events (iam, vault, setup). Extend by INSERT.';

INSERT INTO "04_audit"."01_dim_event_categories" (code, label, description) VALUES
  ('iam',   'IAM',   'Identity and access management events.'),
  ('vault', 'Vault', 'Vault read/write events.'),
  ('setup', 'Setup', 'Installer wizard events. Allowed to have NULL user/session.');

-- ---------------------------------------------------------------------------
-- 02_dim_event_outcomes
-- ---------------------------------------------------------------------------
CREATE TABLE "04_audit"."02_dim_event_outcomes" (
    id            SMALLINT    GENERATED ALWAYS AS IDENTITY,
    code          TEXT        NOT NULL,
    label         TEXT        NOT NULL,
    description   TEXT,
    deprecated_at TIMESTAMP,
    --
    CONSTRAINT pk_audit_event_outcomes      PRIMARY KEY (id),
    CONSTRAINT uq_audit_event_outcomes_code UNIQUE (code)
);

COMMENT ON TABLE "04_audit"."02_dim_event_outcomes" IS
  'Outcome of the audited action. Extend by INSERT.';

INSERT INTO "04_audit"."02_dim_event_outcomes" (code, label, description) VALUES
  ('success', 'Success', 'Action completed successfully.'),
  ('failure', 'Failure', 'Action failed or was rejected. Allowed to have NULL session_id.');

-- ---------------------------------------------------------------------------
-- 03_dim_event_actions
-- Every distinct audit action code lives here. Extending the audit with a
-- new action is an INSERT here, not an ALTER TABLE on the evt table.
-- ---------------------------------------------------------------------------
CREATE TABLE "04_audit"."03_dim_event_actions" (
    id            SMALLINT    GENERATED ALWAYS AS IDENTITY,
    code          TEXT        NOT NULL,
    label         TEXT        NOT NULL,
    description   TEXT,
    deprecated_at TIMESTAMP,
    --
    CONSTRAINT pk_audit_event_actions      PRIMARY KEY (id),
    CONSTRAINT uq_audit_event_actions_code UNIQUE (code)
);

COMMENT ON TABLE "04_audit"."03_dim_event_actions" IS
  'Registered audit action codes. Extend by INSERT — never by ALTER TABLE.';

INSERT INTO "04_audit"."03_dim_event_actions" (code, label, description) VALUES
  ('session.login',          'Session Login',            'User completed a successful login.'),
  ('session.login_failed',   'Session Login Failed',     'Login attempt rejected. No session_id.'),
  ('session.refresh',        'Session Refresh',          'Refresh token rotated.'),
  ('session.switch_scope',   'Session Switch Scope',     'Active org or workspace changed.'),
  ('session.logout',         'Session Logout',           'Session soft-deleted.'),
  ('user.created',           'User Created',             'New user row inserted.'),
  ('user.updated',           'User Updated',             'User attribute changed.'),
  ('user.password_reset',    'User Password Reset',      'Password hash replaced.'),
  ('org.created',            'Org Created',              'New org created.'),
  ('org.updated',            'Org Updated',              'Org attribute changed.'),
  ('org.archived',           'Org Archived',             'Org marked is_active=false.'),
  ('workspace.created',      'Workspace Created',        'New workspace created.'),
  ('workspace.updated',      'Workspace Updated',        'Workspace attribute changed.'),
  ('workspace.archived',     'Workspace Archived',       'Workspace marked is_active=false.'),
  ('membership.org_added',   'Org Membership Added',     'User added to org.'),
  ('membership.org_removed', 'Org Membership Removed',   'User removed from org.'),
  ('membership.ws_added',    'Workspace Membership Added',   'User added to workspace.'),
  ('membership.ws_removed',  'Workspace Membership Removed', 'User removed from workspace.'),
  ('vault.unseal',           'Vault Unseal',             'Vault unsealed on boot.'),
  ('vault.secret_create',    'Vault Secret Create',      'New secret sealed.'),
  ('vault.secret_read',      'Vault Secret Read',        'Secret decrypted for caller.'),
  ('setup.phase_complete',   'Setup Phase Complete',     'Installer wizard phase marker.'),
  ('unknown',                'Unknown',                  'Fallback when an action code is unregistered.');

-- ---------------------------------------------------------------------------
-- 04_dim_entity_types
-- Entity types referenced by 05_dim_attr_defs and 20_dtl_attrs.
-- The 'audit_event' entry is used to scope attrs on events themselves.
-- ---------------------------------------------------------------------------
CREATE TABLE "04_audit"."04_dim_entity_types" (
    id            SMALLINT    GENERATED ALWAYS AS IDENTITY,
    code          TEXT        NOT NULL,
    label         TEXT        NOT NULL,
    description   TEXT,
    deprecated_at TIMESTAMP,
    --
    CONSTRAINT pk_audit_dim_entity_types      PRIMARY KEY (id),
    CONSTRAINT uq_audit_dim_entity_types_code UNIQUE (code)
);

INSERT INTO "04_audit"."04_dim_entity_types" (code, label, description) VALUES
  ('audit_event',  'Audit Event',  'A row in 60_evt_events. Owns its own attrs.'),
  ('iam_user',     'IAM User',     'Target type for events acting on a user.'),
  ('iam_session',  'IAM Session',  'Target type for events acting on a session.'),
  ('iam_org',      'IAM Org',      'Target type for events acting on an org.'),
  ('iam_workspace','IAM Workspace','Target type for events acting on a workspace.'),
  ('vault_secret', 'Vault Secret', 'Target type for events acting on a secret.');

-- ---------------------------------------------------------------------------
-- 05_dim_attr_defs
-- EAV attribute registry for the audit schema.
-- ---------------------------------------------------------------------------
CREATE TABLE "04_audit"."05_dim_attr_defs" (
    id             SMALLINT    GENERATED ALWAYS AS IDENTITY,
    entity_type_id SMALLINT    NOT NULL,
    code           TEXT        NOT NULL,
    label          TEXT        NOT NULL,
    description    TEXT,
    value_column   TEXT        NOT NULL,
    deprecated_at  TIMESTAMP,
    --
    CONSTRAINT pk_audit_dim_attr_defs              PRIMARY KEY (id),
    CONSTRAINT uq_audit_dim_attr_defs_entity_code  UNIQUE (entity_type_id, code),
    CONSTRAINT fk_audit_dim_attr_defs_entity_type  FOREIGN KEY (entity_type_id)
        REFERENCES "04_audit"."04_dim_entity_types" (id),
    CONSTRAINT chk_audit_dim_attr_defs_value_column
        CHECK (value_column IN ('key_text','key_jsonb','key_smallint'))
);

COMMENT ON TABLE "04_audit"."05_dim_attr_defs" IS
  'EAV attribute registry for audit. New context fields land here by INSERT.';

-- Seed: attrs for the audit_event entity.
INSERT INTO "04_audit"."05_dim_attr_defs"
    (entity_type_id, code, label, description, value_column)
SELECT et.id, x.code, x.label, x.description, x.value_column
FROM (VALUES
    ('audit_event', 'target_id',   'Target Id',   'UUID of the resource acted on.',                 'key_text'),
    ('audit_event', 'target_type', 'Target Type', 'Entity type code of the target.',                'key_text'),
    ('audit_event', 'ip_address',  'IP Address',  'IP address of the actor request.',               'key_text'),
    ('audit_event', 'user_agent',  'User Agent',  'User-Agent header of the actor request.',        'key_text'),
    ('audit_event', 'metadata',    'Metadata',    'Freeform JSON context (never secrets/tokens).',  'key_jsonb')
) AS x(entity_code, code, label, description, value_column)
JOIN "04_audit"."04_dim_entity_types" et ON et.code = x.entity_code;

-- ---------------------------------------------------------------------------
-- 20_dtl_attrs
-- EAV values for audit events. Append-only like the rest of the schema —
-- no updated_at, no updated_by, no deleted_at. Exactly one of the three
-- key_* columns is non-NULL per row, enforced by CHECK.
-- ---------------------------------------------------------------------------
CREATE TABLE "04_audit"."20_dtl_attrs" (
    id             VARCHAR(36) NOT NULL,
    entity_type_id SMALLINT    NOT NULL,
    entity_id      VARCHAR(36) NOT NULL,
    attr_def_id    SMALLINT    NOT NULL,
    key_text       TEXT,
    key_jsonb      JSONB,
    key_smallint   SMALLINT,
    created_at     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    --
    CONSTRAINT pk_audit_dtl_attrs              PRIMARY KEY (id),
    CONSTRAINT fk_audit_dtl_attrs_entity_type  FOREIGN KEY (entity_type_id)
        REFERENCES "04_audit"."04_dim_entity_types" (id),
    CONSTRAINT fk_audit_dtl_attrs_attr_def     FOREIGN KEY (attr_def_id)
        REFERENCES "04_audit"."05_dim_attr_defs" (id),
    CONSTRAINT uq_audit_dtl_attrs_entity_attr  UNIQUE (entity_id, attr_def_id),
    CONSTRAINT chk_audit_dtl_attrs_one_value   CHECK (
        (CASE WHEN key_text     IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN key_jsonb    IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN key_smallint IS NOT NULL THEN 1 ELSE 0 END) = 1
    )
);

CREATE INDEX idx_audit_dtl_attrs_entity
    ON "04_audit"."20_dtl_attrs" (entity_type_id, entity_id);
CREATE INDEX idx_audit_dtl_attrs_attr_def
    ON "04_audit"."20_dtl_attrs" (attr_def_id);

COMMENT ON TABLE "04_audit"."20_dtl_attrs" IS
  'EAV attribute values for audit events. Append-only. Deliberately has '
  'no updated_at — audit rows never change after insert.';

-- ---------------------------------------------------------------------------
-- 60_evt_events — pure EAV + mandatory scope columns
-- ---------------------------------------------------------------------------
CREATE TABLE "04_audit"."60_evt_events" (
    id            VARCHAR(36) NOT NULL,
    org_id        VARCHAR(36),                      -- NULL only for setup/system events
    workspace_id  VARCHAR(36),                      -- NULL only for non-ws-scoped events
    user_id       VARCHAR(36),                      -- NULL only for setup events
    session_id    VARCHAR(36),                      -- NULL only for setup or failed-auth events
    category_id   SMALLINT    NOT NULL,
    action_id     SMALLINT    NOT NULL,
    outcome_id    SMALLINT    NOT NULL,
    created_by    VARCHAR(36),                      -- row-author convention; normally equal to user_id
    created_at    TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    --
    CONSTRAINT pk_audit_events           PRIMARY KEY (id),
    CONSTRAINT fk_audit_events_category  FOREIGN KEY (category_id)
        REFERENCES "04_audit"."01_dim_event_categories" (id),
    CONSTRAINT fk_audit_events_action    FOREIGN KEY (action_id)
        REFERENCES "04_audit"."03_dim_event_actions"    (id),
    CONSTRAINT fk_audit_events_outcome   FOREIGN KEY (outcome_id)
        REFERENCES "04_audit"."02_dim_event_outcomes"   (id)
    -- chk_audit_events_user_session_scope is added below via DO block
    -- because CHECK constraints cannot reference subqueries.
);

COMMENT ON TABLE "04_audit"."60_evt_events" IS
  'Append-only audit log. Pure-EAV: only tenant/principal scope columns '
  '(org_id, workspace_id, user_id, session_id) live on the row as mandatory '
  'scope per .claude/rules/common/database.md and the rule that user_id and '
  'session_id are mandatory. All other context lives in 20_dtl_attrs.';

COMMENT ON COLUMN "04_audit"."60_evt_events".org_id IS
  'Org scope of the event. NULL only for setup/system events. Not FK-enforced — '
  'audit rows must survive org archival.';
COMMENT ON COLUMN "04_audit"."60_evt_events".workspace_id IS
  'Workspace scope of the event. NULL for non-workspace-scoped events.';
COMMENT ON COLUMN "04_audit"."60_evt_events".user_id IS
  'Authenticated principal behind the action. NULL only for setup events. '
  'Not FK-enforced — audit rows must survive user soft-delete.';
COMMENT ON COLUMN "04_audit"."60_evt_events".session_id IS
  'Session the action was performed under. NULL only for setup events or '
  'failed auth attempts (login_failed). Not FK-enforced.';
COMMENT ON COLUMN "04_audit"."60_evt_events".created_by IS
  'Row-author convention — normally equal to user_id. Separate from user_id '
  'because future event types (system-initiated cron, etc.) may have '
  'user_id=NULL but a meaningful actor.';

CREATE INDEX idx_audit_events_org_id       ON "04_audit"."60_evt_events" (org_id)       WHERE org_id IS NOT NULL;
CREATE INDEX idx_audit_events_workspace_id ON "04_audit"."60_evt_events" (workspace_id) WHERE workspace_id IS NOT NULL;
CREATE INDEX idx_audit_events_user_id      ON "04_audit"."60_evt_events" (user_id)      WHERE user_id IS NOT NULL;
CREATE INDEX idx_audit_events_session_id   ON "04_audit"."60_evt_events" (session_id)   WHERE session_id IS NOT NULL;
CREATE INDEX idx_audit_events_created_by   ON "04_audit"."60_evt_events" (created_by)   WHERE created_by IS NOT NULL;
CREATE INDEX idx_audit_events_created_at   ON "04_audit"."60_evt_events" (created_at DESC);
CREATE INDEX idx_audit_events_action       ON "04_audit"."60_evt_events" (action_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- chk_audit_events_user_session_scope
-- Encoded at migration time so the CHECK uses literal SMALLINTs.
--
-- Logic:
--   setup events                   → user_id and session_id may be NULL
--   everything else                → user_id must be non-NULL
--     - if outcome = 'failure'     → session_id may be NULL (login_failed)
--     - otherwise                  → session_id must be non-NULL
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    setup_cat_id   SMALLINT;
    failure_out_id SMALLINT;
BEGIN
    SELECT id INTO setup_cat_id
      FROM "04_audit"."01_dim_event_categories" WHERE code = 'setup';
    SELECT id INTO failure_out_id
      FROM "04_audit"."02_dim_event_outcomes"   WHERE code = 'failure';

    EXECUTE format(
        'ALTER TABLE "04_audit"."60_evt_events" '
        'ADD CONSTRAINT chk_audit_events_user_session_scope CHECK ('
        '  category_id = %s '
        '  OR ('
        '    user_id IS NOT NULL '
        '    AND (session_id IS NOT NULL OR outcome_id = %s)'
        '  )'
        ')',
        setup_cat_id, failure_out_id
    );
END $$;

-- ---------------------------------------------------------------------------
-- v_events — read view pivots EAV back to a wide shape for callers.
-- Shape preserved for backwards compatibility with existing query code.
-- ---------------------------------------------------------------------------
CREATE VIEW "04_audit"."v_events" AS
-- Pivot EAV attrs back to a wide shape.
-- Text attrs use MAX(CASE ...) which works natively.
-- JSONB has no aggregate, so metadata uses a correlated scalar subquery.
SELECT
    e.id,
    e.org_id,
    e.workspace_id,
    e.user_id,
    e.session_id,
    c.code  AS category,
    a.code  AS action,
    o.code  AS outcome,
    e.created_by                     AS actor_id,   -- legacy alias for existing consumers
    MAX(CASE WHEN ad.code = 'target_id'   THEN d.key_text END) AS target_id,
    MAX(CASE WHEN ad.code = 'target_type' THEN d.key_text END) AS target_type,
    MAX(CASE WHEN ad.code = 'ip_address'  THEN d.key_text END) AS ip_address,
    MAX(CASE WHEN ad.code = 'user_agent'  THEN d.key_text END) AS user_agent,
    (
        SELECT d2.key_jsonb
          FROM "04_audit"."20_dtl_attrs"  d2
          JOIN "04_audit"."05_dim_attr_defs" ad2 ON ad2.id = d2.attr_def_id
          JOIN "04_audit"."04_dim_entity_types" et2 ON et2.id = d2.entity_type_id
         WHERE d2.entity_id = e.id
           AND et2.code = 'audit_event'
           AND ad2.code = 'metadata'
         LIMIT 1
    ) AS metadata,
    e.created_at
FROM "04_audit"."60_evt_events" e
JOIN "04_audit"."01_dim_event_categories" c ON c.id = e.category_id
JOIN "04_audit"."03_dim_event_actions"    a ON a.id = e.action_id
JOIN "04_audit"."02_dim_event_outcomes"   o ON o.id = e.outcome_id
LEFT JOIN "04_audit"."20_dtl_attrs" d
       ON d.entity_id      = e.id
      AND d.entity_type_id = (SELECT id FROM "04_audit"."04_dim_entity_types" WHERE code = 'audit_event')
LEFT JOIN "04_audit"."05_dim_attr_defs" ad ON ad.id = d.attr_def_id
GROUP BY e.id, e.org_id, e.workspace_id, e.user_id, e.session_id,
         c.code, a.code, o.code, e.created_by, e.created_at;

COMMENT ON VIEW "04_audit"."v_events" IS
  'Read view over audit events. Pivots EAV context attrs and exposes the '
  'mandatory scope columns. Safe for API responses.';

-- ---------------------------------------------------------------------------
-- Grants
-- Write role can INSERT into events + attrs (append-only).
-- No UPDATE or DELETE grants anywhere in this schema.
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA "04_audit" TO tennetctl_write;
GRANT USAGE ON SCHEMA "04_audit" TO tennetctl_read;

GRANT INSERT, SELECT ON "04_audit"."60_evt_events" TO tennetctl_write;
GRANT INSERT, SELECT ON "04_audit"."20_dtl_attrs"  TO tennetctl_write;
GRANT SELECT         ON "04_audit"."60_evt_events" TO tennetctl_read;
GRANT SELECT         ON "04_audit"."20_dtl_attrs"  TO tennetctl_read;

GRANT SELECT ON "04_audit"."01_dim_event_categories" TO tennetctl_read;
GRANT SELECT ON "04_audit"."01_dim_event_categories" TO tennetctl_write;
GRANT SELECT ON "04_audit"."02_dim_event_outcomes"   TO tennetctl_read;
GRANT SELECT ON "04_audit"."02_dim_event_outcomes"   TO tennetctl_write;
GRANT SELECT ON "04_audit"."03_dim_event_actions"    TO tennetctl_read;
GRANT SELECT ON "04_audit"."03_dim_event_actions"    TO tennetctl_write;
GRANT SELECT ON "04_audit"."04_dim_entity_types"     TO tennetctl_read;
GRANT SELECT ON "04_audit"."04_dim_entity_types"     TO tennetctl_write;
GRANT SELECT ON "04_audit"."05_dim_attr_defs"        TO tennetctl_read;
GRANT SELECT ON "04_audit"."05_dim_attr_defs"        TO tennetctl_write;

GRANT SELECT ON "04_audit"."v_events" TO tennetctl_read;
GRANT SELECT ON "04_audit"."v_events" TO tennetctl_write;

-- DOWN ====

DROP VIEW  IF EXISTS "04_audit"."v_events";
DROP TABLE IF EXISTS "04_audit"."60_evt_events";
DROP TABLE IF EXISTS "04_audit"."20_dtl_attrs";
DROP TABLE IF EXISTS "04_audit"."05_dim_attr_defs";
DROP TABLE IF EXISTS "04_audit"."04_dim_entity_types";
DROP TABLE IF EXISTS "04_audit"."03_dim_event_actions";
DROP TABLE IF EXISTS "04_audit"."02_dim_event_outcomes";
DROP TABLE IF EXISTS "04_audit"."01_dim_event_categories";
DROP SCHEMA IF EXISTS "04_audit";
