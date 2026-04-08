## DB Bootstrap — Design

## File layout

```text
scripts/setup/db_bootstrap/
├── __init__.py
├── entrypoint.py        — run_db_bootstrap(opts, state) — the only public fn
├── mode_a.py            — Mode A: superuser role/db creation
├── mode_b.py            — Mode B: pre-provisioned DSN verification
├── passwords.py         — secrets.token_urlsafe wrapper + DSN assembly
├── privileges.py        — the GRANT matrix as parameterised SQL strings
├── migrations.py        — bootstrap apply + runner invocation
└── tests/
    ├── test_mode_a.py
    ├── test_mode_b.py
    └── test_migrations.py
```

## Entrypoint contract

```python
# scripts/setup/db_bootstrap/entrypoint.py

async def run_db_bootstrap(
    opts: SetupOptions,
    state: InstallState,
) -> None:
    """Phase 1: DB role + schema bootstrap.

    Mutates `state` with admin_dsn / write_dsn / read_dsn on success.
    Raises Phase1Error on any failure. Never raises asyncpg exceptions
    directly — always wraps them with the offending DSN (without the
    password) and the specific operation that failed.
    """
    mode = resolve_mode(opts)    # 'a' or 'b' — prompts if unset

    if mode == "a":
        await mode_a.bootstrap_roles(opts, state)
    else:
        await mode_b.verify_dsns(opts, state)

    # Both modes converge here with admin_dsn / write_dsn / read_dsn set
    await migrations.apply_bootstrap(state)
    await migrations.run_runner(state)
```

## Mode A — password generation and DSN assembly

```python
# scripts/setup/db_bootstrap/passwords.py

import secrets
from urllib.parse import quote

def generate_password() -> str:
    """32 bytes of secrets.token_urlsafe → ~43 URL-safe chars.
    More than enough entropy and works in a DSN without escaping."""
    return secrets.token_urlsafe(32)

def assemble_dsn(
    *,
    user:     str,
    password: str,
    host:     str,
    port:     int,
    database: str,
) -> str:
    """Build a postgres:// DSN. Password is URL-encoded so a literal
    '@' or '/' in the password cannot break parsing."""
    return (
        f"postgres://{user}:{quote(password, safe='')}"
        f"@{host}:{port}/{database}"
    )
```

The host/port for the three generated DSNs is parsed from the superuser
DSN the operator supplied — the wizard assumes all four roles live on
the same Postgres instance. Cross-host is out of scope.

## Mode A — role creation SQL

```sql
-- Executed as four separate statements via asyncpg. Passwords are passed
-- as bind parameters where possible, but CREATE ROLE does not accept
-- parameterised passwords, so the password is validated as URL-safe
-- (no quotes, no backslashes) before being interpolated. token_urlsafe
-- output is guaranteed to match [A-Za-z0-9_-]+ so this is safe.

CREATE ROLE tennetctl_admin LOGIN PASSWORD '<admin_pw>';
CREATE ROLE tennetctl_write LOGIN PASSWORD '<write_pw>';
CREATE ROLE tennetctl_read  LOGIN PASSWORD '<read_pw>';

CREATE DATABASE tennetctl OWNER tennetctl_admin;
```

After the database is created, the wizard closes the superuser connection
and opens a new connection as `tennetctl_admin` on the new database to
run the privilege grants:

```sql
-- On tennetctl database as tennetctl_admin

REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT  ALL ON SCHEMA public TO tennetctl_admin;

GRANT CONNECT ON DATABASE tennetctl TO tennetctl_write, tennetctl_read;

ALTER DEFAULT PRIVILEGES FOR ROLE tennetctl_admin
    GRANT SELECT ON TABLES TO tennetctl_read;

ALTER DEFAULT PRIVILEGES FOR ROLE tennetctl_admin
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO tennetctl_write;

ALTER DEFAULT PRIVILEGES FOR ROLE tennetctl_admin
    GRANT USAGE, SELECT ON SEQUENCES TO tennetctl_write;
```

### Idempotency

Mode A handles already-exists cases via a pre-check:

```python
# scripts/setup/db_bootstrap/mode_a.py

async def bootstrap_roles(opts, state) -> None:
    su_dsn = await resolve_superuser_dsn(opts)
    async with asyncpg.connect(su_dsn) as su:
        existing_roles = await _existing_roles(su)

        if existing_roles and existing_roles != EXPECTED_ROLES:
            raise Phase1Error(
                f"Partial role state: {existing_roles} already exist. "
                f"Either drop them manually or rerun with the passwords "
                f"you already know (Mode B)."
            )

        if not existing_roles:
            admin_pw = generate_password()
            write_pw = generate_password()
            read_pw  = generate_password()
            await _create_roles(su, admin_pw, write_pw, read_pw)
            await _create_database(su)
        else:
            # Full set exists — wizard cannot recover the passwords,
            # operator must use Mode B instead
            raise Phase1Error(
                "All three tennetctl roles already exist but the wizard "
                "has no way to recover their passwords. Rerun with "
                "--mode b and supply the DSNs directly."
            )

    # New short-lived admin connection for privilege grants
    state.admin_dsn = assemble_dsn(user="tennetctl_admin", password=admin_pw, ...)
    state.write_dsn = assemble_dsn(user="tennetctl_write", password=write_pw, ...)
    state.read_dsn  = assemble_dsn(user="tennetctl_read",  password=read_pw,  ...)

    async with asyncpg.connect(state.admin_dsn) as admin:
        await _grant_default_privileges(admin)
```

## Mode B — verification probes

```python
# scripts/setup/db_bootstrap/mode_b.py

PROBE_SCHEMA = "_tennetctl_preflight"
PROBE_TABLE  = f'"{PROBE_SCHEMA}"."probe"'

async def verify_dsns(opts, state) -> None:
    admin_dsn = resolve_dsn(opts, "admin")
    write_dsn = resolve_dsn(opts, "write")
    read_dsn  = resolve_dsn(opts, "read")

    # 1. All three connect
    for label, dsn in [("admin", admin_dsn),
                       ("write", write_dsn),
                       ("read",  read_dsn)]:
        try:
            async with asyncpg.connect(dsn) as c:
                await c.fetchval("SELECT 1")
        except Exception as e:
            raise Phase1Error(f"Cannot connect as {label}: {e}") from e

    # 2. Admin can CREATE SCHEMA + CREATE TABLE
    try:
        async with asyncpg.connect(admin_dsn) as admin:
            await admin.execute(f'CREATE SCHEMA "{PROBE_SCHEMA}"')
            await admin.execute(
                f'CREATE TABLE {PROBE_TABLE} (id INT PRIMARY KEY, v TEXT)'
            )
            # Admin grants on the probe table so write/read can touch it
            await admin.execute(
                f'GRANT SELECT, INSERT, UPDATE, DELETE ON {PROBE_TABLE} '
                f'TO tennetctl_write'
            )
            await admin.execute(
                f'GRANT SELECT ON {PROBE_TABLE} TO tennetctl_read'
            )
            await admin.execute(
                f'GRANT USAGE ON SCHEMA "{PROBE_SCHEMA}" '
                f'TO tennetctl_write, tennetctl_read'
            )
    except Exception as e:
        raise Phase1Error(f"admin DSN lacks DDL privileges: {e}") from e

    # 3. Write can INSERT + SELECT
    try:
        async with asyncpg.connect(write_dsn) as w:
            await w.execute(f'INSERT INTO {PROBE_TABLE} VALUES (1, $1)', "probe")
            v = await w.fetchval(f'SELECT v FROM {PROBE_TABLE} WHERE id = 1')
            assert v == "probe"
    except Exception as e:
        raise Phase1Error(f"write DSN cannot INSERT/SELECT: {e}") from e

    # 4. Read can SELECT but NOT INSERT
    try:
        async with asyncpg.connect(read_dsn) as r:
            v = await r.fetchval(f'SELECT v FROM {PROBE_TABLE} WHERE id = 1')
            assert v == "probe"

            try:
                await r.execute(f'INSERT INTO {PROBE_TABLE} VALUES (2, $1)',
                                "oops")
            except asyncpg.InsufficientPrivilegeError:
                pass  # EXPECTED — this is what we want
            else:
                raise Phase1Error(
                    "read DSN was able to INSERT — it has excess privileges"
                )
    except Phase1Error:
        raise
    except Exception as e:
        raise Phase1Error(f"read DSN verification failed: {e}") from e

    # 5. Cleanup — always runs, even on earlier failures (outer try/finally
    #    in the entrypoint wraps this function)
    finally_cleanup_probe(admin_dsn)

    state.admin_dsn = admin_dsn
    state.write_dsn = write_dsn
    state.read_dsn  = read_dsn

async def finally_cleanup_probe(admin_dsn: str) -> None:
    try:
        async with asyncpg.connect(admin_dsn) as admin:
            await admin.execute(f'DROP SCHEMA IF EXISTS "{PROBE_SCHEMA}" CASCADE')
    except Exception:
        # If cleanup fails we still want the original error to surface;
        # the leftover schema is harmless and easy to drop by hand
        logger.warning("Preflight probe schema cleanup failed", exc_info=True)
```

The exact `asyncpg.InsufficientPrivilegeError` check is load-bearing —
we specifically want "permission denied", not any arbitrary error like
"table doesn't exist" (which would incorrectly pass the test).

## Migration apply

```python
# scripts/setup/db_bootstrap/migrations.py

BOOTSTRAP_FILE = (
    "03_docs/features/01_sql_migrator/05_sub_features/00_bootstrap/"
    "09_sql_migrations/02_in_progress/20260408_000_schema_migrations_bootstrap.sql"
)

async def apply_bootstrap(state: InstallState) -> None:
    """Read and execute the migrator bootstrap migration by hand.

    Split on the DOWN marker and execute only the UP section. All
    statements run in a single transaction — partial apply is not a
    valid state for this migration.
    """
    sql = Path(BOOTSTRAP_FILE).read_text()
    up_sql = _extract_up_section(sql)

    async with asyncpg.connect(state.admin_dsn) as conn:
        async with conn.transaction():
            await conn.execute(up_sql)

    # Verify the row landed
    async with asyncpg.connect(state.admin_dsn) as conn:
        count = await conn.fetchval(
            'SELECT COUNT(*) FROM "00_schema_migrations".applied_migrations '
            'WHERE sequence = 0'
        )
        if count != 1:
            raise Phase1Error(
                "Bootstrap migration ran without error but the tracking "
                "row is missing. Refusing to continue."
            )

async def run_runner(state: InstallState) -> None:
    """Invoke the migration runner via its Python API."""
    from scripts.migrate import run_up  # the runner's public entrypoint
    result = await run_up(admin_dsn=state.admin_dsn)
    if result.failed:
        raise Phase1Error(
            f"Migration {result.failed.filename} failed: {result.failed.error}"
        )
```

`_extract_up_section` looks for the literal `-- UP ====` and `-- DOWN ====`
marker comments (already the convention in every project migration) and
returns the text between them. It raises `Phase1Error` if either marker
is missing — forcing every migration file to follow the convention.

## Testing strategy

- **Unit tests** for `passwords.py` assert the generated password
  matches `^[A-Za-z0-9_-]+$` and the assembled DSN round-trips through
  `urllib.parse.urlparse` without corruption.
- **Integration tests** against a disposable Postgres (via the
  `asyncpg-test` fixture pattern) that runs Mode A end-to-end on a
  superuser connection and verifies:
    - roles exist
    - database exists and is owned by `tennetctl_admin`
    - default privileges show up in `pg_default_acl`
    - the three DSNs can connect with the right permission shape
- **Integration tests** for Mode B that pre-provision roles with the
  expected privileges, run the verification probes, and assert they
  pass. A second variant deliberately gives the read role `INSERT`
  and asserts Phase 1 fails with the excess-privilege message.
- **Integration tests** for the migration apply step that run
  `apply_bootstrap` and `run_runner` on a clean database and then
  assert `applied_migrations` contains every sequence from `000`
  through the highest migration in the tree.
- **Idempotency tests** that run Phase 1 twice in Mode A on the same
  DB, assert the second run detects existing roles and fails cleanly
  with the "use Mode B" message.

## Security notes

- The superuser DSN is captured into `InstallState.superuser_dsn`
  only inside `mode_a.bootstrap_roles`. The entrypoint unsets it
  (`state.superuser_dsn = None`) before returning, even on exception
  (via `finally`).
- Generated role passwords never leave `InstallState` — they are passed
  to Phase 2 via `state.admin_dsn` / `write_dsn` / `read_dsn`
  (which include them URL-encoded), and Phase 2 zeroes them after
  writing to the vault.
- Probe schemas use the name `_tennetctl_preflight` — a leading
  underscore guarantees it doesn't collide with any future feature
  schema (feature schemas start with a digit). Cleanup is best-effort;
  a leftover empty schema is harmless.
- The wizard never logs DSNs at any level. The asyncpg connection
  strings are only logged in the form `postgres://<user>@<host>:<port>/<db>`
  with the password stripped before any log call.
