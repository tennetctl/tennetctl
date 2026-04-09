"""Runtime vault state — MDK held in process memory after boot unseal.

Boot sequence:
1. App starts, reads DATABASE_URL from env.
2. init_pool() opens the asyncpg pool (write-role DSN).
3. unseal_on_boot() connects with the same DSN, reads system_meta.unseal_salt,
   derives the wrap_key (Argon2id → HKDF), decrypts the MDK from 10_fct_vault.
4. MDK is stored in this module's _mdk variable for the lifetime of the process.
5. Routes call get_mdk() to obtain it for vault operations.

Security note: MDK lives in Python heap for the process lifetime. This is
intentional for v1 manual-unseal mode. The KMS backends (Azure/AWS) will
hold the MDK only in a short-lived scope after each decrypt call.
"""

from __future__ import annotations

import asyncio
import base64
import importlib
import os

_mdk: bytes | None = None
_unseal_lock = asyncio.Lock()

_kdf = importlib.import_module("scripts.setup.vault_init.kdf")
_vault_service = importlib.import_module("04_backend.02_features.vault.setup.service")
_dsn_mod = importlib.import_module("scripts.00_core.dsn")


def get_mdk() -> bytes:
    """Return the in-memory MDK. Raises RuntimeError if vault not unsealed."""
    if _mdk is None:
        raise RuntimeError("Vault not unsealed — call unseal_on_boot() first.")
    return _mdk


async def unseal_on_boot(pool: object) -> None:  # pool: asyncpg.Pool
    """Derive wrap_key from DATABASE_URL and decrypt MDK from vault.

    Called once during the FastAPI lifespan startup. The lock prevents a
    race if lifespan is ever called concurrently (e.g. test teardown/setup).
    """
    global _mdk
    if _mdk is not None:
        return

    async with _unseal_lock:
        # Re-check inside the lock.
        if _mdk is not None:
            return

        dsn = os.environ.get("DATABASE_URL", "")
        if not dsn:
            raise RuntimeError("DATABASE_URL is not set — cannot unseal vault.")

        dsn_parts = _dsn_mod.parse_dsn(dsn)
        password: str = dsn_parts.get("password") or ""

        import asyncpg  # noqa: PLC0415

        conn = await asyncpg.connect(dsn)
        try:
            row = await conn.fetchrow(
                'SELECT unseal_salt FROM "00_schema_migrations".system_meta WHERE id = 1'
            )
            if row is None or row["unseal_salt"] is None:
                raise RuntimeError("system_meta.unseal_salt is NULL — was setup completed?")

            salt_bytes = base64.urlsafe_b64decode(row["unseal_salt"])
            wrap_key = _kdf.derive_wrap_key(password, salt_bytes)
            _mdk = await _vault_service.unseal_vault(conn, wrap_key=wrap_key)
        finally:
            await conn.close()
