"""DSN (database connection string) utilities.

Handles the postgres:// URI format used throughout the codebase.
Stdlib only — no asyncpg dependency.
"""

from __future__ import annotations

from urllib.parse import quote, unquote, urlparse, urlunparse


def parse_dsn(dsn: str) -> dict[str, str | int]:
    """Parse a postgres:// URI into a dict with keys:
    user, password, host, port, dbname.

    Raises ValueError on malformed input.
    """
    parsed = urlparse(dsn)
    if parsed.scheme not in ("postgres", "postgresql"):
        raise ValueError(f"Not a postgres DSN: {dsn!r}")

    return {
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "dbname": (parsed.path or "/").lstrip("/") or "postgres",
    }


def build_dsn(
    *,
    user: str,
    password: str,
    host: str = "localhost",
    port: int = 5432,
    dbname: str,
) -> str:
    """Build a postgres:// URI from parts. Special characters in user/password
    are percent-encoded."""
    netloc = f"{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}"
    return urlunparse(("postgresql", netloc, f"/{dbname}", "", "", ""))


def mask_dsn(dsn: str) -> str:
    """Replace the password in a DSN with '****' for safe logging."""
    try:
        parts = parse_dsn(dsn)
    except ValueError:
        return "<invalid dsn>"
    return build_dsn(
        user=parts["user"],  # type: ignore[arg-type]
        password="****",
        host=parts["host"],  # type: ignore[arg-type]
        port=parts["port"],  # type: ignore[arg-type]
        dbname=parts["dbname"],  # type: ignore[arg-type]
    )
