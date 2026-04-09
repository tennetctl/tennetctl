"""IAM feature flags repository — raw SQL.

Reads query v_feature_flags. Writes go to raw fct/lnk tables.
No business logic here — one function per query.
"""

from __future__ import annotations

import importlib

_iam_ids = importlib.import_module("04_backend.02_features.iam._iam_attr_ids")
_id_mod = importlib.import_module("scripts.00_core._id")

_FLAG_ENTITY_CODE = "platform_feature_flag"


# ---------------------------------------------------------------------------
# Flag reads
# ---------------------------------------------------------------------------

async def list_flags(
    conn: object,
    *,
    limit: int = 50,
    offset: int = 0,
    product_id: str | None = None,
    scope_id: int | None = None,
    category_id: int | None = None,
    status: str | None = None,
    flag_type: str | None = None,
    include_deleted: bool = False,
) -> tuple[list[dict], int]:
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
    if status is not None:
        params.append(status)
        conditions.append(f"status = ${len(params)}")
    if flag_type is not None:
        params.append(flag_type)
        conditions.append(f"flag_type = ${len(params)}")
    if not include_deleted:
        conditions.append("is_deleted = FALSE")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = await conn.fetch(  # type: ignore[union-attr]
        f"""
        SELECT id, code, name, product_id, product_name, product_code,
               feature_id, scope_id, scope_code, scope_label,
               category_id, category_code, category_label,
               flag_type, status, default_value,
               is_active, is_test, is_deleted,
               created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_feature_flags
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
    if status is not None:
        count_params.append(status)
        count_conditions.append(f"status = ${len(count_params)}")
    if flag_type is not None:
        count_params.append(flag_type)
        count_conditions.append(f"flag_type = ${len(count_params)}")
    if not include_deleted:
        count_conditions.append("is_deleted = FALSE")
    count_where = ("WHERE " + " AND ".join(count_conditions)) if count_conditions else ""

    total = await conn.fetchval(  # type: ignore[union-attr]
        f'SELECT COUNT(*) FROM "03_iam".v_feature_flags {count_where}',
        *count_params,
    )
    return [dict(r) for r in rows], int(total)


async def get_flag(conn: object, flag_id: str) -> dict | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, code, name, product_id, product_name, product_code,
               feature_id, scope_id, scope_code, scope_label,
               category_id, category_code, category_label,
               flag_type, status, default_value,
               is_active, is_test, is_deleted,
               created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_feature_flags
         WHERE id = $1
        """,
        flag_id,
    )
    return dict(row) if row else None


async def get_flag_by_code(conn: object, code: str) -> dict | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, code, name, product_id, product_name, product_code,
               feature_id, scope_id, scope_code, scope_label,
               category_id, category_code, category_label,
               flag_type, status, default_value,
               is_active, is_test, is_deleted,
               created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_feature_flags
         WHERE code = $1
        """,
        code,
    )
    return dict(row) if row else None


async def check_code_exists(conn: object, code: str) -> bool:
    count = await conn.fetchval(  # type: ignore[union-attr]
        """
        SELECT COUNT(*) FROM "03_iam"."10_fct_feature_flags"
         WHERE code = $1 AND deleted_at IS NULL
        """,
        code,
    )
    return int(count) > 0


async def list_flags_by_product(
    conn: object,
    product_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    return await list_flags(
        conn,
        limit=limit,
        offset=offset,
        product_id=product_id,
    )


# ---------------------------------------------------------------------------
# Flag writes
# ---------------------------------------------------------------------------

async def insert_flag(
    conn: object,
    *,
    flag_id: str,
    code: str,
    name: str,
    product_id: str,
    feature_id: str | None,
    scope_id: int,
    category_id: int,
    flag_type: str,
    status: str,
    default_value: object | None,
    actor_id: str,
) -> None:
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."10_fct_feature_flags"
            (id, code, name, product_id, feature_id, scope_id, category_id,
             flag_type, status, default_value,
             created_by, updated_by, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $11,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        flag_id,
        code,
        name,
        product_id,
        feature_id,
        scope_id,
        category_id,
        flag_type,
        status,
        default_value,
        actor_id,
    )


async def update_flag_meta(
    conn: object,
    flag_id: str,
    *,
    actor_id: str,
    name: str | None = None,
    status: str | None = None,
    flag_type: str | None = None,
    default_value: object | None = None,
    is_active: bool | None = None,
) -> None:
    sets = ["updated_by = $2", "updated_at = CURRENT_TIMESTAMP"]
    params: list = [flag_id, actor_id]

    if name is not None:
        params.append(name)
        sets.append(f"name = ${len(params)}")
    if status is not None:
        params.append(status)
        sets.append(f"status = ${len(params)}")
    if flag_type is not None:
        params.append(flag_type)
        sets.append(f"flag_type = ${len(params)}")
    if default_value is not None:
        params.append(default_value)
        sets.append(f"default_value = ${len(params)}")
    if is_active is not None:
        params.append(is_active)
        sets.append(f"is_active = ${len(params)}")

    await conn.execute(  # type: ignore[union-attr]
        f"""
        UPDATE "03_iam"."10_fct_feature_flags"
           SET {", ".join(sets)}
         WHERE id = $1
        """,
        *params,
    )


async def soft_delete_flag(conn: object, flag_id: str, *, actor_id: str) -> None:
    await conn.execute(  # type: ignore[union-attr]
        """
        UPDATE "03_iam"."10_fct_feature_flags"
           SET deleted_at = CURRENT_TIMESTAMP,
               is_active  = FALSE,
               updated_by = $2,
               updated_at = CURRENT_TIMESTAMP
         WHERE id = $1
        """,
        flag_id,
        actor_id,
    )


async def upsert_flag_attr(
    conn: object,
    *,
    id: str,
    entity_type_id: int,
    entity_id: str,
    attr_def_id: int,
    value: str,
) -> None:
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


# ---------------------------------------------------------------------------
# Environment overrides
# ---------------------------------------------------------------------------

async def list_flag_environments(conn: object, flag_id: str) -> list[dict]:
    rows = await conn.fetch(  # type: ignore[union-attr]
        """
        SELECT lfe.id, lfe.flag_id, lfe.environment_id,
               de.code AS environment_code, de.label AS environment_label,
               lfe.enabled, lfe.value, lfe.created_at
          FROM "03_iam"."40_lnk_flag_environments" lfe
          JOIN "03_iam"."06_dim_environments" de ON de.id = lfe.environment_id
         WHERE lfe.flag_id = $1
         ORDER BY lfe.environment_id
        """,
        flag_id,
    )
    return [dict(r) for r in rows]


async def get_flag_environment(
    conn: object, flag_id: str, environment_id: int
) -> dict | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT lfe.id, lfe.flag_id, lfe.environment_id,
               de.code AS environment_code, de.label AS environment_label,
               lfe.enabled, lfe.value, lfe.created_at
          FROM "03_iam"."40_lnk_flag_environments" lfe
          JOIN "03_iam"."06_dim_environments" de ON de.id = lfe.environment_id
         WHERE lfe.flag_id = $1 AND lfe.environment_id = $2
        """,
        flag_id,
        environment_id,
    )
    return dict(row) if row else None


async def get_flag_environment_by_code(
    conn: object, flag_id: str, env_code: str
) -> dict | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT lfe.id, lfe.flag_id, lfe.environment_id,
               de.code AS environment_code, de.label AS environment_label,
               lfe.enabled, lfe.value, lfe.created_at
          FROM "03_iam"."40_lnk_flag_environments" lfe
          JOIN "03_iam"."06_dim_environments" de ON de.id = lfe.environment_id
         WHERE lfe.flag_id = $1 AND de.code = $2
        """,
        flag_id,
        env_code,
    )
    return dict(row) if row else None


async def get_environment_id_by_code(conn: object, env_code: str) -> int | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        'SELECT id FROM "03_iam"."06_dim_environments" WHERE code = $1',
        env_code,
    )
    return int(row["id"]) if row else None


async def upsert_flag_environment(
    conn: object,
    *,
    id: str,
    flag_id: str,
    environment_id: int,
    enabled: bool,
    value: object | None,
) -> dict:
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."40_lnk_flag_environments"
            (id, flag_id, environment_id, enabled, value, created_at)
        VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
        ON CONFLICT (flag_id, environment_id)
        DO UPDATE SET enabled = EXCLUDED.enabled,
                      value   = EXCLUDED.value
        """,
        id,
        flag_id,
        environment_id,
        enabled,
        value,
    )
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT lfe.id, lfe.flag_id, lfe.environment_id,
               de.code AS environment_code, de.label AS environment_label,
               lfe.enabled, lfe.value, lfe.created_at
          FROM "03_iam"."40_lnk_flag_environments" lfe
          JOIN "03_iam"."06_dim_environments" de ON de.id = lfe.environment_id
         WHERE lfe.flag_id = $1 AND lfe.environment_id = $2
        """,
        flag_id,
        environment_id,
    )
    return dict(row)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

async def list_targets(conn: object, flag_id: str, scope_code: str) -> list[dict]:
    """List targets for a flag based on its scope."""
    if scope_code == "platform":
        rows = await conn.fetch(  # type: ignore[union-attr]
            """
            SELECT id, flag_id, value, created_at
              FROM "03_iam"."40_lnk_flag_platform_targets"
             WHERE flag_id = $1
             ORDER BY created_at
            """,
            flag_id,
        )
    elif scope_code == "org":
        rows = await conn.fetch(  # type: ignore[union-attr]
            """
            SELECT id, flag_id, org_id, value, created_at
              FROM "03_iam"."40_lnk_flag_org_targets"
             WHERE flag_id = $1
             ORDER BY created_at
            """,
            flag_id,
        )
    else:  # workspace
        rows = await conn.fetch(  # type: ignore[union-attr]
            """
            SELECT id, flag_id, workspace_id, value, created_at
              FROM "03_iam"."40_lnk_flag_workspace_targets"
             WHERE flag_id = $1
             ORDER BY created_at
            """,
            flag_id,
        )
    return [dict(r) for r in rows]


async def insert_platform_target(
    conn: object,
    *,
    id: str,
    flag_id: str,
    value: object | None,
) -> dict:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."40_lnk_flag_platform_targets"
            (id, flag_id, value, created_at)
        VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
        RETURNING id, flag_id, value, created_at
        """,
        id,
        flag_id,
        value,
    )
    return dict(row)  # type: ignore[arg-type]


async def insert_org_target(
    conn: object,
    *,
    id: str,
    flag_id: str,
    org_id: str,
    value: object | None,
) -> dict:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."40_lnk_flag_org_targets"
            (id, flag_id, org_id, value, created_at)
        VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
        ON CONFLICT (flag_id, org_id) DO UPDATE
            SET value = EXCLUDED.value
        RETURNING id, flag_id, org_id, value, created_at
        """,
        id,
        flag_id,
        org_id,
        value,
    )
    return dict(row)  # type: ignore[arg-type]


async def insert_workspace_target(
    conn: object,
    *,
    id: str,
    flag_id: str,
    workspace_id: str,
    value: object | None,
) -> dict:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."40_lnk_flag_workspace_targets"
            (id, flag_id, workspace_id, value, created_at)
        VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
        ON CONFLICT (flag_id, workspace_id) DO UPDATE
            SET value = EXCLUDED.value
        RETURNING id, flag_id, workspace_id, value, created_at
        """,
        id,
        flag_id,
        workspace_id,
        value,
    )
    return dict(row)  # type: ignore[arg-type]


async def delete_target(conn: object, target_id: str, scope_code: str) -> bool:
    """Delete a target by ID from the correct scope table. Returns True if deleted."""
    if scope_code == "platform":
        result = await conn.execute(  # type: ignore[union-attr]
            'DELETE FROM "03_iam"."40_lnk_flag_platform_targets" WHERE id = $1',
            target_id,
        )
    elif scope_code == "org":
        result = await conn.execute(  # type: ignore[union-attr]
            'DELETE FROM "03_iam"."40_lnk_flag_org_targets" WHERE id = $1',
            target_id,
        )
    else:
        result = await conn.execute(  # type: ignore[union-attr]
            'DELETE FROM "03_iam"."40_lnk_flag_workspace_targets" WHERE id = $1',
            target_id,
        )
    return result != "DELETE 0"


# ---------------------------------------------------------------------------
# Eval helpers
# ---------------------------------------------------------------------------

async def get_org_target_for_flag(
    conn: object, flag_id: str, org_id: str
) -> dict | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, flag_id, org_id, value, created_at
          FROM "03_iam"."40_lnk_flag_org_targets"
         WHERE flag_id = $1 AND org_id = $2
        """,
        flag_id,
        org_id,
    )
    return dict(row) if row else None


async def get_workspace_target_for_flag(
    conn: object, flag_id: str, workspace_id: str
) -> dict | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, flag_id, workspace_id, value, created_at
          FROM "03_iam"."40_lnk_flag_workspace_targets"
         WHERE flag_id = $1 AND workspace_id = $2
        """,
        flag_id,
        workspace_id,
    )
    return dict(row) if row else None


async def list_active_flags_for_bootstrap(
    conn: object,
    *,
    scope_id: int | None = None,
) -> list[dict]:
    """Return all active non-deleted flags (optionally filtered by scope)."""
    conditions = ["is_deleted = FALSE", "is_active = TRUE", "status = 'active'"]
    params: list = []

    if scope_id is not None:
        params.append(scope_id)
        conditions.append(f"scope_id = ${len(params)}")

    where = "WHERE " + " AND ".join(conditions)

    rows = await conn.fetch(  # type: ignore[union-attr]
        f"""
        SELECT id, code, name, product_id, product_name, product_code,
               feature_id, scope_id, scope_code, scope_label,
               category_id, category_code, category_label,
               flag_type, status, default_value,
               is_active, is_test, is_deleted,
               created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_feature_flags
          {where}
         ORDER BY code
        """,
        *params,
    )
    return [dict(r) for r in rows]
