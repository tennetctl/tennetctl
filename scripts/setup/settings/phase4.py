"""Phase 4 — Settings seed.

Inserts the baseline rows into 00_schema_migrations.10_fct_settings using
ON CONFLICT (scope, key) DO NOTHING so re-runs never clobber operator edits.

Also seeds the JWT secret into the vault at ``tennetctl/iam/jwt_secret`` if
it does not already exist (idempotent — skips if the secret is already there).

At the end, prints the write DSN once for the operator to capture, then
waits for Enter (or skips with --yes) before exiting.
"""

from __future__ import annotations

import base64
import importlib
import secrets

import asyncpg

_id_mod = importlib.import_module("scripts.00_core._id")
_errors = importlib.import_module("scripts.00_core.errors")
_vault_service = importlib.import_module("04_backend.02_features.vault.setup.service")
_dsn_mod = importlib.import_module("scripts.00_core.dsn")
_kdf = importlib.import_module("scripts.setup.vault_init.kdf")

_JWT_SECRET_PATH = "tennetctl/iam/jwt_secret"

Phase4Error = _errors.Phase4Error

# ---------------------------------------------------------------------------
# Baseline settings
# (scope, key, value, value_type, value_secret, description)
# ---------------------------------------------------------------------------
_IAM_SETTINGS: list[tuple[str, str, str, str, bool, str]] = [
    (
        "03_iam", "jwt_algorithm", "HS256", "text", False,
        "JWT signing algorithm. HS256 is the only supported value in v1.",
    ),
    (
        "03_iam", "jwt_access_ttl_seconds", "900", "int", False,
        "Access token lifetime in seconds (default: 15 minutes).",
    ),
    (
        "03_iam", "jwt_refresh_ttl_seconds", "604800", "int", False,
        "Refresh token lifetime in seconds (default: 7 days).",
    ),
    (
        "03_iam", "session_absolute_ttl_seconds", "2592000", "int", False,
        "Absolute session lifetime in seconds (default: 30 days). "
        "No extension past this regardless of activity.",
    ),
    (
        "03_iam", "password_min_length", "12", "int", False,
        "Minimum password length enforced on create and update.",
    ),
]


async def run_phase4(
    *,
    admin_dsn: str,
    write_dsn: str,
    env: str,
    yes_flag: bool = False,
) -> None:
    """Execute Phase 4: seed the settings table and print the write DSN.

    Args:
        admin_dsn:  Admin-role DSN (write access to 10_fct_settings).
        write_dsn:  Write-role DSN — shown to the operator at the end.
        env:        Deployment environment (dev | staging | prod).
        yes_flag:   Skip the "press Enter" confirmation.
    """
    print("\n── Phase 4 — Settings Seed ───────────────────────────────")

    rows: list[tuple[str, str, str, str, bool, str]] = [
        (
            "global", "env", env, "text", False,
            "Deployment environment: dev, staging, or prod.",
        ),
        (
            "global", "installer_version", "0.1.0", "text", False,
            "Installer version that produced this install.",
        ),
        *_IAM_SETTINGS,
    ]

    conn = await asyncpg.connect(admin_dsn)
    try:
        inserted = 0
        for scope, key, value, value_type, value_secret, description in rows:
            result = await conn.execute(
                """
                INSERT INTO "00_schema_migrations"."10_fct_settings"
                    (id, scope, key, value, value_type, value_secret, description,
                     created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (scope, key) DO NOTHING
                """,
                _id_mod.uuid7(),
                scope,
                key,
                value,
                value_type,
                value_secret,
                description,
            )
            # asyncpg returns "INSERT 0 N" or "INSERT 0 0"
            if result.endswith("1"):
                inserted += 1

    finally:
        await conn.close()

    print(f"  {inserted} settings row(s) inserted ({len(rows) - inserted} already present).")

    # Seed the JWT signing secret into the vault (idempotent — skip if already there).
    await _seed_jwt_secret(admin_dsn=admin_dsn, write_dsn=write_dsn)

    print("  ✔ Phase 4 complete.\n")

    _print_write_dsn_banner(write_dsn, yes_flag=yes_flag)


# ---------------------------------------------------------------------------
# JWT secret seeder
# ---------------------------------------------------------------------------

async def _seed_jwt_secret(*, admin_dsn: str, write_dsn: str) -> None:
    """Seed a 32-byte random JWT signing secret into the vault.

    Uses the WRITE DSN password (same as what phase2 used as KDF input)
    to re-derive the wrap_key, unseal the vault, and call create_secret.
    Skips silently if the secret already exists (idempotent).
    """
    write_parts = _dsn_mod.parse_dsn(write_dsn)
    kdf_password: str = write_parts["password"]  # type: ignore[assignment]

    conn = await asyncpg.connect(admin_dsn)
    try:
        row = await conn.fetchrow(
            'SELECT unseal_salt FROM "00_schema_migrations".system_meta WHERE id = 1'
        )
        if row is None or row["unseal_salt"] is None:
            raise _errors.Phase4Error(
                "NO_UNSEAL_SALT",
                "system_meta.unseal_salt is NULL — vault not initialised.",
            )

        salt_bytes = base64.urlsafe_b64decode(row["unseal_salt"])
        wrap_key = _kdf.derive_wrap_key(kdf_password, salt_bytes)
        mdk = await _vault_service.unseal_vault(conn, wrap_key=wrap_key)

        # Check if JWT secret already exists
        existing = await conn.fetchrow(
            """
            SELECT id FROM "02_vault"."10_fct_secrets"
             WHERE path = $1 AND deleted_at IS NULL AND is_active = TRUE
            """,
            _JWT_SECRET_PATH,
        )
        if existing is not None:
            print("  [Phase 4] JWT secret already seeded — skipping.")
            return

        # Generate 32 random bytes, base64url-encode for TEXT storage
        jwt_secret_bytes = secrets.token_bytes(32)
        jwt_secret_b64 = base64.urlsafe_b64encode(jwt_secret_bytes).decode("ascii")
        await _vault_service.create_secret(
            conn,
            mdk=mdk,
            path=_JWT_SECRET_PATH,
            plaintext=jwt_secret_b64,
        )
        print(f"  ✔ Sealed: {_JWT_SECRET_PATH}")
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Write DSN banner
# ---------------------------------------------------------------------------

def _print_write_dsn_banner(write_dsn: str, *, yes_flag: bool) -> None:
    """Write the write DSN to stderr and wait for operator acknowledgement.

    Written to stderr so that stdout remains clean for machine consumption
    (e.g. CI pipelines that capture stdout and reject unexpected tokens).
    """
    import sys  # noqa: PLC0415

    banner = f"""
┌─────────────────────────────────────────────────────────────────┐
│  IMPORTANT — capture the write DSN now                          │
│                                                                 │
│  This is the only time tennetctl will display it.               │
│  Export it as $DATABASE_URL on every process start:             │
│                                                                 │
│  export DATABASE_URL="{write_dsn}"
│                                                                 │
│  Press Enter once you have stored it.                           │
└─────────────────────────────────────────────────────────────────┘
"""
    sys.stderr.write(banner)

    if not yes_flag:
        try:
            input("  [Press Enter to continue] ")
        except (EOFError, KeyboardInterrupt):
            pass
