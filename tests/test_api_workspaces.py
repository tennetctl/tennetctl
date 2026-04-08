"""Integration tests for IAM workspaces endpoints.

Requires:
  - Backend running at http://localhost:8000
  - First admin user: username=admin, password=ChangeMe123!
  - At least one org created (setup wizard creates tennetctl org)

Run with:
  pytest tests/test_api_workspaces.py -v -m integration
"""

import uuid

import httpx
import pytest

BASE = "http://localhost:8000"
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
    return f"test-ws-{uuid.uuid4().hex[:8]}"


def _create_org(token: str) -> dict:
    res = httpx.post(
        f"{BASE}/v1/orgs",
        json={"name": "Workspace Test Org", "slug": f"ws-test-org-{uuid.uuid4().hex[:8]}", "owner_id": ""},
        headers=_auth_headers(token),
    )
    assert res.status_code == 201, f"Org create failed: {res.text}"
    return res.json()["data"]


@pytest.mark.integration
def test_create_workspace():
    session = _login()
    token = session["access_token"]
    org = _create_org(token)
    slug = _unique_slug()

    res = httpx.post(
        f"{BASE}/v1/workspaces",
        json={"org_id": org["id"], "name": "Test Workspace", "slug": slug},
        headers=_auth_headers(token),
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["org_id"] == org["id"]
    assert data["slug"] == slug
    assert data["name"] == "Test Workspace"
    assert data["status"] == "active"


@pytest.mark.integration
def test_create_workspace_slug_conflict():
    session = _login()
    token = session["access_token"]
    org = _create_org(token)
    slug = _unique_slug()

    res1 = httpx.post(
        f"{BASE}/v1/workspaces",
        json={"org_id": org["id"], "name": "First", "slug": slug},
        headers=_auth_headers(token),
    )
    assert res1.status_code == 201

    res2 = httpx.post(
        f"{BASE}/v1/workspaces",
        json={"org_id": org["id"], "name": "Second", "slug": slug},
        headers=_auth_headers(token),
    )
    assert res2.status_code == 409, res2.text
    body = res2.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "WORKSPACE_SLUG_CONFLICT"


@pytest.mark.integration
def test_same_slug_different_orgs_allowed():
    """Same slug is fine if it's in a different org."""
    session = _login()
    token = session["access_token"]
    org1 = _create_org(token)
    org2 = _create_org(token)
    slug = _unique_slug()

    res1 = httpx.post(
        f"{BASE}/v1/workspaces",
        json={"org_id": org1["id"], "name": "WS1", "slug": slug},
        headers=_auth_headers(token),
    )
    assert res1.status_code == 201

    res2 = httpx.post(
        f"{BASE}/v1/workspaces",
        json={"org_id": org2["id"], "name": "WS2", "slug": slug},
        headers=_auth_headers(token),
    )
    assert res2.status_code == 201, res2.text


@pytest.mark.integration
def test_list_workspaces():
    session = _login()
    token = session["access_token"]

    res = httpx.get(f"{BASE}/v1/workspaces", headers=_auth_headers(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert "items" in data
    assert "total" in data


@pytest.mark.integration
def test_list_workspaces_filter_by_org():
    session = _login()
    token = session["access_token"]
    org = _create_org(token)
    slug = _unique_slug()

    httpx.post(
        f"{BASE}/v1/workspaces",
        json={"org_id": org["id"], "name": "Filtered WS", "slug": slug},
        headers=_auth_headers(token),
    )

    res = httpx.get(
        f"{BASE}/v1/workspaces",
        params={"org_id": org["id"]},
        headers=_auth_headers(token),
    )
    assert res.status_code == 200
    body = res.json()
    for item in body["data"]["items"]:
        assert item["org_id"] == org["id"]


@pytest.mark.integration
def test_get_workspace():
    session = _login()
    token = session["access_token"]
    org = _create_org(token)

    create_res = httpx.post(
        f"{BASE}/v1/workspaces",
        json={"org_id": org["id"], "name": "Get WS", "slug": _unique_slug()},
        headers=_auth_headers(token),
    )
    assert create_res.status_code == 201
    ws_id = create_res.json()["data"]["id"]

    res = httpx.get(f"{BASE}/v1/workspaces/{ws_id}", headers=_auth_headers(token))
    assert res.status_code == 200
    body = res.json()
    assert body["data"]["id"] == ws_id


@pytest.mark.integration
def test_get_workspace_not_found():
    session = _login()
    token = session["access_token"]

    res = httpx.get(
        f"{BASE}/v1/workspaces/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(token),
    )
    assert res.status_code == 404
    body = res.json()
    assert body["error"]["code"] == "WORKSPACE_NOT_FOUND"


@pytest.mark.integration
def test_update_workspace():
    session = _login()
    token = session["access_token"]
    org = _create_org(token)

    create_res = httpx.post(
        f"{BASE}/v1/workspaces",
        json={"org_id": org["id"], "name": "Old Name", "slug": _unique_slug()},
        headers=_auth_headers(token),
    )
    ws_id = create_res.json()["data"]["id"]

    new_name = f"New Name {uuid.uuid4().hex[:4]}"
    res = httpx.patch(
        f"{BASE}/v1/workspaces/{ws_id}",
        json={"name": new_name},
        headers=_auth_headers(token),
    )
    assert res.status_code == 200
    assert res.json()["data"]["name"] == new_name


@pytest.mark.integration
def test_list_workspaces_unauthenticated():
    res = httpx.get(f"{BASE}/v1/workspaces")
    assert res.status_code == 401
