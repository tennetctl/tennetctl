# SQL Migrator Bootstrap — Scope

## What it does

Creates the `"00_schema_migrations"` Postgres schema and two tables:

1. `applied_migrations` — the runner's tracking table (one row per applied
   SQL file)
2. `system_meta` — the install-state singleton that records *when* the
   install completed, *who* the first admin was, and *which* unseal mode the
   vault is running under. This is the single DB-side install marker the
   `00_setup` feature and the runtime both read on every boot — there is
   no filesystem counterpart.

This is the only migration in the entire project that is applied by hand
(via `psql`) rather than by the runner — because the runner does not exist yet
when this runs.

## In scope

- `CREATE SCHEMA "00_schema_migrations"`
- `applied_migrations` table with all columns, constraints, indexes, and COMMENTs
- `system_meta` singleton table (enforced by `CHECK (id = 1)`) with columns for
  `installed_at`, `installer_version`, `first_admin_username`,
  `first_admin_created_at`, `vault_initialized_at`, `last_migration_at`
- Grant schema and table access to `tennetctl_read` and `tennetctl_write` roles
- Matching DOWN section that drops everything cleanly

## Out of scope

- The Python runner code (that is `01_runner`)
- The install wizard code (that is `00_setup/00_wizard`)
- Any application feature schema
- Populating `system_meta` — the install wizard does that in its final step

## Acceptance criteria

- [ ] `\dn` shows `00_schema_migrations`
- [ ] `\dt "00_schema_migrations".*` shows `applied_migrations` and `system_meta`
- [ ] `\d "00_schema_migrations".applied_migrations` shows all columns and constraints
- [ ] `\d "00_schema_migrations".system_meta` shows the singleton constraint
- [ ] `INSERT INTO system_meta VALUES (2, ...)` fails the `CHECK (id = 1)` constraint
- [ ] Migration round-trips: UP → DOWN → UP on a fresh database
