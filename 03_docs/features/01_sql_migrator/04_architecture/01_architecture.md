# SQL Migrator — Architecture

## Schema layout

```
00_schema_migrations
└── applied_migrations    — one row per applied migration file
```

The `00_schema_migrations` schema sorts before all feature schemas
(`01_sql_migrator`, `02_vault`, etc.) alphabetically and numerically, ensuring
it is always visible as the first schema to exist.

---

## Migration file discovery

The runner walks this glob pattern across the entire repo:

```
03_docs/features/*/05_sub_features/*/09_sql_migrations/02_in_progress/*.sql
```

But it does **not** rely solely on filesystem ordering. Instead it reads
`migration.yaml` files (one per sub-feature) to get the authoritative ordered
list of migrations for that sub-feature. The global order is determined by the
three-digit NNN in each filename.

---

## migration.yaml — per sub-feature manifest

Every sub-feature that has SQL migrations MUST have a `migration.yaml` in its
directory alongside `01_scope.md`. This file declares:

```yaml
# 03_docs/features/{nn}_{feature}/05_sub_features/{nn}_{sub}/migration.yaml

feature: "02_vault"
sub_feature: "01_setup"
migrations:
  - file: "20260408_002_vault_setup.sql"
    sequence: 2
    description: "Vault singleton table and status dim"
    depends_on: []       # list of NNN values that must be applied before this one
    reversible: true     # has a valid DOWN section
```

Rules:
- `sequence` must match the NNN in the filename — the runner validates this
- `sequence` values must be globally unique across ALL features and sub-features
- `depends_on` is informational — the runner orders by sequence anyway, but
  the manifest makes dependencies explicit and detectable

---

## Global ordering algorithm

```
1. Find all migration.yaml files in 03_docs/features/*/*/05_sub_features/*/
2. Parse each: collect { sequence, file_path, feature, sub_feature, depends_on }
3. Sort all entries by sequence (integer ascending)
4. Validate: no duplicate sequences, no missing depends_on, all file paths exist
5. Query applied_migrations for the set of already-applied sequences
6. Diff: pending = sorted_all − applied
7. Apply each pending migration in sequence order
```

---

## Tracking table: applied_migrations

```sql
CREATE TABLE "00_schema_migrations"."applied_migrations" (
    sequence         SMALLINT    NOT NULL,   -- NNN from filename (unique)
    filename         TEXT        NOT NULL,   -- full filename (no path)
    feature          TEXT        NOT NULL,   -- e.g. "02_vault"
    sub_feature      TEXT        NOT NULL,   -- e.g. "01_setup"
    checksum         TEXT        NOT NULL,   -- SHA-256 of file contents
    applied_at       TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    applied_by       TEXT        NOT NULL DEFAULT current_user,
    execution_ms     INTEGER,                -- how long the UP section took

    CONSTRAINT pk_applied_migrations         PRIMARY KEY (sequence),
    CONSTRAINT uq_applied_migrations_file    UNIQUE (filename)
);
```

The `checksum` column catches cases where a migration file is modified after
being applied — the runner warns loudly if checksum mismatches but does not
re-apply (it never re-applies an applied migration).

---

## CLI commands

```bash
# Apply all pending migrations (normal deploy command)
uv run python -m scripts.migrate up

# Show status: applied vs pending
uv run python -m scripts.migrate status

# Roll back the last applied migration (runs DOWN section)
uv run python -m scripts.migrate down

# Roll back to a specific sequence number
uv run python -m scripts.migrate down --to 5

# Validate migration.yaml files without applying anything
uv run python -m scripts.migrate validate

# Apply a single specific migration (for debugging)
uv run python -m scripts.migrate up --only 7
```

---

## Sequence number allocation

NNN values are globally unique across all features and sub-features.

```
001 — 01_sql_migrator / 00_bootstrap  (bootstraps the tracking schema)
002 — 02_vault / 01_setup             (first vault migration)
...
```

The migrator's own bootstrap (NNN=001) is special: it is applied by hand once
(before the runner exists), then the runner takes over for everything after.

After the runner lands, all future migrations are applied via `migrate up`.

---

## Invariants

1. Once a migration is applied, it is never re-applied (sequence PK enforces this).
2. Checksum mismatch on an applied file is an error — alert loudly, do not apply.
3. The DOWN section is never run automatically — only on explicit `down` command.
4. Migrations apply in strict sequence order — no parallel execution.
5. The runner exits non-zero if any migration fails — safe for CI pipelines.
6. Every migration file must have both an UP section and a DOWN section.
