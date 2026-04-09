"""Integration tests for IAM feature flags endpoints.

POST   /v1/feature-flags                         create flag
GET    /v1/feature-flags                         list flags
GET    /v1/feature-flags/bootstrap               all active flags for a context
POST   /v1/feature-flags/eval                    evaluate a flag
GET    /v1/feature-flags/by-product/{product_id} flags by product
GET    /v1/feature-flags/{id}                    get flag
PATCH  /v1/feature-flags/{id}                    update flag
DELETE /v1/feature-flags/{id}                    soft-delete flag
GET    /v1/feature-flags/{id}/environments       list env overrides
PUT    /v1/feature-flags/{id}/environments/{env} upsert env override
GET    /v1/feature-flags/{id}/targets            list targets
POST   /v1/feature-flags/{id}/targets            add target
DELETE /v1/feature-flags/{id}/targets/{tid}      remove target

Requires:
  - Backend running at http://localhost:58000
  - First admin user: username=admin, password=ChangeMe123!

Run with:
  pytest tests/test_api_feature_flags.py -v -m integration
"""

import uuid

import httpx
import pytest

BASE = "http://localhost:58000"
ADMIN_USER = "admin"
ADMIN_PASS = "ChangeMe123!"

# Dimension IDs from seeded data
SCOPE_PLATFORM = 1
SCOPE_ORG = 2
SCOPE_WORKSPACE = 3
CATEGORY_KILL_SWITCH = 16   # flag type
CATEGORY_ROLLOUT = 17       # flag type


# ---------------------------------------------------------------------------
# Module-scoped auth fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def auth_token() -> str:
    res = httpx.post(
        f"{BASE}/v1/sessions",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
    )
    assert res.status_code == 201, f"Login failed: {res.text}"
    return res.json()["data"]["access_token"]


@pytest.fixture(scope="module")
def product_id(auth_token) -> str:
    """Create a product to use in tests."""
    res = httpx.post(
        f"{BASE}/v1/products",
        json={
            "code": f"test-ff-prod-{uuid.uuid4().hex[:8]}",
            "name": "Feature Flag Test Product",
            "category_id": 21,  # core_platform
        },
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 201, f"Product create failed: {res.text}"
    return res.json()["data"]["id"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _unique_code() -> str:
    return f"test.flag.{uuid.uuid4().hex[:8]}"


def _create_flag(token: str, product_id: str, **kwargs) -> dict:
    payload = {
        "code": _unique_code(),
        "name": "Test Flag",
        "product_id": product_id,
        "scope_id": SCOPE_PLATFORM,
        "category_id": CATEGORY_KILL_SWITCH,
        "flag_type": "boolean",
        "default_value": False,
        **kwargs,
    }
    res = httpx.post(
        f"{BASE}/v1/feature-flags",
        json=payload,
        headers=_auth_headers(token),
    )
    assert res.status_code == 201, f"Flag create failed: {res.text}"
    return res.json()["data"]


# ---------------------------------------------------------------------------
# Create flag
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_create_flag_success(auth_token, product_id):
    code = _unique_code()
    res = httpx.post(
        f"{BASE}/v1/feature-flags",
        json={
            "code": code,
            "name": "My Feature Flag",
            "product_id": product_id,
            "scope_id": SCOPE_PLATFORM,
            "category_id": CATEGORY_KILL_SWITCH,
            "flag_type": "boolean",
            "status": "draft",
            "default_value": False,
        },
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["code"] == code
    assert data["name"] == "My Feature Flag"
    assert data["flag_type"] == "boolean"
    assert data["status"] == "draft"
    assert data["scope_code"] == "platform"
    assert data["is_active"] is True
    assert data["is_deleted"] is False
    assert "id" in data


@pytest.mark.integration
def test_create_flag_with_description(auth_token, product_id):
    res = httpx.post(
        f"{BASE}/v1/feature-flags",
        json={
            "code": _unique_code(),
            "name": "Flag With Desc",
            "product_id": product_id,
            "scope_id": SCOPE_PLATFORM,
            "category_id": CATEGORY_KILL_SWITCH,
            "flag_type": "kill_switch",
            "description": "A test description",
            "jira_ticket": "FEAT-123",
        },
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 201, res.text


@pytest.mark.integration
def test_create_flag_missing_required_fields_returns_422(auth_token, product_id):
    # Missing scope_id, category_id, flag_type
    res = httpx.post(
        f"{BASE}/v1/feature-flags",
        json={
            "code": _unique_code(),
            "name": "Incomplete Flag",
            "product_id": product_id,
        },
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 422


@pytest.mark.integration
def test_create_flag_duplicate_code_returns_409(auth_token, product_id):
    code = _unique_code()
    flag = _create_flag(auth_token, product_id, code=code)

    res = httpx.post(
        f"{BASE}/v1/feature-flags",
        json={
            "code": code,
            "name": "Duplicate",
            "product_id": product_id,
            "scope_id": SCOPE_PLATFORM,
            "category_id": CATEGORY_KILL_SWITCH,
            "flag_type": "boolean",
        },
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 409, res.text
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "FLAG_CODE_CONFLICT"


@pytest.mark.integration
def test_create_flag_invalid_category_returns_422(auth_token, product_id):
    # Category 7 is 'iam' (feature type, not flag type)
    res = httpx.post(
        f"{BASE}/v1/feature-flags",
        json={
            "code": _unique_code(),
            "name": "Bad Category Flag",
            "product_id": product_id,
            "scope_id": SCOPE_PLATFORM,
            "category_id": 7,  # iam feature category — not a flag category
            "flag_type": "boolean",
        },
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 422


@pytest.mark.integration
def test_create_flag_unauthenticated(product_id):
    res = httpx.post(
        f"{BASE}/v1/feature-flags",
        json={
            "code": _unique_code(),
            "name": "No Auth",
            "product_id": product_id,
            "scope_id": SCOPE_PLATFORM,
            "category_id": CATEGORY_KILL_SWITCH,
            "flag_type": "boolean",
        },
    )
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# List flags
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_list_flags_empty_returns_list(auth_token, product_id):
    # Create a brand-new product so we can query flags for it specifically
    new_prod_res = httpx.post(
        f"{BASE}/v1/products",
        json={
            "code": f"empty-ff-prod-{uuid.uuid4().hex[:8]}",
            "name": "Empty Product For Flags",
            "category_id": 21,
        },
        headers=_auth_headers(auth_token),
    )
    new_product_id = new_prod_res.json()["data"]["id"]

    res = httpx.get(
        f"{BASE}/v1/feature-flags",
        params={"product_id": new_product_id},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert "items" in data
    assert "total" in data
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.integration
def test_list_flags_with_results(auth_token, product_id):
    _create_flag(auth_token, product_id)
    _create_flag(auth_token, product_id)

    res = httpx.get(
        f"{BASE}/v1/feature-flags",
        params={"product_id": product_id},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["total"] >= 2
    assert len(data["items"]) >= 2


@pytest.mark.integration
def test_list_flags_filter_by_scope_id(auth_token, product_id):
    _create_flag(auth_token, product_id, scope_id=SCOPE_PLATFORM)

    res = httpx.get(
        f"{BASE}/v1/feature-flags",
        params={"scope_id": SCOPE_PLATFORM},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    for item in items:
        assert item["scope_code"] == "platform"


@pytest.mark.integration
def test_list_flags_filter_by_status(auth_token, product_id):
    code = _unique_code()
    _create_flag(auth_token, product_id, code=code, status="active")

    res = httpx.get(
        f"{BASE}/v1/feature-flags",
        params={"status": "active"},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    codes = [i["code"] for i in items]
    assert code in codes


# ---------------------------------------------------------------------------
# Get flag
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_get_flag_found(auth_token, product_id):
    flag = _create_flag(auth_token, product_id)

    res = httpx.get(
        f"{BASE}/v1/feature-flags/{flag['id']}",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["id"] == flag["id"]


@pytest.mark.integration
def test_get_flag_not_found(auth_token):
    res = httpx.get(
        f"{BASE}/v1/feature-flags/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "FLAG_NOT_FOUND"


# ---------------------------------------------------------------------------
# Update flag
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_update_flag_status(auth_token, product_id):
    flag = _create_flag(auth_token, product_id)

    res = httpx.patch(
        f"{BASE}/v1/feature-flags/{flag['id']}",
        json={"status": "active"},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["status"] == "active"


@pytest.mark.integration
def test_update_flag_default_value(auth_token, product_id):
    flag = _create_flag(auth_token, product_id, flag_type="variant", default_value="control")

    res = httpx.patch(
        f"{BASE}/v1/feature-flags/{flag['id']}",
        json={"default_value": "treatment"},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["default_value"] == "treatment"


@pytest.mark.integration
def test_update_flag_not_found(auth_token):
    res = httpx.patch(
        f"{BASE}/v1/feature-flags/00000000-0000-0000-0000-000000000000",
        json={"status": "active"},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "FLAG_NOT_FOUND"


# ---------------------------------------------------------------------------
# Delete flag (soft-delete)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_delete_flag_success(auth_token, product_id):
    flag = _create_flag(auth_token, product_id)

    res = httpx.delete(
        f"{BASE}/v1/feature-flags/{flag['id']}",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 204, res.text


@pytest.mark.integration
def test_delete_flag_idempotent(auth_token, product_id):
    flag = _create_flag(auth_token, product_id)

    res1 = httpx.delete(
        f"{BASE}/v1/feature-flags/{flag['id']}",
        headers=_auth_headers(auth_token),
    )
    assert res1.status_code == 204

    res2 = httpx.delete(
        f"{BASE}/v1/feature-flags/{flag['id']}",
        headers=_auth_headers(auth_token),
    )
    assert res2.status_code == 204


@pytest.mark.integration
def test_delete_flag_not_found(auth_token):
    res = httpx.delete(
        f"{BASE}/v1/feature-flags/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "FLAG_NOT_FOUND"


# ---------------------------------------------------------------------------
# Environment overrides
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_list_environments_empty(auth_token, product_id):
    flag = _create_flag(auth_token, product_id)

    res = httpx.get(
        f"{BASE}/v1/feature-flags/{flag['id']}/environments",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert "items" in data
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.integration
def test_set_env_override_and_list(auth_token, product_id):
    flag = _create_flag(auth_token, product_id)

    # Set an override for prod
    put_res = httpx.put(
        f"{BASE}/v1/feature-flags/{flag['id']}/environments/prod",
        json={"enabled": True, "value": True},
        headers=_auth_headers(auth_token),
    )
    assert put_res.status_code == 200, put_res.text
    override = put_res.json()["data"]
    assert override["environment_code"] == "prod"
    assert override["enabled"] is True

    # List environments — should have 1
    list_res = httpx.get(
        f"{BASE}/v1/feature-flags/{flag['id']}/environments",
        headers=_auth_headers(auth_token),
    )
    assert list_res.status_code == 200
    data = list_res.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["environment_code"] == "prod"


@pytest.mark.integration
def test_set_env_override_not_found_env(auth_token, product_id):
    flag = _create_flag(auth_token, product_id)

    res = httpx.put(
        f"{BASE}/v1/feature-flags/{flag['id']}/environments/nonexistent",
        json={"enabled": True},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "ENV_NOT_FOUND"


@pytest.mark.integration
def test_set_env_override_upserts(auth_token, product_id):
    """Setting the same env override twice updates it."""
    flag = _create_flag(auth_token, product_id)

    httpx.put(
        f"{BASE}/v1/feature-flags/{flag['id']}/environments/dev",
        json={"enabled": True, "value": False},
        headers=_auth_headers(auth_token),
    )
    res2 = httpx.put(
        f"{BASE}/v1/feature-flags/{flag['id']}/environments/dev",
        json={"enabled": False, "value": None},
        headers=_auth_headers(auth_token),
    )
    assert res2.status_code == 200
    assert res2.json()["data"]["enabled"] is False

    # Still only 1 env override
    list_res = httpx.get(
        f"{BASE}/v1/feature-flags/{flag['id']}/environments",
        headers=_auth_headers(auth_token),
    )
    assert list_res.json()["data"]["total"] == 1


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_list_targets_empty(auth_token, product_id):
    flag = _create_flag(auth_token, product_id)

    res = httpx.get(
        f"{BASE}/v1/feature-flags/{flag['id']}/targets",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.integration
def test_add_platform_target(auth_token, product_id):
    """Platform-scoped flag can have a platform target."""
    flag = _create_flag(auth_token, product_id, scope_id=SCOPE_PLATFORM)

    res = httpx.post(
        f"{BASE}/v1/feature-flags/{flag['id']}/targets",
        json={"value": True},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["flag_id"] == flag["id"]


@pytest.mark.integration
def test_add_org_target(auth_token, product_id):
    """Org-scoped flag requires org_id in target."""
    flag = _create_flag(auth_token, product_id, scope_id=SCOPE_ORG)
    fake_org_id = str(uuid.uuid4())

    res = httpx.post(
        f"{BASE}/v1/feature-flags/{flag['id']}/targets",
        json={"org_id": fake_org_id, "value": True},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["org_id"] == fake_org_id


@pytest.mark.integration
def test_add_org_target_missing_org_id_returns_422(auth_token, product_id):
    """Org-scoped flag without org_id should fail."""
    flag = _create_flag(auth_token, product_id, scope_id=SCOPE_ORG)

    res = httpx.post(
        f"{BASE}/v1/feature-flags/{flag['id']}/targets",
        json={"value": True},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 422


@pytest.mark.integration
def test_add_workspace_target(auth_token, product_id):
    """Workspace-scoped flag requires workspace_id in target."""
    flag = _create_flag(auth_token, product_id, scope_id=SCOPE_WORKSPACE)
    fake_ws_id = str(uuid.uuid4())

    res = httpx.post(
        f"{BASE}/v1/feature-flags/{flag['id']}/targets",
        json={"workspace_id": fake_ws_id, "value": {"feature": "enabled"}},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["workspace_id"] == fake_ws_id


@pytest.mark.integration
def test_delete_target_success(auth_token, product_id):
    flag = _create_flag(auth_token, product_id, scope_id=SCOPE_PLATFORM)
    target_res = httpx.post(
        f"{BASE}/v1/feature-flags/{flag['id']}/targets",
        json={"value": True},
        headers=_auth_headers(auth_token),
    )
    target_id = target_res.json()["data"]["id"]

    res = httpx.delete(
        f"{BASE}/v1/feature-flags/{flag['id']}/targets/{target_id}",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 204, res.text


@pytest.mark.integration
def test_delete_target_not_found(auth_token, product_id):
    flag = _create_flag(auth_token, product_id, scope_id=SCOPE_PLATFORM)

    res = httpx.delete(
        f"{BASE}/v1/feature-flags/{flag['id']}/targets/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "TARGET_NOT_FOUND"


# ---------------------------------------------------------------------------
# Eval endpoint
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_eval_flag_inactive_returns_default(auth_token, product_id):
    """Inactive flag always returns default_value."""
    flag = _create_flag(
        auth_token, product_id,
        flag_type="boolean",
        default_value=False,
        status="draft",
    )
    # Set is_active = False
    httpx.patch(
        f"{BASE}/v1/feature-flags/{flag['id']}",
        json={"is_active": False},
        headers=_auth_headers(auth_token),
    )

    res = httpx.post(
        f"{BASE}/v1/feature-flags/eval",
        json={"flag_code": flag["code"], "context": {}},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["value"] == False
    assert data["reason"] == "flag_inactive"


@pytest.mark.integration
def test_eval_flag_archived_returns_default(auth_token, product_id):
    """Archived flag always returns default_value."""
    flag = _create_flag(
        auth_token, product_id,
        default_value="disabled",
        status="active",
    )
    httpx.patch(
        f"{BASE}/v1/feature-flags/{flag['id']}",
        json={"status": "archived"},
        headers=_auth_headers(auth_token),
    )

    res = httpx.post(
        f"{BASE}/v1/feature-flags/eval",
        json={"flag_code": flag["code"], "context": {}},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["value"] == "disabled"
    assert data["reason"] == "flag_inactive"


@pytest.mark.integration
def test_eval_flag_env_override(auth_token, product_id):
    """Active flag with env override returns override value."""
    flag = _create_flag(
        auth_token, product_id,
        default_value=False,
        status="active",
    )
    # Set prod override to True
    httpx.put(
        f"{BASE}/v1/feature-flags/{flag['id']}/environments/prod",
        json={"enabled": True, "value": True},
        headers=_auth_headers(auth_token),
    )

    res = httpx.post(
        f"{BASE}/v1/feature-flags/eval",
        json={
            "flag_code": flag["code"],
            "context": {"environment": "prod"},
        },
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["value"] is True
    assert data["reason"] == "env_override"


@pytest.mark.integration
def test_eval_flag_env_disabled_returns_default(auth_token, product_id):
    """If env override has enabled=False, return default_value."""
    flag = _create_flag(
        auth_token, product_id,
        default_value=False,
        status="active",
    )
    httpx.put(
        f"{BASE}/v1/feature-flags/{flag['id']}/environments/staging",
        json={"enabled": False},
        headers=_auth_headers(auth_token),
    )

    res = httpx.post(
        f"{BASE}/v1/feature-flags/eval",
        json={
            "flag_code": flag["code"],
            "context": {"environment": "staging"},
        },
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["value"] is False
    assert data["reason"] == "env_disabled"


@pytest.mark.integration
def test_eval_flag_org_target(auth_token, product_id):
    """Org-scoped flag with a target returns target value for matching org."""
    flag = _create_flag(
        auth_token, product_id,
        scope_id=SCOPE_ORG,
        default_value=False,
        status="active",
    )
    fake_org_id = str(uuid.uuid4())
    httpx.post(
        f"{BASE}/v1/feature-flags/{flag['id']}/targets",
        json={"org_id": fake_org_id, "value": True},
        headers=_auth_headers(auth_token),
    )

    res = httpx.post(
        f"{BASE}/v1/feature-flags/eval",
        json={
            "flag_code": flag["code"],
            "context": {"org_id": fake_org_id},
        },
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["value"] is True
    assert data["reason"] == "org_target"


@pytest.mark.integration
def test_eval_flag_no_target_match_returns_default(auth_token, product_id):
    """Org-scoped flag without a matching target returns default."""
    flag = _create_flag(
        auth_token, product_id,
        scope_id=SCOPE_ORG,
        default_value=False,
        status="active",
    )

    res = httpx.post(
        f"{BASE}/v1/feature-flags/eval",
        json={
            "flag_code": flag["code"],
            "context": {"org_id": str(uuid.uuid4())},
        },
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["value"] is False
    assert data["reason"] == "default"


@pytest.mark.integration
def test_eval_flag_not_found(auth_token):
    res = httpx.post(
        f"{BASE}/v1/feature-flags/eval",
        json={"flag_code": "does.not.exist.at.all", "context": {}},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "FLAG_NOT_FOUND"


# ---------------------------------------------------------------------------
# Bootstrap endpoint
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_bootstrap_returns_active_flags(auth_token, product_id):
    # Create an active flag
    code = _unique_code()
    _create_flag(auth_token, product_id, code=code, status="active")

    res = httpx.get(
        f"{BASE}/v1/feature-flags/bootstrap",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert "flags" in data
    assert "total" in data
    flag_codes = [f["flag_code"] for f in data["flags"]]
    assert code in flag_codes


@pytest.mark.integration
def test_bootstrap_with_environment_returns_override(auth_token, product_id):
    """Bootstrap with environment applies env overrides."""
    code = _unique_code()
    flag = _create_flag(
        auth_token, product_id,
        code=code,
        status="active",
        default_value=False,
    )
    # Set prod override
    httpx.put(
        f"{BASE}/v1/feature-flags/{flag['id']}/environments/prod",
        json={"enabled": True, "value": True},
        headers=_auth_headers(auth_token),
    )

    res = httpx.get(
        f"{BASE}/v1/feature-flags/bootstrap",
        params={"environment": "prod"},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    flags_by_code = {f["flag_code"]: f for f in data["flags"]}
    assert code in flags_by_code
    assert flags_by_code[code]["value"] is True
    assert flags_by_code[code]["reason"] == "env_override"


@pytest.mark.integration
def test_bootstrap_draft_flag_not_included(auth_token, product_id):
    """Draft flags are not included in bootstrap."""
    code = _unique_code()
    _create_flag(auth_token, product_id, code=code, status="draft")

    res = httpx.get(
        f"{BASE}/v1/feature-flags/bootstrap",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    flag_codes = [f["flag_code"] for f in res.json()["data"]["flags"]]
    assert code not in flag_codes


# ---------------------------------------------------------------------------
# By-product endpoint
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_list_by_product(auth_token, product_id):
    _create_flag(auth_token, product_id)
    _create_flag(auth_token, product_id)

    res = httpx.get(
        f"{BASE}/v1/feature-flags/by-product/{product_id}",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["total"] >= 2


@pytest.mark.integration
def test_list_by_product_not_found(auth_token):
    res = httpx.get(
        f"{BASE}/v1/feature-flags/by-product/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "PRODUCT_NOT_FOUND"
