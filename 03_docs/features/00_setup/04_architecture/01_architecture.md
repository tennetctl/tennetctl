## Setup — Architecture

`00_setup` owns **no schema of its own**. It is a CLI-only feature that writes
into three other schemas (`00_schema_migrations`, `02_vault`, `03_iam`) and
**touches no filesystem state whatsoever**. This document explains how those
writes are ordered, why the ordering is non-obvious, and what happens when it
fails mid-flight.

---

## The chicken-and-egg problem

Every runtime secret tennetctl needs lives in the vault. The vault itself
needs a DB connection to read its own row. The DB connection string is itself
a secret. On a fresh install there is **no vault to read the DSN from yet**,
so we need a single bootstrap entry point the operator can supply before
anything else exists. That entry point is the `$DATABASE_URL` env var,
holding the write-role DSN.

```text
            ┌───────────────────────────┐
            │  $DATABASE_URL  (env)     │
            │  (write DSN, one var)     │
            └────────────┬──────────────┘
                         │ read on every boot
                         ▼
            ┌───────────────────────────┐
            │  Postgres                 │
            │  • 10_fct_settings        │
            │  • 10_fct_vault row       │
            └────────────┬──────────────┘
                         │ contains wrapped MDK
                         ▼
            ┌───────────────────────────┐
            │  Vault (MDK)              │
            │  → admin_dsn              │
            │  → write_dsn              │
            │  → read_dsn               │
            └───────────────────────────┘
```

The install wizard breaks the cycle by running in a **privileged bootstrap
mode** that already has the three DSNs in process memory, writes them all
into the vault in one transaction, and then seeds the runtime settings rows.
After the wizard exits, the operator keeps the write DSN in their secrets
manager and exports it as `$DATABASE_URL` on every subsequent boot — it is
the only piece of credential material the process needs to reach everything
else.

---

## Four-phase install diagram

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                      tennetctl setup  (one command)                    │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 0 — Preflight                                                    │
│  • Refuse if system_meta.installed_at IS NOT NULL AND 10_fct_settings  │
│    already contains a global.env row (fully installed)                 │
│  • Otherwise detect current phase from DB state and resume              │
│  • Print banner, ask operator to confirm target DB host                │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 1 — DB bootstrap  (01_db_bootstrap)                              │
│                                                                        │
│  Mode A (superuser)                      Mode B (pre-provisioned)      │
│  ──────────────────────                  ──────────────────────────    │
│  • prompt superuser DSN                  • prompt 3 DSNs (admin/       │
│  • generate 3 passwords                    write/read)                 │
│  • CREATE ROLE tennetctl_admin           • verify admin can CREATE     │
│  • CREATE ROLE tennetctl_write             SCHEMA                      │
│  • CREATE ROLE tennetctl_read            • verify write can            │
│  • CREATE DATABASE tennetctl               INSERT/SELECT               │
│  • GRANT privilege matrix                • verify read CANNOT          │
│  • drop superuser connection               INSERT                      │
│                                                                        │
│  Both modes converge →                                                 │
│  • apply 01_sql_migrator/00_bootstrap migration by hand                │
│    (creates 00_schema_migrations.applied_migrations, system_meta,      │
│     and 10_fct_settings)                                               │
│  • run `scripts.migrate up` for every other pending migration          │
│    (02_vault setup, 03_iam bootstrap, etc.)                            │
│                                                                        │
│  End state: full schema exists, 3 DSNs held in memory, no vault row,   │
│             no settings rows                                           │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 2 — Vault init  (02_vault_init)                                  │
│                                                                        │
│  • prompt unseal mode: manual | kms_azure | (kms_aws) | (kms_gcp)      │
│  • collect mode-specific config                                        │
│      manual:    two 64-hex-char root keys                              │
│      kms_azure: vault_url + key_name + key_version (pinned)            │
│  • call vault_setup_service.init_vault(mode, config) directly          │
│    (NOT via HTTP — the wizard holds an admin connection already)       │
│      → generates MDK                                                   │
│      → wraps MDK with chosen backend                                   │
│      → writes 10_fct_vault row (status=sealed, unseal_mode_id=...)    │
│      → returns MDK in memory to the wizard                             │
│  • seed the 3 DSNs into the vault at                                   │
│      tennetctl/db/admin_dsn                                            │
│      tennetctl/db/write_dsn                                            │
│      tennetctl/db/read_dsn                                             │
│    (uses the same vault_secret_service the runtime uses — no           │
│     special-case install writer)                                       │
│  • zero admin_dsn and read_dsn from wizard memory                      │
│    (write_dsn survives into Phase 4 for the final print-out)           │
│  • UPDATE system_meta SET vault_initialized_at = now(), unseal_mode=…  │
│                                                                        │
│  End state: vault initialized and sealed, all DSNs inside vault        │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 3 — First admin  (03_first_admin)                                │
│                                                                        │
│  • prompt username, email, password (twice)                            │
│  • validate: 8+ chars, at least one non-alpha                          │
│  • Argon2id hash (time_cost=3, memory_cost=64MB, parallelism=4)        │
│  • INSERT INTO "03_iam"."10_fct_users"                                 │
│       account_type_id = default_admin                                  │
│       auth_type_id    = username_password                              │
│  • INSERT into 20_dtl_attrs for username, email, password_hash         │
│  • UPDATE system_meta SET                                              │
│       installed_at         = now()                                     │
│       first_admin_username = <username>                                │
│       first_admin_created_at = now()                                   │
│                                                                        │
│  End state: system_meta.installed_at IS NOT NULL, but settings not     │
│             yet seeded — the install is NOT complete until Phase 4     │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 4 — Seed settings  (04_settings)                                 │
│  • INSERT mandatory rows into 10_fct_settings via                      │
│    ON CONFLICT (scope, key) DO NOTHING                                 │
│      - global.env     ← from $TENNETCTL_ENV or --env flag              │
│      - iam.*          ← defaults for the IAM runtime settings          │
│  • print the write DSN ONCE with copy-to-secrets-manager instructions │
│    (operator must capture it now — wizard holds no other state)       │
│  • zero write_dsn from wizard memory                                   │
│  • print "next steps" banner and exit 0                                │
└─────────────────────────────────────────────────────────────────────────┘
```

The order matters: settings are seeded **only after** the vault is
initialized and the first admin exists. If any earlier phase fails, the
settings rows are not written and `detect_phase` will correctly place the
next run at the right resume point.

---

## Sealed-boot state machine

After install, on every subsequent process boot, the server checks its
install markers (both in Postgres) before it will serve any HTTP traffic:

```text
process start
     │
     ▼
read $DATABASE_URL from environment
     │
     ├── unset ───────────────────────────► FATAL: "set DATABASE_URL"
     │
     ▼
connect to Postgres as write role
     │
     ├── connection refused ──────────────► FATAL: "bad write DSN or DB down"
     │
     ▼
SELECT * FROM "00_schema_migrations".system_meta WHERE id = 1
     │
     ├── installed_at IS NULL ────────────► FATAL: "install incomplete, run setup"
     │
     ▼
SELECT value FROM "00_schema_migrations"."10_fct_settings"
                WHERE scope='global' AND key='env'
     │
     ├── row missing ─────────────────────► FATAL: "install incomplete, run setup"
     │
     ▼
SELECT * FROM "02_vault".v_vault
     │
     ├── no row ──────────────────────────► FATAL: "vault not initialized"
     │
     ▼
dispatch on unseal_mode (see 02_vault/04_architecture)
     │
     ├── manual ──────► start HTTP in SEALED mode
     │                  only /v1/vault/{status,unseal,seal} + /healthz respond
     │
     └── kms_* ───────► call backend.unseal() via workload identity
                        → load write_dsn/read_dsn from vault
                        → start HTTP in OPERATIONAL mode
```

There is no cross-check against any filesystem marker — there is no
filesystem marker. `system_meta` plus `10_fct_settings` are the single
source of truth. A restored DB snapshot *is* its own install; there is no
second record that could disagree with it.

---

## Install-state persistence

Install state is tracked **entirely in Postgres**, in two complementary
locations:

### 1. `"00_schema_migrations".system_meta` row

Columns relevant to install state:

| Column                  | Set when                                              |
| ----------------------- | ----------------------------------------------------- |
| `id`                    | 1 (singleton, enforced by CHECK)                      |
| `install_id`            | Phase 3 (ULID, identity marker only)                  |
| `installer_version`     | Phase 0                                               |
| `vault_initialized_at`  | Phase 2 — after the vault row is written              |
| `unseal_mode`           | Phase 2                                               |
| `first_admin_username`  | Phase 3                                               |
| `first_admin_created_at`| Phase 3                                               |
| `installed_at`          | Phase 3 — the final write in the admin-insert tx      |

`install_id` is retained as an identity marker (useful for audit logs and
support tickets) but it is no longer cross-checked against anything
outside the DB.

### 2. `"00_schema_migrations".10_fct_settings` rows

Phase 4 seeds one row per mandatory runtime setting. The presence of a
`(scope='global', key='env')` row is the definitive "Phase 4 complete"
marker — `detect_phase` uses it to distinguish "admin done but settings
not seeded" from "fully installed".

### Why no filesystem marker

An earlier design used a `./.tennetctl/config.toml` file plus a drift
check between it and `system_meta`. That design traded a real class of
bugs (filesystem/DB drift across pod restarts, snapshot restores, and
`rm -rf .tennetctl/` accidents) for a defensive guard that never actually
fired in normal operation. Collapsing to a single DB-side source of truth
eliminates the entire `DriftError` code path, the `config.toml` writer,
and the startup file I/O — and makes snapshot restores work correctly
by construction.

---

## Resume-from-phase logic

Every phase writes its completion marker before returning. On re-run the
wizard reads `system_meta` and `10_fct_settings` and skips phases that are
already complete:

```text
Phase 1 complete when:  applied_migrations contains the bootstrap row
                        AND all expected migrations are in applied_migrations
Phase 2 complete when:  10_fct_vault has a row with initialized_at NOT NULL
                        AND the 3 DSN paths exist in the vault
Phase 3 complete when:  system_meta.installed_at IS NOT NULL
Phase 4 complete when:  10_fct_settings has a row at (scope='global', key='env')
```

On a re-run that finds Phase 1 done but Phase 2 incomplete, the wizard
jumps straight to the unseal-mode prompt and does **not** re-run migrations.
It never regenerates the MDK or root keys — if Phase 2 started but didn't
finish, the operator is told to either resume (if the row exists in
`sealed` state but no DSNs were seeded) or wipe the vault row (via a
documented manual SQL command) and start Phase 2 over. The wizard
deliberately does not automate destructive cleanup.

---

## Cross-feature invariants

1. `00_setup` is the only code that writes to `system_meta` during Phase 0–3
   and the only code that inserts the initial `10_fct_settings` seed rows in
   Phase 4. Runtime code only ever reads `system_meta`; settings may be
   edited later via the admin API, but the initial seeds are wizard-only.
2. `00_setup` calls `02_vault`'s `vault_setup_service` as a Python import,
   not over HTTP. The vault HTTP routes require the vault to be unsealed
   already — a chicken-and-egg we sidestep by going through the service layer.
3. `00_setup` creates exactly one row in `03_iam.10_fct_users` and nothing
   else. Subsequent users are created through `03_iam.01_auth` after the
   admin logs in.
4. `00_setup` is the only code that is allowed to run under a Postgres
   superuser connection (Mode A), and only during Phase 1. The superuser
   DSN is dropped before Phase 2 begins and is never written to any
   persistent store.

---

## Failure modes

| Failure                                  | Effect                                          | Recovery                                                                          |
| ---------------------------------------- | ------------------------------------------------ | --------------------------------------------------------------------------------- |
| Phase 1 fails during role creation       | No schema, no vault, no settings                 | Fix superuser permissions and re-run. Partial role creation is idempotent.        |
| Phase 1 fails during migration apply     | Partial schema, no vault, no settings            | Fix migration SQL, run `scripts.migrate up` manually, re-run setup to resume.     |
| Phase 2 fails during `init_vault`        | Schema exists, no vault row, no settings         | Fix unseal-mode config (e.g. Azure permissions) and re-run. Idempotent.           |
| Phase 2 fails after vault row written    | Vault initialized, DSNs not yet seeded           | Re-run setup; it detects the vault row and jumps to DSN seeding.                  |
| Phase 3 fails during admin insert        | Vault initialized, no admin user                 | Re-run setup; it detects an uninitialized admin and re-prompts.                   |
| Phase 4 fails during settings seed       | Admin exists, settings partial or absent         | Re-run setup; ON CONFLICT DO NOTHING makes the re-seed safe.                      |
| System crash mid-phase                   | Whatever got committed stays committed           | Re-run setup; idempotency guards skip completed work.                             |

The guiding principle: **no phase begins its writes until all prompts for
that phase are collected and validated**. This means there is no "half a
phase" state that requires manual DB cleanup — every failure point is
either "before the writes" (nothing to clean up) or "after the writes"
(the next phase's idempotency guard detects completion).
