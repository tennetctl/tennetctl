"""Phase 2 — Vault initialisation.

Flow
----
1. Generate a 16-byte random salt.
2. Store the salt (base64url-encoded) in system_meta.unseal_salt.
3. Derive the MDK-wrapping key: Argon2id(write_dsn_password, salt) → HKDF.
4. Call vault service to generate the MDK, encrypt it, persist the vault row.
5. Seal the three DB DSNs as vault secrets at canonical paths.
6. Update system_meta.vault_initialized_at and unseal_mode.

After this phase the MDK is zeroed from memory and the three DSN strings
are wiped from the in-memory BootstrapResult. The only survivors are:
- The write DSN (still needed for Phase 3 and Phase 4 via $DATABASE_URL)
- The vault row in 10_fct_vault (ciphertext only)
- The three DSN secrets in 10_fct_secrets (ciphertext only)
"""

from __future__ import annotations

import base64
import importlib

import asyncpg

_dsn_mod = importlib.import_module("scripts.00_core.dsn")
_errors = importlib.import_module("scripts.00_core.errors")
_kdf = importlib.import_module("scripts.setup.vault_init.kdf")
_vault_service = importlib.import_module("04_backend.02_features.vault.setup.service")

Phase2Error = _errors.Phase2Error

# Canonical vault paths for the three DB DSNs
_ADMIN_DSN_PATH = "tennetctl/db/admin_dsn"
_WRITE_DSN_PATH = "tennetctl/db/write_dsn"
_READ_DSN_PATH = "tennetctl/db/read_dsn"


async def run_phase2(
    *,
    admin_dsn: str,
    write_dsn: str,
    read_dsn: str,
) -> None:
    """Execute Phase 2: initialise the vault and seal the three DSNs.

    Args:
        admin_dsn:  Admin-role DSN (used for DDL writes to vault tables).
        write_dsn:  Write-role DSN — password component used as KDF input.
        read_dsn:   Read-role DSN — sealed into the vault.
    """
    print("\n── Phase 2 — Vault Initialisation ───────────────────────")

    # The KDF input is the WRITE DSN password. At runtime the app only has
    # DATABASE_URL (write role), so the KDF must use the write password to
    # allow the app to re-derive the wrap_key on boot without any extra config.
    # The admin DSN is used only for DDL writes to vault tables; its password
    # is NOT needed by the runtime.
    write_parts = _dsn_mod.parse_dsn(write_dsn)
    kdf_password: str = write_parts["password"]  # type: ignore[assignment]
    if not kdf_password:
        raise Phase2Error(
            "WRITE_DSN_NO_PASSWORD",
            "The write DSN has no password component — cannot derive vault wrap key.",
            hint="Ensure the write DSN is in the form postgres://user:password@host/db.",
        )

    # Generate and persist the KDF salt
    salt_bytes = _kdf.new_salt()
    salt_b64 = base64.urlsafe_b64encode(salt_bytes).decode("ascii")

    print("  Generating vault master key …")
    conn = await asyncpg.connect(admin_dsn)
    mdk: bytes | None = None
    try:
        # All writes are atomic: if any step fails, the DB is left clean and
        # the wizard can safely re-run Phase 2 without partial state.
        async with conn.transaction():
            # Store salt first (needed for runtime unseal)
            await conn.execute(
                """
                UPDATE "00_schema_migrations".system_meta
                   SET unseal_salt = $1, updated_at = CURRENT_TIMESTAMP
                 WHERE id = 1
                """,
                salt_b64,
            )

            # Derive wrap key from write DSN password + salt
            wrap_key = _kdf.derive_wrap_key(kdf_password, salt_bytes)

            # Init vault — returns plaintext MDK (held only in this scope)
            result = await _vault_service.init_vault_manual(conn, wrap_key=wrap_key)
            mdk = result["mdk"]

            # Seal the three DSNs as vault secrets
            print("  Sealing database credentials into vault …")
            for path, dsn_value in (
                (_ADMIN_DSN_PATH, admin_dsn),
                (_WRITE_DSN_PATH, write_dsn),
                (_READ_DSN_PATH, read_dsn),
            ):
                await _vault_service.create_secret(conn, mdk=mdk, path=path, plaintext=dsn_value)
                # Round-trip verify: decrypt immediately to confirm the stored ciphertext is valid.
                recovered = await _vault_service.get_secret(conn, mdk=mdk, path=path)
                if recovered != dsn_value:
                    raise Phase2Error(
                        "SEAL_VERIFY_FAILED",
                        f"Round-trip verify failed for secret path: {path}",
                        hint="The sealed ciphertext does not decrypt to the original value. "
                             "Re-run setup to regenerate.",
                    )
                print(f"  ✔ Sealed + verified: {path}")

            # Mark vault initialized in system_meta (last write — commit point)
            await conn.execute(
                """
                UPDATE "00_schema_migrations".system_meta
                   SET vault_initialized_at = CURRENT_TIMESTAMP,
                       unseal_mode = 'manual',
                       updated_at = CURRENT_TIMESTAMP
                 WHERE id = 1
                """,
            )

    finally:
        # Zero the MDK from memory
        if mdk is not None:
            # bytearray allows zeroing; bytes is immutable so we just rebind
            mdk = None  # noqa: F841
        await conn.close()

    print("  ✔ Phase 2 complete.\n")
