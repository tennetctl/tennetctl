-- =============================================================================
-- Migration: 20260402_001_iam_org_bootstrap.sql
-- Module:    02_iam
-- Description: Bootstrap org tables with lifecycle states and EAV attributes
-- =============================================================================

-- UP ==========================================================================

CREATE SCHEMA IF NOT EXISTS "02_iam";

-- Lookup: org statuses
CREATE TABLE "02_iam".dim_org_statuses (
    id              SMALLINT     NOT NULL,
    code            VARCHAR(64)  NOT NULL,
    label           VARCHAR(128) NOT NULL,
    description     TEXT,
    deprecated_at   TIMESTAMP,

    CONSTRAINT pk_dim_org_statuses PRIMARY KEY (id),
    CONSTRAINT uq_dim_org_statuses_code UNIQUE (code)
);
COMMENT ON TABLE  "02_iam".dim_org_statuses IS 'Coded org states. Controls overall org access and visibility.';
COMMENT ON COLUMN "02_iam".dim_org_statuses.id   IS 'Stable SMALLINT PK. Never renumber.';
COMMENT ON COLUMN "02_iam".dim_org_statuses.code IS 'Snake_case machine key used in app logic.';
COMMENT ON COLUMN "02_iam".dim_org_statuses.label IS 'Human-readable label for UI display.';
COMMENT ON COLUMN "02_iam".dim_org_statuses.deprecated_at IS 'Set when value is retired. Never DELETE rows.';

INSERT INTO "02_iam".dim_org_statuses (id, code, label, description) VALUES
    (1, 'active',    'Active',    'Org is fully operational'),
    (2, 'suspended', 'Suspended', 'Temporarily blocked — can be reinstated'),
    (3, 'archived',  'Archived',  'Permanently closed');

-- Lookup: Entity Types
CREATE TABLE "02_iam".dim_entity_types (
    id              SMALLINT     NOT NULL,
    code            VARCHAR(64)  NOT NULL,
    label           VARCHAR(128) NOT NULL,
    description     TEXT,
    deprecated_at   TIMESTAMP,

    CONSTRAINT pk_dim_entity_types PRIMARY KEY (id),
    CONSTRAINT uq_dim_entity_types_code UNIQUE (code)
);
COMMENT ON TABLE "02_iam".dim_entity_types IS 'Entity type codes for EAV layer.';
COMMENT ON COLUMN "02_iam".dim_entity_types.id IS 'Stable SMALLINT PK. Never renumber.';

INSERT INTO "02_iam".dim_entity_types (id, code, label, description) VALUES
    (1, 'user', 'User', 'Platform users'),
    (2, 'org', 'Organisation', 'Customer orgs');


-- Lookup: Attribute Definitions
CREATE TABLE "02_iam".dim_attr_defs (
    id              SMALLINT     NOT NULL,
    entity_type_id  SMALLINT     NOT NULL,
    code            VARCHAR(64)  NOT NULL,
    label           VARCHAR(128) NOT NULL,
    value_type      VARCHAR(16)  NOT NULL,
    is_pii          BOOLEAN      NOT NULL DEFAULT false,
    is_encrypted    BOOLEAN      NOT NULL DEFAULT false,
    is_required     BOOLEAN      NOT NULL DEFAULT false,
    is_unique       BOOLEAN      NOT NULL DEFAULT false,
    description     TEXT,
    deprecated_at   TIMESTAMP,

    CONSTRAINT pk_dim_attr_defs PRIMARY KEY (id),
    CONSTRAINT uq_dim_attr_defs_type_code UNIQUE (entity_type_id, code),
    CONSTRAINT chk_dim_attr_defs_value_type CHECK (value_type IN ('text', 'jsonb', 'smallint'))
);
COMMENT ON TABLE "02_iam".dim_attr_defs IS 'Attribute catalog for the EAV layer.';

INSERT INTO "02_iam".dim_attr_defs (id, entity_type_id, code, label, value_type, is_pii, description) VALUES
    (10, 2, 'slug',         'Org Slug',       'text',     false, 'Unique URL-friendly slug'),
    (11, 2, 'display_name', 'Org Name',       'text',     false, 'Human readable org name'),
    (12, 2, 'settings',     'Org Settings',   'jsonb',    false, 'Config objects');


-- Entity: orgs
CREATE TABLE "02_iam"."11_fct_orgs" (
    id              VARCHAR(36)  NOT NULL,
    org_status_id   SMALLINT     NOT NULL DEFAULT 1,
    is_active       BOOLEAN      NOT NULL DEFAULT true,
    is_test         BOOLEAN      NOT NULL DEFAULT false,
    deleted_at      TIMESTAMP,
    created_by      VARCHAR(36),
    updated_by      VARCHAR(36),
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_11_fct_orgs               PRIMARY KEY (id),
    CONSTRAINT fk_11_fct_orgs_status        FOREIGN KEY (org_status_id)
        REFERENCES "02_iam".dim_org_statuses(id)
);
COMMENT ON TABLE  "02_iam"."11_fct_orgs" IS 'Multi-tenant orgs identity table.';
COMMENT ON COLUMN "02_iam"."11_fct_orgs".id             IS 'UUID v7 — time-ordered, app-generated.';
COMMENT ON COLUMN "02_iam"."11_fct_orgs".org_status_id  IS 'References dim_org_statuses. Controls access.';
COMMENT ON COLUMN "02_iam"."11_fct_orgs".is_active      IS 'Quick disable flag.';
COMMENT ON COLUMN "02_iam"."11_fct_orgs".is_test        IS 'Seed/test data marker.';
COMMENT ON COLUMN "02_iam"."11_fct_orgs".deleted_at     IS 'NULL = live. SET = soft-deleted.';
COMMENT ON COLUMN "02_iam"."11_fct_orgs".created_by     IS 'Actor who created this row.';
COMMENT ON COLUMN "02_iam"."11_fct_orgs".updated_by     IS 'Actor who updated this row.';
COMMENT ON COLUMN "02_iam"."11_fct_orgs".created_at     IS 'Row creation timestamp (UTC).';
COMMENT ON COLUMN "02_iam"."11_fct_orgs".updated_at     IS 'Last update timestamp (UTC). Managed by trigger.';

CREATE OR REPLACE FUNCTION "02_iam".set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = CURRENT_TIMESTAMP; RETURN NEW; END;
$$;
COMMENT ON FUNCTION "02_iam".set_updated_at() IS 'Trigger: auto-update updated_at on fct_* mutation.';

CREATE TRIGGER trg_11_fct_orgs_updated_at
    BEFORE UPDATE ON "02_iam"."11_fct_orgs"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

CREATE INDEX idx_11_fct_orgs_live
    ON "02_iam"."11_fct_orgs" (created_at DESC)
    WHERE deleted_at IS NULL;
COMMENT ON INDEX "02_iam".idx_11_fct_orgs_live IS 'Partial index for fast live-org list queries.';


-- Entity Details: dtl_attrs
CREATE TABLE "02_iam"."20_dtl_attrs" (
    entity_type_id  SMALLINT     NOT NULL,
    entity_id       VARCHAR(36)  NOT NULL,
    attr_def_id     SMALLINT     NOT NULL,
    key_text        TEXT,
    key_jsonb       JSONB,
    key_smallint    SMALLINT,
    created_by      VARCHAR(36),
    updated_by      VARCHAR(36),
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_20_dtl_attrs PRIMARY KEY (entity_type_id, entity_id, attr_def_id),
    CONSTRAINT fk_20_dtl_attrs_entity_type FOREIGN KEY (entity_type_id)
        REFERENCES "02_iam".dim_entity_types(id),
    CONSTRAINT fk_20_dtl_attrs_attr_def FOREIGN KEY (attr_def_id)
        REFERENCES "02_iam".dim_attr_defs(id),
    CONSTRAINT chk_20_dtl_attrs_value CHECK (
        (key_text IS NOT NULL)::int +
        (key_jsonb IS NOT NULL)::int +
        (key_smallint IS NOT NULL)::int = 1
    )
);
COMMENT ON TABLE  "02_iam"."20_dtl_attrs" IS 'Generic EAV attribute store for all IAM entities.';
COMMENT ON COLUMN "02_iam"."20_dtl_attrs".entity_type_id IS 'Discriminator: which entity type owns this row.';
COMMENT ON COLUMN "02_iam"."20_dtl_attrs".entity_id      IS 'UUID of the parent fct_* row.';
COMMENT ON COLUMN "02_iam"."20_dtl_attrs".attr_def_id    IS 'Which attribute this row stores. Defined in dim_attr_defs.';
COMMENT ON COLUMN "02_iam"."20_dtl_attrs".key_text       IS 'Text value. Used for strings, slugs, display names, PII.';
COMMENT ON COLUMN "02_iam"."20_dtl_attrs".key_jsonb      IS 'JSONB value. Used for settings objects, arrays, structured data.';
COMMENT ON COLUMN "02_iam"."20_dtl_attrs".key_smallint   IS 'SMALLINT value. FK to a dim_* table (coded lookup).';

-- Evt table (Audit logs for mutations)
CREATE TABLE "02_iam"."60_evt_audit_log" (
    id              VARCHAR(36)  NOT NULL,
    org_id          VARCHAR(36),
    actor_id        VARCHAR(36),
    actor_type_id   SMALLINT,
    action_id       SMALLINT     NOT NULL,
    entity_type_id  SMALLINT     NOT NULL,
    entity_id       VARCHAR(36)  NOT NULL,
    outcome_id      SMALLINT     NOT NULL,
    ip_address      VARCHAR(64),
    metadata        JSONB        NOT NULL DEFAULT '{}',
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_60_evt_audit_log PRIMARY KEY (id)
);
COMMENT ON TABLE "02_iam"."60_evt_audit_log" IS 'Append-only. Never UPDATE or DELETE rows.';

-- View for frontend
CREATE OR REPLACE VIEW "02_iam".v_orgs AS
SELECT
    o.id,
    o.is_active,
    o.is_test,
    s.code   AS status,
    o.deleted_at,
    o.created_by,
    o.updated_by,
    o.created_at,
    o.updated_at,
    MAX(CASE WHEN a.attr_def_id = 10 THEN a.key_text END) AS slug,
    MAX(CASE WHEN a.attr_def_id = 11 THEN a.key_text END) AS display_name,
    COALESCE(MAX(CASE WHEN a.attr_def_id = 12 THEN a.key_jsonb::text END)::jsonb, '{}'::jsonb) AS settings
FROM "02_iam"."11_fct_orgs" o
JOIN "02_iam".dim_org_statuses s ON s.id = o.org_status_id
LEFT JOIN "02_iam"."20_dtl_attrs" a ON a.entity_id = o.id AND a.entity_type_id = 2
GROUP BY o.id, s.code;

COMMENT ON VIEW "02_iam".v_orgs IS 'Read-only view of orgs with resolved status code and EAV properties. Use for all GET queries.';

-- DOWN ========================================================================

DROP VIEW  IF EXISTS "02_iam".v_orgs;
DROP TABLE IF EXISTS "02_iam"."60_evt_audit_log";
DROP TABLE IF EXISTS "02_iam"."20_dtl_attrs";
DROP TABLE IF EXISTS "02_iam"."11_fct_orgs";
DROP TABLE IF EXISTS "02_iam".dim_attr_defs;
DROP TABLE IF EXISTS "02_iam".dim_entity_types;
DROP TABLE IF EXISTS "02_iam".dim_org_statuses;
DROP SCHEMA IF EXISTS "02_iam" CASCADE;
