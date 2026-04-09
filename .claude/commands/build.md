---
description: Full autonomous feature build — understand repo, plan, implement with TDD, review, fix, commit, PR. Runs until the sub-feature is done.
---

# /build

End-to-end workflow for building a sub-feature. Runs autonomously to completion. Only pauses after the plan and on CRITICAL issues.

## Usage

```
/build <what to build>
/build <path/to/repo>: <feature description>
```

Include: what to build, which repo if not CWD, acceptance criteria if known.

## Arguments

`$ARGUMENTS` — full description of the feature to build.

---

## Phase 0 — Repo Understanding

Read the target repo before touching anything:

1. Read `CLAUDE.md` / `.claude/rules/` — these override everything
2. Read `README.md`, `pyproject.toml` / `package.json`
3. Map top-level structure — what does each directory own?
4. Identify: language, framework, DB, auth, test tool
5. Find core entities — migrations, models, schema
6. Read 3–5 representative files to understand:
   - Import patterns
   - DB session usage (`conn` vs `pool`)
   - Error handling style
   - Auth/permission enforcement
   - Audit logging
7. Identify the next migration number
8. Find files that will need to change

Produce a one-paragraph **Repo Brief** before proceeding.

### Backend conventions

- Migrations: `migrations/NNN_description.sql` with `-- up` / `-- down` blocks
- Match existing import and router loading patterns
- EAV: use existing entity/attr IDs — never add new fact columns without discussion
- Audit: emit audit events for all state-changing operations
- Auth: use existing RBAC middleware — never roll custom auth

### Frontend conventions
- Next.js App Router: pages in `app/`, API routes in `app/api/`
- Check `components/` for existing primitives before creating new ones
- Server components by default; client components only when interactivity requires it

---

## Phase 1 — Research & Reuse

Before writing anything:
- Search repo for existing implementations to extend rather than duplicate
- Check for partial implementations of this feature
- Identify exact files to create or modify
- Note the migration number to continue from

---

## Phase 2 — Plan

Invoke the **planner** agent:
- Restate what is being built and why
- Break into phases: schema → backend → frontend → tests
- Identify risks, dependencies, and the files that change
- **STOP — present plan and wait for confirmation before writing any code**

---

## Phase 3 — Schema / Migration (if needed)

1. Write `migrations/NNN_description.sql` with `-- up` and `-- down`
2. Apply migration
3. Verify with a quick query

---

## Phase 4 — Backend (TDD)

For each logical unit:
1. Define interface / type first
2. Write failing tests (RED)
3. Implement minimal code to pass (GREEN)
4. Refactor (IMPROVE)

Follow repo conventions exactly.

---

## Phase 5 — Frontend (if applicable)

- Match existing page/component patterns exactly
- No new libraries without discussion
- Wire to backend endpoints
- Handle loading, error, and empty states

---

## Phase 6 — Code Review

Check all changed files for:

**CRITICAL (block):** hardcoded secrets, SQL injection, XSS, missing auth checks, unvalidated input

**HIGH (fix before PR):** unhandled errors, missing tests, functions >50 lines, logic bugs, N+1 queries

**MEDIUM (fix if quick):** console.log/print statements, missing docstrings, mutation patterns, files >800 lines

Fix all CRITICAL and HIGH before continuing.

---

## Phase 7 — Verify

Run in order — stop and report if anything fails:
1. Build
2. Type check
3. Lint
4. Tests — must be 80%+ coverage on new code
5. No console.log / hardcoded secrets

Output:
```
VERIFY: [PASS/FAIL]
Build: [OK/FAIL] | Types: [OK/X errors] | Lint: [OK/X] | Tests: [X/Y, Z%]
Ready for PR: [YES/NO]
```

---

## Phase 8 — Commit & PR

```bash
git add <specific files>
git commit -m "feat: <description>"
git push -u origin <branch>
gh pr create --title "<title>" --body "<summary + test plan>"
```

Output the PR URL. Done.

---

## Autonomous mode

Runs without stopping except:
- **After Phase 2** — always pause for plan confirmation
- **CRITICAL issue found** — pause and report
- **Decision requires input** — pause and ask

For everything else: make the best call, document it inline, keep moving.
