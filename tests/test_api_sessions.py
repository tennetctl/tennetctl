"""Integration tests for IAM session (auth) endpoints.

Requires:
  - Backend running at http://localhost:8000
  - First admin user: username=admin, password=ChangeMe123!

Run with:
  pytest tests/test_api_sessions.py -v -m integration
"""

import pytest
import httpx


BASE = "http://localhost:8000"
ADMIN_USER = "admin"
ADMIN_PASS = "ChangeMe123!"


def _login() -> dict:
    res = httpx.post(
        f"{BASE}/v1/sessions",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
    )
    assert res.status_code == 201, f"Login failed: {res.text}"
    body = res.json()
    assert body["ok"] is True
    return body["data"]


@pytest.mark.integration
def test_login_success():
    data = _login()
    assert "access_token" in data
    assert "refresh_token" in data
    assert "session_id" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 900


@pytest.mark.integration
def test_login_wrong_password():
    res = httpx.post(
        f"{BASE}/v1/sessions",
        json={"username": ADMIN_USER, "password": "wrong"},
    )
    assert res.status_code == 401
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.integration
def test_login_unknown_user():
    res = httpx.post(
        f"{BASE}/v1/sessions",
        json={"username": "nobody", "password": "whatever"},
    )
    assert res.status_code == 401


@pytest.mark.integration
def test_me_authenticated():
    data = _login()
    token = data["access_token"]
    res = httpx.get(
        f"{BASE}/v1/sessions/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["username"] == ADMIN_USER
    assert body["data"]["account_type"] == "default_admin"


@pytest.mark.integration
def test_me_unauthenticated():
    res = httpx.get(f"{BASE}/v1/sessions/me")
    assert res.status_code == 401
    body = res.json()
    assert body["ok"] is False


@pytest.mark.integration
def test_me_invalid_token():
    res = httpx.get(
        f"{BASE}/v1/sessions/me",
        headers={"Authorization": "Bearer not.a.real.token"},
    )
    assert res.status_code == 401


@pytest.mark.integration
def test_refresh_token():
    data = _login()
    session_id = data["session_id"]
    refresh_token = data["refresh_token"]

    res = httpx.patch(
        f"{BASE}/v1/sessions/{session_id}",
        json={"refresh_token": refresh_token},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    new_data = body["data"]
    assert "access_token" in new_data
    assert new_data["access_token"] != data["access_token"]
    assert new_data["refresh_token"] != data["refresh_token"]


@pytest.mark.integration
def test_refresh_wrong_token():
    data = _login()
    session_id = data["session_id"]

    res = httpx.patch(
        f"{BASE}/v1/sessions/{session_id}",
        json={"refresh_token": "wrong_token"},
    )
    assert res.status_code == 401
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "INVALID_REFRESH_TOKEN"


@pytest.mark.integration
def test_logout():
    data = _login()
    token = data["access_token"]
    session_id = data["session_id"]

    res = httpx.delete(
        f"{BASE}/v1/sessions/{session_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 204
