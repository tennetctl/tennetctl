## What does this PR do?

<!-- 1–2 sentences -->

## Type of change

- [ ] `feat` — new feature
- [ ] `fix` — bug fix
- [ ] `refactor` — no behaviour change
- [ ] `docs` — documentation only
- [ ] `test` — tests only
- [ ] `chore` — maintenance

## Self-review checklist

**Process**
- [ ] I read my own diff before opening this PR
- [ ] Tests were written before the implementation (TDD: RED → GREEN → IMPROVE)
- [ ] All tests pass (`uv run pytest`)
- [ ] Coverage is 80%+ (`uv run pytest --cov=. --cov-report=term-missing`)

**Code**
- [ ] No mutations — all functions return new objects
- [ ] No silent error swallowing — errors are handled or propagated (R-007)
- [ ] No hardcoded values — config lives in `01_core/config.py` (R-010)
- [ ] No file exceeds 500 lines (R-009)
- [ ] Every new function has a docstring (R-006)

**Architecture**
- [ ] No module imports another module's service layer (R-002)
- [ ] No new required dependencies introduced (R-004)
- [ ] Module only queries its own Postgres schema (R-005)

**API**
- [ ] All API responses use the response envelope (`{ "ok": true, "data": {} }`)
- [ ] All user input validated at the boundary via Pydantic (R-008)

**Database** *(skip if no schema changes)*
- [ ] Migration has both UP and DOWN (R-013)
- [ ] Every new table and column has a SQL `COMMENT` (R-011)
- [ ] All constraint names are explicit and prefixed (`pk_`, `fk_`, `uq_`, `chk_`) (R-012)
- [ ] Table naming follows `{nn}_{type}_{name}` convention (R-014)

**Security**
- [ ] No plaintext secrets anywhere (R-015)
- [ ] Every mutating operation emits an audit event within the same transaction (R-016)
- [ ] RLS policy added for any new org-scoped table (R-017)

**Docs**
- [ ] `feature.manifest.yaml` updated if a sub-feature status changed (R-018)
- [ ] ADR added if this changes architecture or cross-module contracts (R-019)
- [ ] Relevant docs in `03_docs/` updated if behaviour changed

## How to test this

<!-- Steps to manually verify the change works -->

## Screenshots

<!-- If this changes the UI, add before/after screenshots -->

## Notes for reviewer

<!-- Anything you want to call out -->
