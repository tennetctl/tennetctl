---
name: build-sub-feature
description: Autonomously build a complete sub-feature end-to-end within a module. Invoke with the module and sub-feature name.
origin: custom
---

# Build Sub-Feature

One command. Research the codebase, then work through five phases until the sub-feature is fully built and tested.

## How to Invoke

```
/build-sub-feature 02_iam/03_auth
/build-sub-feature 05_billing/02_invoice
```

Format: `/build-sub-feature {module}/{sub_feature}`

## Before Writing Anything

Research first:
- Read the process guide (typically `docs/adding_a_feature.md` or equivalent)
- Read the feature manifest for the target module
- Read what already exists in the sub-feature directory
- Study a completed example sub-feature in the same module
- Check any architectural decision records

If on the main branch, stop and tell the user — every sub-feature gets its own branch.

## The Three Phases

Work through these phases in order:

**Phase 1 — Plan.** Write scope, design, API contract, user flows, and a manifest. Identify every layer that needs to change (schema, backend, frontend). Get this right before writing any code. Commit.

**Phase 2 — Implement.** Write the schema migration, then backend (schemas → repo → service → routes), then frontend pages. Follow TDD: failing tests committed before implementation in each layer. Run tests until GREEN with no regressions after each layer. Commit per layer.

**Phase 3 — Test & Close.** Write or finalize E2E tests. Run the full suite (unit + integration + E2E). Update the manifest status to DONE. If all green, push and open a PR.

## Scope Discipline

Only build what the sub-feature requires. No speculative abstractions, no cross-cutting refactors, no improvements to adjacent code that isn't broken.

## Self-Correction

Each iteration: run the verification command, read errors before fixing, fix root causes not symptoms, commit after each meaningful step, never redo already-committed work.
