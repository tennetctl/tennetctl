"""IAM products service — CRUD with audit events + workspace subscriptions."""

from __future__ import annotations

import importlib

_repo = importlib.import_module("04_backend.02_features.iam.products.repository")
_id_mod = importlib.import_module("scripts.00_core._id")
_errors_mod = importlib.import_module("04_backend.01_core.errors")
_audit = importlib.import_module("04_backend.02_features.audit.service")
_iam_ids = importlib.import_module("04_backend.02_features.iam._iam_attr_ids")

AppError = _errors_mod.AppError

_PRODUCT_ENTITY_CODE = "platform_product"


async def _write_product_attrs(
    conn: object,
    product_id: str,
    attrs: dict,
    entity_type_id: int,
    *,
    description: str | None = None,
    slug: str | None = None,
    status: str | None = None,
    pricing_tier: str | None = None,
    owner_user_id: str | None = None,
) -> None:
    """Write EAV attrs for a product. Only writes non-None values."""
    for attr_code, value in [
        ("description", description),
        ("slug", slug),
        ("status", status),
        ("pricing_tier", pricing_tier),
        ("owner_user_id", owner_user_id),
    ]:
        if value is not None:
            await _repo.upsert_product_attr(
                conn,
                id=_id_mod.uuid7(),
                entity_type_id=entity_type_id,
                entity_id=product_id,
                attr_def_id=attrs[attr_code],
                value=value,
            )


async def list_products(
    conn: object,
    *,
    limit: int = 50,
    offset: int = 0,
    category_id: int | None = None,
    is_sellable: bool | None = None,
) -> dict:
    items, total = await _repo.list_products(
        conn,
        limit=limit,
        offset=offset,
        category_id=category_id,
        is_sellable=is_sellable,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


async def get_product(conn: object, product_id: str) -> dict:
    product = await _repo.get_product(conn, product_id)
    if product is None:
        raise AppError("PRODUCT_NOT_FOUND", f"Product '{product_id}' not found.", 404)
    return product


async def create_product(
    conn: object,
    *,
    code: str,
    name: str,
    category_id: int,
    is_sellable: bool = False,
    description: str | None = None,
    slug: str | None = None,
    status: str | None = None,
    pricing_tier: str | None = None,
    owner_user_id: str | None = None,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    # TODO: add platform_admin auth check when RBAC is in place

    # Validate category_type = 'product'
    valid = await _repo.check_category_type(conn, category_id, "product")
    if not valid:
        raise AppError(
            "INVALID_CATEGORY",
            f"Category {category_id} does not exist or is not of type 'product'.",
            422,
        )

    # Check code uniqueness
    code_taken = await _repo.check_code_exists(conn, code)
    if code_taken:
        raise AppError(
            "PRODUCT_CODE_CONFLICT",
            f"A product with code '{code}' already exists.",
            409,
        )

    product_id = _id_mod.uuid7()
    attrs = await _iam_ids.iam_attr_ids(conn, _PRODUCT_ENTITY_CODE)
    entity_type_id = await _iam_ids.iam_entity_type_id(conn, _PRODUCT_ENTITY_CODE)

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.insert_product(
            conn,
            product_id=product_id,
            code=code,
            name=name,
            category_id=category_id,
            is_sellable=is_sellable,
            actor_id=actor_id,
        )
        await _write_product_attrs(
            conn,
            product_id,
            attrs,
            entity_type_id,
            description=description,
            slug=slug,
            status=status,
            pricing_tier=pricing_tier,
            owner_user_id=owner_user_id,
        )
        await _audit.emit(
            conn,
            category="iam",
            action="product.create",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=product_id,
            target_type="platform_product",
        )

    product = await _repo.get_product(conn, product_id)
    return product  # type: ignore[return-value]


async def update_product(
    conn: object,
    product_id: str,
    *,
    name: str | None = None,
    is_sellable: bool | None = None,
    is_active: bool | None = None,
    description: str | None = None,
    slug: str | None = None,
    status: str | None = None,
    pricing_tier: str | None = None,
    owner_user_id: str | None = None,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    existing = await _repo.get_product(conn, product_id)
    if existing is None:
        raise AppError("PRODUCT_NOT_FOUND", f"Product '{product_id}' not found.", 404)

    attrs = await _iam_ids.iam_attr_ids(conn, _PRODUCT_ENTITY_CODE)
    entity_type_id = await _iam_ids.iam_entity_type_id(conn, _PRODUCT_ENTITY_CODE)

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.update_product_meta(
            conn,
            product_id,
            actor_id=actor_id,
            name=name,
            is_sellable=is_sellable,
            is_active=is_active,
        )
        await _write_product_attrs(
            conn,
            product_id,
            attrs,
            entity_type_id,
            description=description,
            slug=slug,
            status=status,
            pricing_tier=pricing_tier,
            owner_user_id=owner_user_id,
        )
        await _audit.emit(
            conn,
            category="iam",
            action="product.update",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=product_id,
            target_type="platform_product",
        )

    return await _repo.get_product(conn, product_id)  # type: ignore[return-value]


async def delete_product(
    conn: object,
    product_id: str,
    *,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> None:
    existing = await _repo.get_product(conn, product_id)
    if existing is None:
        raise AppError("PRODUCT_NOT_FOUND", f"Product '{product_id}' not found.", 404)

    if existing.get("is_deleted"):
        return  # idempotent

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.soft_delete_product(conn, product_id, actor_id=actor_id)
        await _audit.emit(
            conn,
            category="iam",
            action="product.delete",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=product_id,
            target_type="platform_product",
        )


# ---------------------------------------------------------------------------
# Workspace subscriptions
# ---------------------------------------------------------------------------

async def list_workspace_subscriptions(
    conn: object,
    workspace_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    ws_exists = await _repo.check_workspace_exists(conn, workspace_id)
    if not ws_exists:
        raise AppError("WORKSPACE_NOT_FOUND", f"Workspace '{workspace_id}' not found.", 404)

    items, total = await _repo.list_workspace_subscriptions(
        conn, workspace_id, limit=limit, offset=offset
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


async def subscribe_workspace_to_product(
    conn: object,
    workspace_id: str,
    product_id: str,
    *,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    ws_exists = await _repo.check_workspace_exists(conn, workspace_id)
    if not ws_exists:
        raise AppError("WORKSPACE_NOT_FOUND", f"Workspace '{workspace_id}' not found.", 404)

    product = await _repo.get_product(conn, product_id)
    if product is None:
        raise AppError("PRODUCT_NOT_FOUND", f"Product '{product_id}' not found.", 404)

    existing = await _repo.get_workspace_subscription(conn, workspace_id, product_id)
    if existing is not None:
        raise AppError(
            "SUBSCRIPTION_ALREADY_EXISTS",
            f"Workspace '{workspace_id}' is already subscribed to product '{product_id}'.",
            409,
        )

    sub_id = _id_mod.uuid7()

    async with conn.transaction():  # type: ignore[union-attr]
        sub = await _repo.insert_workspace_subscription(
            conn,
            sub_id=sub_id,
            workspace_id=workspace_id,
            product_id=product_id,
            actor_id=actor_id,
        )
        await _audit.emit(
            conn,
            category="iam",
            action="product.workspace.subscribe",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=product_id,
            target_type="platform_product",
        )

    return sub


async def unsubscribe_workspace_from_product(
    conn: object,
    workspace_id: str,
    product_id: str,
    *,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> None:
    ws_exists = await _repo.check_workspace_exists(conn, workspace_id)
    if not ws_exists:
        raise AppError("WORKSPACE_NOT_FOUND", f"Workspace '{workspace_id}' not found.", 404)

    removed = await _repo.deactivate_workspace_subscription(conn, workspace_id, product_id)
    if not removed:
        raise AppError(
            "SUBSCRIPTION_NOT_FOUND",
            f"Workspace '{workspace_id}' is not subscribed to product '{product_id}'.",
            404,
        )

    await _audit.emit(
        conn,
        category="iam",
        action="product.workspace.unsubscribe",
        outcome="success",
        user_id=actor_id,
        session_id=session_id,
        org_id=org_id_audit,
        workspace_id=workspace_id_audit,
        target_id=product_id,
        target_type="platform_product",
    )
