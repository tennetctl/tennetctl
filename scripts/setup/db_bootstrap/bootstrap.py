"""Phase 1 — DB bootstrap.

Handles two modes:
  Mode A (--mode a): Given a superuser DSN, create the three application
      roles and their passwords (if they don't already exist), then build
      the three DSNs from the role credentials.

  Mode B (--mode b): The three roles are pre-provisioned externally.
      The operator provides three DSNs; the wizard verifies each role's
      privileges via probe queries.

After role setup, Phase 1 applies the bootstrap migration (sequence 000)
by hand (because the runner can't track itself until applied_migrations
exists), then runs the Python migration runner for sequences 001-004.

Returns a BootstrapResult with the three DSNs so subsequent phases can
store them in the vault.
"""

from __future__ import annotations

import importlib
import os
import secrets
from dataclasses import dataclass

import asyncpg

_prompt = importlib.import_module("scripts.00_core._prompt")
_dsn_mod = importlib.import_module("scripts.00_core.dsn")
_errors = importlib.import_module("scripts.00_core.errors")
_paths = importlib.import_module("scripts.00_core._paths")
_discovery = importlib.import_module("scripts.01_migrator.discovery")
_runner = importlib.import_module("scripts.01_migrator.runner")

Phase1Error = _errors.Phase1Error


@dataclass(frozen=True)
class BootstrapResult:
    admin_dsn: str
    write_dsn: str
    read_dsn: str


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_phase1(
    *,
    mode: str,
    yes_flag: bool = False,
) -> BootstrapResult:
    """Execute Phase 1 and return the three verified DSNs.

    Args:
        mode:     "a" or "b".
        yes_flag: Skip interactive prompts when True.
    """
    print("\n── Phase 1 — Database Bootstrap ─────────────────────────")

    if mode == "a":
        result = await _mode_a(yes_flag=yes_flag)
    elif mode == "b":
        result = await _mode_b(yes_flag=yes_flag)
    else:
        raise Phase1Error("INVALID_MODE", f"Unknown mode: {mode!r}. Use 'a' or 'b'.")

    print("  Applying database migrations …")
    await _apply_migrations(result.admin_dsn)

    print("  ✔ Phase 1 complete.\n")
    return result


# ---------------------------------------------------------------------------
# Mode A — superuser creates the roles
# ---------------------------------------------------------------------------

async def _mode_a(*, yes_flag: bool) -> BootstrapResult:
    """Mode A: use a superuser DSN to create roles and the tennetctl database."""
    super_dsn = (
        os.environ.get("DATABASE_URL_SUPER")
        or _prompt.ask(
            "Superuser DSN (e.g. postgres://postgres@localhost:5432/postgres)",
            yes_flag=yes_flag,
            validate=_validate_dsn,
        )
    )

    parts = _dsn_mod.parse_dsn(super_dsn)
    host = parts["host"]
    port = parts["port"]
    db_name = "tennetctl"

    print(f"  Connecting as superuser to {_dsn_mod.mask_dsn(super_dsn)} …")
    try:
        super_conn = await asyncpg.connect(super_dsn)
    except Exception as exc:
        raise Phase1Error(
            "SUPERUSER_CONNECT_FAILED",
            f"Cannot connect with superuser DSN: {exc}",
        ) from exc

    try:
        # Check if database exists; create if not
        db_exists = await super_conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname = $1)", db_name
        )
        if not db_exists:
            print(f"  Creating database '{db_name}' …")
            await super_conn.execute(f'CREATE DATABASE "{db_name}"')

        # Create roles with generated passwords (skip if they already exist)
        admin_pw = await _ensure_role(super_conn, "tennetctl_admin", superuser=True)
        write_pw = await _ensure_role(super_conn, "tennetctl_write")
        read_pw = await _ensure_role(super_conn, "tennetctl_read")

        # Grant CONNECT on the database
        for role in ("tennetctl_admin", "tennetctl_write", "tennetctl_read"):
            await super_conn.execute(
                f'GRANT CONNECT ON DATABASE "{db_name}" TO "{role}"'
            )

        # Default privileges so new schemas/tables are accessible
        await super_conn.execute(
            f"""
            ALTER DEFAULT PRIVILEGES FOR ROLE tennetctl_admin IN SCHEMA public
                GRANT SELECT ON TABLES TO tennetctl_read
            """
        )
        await super_conn.execute(
            f"""
            ALTER DEFAULT PRIVILEGES FOR ROLE tennetctl_admin IN SCHEMA public
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO tennetctl_write
            """
        )
    finally:
        await super_conn.close()

    admin_dsn = _dsn_mod.build_dsn(
        user="tennetctl_admin", password=admin_pw, host=str(host), port=int(port), dbname=db_name
    )
    write_dsn = _dsn_mod.build_dsn(
        user="tennetctl_write", password=write_pw, host=str(host), port=int(port), dbname=db_name
    )
    read_dsn = _dsn_mod.build_dsn(
        user="tennetctl_read", password=read_pw, host=str(host), port=int(port), dbname=db_name
    )

    print(f"  ✔ Roles and database ready.")
    return BootstrapResult(
        admin_dsn=admin_dsn,
        write_dsn=write_dsn,
        read_dsn=read_dsn,
    )


async def _ensure_role(conn: object, rolename: str, *, superuser: bool = False) -> str:
    """Create *rolename* if it does not exist. Return its (possibly new) password.

    If the role already exists, generate and set a fresh password so we
    always know the credential. This is idempotent and safe to re-run.
    """
    password = secrets.token_urlsafe(32)
    exists = await conn.fetchval(  # type: ignore[union-attr]
        "SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname = $1)", rolename
    )
    # Passwords in DDL cannot use $N placeholders — use quote_literal via DB
    quoted_pw = await conn.fetchval("SELECT quote_literal($1)", password)  # type: ignore[union-attr]
    if not exists:
        opts = "SUPERUSER" if superuser else "NOINHERIT"
        await conn.execute(  # type: ignore[union-attr]
            f'CREATE ROLE "{rolename}" WITH LOGIN PASSWORD {quoted_pw} {opts}'
        )
        print(f"  Created role '{rolename}'.")
    else:
        # Role exists (e.g. docker init.sql) — update its password
        await conn.execute(  # type: ignore[union-attr]
            f'ALTER ROLE "{rolename}" WITH PASSWORD {quoted_pw}'
        )
        print(f"  Updated password for existing role '{rolename}'.")
    return password


# ---------------------------------------------------------------------------
# Mode B — pre-provisioned DSNs
# ---------------------------------------------------------------------------

async def _mode_b(*, yes_flag: bool) -> BootstrapResult:
    """Mode B: accept three pre-provisioned DSNs and verify their privileges."""
    print("  Mode B: provide three pre-provisioned DSNs.")

    admin_dsn = _prompt.ask(
        "Admin DSN (CREATE/ALTER/DROP privileges)",
        yes_flag=yes_flag,
        validate=_validate_dsn,
    )
    write_dsn = _prompt.ask(
        "Write DSN (SELECT/INSERT/UPDATE/DELETE privileges)",
        yes_flag=yes_flag,
        validate=_validate_dsn,
    )
    read_dsn = _prompt.ask(
        "Read DSN (SELECT privileges only)",
        yes_flag=yes_flag,
        validate=_validate_dsn,
    )

    await _verify_admin_privileges(admin_dsn)
    await _verify_write_privileges(write_dsn)
    await _verify_read_privileges(read_dsn)

    return BootstrapResult(
        admin_dsn=admin_dsn,
        write_dsn=write_dsn,
        read_dsn=read_dsn,
    )


async def _verify_admin_privileges(dsn: str) -> None:
    """Verify the admin DSN can CREATE SCHEMA and CREATE TABLE."""
    print(f"  Verifying admin privileges … ({_dsn_mod.mask_dsn(dsn)})")
    probe_schema = "_tennetctl_probe"
    try:
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{probe_schema}"')
            await conn.execute(
                f'CREATE TABLE IF NOT EXISTS "{probe_schema}"._probe (id INT)'
            )
            await conn.execute(f'DROP SCHEMA "{probe_schema}" CASCADE')
        finally:
            await conn.close()
    except Exception as exc:
        raise Phase1Error(
            "ADMIN_PRIVILEGE_CHECK_FAILED",
            f"Admin DSN lacks required DDL privileges: {exc}",
        ) from exc
    print("  ✔ Admin DSN verified.")


async def _verify_write_privileges(dsn: str) -> None:
    """Verify the write DSN can connect (full DML check deferred to post-migration)."""
    print(f"  Verifying write DSN … ({_dsn_mod.mask_dsn(dsn)})")
    try:
        conn = await asyncpg.connect(dsn)
        await conn.close()
    except Exception as exc:
        raise Phase1Error(
            "WRITE_CONNECT_FAILED",
            f"Cannot connect with write DSN: {exc}",
        ) from exc
    print("  ✔ Write DSN verified.")


async def _verify_read_privileges(dsn: str) -> None:
    """Verify the read DSN can connect."""
    print(f"  Verifying read DSN … ({_dsn_mod.mask_dsn(dsn)})")
    try:
        conn = await asyncpg.connect(dsn)
        await conn.close()
    except Exception as exc:
        raise Phase1Error(
            "READ_CONNECT_FAILED",
            f"Cannot connect with read DSN: {exc}",
        ) from exc
    print("  ✔ Read DSN verified.")


# ---------------------------------------------------------------------------
# Migration application
# ---------------------------------------------------------------------------

async def _apply_migrations(admin_dsn: str) -> None:
    """Apply the bootstrap migration (000) by hand, then run the runner for 001-004."""
    root = _paths.project_root()
    bootstrap_sql_path = (
        root
        / "03_docs/features/01_sql_migrator/05_sub_features/00_bootstrap"
        / "09_sql_migrations/02_in_progress"
        / "20260408_000_schema_migrations_bootstrap.sql"
    )

    conn = await asyncpg.connect(admin_dsn)
    try:
        # Check if bootstrap migration already applied
        applied = await _runner.load_applied_set(conn)
        if 0 not in applied:
            print("  Applying bootstrap migration (000) …")
            _sections = importlib.import_module("scripts.01_migrator.sections")
            up_sql, _ = _sections.split_up_down(bootstrap_sql_path.read_text())
            await conn.execute(up_sql)
            print("  [000] Applied: 20260408_000_schema_migrations_bootstrap.sql")
        else:
            print("  [000] Already applied: 20260408_000_schema_migrations_bootstrap.sql")

        # Run the runner for remaining migrations
        entries = _discovery.discover_migrations(root)
        # Skip sequence 0 — we applied it above or it's already in applied_migrations
        pending = [e for e in entries if e.sequence > 0]
        await _runner.apply_pending(conn, pending)
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def _validate_dsn(value: str) -> str | None:
    """Return an error message string, or None if valid."""
    try:
        _dsn_mod.parse_dsn(value)
        return None
    except ValueError as exc:
        return str(exc)
