# Core Standards

Rules that deviate from defaults or encode project-specific conventions.

## Immutability

ALWAYS return new objects. NEVER mutate. This applies to Python dicts, TypeScript objects, and DB records.

## File Organization

- 200–500 lines typical, 1000 max.
- Organize by feature/domain, not by type.
- Numbered prefixes on all folders and files: `01_core/`, `02_features/`.

## TDD (mandatory)

1. Write failing test (RED)
2. Write minimal implementation (GREEN)
3. Refactor (IMPROVE)
4. Verify 80%+ coverage

Fix implementation, not tests (unless the test is wrong).

## Commit Format

`feat|fix|refactor|docs|test|chore|perf|ci: description`

Use `git add .` to stage all changes. Do not stage file-by-file.

## Feature Workflow

0. Research first — Context7 docs, `gh search`, npm/PyPI registries before writing anything new.
1. Plan — use planner agent, confirm before coding.
2. TDD — tests first.
3. Review — code-reviewer agent, fix CRITICAL and HIGH.
4. Commit + PR.

## Testing Standards

- **Backend**: pytest (`tests/` dir, `test_*.py` files)
- **E2E / Frontend**: Robot Framework + Playwright Browser library (`.robot` files) — NEVER `@playwright/test` or `.spec.ts`
- E2E test location: `tests/e2e/{feature}/01_{sub}.robot`
- **Playwright MCP**: headed live browser for manual inspection alongside `npm run dev`. Not a test runner. Triggered when Sri says "test with Playwright MCP".

## Agents (use without being asked)

| Trigger | Agent |
| --- | --- |
| Complex feature or refactor | planner |
| Architectural decision | architect |
| Code just written/modified | python-reviewer or typescript-reviewer |
| Security-sensitive code | security-reviewer |
| Build fails | build-error-resolver |
| Critical user flows | e2e-runner |
| Analyzing reference projects | ref-reader |

Launch independent agents in parallel, not sequentially.

## Response Envelope

Every API response:
```json
{ "ok": true, "data": {...} }
{ "ok": false, "error": {"code": "NOT_FOUND", "message": "..."} }
```
