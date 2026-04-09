"""Integration tests for IAM feature registry endpoints.

POST   /v1/features              create feature
GET    /v1/features              list features (?product_id=&scope_id=&category_id=)
GET    /v1/features/{id}         get feature
PATCH  /v1/features/{id}         update feature
DELETE /v1/features/{id}         soft-delete feature
GET    /v1/features/{id}/children  list child features

Requires:
  - Backend running at http://localhost:58000
  - First admin user: username=admin, password=ChangeMe123!
"""

import uuid

import httpx
import pytest

BASE = "http://localhost:58000"
ADMIN_USER = "admin"
ADMIN_PASS = "ChangeMe123!"


# ---------------------------------------------------------------------------
# Module-scoped session fixture — one login for the entire test module
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def auth_token() -> str:
    """Login once per module run; return the access token."""
    res = httpx.post(
        f"{BASE}/v1/sessions",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
    )
    assert res.status_code == 201, f"Login failed: {res.text}"
    return res.json()["data"]["access_token"]


@pytest.fixture(scope="module")
def test_product_id(auth_token) -> str:
    """Create a test product for feature tests and return its ID."""
    # Get product category
    res_cats = httpx.get(
        f"{BASE}/v1/categories",
        params={"category_type": "product"},
        headers=_auth_headers(auth_token),
    )
    assert res_cats.status_code == 200
    product_cat_id = res_cats.json()["data"]["items"][0]["id"]

    code = f"test-feat-prod-{uuid.uuid4().hex[:8]}"
    res = httpx.post(
        f"{BASE}/v1/products",
        json={"code": code, "name": "Feature Test Product", "category_id": product_cat_id},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 201, f"Product create failed: {res.text}"
    return res.json()["data"]["id"]


@pytest.fixture(scope="module")
def scope_id(auth_token) -> int:
    """Return the scope_id for 'platform'."""
    res = httpx.get(f"{BASE}/v1/scopes")
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    platform = next((s for s in items if s["code"] == "platform"), None)
    assert platform is not None
    return platform["id"]


@pytest.fixture(scope="module")
def feature_category_id(auth_token) -> int:
    """Return the category_id for feature category 'iam'."""
    res = httpx.get(f"{BASE}/v1/categories", params={"category_type": "feature"})
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    iam_cat = next((c for c in items if c["code"] == "iam"), None)
    assert iam_cat is not None
    return iam_cat["id"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _unique_code() -> str:
    return f"test-feat-{uuid.uuid4().hex[:8]}"


def _create_feature(token: str, product_id: str, scope_id: int, category_id: int, code: str | None = None) -> dict:
    res = httpx.post(
        f"{BASE}/v1/features",
        json={
            "product_id": product_id,
            "code": code or _unique_code(),
            "name": "Test Feature",
            "scope_id": scope_id,
            "category_id": category_id,
        },
        headers=_auth_headers(token),
    )
    assert res.status_code == 201, f"Feature create failed: {res.text}"
    return res.json()["data"]


# ---------------------------------------------------------------------------
# Create feature
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_create_feature_success(auth_token, test_product_id, scope_id, feature_category_id):
    code = _unique_code()
    res = httpx.post(
        f"{BASE}/v1/features",
        json={
            "product_id": test_product_id,
            "code": code,
            "name": "My Feature",
            "scope_id": scope_id,
            "category_id": feature_category_id,
            "description": "A test feature",
        },
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["code"] == code
    assert data["name"] == "My Feature"
    assert data["product_id"] == test_product_id
    assert data["scope_id"] == scope_id
    assert data["category_id"] == feature_category_id
    assert data["is_active"] is True
    assert data["is_deleted"] is False
    assert data["description"] == "A test feature"
    assert data["parent_id"] is None
    assert "id" in data


@pytest.mark.integration
def test_create_feature_requires_auth(test_product_id, scope_id, feature_category_id):
    res = httpx.post(
        f"{BASE}/v1/features",
        json={
            "product_id": test_product_id,
            "code": _unique_code(),
            "name": "Unauth Feature",
            "scope_id": scope_id,
            "category_id": feature_category_id,
        },
    )
    assert res.status_code == 401


@pytest.mark.integration
def test_create_feature_duplicate_code_in_same_product_returns_409(auth_token, test_product_id, scope_id, feature_category_id):
    code = _unique_code()

    # Create first time
    res1 = httpx.post(
        f"{BASE}/v1/features",
        json={"product_id": test_product_id, "code": code, "name": "F1", "scope_id": scope_id, "category_id": feature_category_id},
        headers=_auth_headers(auth_token),
    )
    assert res1.status_code == 201

    # Duplicate
    res2 = httpx.post(
        f"{BASE}/v1/features",
        json={"product_id": test_product_id, "code": code, "name": "F2", "scope_id": scope_id, "category_id": feature_category_id},
        headers=_auth_headers(auth_token),
    )
    assert res2.status_code == 409, res2.text
    assert res2.json()["error"]["code"] == "FEATURE_CODE_CONFLICT"


@pytest.mark.integration
def test_create_feature_invalid_category_type_returns_422(auth_token, test_product_id, scope_id):
    # Use a product category for a feature — wrong type
    res_cats = httpx.get(f"{BASE}/v1/categories", params={"category_type": "product"})
    prod_cat_id = res_cats.json()["data"]["items"][0]["id"]

    res = httpx.post(
        f"{BASE}/v1/features",
        json={
            "product_id": test_product_id,
            "code": _unique_code(),
            "name": "Bad Cat Feature",
            "scope_id": scope_id,
            "category_id": prod_cat_id,
        },
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 422, res.text
    assert res.json()["error"]["code"] == "INVALID_CATEGORY"


@pytest.mark.integration
def test_create_feature_invalid_product_returns_404(auth_token, scope_id, feature_category_id):
    res = httpx.post(
        f"{BASE}/v1/features",
        json={
            "product_id": "00000000-0000-0000-0000-000000000000",
            "code": _unique_code(),
            "name": "Orphan Feature",
            "scope_id": scope_id,
            "category_id": feature_category_id,
        },
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404, res.text
    assert res.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


@pytest.mark.integration
def test_create_child_feature_success(auth_token, test_product_id, scope_id, feature_category_id):
    parent = _create_feature(auth_token, test_product_id, scope_id, feature_category_id)

    res = httpx.post(
        f"{BASE}/v1/features",
        json={
            "product_id": test_product_id,
            "code": _unique_code(),
            "name": "Child Feature",
            "scope_id": scope_id,
            "category_id": feature_category_id,
            "parent_id": parent["id"],
        },
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["parent_id"] == parent["id"]


# ---------------------------------------------------------------------------
# List features
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_list_features_returns_results(auth_token, test_product_id, scope_id, feature_category_id):
    # Create a feature to ensure there's at least one
    _create_feature(auth_token, test_product_id, scope_id, feature_category_id)

    res = httpx.get(f"{BASE}/v1/features", headers=_auth_headers(auth_token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


@pytest.mark.integration
def test_list_features_filter_by_product(auth_token, test_product_id, scope_id, feature_category_id):
    feature = _create_feature(auth_token, test_product_id, scope_id, feature_category_id)

    res = httpx.get(
        f"{BASE}/v1/features",
        params={"product_id": test_product_id},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    items = res.json()["data"]["items"]
    assert any(i["id"] == feature["id"] for i in items)
    for i in items:
        assert i["product_id"] == test_product_id


@pytest.mark.integration
def test_list_features_filter_by_scope(auth_token, test_product_id, scope_id, feature_category_id):
    res = httpx.get(
        f"{BASE}/v1/features",
        params={"scope_id": scope_id},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    items = res.json()["data"]["items"]
    for i in items:
        assert i["scope_id"] == scope_id


@pytest.mark.integration
def test_list_features_requires_auth():
    res = httpx.get(f"{BASE}/v1/features")
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Get feature
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_get_feature_found(auth_token, test_product_id, scope_id, feature_category_id):
    feature = _create_feature(auth_token, test_product_id, scope_id, feature_category_id)

    res = httpx.get(f"{BASE}/v1/features/{feature['id']}", headers=_auth_headers(auth_token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["id"] == feature["id"]
    assert body["data"]["scope_code"] == "platform"


@pytest.mark.integration
def test_get_feature_not_found(auth_token):
    res = httpx.get(
        f"{BASE}/v1/features/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404, res.text
    assert res.json()["error"]["code"] == "FEATURE_NOT_FOUND"


# ---------------------------------------------------------------------------
# Update feature
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_update_feature_success(auth_token, test_product_id, scope_id, feature_category_id):
    feature = _create_feature(auth_token, test_product_id, scope_id, feature_category_id)

    res = httpx.patch(
        f"{BASE}/v1/features/{feature['id']}",
        json={"name": "Updated Feature Name", "description": "New desc", "status": "stable"},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["name"] == "Updated Feature Name"
    assert data["description"] == "New desc"
    assert data["status"] == "stable"


@pytest.mark.integration
def test_update_feature_not_found(auth_token):
    res = httpx.patch(
        f"{BASE}/v1/features/00000000-0000-0000-0000-000000000000",
        json={"name": "Nope"},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404, res.text
    assert res.json()["error"]["code"] == "FEATURE_NOT_FOUND"


# ---------------------------------------------------------------------------
# Delete feature
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_delete_feature_success(auth_token, test_product_id, scope_id, feature_category_id):
    feature = _create_feature(auth_token, test_product_id, scope_id, feature_category_id)

    res = httpx.delete(f"{BASE}/v1/features/{feature['id']}", headers=_auth_headers(auth_token))
    assert res.status_code == 204, res.text


@pytest.mark.integration
def test_delete_feature_idempotent(auth_token, test_product_id, scope_id, feature_category_id):
    feature = _create_feature(auth_token, test_product_id, scope_id, feature_category_id)

    res1 = httpx.delete(f"{BASE}/v1/features/{feature['id']}", headers=_auth_headers(auth_token))
    assert res1.status_code == 204

    res2 = httpx.delete(f"{BASE}/v1/features/{feature['id']}", headers=_auth_headers(auth_token))
    assert res2.status_code == 204


@pytest.mark.integration
def test_delete_feature_not_found(auth_token):
    res = httpx.delete(
        f"{BASE}/v1/features/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "FEATURE_NOT_FOUND"


# ---------------------------------------------------------------------------
# Children
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_list_children_empty(auth_token, test_product_id, scope_id, feature_category_id):
    parent = _create_feature(auth_token, test_product_id, scope_id, feature_category_id)

    res = httpx.get(f"{BASE}/v1/features/{parent['id']}/children", headers=_auth_headers(auth_token))
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.integration
def test_list_children_with_children(auth_token, test_product_id, scope_id, feature_category_id):
    parent = _create_feature(auth_token, test_product_id, scope_id, feature_category_id)

    # Create child
    httpx.post(
        f"{BASE}/v1/features",
        json={
            "product_id": test_product_id,
            "code": _unique_code(),
            "name": "Child",
            "scope_id": scope_id,
            "category_id": feature_category_id,
            "parent_id": parent["id"],
        },
        headers=_auth_headers(auth_token),
    )

    res = httpx.get(f"{BASE}/v1/features/{parent['id']}/children", headers=_auth_headers(auth_token))
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["parent_id"] == parent["id"]


@pytest.mark.integration
def test_list_children_feature_not_found(auth_token):
    res = httpx.get(
        f"{BASE}/v1/features/00000000-0000-0000-0000-000000000000/children",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404, res.text
    assert res.json()["error"]["code"] == "FEATURE_NOT_FOUND"
