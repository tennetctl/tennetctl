# SQL Migrator — Sub-Features

## Build order

### 00_bootstrap
Bootstraps the `00_schema_migrations` Postgres schema and the
`applied_migrations` tracking table. This is applied by hand exactly once on a
fresh database (before the runner itself exists). After that, every subsequent
deploy uses the runner.

### 01_runner
The Python migration runner (`scripts/migrate.py`). Reads `migration.yaml`
manifests, builds the global ordered list, diffs against `applied_migrations`,
and applies new SQL files. Exposes three CLI commands: `up`, `down`, `status`.
