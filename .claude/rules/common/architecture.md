---
paths:
  - "**/*.py"
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.sql"
  - "**/*.yaml"
---

# Architecture & Structure

Project-specific conventions. Not general best practices.

## Feature Numbers

| # | Feature | Schema | Backend | Frontend |
| --- | --- | --- | --- | --- |
| 00 | Setup | `"00_schema_migrations"` (shared) | `scripts/setup/` | — (CLI only) |
| 01 | SQL Migrator | `"00_schema_migrations"` | `scripts/migrator/` | — (CLI only) |
| 02 | Vault | `"02_vault"` | `02_features/vault/` | `/vault` |
| 03 | IAM | `"03_iam"` | `02_features/iam/` | `/iam` |
| 04 | Audit | `"04_audit"` | `02_features/audit/` | `/audit` |
| 05 | Monitoring | `"05_monitoring"` | `02_features/monitoring/` | `/monitoring` |
| 06 | Notify | `"06_notify"` | `02_features/notify/` | `/notify` |
| 07 | Billing | `"07_billing"` | `02_features/billing/` | `/billing` |
| 08 | LLM Ops | `"08_llmops"` | `02_features/llm/` | `/llm` |

Feature numbers are permanent — never renumber. `00_setup` and `01_sql_migrator`
are tooling features (CLI only, no HTTP API, no frontend). `02_vault` and
`03_iam` are the two foundational runtime features — everything else depends
on both being in place.

## Naming

| Artifact | Pattern | Example |
| --- | --- | --- |
| DB schema | `"{nn}_{name}"` | `"03_iam"` |
| DB table | `{nn}_{type}_{name}` | `10_fct_users` |
| DB view | `v_{plural}` | `v_orgs` |
| Migration | `YYYYMMDD_{NNN}_{desc}.sql` | `20260405_007_create-auth-tables.sql` |
| API path | `/v1/{kebab-plural}` | `/v1/feature-flags` |
| Sub-feature dir (backend) | `snake_case` | `iam/feature_flag/` |
| Sub-feature dir (frontend) | `kebab-case` | `/feature-flags` |

## Directory Layout

```text
{project}/
├── 03_docs/features/{nn}_{feature}/
│   ├── feature.manifest.yaml
│   └── 05_sub_features/
│       ├── 00_bootstrap/                       # schema + shared dim/dtl tables
│       │   └── 09_sql_migrations/ (01_migrated/ + 02_in_progress/)
│       └── {nn}_{sub}/
│           └── 09_sql_migrations/ (01_migrated/ + 02_in_progress/)
├── backend/
│   ├── 01_core/              # config, db, id, errors, response, middleware
│   └── 02_features/{feature}/{sub_feature}/
│       ├── __init__.py
│       ├── schemas.py        # Pydantic v2
│       ├── repository.py     # asyncpg raw SQL, reads views
│       ├── service.py        # Business logic + audit
│       └── routes.py         # FastAPI APIRouter
└── frontend/src/
    ├── app/{feature}/{sub-feature}/page.tsx
    ├── features/{feature}/_components/ + hooks/
    └── types/api.ts          # ALL shared TS types (one file)
```

Backend sub-feature = exactly 5 files. No more without clear reason.

## API Design

5-endpoint shape: `GET list`, `POST create`, `GET one`, `PATCH update`, `DELETE soft-delete`.

PATCH handles ALL state changes — never action endpoints (`POST /activate`). Use filter params instead of multiple list endpoints (`GET /orgs?status=active`).

DELETE = soft-delete only (`deleted_at = NOW()`, returns 204).
