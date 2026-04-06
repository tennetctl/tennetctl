-- =============================================================================
-- Migration: 20260403_006a_iam_users.sql
-- Sub-feature: 02_user
-- Description: User identity — dims, fct, dtl (EAV), and read view.
-- UP
-- =============================================================================

SET search_path TO "02_iam", public;

-- Entity types
INSERT INTO "02_iam"."01_dim_org_entity_types" (id, code, label, description) VALUES
    (5, 'credential', 'Credential', 'Auth credential');

-- User statuses
CREATE TABLE "02_iam"."02_dim_user_statuses" (
    id              SMALLINT    NOT NULL,
    code            TEXT        NOT NULL,
    label           TEXT        NOT NULL,
    description     TEXT        NOT NULL DEFAULT '',
    deprecated_at   TIMESTAMP,
    CONSTRAINT pk_02_dim_user_statuses      PRIMARY KEY (id),
    CONSTRAINT uq_02_dim_user_statuses_code UNIQUE (code)
);
COMMENT ON TABLE "02_iam"."02_dim_user_statuses" IS 'User lifecycle statuses.';

INSERT INTO "02_iam"."02_dim_user_statuses" (id, code, label, description) VALUES
    (1, 'active',               'Active',               'Fully operational'),
    (2, 'inactive',             'Inactive',             'Voluntarily deactivated'),
    (3, 'suspended',            'Suspended',            'Admin-suspended'),
    (4, 'pending_verification', 'Pending Verification', 'Email not yet verified'),
    (5, 'deleted',              'Deleted',              'Soft-deleted');

-- Account types
CREATE TABLE "02_iam"."03_dim_account_types" (
    id              SMALLINT    NOT NULL,
    code            TEXT        NOT NULL,
    label           TEXT        NOT NULL,
    description     TEXT        NOT NULL DEFAULT '',
    deprecated_at   TIMESTAMP,
    CONSTRAINT pk_03_dim_account_types      PRIMARY KEY (id),
    CONSTRAINT uq_03_dim_account_types_code UNIQUE (code)
);
COMMENT ON TABLE "02_iam"."03_dim_account_types" IS 'Account type classification.';

INSERT INTO "02_iam"."03_dim_account_types" (id, code, label, description) VALUES
    (1, 'human',           'Human',           'Human user via UI or API'),
    (2, 'service_account', 'Service Account', 'Machine-to-machine'),
    (3, 'bot',             'Bot',             'Automated agent');

-- User EAV attribute definitions
CREATE TABLE "02_iam"."05_dim_user_attr_defs" (
    id              SMALLINT    NOT NULL,
    entity_type_id  SMALLINT    NOT NULL DEFAULT 1,
    code            TEXT        NOT NULL,
    label           TEXT        NOT NULL,
    value_type      TEXT        NOT NULL,
    is_pii          BOOLEAN     NOT NULL DEFAULT false,
    is_system       BOOLEAN     NOT NULL DEFAULT true,
    description     TEXT        NOT NULL DEFAULT '',
    deprecated_at   TIMESTAMP,
    CONSTRAINT pk_05_dim_user_attr_defs         PRIMARY KEY (id),
    CONSTRAINT uq_05_dim_user_attr_defs_code    UNIQUE (entity_type_id, code),
    CONSTRAINT chk_05_dim_user_attr_defs_vtype  CHECK (value_type IN ('text', 'jsonb')),
    CONSTRAINT fk_05_dim_user_attr_defs_etype   FOREIGN KEY (entity_type_id)
        REFERENCES "02_iam"."01_dim_org_entity_types"(id)
);
COMMENT ON TABLE "02_iam"."05_dim_user_attr_defs" IS 'User EAV attribute definitions.';

INSERT INTO "02_iam"."05_dim_user_attr_defs" (id, entity_type_id, code, label, value_type, is_pii, description) VALUES
    (1, 1, 'email',        'Email',        'text',  true,  'Primary email address'),
    (2, 1, 'display_name', 'Display Name', 'text',  false, 'Human-readable name'),
    (3, 1, 'avatar_url',   'Avatar URL',   'text',  false, 'Profile picture URL'),
    (4, 1, 'phone',        'Phone',        'text',  true,  'Phone number E.164'),
    (5, 1, 'settings',     'Settings',     'jsonb', false, 'User preferences');

-- User identity table
CREATE TABLE "02_iam"."10_fct_user_users" (
    id              VARCHAR(36) NOT NULL,
    status_id       SMALLINT    NOT NULL DEFAULT 1,
    account_type_id SMALLINT    NOT NULL DEFAULT 1,
    is_active       BOOLEAN     NOT NULL DEFAULT true,
    is_test         BOOLEAN     NOT NULL DEFAULT false,
    deleted_at      TIMESTAMP,
    created_by      VARCHAR(36),
    updated_by      VARCHAR(36),
    created_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_10_fct_user_users         PRIMARY KEY (id),
    CONSTRAINT fk_10_fct_user_users_status  FOREIGN KEY (status_id)
        REFERENCES "02_iam"."02_dim_user_statuses"(id),
    CONSTRAINT fk_10_fct_user_users_actype  FOREIGN KEY (account_type_id)
        REFERENCES "02_iam"."03_dim_account_types"(id)
);
COMMENT ON TABLE "02_iam"."10_fct_user_users" IS 'User identity. No business data — all descriptive attrs in 20_dtl_user_attrs.';

CREATE INDEX idx_10_fct_user_users_live ON "02_iam"."10_fct_user_users" (created_at DESC) WHERE deleted_at IS NULL;

CREATE TRIGGER trg_10_fct_user_users_updated_at BEFORE UPDATE ON "02_iam"."10_fct_user_users"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- User EAV attributes
CREATE TABLE "02_iam"."20_dtl_user_attrs" (
    entity_type_id  SMALLINT    NOT NULL DEFAULT 1,
    entity_id       VARCHAR(36) NOT NULL,
    attr_def_id     SMALLINT    NOT NULL,
    key_text        TEXT,
    key_jsonb       JSONB,
    created_by      VARCHAR(36),
    updated_by      VARCHAR(36),
    created_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_20_dtl_user_attrs             PRIMARY KEY (entity_type_id, entity_id, attr_def_id),
    CONSTRAINT fk_20_dtl_user_attrs_entity_type FOREIGN KEY (entity_type_id)
        REFERENCES "02_iam"."01_dim_org_entity_types"(id),
    CONSTRAINT fk_20_dtl_user_attrs_attr_def    FOREIGN KEY (attr_def_id)
        REFERENCES "02_iam"."05_dim_user_attr_defs"(id)
);
COMMENT ON TABLE "02_iam"."20_dtl_user_attrs" IS 'User EAV attributes. One row per (user, attribute).';

CREATE INDEX idx_20_dtl_user_attrs_entity ON "02_iam"."20_dtl_user_attrs" (entity_id);
CREATE UNIQUE INDEX uq_20_dtl_user_attrs_email ON "02_iam"."20_dtl_user_attrs" (key_text) WHERE attr_def_id = 1 AND key_text IS NOT NULL;

CREATE TRIGGER trg_20_dtl_user_attrs_updated_at BEFORE UPDATE ON "02_iam"."20_dtl_user_attrs"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- User read view
CREATE VIEW "02_iam"."v_10_user_users" AS
SELECT
    u.id, u.is_active, u.is_test,
    us.code AS status, at.code AS account_type,
    u.deleted_at, u.created_by, u.updated_by, u.created_at, u.updated_at,
    MAX(CASE WHEN a.attr_def_id = 1 THEN a.key_text END) AS email,
    MAX(CASE WHEN a.attr_def_id = 2 THEN a.key_text END) AS display_name,
    MAX(CASE WHEN a.attr_def_id = 3 THEN a.key_text END) AS avatar_url,
    COALESCE(MAX(CASE WHEN a.attr_def_id = 5 THEN a.key_jsonb::text END)::jsonb, '{}'::jsonb) AS settings
FROM "02_iam"."10_fct_user_users" u
JOIN "02_iam"."02_dim_user_statuses" us ON us.id = u.status_id
JOIN "02_iam"."03_dim_account_types" at ON at.id = u.account_type_id
LEFT JOIN "02_iam"."20_dtl_user_attrs" a ON a.entity_id = u.id AND a.entity_type_id = 1
GROUP BY u.id, us.code, at.code;
COMMENT ON VIEW "02_iam"."v_10_user_users" IS 'User read view. Pivots EAV attrs into named columns.';

-- =============================================================================
-- DOWN
-- =============================================================================

DROP VIEW  IF EXISTS "02_iam"."v_10_user_users";
DROP TABLE IF EXISTS "02_iam"."20_dtl_user_attrs";
DROP TABLE IF EXISTS "02_iam"."10_fct_user_users";
DROP TABLE IF EXISTS "02_iam"."05_dim_user_attr_defs";
DROP TABLE IF EXISTS "02_iam"."03_dim_account_types";
DROP TABLE IF EXISTS "02_iam"."02_dim_user_statuses";
DELETE FROM "02_iam"."01_dim_org_entity_types" WHERE id = 5;
