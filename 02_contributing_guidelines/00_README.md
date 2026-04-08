# Contributing Guidelines

Everything you need to contribute to tennetctl. Read these guides in order.

---

## Vocabulary (read this first)

Three words get used a lot. They are not synonyms.

- **Feature** — a top-level domain in tennetctl. IAM, Vault, Audit, Monitoring, Notify, Ops, LLMOps. Roughly 8 of these total. Each feature has its own Postgres schema, its own backend module, its own folder under `03_docs/features/{nn}_{feature}/`. Adding a new feature is rare and requires a foundation PR (scaffold + schema bootstrap) before any real work can land.
- **Sub-feature** — a unit of work *inside* a feature. One sub-feature ships in one PR (or two if you split docs and code). Sub-features have their own scope, design, manifest, migration, backend code, frontend code, tests. Examples inside IAM: `01_org`, `02_user`, `08_auth`, `19_rbac`. Examples inside Vault: `01_project`, `03_secret`, `05_rotation`. Building sub-features is what you do most days.
- **Enhancement** — a change to a sub-feature that's already been merged. Adding a property, an endpoint, a validation rule, a new EAV attribute. No new sub-feature directory; you extend an existing one.

Every feature also has a special `00_bootstrap/` sub-feature that owns the schema-creation migration. You don't build that as normal work — it's created once per feature, during the foundation PR.

> **A note on "module"**: in code and on GitHub labels, the same thing is sometimes called a *module* — `backend/02_features/{module}/` is the Python package, and the issue label is `module:iam`. Module and feature mean the same thing in this project. "Feature" is the doc word, "module" is the code/label word, both refer to IAM, Vault, Audit, etc.

---

## Start Here

| # | Guide | What It Covers |
|---|-------|----------------|
| 01 | [Building a Feature](01_building_a_feature.md) | One-time foundation work for a brand new top-level feature (IAM, Vault, …). Scaffold, manifest, bootstrap migration. Read this first only if you're standing up a feature that doesn't exist yet. |
| 01a | [Building a Sub-Feature](01a_building_a_sub_feature.md) | The day-to-day workflow. Open issue, write scope/design/migration, verify migration, write tests, implement, ship. This is the doc you'll re-read most. |
| 02 | [Building an Enhancement](02_building_an_enhancement.md) | How to extend an already-merged sub-feature — add properties, endpoints, validations. |
| 03 | [Database Structure](03_database_structure.md) | The EAV model, fct/dtl/dim pattern, database accounts (read/write/admin), views, constraints, and migration rules. **Read this before writing any SQL.** |
| 04 | [Folder Naming Standards](04_folder_naming_standards.md) | Numbered prefixes, directory layouts for docs, backend, frontend, and migrations. |
| 05 | [Backend API Standards](05_backend_api_standards.md) | FastAPI patterns, response envelope, 5-file module structure, error handling, audit events. |
| 06 | [Frontend Standards](06_frontend_standards.md) | Next.js App Router, shadcn/ui, TanStack Query, Zod validation, TypeScript strict mode. |
| 07 | [Testing Standards](07_testing_standards.md) | pytest for Python, Robot Framework for API and E2E tests. TDD workflow, coverage requirements. |
| 08 | [Screenshots & Change Tracking](08_screenshots_and_change_tracking.md) | When and how to capture screenshots, PR templates, worklog entries. |
| 09 | [Maintainer Workflow](09_maintainer_workflow.md) | Task board setup, self-review process, docs-first PRs, manifest status transitions. **Read this if you are the maintainer.** |
| 10 | [Day One Workflow](10_day_one_workflow.md) | Complete lifecycle for building a clean module from scratch. Phase 0-4 walkthrough with real Vault example. **Start here for any new module.** |
| 11 | [IAM Build Plan](11_iam_build_plan.md) | Exact step-by-step plan for building IAM. Build order, doc checklist, scope creep traps, first-week schedule. **Your active build plan.** |

---

## Quick Decision Tree

```
Standing up a brand new top-level feature (IAM, Vault, Audit, …)?
  → Read 01_building_a_feature.md
    (then drop into 01a for each sub-feature inside it)

Building a sub-feature inside an existing feature?
  → Read 01a_building_a_sub_feature.md

Modifying a sub-feature that's already been merged?
  → Read 02_building_an_enhancement.md

Need to understand the database before writing SQL?
  → Read 03_database_structure.md

Not sure where a file goes or how to name it?
  → Read 04_folder_naming_standards.md

Writing a backend API?
  → Read 05_backend_api_standards.md

Building a frontend page?
  → Read 06_frontend_standards.md

Writing tests?
  → Read 07_testing_standards.md

Ready to open a PR?
  → Read 08_screenshots_and_change_tracking.md for the PR template

You are the maintainer following the same process?
  → Read 09_maintainer_workflow.md for task board and self-review
```

---

## The Golden Rule

**All properties go through the EAV pattern.** Never add a string column to a `fct_*` table. Register the attribute in `dim_attr_defs`, store values in `dtl_attrs`, materialize in the view. This keeps the database manageable across 8 modules and dozens of contributors.

---

## Prerequisites

Before contributing, also read:

- [Vision](../03_docs/00_main/01_vision.md) — why tennetctl exists
- [Ethos](../03_docs/00_main/02_ethos.md) — principles behind every decision
- [Rules](../03_docs/00_main/03_rules.md) — hard rules that block PRs
- [Setup](../03_docs/00_main/06_setup.md) — local development setup

---

## A Note on `03_docs/features/` Paths

The documentation paths in these guides (e.g., `03_docs/features/{nn}_{feature}/05_sub_features/{nn}_{sub_feature}/`) are forward-looking. As of today, the first feature-specific docs haven't been merged to `main` yet — they will land as part of the initial feature build (IAM). Until then, the `03_docs/features/` directory exists as empty placeholders. When following these guides, treat the paths as "where these files will go" — the directory structure and organization are in place; the content comes with each feature PR.
