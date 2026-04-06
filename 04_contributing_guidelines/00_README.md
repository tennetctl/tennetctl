# Contributing Guidelines

Everything you need to contribute to tennetctl. Read these guides in order.

---

## Start Here

| # | Guide | What It Covers |
|---|-------|----------------|
| 01 | [Building a Feature](01_building_a_feature.md) | End-to-end workflow for adding a new feature or sub-feature. The 10-step process from claiming to PR. |
| 02 | [Building an Enhancement](02_building_an_enhancement.md) | How to enhance an existing feature — add properties, endpoints, validations. The 7-step process. |
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
Want to build something entirely new?
  → Read 01_building_a_feature.md

Want to add/change something in an existing feature?
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
