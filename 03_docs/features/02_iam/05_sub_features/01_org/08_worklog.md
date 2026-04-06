# Org — Worklog

Chronological record of work sessions for this sub-feature.

---

## 2026-04-01 — Initial Build

**Author:** sri
**Branch:** feat/c-iam
**Status:** ✅ Done

### Tasks Completed

- [x] Wrote `01_scope.md` and `02_design.md`
- [x] Authored SQL migration (DDL, dim seeds, read view, trigger, indexes)
- [x] Applied migration via `python 05_scripts/migrate.py up`
- [x] Implemented `schemas.py` — Pydantic v2 models
- [x] Implemented `repository.py` — asyncpg queries, read-view pattern
- [x] Implemented `service.py` — business logic, audit events
- [x] Implemented `routes.py` — FastAPI router, registered in `main.py`
- [x] Verified API with manual curl / Postman tests
- [x] Wrote docs: `03_architecture.md`, `04_user_guide.md`, `06_user_flows.md`

### Decisions Made

- 5-file module structure: schemas / repository / service / routes / __init__
- GET queries use read view (`v_*`); POST/PATCH/DELETE write to `fct_*` tables directly
- Audit events emitted for all mutations (create=1, update=2, delete=3)

### Issues Encountered

- None.

### Next Steps

- Add E2E Playwright test coverage (see `07_planning.md`)

---

> **Log format:** Add a new section `## YYYY-MM-DD — Description` for each work session.

## 2026-04-02 — Phase 5: API Test

**Author:** sri
**Branch:** feat/c-iam
**Status:** ✅ Done

### Tasks Completed

- [x] Started local Uvicorn with mocked `database.py` DB fetcher returning mocked struct.
- [x] Authored `01_org.robot` API test for Org feature HTTP endpoints. 
- [x] Robot Framework tests run and verified 100% PASS for (`Create Org Success`, `Get Org List`, `Get Single Org`, `Delete Org`).

## 2026-04-02 — Phase 6: UI Design

**Author:** sri
**Branch:** feat/c-iam
**Status:** ✅ Done

### Tasks Completed

- [x] Created StitchMCP project `tennetctl - IAM Org`.
- [x] Generated Enterprise Dashboard screen for Orgs containing table of organizations and 'Create Organization' action button.

## 2026-04-02 — Phase 7: Frontend Build

**Author:** sri
**Branch:** feat/c-iam
**Status:** ✅ Done

### Tasks Completed

- [x] Created `src/types/api.ts` with standard `ApiResponse` and `Org` types.
- [x] Implemented React hook `use-orgs.ts` using TanStack Query.
- [x] Hand-coded `OrgTable` component at `src/features/iam/_components/org-table.tsx`.
- [x] Assembled layout inside `src/app/iam/orgs/page.tsx` with appropriate QueryClient providers.

## 2026-04-02 — Phase 8: E2E Testing

**Author:** sri
**Branch:** feat/c-iam
**Status:** ✅ Done

### Tasks Completed

- [x] Authored Playwright spec covering IAM Organization listing and Create action visibility (`04_tests/e2e/02_iam/01_org.spec.ts`).
## 2026-04-02 — Phase 9: Security Audit

**Author:** sri
**Branch:** feat/c-iam
**Status:** ✅ Done

### Tasks Completed

- [x] Verified parameterization used for all asyncpg SQL queries (`$1, $2`), preventing SQL injection.
- [x] Validated Pydantic models with explicit Max/Min length enforcing strict input validation.
- [x] Confirmed UUIDv7 used for resource generation via `_core_id.uuid7()`, eliminating enumerable id references.
- [x] Verified manual SQL triggers (`set_updated_at`) prevent application side tampering of `updated_at`.

## 2026-04-03 — Full TDD Rebuild (Fresh Start)

**Author:** sri + claude
**Branch:** feat/c-iam
**Status:** DONE

### Tasks Completed

- [x] Fixed SQL migration: quoted numeric-prefixed table names, fixed MAX(jsonb) in view
- [x] Applied migration to PG 16 (Docker compose)
- [x] Scaffolded backend core: config, database pool, uuid7, response envelope, exceptions
- [x] Wrote 16 integration tests (TDD RED phase) covering all CRUD + slug recycling
- [x] Implemented 5-file backend module: schemas, repository, service, routes
- [x] All 16 tests GREEN — create, list, get, update, soft-delete, slug reuse
- [x] Initialized Next.js 16 frontend with shadcn/ui v4, TanStack Query, Zod
- [x] Built org list page with table, badges, create dialog
- [x] Built org detail page with suspend/activate/delete actions
- [x] Wrote 5 Playwright E2E tests — all passing
- [x] TypeScript strict: no errors
- [x] Ruff lint: clean (1 intentional S104 for dev config)

### Decisions Made

- importlib for all numeric-prefix imports (Python can't do `from 01_backend...`)
- Base UI Dialog (shadcn v4): uses `render` prop instead of `asChild`
- Test isolation via autouse fixture that truncates org tables before each test
- Backend bound to 0.0.0.0:18000, frontend on 13000 per project convention

### Architecture

- Backend: FastAPI + asyncpg, conn-not-pool, EAV for slug/display_name/settings
- Frontend: Next.js 16 App Router, server + client components, TanStack Query
- API: 5 endpoints following project conventions, response envelope {ok, data}
