"""IAM feature flags routes.

POST   /v1/feature-flags                         create flag
GET    /v1/feature-flags                         list flags (filters: product_id, scope_id, category_id, status, flag_type)
GET    /v1/feature-flags/bootstrap               all active flags for a context
POST   /v1/feature-flags/eval                    evaluate a flag for a context
GET    /v1/feature-flags/by-product/{product_id} flags by product
GET    /v1/feature-flags/{id}                    get flag
PATCH  /v1/feature-flags/{id}                    update flag
DELETE /v1/feature-flags/{id}                    soft-delete flag

GET    /v1/feature-flags/{id}/environments       list env overrides
PUT    /v1/feature-flags/{id}/environments/{env_code}  upsert env override

GET    /v1/feature-flags/{id}/targets            list targets
POST   /v1/feature-flags/{id}/targets            add target
DELETE /v1/feature-flags/{id}/targets/{target_id} remove target
"""

from __future__ import annotations

import importlib

from fastapi import APIRouter, Depends, Query

_db = importlib.import_module("04_backend.01_core.db")
_service = importlib.import_module("04_backend.02_features.iam.feature_flags.service")
_resp = importlib.import_module("04_backend.01_core.response")
_auth = importlib.import_module("04_backend.01_core.auth")
_schemas = importlib.import_module("04_backend.02_features.iam.feature_flags.schemas")

router = APIRouter(tags=["feature-flags"])


# ---------------------------------------------------------------------------
# Fixed-path routes (must be before /{id} to avoid ambiguity)
# ---------------------------------------------------------------------------

@router.get("/v1/feature-flags/bootstrap")
async def bootstrap(
    environment: str | None = Query(None),
    workspace_id: str | None = Query(None),
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Return all active flags for a given environment + workspace context."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.bootstrap_flags(
            conn,
            environment=environment,
            workspace_id=workspace_id,
        )
    return _resp.ok(result)


@router.post("/v1/feature-flags/eval")
async def eval_flag(
    body: _schemas.EvalRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Evaluate a single feature flag for a given context."""
    ctx = body.context
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.eval_flag(
            conn,
            flag_code=body.flag_code,
            user_id=ctx.user_id,
            org_id=ctx.org_id,
            workspace_id=ctx.workspace_id,
            environment=ctx.environment,
        )
    return _resp.ok(result)


@router.get("/v1/feature-flags/by-product/{product_id}")
async def list_by_product(
    product_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """List flags for a specific product."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.list_flags_by_product(
            conn, product_id, limit=limit, offset=offset
        )
    return _resp.ok(result)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post("/v1/feature-flags", status_code=201)
async def create_flag(
    body: _schemas.CreateFlagRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Create a new feature flag."""
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    org_id: str | None = token.get("org_id")
    workspace_id: str | None = token.get("workspace_id")

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.create_flag(
            conn,
            code=body.code,
            name=body.name,
            product_id=body.product_id,
            feature_id=body.feature_id,
            scope_id=body.scope_id,
            category_id=body.category_id,
            flag_type=body.flag_type,
            status=body.status,
            default_value=body.default_value,
            description=body.description,
            owner_user_id=body.owner_user_id,
            jira_ticket=body.jira_ticket,
            rollout_percentage=body.rollout_percentage,
            launch_date=body.launch_date,
            sunset_date=body.sunset_date,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id,
            workspace_id_audit=workspace_id,
        )
    return _resp.ok(result)


@router.get("/v1/feature-flags")
async def list_flags(
    product_id: str | None = Query(None),
    scope_id: int | None = Query(None),
    category_id: int | None = Query(None),
    status: str | None = Query(None),
    flag_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """List feature flags with optional filters."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.list_flags(
            conn,
            limit=limit,
            offset=offset,
            product_id=product_id,
            scope_id=scope_id,
            category_id=category_id,
            status=status,
            flag_type=flag_type,
        )
    return _resp.ok(result)


@router.get("/v1/feature-flags/{flag_id}")
async def get_flag(
    flag_id: str,
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Get a single feature flag by ID."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.get_flag(conn, flag_id)
    return _resp.ok(result)


@router.patch("/v1/feature-flags/{flag_id}")
async def update_flag(
    flag_id: str,
    body: _schemas.UpdateFlagRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Update a feature flag."""
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    org_id: str | None = token.get("org_id")
    workspace_id: str | None = token.get("workspace_id")

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.update_flag(
            conn,
            flag_id,
            name=body.name,
            status=body.status,
            flag_type=body.flag_type,
            default_value=body.default_value,
            is_active=body.is_active,
            description=body.description,
            owner_user_id=body.owner_user_id,
            jira_ticket=body.jira_ticket,
            rollout_percentage=body.rollout_percentage,
            launch_date=body.launch_date,
            sunset_date=body.sunset_date,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id,
            workspace_id_audit=workspace_id,
        )
    return _resp.ok(result)


@router.delete("/v1/feature-flags/{flag_id}", status_code=204)
async def delete_flag(
    flag_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    """Soft-delete a feature flag."""
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    org_id: str | None = token.get("org_id")
    workspace_id: str | None = token.get("workspace_id")

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.delete_flag(
            conn,
            flag_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id,
            workspace_id_audit=workspace_id,
        )


# ---------------------------------------------------------------------------
# Environment overrides
# ---------------------------------------------------------------------------

@router.get("/v1/feature-flags/{flag_id}/environments")
async def list_environments(
    flag_id: str,
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """List environment overrides for a flag."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.list_environments(conn, flag_id)
    return _resp.ok(result)


@router.put("/v1/feature-flags/{flag_id}/environments/{env_code}")
async def upsert_env_override(
    flag_id: str,
    env_code: str,
    body: _schemas.UpsertEnvOverrideRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Create or update an environment override for a flag."""
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    org_id: str | None = token.get("org_id")
    workspace_id: str | None = token.get("workspace_id")

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.upsert_environment_override(
            conn,
            flag_id,
            env_code,
            enabled=body.enabled,
            value=body.value,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id,
            workspace_id_audit=workspace_id,
        )
    return _resp.ok(result)


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

@router.get("/v1/feature-flags/{flag_id}/targets")
async def list_targets(
    flag_id: str,
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """List targeting rules for a flag."""
    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.list_targets(conn, flag_id)
    return _resp.ok(result)


@router.post("/v1/feature-flags/{flag_id}/targets", status_code=201)
async def create_target(
    flag_id: str,
    body: _schemas.CreateTargetRequest,  # type: ignore[name-defined]
    token: dict = Depends(_auth.require_auth),
) -> dict:
    """Add a targeting rule to a flag."""
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    org_id: str | None = token.get("org_id")
    workspace_id: str | None = token.get("workspace_id")

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        result = await _service.create_target(
            conn,
            flag_id,
            org_id=body.org_id,
            workspace_id=body.workspace_id,
            value=body.value,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id,
            workspace_id_audit=workspace_id,
        )
    return _resp.ok(result)


@router.delete("/v1/feature-flags/{flag_id}/targets/{target_id}", status_code=204)
async def delete_target(
    flag_id: str,
    target_id: str,
    token: dict = Depends(_auth.require_auth),
) -> None:
    """Remove a targeting rule from a flag."""
    actor_id: str = token["sub"]
    session_id: str = token.get("sid", "")
    org_id: str | None = token.get("org_id")
    workspace_id: str | None = token.get("workspace_id")

    pool = _db.get_pool()
    async with pool.acquire() as conn:
        await _service.delete_target(
            conn,
            flag_id,
            target_id,
            actor_id=actor_id,
            session_id=session_id,
            org_id_audit=org_id,
            workspace_id_audit=workspace_id,
        )
