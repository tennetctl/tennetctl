"""Integration tests for IAM memberships endpoints.

Requires:
  - Backend running at http://localhost:8000
  - First admin user: username=admin, password=ChangeMe123!

Run with:
  pytest tests/test_api_memberships.py -v -m integration
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


def _get_user_id(token: str) -> str:
    res = httpx.get(f"{BASE}/v1/sessions/me", headers=_auth_headers(token))
    assert res.status_code == 200
    return res.json()["data"]["user_id"]


def _create_org(token: str) -> dict:
    res = httpx.post(
        f"{BASE}/v1/orgs",
        json={
            "name": "Membership Test Org",
            "slug": f"mem-test-org-{uuid.uuid4().hex[:8]}",
            "owner_id": "",
        },
        headers=_auth_headers(token),
    )
    assert res.status_code == 201, f"Org create failed: {res.text}"
    return res.json()["data"]


def _create_workspace(token: str, org_id: str) -> dict:
    res = httpx.post(
        f"{BASE}/v1/workspaces",
        json={
            "org_id": org_id,
            "name": "Membership Test WS",
            "slug": f"mem-test-ws-{uuid.uuid4().hex[:8]}",
        },
        headers=_auth_headers(token),
    )
    assert res.status_code == 201, f"Workspace create failed: {res.text}"
    return res.json()["data"]


# ---------------------------------------------------------------------------
# Org memberships
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_add_user_to_org():
    session = _login()
    token = session["access_token"]
    user_id = _get_user_id(token)
    org = _create_org(token)

    res = httpx.post(
        f"{BASE}/v1/memberships/orgs",
        json={"user_id": user_id, "org_id": org["id"]},
        headers=_auth_headers(token),
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["user_id"] == user_id
    assert data["org_id"] == org["id"]


@pytest.mark.integration
def test_list_user_orgs():
    session = _login()
    token = session["access_token"]
    user_id = _get_user_id(token)

    res = httpx.get(
        f"{BASE}/v1/memberships/orgs",
        params={"user_id": user_id},
        headers=_auth_headers(token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert "items" in body["data"]
    assert "total" in body["data"]


@pytest.mark.integration
def test_remove_user_from_org():
    session = _login()
    token = session["access_token"]
    user_id = _get_user_id(token)
    org = _create_org(token)

    add_res = httpx.post(
        f"{BASE}/v1/memberships/orgs",
        json={"user_id": user_id, "org_id": org["id"]},
        headers=_auth_headers(token),
    )
    assert add_res.status_code == 201
    membership_id = add_res.json()["data"]["id"]

    del_res = httpx.delete(
        f"{BASE}/v1/memberships/orgs/{membership_id}",
        headers=_auth_headers(token),
    )
    assert del_res.status_code == 204, del_res.text


@pytest.mark.integration
def test_list_org_memberships_unauthenticated():
    res = httpx.get(f"{BASE}/v1/memberships/orgs", params={"user_id": "any"})
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Workspace memberships
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_add_user_to_workspace():
    session = _login()
    token = session["access_token"]
    user_id = _get_user_id(token)
    org = _create_org(token)
    ws = _create_workspace(token, org["id"])

    res = httpx.post(
        f"{BASE}/v1/memberships/workspaces",
        json={"user_id": user_id, "workspace_id": ws["id"], "org_id": org["id"]},
        headers=_auth_headers(token),
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["user_id"] == user_id
    assert data["workspace_id"] == ws["id"]


@pytest.mark.integration
def test_list_user_workspaces():
    session = _login()
    token = session["access_token"]
    user_id = _get_user_id(token)

    res = httpx.get(
        f"{BASE}/v1/memberships/workspaces",
        params={"user_id": user_id},
        headers=_auth_headers(token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert "items" in body["data"]


@pytest.mark.integration
def test_remove_user_from_workspace():
    session = _login()
    token = session["access_token"]
    user_id = _get_user_id(token)
    org = _create_org(token)
    ws = _create_workspace(token, org["id"])

    add_res = httpx.post(
        f"{BASE}/v1/memberships/workspaces",
        json={"user_id": user_id, "workspace_id": ws["id"], "org_id": org["id"]},
        headers=_auth_headers(token),
    )
    assert add_res.status_code == 201
    membership_id = add_res.json()["data"]["id"]

    del_res = httpx.delete(
        f"{BASE}/v1/memberships/workspaces/{membership_id}",
        headers=_auth_headers(token),
    )
    assert del_res.status_code == 204, del_res.text


@pytest.mark.integration
def test_list_workspace_memberships_unauthenticated():
    res = httpx.get(f"{BASE}/v1/memberships/workspaces", params={"user_id": "any"})
    assert res.status_code == 401
