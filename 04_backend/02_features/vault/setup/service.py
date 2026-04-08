"""Vault setup service — business logic for vault init and secret operations.

Public API
----------
init_vault_manual(conn, *, wrap_key)  -> dict
    Generate the MDK, encrypt it with wrap_key, persist the vault row.
    Returns ``{'mdk': bytes, 'vault_id': str}``.
    The caller is responsible for zeroing ``mdk`` from memory when done.

create_secret(conn, *, mdk, path, plaintext)  -> dict
    Envelope-encrypt ``plaintext`` under ``mdk`` and persist to
    ``10_fct_secrets``.  The ``path`` is used as AES-GCM AAD so ciphertext
    is cryptographically bound to its canonical path.
    Returns ``{'id': str, 'path': str}``.

get_secret(conn, *, mdk, path)  -> str
    Decrypt and return the plaintext value for ``path``.
    Raises VaultError("SECRET_NOT_FOUND") if missing.
    Raises ``cryptography.exceptions.InvalidSignature`` (via AESGCM) on
    tampered ciphertext — let this propagate to the caller.

Encryption details
------------------
Algorithm : AES-256-GCM (AESGCM from cryptography.hazmat)
MDK       : 32 random bytes, encrypted with ``wrap_key`` (AES-256-GCM)
Secrets   : Each secret encrypted directly with the MDK (no per-secret DEK
            in v1 — simplified from the original design; DEK layer adds
            no security when MDK is the only key in play).
AAD       : ``path.encode("utf-8")`` — binds ciphertext to its path.
Nonces    : 12 random bytes per encryption event; never reused.
Storage   : base64url-encoded TEXT columns.
"""

from __future__ import annotations

import base64
import importlib
import secrets
from datetime import datetime, timezone

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_id_mod = importlib.import_module("scripts.00_core._id")
_repo = importlib.import_module("04_backend.02_features.vault.setup.repository")
_errors = importlib.import_module("scripts.00_core.errors")

VaultError = _errors.VaultError

# Sentinel actor ID used for system-originated writes (wizard install).
SYSTEM_INSTALLER_ACTOR_ID = "00000000-0000-7000-8000-000000000001"

_MDK_WRAP_AAD = b"tennetctl/vault/mdk/v1"


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def _b64_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s)


async def init_vault_manual(conn: object, *, wrap_key: bytes) -> dict:
    """Generate the vault MDK, encrypt it with *wrap_key*, persist the vault row.

    This is the Phase 2 entry point for the manual unseal mode.

    Args:
        conn:      asyncpg Connection with DDL (admin) or DML (write) privileges.
        wrap_key:  32-byte AES key derived from the DB password + salt via KDF.

    Returns:
        ``{'mdk': bytes, 'vault_id': str}``
        The MDK is returned in plaintext so Phase 2 can immediately use it
        to seed the initial secrets. The caller MUST zero this after use.

    Raises:
        VaultError("VAULT_ALREADY_INITIALIZED") if a vault row already exists.
    """
    existing = await _repo.fetch_vault_row(conn)
    if existing is not None:
        raise VaultError(
            "VAULT_ALREADY_INITIALIZED",
            "A vault row already exists — call is idempotent; skipping.",
        )

    mdk = secrets.token_bytes(32)
    mdk_nonce = secrets.token_bytes(12)

    mdk_ciphertext_bytes = AESGCM(wrap_key).encrypt(mdk_nonce, mdk, _MDK_WRAP_AAD)

    # BLAKE2b hash of wrap_key — stored so the runtime can verify it derived
    # the same key before attempting GCM decryption.
    import hashlib  # noqa: PLC0415
    unseal_key_hash = hashlib.blake2b(wrap_key, digest_size=32).hexdigest()

    vault_id = _id_mod.uuid7()
    initialized_at_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    await _repo.insert_vault_row(
        conn,
        id=vault_id,
        unseal_mode_id=1,   # manual
        status_id=2,        # unsealed (MDK is live in memory)
        mdk_ciphertext=_b64_encode(mdk_ciphertext_bytes),
        mdk_nonce=_b64_encode(mdk_nonce),
        unseal_key_hash=unseal_key_hash,
        initialized_at_iso=initialized_at_iso,
    )

    return {"mdk": mdk, "vault_id": vault_id}


async def create_secret(
    conn: object,
    *,
    mdk: bytes,
    path: str,
    plaintext: str,
    actor_id: str = SYSTEM_INSTALLER_ACTOR_ID,
) -> dict:
    """Encrypt *plaintext* and store it at *path* in ``10_fct_secrets``.

    The ``path`` is used as AES-GCM authenticated additional data (AAD),
    binding the ciphertext to its canonical path. Moving ciphertext to a
    different path causes decryption to fail with an authentication error.

    Args:
        conn:      asyncpg Connection.
        mdk:       32-byte Master Data Key (held in memory after vault unseal).
        path:      Slash-delimited secret identifier, e.g. "tennetctl/db/write_dsn".
        plaintext: The secret value to encrypt.
        actor_id:  UUID of the creating actor (defaults to system installer).

    Returns:
        ``{'id': str, 'path': str}``
    """
    nonce = secrets.token_bytes(12)
    aad = path.encode("utf-8")
    ciphertext_bytes = AESGCM(mdk).encrypt(nonce, plaintext.encode("utf-8"), aad)

    secret_id = _id_mod.uuid7()
    await _repo.insert_secret(
        conn,
        id=secret_id,
        path=path,
        ciphertext=_b64_encode(ciphertext_bytes),
        nonce=_b64_encode(nonce),
        created_by=actor_id,
    )
    return {"id": secret_id, "path": path}


async def get_secret(conn: object, *, mdk: bytes, path: str) -> str:
    """Decrypt and return the plaintext value for *path*.

    Args:
        conn:  asyncpg Connection.
        mdk:   32-byte Master Data Key.
        path:  The secret path used at creation time.

    Returns:
        Plaintext string. Never logged or persisted.

    Raises:
        VaultError("SECRET_NOT_FOUND") if the path does not exist or is deleted.
        cryptography.exceptions.InvalidTag if ciphertext is tampered.
    """
    row = await _repo.fetch_secret_by_path(conn, path)
    if row is None:
        raise VaultError(
            "SECRET_NOT_FOUND",
            f"Secret not found at path {path!r}.",
            hint="Ensure the vault is initialised and the path is correct.",
        )

    ciphertext_bytes = _b64_decode(row["ciphertext"])
    nonce = _b64_decode(row["nonce"])
    aad = path.encode("utf-8")

    plaintext_bytes = AESGCM(mdk).decrypt(nonce, ciphertext_bytes, aad)
    return plaintext_bytes.decode("utf-8")


async def unseal_vault(conn: object, *, wrap_key: bytes) -> bytes:
    """Derive the plaintext MDK from the persisted ciphertext.

    Called on application boot (and by the setup wizard after Phase 2 to
    verify the round-trip works).

    Args:
        conn:      asyncpg Connection.
        wrap_key:  32-byte key derived from ``$DATABASE_URL`` password + salt.

    Returns:
        32-byte plaintext MDK ready for use with ``get_secret`` / ``create_secret``.

    Raises:
        VaultError("VAULT_NOT_INITIALIZED") if no vault row exists.
        VaultError("UNSEAL_KEY_HASH_MISMATCH") if the derived wrap_key does not
        match the stored hash — indicates the DB password was rotated without
        re-wrapping the MDK.
        cryptography.exceptions.InvalidTag on bit-flip or corruption.
    """
    import hashlib  # noqa: PLC0415

    row = await _repo.fetch_vault_row(conn)
    if row is None:
        raise VaultError(
            "VAULT_NOT_INITIALIZED",
            "No vault row found in 10_fct_vault.",
            hint="Run 'tennetctl setup' to initialise the vault.",
        )

    # Verify the wrap_key before attempting decryption
    derived_hash = hashlib.blake2b(wrap_key, digest_size=32).hexdigest()
    if derived_hash != row["unseal_key_hash"]:
        raise VaultError(
            "UNSEAL_KEY_HASH_MISMATCH",
            "The derived wrap key does not match the stored hash. "
            "The database password may have been rotated without re-wrapping the MDK.",
            hint="Run 'tennetctl vault rotate-unseal-key' to re-wrap the MDK with the new password.",
        )

    ciphertext_bytes = _b64_decode(row["mdk_ciphertext"])
    nonce = _b64_decode(row["mdk_nonce"])
    mdk = AESGCM(wrap_key).decrypt(nonce, ciphertext_bytes, _MDK_WRAP_AAD)
    return mdk
