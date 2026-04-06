# Day One Workflow

How to build a clean, well-structured tennetctl module from the very first line. This document walks through the entire lifecycle — from empty directory to merged PR — using a real example.

This is the workflow you follow every time. Whether it's your first module or your eighth.

---

## The Lifecycle

```text
Phase 0: Prepare       — Understand what you're building, check roadmap, open issue
Phase 1: Foundation    — Create module scaffold, bootstrap schema, write feature manifest
Phase 2: Sub-Features  — Build each sub-feature one at a time (scope → design → schema → tests → code)
Phase 3: Integration   — Cross-module events, E2E tests, frontend pages
Phase 4: Ship          — Self-review, merge, update roadmap
```

We'll walk through each phase using **Vault** (module 07) as the example.

---

## Phase 0: Prepare

### 0.1 Read Before Building

Before writing a single file, read these docs cover to cover:

| Doc | Why |
| --- | --- |
| [01_vision.md](../03_docs/00_main/01_vision.md) | Does this module belong in tennetctl? |
| [02_ethos.md](../03_docs/00_main/02_ethos.md) | Does the approach match the principles? |
| [03_rules.md](../03_docs/00_main/03_rules.md) | Which rules apply to this module? (All of them.) |
| [04_roadmap.md](../03_docs/00_main/04_roadmap.md) | What phase is this? What comes before and after? |
| [03_database_structure.md](03_database_structure.md) | The EAV pattern you must follow |
| [05_backend_api_standards.md](05_backend_api_standards.md) | The 5-file backend structure |

### 0.2 Define the Module

Answer these questions in writing before creating any directories:

```text
1. What does this module do? (2-3 sentences)
2. What does it NOT do? (explicit boundaries)
3. What other modules does it depend on? (events it consumes)
4. What events does it emit? (events other modules consume)
5. How many sub-features does it have? (list them)
6. What is the build order? (which sub-feature first, second, etc.)
```

### 0.3 Open a Tracking Issue

Use the "Sub-Feature Build" issue template for each sub-feature. But first, create a **parent issue** for the module itself:

```markdown
## Module: 07_vault — Secrets Management

### Overview
{2-3 sentences from step 0.2}

### Sub-features (build order)
- [ ] #101 — 01_project: vault projects (containers for secrets)
- [ ] #102 — 02_environment: env configs per project (dev/staging/prod)
- [ ] #103 — 03_secret: encrypted secret storage with envelope encryption
- [ ] #104 — 04_version: secret versioning and history
- [ ] #105 — 05_rotation: automated secret rotation policies
- [ ] #106 — 06_access: access policies and audit

### Dependencies
- Depends on: IAM (auth, org membership, RBAC)
- Depended on by: Monitoring (for API key storage), LLM Ops (for provider keys)
```

Label it: `module`, `module:vault`, `P0`

Then open one issue per sub-feature using the "Sub-Feature Build" template.

---

## Phase 1: Foundation

### 1.1 Create the Documentation Scaffold

```bash
# Feature docs
mkdir -p 03_docs/features/07_vault/{04_architecture,05_sub_features,09_sql_migrations/{01_migrated,02_in_progress}}
```

### 1.2 Write the Feature Manifest

Create `03_docs/features/07_vault/feature.manifest.yaml`:

```yaml
title: "Vault — Secrets Management"
module: "07_vault"
schema: "07_vault"
status: BUILDING
priority: high
created_at: "2026-04-06"

sub_features:
  - number: 01
    name: project
    status: PLANNED
    description: Vault projects — containers that group secrets by application or service.

  - number: 02
    name: environment
    status: PLANNED
    description: Environment configs per project (dev, staging, prod).

  - number: 03
    name: secret
    status: PLANNED
    description: Encrypted secret storage with AES-256-GCM envelope encryption.

  - number: 04
    name: version
    status: PLANNED
    description: Secret versioning — every update creates a new version.

  - number: 05
    name: rotation
    status: PLANNED
    description: Automated rotation policies with pluggable backends.

  - number: 06
    name: access
    status: PLANNED
    description: Access policies — who can read/write which secrets.

migrations: []
frontend_pages: []
```

### 1.3 Write the Feature Overview

Create `03_docs/features/07_vault/00_overview.md`:

```markdown
# Vault — Secrets Management

## What is this feature?

Vault is tennetctl's secrets manager. Applications fetch secrets at runtime
instead of storing them in environment files, CI variables, or code.

## Why it exists

Every SaaS product needs secrets (API keys, database passwords, certificates).
Most teams scatter them across .env files, CI/CD variables, and cloud secret
managers. Vault centralises them with encryption, versioning, rotation, and audit.

## Scope boundaries

**In scope:**
- Project-based secret organisation
- AES-256-GCM envelope encryption at rest
- Secret versioning with rollback
- Automated rotation policies
- Access policies per project/environment
- Audit events on every access

**Out of scope:**
- HSM integration (future)
- Certificate lifecycle management (future)
- Dynamic secrets (future)

## Sub-features

See feature.manifest.yaml for the full list and build order.
```

### 1.4 Write the Architecture Doc

Create `03_docs/features/07_vault/04_architecture/01_architecture.md`:

Document:
- How envelope encryption works (master key → data key → ciphertext)
- How secrets are stored (fct + dtl pattern)
- How access is controlled (integration with IAM RBAC)
- What events are emitted and consumed

### 1.5 Write the Bootstrap Migration

This is the first migration for the module. It creates the schema and the shared dim/dtl tables that all sub-features will use.

Create `03_docs/features/07_vault/09_sql_migrations/02_in_progress/YYYYMMDD_NNN_vault_bootstrap.sql`:

```sql
-- =============================================================================
-- Migration: YYYYMMDD_NNN_vault_bootstrap.sql
-- Module:    07_vault
-- Description: Bootstrap the vault schema with shared dim and dtl tables
-- =============================================================================

-- UP =========================================================================

CREATE SCHEMA IF NOT EXISTS "07_vault";

-- Shared entity types for this module
CREATE TABLE "07_vault".06_dim_entity_types (
    id            SMALLINT NOT NULL,
    code          TEXT     NOT NULL,
    label         TEXT     NOT NULL,
    description   TEXT     NOT NULL DEFAULT '',
    deprecated_at TIMESTAMP,

    CONSTRAINT pk_dim_entity_types      PRIMARY KEY (id),
    CONSTRAINT uq_dim_entity_types_code UNIQUE (code)
);

COMMENT ON TABLE "07_vault".06_dim_entity_types IS
    'Entity types managed by the vault module. Used by dtl_attrs for EAV.';

INSERT INTO "07_vault".06_dim_entity_types (id, code, label, description) VALUES
    (1, 'project',     'Project',     'Vault project — a container for secrets'),
    (2, 'secret',      'Secret',      'An encrypted secret (key-value pair)'),
    (3, 'rotation',    'Rotation',    'A rotation policy for a secret');

-- Shared attribute definitions
CREATE TABLE "07_vault".07_dim_attr_defs (
    id              SMALLINT NOT NULL,
    entity_type_id  SMALLINT NOT NULL,
    code            TEXT     NOT NULL,
    label           TEXT     NOT NULL,
    value_type      TEXT     NOT NULL DEFAULT 'text',
    is_required     BOOLEAN  NOT NULL DEFAULT FALSE,
    is_unique       BOOLEAN  NOT NULL DEFAULT FALSE,
    description     TEXT     NOT NULL DEFAULT '',

    CONSTRAINT pk_dim_attr_defs            PRIMARY KEY (id),
    CONSTRAINT uq_dim_attr_defs_code       UNIQUE (entity_type_id, code),
    CONSTRAINT fk_dim_attr_defs_entity     FOREIGN KEY (entity_type_id)
        REFERENCES "07_vault".06_dim_entity_types(id),
    CONSTRAINT chk_dim_attr_defs_value_type CHECK (
        value_type IN ('text', 'jsonb')
    )
);

COMMENT ON TABLE "07_vault".07_dim_attr_defs IS
    'Attribute definitions for vault EAV. Every property must be registered here.';

-- Seed initial attribute definitions
INSERT INTO "07_vault".07_dim_attr_defs
    (id, entity_type_id, code, label, value_type, is_required, is_unique, description)
VALUES
    (1, 1, 'name',        'Name',        'text',  true,  false, 'Project display name.'),
    (2, 1, 'slug',        'Slug',        'text',  true,  true,  'URL-safe project identifier.'),
    (3, 1, 'description', 'Description', 'text',  false, false, 'Project description.');

-- Shared EAV attributes table
CREATE TABLE "07_vault".20_dtl_attrs (
    entity_type_id  SMALLINT    NOT NULL,
    entity_id       VARCHAR(36) NOT NULL,
    attr_def_id     SMALLINT    NOT NULL,
    key_text        TEXT,
    key_jsonb       TEXT,
    created_by      VARCHAR(36),
    updated_by      VARCHAR(36),
    created_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_dtl_attrs            PRIMARY KEY (entity_type_id, entity_id, attr_def_id),
    CONSTRAINT fk_dtl_attrs_entity     FOREIGN KEY (entity_type_id)
        REFERENCES "07_vault".06_dim_entity_types(id),
    CONSTRAINT fk_dtl_attrs_attr       FOREIGN KEY (attr_def_id)
        REFERENCES "07_vault".07_dim_attr_defs(id),
    CONSTRAINT chk_dtl_attrs_one_value CHECK (
        (key_text IS NOT NULL AND key_jsonb IS NULL) OR
        (key_jsonb IS NOT NULL AND key_text IS NULL)
    )
);

CREATE INDEX idx_dtl_attrs_entity ON "07_vault".20_dtl_attrs (entity_type_id, entity_id);

COMMENT ON TABLE "07_vault".20_dtl_attrs IS
    'EAV attribute values for all vault entities. One row per attribute per entity.';
COMMENT ON COLUMN "07_vault".20_dtl_attrs.key_text IS
    'Simple string value. Exactly one of key_text or key_jsonb must be set.';
COMMENT ON COLUMN "07_vault".20_dtl_attrs.key_jsonb IS
    'Structured JSON value stored as TEXT for portability. Parse in application.';

-- DOWN =======================================================================

DROP TABLE IF EXISTS "07_vault".20_dtl_attrs;
DROP TABLE IF EXISTS "07_vault".07_dim_attr_defs;
DROP TABLE IF EXISTS "07_vault".06_dim_entity_types;
DROP SCHEMA IF EXISTS "07_vault";
```

### 1.6 Verify the Bootstrap Migration

```bash
uv run python -m scripts.migrate up
docker compose exec postgres psql -U tennetctl -d tennetctl \
  -c '\dt+ "07_vault".*'
uv run python -m scripts.migrate down
uv run python -m scripts.migrate up
```

**GATE:** UP → DOWN → UP must round-trip cleanly.

### 1.7 Create the Backend Scaffold

```bash
# Backend module
mkdir -p backend/02_features/vault
touch backend/02_features/vault/__init__.py
```

### 1.8 Create the Frontend Scaffold

```bash
mkdir -p frontend/src/app/vault
```

### 1.9 Open the Foundation PR

```text
feat(docs): scaffold vault module — schema, manifests, architecture

Contains:
- 03_docs/features/07_vault/ (overview, architecture, manifest)
- Bootstrap migration (schema + shared dim/dtl tables)
- Backend/frontend directory scaffold

This is a docs-first PR. No implementation yet.
```

Merge this. Now you have a clean foundation to build sub-features on.

---

## Phase 2: Sub-Features (One at a Time)

This is where scope creep happens. The discipline is: **one sub-feature at a time, fully complete, before starting the next.**

### The Sub-Feature Build Cycle

For EACH sub-feature, follow this exact cycle:

```text
┌─────────────────────────────────────────────────┐
│                                                 │
│  1. OPEN ISSUE (Scope Lock)                     │
│     └─ Define in-scope, out-of-scope, done-when │
│                                                 │
│  2. DOCS PR (merge before coding)               │
│     ├─ 01_scope.md                              │
│     ├─ 02_design.md                             │
│     ├─ 05_api_contract.yaml                     │
│     ├─ Migration SQL                            │
│     └─ sub_feature.manifest.yaml (DESIGNED)     │
│                                                 │
│  3. IMPLEMENTATION PR                           │
│     ├─ Tests first (RED)                        │
│     ├─ Backend: schemas → repo → service → routes│
│     ├─ Frontend: page → components → hooks      │
│     ├─ Robot Framework API + E2E tests          │
│     └─ sub_feature.manifest.yaml (DONE)         │
│                                                 │
│  4. CLOSE ISSUE                                 │
│     └─ PR auto-closes issue via "Closes #N"     │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Example: Building Sub-Feature 01_project

#### Step 1: Open the Issue

Use the "Sub-Feature Build" template. Fill in:

```markdown
## Sub-Feature: 07_vault / 01_project

### Scope Lock

#### In scope
- [x] Create vault projects (org-scoped)
- [x] List/get/update/soft-delete projects
- [x] EAV attributes: name, slug, description
- [x] View: v_projects (resolves status, materialises attributes)

#### Explicitly out of scope
- Secrets (that's sub-feature 03_secret)
- Environments (that's sub-feature 02_environment)
- Access policies (that's sub-feature 06_access)
- Anything to do with encryption

#### Done when
- [x] CRUD API works: POST/GET/PATCH/DELETE /v1/vault/projects
- [x] Response envelope on every endpoint
- [x] Audit events emitted on create/update/delete
- [x] pytest coverage at 80%+
- [x] Robot Framework API tests pass
```

#### Step 2: Write the Scope Doc

Create `03_docs/features/07_vault/05_sub_features/01_project/01_scope.md`:

```markdown
# Vault Projects — Scope

## What it does

A vault project is a container that groups secrets by application or service.
Each project belongs to an org and can have multiple environments (dev, staging,
prod). Projects are the top-level organising unit in Vault.

## In scope

- Create, read, update, soft-delete vault projects
- Each project belongs to one org (org_id)
- EAV attributes: name, slug, description
- Slug uniqueness within an org
- View v_projects for read queries

## Out of scope

- Environments within projects (02_environment)
- Secrets within projects (03_secret)
- Access policies for projects (06_access)
- Encryption of any kind (handled at the secret level)

## Acceptance criteria

- [ ] POST /v1/vault/projects creates a project
- [ ] GET /v1/vault/projects lists projects for the caller's org
- [ ] GET /v1/vault/projects/{id} returns a single project
- [ ] PATCH /v1/vault/projects/{id} updates name/slug/description
- [ ] DELETE /v1/vault/projects/{id} soft-deletes
- [ ] Duplicate slug within same org returns 409
- [ ] All responses use the response envelope
- [ ] Audit events emitted for create, update, delete

## Dependencies

- Depends on: IAM (org membership, auth middleware)
- Depended on by: 02_environment, 03_secret, 06_access
```

#### Step 3: Write the Design Doc

Create `02_design.md`:

```markdown
# Vault Projects — Design

## Data Model

### Tables

**10_fct_projects** — project identity
- id (VARCHAR(36), UUID v7)
- org_id (VARCHAR(36), FK to 02_iam fct_orgs — not enforced)
- status_id (SMALLINT, FK to dim_project_statuses)
- Standard audit columns

**01_dim_project_statuses** — status codes
- 1: active
- 2: archived

### EAV Attributes (via 07_dim_attr_defs + 20_dtl_attrs)
- name (text, required)
- slug (text, required, unique per org)
- description (text, optional)

### View: v_projects
- Resolves status_id → status code
- Materialises name, slug, description from dtl_attrs
- Filters deleted_at IS NULL

## Service Layer

- create_project(conn, request, actor_id) → dict
  - Validates slug uniqueness within org
  - Creates fct_projects row
  - Stores attributes in dtl_attrs
  - Emits vault.project.created

- get_project(conn, project_id) → dict
  - Reads from v_projects

- update_project(conn, project_id, request, actor_id) → dict
  - Updates dtl_attrs
  - Emits vault.project.updated

- delete_project(conn, project_id, actor_id) → None
  - Soft-deletes fct_projects
  - Emits vault.project.deleted

## API Layer

- POST   /v1/vault/projects
- GET    /v1/vault/projects
- GET    /v1/vault/projects/{id}
- PATCH  /v1/vault/projects/{id}
- DELETE /v1/vault/projects/{id}

## Security

- All endpoints require auth
- Org-scoped: user can only see their org's projects
- Audit events on every mutation
- RLS on fct_projects (org_id)
```

#### Step 4: Write the Migration

Create `YYYYMMDD_NNN_vault_projects.sql` in `09_sql_migrations/02_in_progress/`.

Follow the exact templates from [03_database_structure.md](03_database_structure.md).

#### Step 5: Write the API Contract

Create `05_api_contract.yaml` with OpenAPI fragments.

#### Step 6: Open the Docs PR

```text
feat(docs): scope and design for vault/01_project

Closes #101 (partial — docs phase only)

Contains:
- 01_scope.md
- 02_design.md
- 05_api_contract.yaml
- Migration SQL
- sub_feature.manifest.yaml (status: DESIGNED)
```

Self-review. Merge.

#### Step 7: Write Tests (RED)

```python
# backend/tests/07_vault/01_project/test_create_project.py

async def test_create_project_success(client, seeded_org, auth_headers):
    """Creating a vault project returns 201 with project data."""
    response = await client.post("/api/v1/vault/projects", json={
        "name": "My API",
        "slug": "my-api",
    }, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["ok"] is True
    assert data["data"]["name"] == "My API"
    assert data["data"]["slug"] == "my-api"

async def test_create_project_duplicate_slug(client, seeded_project, auth_headers):
    """Duplicate slug within same org returns 409."""
    response = await client.post("/api/v1/vault/projects", json={
        "name": "Another",
        "slug": seeded_project["slug"],
    }, headers=auth_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SLUG_EXISTS"

async def test_list_projects_excludes_other_org(client, seeded_project, other_org_headers):
    """Projects from another org are not visible."""
    response = await client.get("/api/v1/vault/projects", headers=other_org_headers)
    assert response.status_code == 200
    assert len(response.json()["data"]) == 0

async def test_delete_project_soft_deletes(client, seeded_project, auth_headers):
    """DELETE soft-deletes, returns 204, project no longer in list."""
    pid = seeded_project["id"]
    response = await client.delete(f"/api/v1/vault/projects/{pid}", headers=auth_headers)
    assert response.status_code == 204

    response = await client.get(f"/api/v1/vault/projects/{pid}", headers=auth_headers)
    assert response.status_code == 404
```

Run tests. They fail. Good — RED state.

#### Step 8: Implement Backend

Create the 5 files:

```text
backend/02_features/vault/project/
├── __init__.py
├── schemas.py        # CreateProjectRequest, ProjectResponse
├── repository.py     # insert_project, get_project_by_id, etc.
├── service.py        # create_project, check slug uniqueness, emit events
└── routes.py         # 5 endpoints, response envelope
```

Run tests. They pass. GREEN state.

#### Step 9: Implement Frontend

```text
frontend/src/app/vault/projects/
├── page.tsx              # List view
├── [id]/page.tsx         # Detail view
└── components/
    ├── ProjectList.tsx
    ├── ProjectForm.tsx
    └── ProjectDetail.tsx
```

#### Step 10: Robot Framework Tests

```robot
# tests/e2e/07_vault/01_create_project.robot

*** Test Cases ***
Create Vault Project Successfully
    [Documentation]    POST /v1/vault/projects creates a project
    ${body}=    Create Dictionary    name=RF Project    slug=rf-project
    ${response}=    POST On Session    api    /api/v1/vault/projects    json=${body}
    Status Should Be    201    ${response}
    Should Be True    ${response.json()}[ok]
```

#### Step 11: Update Manifest and Open Implementation PR

Update `sub_feature.manifest.yaml`:

```yaml
status: DONE
completed_at: "2026-04-06"
```

Open the implementation PR:

```text
feat: implement vault/01_project — CRUD for vault projects

Closes #101

## Database changes
- New dim: 01_dim_project_statuses (active, archived)
- New fct: 10_fct_projects
- New attr_defs: name, slug, description
- New view: v_projects

## Rollback plan
- Migration DOWN drops all vault project tables
- No data migration needed (new tables only)
```

Self-review. Merge. Issue auto-closes.

#### Step 12: Move to the Next Sub-Feature

Update `feature.manifest.yaml`:

```yaml
sub_features:
  - number: 01
    name: project
    status: DONE        # ← updated
```

Open the next issue (02_environment). Repeat the cycle.

---

## Phase 3: Integration

After all sub-features are built, do one final integration pass:

### 3.1 Cross-Module Event Wiring

Verify that events emitted by this module are consumed correctly:

```python
# Does IAM receive vault.project.created?
# Does Audit log vault.secret.accessed?
```

### 3.2 End-to-End Workflow Tests

Write Robot Framework tests that cover the full user journey:

```robot
*** Test Cases ***
Complete Vault Workflow
    [Documentation]    Create project → add environment → store secret → read secret
    # Step 1: Create project
    # Step 2: Create environment
    # Step 3: Store a secret
    # Step 4: Read the secret back
    # Step 5: Rotate the secret
    # Step 6: Verify old version still accessible
```

### 3.3 Frontend Navigation

Verify the full navigation flow works:

```text
Dashboard → Vault → Projects → Create → Detail → Secrets → Create → Done
```

### 3.4 Integration PR

```text
feat: vault integration — cross-module events and E2E tests

Contains:
- Event consumer registrations
- E2E workflow tests
- Frontend navigation wiring
- feature.manifest.yaml (status: DONE)
```

---

## Phase 4: Ship

### 4.1 Update the Roadmap

In `03_docs/00_main/04_roadmap.md`, change the module status:

```text
| 07 | Vault | DONE | Secrets management and rotation |
```

### 4.2 Update the Feature Manifest

```yaml
status: DONE
```

### 4.3 Move Migrations

Move all migration files from `09_sql_migrations/02_in_progress/` to `01_migrated/`.

### 4.4 Final Self-Review

Walk the full checklist from [09_maintainer_workflow.md](09_maintainer_workflow.md).

---

## Anti-Patterns to Avoid

### 1. Building Multiple Sub-Features Simultaneously

```text
WRONG:
  Start 01_project → halfway through, start 02_environment →
  realise project needs a field for environments →
  go back to project → now environment is half-done too

RIGHT:
  Finish 01_project completely → merge → start 02_environment
```

### 2. Expanding Scope Mid-Build

```text
WRONG:
  Building 01_project → "oh, I should add encryption here" →
  now you're building half of 03_secret inside 01_project

RIGHT:
  Building 01_project → log "needs encryption" in Scope Creep Log →
  open issue for 03_secret → finish project without encryption
```

### 3. Skipping the Docs PR

```text
WRONG:
  Jump straight to coding → discover design problems at line 300 →
  rewrite everything → waste a day

RIGHT:
  Write scope + design docs → review them → catch problems in prose →
  implement with confidence
```

### 4. Mixing Feature and Enhancement Work

```text
WRONG:
  Building 03_secret → "while I'm here, let me fix the org list sorting" →
  now the PR has vault AND IAM changes

RIGHT:
  Log the IAM fix in Scope Creep Log → open separate issue → stay on vault
```

### 5. Not Verifying Migrations

```text
WRONG:
  Write CREATE TABLE → commit → discover it fails in CI

RIGHT:
  Write CREATE TABLE → run UP locally → run DOWN → run UP again → commit
```

---

## Quick Reference: File Checklist for a New Module

```text
03_docs/features/{nn}_{module}/
├── 00_overview.md                          ✓ Phase 1
├── feature.manifest.yaml                   ✓ Phase 1
├── 04_architecture/
│   └── 01_architecture.md                  ✓ Phase 1
├── 05_sub_features/
│   └── {nn}_{sub}/
│       ├── 01_scope.md                     ✓ Phase 2 (per sub-feature)
│       ├── 02_design.md                    ✓ Phase 2
│       ├── 05_api_contract.yaml            ✓ Phase 2
│       ├── 08_worklog.md                   ✓ Phase 2 (enhancements)
│       └── sub_feature.manifest.yaml       ✓ Phase 2
└── 09_sql_migrations/
    ├── 01_migrated/                        ✓ Phase 4
    └── 02_in_progress/
        └── YYYYMMDD_NNN_description.sql    ✓ Phase 1 + 2

backend/02_features/{module}/{sub_feature}/
├── __init__.py                             ✓ Phase 2
├── schemas.py                              ✓ Phase 2
├── repository.py                           ✓ Phase 2
├── service.py                              ✓ Phase 2
└── routes.py                               ✓ Phase 2

backend/tests/{module}/{sub_feature}/
└── test_{description}.py                   ✓ Phase 2

tests/e2e/{module}/
└── {nn}_{description}.robot                ✓ Phase 2 + 3

frontend/src/app/{module}/{sub-feature}/
├── page.tsx                                ✓ Phase 2
└── components/                             ✓ Phase 2

GitHub Issues:
├── Module parent issue                     ✓ Phase 0
└── Sub-feature issues (one per)            ✓ Phase 2
```

---

## Summary: The Rhythm

```text
For each module:
  Phase 0: One parent issue listing all sub-features
  Phase 1: One PR — scaffold + bootstrap migration + manifests
  Phase 2: Two PRs per sub-feature — docs PR then implementation PR
  Phase 3: One PR — integration tests + event wiring
  Phase 4: One PR — roadmap update + migration cleanup

For each sub-feature:
  Open issue → fill Scope Lock → docs PR → implementation PR → close issue

For scope creep:
  Log it → open new issue → continue current work
```

This is the rhythm. Follow it every time and the project stays clean.
