# SQL Migrator — Incremental Schema Migration Runner

## What this feature does

The SQL migrator discovers all `*.sql` migration files spread across every
feature's `05_sub_features/*/09_sql_migrations/02_in_progress/` directories,
applies them to Postgres in strict global NNN sequence order, and records each
applied migration in a dedicated tracking table. On the next run it skips
already-applied migrations and only applies new ones — making every deploy
fully incremental and idempotent.

## Why it exists

tennetctl manages eight features, dozens of sub-features, and hundreds of SQL
migrations over its lifetime. Without a migration runner, every deploy requires
manually running `psql` commands in the right order — error-prone and
environment-inconsistent. The migrator ensures that initialising a fresh
deployment (staging, prod, a new developer's local environment) applies every
migration exactly once, in the correct order, automatically.

## Design philosophy

- **No external dependencies** — pure Python + asyncpg. No Alembic, no Flyway.
- **SQL files are the source of truth** — each file has UP and DOWN sections.
- **Ordering by NNN** — the three-digit global sequence number embedded in every
  filename (`20260408_NNN_description.sql`) is the single ordering key.
- **Tracking in Postgres** — applied migrations recorded in `00_schema_migrations`.
  The tracking schema is bootstrapped by the migrator itself on first run.
- **migration.yaml per sub-feature** — each sub-feature declares its migrations
  and their order in a `migration.yaml` manifest. The runner uses these to build
  the global ordered list and detect conflicts.

## Scope boundaries

**In scope:**
- Discover all `migration.yaml` files across all sub-features
- Build a globally ordered list of SQL files from `migration.yaml` entries
- Apply unapplied migrations in NNN order (UP only on normal runs)
- Roll back one migration at a time (`down` command, last applied first)
- Track applied migrations in `00_schema_migrations.applied_migrations`
- CLI: `uv run python -m scripts.migrate up|down|status`
- Safe for use in CI/CD pipelines and fresh deployments

**Out of scope:**
- Parallel migration execution (always sequential)
- Branching or merge conflict detection
- Auto-generating SQL from Python models
- Web UI

## Sub-features

See `feature.manifest.yaml` for the full list and build order.

## Dependencies

- Depends on: none (bootstraps itself; runs before any feature schema exists)
- Depended on by: every other feature (all migrations flow through this runner)
