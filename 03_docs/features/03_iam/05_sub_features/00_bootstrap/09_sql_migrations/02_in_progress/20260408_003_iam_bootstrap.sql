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
    'Identity and access management. Owns users, sessions, and all '
    'authentication-related dim and EAV tables. Every runtime HTTP route '
    'in every feature depends on this schema being in place.';

-- ---------------------------------------------------------------------------
-- 06_dim_entity_types
-- Shared entity-type registry used by 20_dtl_attrs.entity_type_id.
-- IAM-local because the EAV pattern keeps attribute scope per schema.
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
    ('iam_user',    'IAM User',    'A user principal that can log in'),
    ('iam_session','IAM Session', 'An active or historical login session');

GRANT SELECT ON "03_iam"."06_dim_entity_types" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE, DELETE ON "03_iam"."06_dim_entity_types" TO tennetctl_write;

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
GRANT SELECT, INSERT, UPDATE, DELETE ON "03_iam"."06_dim_account_types" TO tennetctl_write;

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
GRANT SELECT, INSERT, UPDATE, DELETE ON "03_iam"."07_dim_auth_types" TO tennetctl_write;

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
GRANT SELECT, INSERT, UPDATE, DELETE ON "03_iam"."07_dim_token_types" TO tennetctl_write;

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

-- Seed the eight attributes V1 actually uses. Entity type ids resolved by
-- code so the seed does not depend on insertion order of the entity-type
-- rows above.
INSERT INTO "03_iam"."07_dim_attr_defs"
    (entity_type_id, code, label, description, value_column)
SELECT et.id, x.code, x.label, x.description, x.value_column
FROM (VALUES
    ('iam_user',    'username',      'Username',      'Login identifier, 3-64 chars.',                                    'key_text'),
    ('iam_user',    'email',         'Email',         'Contact email for the user.',                                      'key_text'),
    ('iam_user',    'password_hash', 'Password Hash', 'Argon2id PHC-format password hash.',                               'key_text'),
    ('iam_session', 'token_hash',    'Token Hash',    'Argon2id hash of the raw session token.',                          'key_text'),
    ('iam_session', 'ip_address',    'IP Address',    'IP address that initiated the session.',                           'key_text'),
    ('iam_session', 'user_agent',    'User Agent',    'User-Agent header at session creation time.',                      'key_text'),
    ('iam_session', 'refresh',       'Refresh Token', 'JTI of the current refresh token. Rotated on each /auth/refresh.','key_text'),
    ('iam_session', 'jti',           'JWT ID',        'JWT ID (jti claim) of the latest issued access token.',            'key_text')
) AS x(entity_code, code, label, description, value_column)
JOIN "03_iam"."06_dim_entity_types" et ON et.code = x.entity_code;

GRANT SELECT ON "03_iam"."07_dim_attr_defs" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE, DELETE ON "03_iam"."07_dim_attr_defs" TO tennetctl_write;

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
GRANT SELECT, INSERT, UPDATE, DELETE ON "03_iam"."08_dim_session_statuses" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 10_fct_users
-- User identity. UUIDs and FKs only. Username, email, password_hash
-- live in 20_dtl_attrs.
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."10_fct_users" (
    id               VARCHAR(36) NOT NULL,
    org_id           VARCHAR(36) NOT NULL,
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

CREATE INDEX idx_iam_fct_users_org_id      ON "03_iam"."10_fct_users" (org_id);
CREATE INDEX idx_iam_fct_users_is_active   ON "03_iam"."10_fct_users" (is_active)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_iam_fct_users_created_at  ON "03_iam"."10_fct_users" (created_at DESC);

COMMENT ON TABLE  "03_iam"."10_fct_users" IS
    'User identity. UUIDs and FKs only — username, email, and '
    'password_hash live in 20_dtl_attrs. The first admin row is created '
    'by the install wizard (00_setup/03_first_admin); subsequent users '
    'are created at runtime by authenticated admins.';
COMMENT ON COLUMN "03_iam"."10_fct_users".id IS
    'UUID v7 primary key. Also serves as created_by/updated_by for the '
    'first admin row (reflexive self-reference).';
COMMENT ON COLUMN "03_iam"."10_fct_users".org_id IS
    'Organisation this user belongs to. For the first admin, org_id = id '
    '(singleton reflexive org). For later users, inherited from creator.';
COMMENT ON COLUMN "03_iam"."10_fct_users".account_type_id IS
    'FK to 06_dim_account_types. V1 uses default_admin only.';
COMMENT ON COLUMN "03_iam"."10_fct_users".auth_type_id IS
    'FK to 07_dim_auth_types. V1 uses username_password only.';
COMMENT ON COLUMN "03_iam"."10_fct_users".is_active IS
    'False to disable login without deleting the row. Cheaper than soft-delete.';
COMMENT ON COLUMN "03_iam"."10_fct_users".is_test IS
    'True for fixture/test rows that should be excluded from production counts.';
COMMENT ON COLUMN "03_iam"."10_fct_users".deleted_at IS
    'Soft-delete timestamp. Rows are never hard-deleted.';
COMMENT ON COLUMN "03_iam"."10_fct_users".created_by IS
    'User that created this row. For the first admin, equal to id.';
COMMENT ON COLUMN "03_iam"."10_fct_users".updated_by IS
    'User that last updated this row.';
COMMENT ON COLUMN "03_iam"."10_fct_users".created_at IS
    'Row creation timestamp (UTC).';
COMMENT ON COLUMN "03_iam"."10_fct_users".updated_at IS
    'Last update timestamp. Set by trigger in production; set manually in migrations.';

GRANT SELECT ON "03_iam"."10_fct_users" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE, DELETE ON "03_iam"."10_fct_users" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 20_fct_sessions
-- Active + historical sessions. Token hash, IP, and user agent live in
-- EAV. The four token-fast-path columns below (token_prefix,
-- refresh_token_hash, refresh_token_prefix, refresh_expires_at) are
-- promoted to columns because they are read on every authenticated
-- request and every token refresh — the EAV join would add two JOINs
-- to the hottest query in the API.
-- ---------------------------------------------------------------------------
CREATE TABLE "03_iam"."20_fct_sessions" (
    id                     VARCHAR(36) NOT NULL,
    user_id                VARCHAR(36) NOT NULL,
    status_id              SMALLINT    NOT NULL,
    -- JWT access token fast-path: first 16 chars of the raw token used as
    -- a candidate-filter index. The full Argon2id hash lives in EAV.
    token_prefix           CHAR(16),
    -- Refresh token: stored as Argon2id hash (same params as passwords).
    -- prefix column gives an O(log N) index predicate before the hash verify.
    refresh_token_hash     TEXT,
    refresh_token_prefix   CHAR(16),
    refresh_expires_at     TIMESTAMP,
    expires_at             TIMESTAMP   NOT NULL,
    absolute_expires_at    TIMESTAMP   NOT NULL,
    last_seen_at           TIMESTAMP,
    is_active              BOOLEAN     NOT NULL DEFAULT TRUE,
    is_test                BOOLEAN     NOT NULL DEFAULT FALSE,
    deleted_at             TIMESTAMP,
    created_by             VARCHAR(36) NOT NULL,
    updated_by             VARCHAR(36) NOT NULL,
    created_at             TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at             TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_iam_fct_sessions              PRIMARY KEY (id),
    CONSTRAINT fk_iam_fct_sessions_user         FOREIGN KEY (user_id)
        REFERENCES "03_iam"."10_fct_users" (id),
    CONSTRAINT fk_iam_fct_sessions_status       FOREIGN KEY (status_id)
        REFERENCES "03_iam"."08_dim_session_statuses" (id),
    CONSTRAINT fk_iam_fct_sessions_created_by   FOREIGN KEY (created_by)
        REFERENCES "03_iam"."10_fct_users" (id),
    CONSTRAINT fk_iam_fct_sessions_updated_by   FOREIGN KEY (updated_by)
        REFERENCES "03_iam"."10_fct_users" (id),
    CONSTRAINT chk_iam_fct_sessions_expiry_order
        CHECK (expires_at <= absolute_expires_at)
);

CREATE INDEX idx_iam_fct_sessions_user_id
    ON "03_iam"."20_fct_sessions" (user_id);
CREATE INDEX idx_iam_fct_sessions_active
    ON "03_iam"."20_fct_sessions" (status_id, expires_at)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_iam_fct_sessions_last_seen
    ON "03_iam"."20_fct_sessions" (last_seen_at DESC);
-- Prefix indexes for O(log N) candidate filtering before Argon2id verify.
-- token_prefix filters the access-token scan; refresh_token_prefix filters
-- the refresh-token scan. Both partial on active, non-deleted sessions.
-- status_id = 1 is 'active' (first IDENTITY row seeded in 08_dim_session_statuses).
-- Subqueries are not allowed in partial index predicates; use the literal.
CREATE INDEX idx_iam_fct_sessions_token_prefix
    ON "03_iam"."20_fct_sessions" (token_prefix)
    WHERE deleted_at IS NULL AND status_id = 1;
CREATE INDEX idx_iam_fct_sessions_refresh_prefix
    ON "03_iam"."20_fct_sessions" (refresh_token_prefix)
    WHERE deleted_at IS NULL AND refresh_token_hash IS NOT NULL;

COMMENT ON TABLE  "03_iam"."20_fct_sessions" IS
    'Login sessions. One row per session, kept for audit even after '
    'revocation or expiry. Slow-path metadata (ip_address, user_agent, '
    'jti, refresh JTI) lives in 20_dtl_attrs. The four token_* / '
    'refresh_* columns are promoted to fct_* as a deliberate perf '
    'exception — they are read on every authenticated request.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".id IS
    'UUID v7 primary key.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".user_id IS
    'User this session belongs to. FK to 10_fct_users.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".status_id IS
    'FK to 08_dim_session_statuses. active | revoked | expired.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".token_prefix IS
    'First 16 characters of the raw access token. Used as an index '
    'predicate to narrow the Argon2id verify scan from O(N) to O(1) '
    'candidates. Not a secret — leaking a prefix gives no useful advantage '
    'to an attacker without the full token.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".refresh_token_hash IS
    'Argon2id PHC-format hash of the opaque refresh token. NULL until '
    'first /auth/refresh call. Rotated on every successful refresh.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".refresh_token_prefix IS
    'First 16 characters of the raw refresh token. Index predicate for '
    'the refresh-token verify scan. Same rationale as token_prefix.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".refresh_expires_at IS
    'Absolute expiry for the refresh token (7d from login). Not slideable. '
    'After this point the user must log in again even if they have a valid '
    'access token — access tokens expire in 15 min so this is reached first.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".expires_at IS
    'Sliding expiry for opaque cookie sessions (legacy). For JWT sessions '
    'this still moves on each request for audit/last-seen purposes, but the '
    'access token''s own exp claim is the authoritative expiry.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".absolute_expires_at IS
    'Hard cap. Set at session creation to created_at + 30d. Never extended. '
    'Checked on every authenticated request; the stricter of this and '
    'refresh_expires_at governs when re-login is required.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".last_seen_at IS
    'Last time the session was used for an authenticated request.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".is_active IS
    'Standard fct_* metadata. False means "do not serve this session" without revoking it.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".is_test IS
    'True for fixture/test sessions.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".deleted_at IS
    'Set on logout. Sessions are soft-deleted so the audit trail survives.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".created_by IS
    'User that created the session. Equal to user_id for normal login.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".updated_by IS
    'User that last updated the session (usually equal to user_id).';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".created_at IS
    'Session creation timestamp.';
COMMENT ON COLUMN "03_iam"."20_fct_sessions".updated_at IS
    'Last update timestamp, updated on token rotations and sliding-window resets.';

GRANT SELECT ON "03_iam"."20_fct_sessions" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE, DELETE ON "03_iam"."20_fct_sessions" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- 20_dtl_attrs
-- EAV attribute values for iam_user and iam_session entities.
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
-- Username lookup is the hottest read path in login — partial index
-- on the username attr_def speeds up O(N) scans significantly.
-- Partial index on the username attribute for fast login lookups.
-- attr_def_id = 1 is the 'username' attribute (first IDENTITY row seeded above).
-- Postgres does not allow subqueries in partial index predicates; use the literal.
CREATE INDEX idx_iam_dtl_attrs_username_lookup
    ON "03_iam"."20_dtl_attrs" (key_text)
    WHERE attr_def_id = 1;

COMMENT ON TABLE  "03_iam"."20_dtl_attrs" IS
    'EAV attribute values for IAM entities. One row per '
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
    'String value. Used for usernames, emails, password hashes, etc.';
COMMENT ON COLUMN "03_iam"."20_dtl_attrs".key_jsonb IS
    'JSONB value. Reserved for future structured attributes.';
COMMENT ON COLUMN "03_iam"."20_dtl_attrs".key_smallint IS
    'Integer value, typically a FK into a dim table.';
COMMENT ON COLUMN "03_iam"."20_dtl_attrs".created_at IS 'Row creation timestamp.';
COMMENT ON COLUMN "03_iam"."20_dtl_attrs".updated_at IS 'Last update timestamp.';

GRANT SELECT ON "03_iam"."20_dtl_attrs" TO tennetctl_read;
GRANT SELECT, INSERT, UPDATE, DELETE ON "03_iam"."20_dtl_attrs" TO tennetctl_write;

-- ---------------------------------------------------------------------------
-- v_users
-- Read view. Joins user rows to their username and email EAV rows.
-- Deliberately excludes password_hash so a careless SELECT * never
-- leaks credential material to logs.
-- ---------------------------------------------------------------------------
CREATE VIEW "03_iam".v_users AS
SELECT
    u.id,
    u.org_id,
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
-- Read view for sessions. Exposes the token_prefix and refresh_prefix
-- columns (not secret) plus timing columns. Excludes the raw hashes
-- (token_hash EAV, refresh_token_hash) — the middleware fetches those
-- via dedicated queries against the prefix-filtered row.
-- ---------------------------------------------------------------------------
CREATE VIEW "03_iam".v_sessions AS
SELECT
    s.id,
    s.user_id,
    st.code                    AS status,
    s.token_prefix,
    s.refresh_token_prefix,
    s.refresh_expires_at,
    s.expires_at,
    s.absolute_expires_at,
    s.last_seen_at,
    (s.deleted_at IS NOT NULL) AS is_deleted,
    s.created_by,
    s.updated_by,
    s.created_at,
    s.updated_at
FROM "03_iam"."20_fct_sessions" s
JOIN "03_iam"."08_dim_session_statuses" st ON s.status_id = st.id;

COMMENT ON VIEW "03_iam".v_sessions IS
    'Sessions with status resolved. Exposes prefix columns for index-based '
    'candidate filtering. refresh_token_hash and the EAV token_hash are '
    'deliberately excluded — middleware fetches them via specific queries '
    'after narrowing by prefix.';

GRANT SELECT ON "03_iam".v_sessions TO tennetctl_read;
GRANT SELECT ON "03_iam".v_sessions TO tennetctl_write;

-- DOWN =======================================================================

DROP VIEW  IF EXISTS "03_iam".v_sessions;
DROP VIEW  IF EXISTS "03_iam".v_users;

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
