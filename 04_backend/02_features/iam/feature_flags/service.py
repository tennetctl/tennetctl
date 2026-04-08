"""IAM feature flags service — CRUD, env overrides, targeting, eval."""

from __future__ import annotations

import importlib

_repo = importlib.import_module("04_backend.02_features.iam.feature_flags.repository")
_id_mod = importlib.import_module("scripts.00_core._id")
_errors_mod = importlib.import_module("04_backend.01_core.errors")
_audit = importlib.import_module("04_backend.02_features.audit.service")
_iam_ids = importlib.import_module("04_backend.02_features.iam._iam_attr_ids")

AppError = _errors_mod.AppError

_FLAG_ENTITY_CODE = "platform_feature_flag"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _check_product_exists(conn: object, product_id: str) -> None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        'SELECT id FROM "03_iam"."10_fct_products" WHERE id = $1 AND deleted_at IS NULL',
        product_id,
    )
    if row is None:
        raise AppError("PRODUCT_NOT_FOUND", f"Product '{product_id}' not found.", 404)


async def _check_scope_exists(conn: object, scope_id: int) -> None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        'SELECT id FROM "03_iam"."06_dim_scopes" WHERE id = $1',
        scope_id,
    )
    if row is None:
        raise AppError("INVALID_SCOPE", f"Scope id {scope_id} does not exist.", 422)


async def _check_category_is_flag(conn: object, category_id: int) -> None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        "SELECT id FROM \"03_iam\".\"06_dim_categories\" WHERE id = $1 AND category_type = 'flag'",
        category_id,
    )
    if row is None:
        raise AppError(
            "INVALID_CATEGORY",
            f"Category {category_id} does not exist or is not of type 'flag'.",
            422,
        )


async def _write_flag_attrs(
    conn: object,
    flag_id: str,
    attrs: dict,
    entity_type_id: int,
    *,
    description: str | None = None,
    owner_user_id: str | None = None,
    jira_ticket: str | None = None,
    rollout_percentage: str | None = None,
    launch_date: str | None = None,
    sunset_date: str | None = None,
) -> None:
    for attr_code, value in [
        ("description", description),
        ("owner_user_id", owner_user_id),
        ("jira_ticket", jira_ticket),
        ("rollout_percentage", rollout_percentage),
        ("launch_date", launch_date),
        ("sunset_date", sunset_date),
    ]:
        if value is not None:
            await _repo.upsert_flag_attr(
                conn,
                id=_id_mod.uuid7(),
                entity_type_id=entity_type_id,
                entity_id=flag_id,
                attr_def_id=attrs[attr_code],
                value=value,
            )


# ---------------------------------------------------------------------------
# CRUD
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
) -> dict:
    items, total = await _repo.list_flags(
        conn,
        limit=limit,
        offset=offset,
        product_id=product_id,
        scope_id=scope_id,
        category_id=category_id,
        status=status,
        flag_type=flag_type,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


async def get_flag(conn: object, flag_id: str) -> dict:
    flag = await _repo.get_flag(conn, flag_id)
    if flag is None:
        raise AppError("FLAG_NOT_FOUND", f"Feature flag '{flag_id}' not found.", 404)
    return flag


async def create_flag(
    conn: object,
    *,
    code: str,
    name: str,
    product_id: str,
    feature_id: str | None,
    scope_id: int,
    category_id: int,
    flag_type: str,
    status: str = "draft",
    default_value: object | None = None,
    description: str | None = None,
    owner_user_id: str | None = None,
    jira_ticket: str | None = None,
    rollout_percentage: str | None = None,
    launch_date: str | None = None,
    sunset_date: str | None = None,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    await _check_product_exists(conn, product_id)
    await _check_scope_exists(conn, scope_id)
    await _check_category_is_flag(conn, category_id)

    code_taken = await _repo.check_code_exists(conn, code)
    if code_taken:
        raise AppError(
            "FLAG_CODE_CONFLICT",
            f"A feature flag with code '{code}' already exists.",
            409,
        )

    flag_id = _id_mod.uuid7()
    attrs = await _iam_ids.iam_attr_ids(conn, _FLAG_ENTITY_CODE)
    entity_type_id = await _iam_ids.iam_entity_type_id(conn, _FLAG_ENTITY_CODE)

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.insert_flag(
            conn,
            flag_id=flag_id,
            code=code,
            name=name,
            product_id=product_id,
            feature_id=feature_id,
            scope_id=scope_id,
            category_id=category_id,
            flag_type=flag_type,
            status=status,
            default_value=default_value,
            actor_id=actor_id,
        )
        await _write_flag_attrs(
            conn,
            flag_id,
            attrs,
            entity_type_id,
            description=description,
            owner_user_id=owner_user_id,
            jira_ticket=jira_ticket,
            rollout_percentage=rollout_percentage,
            launch_date=launch_date,
            sunset_date=sunset_date,
        )
        await _audit.emit(
            conn,
            category="iam",
            action="feature_flag.create",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=flag_id,
            target_type="platform_feature_flag",
        )

    flag = await _repo.get_flag(conn, flag_id)
    return flag  # type: ignore[return-value]


async def update_flag(
    conn: object,
    flag_id: str,
    *,
    name: str | None = None,
    status: str | None = None,
    flag_type: str | None = None,
    default_value: object | None = None,
    is_active: bool | None = None,
    description: str | None = None,
    owner_user_id: str | None = None,
    jira_ticket: str | None = None,
    rollout_percentage: str | None = None,
    launch_date: str | None = None,
    sunset_date: str | None = None,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    existing = await _repo.get_flag(conn, flag_id)
    if existing is None:
        raise AppError("FLAG_NOT_FOUND", f"Feature flag '{flag_id}' not found.", 404)

    attrs = await _iam_ids.iam_attr_ids(conn, _FLAG_ENTITY_CODE)
    entity_type_id = await _iam_ids.iam_entity_type_id(conn, _FLAG_ENTITY_CODE)

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.update_flag_meta(
            conn,
            flag_id,
            actor_id=actor_id,
            name=name,
            status=status,
            flag_type=flag_type,
            default_value=default_value,
            is_active=is_active,
        )
        await _write_flag_attrs(
            conn,
            flag_id,
            attrs,
            entity_type_id,
            description=description,
            owner_user_id=owner_user_id,
            jira_ticket=jira_ticket,
            rollout_percentage=rollout_percentage,
            launch_date=launch_date,
            sunset_date=sunset_date,
        )
        await _audit.emit(
            conn,
            category="iam",
            action="feature_flag.update",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=flag_id,
            target_type="platform_feature_flag",
        )

    return await _repo.get_flag(conn, flag_id)  # type: ignore[return-value]


async def delete_flag(
    conn: object,
    flag_id: str,
    *,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> None:
    existing = await _repo.get_flag(conn, flag_id)
    if existing is None:
        raise AppError("FLAG_NOT_FOUND", f"Feature flag '{flag_id}' not found.", 404)

    if existing.get("is_deleted"):
        return  # idempotent

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.soft_delete_flag(conn, flag_id, actor_id=actor_id)
        await _audit.emit(
            conn,
            category="iam",
            action="feature_flag.delete",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=flag_id,
            target_type="platform_feature_flag",
        )


async def list_flags_by_product(
    conn: object,
    product_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    # Verify product exists
    row = await conn.fetchrow(  # type: ignore[union-attr]
        'SELECT id FROM "03_iam"."10_fct_products" WHERE id = $1 AND deleted_at IS NULL',
        product_id,
    )
    if row is None:
        raise AppError("PRODUCT_NOT_FOUND", f"Product '{product_id}' not found.", 404)

    items, total = await _repo.list_flags_by_product(conn, product_id, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


# ---------------------------------------------------------------------------
# Environment overrides
# ---------------------------------------------------------------------------

async def list_environments(conn: object, flag_id: str) -> dict:
    flag = await _repo.get_flag(conn, flag_id)
    if flag is None:
        raise AppError("FLAG_NOT_FOUND", f"Feature flag '{flag_id}' not found.", 404)
    items = await _repo.list_flag_environments(conn, flag_id)
    return {"items": items, "total": len(items)}


async def upsert_environment_override(
    conn: object,
    flag_id: str,
    env_code: str,
    *,
    enabled: bool,
    value: object | None,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    flag = await _repo.get_flag(conn, flag_id)
    if flag is None:
        raise AppError("FLAG_NOT_FOUND", f"Feature flag '{flag_id}' not found.", 404)

    env_id = await _repo.get_environment_id_by_code(conn, env_code)
    if env_id is None:
        raise AppError("ENV_NOT_FOUND", f"Environment '{env_code}' not found.", 404)

    override_id = _id_mod.uuid7()
    result = await _repo.upsert_flag_environment(
        conn,
        id=override_id,
        flag_id=flag_id,
        environment_id=env_id,
        enabled=enabled,
        value=value,
    )
    await _audit.emit(
        conn,
        category="iam",
        action="feature_flag.env_override.set",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=flag_id,
        target_type="platform_feature_flag",
    )
    return result


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

async def list_targets(conn: object, flag_id: str) -> dict:
    flag = await _repo.get_flag(conn, flag_id)
    if flag is None:
        raise AppError("FLAG_NOT_FOUND", f"Feature flag '{flag_id}' not found.", 404)
    scope_code = flag["scope_code"]
    items = await _repo.list_targets(conn, flag_id, scope_code)
    return {"items": items, "total": len(items), "scope": scope_code}


async def create_target(
    conn: object,
    flag_id: str,
    *,
    org_id: str | None,
    workspace_id: str | None,
    value: object | None,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    flag = await _repo.get_flag(conn, flag_id)
    if flag is None:
        raise AppError("FLAG_NOT_FOUND", f"Feature flag '{flag_id}' not found.", 404)

    scope_code = flag["scope_code"]
    target_id = _id_mod.uuid7()

    if scope_code == "platform":
        result = await _repo.insert_platform_target(
            conn, id=target_id, flag_id=flag_id, value=value
        )
    elif scope_code == "org":
        if not org_id:
            raise AppError(
                "MISSING_ORG_ID",
                "org_id is required for org-scoped flags.",
                422,
            )
        result = await _repo.insert_org_target(
            conn, id=target_id, flag_id=flag_id, org_id=org_id, value=value
        )
    else:  # workspace
        if not workspace_id:
            raise AppError(
                "MISSING_WORKSPACE_ID",
                "workspace_id is required for workspace-scoped flags.",
                422,
            )
        result = await _repo.insert_workspace_target(
            conn, id=target_id, flag_id=flag_id, workspace_id=workspace_id, value=value
        )

    await _audit.emit(
        conn,
        category="iam",
        action="feature_flag.target.add",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=flag_id,
        target_type="platform_feature_flag",
    )
    return result


async def delete_target(
    conn: object,
    flag_id: str,
    target_id: str,
    *,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> None:
    flag = await _repo.get_flag(conn, flag_id)
    if flag is None:
        raise AppError("FLAG_NOT_FOUND", f"Feature flag '{flag_id}' not found.", 404)

    scope_code = flag["scope_code"]
    deleted = await _repo.delete_target(conn, target_id, scope_code)
    if not deleted:
        raise AppError("TARGET_NOT_FOUND", f"Target '{target_id}' not found.", 404)

    await _audit.emit(
        conn,
        category="iam",
        action="feature_flag.target.remove",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=flag_id,
        target_type="platform_feature_flag",
    )


# ---------------------------------------------------------------------------
# Eval
# ---------------------------------------------------------------------------

async def eval_flag(
    conn: object,
    *,
    flag_code: str,
    user_id: str | None = None,
    org_id: str | None = None,
    workspace_id: str | None = None,
    environment: str | None = None,
) -> dict:
    """Evaluate a feature flag for a given context.

    Resolution order:
    1. Flag not found → error
    2. Flag inactive or archived → return default_value
    3. Environment override found → use it
    4. Targeting rule found (scope-aware) → return target value
    5. Return default_value
    """
    flag = await _repo.get_flag_by_code(conn, flag_code)
    if flag is None:
        raise AppError("FLAG_NOT_FOUND", f"Feature flag '{flag_code}' not found.", 404)

    flag_id = flag["id"]
    default_value = flag["default_value"]

    # Step 2: inactive or archived
    if not flag["is_active"] or flag["status"] == "archived":
        return {
            "flag_code": flag_code,
            "value": default_value,
            "reason": "flag_inactive",
        }

    # Step 3: environment override
    if environment:
        env_override = await _repo.get_flag_environment_by_code(conn, flag_id, environment)
        if env_override is not None:
            if not env_override["enabled"]:
                return {
                    "flag_code": flag_code,
                    "value": default_value,
                    "reason": "env_disabled",
                }
            if env_override["value"] is not None:
                return {
                    "flag_code": flag_code,
                    "value": env_override["value"],
                    "reason": "env_override",
                }

    # Step 4: targeting
    scope_code = flag["scope_code"]
    if scope_code == "org" and org_id:
        target = await _repo.get_org_target_for_flag(conn, flag_id, org_id)
        if target is not None:
            return {
                "flag_code": flag_code,
                "value": target["value"] if target["value"] is not None else default_value,
                "reason": "org_target",
            }
    elif scope_code == "workspace" and workspace_id:
        target = await _repo.get_workspace_target_for_flag(conn, flag_id, workspace_id)
        if target is not None:
            return {
                "flag_code": flag_code,
                "value": target["value"] if target["value"] is not None else default_value,
                "reason": "workspace_target",
            }

    # Step 5: default
    return {
        "flag_code": flag_code,
        "value": default_value,
        "reason": "default",
    }


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

async def bootstrap_flags(
    conn: object,
    *,
    environment: str | None = None,
    workspace_id: str | None = None,
) -> dict:
    """Return all active flags, with environment overrides applied where applicable."""
    flags = await _repo.list_active_flags_for_bootstrap(conn)

    results = []
    for flag in flags:
        flag_id = flag["id"]
        value = flag["default_value"]
        reason = "default"

        # Apply env override if requested
        if environment:
            env_override = await _repo.get_flag_environment_by_code(conn, flag_id, environment)
            if env_override is not None and env_override["enabled"]:
                if env_override["value"] is not None:
                    value = env_override["value"]
                    reason = "env_override"

        # Apply workspace targeting if provided
        if workspace_id and flag["scope_code"] == "workspace":
            target = await _repo.get_workspace_target_for_flag(conn, flag_id, workspace_id)
            if target is not None:
                value = target["value"] if target["value"] is not None else value
                reason = "workspace_target"

        results.append({
            "flag_code": flag["code"],
            "flag_id": flag["id"],
            "flag_type": flag["flag_type"],
            "scope": flag["scope_code"],
            "value": value,
            "reason": reason,
        })

    return {"flags": results, "total": len(results)}
