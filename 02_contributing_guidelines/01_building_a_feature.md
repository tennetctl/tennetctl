# Building a Feature

How to add a brand new top-level feature to tennetctl. A feature is something like **IAM**, **Vault**, **Audit**, **Monitoring**. There are roughly eight of them total. Each feature is a self-contained domain with its own database schema, its own backend module, its own frontend pages, and its own folder under `03_docs/features/`.

If you are adding a new capability *inside* an existing feature, you do not want this doc — you want [01a_building_a_sub_feature.md](01a_building_a_sub_feature.md). A sub-feature is the unit of work you actually merge in a single PR. This doc is about the one-time scaffold you create *before* the first sub-feature can be built.

> **Vocabulary**
> - **Feature** — a top-level domain. IAM, Vault, Audit, Monitoring, Notify, Ops, LLMOps. ~8 total. Lives at `03_docs/features/{nn}_{feature}/` and `backend/02_features/{nn}_{feature}/`.
> - **Sub-feature** — a unit of work *inside* a feature. One PR (or two if you split docs and code). IAM has sub-features `01_org`, `02_user`, `08_auth`, `19_rbac`, etc.
> - **Enhancement** — a change to an already-merged sub-feature. See [02_building_an_enhancement.md](02_building_an_enhancement.md).

---

## Prerequisites and known gaps

> **The migration runner does not exist yet.** Several phases below tell you to run `uv run python -m scripts.migrate up`. There is no `scripts/migrate.py` in the repo today. The migration runner is itself one of the first sub-features that needs to be built (likely inside the `01_foundation` feature, or as the very first IAM sub-feature). Until then:
>
> - You can still write migration files in the right location.
> - You cannot automatically apply them. You'll need to apply them by hand: `docker compose exec postgres psql -U tennetctl -d tennetctl -f /path/to/migration.sql` for the UP section, and similarly extract and run the DOWN section by hand to verify the round-trip.
> - Treat every "GATE: migration round-trips" check below as a manual verification, not an automated one.
> - Once the runner lands, the commands in this doc will start working as written. No doc changes needed.

## Before you start

Building a new feature is a commitment. Confirm all of the following before opening any files:

1. **Read the project north stars**:
   - [01_vision.md](../03_docs/00_main/01_vision.md) — does this feature belong in tennetctl?
   - [02_ethos.md](../03_docs/00_main/02_ethos.md) — does the approach match the principles?
   - [03_rules.md](../03_docs/00_main/03_rules.md) — which rules apply (all of them)?
   - [04_roadmap.md](../03_docs/00_main/04_roadmap.md) — is this feature on the roadmap, and at what number?
2. **Read the database doctrine**: [03_database_structure.md](03_database_structure.md). Every new feature gets its own Postgres schema and must follow the EAV pattern. If you do not understand `dim_*`, `fct_*`, `dtl_attrs`, `lnk_*`, stop and read this first.
3. **Pick the number**: feature numbers come from the roadmap (`02_iam`, `07_vault`, etc.). Two features cannot share a number. If your feature is not on the roadmap, open a roadmap PR first and get the number assigned before continuing.
4. **Talk to the maintainer** (or, if you are the maintainer, post an intent comment on the parent issue you are about to open). New features are rare and worth a sanity check.

---

## The lifecycle

```
Phase 0: Plan          — Open the feature parent issue. List sub-features in build order.
Phase 1: Scaffold      — Create the feature directory, manifest, overview, architecture doc.
Phase 2: Bootstrap DB  — Write the schema bootstrap migration (schema + shared dim/dtl tables).
Phase 3: Backend dirs  — Create the empty backend/frontend module dirs.
Phase 4: Foundation PR — Merge the scaffold + bootstrap migration. No code yet.
Phase 5: Sub-features  — Build sub-features one at a time using 01a_building_a_sub_feature.md.
Phase 6: Integration   — Cross-module events, E2E tests.
Phase 7: Ship          — Update roadmap, mark feature DONE.
```

Phases 0–4 are this document. Phase 5 is repeated N times (once per sub-feature), each following [01a_building_a_sub_feature.md](01a_building_a_sub_feature.md). Phases 6–7 close out the feature.

A worked example using **Vault** as the feature lives in [10_day_one_workflow.md](10_day_one_workflow.md). A worked example using **IAM** lives in [11_iam_build_plan.md](11_iam_build_plan.md). Read at least one of those alongside this doc.

---

## Phase 0: Plan

Open the feature parent issue on GitHub. This is the only "claim" that exists — the issue is the lock. No `mkdir` claims a feature; the issue does.

```bash
gh issue create \
  --title "Feature: 07_vault — Secrets Management" \
  --label "feature,module:vault,P0" \
  --body "$(cat <<'EOF'
## Feature: 07_vault — Secrets Management

### Overview
Vault is tennetctl's secrets manager. Applications fetch secrets at runtime
instead of storing them in env files, CI variables, or code.

### Sub-features (build order)
- [ ] #__ — 01_project: vault projects (containers for secrets)
- [ ] #__ — 02_environment: env configs per project
- [ ] #__ — 03_secret: encrypted secret storage
- [ ] #__ — 04_version: secret versioning
- [ ] #__ — 05_rotation: rotation policies
- [ ] #__ — 06_access: access policies and audit

### Dependencies
- Depends on: 02_iam (auth, org membership, RBAC)
- Depended on by: 04_monitoring, 08_llmops (consume secrets at runtime)

### Build plan
Following 04_contributing_guidelines/01_building_a_feature.md.
Sub-features will be built one at a time per 01a_building_a_sub_feature.md.
EOF
)"
```

**Verify it worked:** `gh issue list --label feature` should show your new issue. Note the issue number — you'll reference it in the foundation PR.

You will open one sub-feature issue per item in the build order list, but only when you are about to start that sub-feature. Do not open them all upfront.

---

## Phase 1: Scaffold the feature directory

Create the directory layout. The numbered prefixes are non-negotiable — see [04_folder_naming_standards.md](04_folder_naming_standards.md).

```bash
FEAT=07_vault   # change to your feature number_name
mkdir -p 03_docs/features/$FEAT/04_architecture
mkdir -p 03_docs/features/$FEAT/05_sub_features
```

Note: there is no `09_sql_migrations/` at the feature level. Migration files live inside each sub-feature, under `05_sub_features/{nn}_{sub_feature}/09_sql_migrations/`. The feature-wide schema-bootstrap migration lives inside a special `00_bootstrap/` sub-feature you'll create in Phase 2.

**Verify it worked:**

```bash
tree 03_docs/features/$FEAT
```

You should see exactly `04_architecture/` and `05_sub_features/` and nothing else.

### 1.1 Write the feature manifest

Create `03_docs/features/$FEAT/feature.manifest.yaml`:

```yaml
title: "Vault — Secrets Management"
feature: "07_vault"
status: ACTIVE              # PLANNED | ACTIVE | FROZEN | ARCHIVED
owner: "your-github-username"
created_at: "2026-04-07"
description: |
  Secrets management system with encryption, versioning, and rotation policies.

sub_features:
  - number: 1
    name: project
    status: PLANNED
    description: Vault projects — containers that group secrets by application.
  - number: 2
    name: environment
    status: PLANNED
    description: Env configs per project (dev, staging, prod).
  - number: 3
    name: secret
    status: PLANNED
    description: Encrypted secret storage with AES-256-GCM envelope encryption.
  # ... one entry per sub-feature in the parent issue, in build order

migrations: []         # filled in by sub-features
frontend_pages: []     # filled in by sub-features
```

The `status` field on each sub-feature mirrors the lifecycle defined in [09_maintainer_workflow.md](09_maintainer_workflow.md#manifest-status-transitions). Update them as each sub-feature progresses — this manifest is the at-a-glance state of the whole feature.

### 1.2 Write the overview

Create `03_docs/features/$FEAT/00_overview.md`:

```markdown
# Vault — Secrets Management

## What this feature does
{2-3 sentences. What problem it solves. Who uses it.}

## Why it exists
{Motivation. What's broken about doing this without tennetctl.}

## In scope
- {Capability 1}
- {Capability 2}
- {Capability 3}

## Out of scope
- {Tempting thing that is NOT being built}
- {Thing that belongs in another feature}
- {Thing that's a future enhancement}

## Sub-features
See `feature.manifest.yaml` for the full list and build order.

## Dependencies
- Depends on: {other features}
- Depended on by: {other features}
```

Keep this short. The detailed scope per sub-feature lives in each sub-feature's `01_scope.md`.

### 1.3 Write the architecture doc

Create `03_docs/features/$FEAT/04_architecture/01_architecture.md`. Document:

- **Schema layout** — what the Postgres schema looks like at a high level. Which `dim_*` tables exist, which `fct_*` tables, which views.
- **Service boundaries** — which sub-features depend on which other sub-features inside this feature.
- **External boundaries** — events emitted to other features, events consumed from other features. No direct cross-schema joins (that's [R-005](../03_docs/00_main/03_rules.md)).
- **Key invariants** — anything that must always be true (e.g. "every secret has exactly one active version").

For features with non-obvious architecture (encryption schemes, distributed state, etc.), add `02_workflows.md` with sequence diagrams.

### 1.4 Write the sub-features index

Create `03_docs/features/$FEAT/01_sub_features.md`. This is a flat human-readable list of every sub-feature with one paragraph each. Same content as the `sub_features:` block in the manifest, but in prose.

```markdown
# Vault — Sub-Features

## Build order

### Tier 1: Identity primitives
1. **01_project** — Vault projects, the top-level container. CRUD only. No secrets yet.
2. **02_environment** — Per-project environments (dev, staging, prod). CRUD only.

### Tier 2: Storage
3. **03_secret** — Encrypted secret storage. AES-256-GCM envelope encryption.
4. **04_version** — Secret versioning. Every update creates a new version.

### Tier 3: Lifecycle
5. **05_rotation** — Rotation policies with pluggable backends.
6. **06_access** — Access policies and audit events.
```

---

## Phase 2: Bootstrap sub-feature and migration

Every feature gets its own Postgres schema. The bootstrap migration creates the schema and the shared `dim_entity_types`, `dim_attr_defs`, and `dtl_attrs` tables that all *other* sub-features inside this feature will use.

Bootstrap is itself a sub-feature — a special one. Create the `00_bootstrap/` directory under `05_sub_features/`. Its `00_` prefix guarantees the migration runner picks it up before any real sub-feature.

```bash
BOOT=03_docs/features/$FEAT/05_sub_features/00_bootstrap
mkdir -p $BOOT/09_sql_migrations/01_migrated
mkdir -p $BOOT/09_sql_migrations/02_in_progress
```

### 2.1 Write the bootstrap sub-feature manifest

Create `$BOOT/sub_feature.manifest.yaml`:

```yaml
title: "Vault — Schema Bootstrap"
sub_feature: "00_bootstrap"
feature: "07_vault"
status: BUILDING
created_at: "2026-04-07"
description: |
  Creates the 07_vault Postgres schema and the shared EAV tables
  (dim_entity_types, dim_attr_defs, dtl_attrs) used by every other
  sub-feature in this feature. Has no backend or frontend code —
  schema only.
```

### 2.2 Write the bootstrap scope doc

Create `$BOOT/01_scope.md`. Keep it short — bootstrap has no API and no business logic:

```markdown
# Vault Bootstrap — Scope

## What it does
Creates the `07_vault` Postgres schema and the three shared tables every
other vault sub-feature depends on: `06_dim_entity_types`, `07_dim_attr_defs`,
`20_dtl_attrs`.

## In scope
- CREATE SCHEMA "07_vault"
- The three shared dim/dtl tables with COMMENTs and constraints
- Seed rows in `dim_entity_types` for every entity this feature will use
- Seed rows in `dim_attr_defs` for every attribute the bootstrap knows about
  (more get added by individual sub-features as they land)

## Out of scope
- Any fct_* table (those belong to individual sub-features)
- Any backend or frontend code
- Any business logic

## Acceptance criteria
- [ ] `\dt+ "07_vault".*` shows the three tables
- [ ] Migration round-trips: UP -> DOWN -> UP cleanly
- [ ] Schema is dropped completely on DOWN
```

### 2.3 Write the bootstrap migration

Create `$BOOT/09_sql_migrations/02_in_progress/YYYYMMDD_NNN_{feature}_bootstrap.sql`.

`{NNN}` is a global three-digit sequence number shared across **all** features and sub-features. Find the next available number by walking every sub-feature's migrations directory:

```bash
ls 03_docs/features/*/05_sub_features/*/09_sql_migrations/01_migrated/ \
   03_docs/features/*/05_sub_features/*/09_sql_migrations/02_in_progress/ \
   2>/dev/null \
  | grep -oE '_[0-9]{3}_' | sort -u | tail -5
```

Use the next number above the highest existing one. Two migrations with the same number is a hard error — the runner refuses to start.

Use the bootstrap template from [10_day_one_workflow.md §1.5](10_day_one_workflow.md#15-write-the-bootstrap-migration). It contains the exact SQL for `dim_entity_types`, `dim_attr_defs`, and `dtl_attrs` with all required `COMMENT`s, constraints, and the matching DOWN section.

### 2.4 How the migration runner discovers files

The runner (`uv run python -m scripts.migrate up`) walks:

```
03_docs/features/*/05_sub_features/*/09_sql_migrations/02_in_progress/*.sql
```

It collects every file across every feature and every sub-feature, sorts them by the global `{NNN}` sequence number embedded in the filename, and applies them in order. Because `00_bootstrap/` sorts alphabetically before `01_project/`, `02_environment/`, etc., **and** because the bootstrap migration gets the lowest `{NNN}` of the feature's migrations, the schema and shared tables always exist before any sub-feature tries to extend them.

There is no special-case code in the runner for bootstrap — it's just a sub-feature that happens to sort first. This means you don't need a separate "bootstrap" code path: applying `up` from a clean database walks every feature's `00_bootstrap` first, then the rest of the sub-features, in `{NNN}` order.

### Verify the migration round-trips

This is a hard gate. Do not move on until UP → DOWN → UP works on a clean database.

```bash
uv run python -m scripts.migrate up
docker compose exec postgres psql -U tennetctl -d tennetctl \
  -c '\dt+ "07_vault".*'
# You should see: 06_dim_entity_types, 07_dim_attr_defs, 20_dtl_attrs

uv run python -m scripts.migrate down
docker compose exec postgres psql -U tennetctl -d tennetctl \
  -c '\dn' | grep 07_vault
# Should print nothing — the schema is gone.

uv run python -m scripts.migrate up
# Re-applies cleanly. Schema is back.
```

**GATE:** If any of these three steps fail, fix the migration before proceeding. If DOWN leaves orphan objects behind, fix it. If re-applying after rollback fails, fix it.

---

## Phase 3: Backend and frontend scaffold

Create the empty module directories. They will be filled by individual sub-features in Phase 5.

```bash
FEAT_SHORT=vault   # the feature name without the number prefix

mkdir -p backend/02_features/$FEAT_SHORT
touch backend/02_features/$FEAT_SHORT/__init__.py

mkdir -p frontend/src/app/$FEAT_SHORT
mkdir -p backend/tests/$FEAT_SHORT
touch backend/tests/$FEAT_SHORT/__init__.py

mkdir -p tests/e2e/$FEAT_SHORT
```

**Verify it worked:** `ls backend/02_features/$FEAT_SHORT/` should print `__init__.py`.

---

## Phase 4: Foundation PR

You now have:
- A feature parent issue on GitHub.
- A documented feature directory (`03_docs/features/{nn}_{feature}/`) with overview, architecture, manifest, sub-features index.
- A working bootstrap migration (UP → DOWN → UP verified).
- Empty backend/frontend/tests directories.

Open the foundation PR. **This PR has zero application code.** It is pure scaffold + schema.

```bash
git checkout -b feat/$FEAT-foundation
git add .
git commit -m "feat($FEAT_SHORT): scaffold feature — schema, manifests, architecture"
git push -u origin feat/$FEAT-foundation

gh pr create \
  --title "feat($FEAT_SHORT): scaffold feature — schema, manifests, architecture" \
  --body "$(cat <<'EOF'
## What this PR does
Scaffolds the {feature_name} feature: directory structure, feature manifest,
overview, architecture doc, bootstrap migration (schema + shared dim/dtl tables),
and empty backend/frontend module directories.

This is a docs+schema PR. No application code. No sub-features built yet.

## Database changes
- New schema: `{nn}_{feature}`
- New tables: `06_dim_entity_types`, `07_dim_attr_defs`, `20_dtl_attrs`

## Rollback plan
- Migration DOWN drops the schema and all bootstrap tables.
- No data migration. Safe to roll back at any point before sub-features land.

## Next steps after merge
Sub-features will be built per `04_contributing_guidelines/01a_building_a_sub_feature.md`,
in the order listed in `feature.manifest.yaml`.

Refs #{parent_issue}
EOF
)"
```

Self-review using the checklist in [09_maintainer_workflow.md](09_maintainer_workflow.md#self-review-process). Merge it.

**Verify it worked:** after merge, `ls 03_docs/features/$FEAT/` on `main` should show your scaffold. The parent issue stays open until all sub-features are done.

---

## Phase 5: Build sub-features (one at a time)

Now you switch documents. For each sub-feature in the build order, follow [01a_building_a_sub_feature.md](01a_building_a_sub_feature.md) end to end. Do not start the next sub-feature until the previous one is merged.

After each sub-feature merges, update `feature.manifest.yaml`:

```yaml
sub_features:
  - number: 01
    name: project
    status: DONE          # ← was BUILDING, now DONE
    completed_at: "2026-04-07"
```

And tick the box on the parent issue.

---

## Phase 6: Integration

After all sub-features are merged, do one integration pass:

1. **Cross-feature event wiring** — verify events emitted by this feature are consumed by the features that need them. Add consumer registrations in `01_core/events/`.
2. **End-to-end tests** — write Robot Framework tests in `tests/e2e/{feature}/` that cover full user journeys spanning multiple sub-features.
3. **Frontend navigation** — wire the feature's pages into the main navigation.

Open the integration PR:

```bash
git checkout -b feat/$FEAT-integration
# ... make changes ...
gh pr create --title "feat($FEAT_SHORT): integration — cross-feature events and E2E tests"
```

---

## Phase 7: Ship

1. **Update the roadmap.** In `03_docs/00_main/04_roadmap.md`, change this feature's status to `DONE`.
2. **Update `feature.manifest.yaml`:** set top-level `status: DONE` and add `completed_at`.
3. **Move migrations.** For every sub-feature in this feature (including `00_bootstrap/`), move all files from `05_sub_features/{nn}_{sub}/09_sql_migrations/02_in_progress/` into the matching `01_migrated/` directory.
4. **Close the parent issue.** Comment with a summary of what shipped, then close.

The feature is done.

---

## Common mistakes

| Mistake | Correct approach |
| ------- | ---------------- |
| Building two features in parallel | Finish one feature's foundation PR before starting another's. Schemas can collide on migration numbers. |
| Skipping the foundation PR and going straight to sub-features | The bootstrap migration must be merged first, otherwise sub-feature migrations have nothing to extend. |
| Listing sub-features that don't have a clear scope | If you can't write a one-paragraph description in `01_sub_features.md`, you don't understand it well enough yet. |
| Adding code to the foundation PR | The foundation PR is scaffold + schema only. Code goes in sub-feature PRs. |
| Putting cross-feature dependencies in the schema | Cross-feature communication is via events (see [R-002](../03_docs/00_main/03_rules.md)), never via FK. |
| Using `CREATE TYPE ... AS ENUM` for statuses | Always a `dim_*` table. ENUMs are banned project-wide. |

---

## Where to go from here

- Building a sub-feature now? → [01a_building_a_sub_feature.md](01a_building_a_sub_feature.md)
- Worked example (Vault, hypothetical): [10_day_one_workflow.md](10_day_one_workflow.md)
- Worked example (IAM, real): [11_iam_build_plan.md](11_iam_build_plan.md)
- Self-review and PR discipline: [09_maintainer_workflow.md](09_maintainer_workflow.md)
