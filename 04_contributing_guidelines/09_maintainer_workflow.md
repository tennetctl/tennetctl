# Maintainer Workflow

How the maintainer (or any solo contributor) follows the same process as external contributors. No shortcuts. The review discipline matters most when nobody is watching.

---

## Why Follow Your Own Process?

1. **Muscle memory** — when contributors join, you can point them to a process you actually use, not one you wrote and forgot
2. **Audit trail** — every feature has a clean issue -> scope -> design -> schema -> PR chain
3. **Quality gate** — self-review catches bugs that "just push it" misses
4. **Context recovery** — when you return to a feature after weeks, the docs tell you where you left off

---

## Tracking System: GitHub Issues (Not Projects)

GitHub Issues is the tracker. Not GitHub Projects, not Notion, not a spreadsheet. One issue per sub-feature or enhancement. The issue IS the scope lock.

### Why Issues, Not Projects?

- **Projects add overhead** — dragging cards between columns feels productive but isn't. You're a solo maintainer, not a PM managing a team.
- **Issues have checkboxes** — the task list in the issue body IS your progress tracker. When all boxes are checked, you're done.
- **Issues link to PRs** — `Closes #42` in the PR body auto-closes the issue. Clean lifecycle.
- **Issue templates enforce structure** — you can't "forget" to define scope because the template requires it before you start.

### How It Works

```text
1. Open an issue using the "Sub-Feature Build" or "Sub-Feature Enhancement" template
2. Fill in the Scope Lock section FIRST (before any code)
3. Work through the Progress checkboxes in order
4. If you discover something out of scope, log it in the Scope Creep Log
5. Open a PR with "Closes #issue_number"
6. Merge → issue auto-closes
```

Every sub-feature or enhancement gets its own issue. No batching multiple things into one issue.

### Issue Templates

Two templates exist in `.github/ISSUE_TEMPLATE/`:

| Template | When to use |
| -------- | ----------- |
| `sub_feature_build.md` | Building a new sub-feature from scratch |
| `sub_feature_enhancement.md` | Enhancing an existing sub-feature |

Both templates have:

- **Scope Lock** — define in-scope, out-of-scope, and acceptance criteria upfront
- **Progress** — phased checkboxes matching the workflow steps
- **Scope Creep Log** — a table where discoveries become new issues, not scope additions

### Labels for Filtering

Use these labels to see your board at a glance:

```text
sub-feature          — all sub-feature work
feature              — new builds
enhancement          — modifications to existing
module:iam           — IAM module
module:audit         — Audit module
module:vault         — Vault module
(etc.)
P0 / P1 / P2         — priority
```

To see your "board":

```bash
# All open sub-feature work
gh issue list --label sub-feature

# Just IAM
gh issue list --label sub-feature --label module:iam

# What's P0
gh issue list --label P0
```

This is simpler than a Projects board and gives you the same information.

---

## Scope Creep Prevention

Scope creep is the #1 risk for solo maintainers. You're the developer AND the PM, so there's nobody to say "that's a separate ticket." You have to be that person for yourself.

### The Rule

> **If it's not in the Scope Lock section of the issue, it does not go in this PR.**

No exceptions. Not "it's small." Not "it's related." Not "I'm already here."

### How Scope Creep Happens

```text
You're building user invitations.
You notice the org member list doesn't show roles.
You add role display to the member list.
Now the member list needs a role filter.
Now you need to update the API to support role filtering.
Now you've spent 3 hours on org members, not invitations.
```

Every single one of those steps felt reasonable in the moment. That's what makes scope creep dangerous — each addition is small and logical.

### The Scope Creep Log

Both issue templates include a **Scope Creep Log** table at the bottom:

```markdown
## Scope Creep Log

| Date | Discovery | Action |
| ---- | --------- | ------ |
| 2026-04-06 | Member list should show roles | Opened #45 as enhancement |
| 2026-04-07 | Need role filter on member API | Opened #46 as enhancement |
```

When you discover something that needs doing:

1. **Stop.** Do not implement it.
2. **Log it** in the Scope Creep Log table on the current issue.
3. **Open a new issue** for the discovery (use the enhancement template).
4. **Continue** with the original scope.

### The 3-Question Test

Before adding anything to your current work, ask:

1. **Is this in the Scope Lock?** If no, it's a new issue.
2. **Would this PR make sense without it?** If yes, it's a new issue.
3. **Can this ship separately?** If yes, it's a new issue.

If all three answers point to "new issue," open one and move on.

### When Scope SHOULD Change

Rarely, you discover that the original scope is wrong — not just incomplete, but fundamentally wrong. The design doesn't work without this change.

In that case:

1. **Stop implementing.**
2. **Edit the Scope Lock** on the issue — add the change, explain why in a comment.
3. **Update `01_scope.md`** to match.
4. **Continue.**

The key difference: you're deliberately choosing to expand scope with a documented reason, not drifting into it.

---

## Self-Review Process

You review your own PRs with the same rigor as an external contributor's PR. This is the discipline that matters.

### Step 1: Wait Before Reviewing

After opening the PR, **do not review immediately**. Context-switch for at least 30 minutes. Fresh eyes catch what tired eyes miss.

### Step 2: Read the Diff on GitHub

Read the diff on GitHub, not in your editor. The GitHub diff view shows you what a reviewer would see — not what you intended to write.

### Step 3: Walk the Checklist

Go through every item in the PR checklist. Do not check items without verifying them.

```text
Architecture
- [ ] No module imports another module's service layer (R-002)
- [ ] No new required dependencies (R-004)
- [ ] Module only queries its own schema (R-005)

Code Quality
- [ ] Every new function has a docstring (R-006)
- [ ] No silent error swallowing (R-007)
- [ ] All user input validated at boundary (R-008)
- [ ] No file exceeds 500 lines (R-009)
- [ ] No hardcoded values (R-010)

Database
- [ ] Every table and column has a COMMENT (R-011)
- [ ] All constraint names explicit and prefixed (R-012)
- [ ] Migration has UP and DOWN (R-013)
- [ ] Table naming follows convention (R-014)
- [ ] Properties in dtl_attrs, not fct_* columns
- [ ] No triggers, ENUMs, stored procedures
- [ ] Migration round-trip verified

Security
- [ ] No plaintext secrets (R-015)
- [ ] Mutating operations emit audit events (R-016)
- [ ] RLS on org-scoped tables (R-017)

Documentation
- [ ] Feature manifest updated (R-018)
- [ ] ADR written if architectural decision (R-019)
- [ ] worklog.md updated (for enhancements)

Cross-Module
- [ ] New events documented
- [ ] Consumer modules identified
- [ ] No cross-schema JOINs

Rollback
- [ ] Migration DOWN tested
- [ ] Rollback steps documented in PR
```

### Step 4: Run the Agents

Before merging, run the automated review agents:

```text
code-reviewer    -> Check code quality and conventions
security-reviewer -> Check for vulnerabilities
build-error-resolver -> Verify build passes
```

### Step 5: Merge

Only merge after all checklist items pass. If something fails, fix it in a new commit on the same PR — do not amend and force-push.

---

## Docs-First PRs

For larger features, split into two PRs:

### PR 1: Docs (scope + design + schema + contract)

```text
feat(docs): scope and design for {sub-feature}

Contains:
- 01_scope.md
- 02_design.md
- 05_api_contract.yaml
- Migration SQL in 09_sql_migrations/02_in_progress/
- sub_feature.manifest.yaml (status: DESIGNED)
```

Review this PR. Merge it. Then start implementation.

### PR 2: Implementation (tests + code + frontend)

```text
feat: implement {sub-feature}

Contains:
- Backend: schemas, repository, service, routes
- Frontend: page, components, hooks
- Tests: pytest + Robot Framework
- sub_feature.manifest.yaml (status: DONE)
```

**Why split?** The docs PR forces you to think through the design without the sunk-cost pressure of already-written code. If the design is wrong, you've wasted a few hours of writing, not days of implementation.

---

## Manifest Status Transitions

Track progress via `sub_feature.manifest.yaml` status:

```text
DRAFT     ->  You've claimed it, directory created
SCOPED    ->  01_scope.md written and reviewed
DESIGNED  ->  02_design.md + 05_api_contract.yaml written
BUILDING  ->  Implementation in progress
DONE      ->  PR merged, feature complete
```

Update the manifest at each transition. This is how you (and future contributors) know the state of every sub-feature at a glance.

---

## Weekly Hygiene

Once a week, spend 15 minutes:

1. **Review the board** — any stale items? Move or close them.
2. **Check manifests** — do they match reality? Update statuses.
3. **Review worklogs** — any enhancements missing entries?
4. **Check for orphaned migrations** — any in `02_in_progress/` that should be in `01_migrated/`?

---

## When to Break the Process

The process exists to prevent mistakes, not to slow down trivial changes. Use judgement:

| Change | Full process? |
| ------ | ------------- |
| New sub-feature | Yes — all 12 steps |
| Significant enhancement | Yes — all 9 steps |
| Typo fix in docs | No — direct commit |
| Adding a dim row | Lightweight — issue + migration + PR |
| Bug fix with test | Lightweight — issue + test + fix + PR |
| Refactor (no behavior change) | Lightweight — issue + tests pass + PR |

"Lightweight" means: open an issue, make the change, verify tests pass, open a PR with a short description. Skip scope/design docs.
