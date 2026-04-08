"""Vault runtime repository — read vault status from DB."""

from __future__ import annotations


async def fetch_vault_status(conn: object) -> dict | None:
    """Return vault status row from the v_vault view or None if not init."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, status, unseal_mode, initialized_at
          FROM "02_vault".v_vault
         LIMIT 1
        """
    )
    return dict(row) if row else None
