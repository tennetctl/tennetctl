"""Integration tests for IAM orgs endpoints.

Requires:
  - Backend running at http://localhost:8000
  - First admin user: username=admin, password=ChangeMe123!

Run with:
  pytest tests/test_api_orgs.py -v -m integration
"""

import uuid

import httpx
import pytest

BASE = "http://localhost:58000"
ADMIN_USER = "admin"
ADMIN_PASS = "ChangeMe123!"


def _login() -> dict:
    res = httpx.post(
        f"{BASE}/v1/sessions",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
    )
    assert res.status_code == 201, f"Login failed: {res.text}"
    return res.json()["data"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _unique_slug() -> str:
    return f"test-org-{uuid.uuid4().hex[:8]}"


@pytest.mark.integration
def test_create_org():
    session = _login()
    token = session["access_token"]
    slug = _unique_slug()

    res = httpx.post(
        f"{BASE}/v1/orgs",
        json={"name": "Test Org", "slug": slug, "owner_id": ""},
        headers=_auth_headers(token),
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["slug"] == slug
    assert data["name"] == "Test Org"
    assert data["status"] == "active"
    assert data["is_active"] is True


@pytest.mark.integration
def test_list_orgs():
    session = _login()
    token = session["access_token"]

    res = httpx.get(f"{BASE}/v1/orgs", headers=_auth_headers(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


@pytest.mark.integration
def test_list_orgs_filter_active():
    session = _login()
    token = session["access_token"]

    res = httpx.get(
        f"{BASE}/v1/orgs",
        params={"is_active": "true"},
        headers=_auth_headers(token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    for item in body["data"]["items"]:
        assert item["is_active"] is True


@pytest.mark.integration
def test_get_org():
    session = _login()
    token = session["access_token"]
    slug = _unique_slug()

    create_res = httpx.post(
        f"{BASE}/v1/orgs",
        json={"name": "Get Org Test", "slug": slug, "owner_id": ""},
        headers=_auth_headers(token),
    )
    assert create_res.status_code == 201
    org_id = create_res.json()["data"]["id"]

    res = httpx.get(f"{BASE}/v1/orgs/{org_id}", headers=_auth_headers(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["id"] == org_id


@pytest.mark.integration
def test_get_org_not_found():
    session = _login()
    token = session["access_token"]

    res = httpx.get(
        f"{BASE}/v1/orgs/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(token),
    )
    assert res.status_code == 404
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "ORG_NOT_FOUND"


@pytest.mark.integration
def test_update_org():
    session = _login()
    token = session["access_token"]
    slug = _unique_slug()

    create_res = httpx.post(
        f"{BASE}/v1/orgs",
        json={"name": "Before Update", "slug": slug, "owner_id": ""},
        headers=_auth_headers(token),
    )
    assert create_res.status_code == 201
    org_id = create_res.json()["data"]["id"]

    new_name = f"After Update {uuid.uuid4().hex[:4]}"
    res = httpx.patch(
        f"{BASE}/v1/orgs/{org_id}",
        json={"name": new_name},
        headers=_auth_headers(token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["name"] == new_name


@pytest.mark.integration
def test_delete_org_not_allowed():
    """DELETE /v1/orgs/{id} must not exist — orgs are permanent."""
    session = _login()
    token = session["access_token"]

    res = httpx.delete(
        f"{BASE}/v1/orgs/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(token),
    )
    assert res.status_code == 405, f"Expected 405 Method Not Allowed, got {res.status_code}"


@pytest.mark.integration
def test_list_orgs_unauthenticated():
    res = httpx.get(f"{BASE}/v1/orgs")
    assert res.status_code == 401
