"""Vault setup repository — raw SQL against 02_vault tables.

All writes go to raw fct_* tables plus 20_dtl_attrs.
All reads go via v_* views (except the key-material read needed for unseal,
which reads 20_dtl_attrs directly because v_vault excludes key material).

Functions accept an asyncpg Connection, never a Pool.
"""

from __future__ import annotations

# Entity type codes — stable, match 06_dim_entity_types seed.
_VAULT_ENTITY_CODE  = "vault"
_SECRET_ENTITY_CODE = "secret"


async def _vault_entity_type_id(conn: object) -> int:
    """Resolve the vault entity type ID from the dim table."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        'SELECT id FROM "02_vault"."06_dim_entity_types" WHERE code = $1',
        _VAULT_ENTITY_CODE,
    )
    if row is None:
        raise RuntimeError("vault entity type not found in 06_dim_entity_types")
    return row["id"]


async def _secret_entity_type_id(conn: object) -> int:
    """Resolve the secret entity type ID from the dim table."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        'SELECT id FROM "02_vault"."06_dim_entity_types" WHERE code = $1',
        _SECRET_ENTITY_CODE,
    )
    if row is None:
        raise RuntimeError("secret entity type not found in 06_dim_entity_types")
    return row["id"]


async def _attr_ids(conn: object, entity_type_id: int) -> dict[str, int]:
    """Return a code→id mapping for all attr_defs belonging to entity_type_id."""
    rows = await conn.fetch(  # type: ignore[union-attr]
        'SELECT id, code FROM "02_vault"."07_dim_attr_defs" WHERE entity_type_id = $1',
        entity_type_id,
    )
    return {r["code"]: r["id"] for r in rows}


async def insert_vault_row(
    conn: object,
    *,
    id: str,
    unseal_mode_id: int,
    status_id: int,
    mdk_ciphertext: str,
    mdk_nonce: str,
    unseal_key_hash: str,
    initialized_at_iso: str,
) -> None:
    """Insert the vault singleton fct row then write key-material attrs.

    Pure-EAV: the fct row holds only FK IDs. All cryptographic data goes
    to 20_dtl_attrs so new unseal modes can add attrs without ALTER TABLE.
    """
    # Insert the lean fct row (FK IDs + housekeeping only).
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "02_vault"."10_fct_vault"
            (id, status_id, unseal_mode_id, created_at, updated_at)
        VALUES ($1, $2, $3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        id,
        status_id,
        unseal_mode_id,
    )

    # Write key-material attrs.  The attr_def IDs are resolved by code so
    # this function survives IDENTITY shifts across environments.
    et_id = await _vault_entity_type_id(conn)
    ids = await _attr_ids(conn, et_id)

    text_attrs = {
        "mdk_ciphertext":  mdk_ciphertext,
        "mdk_nonce":       mdk_nonce,
        "unseal_key_hash": unseal_key_hash,
        "initialized_at":  initialized_at_iso,
    }
    for code, value in text_attrs.items():
        await conn.execute(  # type: ignore[union-attr]
            """
            INSERT INTO "02_vault"."20_dtl_attrs"
                (entity_type_id, entity_id, attr_def_id, key_text)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (entity_type_id, entity_id, attr_def_id) DO UPDATE
                SET key_text = EXCLUDED.key_text,
                    updated_at = CURRENT_TIMESTAMP
            """,
            et_id,
            id,
            ids[code],
            value,
        )


async def update_vault_status(conn: object, vault_id: str, status_id: int) -> None:
    """Update the vault status_id on the fct row (seal/unseal operations)."""
    await conn.execute(  # type: ignore[union-attr]
        """
        UPDATE "02_vault"."10_fct_vault"
           SET status_id = $1, updated_at = CURRENT_TIMESTAMP
         WHERE id = $2
        """,
        status_id,
        vault_id,
    )


async def fetch_vault_row(conn: object) -> dict | None:
    """Fetch the vault singleton row including key material (for unsealing).

    Reads 20_dtl_attrs directly — v_vault deliberately excludes key material.
    Returns None if no vault has been initialised yet.
    """
    fct_row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, status_id, unseal_mode_id
          FROM "02_vault"."10_fct_vault"
         WHERE deleted_at IS NULL
         LIMIT 1
        """
    )
    if fct_row is None:
        return None

    vault_id = fct_row["id"]
    et_id = await _vault_entity_type_id(conn)
    ids = await _attr_ids(conn, et_id)

    # Fetch all text attrs for this vault in one query.
    attr_rows = await conn.fetch(  # type: ignore[union-attr]
        """
        SELECT attr_def_id, key_text
          FROM "02_vault"."20_dtl_attrs"
         WHERE entity_type_id = $1 AND entity_id = $2
        """,
        et_id,
        vault_id,
    )

    # Invert ids map to look up code by id.
    id_to_code = {v: k for k, v in ids.items()}
    attrs = {id_to_code[r["attr_def_id"]]: r["key_text"] for r in attr_rows
             if r["attr_def_id"] in id_to_code}

    return {
        "id":              vault_id,
        "status_id":       fct_row["status_id"],
        "unseal_mode_id":  fct_row["unseal_mode_id"],
        "mdk_ciphertext":  attrs.get("mdk_ciphertext"),
        "mdk_nonce":       attrs.get("mdk_nonce"),
        "unseal_key_hash": attrs.get("unseal_key_hash"),
    }


async def insert_secret(
    conn: object,
    *,
    id: str,
    path: str,
    ciphertext: str,
    nonce: str,
    created_by: str | None = None,
) -> None:
    """Insert a new secret row into 10_fct_secrets (pure-EAV).

    Writes the lean fct row (identity + housekeeping only) then inserts
    path, ciphertext, and nonce into 20_dtl_attrs.
    """
    # Insert the lean fct row — no wide columns.
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "02_vault"."10_fct_secrets"
            (id, is_active, is_test,
             created_by, updated_by, created_at, updated_at)
        VALUES ($1, TRUE, FALSE,
                $2, $2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        id,
        created_by,
    )

    # Resolve secret entity type id + attr_def ids by code.
    et_id = await _secret_entity_type_id(conn)
    ids = await _attr_ids(conn, et_id)

    # Write path, ciphertext, nonce as EAV attrs.
    text_attrs = {
        "path":       path,
        "ciphertext": ciphertext,
        "nonce":      nonce,
    }
    for code, value in text_attrs.items():
        await conn.execute(  # type: ignore[union-attr]
            """
            INSERT INTO "02_vault"."20_dtl_attrs"
                (entity_type_id, entity_id, attr_def_id, key_text)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (entity_type_id, entity_id, attr_def_id) DO UPDATE
                SET key_text = EXCLUDED.key_text,
                    updated_at = CURRENT_TIMESTAMP
            """,
            et_id,
            id,
            ids[code],
            value,
        )


async def fetch_secret_by_path(conn: object, path: str) -> dict | None:
    """Fetch ciphertext + nonce for a live secret by path.

    Resolves entity_id via the path attr in 20_dtl_attrs, then checks the
    fct row for liveness (is_active + deleted_at), then fetches crypto attrs.
    Returns None if not found, soft-deleted, or inactive.
    """
    et_id = await _secret_entity_type_id(conn)
    ids = await _attr_ids(conn, et_id)

    # Step 1: find entity_id by path value.
    path_row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT entity_id
          FROM "02_vault"."20_dtl_attrs"
         WHERE attr_def_id = $1
           AND key_text    = $2
        """,
        ids["path"],
        path,
    )
    if path_row is None:
        return None

    entity_id = path_row["entity_id"]

    # Step 2: check fct row is live and active.
    fct_row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, is_active, deleted_at
          FROM "02_vault"."10_fct_secrets"
         WHERE id = $1
        """,
        entity_id,
    )
    if fct_row is None or not fct_row["is_active"] or fct_row["deleted_at"] is not None:
        return None

    # Step 3: fetch all attrs for this entity.
    attr_rows = await conn.fetch(  # type: ignore[union-attr]
        """
        SELECT attr_def_id, key_text
          FROM "02_vault"."20_dtl_attrs"
         WHERE entity_type_id = $1
           AND entity_id      = $2
        """,
        et_id,
        entity_id,
    )

    id_to_code = {v: k for k, v in ids.items()}
    attrs = {id_to_code[r["attr_def_id"]]: r["key_text"] for r in attr_rows
             if r["attr_def_id"] in id_to_code}

    return {
        "id":         entity_id,
        "path":       attrs.get("path"),
        "ciphertext": attrs.get("ciphertext"),
        "nonce":      attrs.get("nonce"),
    }
