# SQL Migrator Runner — Design

## File layout

```
scripts/
└── migrate.py          — CLI entry point (python -m scripts.migrate)

scripts/migrator/
├── __init__.py
├── config.py           — DB URL from env, repo root detection
├── discovery.py        — Find + parse all migration.yaml files
├── registry.py         — Build global ordered list, validate, diff vs applied
├── executor.py         — Apply UP/DOWN SQL, manage transactions
└── tracker.py          — Read/write applied_migrations table
```

## migration.yaml format (per sub-feature)

Every sub-feature with SQL migrations places a `migration.yaml` alongside its
`01_scope.md`. The runner discovers these by walking:

```
03_docs/features/*/05_sub_features/*/migration.yaml
```

### Full schema

```yaml
feature: "02_vault"               # must match parent feature folder name
sub_feature: "01_setup"           # must match this sub-feature folder name

migrations:
  - file: "20260408_002_vault_setup.sql"
    sequence: 2                   # NNN — globally unique integer, matches filename
    description: "Vault singleton table and status dim"
    depends_on: []                # list of sequence integers that must precede this
    reversible: true              # true = has a valid DOWN section
    notes: ""                     # optional free-text notes for humans
```

### Validation rules (enforced by `migrate validate`)

| Rule | Error |
|------|-------|
| `sequence` must match NNN in filename | `SEQUENCE_MISMATCH` |
| `sequence` must be unique across all manifests | `DUPLICATE_SEQUENCE` |
| `file` must exist at the expected path | `FILE_NOT_FOUND` |
| All `depends_on` values must reference existing sequences | `MISSING_DEPENDENCY` |
| File must contain `-- UP` and `-- DOWN` markers | `MISSING_SECTION` |

## SQL file format

Every migration file must have exactly these two section markers:

```sql
-- UP =========================================================================
... SQL statements for forward migration ...

-- DOWN =======================================================================
... SQL statements for rollback (must be a complete revert of UP) ...
```

The parser splits on `-- DOWN` (case-insensitive, surrounded by any whitespace).
Everything before is the UP section; everything after is the DOWN section.

## Execution model

```
migrate up:
  1. Parse all migration.yaml files → sorted list of MigrationEntry
  2. validate(): check sequences, deps, files, sections
  3. Query applied_migrations → set of applied sequences
  4. pending = [m for m in sorted_list if m.sequence not in applied]
  5. For each pending migration (in sequence order):
     a. Read file, compute SHA-256 checksum
     b. Extract UP section
     c. BEGIN TRANSACTION
     d. Execute UP SQL
     e. INSERT INTO applied_migrations (sequence, filename, feature, sub_feature, checksum, ...)
     f. COMMIT
     g. Print: "[002] Applied: 20260408_002_vault_setup.sql (34ms)"
  6. Exit 0

migrate down:
  1. Query applied_migrations ORDER BY sequence DESC LIMIT 1 → last_applied
  2. Find migration file for last_applied.sequence
  3. Extract DOWN section
  4. BEGIN TRANSACTION
  5. Execute DOWN SQL
  6. DELETE FROM applied_migrations WHERE sequence = last_applied.sequence
  7. COMMIT
  8. Print: "[002] Rolled back: 20260408_002_vault_setup.sql"
  9. Exit 0

migrate status:
  1. Parse all manifests → global list
  2. Query applied_migrations → applied set
  3. Print table:
     SEQ  FILENAME                           STATUS     APPLIED_AT
     000  20260408_000_schema_...bootstrap   applied    2026-04-08 12:00:00
     001  20260408_001_vault_bootstrap       applied    2026-04-08 12:01:00
     002  20260408_002_vault_setup           applied    2026-04-08 12:01:05
     003  20260408_003_vault_project         pending    —
```

## Error handling

```
SQL error during UP  → ROLLBACK, delete from applied_migrations if inserted, exit 1
Missing DOWN section → refuse to run down, exit 1
Checksum mismatch (applied file changed) → print WARNING, continue up for unapplied
Duplicate sequence   → exit 1 before touching DB
Missing file         → exit 1 before touching DB
```

## Environment

The runner reads one environment variable:

```
DATABASE_URL=postgresql://tennetctl_admin:tennetctl_admin_dev@localhost:5432/tennetctl
```

The admin role is required because migrations may CREATE SCHEMA, CREATE TABLE, etc.
(the write role has no DDL privileges).

The runner must NOT be used with the write or read roles.

## Startup check

On every invocation, the runner checks that `00_schema_migrations.applied_migrations`
exists before doing anything else. If it does not exist, it prints:

```
ERROR: Tracking table not found. Apply the bootstrap migration first:
  docker compose exec postgres psql -U tennetctl_admin -d tennetctl \
    -f 03_docs/features/01_sql_migrator/05_sub_features/00_bootstrap/\
       09_sql_migrations/02_in_progress/20260408_000_schema_migrations_bootstrap.sql
```

Then exits 1.
