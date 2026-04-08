# IAM Build Plan — Exact Steps

This is the exact, step-by-step plan for building IAM from where it stands today. No code — just the workflow you follow. Review this, then execute it one sub-feature at a time.

> **Vocabulary**: in this doc "IAM" is a **feature** in tennetctl terminology — see [00_README.md](00_README.md#vocabulary-read-this-first). Inside IAM are sub-features (`00_bootstrap`, `01_org`, `02_user`, `08_auth`, etc.). The word "module" appears below where it refers to backend Python packages or GitHub labels (`module:iam`); module and feature mean the same thing in this project.
>
> **The migration runner does not exist yet.** Several phases below run `uv run python -m scripts.migrate up`. There is no `scripts/migrate.py` in the repo today — building it is one of the very first sub-features (likely inside `01_foundation` or as a tool sub-feature inside IAM itself). Until it lands, apply migrations by hand with `docker compose exec postgres psql -U tennetctl -d tennetctl -f /path/to/migration.sql` and verify the round-trip manually.

---

## Current State

### What Exists

- Feature manifest (`feature.manifest.yaml`) — lists 12+ sub-features with statuses
- 25 migration SQL files — schema design is done for most sub-features
- Full doc sets for: `01_org`, `02_user`, `03_workspace`, `08_auth` (scope, design, architecture, API contract)
- Partial docs for: `04_group`, `05_org_member`, `06_group_member`, `07_workspace_member`, `19_rbac`, `24_feature_flag`, `25_license_profile` (README or scope only)
- Empty docs for: `33_invitation`, `34_mfa`, `35_personal_access_token`, `36_api_key` (just migration SQL)
- Sub-features listed but no directory yet: `09_session`, `10_auth_config`, `11_mfa (separate)`, `12_oauth2`, etc.
- **No backend code** (no `backend/02_features/iam/` with Python files)
- **No frontend code** (no `frontend/src/app/iam/` with .tsx files)
- **No tests** (no `backend/tests/02_iam/`)

### What Needs to Happen

1. Complete docs for all sub-features (scope + design + API contract)
2. Verify all migrations round-trip cleanly
3. Build backend code for each sub-feature (5 files each)
4. Build frontend pages
5. Write tests (pytest + Robot Framework)
6. Wire cross-module events (audit integration)

---

## Build Order

IAM has dependencies between sub-features. You must build them in this order — each sub-feature depends on the ones above it.

### Tier 0: Bootstrap (must land before any other IAM sub-feature)

```text
Step 0:  00_bootstrap    — CREATE SCHEMA "02_iam" + shared dim_entity_types,
                           dim_attr_defs, dtl_attrs tables. Schema-only, no
                           backend or frontend code. The migration in this
                           sub-feature runs before any Tier 1 migration
                           because 00_ sorts first.
```

The bootstrap sub-feature exists in every feature. It owns the schema-creation migration that all other sub-features extend. See [01_building_a_feature.md §Phase 2](01_building_a_feature.md#phase-2-bootstrap-sub-feature-and-migration) for the template.

### Tier 1: Core Identity (build after bootstrap — everything below depends on these)

```text
Step 1:  01_org          — organisations (tenants)
Step 2:  02_user         — user accounts
Step 3:  03_workspace    — org-scoped workspaces
Step 4:  04_group        — org-scoped groups
Step 5:  05_org_member   — user ↔ org link
Step 6:  06_group_member — user ↔ group link
Step 7:  07_workspace_member — user ↔ workspace link
```

### Tier 2: Authentication (build after Tier 1)

```text
Step 8:  08_auth         — register, login, JWT tokens, password hashing
Step 9:  19_rbac         — roles, permissions, enforcement
```

### Tier 3: Feature Flags (build after Tier 2)

```text
Step 10: 24_feature_flag — flags, segments, variants, rules, evaluation
Step 11: 25_license_profile — per-org license tiers and entitlements
```

### Tier 4: Security Hardening (build after Tier 2)

```text
Step 12: 33_invitation   — email invitations with magic links
Step 13: 34_mfa          — TOTP + backup codes
Step 14: 35_personal_access_token — long-lived tokens for CLI/scripts
Step 15: 36_api_key      — machine-to-machine API keys with scopes
```

### Tier 5: Advanced (build last)

```text
Step 16+: 09_session, 10_auth_config, 12_oauth2, 13_sso, 14_scim, etc.
         (these are listed in 01_sub_features.md but have no directories yet —
          create them when you get here)
```

---

## Exact Workflow Per Sub-Feature

### Before You Start Each Sub-Feature

Open a GitHub issue using the "Sub-Feature Build" template. Fill in:

```text
Title: "Build: 02_iam / 01_org — Organisations"
Labels: sub-feature, module:iam, P0
```

Fill the **Scope Lock** from the existing `01_scope.md` (or write it if missing).

---

### For Sub-Features WITH Full Docs (01_org, 02_user, 03_workspace, 08_auth)

These already have scope, design, architecture, and API contract docs. Skip straight to implementation.

```text
Issue open ✓
Scope doc exists ✓
Design doc exists ✓
API contract exists ✓
Migration SQL exists ✓

Your workflow:
1. Verify the migration round-trips: UP → DOWN → UP
2. Check cross-module impact (events emitted/consumed)
3. Write pytest tests (RED)
4. Build the 5 backend files (schemas, repository, service, routes)
5. Run tests (GREEN)
6. Build frontend page + components
7. Write Robot Framework API tests
8. Write Robot Framework E2E tests
9. Update sub_feature.manifest.yaml → status: DONE
10. Open PR: "feat: implement 02_iam/01_org — CRUD for organisations"
11. Self-review using 09_maintainer_workflow.md checklist
12. Merge → issue auto-closes
```

**Time estimate per sub-feature:** ~1 focused session (2-4 hours for simple ones like org_member, longer for auth/rbac/feature_flag)

---

### For Sub-Features WITH Partial Docs (04_group, 05_org_member, etc.)

These have a README and migration SQL but no full scope/design/API contract.

```text
Issue open ✓
Migration SQL exists ✓
README exists ✓

Your workflow:
1. Write 01_scope.md (from the README + migration SQL)
2. Write 02_design.md (data model from migration, service functions, API endpoints)
3. Write 05_api_contract.yaml
4. Create sub_feature.manifest.yaml (status: DESIGNED)
5. Open docs PR: "feat(docs): scope and design for 02_iam/04_group"
6. Self-review → merge the docs PR
7. Then follow the implementation steps from above (verify migration → tests → code → PR)
```

---

### For Sub-Features WITH Only Migration SQL (33_invitation, 34_mfa, 35_personal_access_token, 36_api_key)

These have migration SQL but no docs at all.

```text
Issue open ✓
Migration SQL exists ✓

Your workflow:
1. Read the migration SQL carefully — understand the tables
2. Write 01_scope.md
3. Write 02_design.md
4. Write 05_api_contract.yaml
5. Create sub_feature.manifest.yaml (status: DESIGNED)
6. Open docs PR → merge
7. Then follow the implementation steps
```

---

### For Sub-Features WITH No Directory Yet (09_session, 10_auth_config, 12_oauth2, etc.)

These are listed in `01_sub_features.md` but have no directory.

```text
Your workflow:
1. Create the directory: mkdir -p 03_docs/features/02_iam/05_sub_features/{nn}_{name}/09_sql_migrations/{01_migrated,02_in_progress}
2. Write 01_scope.md
3. Write 02_design.md
4. Write the migration SQL
5. Write 05_api_contract.yaml
6. Create sub_feature.manifest.yaml (status: DESIGNED)
7. Verify migration: UP → DOWN → UP
8. Open docs PR → merge
9. Then follow the implementation steps
```

---

## Step-by-Step: Building 01_org (The First Sub-Feature)

Here's exactly what you do on day 1. This is the template for every sub-feature after it.

### Day 1, Part 1: Setup and Docs Verification

```text
1. Open GitHub issue:
   Title: "Build: 02_iam / 01_org — Organisations"
   Template: Sub-Feature Build
   Labels: sub-feature, module:iam, P0

2. Fill the Scope Lock from existing 01_scope.md:
   In scope:
   - [x] Create, update, soft-delete organisations
   - [x] Slug uniqueness across non-deleted orgs
   - [x] EAV attributes: name, slug, settings
   - [x] View v_orgs for read queries
   - [x] Audit events on all mutations

   Out of scope:
   - Membership (05_org_member)
   - Resource ownership (other modules)

   Done when:
   - [x] CRUD API works: POST/GET/PATCH/DELETE /v1/orgs
   - [x] Response envelope on every endpoint
   - [x] Audit events emitted
   - [x] 80%+ test coverage

3. Verify existing docs are complete:
   - 01_scope.md ✓ (exists, reviewed)
   - 02_design.md ✓ (exists, reviewed)
   - 05_api_contract.yaml — CHECK: does it exist?
   - If any doc is missing → write it now
```

### Day 1, Part 2: Migration Verification

```bash
# Verify the bootstrap migration works
uv run python -m scripts.migrate up

# Inspect the tables
docker compose exec postgres psql -U tennetctl -d tennetctl \
  -c '\dt+ "02_iam".*'

# Check specific table structure
docker compose exec postgres psql -U tennetctl -d tennetctl \
  -c '\d+ "02_iam"."11_fct_orgs"'

# Verify the view
docker compose exec postgres psql -U tennetctl -d tennetctl \
  -c '\d+ "02_iam".v_orgs'

# Roll back and re-apply
uv run python -m scripts.migrate down
uv run python -m scripts.migrate up
```

**GATE:** If this fails, fix the migration before writing any code.

### Day 1, Part 3: Backend Scaffold

```bash
# Create the backend module structure
mkdir -p backend/02_features/iam/org
touch backend/02_features/iam/__init__.py
touch backend/02_features/iam/org/__init__.py
touch backend/02_features/iam/org/schemas.py
touch backend/02_features/iam/org/repository.py
touch backend/02_features/iam/org/service.py
touch backend/02_features/iam/org/routes.py
```

### Day 1, Part 4: Write Tests (RED)

```bash
mkdir -p backend/tests/02_iam/01_org
touch backend/tests/02_iam/__init__.py
touch backend/tests/02_iam/01_org/__init__.py
```

Write `backend/tests/02_iam/01_org/test_create_org.py`:

```python
async def test_create_org_success(client, auth_headers):
    """Creating an org with valid data returns 201."""
    response = await client.post("/api/v1/orgs", json={
        "name": "Acme Corp",
        "slug": "acme-corp",
    }, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["ok"] is True
    assert data["data"]["name"] == "Acme Corp"
    assert data["data"]["slug"] == "acme-corp"
```

Write `test_list_orgs.py`, `test_get_org.py`, `test_update_org.py`, `test_delete_org.py`.

Run: `uv run pytest tests/02_iam/01_org/ -v`

**All tests must fail.** This is correct — RED state.

### Day 1, Part 5: Implement Backend

Fill in the 5 files:

**schemas.py:**
```python
from pydantic import BaseModel, Field

class CreateOrgRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(pattern=r'^[a-z0-9-]+$', min_length=2, max_length=50)
    # description, settings are optional EAV attrs

class OrgResponse(BaseModel):
    id: str
    name: str
    slug: str
    status: str
    is_active: bool
    created_at: str
```

**repository.py:**
- `insert_org(conn, org_id, status_id, actor_id)`
- `set_org_attrs(conn, org_id, attrs, actor_id)`
- `get_org_by_id(conn, org_id)` — reads from `v_orgs`
- `get_org_by_slug(conn, slug)`
- `list_orgs(conn, filters)`
- `update_org_attrs(conn, org_id, attrs, actor_id)`
- `soft_delete_org(conn, org_id, actor_id)`

**service.py:**
- `create_org(conn, request, actor_id)` — validate slug uniqueness, insert fct, set attrs, emit event
- `get_org(conn, org_id)` — read from view
- `list_orgs(conn, filters)` — read from view
- `update_org(conn, org_id, request, actor_id)` — update attrs, emit event
- `delete_org(conn, org_id, actor_id)` — soft delete, emit event

**routes.py:**
- `POST /v1/orgs` → 201
- `GET /v1/orgs` → 200 with list
- `GET /v1/orgs/{id}` → 200
- `PATCH /v1/orgs/{id}` → 200
- `DELETE /v1/orgs/{id}` → 204

Run tests: `uv run pytest tests/02_iam/01_org/ -v`

**All tests must pass.** GREEN state.

### Day 1, Part 6: Robot Framework API Tests

```bash
mkdir -p tests/e2e/02_iam
```

Write `tests/e2e/02_iam/01_org_crud.robot`:

```robot
*** Settings ***
Library    RequestsLibrary
Suite Setup    Create Session    api    http://localhost:51734

*** Test Cases ***
Create Organisation
    [Documentation]    POST /v1/orgs creates an org
    ${body}=    Create Dictionary    name=RF Org    slug=rf-org
    ${response}=    POST On Session    api    /api/v1/orgs    json=${body}
    Status Should Be    201    ${response}
    Should Be True    ${response.json()}[ok]

List Organisations
    [Documentation]    GET /v1/orgs returns list
    ${response}=    GET On Session    api    /api/v1/orgs
    Status Should Be    200    ${response}
    Should Be True    ${response.json()}[ok]
```

### Day 1, Part 7: Frontend

```bash
mkdir -p frontend/src/app/iam/orgs/\[id\]
mkdir -p frontend/src/features/iam/orgs/{components,hooks}
```

Build:
- `page.tsx` — list view using TanStack Query
- `[id]/page.tsx` — detail view
- `components/OrgList.tsx`, `OrgForm.tsx`, `OrgDetail.tsx`
- `hooks/useOrgs.ts` — query + mutation hooks

### Day 1, Part 8: Ship

```text
1. Update sub_feature.manifest.yaml:
   status: DONE
   completed_at: "2026-04-06"

2. Update feature.manifest.yaml:
   sub_features[0].status: DONE

3. Open PR:
   Title: "feat: implement 02_iam/01_org — organisation CRUD"
   Body: Use the PR template from 01_building_a_feature.md
   Include: "Closes #issue_number"

4. Self-review:
   - Wait 30 minutes
   - Read the diff on GitHub
   - Walk the full checklist from 09_maintainer_workflow.md
   - Run code-reviewer agent

5. Merge → issue auto-closes

6. Check off 01_org in the module parent issue
```

### Day 2: Next Sub-Feature

Move to `02_user`. Open a new issue. Repeat the exact same cycle.

---

## The Rhythm

```text
Every sub-feature, every time:

Morning:
  1. Open issue (fill Scope Lock)
  2. Verify/write docs (scope, design, API contract)
  3. Verify migration (UP → DOWN → UP)

Build:
  4. Write tests (RED)
  5. Implement backend (GREEN)
  6. Write Robot Framework tests
  7. Implement frontend

Ship:
  8. Update manifest
  9. Open PR
  10. Self-review
  11. Merge
  12. Move to next sub-feature
```

**One sub-feature per session. Do not start the next one until the current one is merged.**

---

## Doc Completeness Checklist

Before implementing any sub-feature, verify these docs exist:

| Sub-Feature | scope | design | contract | migration | manifest |
| ----------- | ----- | ------ | -------- | --------- | -------- |
| 00_bootstrap | ✅ | ✅ | n/a | ✅ (1 file) | ✅ |
| 01_org | ✅ | ✅ | check | ✅ (4 files) | ✅ |
| 02_user | ✅ | ✅ | check | ✅ | ✅ |
| 03_workspace | ✅ | ✅ | ✅ | ✅ | ✅ |
| 08_auth | ✅ | ✅ | check | ✅ (3 files) | ✅ |
| 04_group | ❌ README only | ❌ | ❌ | ✅ | ❌ |
| 05_org_member | ❌ README only | ❌ | ❌ | ✅ | ❌ |
| 06_group_member | ❌ README only | ❌ | ❌ | ✅ | ❌ |
| 07_workspace_member | ❌ README only | ❌ | ❌ | ✅ | ❌ |
| 19_rbac | ❌ README only | ❌ | ❌ | ✅ | ❌ |
| 24_feature_flag | ✅ | ❌ | ❌ | ✅ (4 files) | ❌ |
| 25_license_profile | ❌ README only | ❌ | ❌ | ✅ | ❌ |
| 33_invitation | ❌ | ❌ | ❌ | ✅ (2 files) | ❌ |
| 34_mfa | ❌ | ❌ | ❌ | ✅ | ❌ |
| 35_personal_access_token | ❌ | ❌ | ❌ | ✅ | ❌ |
| 36_api_key | ❌ | ❌ | ❌ | ✅ | ❌ |

**Action:** Before each sub-feature build, fill in the missing ❌ cells. This is your docs PR.

---

## Scope Creep Traps Specific to IAM

These are the things that WILL tempt you. Log them and move on.

| Trap | While building | What to do |
| ---- | -------------- | ---------- |
| "Let me add email verification to users" | 02_user | Separate enhancement issue. User CRUD comes first. |
| "Auth should also handle OAuth2" | 08_auth | OAuth2 is sub-feature 12. Email/password first. |
| "Groups should have nested groups" | 04_group | Out of scope. Log it. Flat groups first. |
| "RBAC should have resource-level permissions" | 19_rbac | Enhancement. Role-based first. Resource-level later. |
| "Feature flags need a UI evaluation playground" | 24_feature_flag | Enhancement. Backend evaluation engine first. |
| "Invitations should support bulk import" | 33_invitation | That's sub-feature 38_user_import. Single invite first. |
| "MFA should support passkeys" | 34_mfa | TOTP first. Passkeys are a separate sub-feature. |
| "API keys should have rate limiting" | 36_api_key | Enhancement. Key CRUD + auth first. Rate limiting later. |

---

## GitHub Setup (Do This Once Before Starting)

### Create Labels

```bash
# Module labels
gh label create "module:iam" --color "0075ca" --description "IAM module"
gh label create "module:audit" --color "0075ca" --description "Audit module"
gh label create "module:vault" --color "0075ca" --description "Vault module"

# Type labels
gh label create "sub-feature" --color "a2eeef" --description "Sub-feature build"
gh label create "enhancement" --color "a2eeef" --description "Enhancement to existing sub-feature"

# Priority labels
gh label create "P0" --color "d73a4a" --description "Critical — blocking other work"
gh label create "P1" --color "e4e669" --description "Important — needed soon"
gh label create "P2" --color "0e8a16" --description "Nice to have — do when time allows"

# Tier labels (for build order)
gh label create "tier:1-core" --color "fbca04" --description "Core identity sub-features"
gh label create "tier:2-auth" --color "fbca04" --description "Authentication sub-features"
gh label create "tier:3-flags" --color "fbca04" --description "Feature flag sub-features"
gh label create "tier:4-security" --color "fbca04" --description "Security hardening sub-features"
```

### Open the Module Parent Issue

```bash
gh issue create \
  --title "Module: 02_iam — Identity & Access Management" \
  --label "module:iam,P0" \
  --body "$(cat <<'EOF'
## Module: 02_iam — Identity & Access Management

### Build Order

#### Tier 1: Core Identity
- [ ] #__ — 01_org: Organisation CRUD
- [ ] #__ — 02_user: User account CRUD
- [ ] #__ — 03_workspace: Workspace CRUD
- [ ] #__ — 04_group: Group CRUD
- [ ] #__ — 05_org_member: User ↔ org membership
- [ ] #__ — 06_group_member: User ↔ group membership
- [ ] #__ — 07_workspace_member: User ↔ workspace membership

#### Tier 2: Authentication
- [ ] #__ — 08_auth: Register, login, JWT tokens
- [ ] #__ — 19_rbac: Roles, permissions, enforcement

#### Tier 3: Feature Flags
- [ ] #__ — 24_feature_flag: Flags, segments, variants, evaluation
- [ ] #__ — 25_license_profile: Per-org license tiers

#### Tier 4: Security Hardening
- [ ] #__ — 33_invitation: Email invitations
- [ ] #__ — 34_mfa: TOTP + backup codes
- [ ] #__ — 35_personal_access_token: Long-lived tokens
- [ ] #__ — 36_api_key: Machine-to-machine keys

### Dependencies
- Depends on: 01_foundation (core infra)
- Depended on by: Everything (all modules need auth)
EOF
)"
```

Then open one issue per sub-feature using the "Sub-Feature Build" template. Update the parent issue with the issue numbers.

---

## Summary: Your First Week

```text
Day 0 (setup):
  - Create GitHub labels
  - Open module parent issue
  - Open issue for 01_org

Day 1:
  - 01_org: verify docs → verify migration → write tests → implement → ship

Day 2:
  - 02_user: write missing docs → verify migration → write tests → implement → ship

Day 3:
  - 03_workspace: same cycle
  - 04_group: write scope + design docs first → docs PR → then implement

Day 4:
  - 05_org_member: write docs → implement
  - 06_group_member: write docs → implement (these are small lnk_ sub-features)

Day 5:
  - 07_workspace_member: write docs → implement
  - Review the week: all Tier 1 done? Update parent issue.

Week 2:
  - 08_auth → 19_rbac (Tier 2)

Week 3:
  - 24_feature_flag → 25_license_profile (Tier 3)

Week 4:
  - 33_invitation → 34_mfa → 35_personal_access_token → 36_api_key (Tier 4)
```

This is the plan. One sub-feature at a time. No jumping ahead. No scope creep.
