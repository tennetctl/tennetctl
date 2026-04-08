"""IAM workspaces repository — reads v_workspaces, writes 10_fct_workspaces + 20_dtl_attrs."""

from __future__ import annotations

import importlib

_iam_ids = importlib.import_module("04_backend.02_features.iam._iam_attr_ids")
_id_mod = importlib.import_module("scripts.00_core._id")


async def _active_status_id(conn: object) -> int:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        "SELECT id FROM \"03_iam\".\"02_dim_workspace_statuses\" WHERE code = 'active'"
    )
    return int(row["id"])


async def _status_id_by_code(conn: object, code: str) -> int:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        "SELECT id FROM \"03_iam\".\"02_dim_workspace_statuses\" WHERE code = $1",
        code,
    )
    if row is None:
        raise ValueError(f"Unknown workspace status: {code!r}")
    return int(row["id"])


async def list_workspaces(
    conn: object,
    *,
    limit: int = 50,
    offset: int = 0,
    org_id: str | None = None,
    is_active: bool | None = None,
) -> tuple[list[dict], int]:
    """Return (page, total) from v_workspaces."""
    conditions = []
    params: list = [limit, offset]

    if org_id is not None:
        params.append(org_id)
        conditions.append(f"org_id = ${len(params)}")
    if is_active is not None:
        params.append(is_active)
        conditions.append(f"is_active = ${len(params)}")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = await conn.fetch(  # type: ignore[union-attr]
        f"""
        SELECT id, org_id, name, slug, status,
               is_active, created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_workspaces
          {where}
         ORDER BY created_at DESC
         LIMIT $1 OFFSET $2
        """,
        *params,
    )
    # COUNT query is independent of LIMIT/OFFSET — re-number filter params from $1
    filter_params = params[2:]
    count_conditions = []
    if org_id is not None:
        count_conditions.append(f"org_id = ${len(count_conditions) + 1}")
    if is_active is not None:
        count_conditions.append(f"is_active = ${len(count_conditions) + 1}")
    count_where = ("WHERE " + " AND ".join(count_conditions)) if count_conditions else ""
    total = await conn.fetchval(  # type: ignore[union-attr]
        f'SELECT COUNT(*) FROM "03_iam".v_workspaces {count_where}',
        *filter_params,
    )
    return [dict(r) for r in rows], int(total)


async def slug_exists_in_org(conn: object, org_id: str, slug: str, *, exclude_id: str | None = None) -> bool:
    """Return True if a workspace with this slug already exists in the org."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT w.id
          FROM "03_iam"."10_fct_workspaces" w
          JOIN "03_iam"."20_dtl_attrs" s
                 ON s.entity_id   = w.id
                AND s.attr_def_id = (
                    SELECT d.id
                      FROM "03_iam"."07_dim_attr_defs" d
                      JOIN "03_iam"."06_dim_entity_types" et ON d.entity_type_id = et.id
                     WHERE et.code = 'iam_workspace' AND d.code = 'slug'
                )
         WHERE w.org_id = $1
           AND s.key_text = $2
           AND w.is_active = TRUE
           AND ($3::varchar IS NULL OR w.id != $3)
        """,
        org_id,
        slug,
        exclude_id,
    )
    return row is not None


async def get_workspace(conn: object, workspace_id: str) -> dict | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, org_id, name, slug, status,
               is_active, created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_workspaces
         WHERE id = $1
        """,
        workspace_id,
    )
    return dict(row) if row else None


async def create_workspace(
    conn: object,
    *,
    workspace_id: str,
    org_id: str,
    name: str,
    slug: str,
    actor_id: str,
) -> None:
    status_id = await _active_status_id(conn)
    attrs = await _iam_ids.iam_attr_ids(conn, "iam_workspace")
    entity_type_id = await _iam_ids.iam_entity_type_id(conn, "iam_workspace")

    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."10_fct_workspaces"
            (id, org_id, status_id, created_by, updated_by, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $4, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        workspace_id,
        org_id,
        status_id,
        actor_id,
    )

    for attr_code, value in [("name", name), ("slug", slug)]:
        await conn.execute(  # type: ignore[union-attr]
            """
            INSERT INTO "03_iam"."20_dtl_attrs"
                (id, entity_type_id, entity_id, attr_def_id,
                 key_text, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            _id_mod.uuid7(),
            entity_type_id,
            workspace_id,
            attrs[attr_code],
            value,
        )


async def update_workspace(
    conn: object,
    workspace_id: str,
    *,
    name: str | None = None,
    slug: str | None = None,
    status_code: str | None = None,
    actor_id: str,
) -> None:
    if status_code is not None:
        status_id = await _status_id_by_code(conn, status_code)
        is_active = status_code == "active"
        await conn.execute(  # type: ignore[union-attr]
            """
            UPDATE "03_iam"."10_fct_workspaces"
               SET status_id  = $2,
                   is_active  = $3,
                   updated_by = $4,
                   updated_at = CURRENT_TIMESTAMP
             WHERE id = $1
            """,
            workspace_id,
            status_id,
            is_active,
            actor_id,
        )
    else:
        await conn.execute(  # type: ignore[union-attr]
            """
            UPDATE "03_iam"."10_fct_workspaces"
               SET updated_by = $2,
                   updated_at = CURRENT_TIMESTAMP
             WHERE id = $1
            """,
            workspace_id,
            actor_id,
        )

    attrs = await _iam_ids.iam_attr_ids(conn, "iam_workspace")
    entity_type_id = await _iam_ids.iam_entity_type_id(conn, "iam_workspace")

    for attr_code, value in [("name", name), ("slug", slug)]:
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
                workspace_id,
                attrs[attr_code],
                value,
            )


async def delete_workspace(conn: object, workspace_id: str, *, actor_id: str) -> None:
    """Soft-delete workspace (archive — no deleted_at column)."""
    archived_id = await _status_id_by_code(conn, "archived")
    await conn.execute(  # type: ignore[union-attr]
        """
        UPDATE "03_iam"."10_fct_workspaces"
           SET is_active  = FALSE,
               status_id  = $2,
               updated_by = $3,
               updated_at = CURRENT_TIMESTAMP
         WHERE id = $1
        """,
        workspace_id,
        archived_id,
        actor_id,
    )
