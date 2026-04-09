# SQL Migrator Runner — Scope

## What it does

A Python CLI (`scripts/migrate.py`) that:
1. Discovers all `migration.yaml` files across every feature sub-feature
2. Builds a globally sorted list of SQL migration files ordered by NNN sequence
3. Queries `00_schema_migrations.applied_migrations` to find what has already run
4. Applies pending migrations in order (UP section only), recording each in the tracking table
5. Supports rolling back the last applied migration (DOWN section)
6. Validates migration manifests without touching the database

## In scope

- `migrate up` — apply all pending migrations in sequence order
- `migrate down` — roll back the most recently applied migration
- `migrate down --to N` — roll back all migrations with sequence > N
- `migrate status` — list applied vs pending migrations with sequences and filenames
- `migrate validate` — parse all `migration.yaml` files, check for duplicate sequences,
  missing files, and malformed SQL (UP/DOWN section detection)
- Checksum validation on every `up` run (warn if applied file changed on disk)
- Exit code 0 on success, non-zero on any error (CI-safe)
- Atomic migration: each SQL file runs in a transaction; rolled back on error

## Out of scope

- Parallel migration execution
- Auto-generating SQL from Python models or schemas
- Web UI or dashboard
- Cloud-provider deployment hooks
- Multi-database support (Postgres only)

## Acceptance criteria

- [ ] `migrate up` on a fresh database (after bootstrap) applies all pending migrations
      in NNN order and inserts a row into `applied_migrations` for each
- [ ] Re-running `migrate up` when nothing is pending exits 0 and prints "Nothing to apply"
- [ ] `migrate status` shows applied migrations (with timestamps) and pending ones
- [ ] `migrate down` rolls back the last applied migration and removes its row from tracking
- [ ] `migrate validate` reports errors for duplicate NNN values or missing files
- [ ] Checksum mismatch prints a warning but does not block `up` for unapplied migrations
- [ ] Checksum mismatch on an already-applied migration prints a loud warning
- [ ] If a SQL file is missing a DOWN section, `migrate down` refuses and exits non-zero
- [ ] A failed migration (SQL error) rolls back the transaction and exits non-zero

## Dependencies

- Depends on: `00_bootstrap` (tracking schema must exist before runner can run)
- Depended on by: every other feature build (they all use `migrate up`)
