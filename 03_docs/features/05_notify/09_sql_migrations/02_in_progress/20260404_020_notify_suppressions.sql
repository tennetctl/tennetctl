-- UP ====
-- Migration 020: Email suppression list for bounced/unsubscribed/complained addresses.
-- Hard bounces and unsubscribe events auto-populate this table via webhook handler.
-- Depends on: 018 (schema 05_notify, set_updated_at function).

SET search_path TO "05_notify";

CREATE TABLE IF NOT EXISTS "05_notify"."50_fct_suppressions" (
    id           VARCHAR(36)   NOT NULL,
    org_id       VARCHAR(36)   NOT NULL,
    email        VARCHAR(320)  NOT NULL,
    reason       VARCHAR(50)   NOT NULL,
    source       VARCHAR(50)   NOT NULL DEFAULT 'system',
    send_log_id  VARCHAR(36)   NULL,
    metadata     JSONB         NOT NULL DEFAULT '{}',
    created_by   VARCHAR(36)   NOT NULL DEFAULT 'system',
    updated_by   VARCHAR(36)   NOT NULL DEFAULT 'system',
    created_at   TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at   TIMESTAMP     NULL,
    CONSTRAINT pk_fct_suppressions        PRIMARY KEY (id),
    CONSTRAINT fk_fct_suppressions_org    FOREIGN KEY (org_id) REFERENCES "02_iam"."01_fct_org_orgs" (id),
    CONSTRAINT chk_fct_suppressions_reason CHECK (reason IN ('bounce_hard','bounce_soft','unsubscribed','complained','manual'))
);

CREATE TRIGGER trg_fct_suppressions_updated_at
BEFORE UPDATE ON "05_notify"."50_fct_suppressions"
FOR EACH ROW EXECUTE FUNCTION "05_notify".set_updated_at();

-- Partial unique: one active suppression per org+email (re-add after removal is fine)
CREATE UNIQUE INDEX uq_fct_suppressions_org_email
    ON "05_notify"."50_fct_suppressions" (org_id, email)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_fct_suppressions_org
    ON "05_notify"."50_fct_suppressions" (org_id, created_at DESC)
    WHERE deleted_at IS NULL;

COMMENT ON TABLE "05_notify"."50_fct_suppressions" IS 'Email suppression list. Addresses here are never sent to until suppression is removed by admin.';
COMMENT ON COLUMN "05_notify"."50_fct_suppressions".id          IS 'UUID v7 primary key.';
COMMENT ON COLUMN "05_notify"."50_fct_suppressions".org_id      IS 'FK to 02_iam.11_fct_orgs. Org that owns this suppression.';
COMMENT ON COLUMN "05_notify"."50_fct_suppressions".email       IS 'Suppressed email address (lowercase).';
COMMENT ON COLUMN "05_notify"."50_fct_suppressions".reason      IS 'Why suppressed: bounce_hard, bounce_soft, unsubscribed, complained, manual.';
COMMENT ON COLUMN "05_notify"."50_fct_suppressions".source      IS 'How it was added: webhook (provider callback), api (transactional), admin (manual).';
COMMENT ON COLUMN "05_notify"."50_fct_suppressions".send_log_id IS 'FK to 60_evt_send_log. The send that triggered suppression (if any).';
COMMENT ON COLUMN "05_notify"."50_fct_suppressions".metadata    IS 'Extra context: provider event payload, bounce type, etc.';
COMMENT ON COLUMN "05_notify"."50_fct_suppressions".deleted_at  IS 'NULL = active suppression. SET = admin removed, address can be sent to again.';

CREATE OR REPLACE VIEW "05_notify"."v_suppressions" AS
SELECT
    id, org_id, email, reason, source, send_log_id, metadata,
    created_by, updated_by, created_at, updated_at,
    (deleted_at IS NOT NULL) AS is_removed,
    deleted_at AS removed_at
FROM "05_notify"."50_fct_suppressions";

COMMENT ON VIEW "05_notify"."v_suppressions" IS 'Read view for email suppressions. Maps deleted_at to is_removed/removed_at.';

-- DOWN ====
-- DROP VIEW IF EXISTS "05_notify"."v_suppressions";
-- DROP TABLE IF EXISTS "05_notify"."50_fct_suppressions";
