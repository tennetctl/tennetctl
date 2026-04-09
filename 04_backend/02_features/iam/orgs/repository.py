"""IAM orgs repository — reads v_orgs, writes 10_fct_orgs + 20_dtl_attrs."""

from __future__ import annotations

import importlib

_iam_ids = importlib.import_module("04_backend.02_features.iam._iam_attr_ids")
_id_mod = importlib.import_module("scripts.00_core._id")


async def _active_status_id(conn: object) -> int:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        "SELECT id FROM \"03_iam\".\"01_dim_org_statuses\" WHERE code = 'active'"
    )
    return int(row["id"])


async def _status_id_by_code(conn: object, code: str) -> int:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        "SELECT id FROM \"03_iam\".\"01_dim_org_statuses\" WHERE code = $1",
        code,
    )
    if row is None:
        raise ValueError(f"Unknown org status: {code!r}")
    return int(row["id"])


async def list_orgs(
    conn: object,
    *,
    limit: int = 50,
    offset: int = 0,
    is_active: bool | None = None,
) -> tuple[list[dict], int]:
    """Return (page, total) from v_orgs."""
    where = ""
    params: list = [limit, offset]
    if is_active is not None:
        params.append(is_active)
        where = f"WHERE is_active = ${len(params)}"

    rows = await conn.fetch(  # type: ignore[union-attr]
        f"""
        SELECT id, name, slug, description, status,
               is_active, created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_orgs
          {where}
         ORDER BY created_at DESC
         LIMIT $1 OFFSET $2
        """,
        *params,
    )
    # COUNT query is independent of LIMIT/OFFSET — use filter-only params re-numbered from $1
    filter_params = params[2:]
    count_where = f"WHERE is_active = $1" if filter_params else ""
    total = await conn.fetchval(  # type: ignore[union-attr]
        f'SELECT COUNT(*) FROM "03_iam".v_orgs {count_where}',
        *filter_params,
    )
    return [dict(r) for r in rows], int(total)


async def get_org(conn: object, org_id: str) -> dict | None:
    """Return a single org from v_orgs or None."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, name, slug, description, status,
               is_active, created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_orgs
         WHERE id = $1
        """,
        org_id,
    )
    return dict(row) if row else None


async def create_org(
    conn: object,
    *,
    org_id: str,
    name: str,
    slug: str,
    description: str | None,
    owner_id: str,
    actor_id: str,
) -> None:
    """Insert org fact row + EAV attrs."""
    status_id = await _active_status_id(conn)
    attrs = await _iam_ids.iam_attr_ids(conn, "iam_org")
    entity_type_id = await _iam_ids.iam_entity_type_id(conn, "iam_org")

    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."10_fct_orgs"
            (id, status_id, created_by, updated_by, created_at, updated_at)
        VALUES ($1, $2, $3, $3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        org_id,
        status_id,
        actor_id,
    )

    eav_entries = [("name", name), ("slug", slug)]
    if description:
        eav_entries.append(("description", description))

    for attr_code, value in eav_entries:
        await conn.execute(  # type: ignore[union-attr]
            """
            INSERT INTO "03_iam"."20_dtl_attrs"
                (id, entity_type_id, entity_id, attr_def_id,
                 key_text, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            _id_mod.uuid7(),
            entity_type_id,
            org_id,
            attrs[attr_code],
            value,
        )


async def update_org(
    conn: object,
    org_id: str,
    *,
    name: str | None = None,
    slug: str | None = None,
    description: str | None = None,
    status_code: str | None = None,
    actor_id: str,
) -> None:
    """Update org EAV attrs and optionally status_id."""
    if status_code is not None:
        status_id = await _status_id_by_code(conn, status_code)
        is_active = status_code == "active"
        await conn.execute(  # type: ignore[union-attr]
            """
            UPDATE "03_iam"."10_fct_orgs"
               SET status_id  = $2,
                   is_active  = $3,
                   updated_by = $4,
                   updated_at = CURRENT_TIMESTAMP
             WHERE id = $1
            """,
            org_id,
            status_id,
            is_active,
            actor_id,
        )
    else:
        await conn.execute(  # type: ignore[union-attr]
            """
            UPDATE "03_iam"."10_fct_orgs"
               SET updated_by = $2,
                   updated_at = CURRENT_TIMESTAMP
             WHERE id = $1
            """,
            org_id,
            actor_id,
        )

    attrs = await _iam_ids.iam_attr_ids(conn, "iam_org")
    entity_type_id = await _iam_ids.iam_entity_type_id(conn, "iam_org")

    for attr_code, value in [("name", name), ("slug", slug), ("description", description)]:
        if value is not None:
            await conn.execute(  # type: ignore[union-attr]
                """
                INSERT INTO "03_iam"."20_dtl_attrs"
                    (id, entity_type_id, entity_id, attr_def_id,
                     key_text, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (entity_id, attr_def_id)
                DO UPDATE SET key_text   = EXCLUDED.key_text,
                              updated_at = CURRENT_TIMESTAMP
                """,
                _id_mod.uuid7(),
                entity_type_id,
                org_id,
                attrs[attr_code],
                value,
            )
