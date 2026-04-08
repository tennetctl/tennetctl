"""tennetctl admin reset-password — reset a user's password from the CLI.

Usage:
    tennetctl admin reset-password <username> [--yes]

Reads the admin DSN from $DATABASE_URL_ADMIN (preferred) or $DATABASE_URL.
Password is always prompted interactively — never accepted on the command line
to avoid plaintext credentials appearing in shell history or process lists.
"""

from __future__ import annotations

import importlib
import sys

import asyncpg

_prompt = importlib.import_module("scripts.00_core._prompt")
_password_mod = importlib.import_module("04_backend.02_features.iam.auth.password")
_audit = importlib.import_module("04_backend.02_features.audit.service")


async def _run(username: str, yes_flag: bool) -> int:
    import os  # noqa: PLC0415

    # Resolve DSN — prefer admin so we can write to attr table
    dsn = os.environ.get("DATABASE_URL_ADMIN") or os.environ.get("DATABASE_URL")
    if not dsn:
        sys.stderr.write("Error: $DATABASE_URL_ADMIN or $DATABASE_URL must be set.\n")
        return 1

    # Always prompt — never accept password via CLI flag (prevents shell history leaks)
    new_password = _prompt.ask(
        f"New password for '{username}'",
        secret=True,
        validate=lambda v: None if len(v) >= 12 else "Password must be at least 12 characters.",
    )

    if not yes_flag:
        if not _prompt.confirm(f"Reset password for user '{username}'?"):
            sys.stdout.write("Aborted.\n")
            return 0

    conn = await asyncpg.connect(dsn)
    try:
        # Find the user by username (attr_def_id=3)
        row = await conn.fetchrow(
            """
            SELECT u.id
              FROM "03_iam"."10_fct_users" u
              JOIN "03_iam"."20_dtl_attrs" a
                     ON a.entity_id   = u.id
                    AND a.attr_def_id = 3
             WHERE a.key_text = $1
               AND u.deleted_at IS NULL
            """,
            username,
        )
        if row is None:
            sys.stderr.write(f"Error: User '{username}' not found.\n")
            return 1

        user_id: str = row["id"]
        new_hash = _password_mod.hash_password(new_password)

        async with conn.transaction():
            # Update the password_hash EAV attribute (attr_def_id=1)
            updated = await conn.execute(
                """
                UPDATE "03_iam"."20_dtl_attrs"
                   SET key_text   = $2,
                       updated_at = CURRENT_TIMESTAMP
                 WHERE entity_id   = $1
                   AND attr_def_id = 1
                """,
                user_id,
                new_hash,
            )
            if updated == "UPDATE 0":
                sys.stderr.write(
                    f"Error: password_hash attribute not found for user '{username}'.\n"
                )
                return 1

            # Emit audit event for the password reset.
            # This is an out-of-band admin operation with no interactive
            # session, so we classify it as category="setup" which bypasses
            # the user_id/session_id mandatory check. The actor is still
            # recorded so "who reset this password" is queryable.
            await _audit.emit(
                conn,
                category="setup",
                action="user.password_reset",
                outcome="success",
                user_id=None,
                session_id=None,
                actor_id=user_id,
                target_id=user_id,
                target_type="iam_user",
            )

    finally:
        await conn.close()

    sys.stdout.write(f"  ✔ Password reset for user '{username}'.\n")
    return 0


def run(argv: list[str]) -> int:
    """Parse argv and run the reset-password command."""
    import argparse  # noqa: PLC0415
    import asyncio  # noqa: PLC0415

    parser = argparse.ArgumentParser(
        prog="tennetctl admin reset-password",
        description="Reset a user password from the CLI.",
    )
    parser.add_argument("username", help="Username to reset")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    opts = parser.parse_args(argv)

    return asyncio.run(_run(opts.username, opts.yes))
