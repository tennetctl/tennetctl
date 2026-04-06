-- =============================================================================
-- Migration: 20260404_015_iam_license_profiles.sql
-- Sub-feature: 25_license_profile
-- Description: License profiles — per-org/workspace tier assignment,
--   feature entitlements via flag linkage, JSONB limits.
--   Uses dim_license_tiers from migration 014.
-- UP
-- =============================================================================

SET search_path TO "02_iam", public;

-- ---------------------------------------------------------------------------
-- Fact: license profiles (specific limit configurations within a tier)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."58_fct_license_profiles" (
    id              VARCHAR(36)  NOT NULL,
    tier_id         SMALLINT     NOT NULL,
    name            TEXT         NOT NULL,
    description     TEXT,
    feature_limits  JSONB        NOT NULL DEFAULT '{}'::jsonb,
    is_active       BOOLEAN      NOT NULL DEFAULT true,
    is_test         BOOLEAN      NOT NULL DEFAULT false,
    deleted_at      TIMESTAMP,
    created_by      VARCHAR(36),
    updated_by      VARCHAR(36),
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_fct_license_profiles PRIMARY KEY (id),
    CONSTRAINT fk_fct_license_profiles_tier FOREIGN KEY (tier_id)
        REFERENCES "02_iam"."08_dim_license_tiers"(id)
);
COMMENT ON TABLE "02_iam"."58_fct_license_profiles" IS 'License profiles with specific limits within a tier. One profile can be assigned to many orgs.';
COMMENT ON COLUMN "02_iam"."58_fct_license_profiles".feature_limits IS 'JSONB freeform limits: {"max_users": 50, "sso_enabled": false, "audit_retention_days": 30}';

CREATE INDEX idx_fct_license_profiles_tier ON "02_iam"."58_fct_license_profiles" (tier_id)
    WHERE deleted_at IS NULL;

CREATE TRIGGER trg_fct_license_profiles_updated_at
    BEFORE UPDATE ON "02_iam"."58_fct_license_profiles"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".set_updated_at();

-- Seed default profiles per tier
INSERT INTO "02_iam"."58_fct_license_profiles" (id, tier_id, name, description, feature_limits) VALUES
    ('00000000-0000-0000-0000-000000000301', 1, 'Free',       'Default free tier limits',
     '{"max_orgs": 1, "max_users": 5, "max_workspaces": 2, "max_api_keys": 2, "max_feature_flags": 10, "sso_enabled": false, "mfa_required": false, "audit_retention_days": 7, "custom_roles": false}'::jsonb),
    ('00000000-0000-0000-0000-000000000302', 2, 'Starter',    'Default starter tier limits',
     '{"max_orgs": 3, "max_users": 25, "max_workspaces": 10, "max_api_keys": 10, "max_feature_flags": 50, "sso_enabled": false, "mfa_required": false, "audit_retention_days": 30, "custom_roles": false}'::jsonb),
    ('00000000-0000-0000-0000-000000000303', 3, 'Pro',        'Default pro tier limits',
     '{"max_orgs": 10, "max_users": 100, "max_workspaces": 50, "max_api_keys": 50, "max_feature_flags": 500, "sso_enabled": true, "mfa_required": true, "audit_retention_days": 90, "custom_roles": true}'::jsonb),
    ('00000000-0000-0000-0000-000000000304', 4, 'Enterprise', 'Default enterprise tier limits',
     '{"max_orgs": -1, "max_users": -1, "max_workspaces": -1, "max_api_keys": -1, "max_feature_flags": -1, "sso_enabled": true, "mfa_required": true, "audit_retention_days": 365, "custom_roles": true}'::jsonb);

-- ---------------------------------------------------------------------------
-- Link: org → license profile assignment (one active per org)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."59_lnk_org_license" (
    id              VARCHAR(36)  NOT NULL,
    org_id          VARCHAR(36)  NOT NULL,
    profile_id      VARCHAR(36)  NOT NULL,
    expires_at      TIMESTAMP,
    assigned_by     VARCHAR(36),
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_lnk_org_license PRIMARY KEY (id),
    CONSTRAINT fk_lnk_org_license_profile FOREIGN KEY (profile_id)
        REFERENCES "02_iam"."58_fct_license_profiles"(id)
);
COMMENT ON TABLE "02_iam"."59_lnk_org_license" IS 'One active license profile per org. Upsert on org_id.';

CREATE UNIQUE INDEX idx_uq_lnk_org_license_org
    ON "02_iam"."59_lnk_org_license" (org_id);

-- ---------------------------------------------------------------------------
-- Link: workspace → license profile override (optional, inherits from org)
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."60_lnk_workspace_license" (
    id              VARCHAR(36)  NOT NULL,
    workspace_id    VARCHAR(36)  NOT NULL,
    profile_id      VARCHAR(36)  NOT NULL,
    expires_at      TIMESTAMP,
    assigned_by     VARCHAR(36),
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_lnk_workspace_license PRIMARY KEY (id),
    CONSTRAINT fk_lnk_workspace_license_profile FOREIGN KEY (profile_id)
        REFERENCES "02_iam"."58_fct_license_profiles"(id)
);
COMMENT ON TABLE "02_iam"."60_lnk_workspace_license" IS 'Optional per-workspace license override. Falls back to org license if absent.';

CREATE UNIQUE INDEX idx_uq_lnk_workspace_license_ws
    ON "02_iam"."60_lnk_workspace_license" (workspace_id);

-- ---------------------------------------------------------------------------
-- Link: tier → feature flag entitlements
-- ---------------------------------------------------------------------------
CREATE TABLE "02_iam"."61_lnk_license_flag_entitlements" (
    id              VARCHAR(36)  NOT NULL,
    tier_id         SMALLINT     NOT NULL,
    flag_id         VARCHAR(36)  NOT NULL,
    flag_value      JSONB,
    created_by      VARCHAR(36),
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_lnk_license_flag_entitlements PRIMARY KEY (id),
    CONSTRAINT fk_lnk_license_flag_ent_tier FOREIGN KEY (tier_id)
        REFERENCES "02_iam"."08_dim_license_tiers"(id),
    CONSTRAINT fk_lnk_license_flag_ent_flag FOREIGN KEY (flag_id)
        REFERENCES "02_iam"."22_fct_feature_flags"(id) ON DELETE CASCADE,
    CONSTRAINT uq_lnk_license_flag_entitlements UNIQUE (tier_id, flag_id)
);
COMMENT ON TABLE "02_iam"."61_lnk_license_flag_entitlements" IS 'Which flags are granted by each license tier. flag_value overrides the flag default for this tier.';

-- ---------------------------------------------------------------------------
-- View: org license with resolved tier
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW "02_iam".v_org_licenses AS
SELECT
    ol.id,
    ol.org_id,
    ol.profile_id,
    lp.name         AS profile_name,
    lp.tier_id,
    lt.code         AS tier_code,
    lt.label        AS tier_label,
    lp.feature_limits,
    ol.expires_at,
    ol.assigned_by,
    ol.created_at
FROM "02_iam"."59_lnk_org_license" ol
JOIN "02_iam"."58_fct_license_profiles" lp ON lp.id = ol.profile_id
JOIN "02_iam"."08_dim_license_tiers" lt ON lt.id = lp.tier_id;

-- ---------------------------------------------------------------------------
-- View: flag entitlements per tier
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW "02_iam".v_license_flag_entitlements AS
SELECT
    e.id,
    e.tier_id,
    lt.code         AS tier_code,
    lt.label        AS tier_label,
    e.flag_id,
    f.key           AS flag_key,
    f.name          AS flag_name,
    f.default_value AS flag_default,
    e.flag_value,
    COALESCE(e.flag_value, f.default_value) AS resolved_value,
    e.created_by,
    e.created_at
FROM "02_iam"."61_lnk_license_flag_entitlements" e
JOIN "02_iam"."08_dim_license_tiers" lt ON lt.id = e.tier_id
JOIN "02_iam"."22_fct_feature_flags" f ON f.id = e.flag_id;

-- =============================================================================
-- DOWN
-- =============================================================================

DROP VIEW  IF EXISTS "02_iam".v_license_flag_entitlements;
DROP VIEW  IF EXISTS "02_iam".v_org_licenses;
DROP TABLE IF EXISTS "02_iam"."61_lnk_license_flag_entitlements" CASCADE;
DROP TABLE IF EXISTS "02_iam"."60_lnk_workspace_license" CASCADE;
DROP TABLE IF EXISTS "02_iam"."59_lnk_org_license" CASCADE;
DROP TABLE IF EXISTS "02_iam"."58_fct_license_profiles" CASCADE;
