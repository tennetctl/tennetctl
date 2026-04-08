---
description: Review a PR or local changes — checkout branch, read full context, produce severity-rated findings. Also runs verify, e2e, and coverage checks.
---

# /review

Review a PR or the current working tree. Reads the full file (not just the diff) for every changed file, understands changes in repo context, and produces a structured report.

## Usage

```
/review                        # review uncommitted local changes
/review 42                     # review PR #42
/review feat/my-branch         # review a branch
/review coverage               # coverage gaps + missing tests only
/review e2e                    # run E2E tests and report
/review full                   # PR/local + verify + coverage + e2e
```

## Arguments

`$ARGUMENTS` — PR number, branch name, or mode keyword.

---

## Step 1 — Get the diff

**For local changes:**
```bash
git diff --name-only HEAD
git diff HEAD
```

**For a PR / branch:**
```bash
gh pr checkout $PR_NUMBER        # or: git fetch origin $BRANCH && git checkout $BRANCH
gh pr view $PR_NUMBER --json title,body,author,baseRefName,headRefName,files,commits
git diff origin/main...HEAD --stat
git diff origin/main...HEAD
```

---

## Step 2 — Read full context

For every changed file:
- Read the entire file, not just the diff
- Understand what the file does in the system
- Understand what the change accomplishes

If `/build` hasn't run this session, do a quick repo orient first (read README, key config, conventions).

---

## Step 3 — Review checklist

**CRITICAL — block merge:**
- [ ] No hardcoded secrets, tokens, credentials
- [ ] All user input validated before use
- [ ] No SQL injection (parameterized queries only)
- [ ] No XSS (user content escaped before render)
- [ ] Auth/permission checks on every new endpoint
- [ ] No sensitive data in logs or error responses

**HIGH — fix before merge:**
- [ ] Logic matches PR intent
- [ ] Edge cases handled (null, empty, concurrent writes, zero)
- [ ] Error paths return correct status codes and messages
- [ ] No silent failures (swallowed exceptions, unchecked returns)
- [ ] DB transactions used where atomicity required
- [ ] New code has tests (happy path + error path)
- [ ] No mocked DB in integration tests

**MEDIUM — fix if quick:**
- [ ] Repo conventions followed (imports, session, audit, EAV)
- [ ] Migration has `-- up` and `-- down` blocks
- [ ] Immutable patterns — no in-place mutation
- [ ] Functions <50 lines, files <800 lines

**LOW — notes:**
- [ ] No console.log / debug prints
- [ ] No TODO/FIXME left uncommitted
- [ ] New public functions have docstrings

---

## Step 4 — Verify (if `full` or standalone)

Run in order, stop and report on failure:
1. Build
2. Type check
3. Lint
4. Tests

```
VERIFY: [PASS/FAIL]
Build: [OK/FAIL] | Types: [OK/X] | Lint: [OK/X] | Tests: [X/Y, Z%]
```

---

## Step 5 — Coverage (if `coverage` or `full`)

1. Run coverage tool for the project
2. Find files with <80% coverage
3. For each gap: show which lines are uncovered and suggest the missing test case
4. Generate missing tests if requested

---

## Step 6 — E2E (if `e2e` or `full`)

1. Start dev server if not running
2. Run Playwright tests
3. Capture screenshots on failure
4. Report pass/fail per journey

Always use context-mode MCP with Playwright. Screenshots are OK for visual checks.

---

## Step 7 — Report

```
## Review: [title or "local changes"]

**Files changed**: N | **Commits**: N (if PR)

### Summary
[2–3 sentences: what this does and whether the approach is sound]

### Findings

#### CRITICAL
- [file:line] — [issue] — [fix]

#### HIGH
- [file:line] — [issue] — [fix]

#### MEDIUM
- [file:line] — [issue] — [fix]

#### LOW
- [file:line] — [note]

### Verdict
APPROVE / REQUEST CHANGES / BLOCK

Must fix before merge:
- [ ] ...
```

---

## Notes

- Touch auth, payments, or user data → treat as security review
- Missing tests for new logic is always HIGH
- Check that PR description matches what the code actually does
