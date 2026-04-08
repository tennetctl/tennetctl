"""Shared helpers for resolving IAM EAV dim IDs by code.

No process-level cache — callers operate per-request and we cannot safely
share a cache across test fixtures that recreate the schema.  Each call
issues at most one lightweight SELECT on a small dim table.
"""

from __future__ import annotations


async def iam_attr_ids(conn: object, entity_code: str) -> dict[str, int]:
    """Return code→id mapping for all attr_defs of the given entity type.

    Args:
        conn:         asyncpg connection.
        entity_code:  e.g. 'iam_user', 'iam_session', 'iam_org', 'iam_workspace'.

    Returns:
        Dict mapping attr_def code to its SMALLINT id.
    """
    rows = await conn.fetch(  # type: ignore[union-attr]
        """
        SELECT d.id, d.code
          FROM "03_iam"."07_dim_attr_defs" d
          JOIN "03_iam"."06_dim_entity_types" et ON d.entity_type_id = et.id
         WHERE et.code = $1
        """,
        entity_code,
    )
    return {r["code"]: r["id"] for r in rows}


async def iam_entity_type_id(conn: object, entity_code: str) -> int:
    """Return the id of the given entity type.

    Args:
        conn:         asyncpg connection.
        entity_code:  e.g. 'iam_session', 'iam_org'.

    Returns:
        The SMALLINT id for that entity type.

    Raises:
        KeyError if the code does not exist.
    """
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id
          FROM "03_iam"."06_dim_entity_types"
         WHERE code = $1
        """,
        entity_code,
    )
    if row is None:
        raise KeyError(f"Unknown IAM entity type: {entity_code!r}")
    return int(row["id"])
