# Scoping — Gaps, Edge Cases, and God-Tier Enhancements

## Gaps Found (vs Auth0 / WorkOS / Clerk / Frontegg / Propel Auth)

### 1. Org Types / Org Tiers — MISSING

Real platforms let super admins define **types of orgs** (B2B customer, internal team, partner, trial, sandbox). This affects:
- Which features are available
- Which license profile auto-assigns
- UI branding and customisation
- Onboarding flow

**Resolution:** Add `dim_org_types` and a `type_id` column to `fct_org_orgs`.

### 2. Invitation Scoping — MISSING

When inviting users, the scope determines what they're invited TO:
- Platform invitation (super admin inviting to manage platform)
- Org invitation (org admin inviting to their org)
- Project invitation (project lead inviting to a project)

Currently no invitation system exists. Future sub-feature but scope model must support it.

### 3. API Key Scoping — MISSING

API keys need scope too:
- Platform API key (super admin, access to all orgs)
- Org API key (org-scoped, only this org's data)
- Project API key / SDK token (already exists for flags)

### 4. Webhook Scoping — PARTIAL

Flag webhooks exist per-project. But org-level webhooks (notify on any event in the org) and platform webhooks (notify on any event anywhere) are missing.

### 5. Custom Domains / Branding per Org — FUTURE

Not needed now but the scope model should not block it. Org-level settings (EAV on orgs) already support this.

### 6. Environment Scoping — IMPORTANT

Environments (dev/staging/prod) are currently global (`dim_environments`). But projects need per-project environments:
- Project A might have dev/staging/prod
- Project B might have dev/qa/uat/prod

**Resolution:** Keep `dim_environments` as the system catalogue. Add `lnk_project_environments` to map which envs each project uses. Projects inherit all global envs by default but can add custom ones.

### 7. Impersonation — FUTURE

Super admin impersonating an org admin to debug. Requires scope-aware session with `acting_as_org_id`. Not needed now but don't block it.

### 8. Cross-Org Resources — EDGE CASE

Can a user in Org A see a platform group? **Yes** — platform groups are inherited by all orgs. Can they see Org B's groups? **No** — scope filter prevents it.

Can a platform flag reference an org-scoped segment? **No** — a platform flag's rules should only reference platform-scoped segments. Org flags can reference org segments OR platform segments (inheritance).

**Resolution:** Validate scope compatibility at write time:
- Platform flag → platform segment only
- Org flag → org segment + platform segment
- Project flag → project segment + org segment + platform segment

## Edge Case Resolutions

### E1: Unique Constraints with Scoping

**Problem:** `fct_roles.key` currently has a global unique index. With scoping, Org A and Org B should be able to create a role with the same key. But a platform role key must not collide with org roles.

**Resolution:** Partial unique indexes:
```sql
-- Platform keys are globally unique
CREATE UNIQUE INDEX idx_uq_roles_key_platform
    ON fct_roles (key) WHERE scope_type_id = 1 AND deleted_at IS NULL;

-- Org keys are unique within their org
CREATE UNIQUE INDEX idx_uq_roles_key_org
    ON fct_roles (scope_type_id, scope_id, key) WHERE scope_type_id = 2 AND deleted_at IS NULL;
```

Same pattern for flags, groups, segments.

### E2: Platform Flag with project_id

**Problem:** Platform flags (`scope_type_id=1`) don't belong to any project. But `project_id` is a column on the flags table.

**Resolution:** `project_id` is nullable. Platform flags have `project_id=NULL`. Org-scoped flags can optionally have a `project_id`. The `fct_flag_projects` table (renamed to conceptual projects) is strictly org-scoped.

### E3: Default Project Seed Row

**Problem:** Migration 013 seeded a "default" project with `org_id=NULL`. Projects are org-scoped.

**Resolution:** Remove the default seed. Platform flags don't need a project. The seeded "default" row becomes org-specific (each org gets a default project on creation, or no project needed for platform flags).

### E4: Group Membership Validation

**Problem:** Org admin adds a user to a platform group.

**Resolution:** Service layer validates: only super admins can modify membership of `scope_type_id=1` groups. Org admins can only modify `scope_type_id=2, scope_id=their_org` groups.

### E5: Role Permission Resolution

**Problem:** `check_user_permission` joins `dim_org_roles.name` → `fct_roles.key` by string match. This is fragile and doesn't respect scoping.

**Resolution:** Change `lnk_org_members.role_id` to FK directly to `fct_roles.id` instead of `dim_org_roles.id`. Remove the string-match join. The org membership role IS a `fct_roles` row.

Actually — `dim_org_roles` was an interim solution. With proper RBAC (`fct_roles` + `lnk_role_permissions`), `dim_org_roles` becomes redundant. Org membership should reference `fct_roles` directly.

**Migration path:**
1. Map existing `dim_org_roles` entries to `fct_roles`: owner→super-admin, admin→org-admin, member→org-member, viewer→org-viewer
2. Change `lnk_org_members.role_id` FK from `dim_org_roles` to `fct_roles`
3. Drop `dim_org_roles`

This is a bigger change — defer to a follow-up migration but design for it now.

### E6: Scope Inheritance in Flag Evaluation

**Problem:** When evaluating flags for a user in an org, which flags apply?

**Resolution:** Evaluation query:
```sql
WHERE (scope_type_id = 1)  -- platform flags always apply
   OR (scope_type_id = 2 AND scope_id = $org_id)  -- org flags
   OR (scope_type_id = 3 AND scope_id = $project_id)  -- project flags
```

After fetching all applicable flags, org/user overrides are applied as before.

## Implementation Priority

### Phase 1 (this migration — MUST)
- `dim_scope_types` table
- `scope_type_id + scope_id` on `fct_feature_flags`, `fct_roles`, `fct_groups`, `fct_flag_segments`
- `fct_projects` (org-scoped, replaces `fct_flag_projects`)
- Backfill existing data
- Update views
- Update repositories with scope-aware queries
- Update routes with `?scope=` parameter

### Phase 2 (follow-up — SHOULD)
- Remove `dim_org_roles`, point `lnk_org_members.role_id` → `fct_roles`
- Remove `dim_workspace_roles`, point `lnk_workspace_members.role_id` → `fct_roles`
- `dim_org_types` for org classification
- Per-project environments (`lnk_project_environments`)
- Scope validation at write time (platform flag → platform segment only)

### Phase 3 (future — NICE)
- Impersonation
- Cross-scope audit trail
- Org-level webhooks
- Platform API keys
- Invitation scoping
