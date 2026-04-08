"""IAM products repository — raw SQL for product CRUD + workspace subscriptions.

All attr_def_ids are resolved dynamically from 07_dim_attr_defs by code.
No hardcoded IDENTITY values anywhere in this file.

10_fct_products has code and name as identity columns (exception for catalog
lookup performance). All extended attrs (description, slug, status,
pricing_tier, owner_user_id) live in 20_dtl_attrs.
"""

from __future__ import annotations

import importlib

_iam_ids = importlib.import_module("04_backend.02_features.iam._iam_attr_ids")
_id_mod = importlib.import_module("scripts.00_core._id")


# ---------------------------------------------------------------------------
# Product reads
# ---------------------------------------------------------------------------

async def list_products(
    conn: object,
    *,
    limit: int = 50,
    offset: int = 0,
    category_id: int | None = None,
    is_sellable: bool | None = None,
    include_deleted: bool = False,
) -> tuple[list[dict], int]:
    """Return (page, total) from v_products."""
    conditions: list[str] = []
    params: list = [limit, offset]

    if category_id is not None:
        params.append(category_id)
        conditions.append(f"category_id = ${len(params)}")

    if is_sellable is not None:
        params.append(is_sellable)
        conditions.append(f"is_sellable = ${len(params)}")

    if not include_deleted:
        conditions.append("is_deleted = FALSE")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = await conn.fetch(  # type: ignore[union-attr]
        f"""
        SELECT id, code, name, category_id, category_code, category_label,
               is_sellable, is_active, is_deleted,
               description, slug, status, pricing_tier, owner_user_id,
               created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_products
          {where}
         ORDER BY created_at DESC
         LIMIT $1 OFFSET $2
        """,
        *params,
    )

    count_conditions: list[str] = []
    count_params: list = []
    if category_id is not None:
        count_params.append(category_id)
        count_conditions.append(f"category_id = ${len(count_params)}")
    if is_sellable is not None:
        count_params.append(is_sellable)
        count_conditions.append(f"is_sellable = ${len(count_params)}")
    if not include_deleted:
        count_conditions.append("is_deleted = FALSE")
    count_where = ("WHERE " + " AND ".join(count_conditions)) if count_conditions else ""

    total = await conn.fetchval(  # type: ignore[union-attr]
        f'SELECT COUNT(*) FROM "03_iam".v_products {count_where}',
        *count_params,
    )
    return [dict(r) for r in rows], int(total)


async def get_product(conn: object, product_id: str) -> dict | None:
    """Return a single product from v_products or None."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, code, name, category_id, category_code, category_label,
               is_sellable, is_active, is_deleted,
               description, slug, status, pricing_tier, owner_user_id,
               created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_products
         WHERE id = $1
        """,
        product_id,
    )
    return dict(row) if row else None


async def check_code_exists(conn: object, code: str) -> bool:
    """Check if a product code already exists."""
    count = await conn.fetchval(  # type: ignore[union-attr]
        """
        SELECT COUNT(*) FROM "03_iam"."10_fct_products"
         WHERE code = $1 AND deleted_at IS NULL
        """,
        code,
    )
    return int(count) > 0


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
# Product writes
# ---------------------------------------------------------------------------

async def insert_product(
    conn: object,
    *,
    product_id: str,
    code: str,
    name: str,
    category_id: int,
    is_sellable: bool,
    actor_id: str,
) -> None:
    """Insert the product fact row."""
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."10_fct_products"
            (id, code, name, category_id, is_sellable,
             created_by, updated_by, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $6, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        product_id,
        code,
        name,
        category_id,
        is_sellable,
        actor_id,
    )


async def upsert_product_attr(
    conn: object,
    *,
    id: str,
    entity_type_id: int,
    entity_id: str,
    attr_def_id: int,
    value: str,
) -> None:
    """Upsert one EAV attribute row for a product."""
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


async def update_product_meta(
    conn: object,
    product_id: str,
    *,
    actor_id: str,
    name: str | None = None,
    is_sellable: bool | None = None,
    is_active: bool | None = None,
) -> None:
    """Update fct row columns: name, is_sellable, is_active, updated_by/at."""
    sets = ["updated_by = $2", "updated_at = CURRENT_TIMESTAMP"]
    params: list = [product_id, actor_id]

    if name is not None:
        params.append(name)
        sets.append(f"name = ${len(params)}")

    if is_sellable is not None:
        params.append(is_sellable)
        sets.append(f"is_sellable = ${len(params)}")

    if is_active is not None:
        params.append(is_active)
        sets.append(f"is_active = ${len(params)}")

    await conn.execute(  # type: ignore[union-attr]
        f"""
        UPDATE "03_iam"."10_fct_products"
           SET {", ".join(sets)}
         WHERE id = $1
        """,
        *params,
    )


async def soft_delete_product(conn: object, product_id: str, *, actor_id: str) -> None:
    """Soft-delete a product."""
    await conn.execute(  # type: ignore[union-attr]
        """
        UPDATE "03_iam"."10_fct_products"
           SET deleted_at = CURRENT_TIMESTAMP,
               is_active  = FALSE,
               updated_by = $2,
               updated_at = CURRENT_TIMESTAMP
         WHERE id = $1
        """,
        product_id,
        actor_id,
    )


# ---------------------------------------------------------------------------
# Workspace-product subscription reads
# ---------------------------------------------------------------------------

async def list_workspace_subscriptions(
    conn: object,
    workspace_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Return (page, total) of active product subscriptions for a workspace."""
    rows = await conn.fetch(  # type: ignore[union-attr]
        """
        SELECT id, workspace_id, product_id, subscribed_at, subscribed_by, is_active
          FROM "03_iam"."40_lnk_workspace_products"
         WHERE workspace_id = $3 AND is_active = TRUE
         ORDER BY subscribed_at DESC
         LIMIT $1 OFFSET $2
        """,
        limit,
        offset,
        workspace_id,
    )
    total = await conn.fetchval(  # type: ignore[union-attr]
        """
        SELECT COUNT(*) FROM "03_iam"."40_lnk_workspace_products"
         WHERE workspace_id = $1 AND is_active = TRUE
        """,
        workspace_id,
    )
    return [dict(r) for r in rows], int(total)


async def get_workspace_subscription(
    conn: object, workspace_id: str, product_id: str
) -> dict | None:
    """Return an active subscription row or None."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, workspace_id, product_id, subscribed_at, subscribed_by, is_active
          FROM "03_iam"."40_lnk_workspace_products"
         WHERE workspace_id = $1 AND product_id = $2 AND is_active = TRUE
        """,
        workspace_id,
        product_id,
    )
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Workspace-product subscription writes
# ---------------------------------------------------------------------------

async def insert_workspace_subscription(
    conn: object,
    *,
    sub_id: str,
    workspace_id: str,
    product_id: str,
    actor_id: str,
) -> dict:
    """Insert a workspace-product subscription. Raises on duplicate."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."40_lnk_workspace_products"
            (id, workspace_id, product_id, subscribed_by, is_active, subscribed_at)
        VALUES ($1, $2, $3, $4, TRUE, CURRENT_TIMESTAMP)
        RETURNING id, workspace_id, product_id, subscribed_at, subscribed_by, is_active
        """,
        sub_id,
        workspace_id,
        product_id,
        actor_id,
    )
    return dict(row)  # type: ignore[arg-type]


async def deactivate_workspace_subscription(
    conn: object, workspace_id: str, product_id: str
) -> bool:
    """Deactivate a workspace-product subscription. Returns True if updated."""
    result = await conn.execute(  # type: ignore[union-attr]
        """
        UPDATE "03_iam"."40_lnk_workspace_products"
           SET is_active = FALSE
         WHERE workspace_id = $1 AND product_id = $2 AND is_active = TRUE
        """,
        workspace_id,
        product_id,
    )
    return result != "UPDATE 0"


async def check_workspace_exists(conn: object, workspace_id: str) -> bool:
    """Check if a workspace exists and is active."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id FROM "03_iam"."10_fct_workspaces"
         WHERE id = $1 AND is_active = TRUE
        """,
        workspace_id,
    )
    return row is not None
