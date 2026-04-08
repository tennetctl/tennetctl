---
name: enhance-sub-feature
description: Autonomously enhance a specific aspect of an already-built sub-feature. Invoke with the module, sub-feature, and what to change.
origin: custom
---

# Enhance Sub-Feature

One command. Read the current state of an existing sub-feature, understand what's there, then implement the specific enhancement.

## How to Invoke

```
/enhance-sub-feature 02_iam/03_auth add rate limiting to login endpoint
/enhance-sub-feature 02_iam/01_org add bulk delete with cascade
/enhance-sub-feature 05_billing/02_invoice add PDF export button to detail page
```

Format: `/enhance-sub-feature {module}/{sub_feature} {what to change}`

## Before Writing Anything

Read the full current state: docs, backend, tests, frontend, E2E tests. Understand what exists before changing anything.

## Enhancement Classification

Classify what's changing to know which layers to touch:

- **API change** (new endpoint, field, validation) → schemas + repo + service + routes + tests
- **UI change** (new button, page, filter) → components + E2E tests
- **SQL change** (new column, index, view) → migration + repo update + tests
- **Test coverage** (more edge cases) → tests only
- **Doc update** → docs only
- **Full-stack** → all layers

## Three Phases Still Apply

Even for enhancements: Plan what's changing and which layers are affected → Implement with TDD (failing test first, then code) → Test & verify the full suite passes with no regressions.

## Scope Discipline

Only change what the enhancement requires. No refactoring unrelated code. No improving things that aren't broken. Update docs only if the API contract changes.

## After Completion

Update the worklog with what was enhanced. Push the branch and open a PR.
