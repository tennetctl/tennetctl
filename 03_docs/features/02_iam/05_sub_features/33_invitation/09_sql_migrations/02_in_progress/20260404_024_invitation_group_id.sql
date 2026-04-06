-- UP ====

-- Add group_id to invitations so accepted users can be auto-added to a default group.

ALTER TABLE "02_iam"."53_fct_invitations"
    ADD COLUMN IF NOT EXISTS group_id VARCHAR(36) NULL;

COMMENT ON COLUMN "02_iam"."53_fct_invitations".group_id IS
    'Optional default group the invited user is added to on acceptance.';

-- DOWN ====

ALTER TABLE "02_iam"."53_fct_invitations"
    DROP COLUMN IF EXISTS group_id;
