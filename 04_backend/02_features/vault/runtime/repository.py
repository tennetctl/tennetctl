"""Vault runtime repository — read vault status from DB."""

from __future__ import annotations


async def fetch_vault_status(conn: object) -> dict | None:
    """Return vault status row (joined with dim tables) or None if not init."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT
            v.id,
            vs.code   AS status,
            vm.code   AS unseal_mode,
            v.initialized_at
        FROM "02_vault"."10_fct_vault" v
        JOIN "02_vault"."02_dim_unseal_modes"  vm ON v.unseal_mode_id = vm.id
        JOIN "02_vault"."01_dim_vault_statuses" vs ON v.status_id     = vs.id
        LIMIT 1
        """
    )
    return dict(row) if row else None
