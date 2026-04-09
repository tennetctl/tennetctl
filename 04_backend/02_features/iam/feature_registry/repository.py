"""IAM feature registry repository — raw SQL for feature CRUD.

All attr_def_ids are resolved dynamically from 07_dim_attr_defs by code.
No hardcoded IDENTITY values anywhere in this file.

10_fct_features has code and name as identity columns (exception for catalog
lookup performance). All extended attrs (description, status, doc_url,
owner_user_id, version_introduced) live in 20_dtl_attrs.
"""

from __future__ import annotations

import importlib

_iam_ids = importlib.import_module("04_backend.02_features.iam._iam_attr_ids")
_id_mod = importlib.import_module("scripts.00_core._id")


# ---------------------------------------------------------------------------
# Feature reads
# ---------------------------------------------------------------------------

async def list_features(
    conn: object,
    *,
    limit: int = 50,
    offset: int = 0,
    product_id: str | None = None,
    scope_id: int | None = None,
    category_id: int | None = None,
    parent_id: str | None = None,
    include_deleted: bool = False,
) -> tuple[list[dict], int]:
    """Return (page, total) from v_features."""
    conditions: list[str] = []
    params: list = [limit, offset]

    if product_id is not None:
        params.append(product_id)
        conditions.append(f"product_id = ${len(params)}")

    if scope_id is not None:
        params.append(scope_id)
        conditions.append(f"scope_id = ${len(params)}")

    if category_id is not None:
        params.append(category_id)
        conditions.append(f"category_id = ${len(params)}")

    if parent_id is not None:
        params.append(parent_id)
        conditions.append(f"parent_id = ${len(params)}")

    if not include_deleted:
        conditions.append("is_deleted = FALSE")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = await conn.fetch(  # type: ignore[union-attr]
        f"""
        SELECT id, product_id, parent_id, code, name,
               scope_id, scope_code, scope_label,
               category_id, category_code, category_label,
               is_active, is_deleted,
               description, status, doc_url, owner_user_id, version_introduced,
               created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_features
          {where}
         ORDER BY created_at DESC
         LIMIT $1 OFFSET $2
        """,
        *params,
    )

    count_conditions: list[str] = []
    count_params: list = []
    if product_id is not None:
        count_params.append(product_id)
        count_conditions.append(f"product_id = ${len(count_params)}")
    if scope_id is not None:
        count_params.append(scope_id)
        count_conditions.append(f"scope_id = ${len(count_params)}")
    if category_id is not None:
        count_params.append(category_id)
        count_conditions.append(f"category_id = ${len(count_params)}")
    if parent_id is not None:
        count_params.append(parent_id)
        count_conditions.append(f"parent_id = ${len(count_params)}")
    if not include_deleted:
        count_conditions.append("is_deleted = FALSE")
    count_where = ("WHERE " + " AND ".join(count_conditions)) if count_conditions else ""

    total = await conn.fetchval(  # type: ignore[union-attr]
        f'SELECT COUNT(*) FROM "03_iam".v_features {count_where}',
        *count_params,
    )
    return [dict(r) for r in rows], int(total)


async def get_feature(conn: object, feature_id: str) -> dict | None:
    """Return a single feature from v_features or None."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, product_id, parent_id, code, name,
               scope_id, scope_code, scope_label,
               category_id, category_code, category_label,
               is_active, is_deleted,
               description, status, doc_url, owner_user_id, version_introduced,
               created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_features
         WHERE id = $1
        """,
        feature_id,
    )
    return dict(row) if row else None


async def list_children(
    conn: object,
    parent_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Return (page, total) of direct children of a feature."""
    return await list_features(
        conn,
        limit=limit,
        offset=offset,
        parent_id=parent_id,
    )


async def check_code_exists(conn: object, product_id: str, code: str) -> bool:
    """Check if feature code already exists within a product."""
    count = await conn.fetchval(  # type: ignore[union-attr]
        """
        SELECT COUNT(*) FROM "03_iam"."10_fct_features"
         WHERE product_id = $1 AND code = $2 AND deleted_at IS NULL
        """,
        product_id,
        code,
    )
    return int(count) > 0


async def check_product_exists(conn: object, product_id: str) -> bool:
    """Check if a product exists and is not deleted."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id FROM "03_iam"."10_fct_products"
         WHERE id = $1 AND deleted_at IS NULL
        """,
        product_id,
    )
    return row is not None


async def check_scope_exists(conn: object, scope_id: int) -> bool:
    """Check if a scope_id exists."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        "SELECT id FROM \"03_iam\".\"06_dim_scopes\" WHERE id = $1",
        scope_id,
    )
    return row is not None


async def check_category_type(conn: object, category_id: int, expected_type: str) -> bool:
    """Check that the category_id belongs to the expected category_type."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id FROM "03_iam"."06_dim_categories"
         WHERE id = $1 AND category_type = $2
        """,
        category_id,
        expected_type,
    )
    return row is not None


# ---------------------------------------------------------------------------
# Feature writes
# ---------------------------------------------------------------------------

async def insert_feature(
    conn: object,
    *,
    feature_id: str,
    product_id: str,
    parent_id: str | None,
    code: str,
    name: str,
    scope_id: int,
    category_id: int,
    actor_id: str,
) -> None:
    """Insert the feature fact row."""
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."10_fct_features"
            (id, product_id, parent_id, code, name, scope_id, category_id,
             created_by, updated_by, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $8, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        feature_id,
        product_id,
        parent_id,
        code,
        name,
        scope_id,
        category_id,
        actor_id,
    )


async def upsert_feature_attr(
    conn: object,
    *,
    id: str,
    entity_type_id: int,
    entity_id: str,
    attr_def_id: int,
    value: str,
) -> None:
    """Upsert one EAV attribute row for a feature."""
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
        id,
        entity_type_id,
        entity_id,
        attr_def_id,
        value,
    )


async def update_feature_meta(
    conn: object,
    feature_id: str,
    *,
    actor_id: str,
    name: str | None = None,
    scope_id: int | None = None,
    category_id: int | None = None,
    is_active: bool | None = None,
) -> None:
    """Update fct row columns: name, scope_id, category_id, is_active, updated_by/at."""
    sets = ["updated_by = $2", "updated_at = CURRENT_TIMESTAMP"]
    params: list = [feature_id, actor_id]

    if name is not None:
        params.append(name)
        sets.append(f"name = ${len(params)}")

    if scope_id is not None:
        params.append(scope_id)
        sets.append(f"scope_id = ${len(params)}")

    if category_id is not None:
        params.append(category_id)
        sets.append(f"category_id = ${len(params)}")

    if is_active is not None:
        params.append(is_active)
        sets.append(f"is_active = ${len(params)}")

    await conn.execute(  # type: ignore[union-attr]
        f"""
        UPDATE "03_iam"."10_fct_features"
           SET {", ".join(sets)}
         WHERE id = $1
        """,
        *params,
    )


async def soft_delete_feature(conn: object, feature_id: str, *, actor_id: str) -> None:
    """Soft-delete a feature."""
    await conn.execute(  # type: ignore[union-attr]
        """
        UPDATE "03_iam"."10_fct_features"
           SET deleted_at = CURRENT_TIMESTAMP,
               is_active  = FALSE,
               updated_by = $2,
               updated_at = CURRENT_TIMESTAMP
         WHERE id = $1
        """,
        feature_id,
        actor_id,
    )
