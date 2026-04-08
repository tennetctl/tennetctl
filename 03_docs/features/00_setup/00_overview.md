# Setup — First-Run Install Workflow

## What this feature does

`00_setup` is the first-run installer for tennetctl. A single CLI command —
`tennetctl setup` — walks the operator through the full install in four
phases:

1. **DB access** — either bootstrap fresh Postgres roles from a superuser
   (Mode A), or accept three pre-provisioned DSNs (Mode B).
2. **Schema bootstrap** — apply the migrator bootstrap migration by hand,
   then run the full migration runner to land every `02_in_progress/*.sql`
   file in NNN order.
3. **Vault init** — pick an unseal backend (manual, kms_azure, etc.),
   generate the MDK, wrap it with the chosen backend, seed the three DB
   DSNs into the vault.
4. **First admin** — create the `default_admin` user with a username +
   password (Argon2id hash) in `03_iam.10_fct_users`.

The installer is idempotent in both directions: it refuses to clobber an
existing install (checks `00_schema_migrations.system_meta` and the
presence of seeded rows in `10_fct_settings`), and on partial failure it
records which phase succeeded in `system_meta` so re-running resumes
where it left off. The wizard locates Postgres via the `$DATABASE_URL`
env var — the single entry point for everything else.

## Why it exists

Before this feature, a fresh tennetctl deployment required:

- Manually creating three Postgres roles with the right privilege matrix
- Hand-applying the migrator bootstrap migration
- Running the migration runner with the right env var pointing at the admin DSN
- Hand-writing an `.env` file with the write DSN
- Running a separate CLI to init the vault with two SHA-256 keys
- Running another CLI to seed the three DSNs into the vault
- Running yet another CLI to create the first admin user

Eight steps, eight places to get it wrong, no idempotency. `00_setup`
collapses all of this into one interactive command that produces the same
state whether you're bootstrapping on a developer laptop (manual unseal
mode, SQLite-like simplicity) or an AKS cluster (Azure Key Vault auto-unseal,
workload identity, fully unattended pod restarts).

## Design philosophy

- **One command, one env var.** The `.env` file does not exist in a
  tennetctl deployment. The wizard and the runtime both take exactly one
  variable from the environment: `$DATABASE_URL`, the write-role Postgres
  DSN. Nothing else lives on disk. Every other runtime secret lives in
  the vault, and every other piece of runtime config lives in
  `"00_schema_migrations"."10_fct_settings"`.
- **Interactive CLI, not a web wizard.** Web wizards are hostile to CLI
  tools whose operators already have a terminal. Env-var-only installs
  (like Grafana) are hostile to zero-env-file deployments. The Mastodon /
  Sentry / Discourse pattern of a rich interactive CLI is the right fit.
- **CI override via flags, not env vars.** Every prompt has a matching
  `--flag` form so CI can run `tennetctl setup` non-interactively. But
  the canonical path is interactive, and all flags still write their
  values into the vault or into `10_fct_settings`, never into disk config.
- **Postgres is the single source of truth.** There is exactly one marker
  for "install is done": the row in `00_schema_migrations.system_meta`
  with `installed_at IS NOT NULL`, plus the seeded rows in
  `10_fct_settings`. No filesystem marker, no cross-check, no drift class
  of errors to reason about.
- **Never regenerates secrets on re-run.** If an install is half-done,
  rerunning `tennetctl setup` resumes the missing phases — it does **not**
  regenerate the MDK, root keys, or admin passwords. Regenerating secrets
  silently invalidates every previous session/token (the Supabase JWT-chain
  footgun).

## Two DB access modes

### Mode A — Superuser bootstrap

The operator hands the installer a Postgres superuser DSN (e.g.
`postgres://postgres:...@host/postgres`). The installer:

1. Generates three strong passwords with `secrets.token_urlsafe(32)`
2. Creates `tennetctl_admin`, `tennetctl_write`, `tennetctl_read` roles
3. Creates the `tennetctl` database owned by `tennetctl_admin`
4. Grants the privilege matrix (admin = DDL, write = SELECT/INSERT/UPDATE,
   read = SELECT only)
5. **Forgets the superuser DSN immediately** — it is never persisted
6. The three generated passwords are held in memory until they can be
   written into the vault in phase 3, then zeroed

The operator never sees the three generated passwords. They exist only
in the vault.

### Mode B — Pre-provisioned

The operator already created the database and the three roles (e.g. via
their platform's Postgres provisioning, or Terraform). They paste three
DSNs into the install prompt:

- admin DSN (must have `CREATE SCHEMA`)
- write DSN (must have `SELECT/INSERT/UPDATE`)
- read DSN (must be denied `INSERT`)

The installer verifies each by creating and dropping a scratch table as
admin, inserting+selecting as write, and asserting an insert-as-read is
rejected. Any failure aborts the install before any state is written.

Both modes converge on the same state: three verified DSNs held in memory,
ready to be seeded into the vault.

## Unseal mode selection

Between schema bootstrap and vault init, the installer prompts:

```text
How will the vault unseal itself on pod restart?

( ) manual     — I will paste the Root Unseal Key on every boot.
                  Good for local dev and single-VM deployments.

( ) kms_azure  — Pods auto-unseal via Azure Key Vault.
                  Requires: AKS + Workload Identity + a KV wrapping key
                  with Key Vault Crypto User granted to the pod's identity.

( ) kms_aws    — PLANNED (not available in v1)
( ) kms_gcp    — PLANNED (not available in v1)
```

The choice is persisted in `10_fct_vault.unseal_mode_id` and cannot change
without re-encrypting the MDK — a dedicated "rotate unseal backend"
ceremony we will build later if needed.

## Scope boundaries

**In scope:**

- Interactive CLI (`tennetctl setup`) with prompts + non-interactive flags
- Mode A and Mode B DB credential capture
- Applying the `01_sql_migrator/00_bootstrap` migration by hand
- Running `scripts.migrate up` for all subsequent migrations
- Unseal backend selection (prompts defined; implementations live in
  `02_vault`)
- Vault init (calls `vault_setup_service.init_vault()` directly, not via
  HTTP)
- Seeding `tennetctl/db/admin_dsn`, `write_dsn`, `read_dsn` into the vault
- First admin user creation in `03_iam.10_fct_users`
- Seeding mandatory rows into
  `"00_schema_migrations"."10_fct_settings"` (including `global.env`)
- Populating `00_schema_migrations.system_meta` with install state
- Idempotency guards and resume-from-phase logic (all driven by DB state)
- Printing the write DSN once at the end for operator capture, with
  clear "next steps" instructions

**Out of scope:**

- Web install wizard (no thanks)
- `.env` file generation (the whole point is no .env files)
- Multi-tenant install (one DB, one vault, one admin)
- Automated cloud resource provisioning (Azure Key Vault, the Postgres
  instance, the AKS cluster — those are Terraform's job, not ours)
- Unseal mode rotation (future)
- Admin password reset from the installer (future; for now the operator
  deletes the row and reruns the first-admin phase)

## Dependencies

- Depends on: `01_sql_migrator` (needs the runner to apply migrations)
  and `02_vault` (needs the `UnsealBackend` interface and the chosen
  concrete implementation) and `03_iam` (needs `10_fct_users` and the
  dim tables for account type / auth type)
- Depended on by: nothing — this is the entry point

## Dependents' view

Every other feature depends on `00_setup` having completed successfully.
The very first thing every feature's code does on startup is verify that
`system_meta.installed_at IS NOT NULL`. Features that run before install
is complete fail loud and refuse to start.
