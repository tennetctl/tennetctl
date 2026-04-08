"""Argon2id password hashing for IAM authentication.

Uses argon2-cffi's high-level PasswordHasher interface which handles
salt generation, PHC string formatting, and automatic rehashing.

Parameters follow OWASP Password Storage Cheat Sheet (2024):
- Algorithm: Argon2id (combines Argon2i + Argon2d defences)
- time_cost: 3 iterations
- memory_cost: 65536 KiB (64 MiB) — punishes GPU-based attacks
- parallelism: 1 thread (keep low; the hash runs outside DB transactions)
- hash_len: 32 bytes (256-bit derived key)
- salt_len: 16 bytes (128-bit random, generated per-hash by the library)

Output format: PHC string, e.g.
  ``$argon2id$v=19$m=65536,t=3,p=1$<b64salt>$<b64hash>``

The PHC string is safe to store directly in ``03_iam.20_dtl_attrs`` as
``key_text`` for the ``password_hash`` attribute.
"""

from __future__ import annotations

import hashlib
import hmac

from argon2 import PasswordHasher, exceptions

_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=1,
    hash_len=32,
    salt_len=16,
)


def hash_password(plain: str) -> str:
    """Hash *plain* with Argon2id and return the PHC-format string.

    A fresh random salt is generated on every call, so the same
    plaintext produces a different hash each time.
    """
    return _HASHER.hash(plain)


def verify_password(phc: str, plain: str) -> bool:
    """Return True if *plain* matches the stored *phc* hash, False otherwise.

    Never raises — invalid hashes and wrong passwords both return False.
    """
    try:
        return _HASHER.verify(phc, plain)
    except (
        exceptions.VerifyMismatchError,
        exceptions.VerificationError,
        exceptions.InvalidHashError,
    ):
        return False


def hash_token(token: str) -> str:
    """Hash an opaque token (e.g. refresh token) with BLAKE2b-256.

    Returns a hex-encoded digest. BLAKE2b is fast and appropriate for
    high-entropy tokens (no need for Argon2id's GPU-hardening here because
    the input is a 40-byte CSPRNG token, not a user password).
    """
    return hashlib.blake2b(token.encode("utf-8"), digest_size=32).hexdigest()


def verify_token_hash(stored_hex: str, token: str) -> bool:
    """Constant-time compare a stored BLAKE2b hex digest against *token*.

    Returns False instead of raising on any input error.

    Legacy fallback: if the stored value looks like an Argon2id PHC string
    (starts with $argon2id$), fall back to Argon2id verification so that
    sessions created before the BLAKE2b migration can still be refreshed.
    New sessions always use BLAKE2b.
    """
    if not stored_hex:
        return False
    try:
        if stored_hex.startswith("$argon2"):
            # Legacy Argon2id hash — use the password verifier.
            return verify_password(stored_hex, token)
        expected = hashlib.blake2b(token.encode("utf-8"), digest_size=32).hexdigest()
        return hmac.compare_digest(stored_hex, expected)
    except Exception:
        return False
