# Setup — Sub-Features

Build order is strict and sequential. Each phase depends on the one before it.
There is no bootstrap schema sub-feature here — `00_setup` owns no tables.
All schema it touches belongs to `01_sql_migrator`, `02_vault`, or `03_iam`.

## 00_wizard

The interactive CLI shell itself — the top-level `tennetctl setup` command,
its prompt loop, input validation, confirmation screens, and
resume-from-phase logic. Locates Postgres via the `$DATABASE_URL` env var
and detects phase by querying `00_schema_migrations` (migrations table,
`system_meta`, and `10_fct_settings`). Does not write any filesystem state;
delegates every mutation to the other sub-features.

## 01_db_bootstrap

Phase 1. Captures DB access in either Mode A (superuser bootstrap) or
Mode B (pre-provisioned DSNs). Creates the three Postgres roles, verifies
the privilege matrix, and hands three verified DSNs back to the wizard.
Also applies `01_sql_migrator/00_bootstrap` by hand and runs
`scripts.migrate up` for every subsequent migration. At the end of this
phase the DB has the full schema but the vault is not yet initialized.

## 02_vault_init

Phase 2. Prompts for unseal mode (manual / kms_azure / ...), collects
the mode-specific config (two SHA-256 keys for manual; Key Vault URL +
key name + key version for kms_azure), calls
`vault_setup_service.init_vault()` to wrap the MDK, and then seeds the
three DB DSNs into the vault at `tennetctl/db/admin_dsn`, `write_dsn`,
`read_dsn`. At the end of this phase the vault is initialized and sealed,
and every runtime secret the app needs is in the vault.

## 03_first_admin

Phase 3. Prompts for first admin username, email, password (with Argon2id
hashing), inserts into `03_iam.10_fct_users` with `account_type_id =
default_admin` and `auth_type_id = username_password`, and writes the
final `system_meta` row with `installed_at = now()`. At the end of this
phase an admin user exists but runtime settings have not been seeded yet.

## 04_settings

Phase 4. Seeds the runtime settings rows in
`"00_schema_migrations"."10_fct_settings"` — one row per mandatory setting
required for app startup, including `global.env` (taken from the
`$TENNETCTL_ENV` flag/prompt). All inserts use
`ON CONFLICT (scope, key) DO NOTHING` so re-runs are idempotent. After
the rows land, the wizard prints the write-role DSN once with
copy-to-secrets-manager instructions — this is the operator's only
chance to capture it, as the wizard intentionally writes no filesystem
state. At the end of this phase the install is complete and the operator
can start the server.

## Build order

```text
00_wizard   ←─ shell only, depends on 01/02/03/04 for actual work
01_db_bootstrap
02_vault_init
03_first_admin
04_settings
```

The wizard can be built first with stubs for the other four, or all five
in parallel once the CLI plumbing is in place. Either way, they must all
land before the feature is usable.
