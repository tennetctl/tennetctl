"""tennetctl migrate — CLI entry for the migration runner.

Commands:
  status   Show applied and pending migrations.
  up       Apply all pending migrations.

DSN priority (for the admin/DDL role):
  1. --dsn flag
  2. $DATABASE_URL_ADMIN environment variable
  3. $DATABASE_URL (fallback — works for all-in-one dev setups)
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import os
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tennetctl migrate",
        description="Manage database schema migrations.",
    )
    parser.add_argument(
        "--dsn",
        default=None,
        help=(
            "Admin-role DSN (DDL privileges required). "
            "Defaults to $DATABASE_URL_ADMIN or $DATABASE_URL."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show applied and pending migrations.")
    sub.add_parser("up", help="Apply all pending migrations.")
    return parser


def _resolve_dsn(cli_dsn: str | None) -> str:
    dsn = cli_dsn or os.environ.get("DATABASE_URL_ADMIN") or os.environ.get("DATABASE_URL")
    if not dsn:
        sys.stderr.write(
            "error: no DSN found. "
            "Pass --dsn, set $DATABASE_URL_ADMIN, or set $DATABASE_URL.\n"
        )
        raise SystemExit(1)
    return dsn


def _project_root() -> Path:
    _paths = importlib.import_module("scripts.00_core._paths")
    return _paths.project_root()


async def _cmd_status(dsn: str) -> int:
    import asyncpg  # noqa: PLC0415

    discovery = importlib.import_module("scripts.01_migrator.discovery")
    runner = importlib.import_module("scripts.01_migrator.runner")

    entries = discovery.discover_migrations(_project_root())
    conn = await asyncpg.connect(dsn)
    try:
        applied = await runner.load_applied_set(conn)
    finally:
        await conn.close()

    print(f"{'SEQ':>4}  {'STATUS':<10}  FILENAME")
    print("-" * 70)
    for e in entries:
        status = "applied" if e.sequence in applied else "pending"
        print(f"{e.sequence:>4}  {status:<10}  {e.filename}")

    pending_count = sum(1 for e in entries if e.sequence not in applied)
    applied_count = len(applied)
    print(f"\n  {applied_count} applied, {pending_count} pending")
    return 0


async def _cmd_up(dsn: str) -> int:
    import asyncpg  # noqa: PLC0415

    discovery = importlib.import_module("scripts.01_migrator.discovery")
    runner = importlib.import_module("scripts.01_migrator.runner")

    entries = discovery.discover_migrations(_project_root())
    conn = await asyncpg.connect(dsn)
    try:
        results = await runner.apply_pending(conn, entries)
    finally:
        await conn.close()

    if not results:
        print("  Nothing to apply — all migrations are up to date.")
    else:
        print(f"\n  {len(results)} migration(s) applied.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    dsn = _resolve_dsn(args.dsn)

    _paths = importlib.import_module("scripts.00_core._paths")
    _paths.ensure_backend_on_syspath()

    if args.command == "status":
        return asyncio.run(_cmd_status(dsn))
    if args.command == "up":
        return asyncio.run(_cmd_up(dsn))

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
