"""IAM feature registry routes — platform feature CRUD.

POST   /v1/features                          create feature
GET    /v1/features                          list features (?product_id=&scope_id=&category_id=&parent_id=)
GET    /v1/features/{id}                     get feature
PATCH  /v1/features/{id}                     update feature
DELETE /v1/features/{id}                     soft-delete feature
GET    /v1/features/{id}/children            list child features
"""

from __future__ import annotations

import importlib

from fastapi import APIRouter, Depends, Query

_db = importlib.import_module("04_backend.01_core.db")
_service = importlib.import_module("04_backend.02_features.iam.feature_registry.service")
_resp = importlib.import_module("04_backend.01_core.response")
_auth = importlib.import_module("04_backend.01_core.auth")
_schemas = importlib.import_module("04_backend.02_features.iam.feature_registry.schemas")

router = APIRouter(prefix="/v1/features", tags=["features"])


@router.post("", status_code=201)
async def create_feature(
    body: _schemas.CreateFeatureRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Create a new platform feature."""
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    org_id: str | None = token.get("org_id")
    workspace_id: str | None = token.get("workspace_id")

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.create_feature(
            conn,
            product_id=body.product_id,
            code=body.code,
            name=body.name,
            scope_id=body.scope_id,
            category_id=body.category_id,
            parent_id=body.parent_id,
            description=body.description,
            status=body.status,
            doc_url=body.doc_url,
            owner_user_id=body.owner_user_id,
            version_introduced=body.version_introduced,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id,
            workspace_id_audit=workspace_id,
        )
    return _resp.ok(result)


@router.get("")
async def list_features(
    product_id: str | None = Query(None),
    scope_id: int | None = Query(None),
    category_id: int | None = Query(None),
    parent_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """List features with optional filtering."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.list_features(
            conn,
            limit=limit,
            offset=offset,
            product_id=product_id,
            scope_id=scope_id,
            category_id=category_id,
            parent_id=parent_id,
        )
    return _resp.ok(result)


@router.get("/{feature_id}")
async def get_feature(
    feature_id: str,
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Get a single feature by ID."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.get_feature(conn, feature_id)
    return _resp.ok(result)


@router.patch("/{feature_id}")
async def update_feature(
    feature_id: str,
    body: _schemas.UpdateFeatureRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Update a feature."""
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    org_id: str | None = token.get("org_id")
    workspace_id: str | None = token.get("workspace_id")

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.update_feature(
            conn,
            feature_id,
            name=body.name,
            scope_id=body.scope_id,
            category_id=body.category_id,
            is_active=body.is_active,
            description=body.description,
            status=body.status,
            doc_url=body.doc_url,
            owner_user_id=body.owner_user_id,
            version_introduced=body.version_introduced,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id,
            workspace_id_audit=workspace_id,
        )
    return _resp.ok(result)


@router.delete("/{feature_id}", status_code=204)
async def delete_feature(
    feature_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    """Soft-delete a feature."""
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    org_id: str | None = token.get("org_id")
    workspace_id: str | None = token.get("workspace_id")

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.delete_feature(
            conn,
            feature_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id,
            workspace_id_audit=workspace_id,
        )


@router.get("/{feature_id}/children")
async def list_feature_children(
    feature_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """List direct child features of a feature."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.list_feature_children(
            conn, feature_id, limit=limit, offset=offset
        )
    return _resp.ok(result)
