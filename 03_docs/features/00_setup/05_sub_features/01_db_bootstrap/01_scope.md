## DB Bootstrap — Scope

## What it does

Phase 1 of the install wizard. Establishes the DB layer tennetctl needs to
run: three Postgres roles with the correct privilege matrix, a `tennetctl`
database owned by the admin role, and every schema migration applied. At
the end of Phase 1 the database is in its full runtime shape but the vault
row does not yet exist and nothing has been seeded.

This sub-feature supports two modes that converge on the same final state.

## Mode A — Superuser bootstrap

The operator provides a Postgres superuser DSN. The wizard:

1. Connects as the superuser.
2. Generates three strong passwords with `secrets.token_urlsafe(32)`.
3. Creates the three roles (`tennetctl_admin`, `tennetctl_write`,
   `tennetctl_read`) with those passwords.
4. Creates the `tennetctl` database owned by `tennetctl_admin`.
5. Grants the privilege matrix described below.
6. Closes the superuser connection and **forgets the superuser DSN**.
7. Opens a new connection as `tennetctl_admin` using the generated
   admin DSN and applies the migrator bootstrap migration by hand.
8. Invokes `scripts.migrate up` (imported as a module) to apply every
   other pending migration.

The three generated passwords are held in `InstallState` in wizard memory
until Phase 2 writes them into the vault, then zeroed. The operator never
sees them.

## Mode B — Pre-provisioned DSNs

The operator has already created the database and the three roles (via
Terraform, their cloud provider's managed Postgres UI, etc.) and provides
three DSNs. The wizard:

1. Verifies each DSN can connect.
2. Verifies the admin DSN has `CREATE SCHEMA` privilege by creating and
   dropping a scratch schema `_tennetctl_preflight`.
3. Verifies the write DSN can `INSERT` and `SELECT` on a scratch table
   owned by admin.
4. Verifies the read DSN can `SELECT` from the scratch table but is
   **denied** `INSERT` — if the insert succeeds, the read role has
   excess privileges and the wizard aborts.
5. Drops the scratch table and schema.
6. Applies the migrator bootstrap migration via the admin DSN.
7. Invokes `scripts.migrate up` via the admin DSN.

Mode B never touches roles or databases — it treats them as preconditions
and verifies them. Any missing or excess privilege is a hard error.

## Privilege matrix

| Role              | DDL (CREATE/DROP/ALTER) | SELECT | INSERT/UPDATE | DELETE | Use case                          |
| ----------------- | ----------------------- | ------ | ------------- | ------ | --------------------------------- |
| `tennetctl_admin` | ✓ (all schemas)         | ✓      | ✓             | ✓      | Migrations, schema changes only   |
| `tennetctl_write` | —                       | ✓      | ✓             | ✓      | Runtime app connection            |
| `tennetctl_read`  | —                       | ✓      | —             | —      | Reporting, BI, read-only dashboards |

Mode A creates these grants as part of the role creation step. Mode B
verifies them by probe (create + insert + select + denied-insert).

### SQL for Mode A

```sql
-- Run as superuser, in the target cluster's default database.

CREATE ROLE tennetctl_admin LOGIN PASSWORD :'admin_pw';
CREATE ROLE tennetctl_write LOGIN PASSWORD :'write_pw';
CREATE ROLE tennetctl_read  LOGIN PASSWORD :'read_pw';

CREATE DATABASE tennetctl OWNER tennetctl_admin;

-- Switch to the tennetctl database for the rest
\connect tennetctl

-- Admin owns the public schema (legacy PG default); revoke from PUBLIC.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT  ALL ON SCHEMA public TO tennetctl_admin;

-- Write and read roles will be granted per-schema inside each migration,
-- but they need CONNECT on the database and USAGE will be granted by
-- the per-schema migration for 00_schema_migrations (the first migration).
GRANT CONNECT ON DATABASE tennetctl TO tennetctl_write, tennetctl_read;

-- Default privileges: anything created by tennetctl_admin in any future
-- schema grants SELECT to read and SELECT/INSERT/UPDATE/DELETE to write.
ALTER DEFAULT PRIVILEGES FOR ROLE tennetctl_admin
    GRANT SELECT ON TABLES TO tennetctl_read;

ALTER DEFAULT PRIVILEGES FOR ROLE tennetctl_admin
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO tennetctl_write;

ALTER DEFAULT PRIVILEGES FOR ROLE tennetctl_admin
    GRANT USAGE, SELECT ON SEQUENCES TO tennetctl_write;
```

The `ALTER DEFAULT PRIVILEGES` calls are the load-bearing part: after
they run, every subsequent `CREATE TABLE` in a migration automatically
gets the right grants without each migration having to remember to
write `GRANT ... TO tennetctl_write` by hand.

## Migration apply

Once the DB layer is in place (either mode) Phase 1 applies migrations:

```text
Step 1: bootstrap migration (applied by hand)
  FILE: 03_docs/features/01_sql_migrator/05_sub_features/00_bootstrap/
        09_sql_migrations/02_in_progress/20260408_000_schema_migrations_bootstrap.sql
  HOW:  read the file, execute it on the admin connection in one tx
  WHY:  the runner can't track itself — it needs the applied_migrations
        table to exist before it can do anything

Step 2: every other pending migration (applied by the runner)
  HOW:  import scripts.migrate as a module and call
        migrate.run_up(admin_dsn=state.admin_dsn)
  WHY:  the runner has proper transaction handling, checksum tracking,
        and dependency ordering; re-implementing it in the wizard would
        drift
```

The wizard does **not** reach into the migrator's SQL directly after the
bootstrap file. All subsequent migrations go through the normal runner
path. This means `00_setup` has only one piece of hand-rolled SQL apply
code (the bootstrap), and it's identical to what the migrator scope
document describes as the manual-apply step.

## In scope

- Prompts for Mode A/B selection and mode-specific DSN capture
  (delegated to `00_wizard`'s prompt helpers)
- Mode A: role creation, database creation, privilege grant matrix
- Mode A: password generation via `secrets.token_urlsafe(32)`
- Mode B: DSN connection verification
- Mode B: privilege verification via probe (create/insert/deny-insert)
- Hand-apply of the `01_sql_migrator/00_bootstrap` migration
- Invocation of `scripts.migrate up` (as a Python import, not a subprocess)
- Returning three verified DSNs to the wizard in `InstallState`
- Dropping the superuser connection (Mode A) after role creation

## Out of scope

- Creating extensions (`uuid-ossp`, `pgcrypto`) — the migrations do this
  as needed
- Tuning Postgres configuration (`shared_buffers`, `work_mem`, etc.) —
  that's an operator/ops concern, not install
- Row-Level Security policy creation — individual migrations handle RLS
  within each feature schema
- Backup configuration — out of band
- Connection pooling (pgbouncer) — out of band
- Verifying disk space or Postgres version — future enhancement (would
  be a nice preflight but not blocking)
- Rolling back created roles on Phase 1 failure — the operator fixes
  the issue and re-runs; `CREATE ROLE IF NOT EXISTS` is not valid SQL
  so retries catch duplicate-role errors and move on

## Acceptance criteria

### Mode A

- [ ] Superuser DSN can be supplied via `--superuser-dsn` or interactive
      prompt; prompt masks the password portion
- [ ] Three roles are created with 32-byte urlsafe passwords
- [ ] `tennetctl` database is created with `tennetctl_admin` as owner
- [ ] `ALTER DEFAULT PRIVILEGES` grants are in place for both read and
      write roles
- [ ] Superuser connection is closed and the superuser DSN is removed
      from `InstallState` before Phase 1 returns
- [ ] Re-running Phase 1 in Mode A on a partial install
      (e.g. admin role exists but `tennetctl_write` does not) detects
      existing roles and re-uses them rather than failing on duplicate
- [ ] Re-running Phase 1 with different superuser credentials does not
      regenerate the role passwords if the roles already exist — it
      aborts with a clear message because the wizard has no way to
      recover the existing passwords

### Mode B

- [ ] All three DSNs are prompted or flagged
- [ ] Admin DSN can `CREATE SCHEMA` and `DROP SCHEMA`
- [ ] Write DSN can `INSERT` and `SELECT` on an admin-owned table
- [ ] Read DSN can `SELECT` on an admin-owned table
- [ ] Read DSN `INSERT` is rejected with a privilege error; test passes
      ONLY on the expected error, not on any error
- [ ] Scratch schema and table are dropped even on verification failure
- [ ] Any verification failure aborts Phase 1 with a specific message
      naming the failing privilege

### Migration apply

- [ ] The bootstrap migration is applied exactly once
- [ ] `applied_migrations` contains a row with `sequence = 0` after
      bootstrap apply
- [ ] `scripts.migrate up` is invoked and applies every pending
      migration in sequence order
- [ ] On migration failure, the wizard prints the failing migration's
      filename and the Postgres error verbatim
- [ ] Re-running Phase 1 detects that migrations are already applied
      and skips directly to Phase 2 (delegated to the wizard's phase
      detection)

### State handoff

- [ ] `InstallState.admin_dsn`, `write_dsn`, `read_dsn` are populated
      with fully-qualified connection strings (not just passwords)
- [ ] `InstallState.superuser_dsn` is `None` after Phase 1 returns
      (even on failure paths)

## Dependencies

- Depends on: `01_sql_migrator.00_bootstrap` (the SQL file that Phase 1
  applies by hand)
- Depends on: `01_sql_migrator.01_runner` (for `scripts.migrate up`)
- Depends on: every feature's `00_bootstrap` migrations landing under
  `03_docs/features/*/05_sub_features/00_bootstrap/09_sql_migrations/`
  — the runner picks them up automatically by sequence number
- Depended on by: `00_wizard` (which calls this phase), `02_vault_init`
  (which needs the schema to exist), `03_first_admin` (which needs
  `03_iam.10_fct_users`)
