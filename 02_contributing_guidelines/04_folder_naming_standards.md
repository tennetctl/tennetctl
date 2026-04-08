# Folder and File Naming Standards

Every folder and file in tennetctl uses numbered prefixes. This is not optional — it enforces reading order and prevents naming collisions across contributors.

---

## The Rule

```
{nn}_{name}/        — folders
{nn}_{name}.md      — docs
{nn}_{name}.py      — code
```

Where `{nn}` is a two-digit number that determines sort order.

---

## Top-Level Repository Structure

```
tennetctl/
├── 01_core/                    # Shared infrastructure (config, exceptions, encryption)
├── 02_features/                # Feature modules (backend)
│   ├── 02_iam/
│   ├── 03_audit/
│   ├── 04_monitoring/
│   ├── 05_notify/
│   ├── 06_ops/
│   ├── 07_vault/
│   └── 08_llmops/
├── 03_docs/                    # All documentation
│   ├── 00_main/                # Project-level docs
│   │   ├── 01_vision.md
│   │   ├── 02_ethos.md
│   │   ├── 03_rules.md
│   │   ├── 04_roadmap.md
│   │   ├── 05_contributing.md
│   │   ├── 06_setup.md
│   │   ├── 07_adding_a_feature.md
│   │   └── 08_decisions/       # Architecture Decision Records
│   └── features/               # Per-feature documentation
│       ├── 02_iam/
│       ├── 90_audit/
│       └── ...
├── 04_contributing_guidelines/ # This folder — contributor guides
├── frontend/                   # Next.js frontend
├── backend/                    # FastAPI backend
└── tests/                      # Test suites
```

---

## Feature Documentation Structure

Every feature follows the same directory layout:

```
03_docs/features/{nn}_{feature}/
├── 00_overview.md              # What this feature does
├── 01_sub_features.md          # List of all sub-features
├── 04_architecture/            # Architecture docs
│   ├── 01_architecture.md
│   └── 02_workflows.md
├── 05_sub_features/            # One folder per sub-feature
│   ├── 00_bootstrap/           # Special: schema + shared dim/dtl tables
│   │   ├── 01_scope.md
│   │   ├── 02_design.md
│   │   ├── sub_feature.manifest.yaml
│   │   └── 09_sql_migrations/
│   │       ├── 01_migrated/
│   │       └── 02_in_progress/
│   │           └── YYYYMMDD_NNN_{feature}_bootstrap.sql
│   ├── {nn}_{sub_feature}/
│   │   ├── 01_scope.md
│   │   ├── 02_design.md
│   │   ├── 03_architecture.md
│   │   ├── 04_user_guide.md
│   │   ├── 05_api_contract.yaml
│   │   ├── 06_user_flows.md
│   │   ├── 07_decisions.md
│   │   ├── 08_worklog.md
│   │   ├── sub_feature.manifest.yaml
│   │   └── 09_sql_migrations/
│   │       ├── 01_migrated/    # Applied migrations
│   │       └── 02_in_progress/ # Pending migrations
│   └── ...
└── feature.manifest.yaml
```

Migration files live inside the **sub-feature** that owns them, never at the feature level. The migration runner walks `03_docs/features/*/05_sub_features/*/09_sql_migrations/02_in_progress/` and applies files in global `{NNN}` sequence order. The `00_bootstrap/` sub-feature exists in every feature and owns the schema-creation migration — it sorts first naturally because of its `00_` prefix, so no special-casing in the runner.

### Bootstrap sub-feature minimum file set

The `00_bootstrap/` sub-feature is special — it only needs three files:

- `sub_feature.manifest.yaml` — status is always `DONE`
- `01_scope.md` — describes the schema and shared tables being created
- `09_sql_migrations/02_in_progress/YYYYMMDD_{NNN}_{feature}_bootstrap.sql` — the schema creation

It does **not** need `02_design.md`, `05_api_contract.yaml`, `06_user_flows.md`, `07_decisions.md`, or `08_worklog.md`. The bootstrap migration is infrastructure, not a feature.

---

## Manifest Schema

Two manifests exist in every feature, both in YAML:

### `feature.manifest.yaml` (at feature root)

```yaml
title: "IAM"
feature: "02_iam"
status: "ACTIVE"        # PLANNED | ACTIVE | FROZEN | ARCHIVED
owner: "your-github-username"
created_at: "2026-04-01"
description: |
  Organisations, users, groups, roles, and access control.
sub_features:
  - number: 0
    name: bootstrap
    status: DONE
    completed_at: "2026-04-07"
  - number: 1
    name: org
    status: DONE
    completed_at: "2026-04-08"
  - number: 2
    name: user
    status: BUILDING
  - number: 3
    name: workspace
    status: PLANNED
```

### `sub_feature.manifest.yaml` (inside each sub-feature folder)

```yaml
title: "Organisations"
sub_feature: "01_org"
feature: "02_iam"
status: "DONE"          # PLANNED | SCOPED | DESIGNED | BUILDING | DONE
owner: "your-github-username"
created_at: "2026-04-07"
completed_at: "2026-04-08"
issue: 42               # GitHub issue number
description: |
  Top-level tenants in tennetctl. CRUD only — membership, roles, and
  resources are separate sub-features.
```

Both manifests use the same `{nn}_{name}` format in doc folders. Do not use underscores in the YAML `name:` field — keep it lowercase alphanumeric only.

---

## Sub-Feature Doc Numbering

The doc files inside each sub-feature are always numbered in this order:

| Number | File | Purpose |
|--------|------|---------|
| 01 | `01_scope.md` | What it does, what's out of scope, acceptance criteria |
| 02 | `02_design.md` | Data model, service layer, API overview, security |
| 03 | `03_architecture.md` | Technical architecture, dependencies |
| 04 | `04_user_guide.md` | How to use it |
| 05 | `05_api_contract.yaml` | OpenAPI fragment |
| 06 | `06_user_flows.md` | User interaction flows |
| 07 | `07_decisions.md` | Sub-feature-specific decisions |
| 08 | `08_worklog.md` | Enhancement log and change history |

---

## Backend Module Structure

Every sub-feature's backend code follows the same 5-file structure:

```
backend/02_features/{module}/{sub_feature}/
├── __init__.py
├── schemas.py          # Pydantic v2 request/response models
├── repository.py       # Data access — raw SQL only
├── service.py          # Business logic
└── routes.py           # FastAPI router
```

No exceptions. No extra files unless the module genuinely needs splitting (and it must stay under 500 lines per file).

---

## Frontend Structure

```
frontend/src/app/features/{module}/{sub_feature}/
├── page.tsx            # Next.js page
├── components/         # Sub-feature-specific components
│   ├── {Entity}List.tsx
│   ├── {Entity}Form.tsx
│   └── {Entity}Detail.tsx
├── hooks/              # Custom hooks (TanStack Query)
│   └── use{Entity}.ts
└── types/              # TypeScript types
    └── index.ts
```

---

## Migration File Naming

```
YYYYMMDD_{NNN}_{description}.sql
```

- `YYYYMMDD` — date the migration was written
- `{NNN}` — global three-digit sequence number (shared across all modules)
- `{description}` — snake_case description

Example: `20260405_025_iam_api_keys.sql`

Two migrations with the same `{NNN}` is a hard error.

---

## Database Object Naming

| Object | Convention | Example |
|--------|-----------|---------|
| Schema | `"{nn}_{module}"` | `"02_iam"` |
| Table | `{nn}_{type}_{name}` | `11_fct_orgs` |
| View | `v_{plural_entity}` | `v_orgs` |
| Materialized View | `mv_{description}` | `mv_org_member_counts` |
| Primary Key | `pk_{table}` | `pk_fct_orgs` |
| Foreign Key | `fk_{table}_{ref}` | `fk_fct_orgs_status` |
| Unique | `uq_{table}_{cols}` | `uq_fct_users_email` |
| Check | `chk_{table}_{desc}` | `chk_fct_users_email` |
| Index | `idx_{table}_{cols}` | `idx_fct_orgs_live` |
| RLS Policy | `rls_{table}_{scope}` | `rls_fct_orgs_tenant` |

---

## Naming Rules Summary

| Rule | Correct | Wrong |
|------|---------|-------|
| Numbered prefixes on folders | `02_iam/` | `iam/` |
| Numbered prefixes on docs | `01_scope.md` | `scope.md` |
| snake_case everywhere | `feature_flags` | `featureFlags` |
| Plural for list resources | `v_orgs` | `v_org` |
| No abbreviations in names | `organisations` | `orgs` (in docs) |
| Abbreviations OK in code/DB | `fct_orgs` | `fct_organisations` |
