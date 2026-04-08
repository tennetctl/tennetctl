"""Integration tests for IAM users endpoints.

Requires:
  - Backend running at http://localhost:8000
  - First admin user: username=admin, password=ChangeMe123!

Run with:
  pytest tests/test_api_users.py -v -m integration
"""

import pytest
import httpx


BASE = "http://localhost:58000"
ADMIN_USER = "admin"
ADMIN_PASS = "ChangeMe123!"


def _access_token() -> str:
    res = httpx.post(
        f"{BASE}/v1/sessions",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
    )
    assert res.status_code == 201
    return res.json()["data"]["access_token"]


@pytest.mark.integration
def test_list_users_requires_auth():
    res = httpx.get(f"{BASE}/v1/users")
    assert res.status_code == 401


@pytest.mark.integration
def test_list_users():
    token = _access_token()
    res = httpx.get(
        f"{BASE}/v1/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    admin = next((u for u in data["items"] if u["username"] == ADMIN_USER), None)
    assert admin is not None
    assert admin["account_type"] == "default_admin"
    assert admin["is_active"] is True


@pytest.mark.integration
def test_get_user():
    token = _access_token()

    # Get list first to grab the user ID
    list_res = httpx.get(
        f"{BASE}/v1/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    user_id = list_res.json()["data"]["items"][0]["id"]

    res = httpx.get(
        f"{BASE}/v1/users/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["id"] == user_id


@pytest.mark.integration
def test_get_user_not_found():
    token = _access_token()
    res = httpx.get(
        f"{BASE}/v1/users/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "USER_NOT_FOUND"


@pytest.mark.integration
def test_patch_user_email():
    token = _access_token()

    # Get list to get user ID
    list_res = httpx.get(
        f"{BASE}/v1/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    user_id = list_res.json()["data"]["items"][0]["id"]

    new_email = "admin.test@example.com"
    res = httpx.patch(
        f"{BASE}/v1/users/{user_id}",
        json={"email": new_email},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["email"] == new_email

    # Restore original email
    httpx.patch(
        f"{BASE}/v1/users/{user_id}",
        json={"email": "admin@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
