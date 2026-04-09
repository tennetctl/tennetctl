## Setup Wizard — Scope

## What it does

Provides the `tennetctl setup` CLI command — the single entry point a new
operator runs to install tennetctl. Owns the prompt loop, argument parsing,
phase orchestration, and the final "next steps" banner. Does not touch
Postgres or the vault directly — every mutation is delegated to the four
phase sub-features (`01_db_bootstrap`, `02_vault_init`, `03_first_admin`,
`04_settings`).

The wizard writes no files. All install state lives in the database:
`system_meta` records install progress and the `10_fct_settings` table
holds every mutable runtime setting. At runtime the application locates
the database via the `$DATABASE_URL` env var and loads everything else
from `10_fct_settings`. There is no `config.toml`.

## CLI shape

```text
tennetctl setup [OPTIONS]

Options:
  --mode [a|b]             DB mode: 'a' = superuser bootstrap,
                           'b' = pre-provisioned DSNs. Prompts if omitted.

  --superuser-dsn URL      Mode A only. Postgres superuser DSN used to
                           create roles and database. Never persisted.

  --admin-dsn URL          Mode B only. Pre-provisioned admin DSN.
  --write-dsn URL          Mode B only. Pre-provisioned write DSN.
  --read-dsn URL           Mode B only. Pre-provisioned read DSN.

  --env [dev|staging|prod] Deployment environment. Seeded into the
                           global.env row of 10_fct_settings. Prompts if
                           omitted. Also read from $TENNETCTL_ENV.

  --unseal-mode CODE       manual | kms_azure | kms_aws | kms_gcp
                           Prompts if omitted.

  --root-unseal-key HEX    manual mode only. 64 lowercase hex chars.
  --root-read-key HEX      manual mode only. 64 lowercase hex chars.

  --azure-vault-url URL    kms_azure only. e.g. https://kv-prod.vault.azure.net/
  --azure-key-name NAME    kms_azure only. Wrapping key name.
  --azure-key-version VER  kms_azure only. Pinned version id.

  --admin-username NAME    First admin username.
  --admin-email EMAIL      First admin email.
  --admin-password PW      First admin password.
                           (CI only — interactive prompt is preferred.)

  --yes                    Accept all confirmation prompts.
  --resume                 Explicitly resume a partial install. Required if
                           system_meta has any non-NULL install columns.

  -h, --help               Show this help.
```

Every prompt has a matching `--flag` form so CI can run the wizard
non-interactively. When all flags are supplied, the wizard runs
straight through with no TTY interaction.

## Resume-from-phase behaviour

On startup the wizard reads `system_meta` (if the schema exists) and
computes the current phase state. `system_meta` in the database is the
single source of truth — there is no filesystem marker to cross-check.

```text
phase = 0                              # nothing started
  AND applied_migrations is empty
  AND system_meta row has id=1 with all install cols NULL

phase = 1                              # migrations done
  AND system_meta.vault_initialized_at IS NULL

phase = 2                              # vault seeded
  AND system_meta.first_admin_created_at IS NULL

phase = 3                              # admin created, settings not yet seeded
  AND system_meta.installed_at IS NOT NULL
  AND 10_fct_settings has no global.env row

phase = 4                              # fully installed
  AND system_meta.installed_at IS NOT NULL
  AND 10_fct_settings has a global.env row
```

If the wizard finds state in the range (0, 4), it prints the detected phase
and — unless `--resume` is passed — refuses to continue. This is deliberate:
silent resume after a half-install is how the Supabase JWT-chain footgun
happens. The operator has to explicitly acknowledge that they want to
continue from where the previous run failed.

On `phase = 4` the wizard exits with:

```text
tennetctl is already installed.
Install ID: 01JCX8R4V3Y2ZK7F9QH3W8XNMT
Installed:  2026-04-08T14:22:03Z

To wipe and reinstall, drop the tennetctl database and re-run setup.
The wizard will not destroy existing data on its own.
```

## In scope

- The `tennetctl setup` command, registered in `backend/01_core/cli.py`
  under the main Typer app.
- Argument parsing (Typer) with the full flag matrix above.
- Phase-state detection by querying `system_meta` and `10_fct_settings`
  via a short-lived connection (Mode A: uses superuser DSN; Mode B: uses
  admin DSN).
- Interactive prompts for any values not provided via flags. Uses
  `rich.prompt` for masked password input and `rich.console` for
  formatted output.
- Phase orchestration: call `01_db_bootstrap`, `02_vault_init`,
  `03_first_admin`, `04_settings` in order, pass results between phases
  via typed Python objects (no globals).
- Confirmation screens before each phase that writes DB state.
- Resume-from-phase logic that skips already-complete phases on re-run.
- Capture of the deployment environment (`--env` / `$TENNETCTL_ENV`)
  and forwarding it to Phase 4 for `global.env` seeding.
- Final output: the write DSN is printed exactly once with a clear
  instruction to copy it into the operator's secret manager, plus a
  "next steps" banner with the server start command.
- Error handling that translates phase failures into actionable messages
  with a link to the relevant runbook section.

## Out of scope

- Actual role creation, migration apply, vault init, admin creation, or
  settings seeding — all delegated to the phase sub-features.
- Writing any file to disk — the wizard is filesystem-free.
- Any HTTP serving — the wizard is a one-shot CLI command.
- Uninstall or teardown — dropping data is an operator responsibility.
- Admin password reset — future; for now the operator deletes the row
  by hand and re-runs Phase 3 via `tennetctl setup --resume`.
- Multi-environment install (dev + prod in one run) — each environment
  gets its own setup run.
- Storing or recovering the write DSN — the operator captures it once
  at install end and puts it into their own secret store.

## Acceptance criteria

### Command registration

- [ ] `tennetctl setup --help` shows the full flag matrix
- [ ] `tennetctl setup` with no args launches the interactive wizard
- [ ] All flags can be provided via env vars with `TENNETCTL_SETUP_` prefix
      (e.g. `TENNETCTL_SETUP_ADMIN_USERNAME`)
- [ ] `--env` is additionally resolvable from `$TENNETCTL_ENV`
      (no `TENNETCTL_SETUP_` prefix) to match the runtime env var name

### Phase-state detection

- [ ] Detects "fresh DB" (no `00_schema_migrations` schema at all)
- [ ] Detects "migrations done, vault pending"
      (`vault_initialized_at IS NULL`)
- [ ] Detects "vault done, admin pending"
      (`first_admin_created_at IS NULL`)
- [ ] Detects "admin done, settings pending"
      (`installed_at IS NOT NULL` AND no `global.env` row in
      `10_fct_settings`)
- [ ] Detects "fully installed"
      (`installed_at IS NOT NULL` AND `global.env` row present)

### Interactive prompts

- [ ] Prompts for mode A/B if not given
- [ ] Mode A: prompts for superuser DSN, masks the password portion
      when echoing
- [ ] Mode B: prompts for 3 DSNs separately, does not display them after
      input
- [ ] Prompts for `--env` if neither the flag nor `$TENNETCTL_ENV` is set
- [ ] Prompts for unseal mode with numbered options
- [ ] Mode-specific prompts: manual root keys OR Azure KV config
- [ ] Prompts for admin username, email, password (twice with confirmation)
- [ ] Confirmation screen before each destructive phase with a "yes/no"
      gate (bypassed by `--yes`)

### Resume behaviour

- [ ] Running the wizard on a partial install without `--resume` refuses
      and prints detected phase
- [ ] Running with `--resume` jumps to the correct phase and skips prior
      phases entirely (no re-prompting)
- [ ] Resume from Phase 2 does not re-generate the MDK
- [ ] Resume from Phase 3 does not prompt for unseal mode again
- [ ] Resume from Phase 4 does not re-insert the first admin row

### Final output

- [ ] Prints install summary (install_id, env, unseal mode, admin username)
- [ ] Prints the write DSN exactly once inside a clearly-marked "copy
      this into your secrets manager" block
- [ ] Prints the exact server-start command including
      `DATABASE_URL=<write_dsn>` as an inline export example
- [ ] Exits 0 on success
- [ ] Exits non-zero with a readable error message on any failure
- [ ] Never prints any other secret (root keys, admin password, MDK,
      unwrap key) to stdout or stderr
- [ ] Re-running the wizard on an already-installed DB prints the
      "already installed" banner with no secret material at all

## Dependencies

- Depends on: `01_db_bootstrap`, `02_vault_init`, `03_first_admin`,
  `04_settings` (the wizard calls into each phase via a Python import)
- Depends on: `01_sql_migrator.01_runner` (to apply migrations in Phase 1)
- Depends on: `02_vault.01_setup` (to call `vault_setup_service.init_vault`
  in Phase 2)
- Depends on: `03_iam.00_bootstrap` (the `10_fct_users` table must exist
  before Phase 3 can insert into it)
- Depended on by: nothing — this is the CLI entry point
