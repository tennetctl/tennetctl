## Setup Wizard — Design

## File layout

```text
scripts/setup/
├── __init__.py
├── cli.py                — Typer command: `tennetctl setup`
├── state.py              — InstallState dataclass + phase detection
├── prompts.py            — rich-based interactive prompts (all I/O lives here)
├── phases.py             — orchestration: calls each phase in order
└── errors.py             — SetupError hierarchy + exit codes
```

No filesystem state. The wizard writes everything it needs into Postgres
(`"00_schema_migrations".system_meta`, `"00_schema_migrations"."10_fct_settings"`,
and the per-feature schemas) and never touches disk. At runtime the app
locates Postgres via `$DATABASE_URL` and everything else comes from the
`10_fct_settings` table.

Nothing else in `scripts/setup/` — the phase modules (`db_bootstrap`,
`vault_init`, `first_admin`) live in their own sub-feature directories
and are imported from here.

## InstallState dataclass

```python
# scripts/setup/state.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from pathlib import Path

class Phase(IntEnum):
    FRESH          = 0
    DB_READY       = 1   # migrations applied
    VAULT_READY    = 2   # vault initialized + DSNs seeded
    ADMIN_READY    = 3   # first admin inserted (system_meta.installed_at set)
    INSTALLED      = 4   # settings rows seeded — install complete

@dataclass
class InstallState:
    """In-memory state the wizard carries across phases.

    Passwords and root keys live on this object only for the lifetime of the
    install run and are zeroed before the wizard exits. Never logged. Nothing
    on this object is ever persisted to disk — it exists only to pass values
    between phases.
    """

    # Detection
    current_phase:    Phase
    install_id:       str | None = None           # ULID, set in Phase 0 if FRESH

    # Phase 0 capture — deployment environment, prompted once and seeded into
    # 10_fct_settings in Phase 4. Also echoed to the operator at the end of
    # install so they can verify their target matches their intent.
    env:              str | None = None           # "dev" | "staging" | "prod"

    # Phase 1 outputs (held in memory, never persisted to disk)
    admin_dsn:        str | None = None
    write_dsn:        str | None = None
    read_dsn:         str | None = None

    # Phase 2 outputs
    unseal_mode:      str | None = None           # "manual" | "kms_azure" | ...
    vault_initialized_at: datetime | None = None

    # Phase 3 outputs
    admin_username:   str | None = None
    admin_created_at: datetime | None = None

    def zero(self) -> None:
        """Clear all secret material. Called in a try/finally wrapper around
        the whole wizard run, so an exception still triggers zeroing."""
        self.admin_dsn = None
        self.write_dsn = None
        self.read_dsn  = None
```

## Phase detection

```python
# scripts/setup/state.py (continued)

async def detect_phase(conn_or_none) -> Phase:
    """
    Returns the current install phase.

    conn_or_none is an asyncpg connection opened with whichever DSN the
    operator supplied (superuser or admin). If None, there is no DB to
    inspect yet → Phase.FRESH.

    The database is the single source of truth for install state. There
    is no filesystem marker to cross-check — system_meta in the DB is the
    only record of progress.
    """

    if conn_or_none is None:
        return Phase.FRESH

    has_schema = await conn_or_none.fetchval(
        "SELECT EXISTS ("
        "  SELECT 1 FROM information_schema.schemata"
        "  WHERE schema_name = '00_schema_migrations'"
        ")"
    )

    if not has_schema:
        return Phase.FRESH

    row = await conn_or_none.fetchrow(
        'SELECT installed_at, vault_initialized_at, first_admin_created_at '
        'FROM "00_schema_migrations".system_meta WHERE id = 1'
    )

    if row is None:
        return Phase.FRESH

    # installed_at is written in Phase 3 atomically with the first admin
    # insert. Phase 4 then seeds settings rows. We distinguish "admin inserted
    # but settings not yet seeded" from "fully installed" by checking the
    # 10_fct_settings table for at least one global row.
    if row["installed_at"] is not None:
        settings_seeded = await conn_or_none.fetchval(
            'SELECT EXISTS (SELECT 1 FROM "00_schema_migrations"."10_fct_settings" '
            'WHERE scope = $1)',
            'global',
        )
        return Phase.INSTALLED if settings_seeded else Phase.ADMIN_READY

    if row["first_admin_created_at"] is not None:
        return Phase.ADMIN_READY

    if row["vault_initialized_at"] is not None:
        return Phase.VAULT_READY

    return Phase.DB_READY
```

## Top-level orchestration

```python
# scripts/setup/phases.py

async def run_setup(opts: SetupOptions) -> int:
    """Main entry point. Returns process exit code."""

    state = InstallState(current_phase=Phase.FRESH)

    try:
        # Preflight: detect phase using whichever DSN we can get hold of
        async with open_bootstrap_conn(opts) as conn:
            state.current_phase = await detect_phase(conn)

        if state.current_phase == Phase.INSTALLED:
            print_already_installed(state)
            return 0

        if state.current_phase != Phase.FRESH and not opts.resume:
            raise ResumeRequiredError(state)

        # Phase 0: capture deployment environment (dev | staging | prod).
        # Resolved from --env flag, $TENNETCTL_ENV, or interactive prompt.
        # Held on state until Phase 4 seeds it into 10_fct_settings.
        state.env = resolve_env(opts)

        # Phase 1: DB bootstrap + migrations (skipped if current_phase >= DB_READY)
        if state.current_phase < Phase.DB_READY:
            from scripts.setup.db_bootstrap import run_db_bootstrap
            await run_db_bootstrap(opts, state)
            state.current_phase = Phase.DB_READY

        # Phase 2: vault init + DSN seeding
        if state.current_phase < Phase.VAULT_READY:
            from scripts.setup.vault_init import run_vault_init
            await run_vault_init(opts, state)
            state.current_phase = Phase.VAULT_READY

        # Phase 3: first admin (writes installed_at in the same tx)
        if state.current_phase < Phase.ADMIN_READY:
            from scripts.setup.first_admin import run_first_admin
            await run_first_admin(opts, state)
            state.current_phase = Phase.ADMIN_READY

        # Phase 4: seed the 10_fct_settings rows. Idempotent — each INSERT is
        # guarded by ON CONFLICT (scope, key) DO NOTHING so re-running the
        # wizard after a partial Phase 4 does not clobber any operator edits.
        if state.current_phase < Phase.INSTALLED:
            from scripts.setup.settings import seed_settings
            await seed_settings(state)
            state.current_phase = Phase.INSTALLED

        print_next_steps(state)
        return 0

    except SetupError as e:
        print_error(e)
        return e.exit_code
    finally:
        state.zero()
```

The pattern is: every phase is a pure async function that takes `(opts,
state)`, mutates `state` with its outputs, and raises `SetupError`
subclasses on failure. The orchestrator is linear and has no
conditionals beyond the phase-skip guards.

## Prompt/flag resolution

Every prompt goes through a single helper that prefers the flag value,
then the env var, then an interactive prompt:

```python
# scripts/setup/prompts.py

def resolve(
    flag_value:    str | None,
    env_var:       str,
    prompt_label:  str,
    *,
    secret:        bool = False,
    validator:     Callable[[str], str] | None = None,
) -> str:
    """
    Returns the resolved value. Order of precedence:
      1. --flag  (from opts)
      2. $ENV_VAR
      3. interactive prompt via rich.prompt
    Applies validator to whichever source won.
    Raises NonInteractiveError if stdin is not a TTY and no flag/env found.
    """
    value = flag_value or os.environ.get(env_var)
    if value is None:
        if not sys.stdin.isatty():
            raise NonInteractiveError(
                f"{prompt_label} not provided (flag, env, or TTY required)"
            )
        value = Prompt.ask(prompt_label, password=secret)

    if validator is not None:
        value = validator(value)
    return value
```

Validators are stand-alone functions per input type (`validate_dsn`,
`validate_hex_64`, `validate_email`, etc.) and raise `ValueError` on bad
input. The prompt helper catches and re-prompts interactively, or
propagates in non-interactive mode.

## Settings seeder (Phase 4)

Phase 4 seeds the `"00_schema_migrations"."10_fct_settings"` table with
the v1 defaults. All inserts are idempotent via `ON CONFLICT (scope, key)
DO NOTHING` so re-running the wizard never overwrites a setting an
operator has edited.

```python
# scripts/setup/settings.py

import asyncpg

from backend.core.ids import new_uuid_v7
from .state import InstallState


_SEED_ROWS: list[tuple[str, str, str, bool, str]] = [
    # (scope, key, value, value_secret, description)
    ("global", "env",                           None,    False,
        "Deployment environment (dev | staging | prod). Seeded from "
        "--env / $TENNETCTL_ENV at install time."),
    ("03_iam", "jwt_expiry_seconds",            "900",   False,
        "JWT access token TTL in seconds. Default 15 minutes."),
    ("03_iam", "cookie_secure",                 "false", False,
        "Set the Secure flag on the tcc_refresh cookie. False for local "
        "dev over http; true for any non-dev deployment."),
    ("03_iam", "refresh_token_ttl_days",        "7",     False,
        "Refresh token lifetime in days."),
    ("03_iam", "session_absolute_ttl_days",     "30",    False,
        "Hard session cap in days. Re-login required after this regardless "
        "of refresh activity."),
]


async def seed_settings(state: InstallState) -> None:
    """Insert v1 default settings rows into 10_fct_settings.

    Idempotent: ON CONFLICT DO NOTHING means re-running after a partial
    Phase 4 picks up only the missing rows and leaves anything the
    operator has changed untouched.
    """
    rows = []
    for scope, key, value, secret, desc in _SEED_ROWS:
        # global.env is the only row whose value comes from InstallState
        resolved = state.env if (scope, key) == ("global", "env") else value
        rows.append((new_uuid_v7(), scope, key, resolved, secret, desc))

    async with asyncpg.connect(state.admin_dsn) as conn:
        await conn.executemany(
            '''INSERT INTO "00_schema_migrations"."10_fct_settings"
                   (id, scope, key, value, value_secret, description)
               VALUES ($1, $2, $3, $4, $5, $6)
               ON CONFLICT (scope, key) DO NOTHING''',
            rows,
        )
```

If Phase 4 crashes partway through the seed, re-running the wizard is
safe — `detect_phase` sees `system_meta.installed_at IS NOT NULL` but the
`global.env` settings row missing, so it returns `Phase.ADMIN_READY` and
the orchestrator retries `seed_settings`.

## Error hierarchy

```python
# scripts/setup/errors.py

class SetupError(Exception):
    exit_code: int = 1

class ResumeRequiredError(SetupError):
    """Partial install detected; --resume not passed."""
    exit_code = 11

class NonInteractiveError(SetupError):
    """Missing flag/env in non-TTY mode."""
    exit_code = 12

class Phase1Error(SetupError):
    """Delegated from 01_db_bootstrap."""
    exit_code = 21

class Phase2Error(SetupError):
    """Delegated from 02_vault_init."""
    exit_code = 22

class Phase3Error(SetupError):
    """Delegated from 03_first_admin."""
    exit_code = 23

class Phase4Error(SetupError):
    """Delegated from 04_settings."""
    exit_code = 24
```

Exit codes let CI scripts distinguish "invalid invocation" (11–12) from
"Azure credentials expired" (22) without parsing stderr.

## Testing strategy

- **Unit tests** for `detect_phase` using a real Postgres (via the test
  fixture that sets up and tears down `00_schema_migrations`) —
  parameterised across every `system_meta` state (fresh, DB-ready,
  vault-ready, admin-ready-but-settings-missing, fully installed),
  asserting the returned Phase for each.
- **Unit tests** for `seed_settings` that assert (a) every v1 seed row
  lands in `10_fct_settings`, (b) `global.env` picks up `state.env`,
  (c) re-running does not overwrite a row whose value has been edited
  (ON CONFLICT DO NOTHING), and (d) a partial Phase 4 crash leaves the
  table in a state that `detect_phase` correctly reports as
  `Phase.ADMIN_READY`.
- **Unit tests** for the Typer command surface that assert every flag
  parses, every env var is picked up, and `--help` output matches the
  scope doc.
- **Integration tests** that run `tennetctl setup` end-to-end against a
  disposable Postgres container with every mode combination
  (A×manual, A×kms_azure, B×manual, B×kms_azure) and assert the final
  state in `system_meta` and `10_fct_settings`. kms_azure uses the mocked
  backend by setting `TENNETCTL_UNSEAL_BACKEND_FAKE=1`.
- **Idempotency tests** that run the wizard, kill it mid-Phase-2, then
  re-run with `--resume` and assert the install completes without
  re-generating the MDK.

## Security notes

- Secret material in `InstallState` lives in plain attributes. Python does
  not give us guaranteed memory zeroing (strings are immutable, garbage
  collection is non-deterministic), but `state.zero()` in the `finally`
  block at least removes references so the GC can reclaim them. For
  manual-mode root keys this is still weaker than an HSM, which is why
  the docs recommend KMS modes for production.
- No prompt value is ever echoed to the terminal. `rich.Prompt.ask` with
  `password=True` suppresses echo and is used for every secret.
- The superuser DSN (Mode A) and the admin DSN (Mode B) are never written
  to any file or environment variable. They live on `InstallState` and
  are zeroed when the wizard exits.
- The wizard writes no files. All install state lives in Postgres. The
  only credential material that leaves the wizard process is the write
  DSN itself, which the operator captures at the end of install and
  places into their deployment's secret store (`$DATABASE_URL` env var
  for the running app). There is no on-disk `config.toml`, no atomic
  rename dance, and no filesystem mode bits to get wrong.
- The write DSN is printed to the operator exactly once, at the end of a
  successful run, with a clear banner instructing them to copy it into
  their secret manager and warning that the wizard cannot recover it if
  lost. Re-running `tennetctl setup` against an already-installed DB
  prints nothing secret — it exits with "already installed" and zero
  sensitive output.
