"""IAM feature registry service — CRUD with audit events."""

from __future__ import annotations

import importlib

_repo = importlib.import_module("04_backend.02_features.iam.feature_registry.repository")
_id_mod = importlib.import_module("scripts.00_core._id")
_errors_mod = importlib.import_module("04_backend.01_core.errors")
_audit = importlib.import_module("04_backend.02_features.audit.service")
_iam_ids = importlib.import_module("04_backend.02_features.iam._iam_attr_ids")

AppError = _errors_mod.AppError

_FEATURE_ENTITY_CODE = "platform_feature"


async def _write_feature_attrs(
    conn: object,
    feature_id: str,
    attrs: dict,
    entity_type_id: int,
    *,
    description: str | None = None,
    status: str | None = None,
    doc_url: str | None = None,
    owner_user_id: str | None = None,
    version_introduced: str | None = None,
) -> None:
    """Write EAV attrs for a feature. Only writes non-None values."""
    for attr_code, value in [
        ("description", description),
        ("status", status),
        ("doc_url", doc_url),
        ("owner_user_id", owner_user_id),
        ("version_introduced", version_introduced),
    ]:
        if value is not None:
            await _repo.upsert_feature_attr(
                conn,
                id=_id_mod.uuid7(),
                entity_type_id=entity_type_id,
                entity_id=feature_id,
                attr_def_id=attrs[attr_code],
                value=value,
            )


async def list_features(
    conn: object,
    *,
    limit: int = 50,
    offset: int = 0,
    product_id: str | None = None,
    scope_id: int | None = None,
    category_id: int | None = None,
    parent_id: str | None = None,
) -> dict:
    items, total = await _repo.list_features(
        conn,
        limit=limit,
        offset=offset,
        product_id=product_id,
        scope_id=scope_id,
        category_id=category_id,
        parent_id=parent_id,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


async def get_feature(conn: object, feature_id: str) -> dict:
    feature = await _repo.get_feature(conn, feature_id)
    if feature is None:
        raise AppError("FEATURE_NOT_FOUND", f"Feature '{feature_id}' not found.", 404)
    return feature


async def list_feature_children(
    conn: object,
    feature_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    feature = await _repo.get_feature(conn, feature_id)
    if feature is None:
        raise AppError("FEATURE_NOT_FOUND", f"Feature '{feature_id}' not found.", 404)

    items, total = await _repo.list_children(conn, feature_id, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


async def create_feature(
    conn: object,
    *,
    product_id: str,
    code: str,
    name: str,
    scope_id: int,
    category_id: int,
    parent_id: str | None = None,
    description: str | None = None,
    status: str | None = None,
    doc_url: str | None = None,
    owner_user_id: str | None = None,
    version_introduced: str | None = None,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    # Validate product exists
    product_exists = await _repo.check_product_exists(conn, product_id)
    if not product_exists:
        raise AppError("PRODUCT_NOT_FOUND", f"Product '{product_id}' not found.", 404)

    # Validate scope exists
    scope_exists = await _repo.check_scope_exists(conn, scope_id)
    if not scope_exists:
        raise AppError("SCOPE_NOT_FOUND", f"Scope '{scope_id}' not found.", 422)

    # Validate category_type = 'feature'
    valid_cat = await _repo.check_category_type(conn, category_id, "feature")
    if not valid_cat:
        raise AppError(
            "INVALID_CATEGORY",
            f"Category {category_id} does not exist or is not of type 'feature'.",
            422,
        )

    # Validate parent exists (if provided)
    if parent_id is not None:
        parent = await _repo.get_feature(conn, parent_id)
        if parent is None:
            raise AppError("PARENT_FEATURE_NOT_FOUND", f"Parent feature '{parent_id}' not found.", 404)

    # Check code uniqueness within product
    code_taken = await _repo.check_code_exists(conn, product_id, code)
    if code_taken:
        raise AppError(
            "FEATURE_CODE_CONFLICT",
            f"A feature with code '{code}' already exists in this product.",
            409,
        )

    feature_id = _id_mod.uuid7()
    attrs = await _iam_ids.iam_attr_ids(conn, _FEATURE_ENTITY_CODE)
    entity_type_id = await _iam_ids.iam_entity_type_id(conn, _FEATURE_ENTITY_CODE)

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.insert_feature(
            conn,
            feature_id=feature_id,
            product_id=product_id,
            parent_id=parent_id,
            code=code,
            name=name,
            scope_id=scope_id,
            category_id=category_id,
            actor_id=actor_id,
        )
        await _write_feature_attrs(
            conn,
            feature_id,
            attrs,
            entity_type_id,
            description=description,
            status=status,
            doc_url=doc_url,
            owner_user_id=owner_user_id,
            version_introduced=version_introduced,
        )
        await _audit.emit(
            conn,
            category="iam",
            action="feature.create",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=feature_id,
            target_type="platform_feature",
        )

    feature = await _repo.get_feature(conn, feature_id)
    return feature  # type: ignore[return-value]


async def update_feature(
    conn: object,
    feature_id: str,
    *,
    name: str | None = None,
    scope_id: int | None = None,
    category_id: int | None = None,
    is_active: bool | None = None,
    description: str | None = None,
    status: str | None = None,
    doc_url: str | None = None,
    owner_user_id: str | None = None,
    version_introduced: str | None = None,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> dict:
    existing = await _repo.get_feature(conn, feature_id)
    if existing is None:
        raise AppError("FEATURE_NOT_FOUND", f"Feature '{feature_id}' not found.", 404)

    # Validate scope if being changed
    if scope_id is not None:
        scope_exists = await _repo.check_scope_exists(conn, scope_id)
        if not scope_exists:
            raise AppError("SCOPE_NOT_FOUND", f"Scope '{scope_id}' not found.", 422)

    # Validate category if being changed
    if category_id is not None:
        valid_cat = await _repo.check_category_type(conn, category_id, "feature")
        if not valid_cat:
            raise AppError(
                "INVALID_CATEGORY",
                f"Category {category_id} does not exist or is not of type 'feature'.",
                422,
            )

    attrs = await _iam_ids.iam_attr_ids(conn, _FEATURE_ENTITY_CODE)
    entity_type_id = await _iam_ids.iam_entity_type_id(conn, _FEATURE_ENTITY_CODE)

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.update_feature_meta(
            conn,
            feature_id,
            actor_id=actor_id,
            name=name,
            scope_id=scope_id,
            category_id=category_id,
            is_active=is_active,
        )
        await _write_feature_attrs(
            conn,
            feature_id,
            attrs,
            entity_type_id,
            description=description,
            status=status,
            doc_url=doc_url,
            owner_user_id=owner_user_id,
            version_introduced=version_introduced,
        )
        await _audit.emit(
            conn,
            category="iam",
            action="feature.update",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=feature_id,
            target_type="platform_feature",
        )

    return await _repo.get_feature(conn, feature_id)  # type: ignore[return-value]


async def delete_feature(
    conn: object,
    feature_id: str,
    *,
    actor_id: str,
    session_id: str | None = None,
    org_id_audit: str | None = None,
    workspace_id_audit: str | None = None,
) -> None:
    existing = await _repo.get_feature(conn, feature_id)
    if existing is None:
        raise AppError("FEATURE_NOT_FOUND", f"Feature '{feature_id}' not found.", 404)

    if existing.get("is_deleted"):
        return  # idempotent

    async with conn.transaction():  # type: ignore[union-attr]
        await _repo.soft_delete_feature(conn, feature_id, actor_id=actor_id)
        await _audit.emit(
            conn,
            category="iam",
            action="feature.delete",
            outcome="success",
            user_id=actor_id,
            session_id=session_id,
            org_id=org_id_audit,
            workspace_id=workspace_id_audit,
            target_id=feature_id,
            target_type="platform_feature",
        )
