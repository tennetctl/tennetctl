"""JWT sign and verify utilities.

The JWT secret is a 32-byte random value stored in vault at path
``tennetctl/iam/jwt_secret``. It is seeded by the setup wizard (phase 4).

The secret is cached after the first vault read so only one decrypt call
is made per process lifetime.

Algorithm : HS256 (HMAC-SHA256)
Payload   : {sub: user_id, sid: session_id, jti: uuid7, iat: unix_ts, exp: unix_ts}
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import importlib
import json
import secrets
import time

_vault_state = importlib.import_module("04_backend.01_core.vault_state")
_vault_service = importlib.import_module("04_backend.02_features.vault.setup.service")
_id_mod = importlib.import_module("scripts.00_core._id")

_JWT_SECRET_PATH = "tennetctl/iam/jwt_secret"
_cached_secret: bytes | None = None
_jwt_lock = asyncio.Lock()


async def _get_jwt_secret() -> bytes:
    """Return the JWT signing key (bytes). Reads from vault on first call.

    The lock prevents multiple concurrent requests from racing to populate
    the cache on the first request after boot.
    """
    global _cached_secret
    if _cached_secret is not None:
        return _cached_secret

    async with _jwt_lock:
        # Re-check inside the lock — another coroutine may have populated it.
        if _cached_secret is not None:
            return _cached_secret

        import asyncpg  # noqa: PLC0415
        import os  # noqa: PLC0415

        dsn = os.environ.get("DATABASE_URL", "")
        conn = await asyncpg.connect(dsn)
        try:
            mdk = _vault_state.get_mdk()
            secret_b64 = await _vault_service.get_secret(conn, mdk=mdk, path=_JWT_SECRET_PATH)
            _cached_secret = base64.urlsafe_b64decode(secret_b64)
        finally:
            await conn.close()

    return _cached_secret


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * (padding % 4))


async def issue_token(user_id: str, ttl_seconds: int, *, session_id: str) -> str:
    """Sign and return a JWT access token.

    Args:
        user_id:     The subject UUID.
        ttl_seconds: Token lifetime in seconds.
        session_id:  The session PK — stored as ``sid`` claim so routes can
                     call touch_session and similar without a DB lookup.

    Returns:
        A signed compact JWT string.
    """
    secret = await _get_jwt_secret()
    now = int(time.time())
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(
        json.dumps(
            {
                "sub": user_id,
                "sid": session_id,
                "jti": _id_mod.uuid7(),
                "iat": now,
                "exp": now + ttl_seconds,
            }
        ).encode()
    )
    signing_input = f"{header}.{payload}"
    sig = hmac.new(secret, signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(sig)}"


def verify_token(token: str) -> dict:
    """Verify signature and expiry; return the decoded payload dict.

    Raises ValueError on any verification failure.
    """
    # Synchronous — reads _cached_secret which must be populated at boot.
    if _cached_secret is None:
        raise ValueError("JWT secret not loaded — vault not unsealed.")

    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed JWT.")

    header_b64, payload_b64, sig_b64 = parts

    # Verify the algorithm header before touching the signature.
    # Rejecting alg=none and unexpected algorithms prevents downgrade attacks.
    try:
        header = json.loads(_b64url_decode(header_b64))
    except Exception as exc:
        raise ValueError(f"JWT header decode failed: {exc}") from exc

    if header.get("alg") != "HS256":
        raise ValueError(f"Unsupported JWT algorithm: {header.get('alg')!r}. Expected HS256.")

    signing_input = f"{header_b64}.{payload_b64}"
    expected_sig = hmac.new(_cached_secret, signing_input.encode(), hashlib.sha256).digest()
    provided_sig = _b64url_decode(sig_b64)

    if not hmac.compare_digest(expected_sig, provided_sig):
        raise ValueError("JWT signature invalid.")

    payload = json.loads(_b64url_decode(payload_b64))
    if payload.get("exp", 0) < int(time.time()):
        raise ValueError("JWT expired.")

    return payload


async def warm_cache() -> None:
    """Pre-load the JWT secret at boot. Called during lifespan startup."""
    await _get_jwt_secret()


def generate_refresh_token() -> str:
    """Return a 40-byte URL-safe random refresh token string."""
    return secrets.token_urlsafe(40)
