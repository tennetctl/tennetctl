"""Vault setup repository — raw SQL against 02_vault tables.

All writes go to raw fct_* tables.
All reads go via v_* views (except the key-material read needed for unseal).

Functions accept an asyncpg Connection, never a Pool.
"""

from __future__ import annotations


async def insert_vault_row(
    conn: object,
    *,
    id: str,
    unseal_mode_id: int,
    status_id: int,
    mdk_ciphertext: str,
    mdk_nonce: str,
    unseal_key_hash: str,
) -> None:
    """Insert the vault singleton row in manual unseal mode."""
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "02_vault"."10_fct_vault"
            (id, status_id, unseal_mode_id, mdk_ciphertext, mdk_nonce,
             unseal_key_hash, initialized_at, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        id,
        status_id,
        unseal_mode_id,
        mdk_ciphertext,
        mdk_nonce,
        unseal_key_hash,
    )


async def fetch_vault_row(conn: object) -> dict | None:
    """Fetch the vault singleton row including key material (for unsealing).

    Returns None if no vault has been initialised yet.
    Never exposed to API responses — use v_vault for that.
    """
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, status_id, unseal_mode_id,
               mdk_ciphertext, mdk_nonce, unseal_key_hash
          FROM "02_vault"."10_fct_vault"
         LIMIT 1
        """
    )
    return dict(row) if row else None


async def insert_secret(
    conn: object,
    *,
    id: str,
    path: str,
    ciphertext: str,
    nonce: str,
    created_by: str | None = None,
) -> None:
    """Insert a new secret row into 10_fct_secrets."""
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "02_vault"."10_fct_secrets"
            (id, path, ciphertext, nonce, is_active, is_test,
             created_by, updated_by, created_at, updated_at)
        VALUES ($1, $2, $3, $4, TRUE, FALSE,
                $5, $5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        id,
        path,
        ciphertext,
        nonce,
        created_by,
    )


async def fetch_secret_by_path(conn: object, path: str) -> dict | None:
    """Fetch ciphertext + nonce for a live secret by path.

    Returns None if not found or soft-deleted.
    """
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, path, ciphertext, nonce
          FROM "02_vault"."10_fct_secrets"
         WHERE path = $1
           AND deleted_at IS NULL
           AND is_active = TRUE
        """,
        path,
    )
    return dict(row) if row else None
