# Setup — Implementation Plan

Concrete, ordered steps to get `00_setup` built and a fresh `tennetctl`
install reachable from zero. This is the execution plan for the
Option-A architecture: Postgres is the single source of truth,
`$DATABASE_URL` is the one env var, no filesystem state.

Every step lists the artifact produced, the files touched, and the
exit criterion (what "done" means for that step). Steps are strictly
sequential unless marked `[parallel]`.

---

## Prerequisites

Before any code is written:

- Postgres 16+ reachable locally (docker-compose already in repo root).
- `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
- `$DATABASE_URL` export convention agreed: write-role DSN, nothing else.
- `$TENNETCTL_ENV` convention agreed: one of `dev | staging | prod`.
- Read these four docs end-to-end:
  - [00_overview.md](00_overview.md)
  - [01_sub_features.md](01_sub_features.md)
  - [04_architecture/01_architecture.md](04_architecture/01_architecture.md)
  - [05_sub_features/00_wizard/02_design.md](05_sub_features/00_wizard/02_design.md)

---

## Step 0 — Repo scaffolding

**Artifact:** empty Python package ready to grow.

1. Create `scripts/setup/` with `__init__.py`.
2. Add sub-package dirs: `wizard/`, `db_bootstrap/`, `vault_init/`,
   `first_admin/`, `settings/`.
3. Add a stub `scripts/setup/__main__.py` that parses
   `tennetctl setup --help` and exits 0.
4. Wire `[project.scripts] tennetctl = "scripts.cli:main"` into
   `pyproject.toml`; the `setup` subcommand calls `scripts.setup.main`.
5. Add `pytest` + `pytest-asyncio` + `asyncpg` to dev deps if not
   already present.

**Exit:** `uv run tennetctl setup --help` prints a usage line.

---

## Step 1 — `01_sql_migrator/00_bootstrap` migration

**Artifact:** the one hand-applied SQL file that creates
`"00_schema_migrations"` schema plus three tables:
`applied_migrations`, `system_meta`, `10_fct_settings`.

1. Verify
   [20260408_000_schema_migrations_bootstrap.sql](../01_sql_migrator/05_sub_features/00_bootstrap/09_sql_migrations/02_in_progress/20260408_000_schema_migrations_bootstrap.sql)
   matches the current architecture (no drift comments — already
   cleaned in the Option-A pass).
2. Add `10_fct_settings` to the same file if it is not there yet
   (scope, key, value, value_type, value_secret, created_at,
   updated_at; `UNIQUE (scope, key)`, `chk_settings_scope` on
   `^[0-9a-z_]+$`). See
   [04_settings/01_scope.md](05_sub_features/04_settings/01_scope.md).
3. Seed the five IAM runtime settings rows as part of the migration
   (optional — can also be done by the wizard; pick one and stick with
   it). Recommendation: DDL lives in the migration; **data lives in
   the wizard Phase 4** so re-seeding is a wizard concern, not a
   migration concern.
4. `psql "$DATABASE_URL_SUPER" -f <file>` against a throwaway DB;
   confirm the three tables exist with correct grants.

**Exit:** applying the file twice by hand raises `duplicate_table` on
the second run (confirms non-idempotent DDL as expected for a
hand-applied bootstrap).

---

## Step 2 — `01_sql_migrator` runner (minimal)

**Artifact:** `scripts/migrator/run.py` that applies every
`02_in_progress/*.sql` file in lexical order against
`$DATABASE_URL_ADMIN` and records them in `applied_migrations`.

1. Read every sub-feature's `09_sql_migrations/02_in_progress/` dir.
2. Sort by filename (`YYYYMMDD_NNN_*.sql`).
3. For each file not already in `applied_migrations`:
   - Open a transaction, run the `-- UP ====` block, insert a row
     into `applied_migrations`, commit.
   - On failure: rollback, print the filename, exit non-zero.
4. Expose as `scripts.migrate:up`.

**Exit:** `uv run python -m scripts.migrator up` is idempotent on a
bootstrapped DB (prints "nothing to apply" on second run).

---

## Step 3 — `InstallState` + error hierarchy

**Artifact:** `scripts/setup/wizard/state.py` and `errors.py`.

1. `InstallState` dataclass with these fields only:
   `install_id: str | None`, `env: str | None`,
   `superuser_dsn: SecretStr | None`, `admin_dsn: SecretStr | None`,
   `write_dsn: SecretStr | None`, `read_dsn: SecretStr | None`,
   `unseal_mode: str | None`, `unseal_config: dict | None`,
   `installed_at: datetime | None`.
2. `zero()` method that overwrites every `SecretStr` with empty and
   sets the rest to None.
3. Error classes: `WizardError` (base), `Phase0Error`, `Phase1Error`,
   `Phase2Error`, `Phase3Error`, `Phase4Error`, `AbortedByUser`.
   **No `DriftError`.**
4. Unit tests: `zero()` really zeroes, equality works, no
   `config_path`/`drift_detected` fields exist.

**Exit:** `pytest scripts/setup/wizard/tests/test_state.py` green.

---

## Step 4 — `detect_phase` function

**Artifact:** `scripts/setup/wizard/detect_phase.py`.

Given a write-role connection, returns a `Phase` enum value:

```text
Phase.FRESH         — applied_migrations empty OR missing bootstrap row
Phase.MIGRATIONS    — bootstrap applied, not all migrations applied
Phase.VAULT         — migrations done, 10_fct_vault row missing/partial
Phase.ADMIN         — vault initialized + DSNs seeded, system_meta.installed_at IS NULL
Phase.SETTINGS      — system_meta.installed_at NOT NULL, 10_fct_settings missing (scope='global', key='env')
Phase.DONE          — all of the above, plus global.env row present
```

1. Pure read-only SQL, one function per check.
2. Unit tests using an in-memory snapshot harness or a real throwaway
   DB (pick one; stick with it).

**Exit:** six tests, one per phase, all green against a seeded
fixture DB.

---

## Step 5 — Sub-feature 01_db_bootstrap

**Artifact:** `scripts/setup/db_bootstrap/entrypoint.py` +
`prompts.py` + `mode_a.py` + `mode_b.py`.

1. Prompt superuser DSN (Mode A) or three DSNs (Mode B).
2. Mode A: `CREATE ROLE` × 3, generate passwords with
   `secrets.token_urlsafe(32)`, `CREATE DATABASE`, grant privilege
   matrix.
3. Mode B: connect as each role, run the verification queries from
   [01_db_bootstrap/02_design.md](05_sub_features/01_db_bootstrap/02_design.md).
4. Apply bootstrap migration by hand (read the file, execute against
   admin DSN).
5. Call `scripts.migrate.up(admin_dsn)` for the rest.
6. Populate `state.admin_dsn / write_dsn / read_dsn`.

**Exit:** running Phase 1 against a fresh Postgres leaves you with a
full schema, three verified DSNs in `state`, and
`applied_migrations` populated.

---

## Step 6 — `02_vault` service layer (stub-friendly)

**Artifact:** enough of `backend/02_features/vault/` to let Phase 2
import `vault_setup_service.init_vault()` and
`vault_secret_service.create_secret()`.

This is a **parallel track** with Steps 5 and 7 — the wizard only
needs the Python import surface, not the HTTP routes.

1. `init_vault(conn, *, mode, config) -> {mdk, initialized_at}`
   - Generate 32-byte MDK.
   - Wrap with backend (manual: XOR-split; kms_azure: Key Vault
     wrap).
   - Insert `10_fct_vault` row with `status='sealed'`.
2. `create_secret(conn, vault_state, path, value, secret_type)`
   - AES-256-GCM encrypt `value` with `vault_state.mdk`.
   - Insert `14_fct_secret_versions` row.

**Exit:** integration test creates a vault, seeds one secret, reads
it back after unsealing — all via Python imports, no HTTP.

---

## Step 7 — Sub-feature 02_vault_init

**Artifact:** `scripts/setup/vault_init/entrypoint.py` +
`prompts.py`.

1. Prompt unseal mode (manual / kms_azure / others disabled).
2. Collect mode-specific config.
3. Inside an admin connection transaction:
   - Call `vault_setup_service.init_vault(...)`.
   - Seed the three DSN secrets via `vault_secret_service.create_secret`.
   - `UPDATE system_meta SET vault_initialized_at = now(),
      unseal_mode = ...`.
4. Clear `state.read_dsn`; keep `state.admin_dsn` and
   `state.write_dsn` alive (needed by Phases 3–4).
5. Best-effort zero of the MDK variable.

**Exit:** Phase 2 leaves `10_fct_vault` populated, three DSN paths
present in `14_fct_secret_versions`, `system_meta.vault_initialized_at`
set.

---

## Step 8 — Sub-feature 03_first_admin

**Artifact:** `scripts/setup/first_admin/entrypoint.py` +
`prompts.py` + `hash.py`.

1. Prompt username / email / password (twice) with validation per
   [03_first_admin/01_scope.md](05_sub_features/03_first_admin/01_scope.md).
2. Argon2id hash **outside** the transaction (memory_cost=64MB).
3. Single transaction:
   - `INSERT INTO "03_iam"."10_fct_users"` with `default_admin` +
     `username_password`.
   - Three `INSERT INTO "03_iam"."20_dtl_attrs"` (username, email,
     password_hash).
   - `UPDATE system_meta SET installed_at = now(),
     first_admin_username = ..., first_admin_created_at = now(),
     install_id = ...`.
4. Do **not** clear `state.admin_dsn` yet — Phase 4 needs it.

**Exit:** Phase 3 leaves one row in `10_fct_users`, three rows in
`20_dtl_attrs`, and `system_meta.installed_at IS NOT NULL`.

---

## Step 9 — Sub-feature 04_settings

**Artifact:** `scripts/setup/settings/entrypoint.py` +
`seed_rows.py`.

1. Compute the row set:
   - `(global, env, <state.env>, text, false)`
   - Five IAM runtime setting defaults (values from
     [04_settings/01_scope.md](05_sub_features/04_settings/01_scope.md)).
2. One transaction, one `INSERT ... ON CONFLICT (scope, key) DO
   NOTHING` per row (or a single multi-row insert — either works).
3. Print the write DSN **once** with this exact wording:

   ```text
   ┌────────────────────────────────────────────────────────────────┐
   │ IMPORTANT — capture the write DSN now                         │
   │                                                                │
   │ This is the only time tennetctl will show it. Copy it into    │
   │ your secrets manager and export it as $DATABASE_URL on every  │
   │ boot:                                                          │
   │                                                                │
   │   <write_dsn>                                                  │
   │                                                                │
   │ Press Enter once you have stored it. The wizard will then     │
   │ zero it from memory and exit.                                  │
   └────────────────────────────────────────────────────────────────┘
   ```
4. Wait for Enter, call `state.zero()`, exit 0.

**Exit:** Phase 4 leaves `10_fct_settings` populated and the wizard
process exits cleanly with no DSN left in memory.

---

## Step 10 — `run_setup` orchestrator

**Artifact:** `scripts/setup/wizard/run.py`.

1. Parse CLI flags (see
   [00_wizard/01_scope.md](05_sub_features/00_wizard/01_scope.md)):
   `--env`, `--mode`, `--unseal-mode`, plus per-mode config flags.
   **No `--config-path`.**
2. Connect to `$DATABASE_URL` (may not exist yet on a truly fresh
   install — that's Phase 1's job to produce).
3. Call `detect_phase`.
4. Dispatch to Phase 1/2/3/4 in order, starting from the detected
   phase.
5. `try/finally`: on exit, `state.zero()` unconditionally.
6. Phase errors bubble up with a human-readable banner; CLI exits
   non-zero.

**Exit:** `uv run tennetctl setup` on a fresh DB walks all four
phases and ends with "install complete" + the DSN print-out.

---

## Step 11 — End-to-end smoke test

**Artifact:** `tests/e2e/setup/01_fresh_install.robot` (Robot
Framework, per the project's test standard).

1. Stand up an ephemeral Postgres via docker-compose.
2. Run `tennetctl setup` with all flags pre-filled so it's
   non-interactive.
3. Assert:
   - `applied_migrations` contains every expected row.
   - `10_fct_vault.initialized_at IS NOT NULL`.
   - `14_fct_secret_versions` has three rows at the three DSN paths.
   - `10_fct_users` has exactly one row.
   - `system_meta.installed_at IS NOT NULL`.
   - `10_fct_settings` has a row at `(global, env)` matching
     `$TENNETCTL_ENV`.
4. Run `tennetctl setup` a second time; assert it prints "install
   already complete" and exits 0.

**Exit:** both runs pass in CI.

---

## Step 12 — Resume scenarios (unit-ish integration)

**Artifact:** `tests/setup/test_resume.py`.

Seed the DB into each intermediate state and assert the wizard picks
up from the right phase:

| Seeded state                                      | Expected phase |
| ------------------------------------------------- | -------------- |
| Nothing                                           | Phase 1        |
| Bootstrap migration only                          | Phase 1        |
| All migrations, no vault row                      | Phase 2        |
| Vault initialized, no admin user                  | Phase 3        |
| Admin user exists, `installed_at IS NOT NULL`,   | Phase 4        |
| no `global.env` settings row                      |                |
| Everything above + `global.env` row               | DONE (exit)    |

**Exit:** six tests, all green.

---

## Step 13 — Docs cross-check

**Artifact:** none (verification only).

1. Grep `03_docs/features` for `config.toml`, `DriftError`,
   `--config-path`, `drift_detected`, `config_path`. Only legitimate
   historical/rationale references should remain.
2. Grep `scripts/setup` for the same set. Zero matches expected.
3. Confirm [01_sub_features.md](01_sub_features.md) lists five
   sub-features (wizard + 1/2/3/4) and the build order matches the
   code.

**Exit:** clean grep; docs match code.

---

## Step 14 — Cut v0.1.0

**Artifact:** a tagged commit.

1. Update `pyproject.toml` version to `0.1.0`.
2. `git add .` (per project convention; no file-by-file staging).
3. Commit: `feat(00_setup): first-run install wizard (Option A, DB-only state)`.
4. Tag `v0.1.0`.

**Exit:** `git tag` shows `v0.1.0` on the current HEAD.

---

## Dependency graph

```text
Step 0 ──┐
         ├─► Step 1 ──► Step 2 ──┐
Step 3 ──┤                       ├─► Step 4 ──► Step 5 ──► Step 7 ──► Step 8 ──► Step 9 ──► Step 10 ──► Step 11 ──► Step 12 ──► Step 13 ──► Step 14
         │                       │                ▲
         └─ Step 6 [parallel] ───┘                │
              (vault service)                     │
              can start as soon as Step 0 done ───┘
```

Steps 6 and 5/7 can overlap if two people are working. Everything
else is sequential.

---

## Success criterion (the whole feature)

A fresh Mac with Postgres and `uv` can go from `git clone` to a
running tennetctl process in **under five minutes**, with exactly
these three operator actions:

1. `export DATABASE_URL_SUPER=postgres://postgres@localhost/postgres`
   (for the one-time bootstrap)
2. `uv run tennetctl setup --env dev` — answer five prompts
3. Copy the printed write DSN into `$DATABASE_URL`, run
   `uv run tennetctl serve`

Nothing on disk in `~/.tennetctl`. Nothing in a `.env` file. One env
var, one database, one running process.
