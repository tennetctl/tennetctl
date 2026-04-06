-- =============================================================================
-- Migration: 20260403_005_audit_bootstrap.sql
-- Module:    90_audit (global audit infrastructure)
-- Description: Hybrid audit system — shared dims in "90_audit" schema,
--   per-feature audit tables in each feature schema, global UNION ALL view.
--   First feature: IAM (02_iam) gets 90_fct_iam_audit_events + 91_dtl_iam_audit_attrs.
--   Old 01_evt_org_audit_log is migrated and dropped.
-- =============================================================================

-- UP ==========================================================================

-- ----------------------------------------------------------------------------
-- 1. Create audit schema
-- ----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS "90_audit";

-- ----------------------------------------------------------------------------
-- 2. Shared dimension: audit actions (what was done)
-- ----------------------------------------------------------------------------
CREATE TABLE "90_audit"."01_dim_audit_actions" (
    id              SMALLINT    NOT NULL,
    code            TEXT        NOT NULL,
    label           TEXT        NOT NULL,
    description     TEXT        NOT NULL DEFAULT '',
    deprecated_at   TIMESTAMP,

    CONSTRAINT pk_dim_audit_actions      PRIMARY KEY (id),
    CONSTRAINT uq_dim_audit_actions_code UNIQUE (code)
);

COMMENT ON TABLE  "90_audit"."01_dim_audit_actions"                IS 'Enumeration of audit action types. Shared across all feature audit tables.';
COMMENT ON COLUMN "90_audit"."01_dim_audit_actions".id             IS 'Stable numeric PK. Never reuse a retired ID.';
COMMENT ON COLUMN "90_audit"."01_dim_audit_actions".code           IS 'Machine-readable action code (e.g. create, update, delete). Immutable after first release.';
COMMENT ON COLUMN "90_audit"."01_dim_audit_actions".label          IS 'Human-readable label for UI display.';
COMMENT ON COLUMN "90_audit"."01_dim_audit_actions".description    IS 'What this action means operationally.';
COMMENT ON COLUMN "90_audit"."01_dim_audit_actions".deprecated_at  IS 'NULL = active. SET = retired action code.';

INSERT INTO "90_audit"."01_dim_audit_actions" (id, code, label, description) VALUES
    (1,  'create',  'Create',  'Entity was created'),
    (2,  'update',  'Update',  'Entity was updated'),
    (3,  'delete',  'Delete',  'Entity was soft-deleted'),
    (4,  'read',    'Read',    'Entity was read/accessed'),
    (5,  'login',   'Login',   'Authentication login event'),
    (6,  'logout',  'Logout',  'Authentication logout event'),
    (7,  'access',  'Access',  'Sensitive resource was accessed (e.g. secret reveal)'),
    (8,  'export',  'Export',  'Data was exported'),
    (9,  'enable',  'Enable',  'Entity was enabled/activated'),
    (10, 'disable', 'Disable', 'Entity was disabled/deactivated'),
    (11, 'rotate',  'Rotate',  'Credential or key was rotated'),
    (12, 'restore', 'Restore', 'Entity was restored from soft-delete');

-- ----------------------------------------------------------------------------
-- 3. Shared dimension: audit outcomes (what happened)
-- ----------------------------------------------------------------------------
CREATE TABLE "90_audit"."02_dim_audit_outcomes" (
    id              SMALLINT    NOT NULL,
    code            TEXT        NOT NULL,
    label           TEXT        NOT NULL,
    description     TEXT        NOT NULL DEFAULT '',
    deprecated_at   TIMESTAMP,

    CONSTRAINT pk_dim_audit_outcomes      PRIMARY KEY (id),
    CONSTRAINT uq_dim_audit_outcomes_code UNIQUE (code)
);

COMMENT ON TABLE  "90_audit"."02_dim_audit_outcomes"                IS 'Enumeration of audit event outcomes. Shared across all feature audit tables.';
COMMENT ON COLUMN "90_audit"."02_dim_audit_outcomes".id             IS 'Stable numeric PK.';
COMMENT ON COLUMN "90_audit"."02_dim_audit_outcomes".code           IS 'Machine-readable outcome code.';
COMMENT ON COLUMN "90_audit"."02_dim_audit_outcomes".label          IS 'Human-readable label.';
COMMENT ON COLUMN "90_audit"."02_dim_audit_outcomes".description    IS 'What this outcome means.';
COMMENT ON COLUMN "90_audit"."02_dim_audit_outcomes".deprecated_at  IS 'NULL = active. SET = retired.';

INSERT INTO "90_audit"."02_dim_audit_outcomes" (id, code, label, description) VALUES
    (1, 'success', 'Success', 'Operation completed successfully'),
    (2, 'failure', 'Failure', 'Operation failed'),
    (3, 'denied',  'Denied',  'Operation was denied by access control'),
    (4, 'partial', 'Partial', 'Operation partially succeeded'),
    (5, 'error',   'Error',   'Operation failed due to system error');

-- ----------------------------------------------------------------------------
-- 4. Shared dimension: audit actor types (who did it)
-- ----------------------------------------------------------------------------
CREATE TABLE "90_audit"."03_dim_audit_actor_types" (
    id              SMALLINT    NOT NULL,
    code            TEXT        NOT NULL,
    label           TEXT        NOT NULL,
    description     TEXT        NOT NULL DEFAULT '',
    deprecated_at   TIMESTAMP,

    CONSTRAINT pk_dim_audit_actor_types      PRIMARY KEY (id),
    CONSTRAINT uq_dim_audit_actor_types_code UNIQUE (code)
);

COMMENT ON TABLE  "90_audit"."03_dim_audit_actor_types"                IS 'Enumeration of actor types that can trigger audit events.';
COMMENT ON COLUMN "90_audit"."03_dim_audit_actor_types".id             IS 'Stable numeric PK.';
COMMENT ON COLUMN "90_audit"."03_dim_audit_actor_types".code           IS 'Machine-readable actor type code.';
COMMENT ON COLUMN "90_audit"."03_dim_audit_actor_types".label          IS 'Human-readable label.';
COMMENT ON COLUMN "90_audit"."03_dim_audit_actor_types".description    IS 'What this actor type represents.';
COMMENT ON COLUMN "90_audit"."03_dim_audit_actor_types".deprecated_at  IS 'NULL = active. SET = retired.';

INSERT INTO "90_audit"."03_dim_audit_actor_types" (id, code, label, description) VALUES
    (1, 'user',            'User',            'Human user via UI or API'),
    (2, 'service_account', 'Service Account', 'Machine-to-machine service account'),
    (3, 'api_key',         'API Key',         'Programmatic API key'),
    (4, 'system',          'System',          'Internal system process');

-- ----------------------------------------------------------------------------
-- 5. Per-feature audit table: IAM
--    All IAM sub-features (org, user, workspace, group, etc.) write here.
--    Append-only: NO updated_at, NO deleted_at.
-- ----------------------------------------------------------------------------
CREATE TABLE "02_iam"."90_fct_iam_audit_events" (
    id              VARCHAR(36) NOT NULL,
    org_id          VARCHAR(36),
    actor_id        VARCHAR(36),
    actor_type_id   SMALLINT    NOT NULL DEFAULT 4,
    action_id       SMALLINT    NOT NULL,
    entity_type_id  SMALLINT    NOT NULL,
    entity_id       VARCHAR(36) NOT NULL,
    outcome_id      SMALLINT    NOT NULL DEFAULT 1,
    ip_address      VARCHAR(64),
    metadata        JSONB       NOT NULL DEFAULT '{}',
    created_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_90_fct_iam_audit_events              PRIMARY KEY (id),
    CONSTRAINT fk_90_fct_iam_audit_events_action       FOREIGN KEY (action_id)
        REFERENCES "90_audit"."01_dim_audit_actions"(id),
    CONSTRAINT fk_90_fct_iam_audit_events_outcome      FOREIGN KEY (outcome_id)
        REFERENCES "90_audit"."02_dim_audit_outcomes"(id),
    CONSTRAINT fk_90_fct_iam_audit_events_actor_type   FOREIGN KEY (actor_type_id)
        REFERENCES "90_audit"."03_dim_audit_actor_types"(id),
    CONSTRAINT fk_90_fct_iam_audit_events_entity_type  FOREIGN KEY (entity_type_id)
        REFERENCES "02_iam"."01_dim_org_entity_types"(id)
);

COMMENT ON TABLE  "02_iam"."90_fct_iam_audit_events"                IS 'Append-only audit event log for all IAM sub-features. Events are immutable — never updated or deleted.';
COMMENT ON COLUMN "02_iam"."90_fct_iam_audit_events".id             IS 'UUID v7 stored as VARCHAR(36). Time-ordered.';
COMMENT ON COLUMN "02_iam"."90_fct_iam_audit_events".org_id         IS 'Tenant org UUID. NULL for platform-level events.';
COMMENT ON COLUMN "02_iam"."90_fct_iam_audit_events".actor_id       IS 'UUID of the acting principal. NULL for system-initiated events.';
COMMENT ON COLUMN "02_iam"."90_fct_iam_audit_events".actor_type_id  IS 'FK → 90_audit.03_dim_audit_actor_types. Default 4 = system.';
COMMENT ON COLUMN "02_iam"."90_fct_iam_audit_events".action_id      IS 'FK → 90_audit.01_dim_audit_actions. What was done.';
COMMENT ON COLUMN "02_iam"."90_fct_iam_audit_events".entity_type_id IS 'FK → 02_iam.01_dim_org_entity_types. What type of entity was affected.';
COMMENT ON COLUMN "02_iam"."90_fct_iam_audit_events".entity_id      IS 'UUID of the affected entity.';
COMMENT ON COLUMN "02_iam"."90_fct_iam_audit_events".outcome_id     IS 'FK → 90_audit.02_dim_audit_outcomes. Default 1 = success.';
COMMENT ON COLUMN "02_iam"."90_fct_iam_audit_events".ip_address     IS 'Client IP address. NULL for system events.';
COMMENT ON COLUMN "02_iam"."90_fct_iam_audit_events".metadata       IS 'Free-form JSONB context (slug, attr_key, etc.).';
COMMENT ON COLUMN "02_iam"."90_fct_iam_audit_events".created_at     IS 'Event timestamp. Immutable. Set by DEFAULT CURRENT_TIMESTAMP.';

CREATE INDEX idx_90_fct_iam_audit_org_time
    ON "02_iam"."90_fct_iam_audit_events" (org_id, created_at DESC);

CREATE INDEX idx_90_fct_iam_audit_entity
    ON "02_iam"."90_fct_iam_audit_events" (entity_type_id, entity_id, created_at DESC);

CREATE INDEX idx_90_fct_iam_audit_actor
    ON "02_iam"."90_fct_iam_audit_events" (actor_id, created_at DESC);

CREATE INDEX idx_90_fct_iam_audit_action_time
    ON "02_iam"."90_fct_iam_audit_events" (action_id, created_at DESC);

-- ----------------------------------------------------------------------------
-- 6. Per-feature audit attrs: IAM
--    Structured per-event attributes (before/after values, field names).
-- ----------------------------------------------------------------------------
CREATE TABLE "02_iam"."91_dtl_iam_audit_attrs" (
    id          VARCHAR(36)     NOT NULL,
    event_id    VARCHAR(36)     NOT NULL,
    attr_key    VARCHAR(100)    NOT NULL,
    key_text    TEXT,
    key_jsonb   JSONB,

    CONSTRAINT pk_91_dtl_iam_audit_attrs        PRIMARY KEY (id),
    CONSTRAINT fk_91_dtl_iam_audit_attrs_event  FOREIGN KEY (event_id)
        REFERENCES "02_iam"."90_fct_iam_audit_events"(id),
    CONSTRAINT uq_91_dtl_iam_audit_attrs_key    UNIQUE (event_id, attr_key)
);

COMMENT ON TABLE  "02_iam"."91_dtl_iam_audit_attrs"            IS 'EAV attributes for IAM audit events. One row per (event, key) pair. Text values in key_text, structured values in key_jsonb.';
COMMENT ON COLUMN "02_iam"."91_dtl_iam_audit_attrs".id         IS 'UUID v7 PK.';
COMMENT ON COLUMN "02_iam"."91_dtl_iam_audit_attrs".event_id   IS 'FK → 90_fct_iam_audit_events. Parent audit event.';
COMMENT ON COLUMN "02_iam"."91_dtl_iam_audit_attrs".attr_key   IS 'Attribute key (e.g. previous_status, new_value, field_name).';
COMMENT ON COLUMN "02_iam"."91_dtl_iam_audit_attrs".key_text   IS 'Plain-text value. NULL when key_jsonb is set.';
COMMENT ON COLUMN "02_iam"."91_dtl_iam_audit_attrs".key_jsonb  IS 'Structured JSONB value. NULL when key_text is set.';

CREATE INDEX idx_91_dtl_iam_audit_attrs_event
    ON "02_iam"."91_dtl_iam_audit_attrs" (event_id);

-- ----------------------------------------------------------------------------
-- 7. Global read view: UNION ALL across all feature audit tables
--    Currently only IAM. Each new feature adds a UNION ALL block.
-- ----------------------------------------------------------------------------
CREATE VIEW "90_audit".v_audit_events AS
SELECT
    e.id,
    e.org_id,
    e.actor_id,
    at.code                 AS actor_type,
    a.code                  AS action,
    a.label                 AS action_label,
    et.code                 AS entity_type,
    e.entity_id,
    o.code                  AS outcome,
    o.label                 AS outcome_label,
    e.ip_address,
    e.metadata,
    e.created_at,
    '02_iam'::TEXT          AS source_schema
FROM "02_iam"."90_fct_iam_audit_events" e
JOIN "90_audit"."01_dim_audit_actions"      a  ON a.id  = e.action_id
JOIN "90_audit"."02_dim_audit_outcomes"     o  ON o.id  = e.outcome_id
JOIN "90_audit"."03_dim_audit_actor_types"  at ON at.id = e.actor_type_id
JOIN "02_iam"."01_dim_org_entity_types"     et ON et.id = e.entity_type_id
-- UNION ALL for future features:
-- UNION ALL SELECT ... FROM "07_vault"."90_fct_vault_audit_events" ...
;

COMMENT ON VIEW "90_audit".v_audit_events
    IS 'Global read-only audit view. UNION ALL across all per-feature audit tables. Joins shared dims for human-readable codes.';

-- ----------------------------------------------------------------------------
-- 8. Migrate existing data from old org audit table
-- ----------------------------------------------------------------------------
INSERT INTO "02_iam"."90_fct_iam_audit_events"
    (id, org_id, actor_id, actor_type_id, action_id, entity_type_id, entity_id, outcome_id, ip_address, metadata, created_at)
SELECT
    id, org_id, actor_id,
    COALESCE(actor_type_id, 4),
    action_id,
    entity_type_id, entity_id,
    outcome_id,
    ip_address,
    metadata,
    created_at
FROM "02_iam"."01_evt_org_audit_log";

-- ----------------------------------------------------------------------------
-- 9. Drop old table
-- ----------------------------------------------------------------------------
DROP TABLE "02_iam"."01_evt_org_audit_log";

-- DOWN ========================================================================

-- Recreate old table
CREATE TABLE "02_iam"."01_evt_org_audit_log" (
    id              VARCHAR(36) NOT NULL,
    org_id          VARCHAR(36),
    actor_id        VARCHAR(36),
    actor_type_id   SMALLINT,
    action_id       SMALLINT    NOT NULL,
    entity_type_id  SMALLINT    NOT NULL DEFAULT 2,
    entity_id       VARCHAR(36) NOT NULL,
    outcome_id      SMALLINT    NOT NULL DEFAULT 1,
    ip_address      VARCHAR(64),
    metadata        JSONB       NOT NULL DEFAULT '{}',
    created_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_01_evt_org_audit_log PRIMARY KEY (id)
);

-- Move data back
INSERT INTO "02_iam"."01_evt_org_audit_log"
    (id, org_id, actor_id, actor_type_id, action_id, entity_type_id, entity_id, outcome_id, ip_address, metadata, created_at)
SELECT id, org_id, actor_id, actor_type_id, action_id, entity_type_id, entity_id, outcome_id, ip_address, metadata, created_at
FROM "02_iam"."90_fct_iam_audit_events";

-- Drop new objects
DROP VIEW  IF EXISTS "90_audit".v_audit_events;
DROP TABLE IF EXISTS "02_iam"."91_dtl_iam_audit_attrs";
DROP TABLE IF EXISTS "02_iam"."90_fct_iam_audit_events";
DROP TABLE IF EXISTS "90_audit"."03_dim_audit_actor_types";
DROP TABLE IF EXISTS "90_audit"."02_dim_audit_outcomes";
DROP TABLE IF EXISTS "90_audit"."01_dim_audit_actions";
DROP SCHEMA IF EXISTS "90_audit";
