"""IAM products routes — platform product catalog CRUD + workspace subscriptions.

POST   /v1/products                          create product (TODO: platform admin only)
GET    /v1/products                          list products (?category_id=&is_sellable=)
GET    /v1/products/{id}                     get product
PATCH  /v1/products/{id}                     update product
DELETE /v1/products/{id}                     soft-delete product

GET    /v1/workspaces/{ws_id}/products       list products subscribed to a workspace
POST   /v1/workspaces/{ws_id}/products       subscribe workspace to a product
DELETE /v1/workspaces/{ws_id}/products/{product_id}  unsubscribe
"""

from __future__ import annotations

import importlib

from fastapi import APIRouter, Depends, Query

_db = importlib.import_module("04_backend.01_core.db")
_service = importlib.import_module("04_backend.02_features.iam.products.service")
_resp = importlib.import_module("04_backend.01_core.response")
_auth = importlib.import_module("04_backend.01_core.auth")
_schemas = importlib.import_module("04_backend.02_features.iam.products.schemas")

router = APIRouter(tags=["products"])


@router.post("/v1/products", status_code=201)
async def create_product(
    body: _schemas.CreateProductRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Create a new platform product.

    TODO: restrict to platform_admin role once RBAC is in place.
    """
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    org_id: str | None = token.get("org_id")
    workspace_id: str | None = token.get("workspace_id")

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.create_product(
            conn,
            code=body.code,
            name=body.name,
            category_id=body.category_id,
            is_sellable=body.is_sellable,
            description=body.description,
            slug=body.slug,
            status=body.status,
            pricing_tier=body.pricing_tier,
            owner_user_id=body.owner_user_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id,
            workspace_id_audit=workspace_id,
        )
    return _resp.ok(result)


@router.get("/v1/products")
async def list_products(
    category_id: int | None = Query(None),
    is_sellable: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """List products with optional filtering."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.list_products(
            conn,
            limit=limit,
            offset=offset,
            category_id=category_id,
            is_sellable=is_sellable,
        )
    return _resp.ok(result)


@router.get("/v1/products/{product_id}")
async def get_product(
    product_id: str,
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Get a single product by ID."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.get_product(conn, product_id)
    return _resp.ok(result)


@router.patch("/v1/products/{product_id}")
async def update_product(
    product_id: str,
    body: _schemas.UpdateProductRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Update a product."""
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    org_id: str | None = token.get("org_id")
    workspace_id: str | None = token.get("workspace_id")

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.update_product(
            conn,
            product_id,
            name=body.name,
            is_sellable=body.is_sellable,
            is_active=body.is_active,
            description=body.description,
            slug=body.slug,
            status=body.status,
            pricing_tier=body.pricing_tier,
            owner_user_id=body.owner_user_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id,
            workspace_id_audit=workspace_id,
        )
    return _resp.ok(result)


@router.delete("/v1/products/{product_id}", status_code=204)
async def delete_product(
    product_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    """Soft-delete a product."""
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    org_id: str | None = token.get("org_id")
    workspace_id: str | None = token.get("workspace_id")

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.delete_product(
            conn,
            product_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id,
            workspace_id_audit=workspace_id,
        )


# ---------------------------------------------------------------------------
# Workspace-product subscriptions
# ---------------------------------------------------------------------------

@router.get("/v1/workspaces/{workspace_id}/products")
async def list_workspace_products(
    workspace_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """List products subscribed to a workspace."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.list_workspace_subscriptions(
            conn, workspace_id, limit=limit, offset=offset
        )
    return _resp.ok(result)


@router.post("/v1/workspaces/{workspace_id}/products", status_code=201)
async def subscribe_workspace_to_product(
    workspace_id: str,
    body: _schemas.SubscribeWorkspaceProductRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Subscribe a workspace to a product."""
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    org_id: str | None = token.get("org_id")
    workspace_id_audit: str | None = token.get("workspace_id")

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.subscribe_workspace_to_product(
            conn,
            workspace_id,
            body.product_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id,
            workspace_id_audit=workspace_id_audit,
        )
    return _resp.ok(result)


@router.delete("/v1/workspaces/{workspace_id}/products/{product_id}", status_code=204)
async def unsubscribe_workspace_from_product(
    workspace_id: str,
    product_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    """Unsubscribe a workspace from a product."""
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    org_id: str | None = token.get("org_id")
    workspace_id_audit: str | None = token.get("workspace_id")

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.unsubscribe_workspace_from_product(
            conn,
            workspace_id,
            product_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id,
            workspace_id_audit=workspace_id_audit,
        )
