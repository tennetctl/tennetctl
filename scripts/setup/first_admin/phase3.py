"""Phase 3 — First admin user creation.

Prompts for username, email, and password (with confirmation), hashes the
password with Argon2id, then inserts the user row + three EAV attribute
rows into 03_iam inside a single transaction.

Sets system_meta.installed_at on success — this is the canonical marker
that the installation is complete from an IAM perspective.
"""

from __future__ import annotations

import importlib
import re

import asyncpg

_prompt = importlib.import_module("scripts.00_core._prompt")
_errors = importlib.import_module("scripts.00_core.errors")
_id_mod = importlib.import_module("scripts.00_core._id")
_password = importlib.import_module("04_backend.02_features.iam.auth.password")

Phase3Error = _errors.Phase3Error

_USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,64}$")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# ---------------------------------------------------------------------------
# Prompt validators
# ---------------------------------------------------------------------------

def _validate_username(value: str) -> str | None:
    if not _USERNAME_RE.match(value):
        return (
            "Username must be 3–64 characters and contain only "
            "letters, digits, dots, hyphens, or underscores."
        )
    return None


def _validate_email(value: str) -> str | None:
    if not _EMAIL_RE.match(value):
        return "Please enter a valid email address."
    return None


def _validate_password(value: str) -> str | None:
    if len(value) < 12:
        return "Password must be at least 12 characters."
    if value.isalpha():
        return "Password must contain at least one non-letter character."
    return None


# ---------------------------------------------------------------------------
# Phase entry point
# ---------------------------------------------------------------------------

async def run_phase3(*, admin_dsn: str, yes_flag: bool = False) -> None:
    """Execute Phase 3: create the first admin user.

    Args:
        admin_dsn:  Admin-role DSN (needs INSERT on 03_iam tables).
        yes_flag:   Skip interactive prompts (uses defaults — for testing only).
    """
    print("\n── Phase 3 — First Admin ─────────────────────────────────")

    username = _prompt.ask(
        "Admin username",
        default="admin" if yes_flag else None,
        validate=_validate_username,
        yes_flag=yes_flag,
    )
    email = _prompt.ask(
        "Admin email",
        default="admin@example.com" if yes_flag else None,
        validate=_validate_email,
        yes_flag=yes_flag,
    )

    # Password prompt — ask twice to confirm
    password: str | None = None
    while password is None:
        pw1 = _prompt.ask(
            "Admin password",
            secret=True,
            validate=_validate_password,
            yes_flag=yes_flag,
            default="ChangeMe123!" if yes_flag else None,
        )
        if yes_flag:
            password = pw1
            break
        pw2 = _prompt.ask("Confirm password", secret=True, yes_flag=yes_flag, default=pw1)
        if pw1 != pw2:
            print("  Passwords do not match — please try again.")
        else:
            password = pw1

    print("  Hashing password (Argon2id, 64 MiB) …")
    password_hash = _password.hash_password(password)

    await _insert_first_admin(
        admin_dsn=admin_dsn,
        username=username,
        email=email,
        password_hash=password_hash,
    )

    print("  ✔ Phase 3 complete.\n")


# ---------------------------------------------------------------------------
# DB writes
# ---------------------------------------------------------------------------

async def _insert_first_admin(
    *,
    admin_dsn: str,
    username: str,
    email: str,
    password_hash: str,
) -> None:
    """Insert the first admin user and EAV attributes in a single transaction."""
    conn = await asyncpg.connect(admin_dsn)
    try:
        async with conn.transaction():
            # Resolve dim IDs
            account_type_id = await conn.fetchval(
                'SELECT id FROM "03_iam"."06_dim_account_types" WHERE code = $1',
                "default_admin",
            )
            auth_type_id = await conn.fetchval(
                'SELECT id FROM "03_iam"."07_dim_auth_types" WHERE code = $1',
                "username_password",
            )
            entity_type_id = await conn.fetchval(
                'SELECT id FROM "03_iam"."06_dim_entity_types" WHERE code = $1',
                "iam_user",
            )

            if None in (account_type_id, auth_type_id, entity_type_id):
                raise Phase3Error(
                    "IAM_DIM_MISSING",
                    "Required IAM dim rows not found — migrations may not have been applied.",
                    hint="Run Phase 1 first to apply all migrations.",
                )

            # Resolve EAV attribute definition IDs
            attr_rows = await conn.fetch(
                """
                SELECT d.id, d.code
                  FROM "03_iam"."07_dim_attr_defs" d
                  JOIN "03_iam"."06_dim_entity_types" et ON d.entity_type_id = et.id
                 WHERE et.code = 'iam_user'
                   AND d.code = ANY($1::text[])
                """,
                ["username", "email", "password_hash"],
            )
            attr_ids = {row["code"]: row["id"] for row in attr_rows}
            for required in ("username", "email", "password_hash"):
                if required not in attr_ids:
                    raise Phase3Error(
                        "IAM_ATTR_DEF_MISSING",
                        f"Attribute definition '{required}' not found in 03_iam.07_dim_attr_defs.",
                    )

            # Generate UUID v7 for the user
            user_id = _id_mod.uuid7()

            # Insert user row — self-referential created_by/updated_by
            await conn.execute(
                """
                INSERT INTO "03_iam"."10_fct_users"
                    (id, org_id, account_type_id, auth_type_id,
                     is_active, is_test, created_by, updated_by,
                     created_at, updated_at)
                VALUES ($1, $1, $2, $3,
                        TRUE, FALSE, $1, $1,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                user_id,
                account_type_id,
                auth_type_id,
            )

            # Insert three EAV attribute rows
            eav_rows = [
                (_id_mod.uuid7(), entity_type_id, user_id, attr_ids["username"],      username),
                (_id_mod.uuid7(), entity_type_id, user_id, attr_ids["email"],         email),
                (_id_mod.uuid7(), entity_type_id, user_id, attr_ids["password_hash"], password_hash),
            ]
            await conn.executemany(
                """
                INSERT INTO "03_iam"."20_dtl_attrs"
                    (id, entity_type_id, entity_id, attr_def_id, key_text,
                     created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                eav_rows,
            )

            # Mark install complete in system_meta
            await conn.execute(
                """
                UPDATE "00_schema_migrations".system_meta
                   SET installed_at           = CURRENT_TIMESTAMP,
                       installer_version      = '0.1.0',
                       first_admin_username   = $1,
                       first_admin_created_at = CURRENT_TIMESTAMP,
                       install_id             = $2,
                       updated_at             = CURRENT_TIMESTAMP
                 WHERE id = 1
                """,
                username,
                _id_mod.uuid7(),
            )

    finally:
        await conn.close()

    print(f"  Created admin user '{username}'.")
