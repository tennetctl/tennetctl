-- =============================================================================
-- Migration:   20260408_003_iam_bootstrap.sql
-- Module:      03_iam
-- Sub-feature: 00_bootstrap
-- Sequence:    003
-- Depends on:  002 (02_vault/01_setup)
-- Description: Create the 03_iam schema with users, sessions, dim tables,
--              EAV attribute definitions, and all seed rows. Applied by the
--              migration runner after 02_vault/01_setup. This is the schema
--              that 00_setup/03_first_admin writes to during the install.
-- =============================================================================

-- UP =========================================================================

CREATE SCHEMA IF NOT EXISTS "03_iam";

GRANT USAGE ON SCHEMA "03_iam" TO tennetctl_read;
GRANT USAGE ON SCHEMA "03_iam" TO tennetctl_write;

COMMENT ON SCHEMA "03_iam" IS
    'Identity and access management. Owns users, sessions, orgs, workspaces, '
    'memberships, and all authentication-related dim and EAV tables. Every '
    'runtime HTTP route in every feature depends on this schema being in place.';

-- ---------------------------------------------------------------------------
-- 06_dim_entity_types
-- Shared entity-type registry used by 20_dtl_attrs.entity_type_id.
-- Insert order is significant — IDENTITY values are assigned sequentially.
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."06_dim_entity_types" (
    id             SMALLINT    GENERATED ALWAYS AS IDENTITY,
    code           TEXT        NOT NULL,
    label          TEXT        NOT NULL,
    description    TEXT,
    deprecated_at  TIMESTAMP,

    CONSTRAINT pk_iam_dim_entity_types       PRIMARY KEY (id),
    CONSTRAINT uq_iam_dim_entity_types_code  UNIQUE (code)
);

COMMENT ON TABLE  "03_iam"."06_dim_entity_types" IS
    'Entity-type registry for IAM EAV attributes. One row per kind of '
    'entity that can own attributes in 20_dtl_attrs.';
COMMENT ON COLUMN "03_iam"."06_dim_entity_types".id IS
    'Auto-assigned primary key. Permanent — never renumbered.';
COMMENT ON COLUMN "03_iam"."06_dim_entity_types".code IS
    'Stable machine-readable identifier used by app code.';
COMMENT ON COLUMN "03_iam"."06_dim_entity_types".label IS
    'Human-readable name for display in admin UIs.';
COMMENT ON COLUMN "03_iam"."06_dim_entity_types".description IS
    'Optional long-form description.';
COMMENT ON COLUMN "03_iam"."06_dim_entity_types".deprecated_at IS
    'Set when a row is being phased out. Rows are never deleted.';

INSERT INTO "03_iam"."06_dim_entity_types" (code, label, description) VALUES
    ('iam_user',            'IAM User',            'A user principal that can log in.'),
    ('iam_session',         'IAM Session',         'An active or historical login session.'),
    ('iam_org',             'IAM Org',             'A tenant organisation.'),
    ('iam_workspace',       'IAM Workspace',       'A department/workspace inside an org.'),
    ('iam_user_org',        'IAM User-Org',        'Membership link between a user and an org.'),
    ('iam_user_workspace',  'IAM User-Workspace',  'Membership link between a user and a workspace.');

GRANT SELECT ON "03_iam"."06_dim_entity_types" TO tennetctl_read;
GRANT SELECT ON "03_iam"."06_dim_entity_types" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 06_dim_account_types
-- Coarse user category. V1 has only default_admin in use; default_user
-- is a stub for v2 role work.
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."06_dim_account_types" (
    id             SMALLINT    GENERATED ALWAYS AS IDENTITY,
    code           TEXT        NOT NULL,
    label          TEXT        NOT NULL,
    description    TEXT,
    deprecated_at  TIMESTAMP,

    CONSTRAINT pk_iam_dim_account_types       PRIMARY KEY (id),
    CONSTRAINT uq_iam_dim_account_types_code  UNIQUE (code)
);

COMMENT ON TABLE  "03_iam"."06_dim_account_types" IS
    'Coarse user category. V1 has no RBAC — default_admin can do '
    'everything; default_user is a stub for v2.';
COMMENT ON COLUMN "03_iam"."06_dim_account_types".id IS
    'Auto-assigned primary key. Permanent.';
COMMENT ON COLUMN "03_iam"."06_dim_account_types".code IS
    'Stable machine-readable identifier.';
COMMENT ON COLUMN "03_iam"."06_dim_account_types".label IS
    'Human-readable name.';
COMMENT ON COLUMN "03_iam"."06_dim_account_types".description IS
    'Optional description.';
COMMENT ON COLUMN "03_iam"."06_dim_account_types".deprecated_at IS
    'Set when phasing out a row.';

INSERT INTO "03_iam"."06_dim_account_types" (code, label, description) VALUES
    ('default_admin', 'Default Admin', 'Full access. Created by the install wizard for the first admin.'),
    ('default_user',  'Default User',  'Non-admin user. Stub — unused in v1.');

GRANT SELECT ON "03_iam"."06_dim_account_types" TO tennetctl_read;
GRANT SELECT ON "03_iam"."06_dim_account_types" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 07_dim_auth_types
-- Authentication method registry. V1 ships one method; future methods
-- (TOTP, WebAuthn, OAuth providers) append new rows.
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."07_dim_auth_types" (
    id             SMALLINT    GENERATED ALWAYS AS IDENTITY,
    code           TEXT        NOT NULL,
    label          TEXT        NOT NULL,
    description    TEXT,
    deprecated_at  TIMESTAMP,

    CONSTRAINT pk_iam_dim_auth_types       PRIMARY KEY (id),
    CONSTRAINT uq_iam_dim_auth_types_code  UNIQUE (code)
);

COMMENT ON TABLE  "03_iam"."07_dim_auth_types" IS
    'Authentication method registry. Extend by INSERT, never ALTER.';
COMMENT ON COLUMN "03_iam"."07_dim_auth_types".id IS
    'Auto-assigned primary key. Permanent.';
COMMENT ON COLUMN "03_iam"."07_dim_auth_types".code IS
    'Stable machine-readable identifier used by app code when dispatching '
    'to the right verification path.';
COMMENT ON COLUMN "03_iam"."07_dim_auth_types".label IS
    'Human-readable name.';
COMMENT ON COLUMN "03_iam"."07_dim_auth_types".description IS
    'Optional description.';
COMMENT ON COLUMN "03_iam"."07_dim_auth_types".deprecated_at IS
    'Set when phasing out a method.';

INSERT INTO "03_iam"."07_dim_auth_types" (code, label, description) VALUES
    ('username_password', 'Username + Password', 'Classic credentials with Argon2id hashing. v1 only.');

GRANT SELECT ON "03_iam"."07_dim_auth_types" TO tennetctl_read;
GRANT SELECT ON "03_iam"."07_dim_auth_types" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 07_dim_token_types
-- Distinguishes access tokens from refresh tokens for audit queries.
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."07_dim_token_types" (
    id             SMALLINT    GENERATED ALWAYS AS IDENTITY,
    code           TEXT        NOT NULL,
    label          TEXT        NOT NULL,
    description    TEXT,
    deprecated_at  TIMESTAMP,

    CONSTRAINT pk_iam_dim_token_types       PRIMARY KEY (id),
    CONSTRAINT uq_iam_dim_token_types_code  UNIQUE (code)
);

COMMENT ON TABLE  "03_iam"."07_dim_token_types" IS
    'Token type registry. access = short-lived JWT. refresh = long-lived '
    'opaque rotation token. Used to scope audit events.';

INSERT INTO "03_iam"."07_dim_token_types" (code, label, description) VALUES
    ('access',  'Access Token',  'Short-lived signed JWT (15 min). Verified statelessly.'),
    ('refresh', 'Refresh Token', 'Long-lived opaque rotation token (7d). Verified against DB hash + prefix.');

GRANT SELECT ON "03_iam"."07_dim_token_types" TO tennetctl_read;
GRANT SELECT ON "03_iam"."07_dim_token_types" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 07_dim_attr_defs
-- EAV attribute registry. Every attribute any 20_dtl_attrs row can
-- reference must be registered here first.
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."07_dim_attr_defs" (
    id              SMALLINT    GENERATED ALWAYS AS IDENTITY,
    entity_type_id  SMALLINT    NOT NULL,
    code            TEXT        NOT NULL,
    label           TEXT        NOT NULL,
    description     TEXT,
    value_column    TEXT        NOT NULL,
    deprecated_at   TIMESTAMP,

    CONSTRAINT pk_iam_dim_attr_defs                PRIMARY KEY (id),
    CONSTRAINT uq_iam_dim_attr_defs_entity_code    UNIQUE (entity_type_id, code),
    CONSTRAINT fk_iam_dim_attr_defs_entity_type    FOREIGN KEY (entity_type_id)
        REFERENCES "03_iam"."06_dim_entity_types" (id),
    CONSTRAINT chk_iam_dim_attr_defs_value_column
        CHECK (value_column IN ('key_text', 'key_jsonb', 'key_smallint'))
);

CREATE INDEX idx_iam_dim_attr_defs_entity_type
    ON "03_iam"."07_dim_attr_defs" (entity_type_id);

COMMENT ON TABLE  "03_iam"."07_dim_attr_defs" IS
    'Registered EAV attributes. Every 20_dtl_attrs row must reference an '
    'entry here. value_column says which column in 20_dtl_attrs carries '
    'the value for this attribute.';
COMMENT ON COLUMN "03_iam"."07_dim_attr_defs".id IS
    'Auto-assigned primary key. Permanent.';
COMMENT ON COLUMN "03_iam"."07_dim_attr_defs".entity_type_id IS
    'Which entity type this attribute belongs to. FK to 06_dim_entity_types.';
COMMENT ON COLUMN "03_iam"."07_dim_attr_defs".code IS
    'Attribute identifier, unique within its entity type.';
COMMENT ON COLUMN "03_iam"."07_dim_attr_defs".label IS
    'Human-readable name.';
COMMENT ON COLUMN "03_iam"."07_dim_attr_defs".description IS
    'Optional description.';
COMMENT ON COLUMN "03_iam"."07_dim_attr_defs".value_column IS
    'Which key_* column in 20_dtl_attrs holds the value. One of '
    'key_text, key_jsonb, key_smallint.';
COMMENT ON COLUMN "03_iam"."07_dim_attr_defs".deprecated_at IS
    'Set when an attribute is being removed. Rows are never deleted.';

-- Seed all attribute definitions. Entity type ids resolved by code via JOIN
-- so the seed does not depend on insertion-order IDENTITY values.
INSERT INTO "03_iam"."07_dim_attr_defs"
    (entity_type_id, code, label, description, value_column)
SELECT et.id, x.code, x.label, x.description, x.value_column
FROM (VALUES
    -- iam_user (3 attrs)
    ('iam_user', 'username',                    'Username',                     'Login identifier, 3-64 chars.',                                                         'key_text'),
    ('iam_user', 'email',                       'Email',                        'Contact email for the user.',                                                           'key_text'),
    ('iam_user', 'password_hash',               'Password Hash',                'Argon2id PHC-format password hash.',                                                    'key_text'),
    -- iam_session (14 attrs)
    ('iam_session', 'token_hash',               'Token Hash',                   'Argon2id hash of the raw session token.',                                               'key_text'),
    ('iam_session', 'ip_address',               'IP Address',                   'IP address that initiated the session.',                                                'key_text'),
    ('iam_session', 'user_agent',               'User Agent',                   'User-Agent header at session creation time.',                                           'key_text'),
    ('iam_session', 'refresh',                  'Refresh Token',                'JTI of the current refresh token. Rotated on each /auth/refresh.',                     'key_text'),
    ('iam_session', 'jti',                      'JWT ID',                       'JWT ID (jti claim) of the latest issued access token.',                                 'key_text'),
    ('iam_session', 'token_prefix',             'Token Prefix',                 'First 16 characters of the raw access token for index-based candidate filtering.',     'key_text'),
    ('iam_session', 'refresh_token_hash',       'Refresh Token Hash',           'Argon2id PHC-format hash of the opaque refresh token.',                                'key_text'),
    ('iam_session', 'refresh_token_prefix',     'Refresh Token Prefix',         'First 16 characters of the raw refresh token for index-based candidate filtering.',   'key_text'),
    ('iam_session', 'refresh_expires_at',       'Refresh Expires At',           'Absolute expiry for the refresh token (7d from login). Not slideable.',               'key_text'),
    ('iam_session', 'expires_at',               'Expires At',                   'Sliding expiry for the session.',                                                      'key_text'),
    ('iam_session', 'absolute_expires_at',      'Absolute Expires At',          'Hard cap set at session creation (created_at + 30d). Never extended.',                'key_text'),
    ('iam_session', 'last_seen_at',             'Last Seen At',                 'Last time the session was used for an authenticated request.',                         'key_text'),
    ('iam_session', 'active_org_id',            'Active Org ID',                'The org the session is currently scoped to.',                                          'key_text'),
    ('iam_session', 'active_workspace_id',      'Active Workspace ID',          'The workspace the session is currently scoped to.',                                    'key_text'),
    -- iam_org (5 attrs)
    ('iam_org', 'name',                         'Name',                         'Display name of the organisation.',                                                    'key_text'),
    ('iam_org', 'slug',                         'Slug',                         'URL-safe unique identifier for the org.',                                              'key_text'),
    ('iam_org', 'description',                  'Description',                  'Optional description of the organisation.',                                            'key_text'),
    ('iam_org', 'logo_url',                     'Logo URL',                     'URL to the organisation logo image.',                                                  'key_text'),
    ('iam_org', 'billing_email',                'Billing Email',                'Billing contact email for the organisation.',                                          'key_text'),
    -- iam_workspace (4 attrs)
    ('iam_workspace', 'name',                   'Name',                         'Display name of the workspace.',                                                       'key_text'),
    ('iam_workspace', 'slug',                   'Slug',                         'URL-safe identifier for the workspace, unique within the org.',                       'key_text'),
    ('iam_workspace', 'description',            'Description',                  'Optional description of the workspace.',                                               'key_text'),
    ('iam_workspace', 'icon',                   'Icon',                         'Icon identifier or URL for the workspace.',                                            'key_text')
) AS x(entity_code, code, label, description, value_column)
JOIN "03_iam"."06_dim_entity_types" et ON et.code = x.entity_code;

GRANT SELECT ON "03_iam"."07_dim_attr_defs" TO tennetctl_read;
GRANT SELECT ON "03_iam"."07_dim_attr_defs" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 08_dim_session_statuses
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."08_dim_session_statuses" (
    id             SMALLINT    GENERATED ALWAYS AS IDENTITY,
    code           TEXT        NOT NULL,
    label          TEXT        NOT NULL,
    description    TEXT,
    deprecated_at  TIMESTAMP,

    CONSTRAINT pk_iam_dim_session_statuses      PRIMARY KEY (id),
    CONSTRAINT uq_iam_dim_session_statuses_code UNIQUE (code)
);

COMMENT ON TABLE  "03_iam"."08_dim_session_statuses" IS
    'Session lifecycle status. active = valid, revoked = logged out, '
    'expired = past expires_at or absolute_expires_at.';

INSERT INTO "03_iam"."08_dim_session_statuses" (code, label, description) VALUES
    ('active',  'Active',  'Session is valid and can be used for authenticated requests.'),
    ('revoked', 'Revoked', 'Session was explicitly logged out and can no longer be used.'),
    ('expired', 'Expired', 'Session passed its expires_at or absolute_expires_at.');

GRANT SELECT ON "03_iam"."08_dim_session_statuses" TO tennetctl_read;
GRANT SELECT ON "03_iam"."08_dim_session_statuses" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 10_fct_users
-- User identity. Pure-EAV shape — NO org_id column. Username, email,
-- and password_hash live in 20_dtl_attrs.
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."10_fct_users" (
    id               VARCHAR(36) NOT NULL,
    account_type_id  SMALLINT    NOT NULL,
    auth_type_id     SMALLINT    NOT NULL,
    is_active        BOOLEAN     NOT NULL DEFAULT TRUE,
    is_test          BOOLEAN     NOT NULL DEFAULT FALSE,
    deleted_at       TIMESTAMP,
    created_by       VARCHAR(36) NOT NULL,
    updated_by       VARCHAR(36) NOT NULL,
    created_at       TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_iam_fct_users                  PRIMARY KEY (id),
    CONSTRAINT fk_iam_fct_users_account_type     FOREIGN KEY (account_type_id)
        REFERENCES "03_iam"."06_dim_account_types" (id),
    CONSTRAINT fk_iam_fct_users_auth_type        FOREIGN KEY (auth_type_id)
        REFERENCES "03_iam"."07_dim_auth_types" (id),
    CONSTRAINT fk_iam_fct_users_created_by       FOREIGN KEY (created_by)
        REFERENCES "03_iam"."10_fct_users" (id) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT fk_iam_fct_users_updated_by       FOREIGN KEY (updated_by)
        REFERENCES "03_iam"."10_fct_users" (id) DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX idx_iam_fct_users_is_active   ON "03_iam"."10_fct_users" (is_active)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_iam_fct_users_created_at  ON "03_iam"."10_fct_users" (created_at DESC);

COMMENT ON TABLE  "03_iam"."10_fct_users" IS
    'User identity. Pure-EAV — username, email, and password_hash live in '
    '20_dtl_attrs. No org_id column: org membership is in 40_lnk_user_orgs. '
    'The first admin row is created by the install wizard; subsequent users '
    'are created at runtime by authenticated admins.';
COMMENT ON COLUMN "03_iam"."10_fct_users".id IS
    'UUID v7 primary key. Also serves as created_by/updated_by for the '
    'first admin row (reflexive self-reference, allowed by DEFERRABLE FK).';
COMMENT ON COLUMN "03_iam"."10_fct_users".account_type_id IS
    'FK to 06_dim_account_types. V1 uses default_admin only.';
COMMENT ON COLUMN "03_iam"."10_fct_users".auth_type_id IS
    'FK to 07_dim_auth_types. V1 uses username_password only.';
COMMENT ON COLUMN "03_iam"."10_fct_users".is_active IS
    'False to disable login without deleting the row.';
COMMENT ON COLUMN "03_iam"."10_fct_users".is_test IS
    'True for fixture/test rows excluded from production counts.';
COMMENT ON COLUMN "03_iam"."10_fct_users".deleted_at IS
    'Soft-delete timestamp. Rows are never hard-deleted.';
COMMENT ON COLUMN "03_iam"."10_fct_users".created_by IS
    'User that created this row. For the first admin, equal to id.';
COMMENT ON COLUMN "03_iam"."10_fct_users".updated_by IS
    'User that last updated this row.';
COMMENT ON COLUMN "03_iam"."10_fct_users".created_at IS
    'Row creation timestamp (UTC).';
COMMENT ON COLUMN "03_iam"."10_fct_users".updated_at IS
    'Last update timestamp.';

GRANT SELECT ON "03_iam"."10_fct_users" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE, DELETE ON "03_iam"."10_fct_users" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 20_fct_sessions
-- Pure-EAV shape. All token/timing fields live in 20_dtl_attrs as EAV rows.
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."20_fct_sessions" (
    id               VARCHAR(36) NOT NULL,
    user_id          VARCHAR(36) NOT NULL,
    status_id        SMALLINT    NOT NULL,
    is_active        BOOLEAN     NOT NULL DEFAULT TRUE,
    is_test          BOOLEAN     NOT NULL DEFAULT FALSE,
    deleted_at       TIMESTAMP,
    created_by       VARCHAR(36) NOT NULL,
    updated_by       VARCHAR(36) NOT NULL,
    created_at       TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_iam_fct_sessions              PRIMARY KEY (id),
    CONSTRAINT fk_iam_fct_sessions_user         FOREIGN KEY (user_id)
        REFERENCES "03_iam"."10_fct_users" (id),
    CONSTRAINT fk_iam_fct_sessions_status       FOREIGN KEY (status_id)
        REFERENCES "03_iam"."08_dim_session_statuses" (id),
    CONSTRAINT fk_iam_fct_sessions_created_by   FOREIGN KEY (created_by)
        REFERENCES "03_iam"."10_fct_users" (id),
    CONSTRAINT fk_iam_fct_sessions_updated_by   FOREIGN KEY (updated_by)
        REFERENCES "03_iam"."10_fct_users" (id)
);

CREATE INDEX idx_iam_fct_sessions_user_id
    ON "03_iam"."20_fct_sessions" (user_id);
CREATE INDEX idx_iam_fct_sessions_active
    ON "03_iam"."20_fct_sessions" (status_id)
    WHERE deleted_at IS NULL;

COMMENT ON TABLE  "03_iam"."20_fct_sessions" IS
    'Login sessions. One row per session, kept for audit even after '
    'revocation or expiry. Pure-EAV: all token and timing metadata '
    '(token_prefix, refresh_token_hash, expires_at, etc.) lives in '
    '20_dtl_attrs. active_org_id and active_workspace_id are also in EAV.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".id IS 'UUID v7 primary key.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".user_id IS
    'User this session belongs to. FK to 10_fct_users.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".status_id IS
    'FK to 08_dim_session_statuses. active | revoked | expired.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".is_active IS
    'Standard fct_* metadata. False means do not serve this session.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".is_test IS
    'True for fixture/test sessions.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".deleted_at IS
    'Set on logout. Sessions are soft-deleted so the audit trail survives.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".created_by IS
    'User that created the session. Equal to user_id for normal login.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".updated_by IS
    'User that last updated the session.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".created_at IS
    'Session creation timestamp.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".updated_at IS
    'Last update timestamp, updated on token rotations.';

GRANT SELECT ON "03_iam"."20_fct_sessions" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE, DELETE ON "03_iam"."20_fct_sessions" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 20_dtl_attrs
-- EAV attribute values for all IAM entities.
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."20_dtl_attrs" (
    id              VARCHAR(36) NOT NULL,
    entity_type_id  SMALLINT    NOT NULL,
    entity_id       VARCHAR(36) NOT NULL,
    attr_def_id     SMALLINT    NOT NULL,
    key_text        TEXT,
    key_jsonb       JSONB,
    key_smallint    SMALLINT,
    created_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_iam_dtl_attrs                  PRIMARY KEY (id),
    CONSTRAINT fk_iam_dtl_attrs_entity_type      FOREIGN KEY (entity_type_id)
        REFERENCES "03_iam"."06_dim_entity_types" (id),
    CONSTRAINT fk_iam_dtl_attrs_attr_def         FOREIGN KEY (attr_def_id)
        REFERENCES "03_iam"."07_dim_attr_defs" (id),
    CONSTRAINT uq_iam_dtl_attrs_entity_attr      UNIQUE (entity_id, attr_def_id),
    CONSTRAINT chk_iam_dtl_attrs_one_value       CHECK (
        (CASE WHEN key_text     IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN key_jsonb    IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN key_smallint IS NOT NULL THEN 1 ELSE 0 END) = 1
    )
);

CREATE INDEX idx_iam_dtl_attrs_entity
    ON "03_iam"."20_dtl_attrs" (entity_type_id, entity_id);
CREATE INDEX idx_iam_dtl_attrs_attr_def
    ON "03_iam"."20_dtl_attrs" (attr_def_id);

COMMENT ON TABLE  "03_iam"."20_dtl_attrs" IS
    'EAV attribute values for all IAM entities. One row per '
    '(entity, attr_def) pair. Exactly one of the three key_* columns '
    'is non-NULL, enforced by CHECK.';
COMMENT ON COLUMN "03_iam"."20_dtl_attrs".id IS 'UUID v7 primary key.';
COMMENT ON COLUMN "03_iam"."20_dtl_attrs".entity_type_id IS
    'FK to 06_dim_entity_types. Determines which table entity_id points into.';
COMMENT ON COLUMN "03_iam"."20_dtl_attrs".entity_id IS
    'Id of the target entity. Not enforced by FK because the target '
    'table varies with entity_type_id.';
COMMENT ON COLUMN "03_iam"."20_dtl_attrs".attr_def_id IS
    'FK to 07_dim_attr_defs. Says which attribute this row carries.';
COMMENT ON COLUMN "03_iam"."20_dtl_attrs".key_text IS
    'String value. Used for usernames, emails, password hashes, token fields, etc.';
COMMENT ON COLUMN "03_iam"."20_dtl_attrs".key_jsonb IS
    'JSONB value. Reserved for future structured attributes.';
COMMENT ON COLUMN "03_iam"."20_dtl_attrs".key_smallint IS
    'Integer value, typically a FK into a dim table.';
COMMENT ON COLUMN "03_iam"."20_dtl_attrs".created_at IS 'Row creation timestamp.';
COMMENT ON COLUMN "03_iam"."20_dtl_attrs".updated_at IS 'Last update timestamp.';

GRANT SELECT ON "03_iam"."20_dtl_attrs" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE, DELETE ON "03_iam"."20_dtl_attrs" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- Hot-path partial indexes on 20_dtl_attrs
-- attr_def_ids resolved by code + entity code — no hardcoded literals.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    username_id          SMALLINT;
    jti_id               SMALLINT;
    refresh_token_hash_id SMALLINT;
    abs_exp_id           SMALLINT;
BEGIN
    SELECT d.id INTO username_id
      FROM "03_iam"."07_dim_attr_defs" d
      JOIN "03_iam"."06_dim_entity_types" et ON d.entity_type_id = et.id
     WHERE et.code = 'iam_user' AND d.code = 'username';

    SELECT d.id INTO jti_id
      FROM "03_iam"."07_dim_attr_defs" d
      JOIN "03_iam"."06_dim_entity_types" et ON d.entity_type_id = et.id
     WHERE et.code = 'iam_session' AND d.code = 'jti';

    SELECT d.id INTO refresh_token_hash_id
      FROM "03_iam"."07_dim_attr_defs" d
      JOIN "03_iam"."06_dim_entity_types" et ON d.entity_type_id = et.id
     WHERE et.code = 'iam_session' AND d.code = 'refresh_token_hash';

    SELECT d.id INTO abs_exp_id
      FROM "03_iam"."07_dim_attr_defs" d
      JOIN "03_iam"."06_dim_entity_types" et ON d.entity_type_id = et.id
     WHERE et.code = 'iam_session' AND d.code = 'absolute_expires_at';

    EXECUTE format(
        'CREATE INDEX idx_iam_dtl_attrs_username_lookup ON "03_iam"."20_dtl_attrs" (key_text) WHERE attr_def_id = %s',
        username_id);

    EXECUTE format(
        'CREATE INDEX idx_iam_dtl_attrs_jti_lookup ON "03_iam"."20_dtl_attrs" (key_text) WHERE attr_def_id = %s',
        jti_id);

    EXECUTE format(
        'CREATE INDEX idx_iam_dtl_attrs_refresh_hash ON "03_iam"."20_dtl_attrs" (entity_id) WHERE attr_def_id = %s',
        refresh_token_hash_id);

    EXECUTE format(
        'CREATE INDEX idx_iam_dtl_attrs_abs_exp ON "03_iam"."20_dtl_attrs" (entity_id) WHERE attr_def_id = %s',
        abs_exp_id);
END $$;

-- ---------------------------------------------------------------------------
-- v_users
-- Read view. Resolves attr_def_ids by code — no hardcoded IDs.
-- password_hash deliberately excluded so SELECT * never leaks credentials.
-- ---------------------------------------------------------------------------
CREATE VIEW "03_iam".v_users AS
SELECT
    u.id,
    a.code                 AS account_type,
    t.code                 AS auth_type,
    un.key_text            AS username,
    em.key_text            AS email,
    u.is_active,
    (u.deleted_at IS NOT NULL) AS is_deleted,
    u.created_by,
    u.updated_by,
    u.created_at,
    u.updated_at
FROM "03_iam"."10_fct_users" u
JOIN "03_iam"."06_dim_account_types" a ON u.account_type_id = a.id
JOIN "03_iam"."07_dim_auth_types"    t ON u.auth_type_id    = t.id
LEFT JOIN "03_iam"."20_dtl_attrs" un
       ON un.entity_id = u.id
      AND un.attr_def_id = (
          SELECT d.id
            FROM "03_iam"."07_dim_attr_defs" d
            JOIN "03_iam"."06_dim_entity_types" et ON d.entity_type_id = et.id
           WHERE d.code = 'username' AND et.code = 'iam_user'
      )
LEFT JOIN "03_iam"."20_dtl_attrs" em
       ON em.entity_id = u.id
      AND em.attr_def_id = (
          SELECT d.id
            FROM "03_iam"."07_dim_attr_defs" d
            JOIN "03_iam"."06_dim_entity_types" et ON d.entity_type_id = et.id
           WHERE d.code = 'email' AND et.code = 'iam_user'
      );

COMMENT ON VIEW "03_iam".v_users IS
    'Users with username and email resolved from EAV. password_hash is '
    'deliberately NOT exposed here — login code fetches it via a '
    'dedicated query so SELECT * in logs never leaks a hash.';

GRANT SELECT ON "03_iam".v_users TO tennetctl_read;
GRANT SELECT ON "03_iam".v_users TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- v_sessions
-- Full EAV pivot using GROUP BY + MAX(CASE WHEN) for all session attrs.
-- ---------------------------------------------------------------------------
CREATE VIEW "03_iam".v_sessions AS
SELECT
    s.id,
    s.user_id,
    st.code AS status,
    MAX(CASE WHEN ad.code = 'token_prefix'         THEN a.key_text END)            AS token_prefix,
    MAX(CASE WHEN ad.code = 'refresh_token_prefix' THEN a.key_text END)            AS refresh_token_prefix,
    MAX(CASE WHEN ad.code = 'refresh_expires_at'   THEN a.key_text END)::timestamp AS refresh_expires_at,
    MAX(CASE WHEN ad.code = 'expires_at'           THEN a.key_text END)::timestamp AS expires_at,
    MAX(CASE WHEN ad.code = 'absolute_expires_at'  THEN a.key_text END)::timestamp AS absolute_expires_at,
    MAX(CASE WHEN ad.code = 'last_seen_at'         THEN a.key_text END)::timestamp AS last_seen_at,
    MAX(CASE WHEN ad.code = 'active_org_id'        THEN a.key_text END)            AS active_org_id,
    MAX(CASE WHEN ad.code = 'active_workspace_id'  THEN a.key_text END)            AS active_workspace_id,
    (s.deleted_at IS NOT NULL) AS is_deleted,
    s.created_by,
    s.updated_by,
    s.created_at,
    s.updated_at
FROM "03_iam"."20_fct_sessions" s
JOIN "03_iam"."08_dim_session_statuses" st ON s.status_id = st.id
LEFT JOIN "03_iam"."20_dtl_attrs" a
       ON a.entity_type_id = (SELECT id FROM "03_iam"."06_dim_entity_types" WHERE code = 'iam_session')
      AND a.entity_id = s.id
LEFT JOIN "03_iam"."07_dim_attr_defs" ad ON ad.id = a.attr_def_id
GROUP BY s.id, s.user_id, st.code, s.deleted_at, s.created_by, s.updated_by, s.created_at, s.updated_at;

COMMENT ON VIEW "03_iam".v_sessions IS
    'Sessions with status and all EAV attrs pivoted. Exposes prefix columns '
    'for index-based candidate filtering. refresh_token_hash and the EAV '
    'token_hash are deliberately excluded — middleware fetches them via '
    'specific queries after narrowing by prefix.';

GRANT SELECT ON "03_iam".v_sessions TO tennetctl_read;
GRANT SELECT ON "03_iam".v_sessions TO tennetctl_write;

-- DOWN =======================================================================

DROP VIEW IF EXISTS "03_iam".v_sessions;
DROP VIEW IF EXISTS "03_iam".v_users;
DROP INDEX IF EXISTS idx_iam_dtl_attrs_username_lookup;
DROP INDEX IF EXISTS idx_iam_dtl_attrs_jti_lookup;
DROP INDEX IF EXISTS idx_iam_dtl_attrs_refresh_hash;
DROP INDEX IF EXISTS idx_iam_dtl_attrs_abs_exp;
DROP TABLE IF EXISTS "03_iam"."20_dtl_attrs";
DROP TABLE IF EXISTS "03_iam"."20_fct_sessions";
DROP TABLE IF EXISTS "03_iam"."10_fct_users";
DROP TABLE IF EXISTS "03_iam"."08_dim_session_statuses";
DROP TABLE IF EXISTS "03_iam"."07_dim_attr_defs";
DROP TABLE IF EXISTS "03_iam"."07_dim_token_types";
DROP TABLE IF EXISTS "03_iam"."07_dim_auth_types";
DROP TABLE IF EXISTS "03_iam"."06_dim_account_types";
DROP TABLE IF EXISTS "03_iam"."06_dim_entity_types";
DROP SCHEMA IF EXISTS "03_iam";
