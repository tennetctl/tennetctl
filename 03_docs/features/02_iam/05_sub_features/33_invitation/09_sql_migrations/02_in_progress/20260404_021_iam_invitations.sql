-- =============================================================================
-- Migration: 20260404_021_iam_invitations
-- Description: Add invitation system — dim_invitation_statuses, fct_invitations,
--              v_invitations view, and related indexes/triggers.
-- Schema: "02_iam"
-- =============================================================================

-- UP ====

-- ---------------------------------------------------------------------------
-- Dimension table: invitation statuses
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "02_iam"."30_dim_invitation_statuses" (
    id           SMALLINT     NOT NULL,
    code         VARCHAR(32)  NOT NULL,
    label        VARCHAR(64)  NOT NULL,
    description  TEXT,
    deprecated_at TIMESTAMP,

    CONSTRAINT pk_30_dim_invitation_statuses PRIMARY KEY (id),
    CONSTRAINT uq_30_dim_invitation_statuses_code UNIQUE (code)
);

COMMENT ON TABLE  "02_iam"."30_dim_invitation_statuses"         IS 'Lookup: possible invitation lifecycle statuses.';
COMMENT ON COLUMN "02_iam"."30_dim_invitation_statuses".id          IS 'Stable numeric PK — never renumber.';
COMMENT ON COLUMN "02_iam"."30_dim_invitation_statuses".code        IS 'Machine-readable status code used in views and service code.';
COMMENT ON COLUMN "02_iam"."30_dim_invitation_statuses".label       IS 'Human-readable label for UI display.';
COMMENT ON COLUMN "02_iam"."30_dim_invitation_statuses".description IS 'Optional description of when this status applies.';
COMMENT ON COLUMN "02_iam"."30_dim_invitation_statuses".deprecated_at IS 'When non-NULL this status is retired (dim rows are never deleted).';

INSERT INTO "02_iam"."30_dim_invitation_statuses" (id, code, label, description) VALUES
    (1, 'pending',  'Pending',  'Invitation has been sent and is awaiting acceptance.'),
    (2, 'accepted', 'Accepted', 'Invitee has accepted the invitation.'),
    (3, 'revoked',  'Revoked',  'Invitation was revoked by an admin before acceptance.'),
    (4, 'expired',  'Expired',  'Invitation passed its expiry timestamp without being accepted.'),
    (5, 'declined', 'Declined', 'Invitee explicitly declined the invitation.')
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Fact table: invitations
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "02_iam"."53_fct_invitations" (
    id             VARCHAR(36)   NOT NULL,
    org_id         VARCHAR(36)   NOT NULL,
    workspace_id   VARCHAR(36),
    invited_by     VARCHAR(36),
    email          VARCHAR(320)  NOT NULL,
    role_id        SMALLINT      NOT NULL DEFAULT 3,
    token_hash     VARCHAR(64)   NOT NULL,
    status_id      SMALLINT      NOT NULL DEFAULT 1,
    custom_message TEXT,
    max_uses       SMALLINT      NOT NULL DEFAULT 1,
    use_count      SMALLINT      NOT NULL DEFAULT 0,
    expires_at     TIMESTAMP     NOT NULL,
    accepted_at    TIMESTAMP,
    accepted_by    VARCHAR(36),
    deleted_at     TIMESTAMP,
    created_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_53_fct_invitations       PRIMARY KEY (id),
    CONSTRAINT uq_53_fct_invitations_token UNIQUE (token_hash),
    CONSTRAINT fk_53_fct_invitations_org   FOREIGN KEY (org_id)       REFERENCES "02_iam"."11_fct_orgs"(id),
    CONSTRAINT fk_53_fct_invitations_status FOREIGN KEY (status_id)   REFERENCES "02_iam"."30_dim_invitation_statuses"(id),
    CONSTRAINT chk_53_fct_invitations_uses  CHECK (use_count <= max_uses),
    CONSTRAINT chk_53_fct_invitations_max   CHECK (max_uses >= 1)
);

COMMENT ON TABLE  "02_iam"."53_fct_invitations"                IS 'Pending and historical org invitations — one row per invite, status tracked via dim.';
COMMENT ON COLUMN "02_iam"."53_fct_invitations".id             IS 'UUID v7 primary key.';
COMMENT ON COLUMN "02_iam"."53_fct_invitations".org_id         IS 'The org the invitee is being invited to join.';
COMMENT ON COLUMN "02_iam"."53_fct_invitations".workspace_id   IS 'Optional workspace UUID — also adds the user to this workspace on accept.';
COMMENT ON COLUMN "02_iam"."53_fct_invitations".invited_by     IS 'User UUID of the actor who sent the invitation. NULL = system-generated.';
COMMENT ON COLUMN "02_iam"."53_fct_invitations".email          IS 'Email address the invitation was sent to.';
COMMENT ON COLUMN "02_iam"."53_fct_invitations".role_id        IS 'FK → dim_org_roles — role the invitee will receive on accept.';
COMMENT ON COLUMN "02_iam"."53_fct_invitations".token_hash     IS 'SHA-256 hex digest of the raw URL token. Never store the raw token.';
COMMENT ON COLUMN "02_iam"."53_fct_invitations".status_id      IS 'FK → 30_dim_invitation_statuses (1=pending, 2=accepted, 3=revoked, 4=expired, 5=declined).';
COMMENT ON COLUMN "02_iam"."53_fct_invitations".custom_message IS 'Optional personal note from the inviter included in the email.';
COMMENT ON COLUMN "02_iam"."53_fct_invitations".max_uses       IS 'Maximum number of times this token can be consumed. 1 = single-use (default).';
COMMENT ON COLUMN "02_iam"."53_fct_invitations".use_count      IS 'Number of times this token has been successfully consumed.';
COMMENT ON COLUMN "02_iam"."53_fct_invitations".expires_at     IS 'UTC expiry timestamp. Service validates expires_at > now() before consuming.';
COMMENT ON COLUMN "02_iam"."53_fct_invitations".accepted_at    IS 'When the last/final acceptance occurred. NULL until accepted.';
COMMENT ON COLUMN "02_iam"."53_fct_invitations".accepted_by    IS 'User UUID of the accepting user. NULL until accepted.';
COMMENT ON COLUMN "02_iam"."53_fct_invitations".deleted_at     IS 'Soft-delete timestamp. NULL = active.';

-- Partial unique index: only one live pending invitation per email+org
CREATE UNIQUE INDEX IF NOT EXISTS uq_53_fct_invitations_email_org_pending
    ON "02_iam"."53_fct_invitations" (org_id, email)
    WHERE status_id = 1 AND deleted_at IS NULL;

-- Index for token hash lookups (accept flow)
CREATE INDEX IF NOT EXISTS idx_53_fct_invitations_token_hash
    ON "02_iam"."53_fct_invitations" (token_hash);

-- Index for listing by org
CREATE INDEX IF NOT EXISTS idx_53_fct_invitations_org_id
    ON "02_iam"."53_fct_invitations" (org_id, created_at DESC);

-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION "02_iam".trg_set_updated_at_53_fct_invitations()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_53_fct_invitations_updated_at
    BEFORE UPDATE ON "02_iam"."53_fct_invitations"
    FOR EACH ROW EXECUTE FUNCTION "02_iam".trg_set_updated_at_53_fct_invitations();

-- ---------------------------------------------------------------------------
-- View: v_invitations
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW "02_iam".v_invitations AS
SELECT
    i.id,
    i.org_id,
    i.workspace_id,
    i.invited_by,
    i.email,
    i.role_id,
    COALESCE(r.code, 'member')  AS role_code,
    COALESCE(r.label, 'Member') AS role_label,
    i.status_id,
    s.code                      AS status_code,
    s.label                     AS status_label,
    i.custom_message,
    i.max_uses,
    i.use_count,
    i.expires_at,
    i.accepted_at,
    i.accepted_by,
    i.token_hash,
    (i.deleted_at IS NOT NULL)  AS is_deleted,
    i.deleted_at,
    i.created_at,
    i.updated_at
FROM "02_iam"."53_fct_invitations" i
JOIN "02_iam"."30_dim_invitation_statuses" s ON s.id = i.status_id
LEFT JOIN "02_iam"."dim_org_roles"         r ON r.id = i.role_id;

COMMENT ON VIEW "02_iam".v_invitations IS 'Resolved invitation view — joins dim tables, exposes is_deleted flag.';

-- DOWN ====

-- DROP VIEW IF EXISTS "02_iam".v_invitations;
-- DROP TRIGGER IF EXISTS trg_53_fct_invitations_updated_at ON "02_iam"."53_fct_invitations";
-- DROP FUNCTION IF EXISTS "02_iam".trg_set_updated_at_53_fct_invitations();
-- DROP TABLE IF EXISTS "02_iam"."53_fct_invitations";
-- DELETE FROM "02_iam"."30_dim_invitation_statuses";
-- DROP TABLE IF EXISTS "02_iam"."30_dim_invitation_statuses";
