"""Vault runtime service — status and unseal operations."""

from __future__ import annotations

import importlib

_repo = importlib.import_module("04_backend.02_features.vault.runtime.repository")
_vault_state = importlib.import_module("04_backend.01_core.vault_state")


async def get_vault_status(conn: object) -> dict:
    """Return a dict suitable for the VaultStatusData schema.

    Always returns a valid dict even when no vault row exists.
    """
    row = await _repo.fetch_vault_status(conn)
    if row is None:
        return {
            "initialized": False,
            "status": "sealed",
            "unseal_mode": "unknown",
            "initialized_at": None,
        }
    return {
        "initialized": row["initialized_at"] is not None,
        "status": row["status"],
        "unseal_mode": row["unseal_mode"],
        "initialized_at": row["initialized_at"],
    }


def is_unsealed() -> bool:
    """True if the vault MDK is loaded in memory."""
    try:
        _vault_state.get_mdk()
        return True
    except RuntimeError:
        return False
