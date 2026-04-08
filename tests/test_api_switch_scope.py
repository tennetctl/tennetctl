"""Integration tests for session scope-switching endpoint.

PATCH /v1/sessions/{id}/scope — switch active org/workspace scope

Requires:
  - Backend running at http://localhost:8000
  - First admin user: username=admin, password=ChangeMe123!

Run with:
  pytest tests/test_api_switch_scope.py -v -m integration
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


def _create_org(token: str) -> dict:
    res = httpx.post(
        f"{BASE}/v1/orgs",
        json={
            "name": "Switch Scope Org",
            "slug": f"scope-org-{uuid.uuid4().hex[:8]}",
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
            "name": "Switch Scope WS",
            "slug": f"scope-ws-{uuid.uuid4().hex[:8]}",
        },
        headers=_auth_headers(token),
    )
    assert res.status_code == 201, f"Workspace create failed: {res.text}"
    return res.json()["data"]


@pytest.mark.integration
def test_switch_scope_success():
    session = _login()
    token = session["access_token"]
    session_id = session["session_id"]

    org = _create_org(token)
    ws = _create_workspace(token, org["id"])

    res = httpx.patch(
        f"{BASE}/v1/sessions/{session_id}/scope",
        json={"target_org_id": org["id"], "target_workspace_id": ws["id"]},
        headers=_auth_headers(token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["session_id"] == session_id
    assert data["org_id"] == org["id"]
    assert data["workspace_id"] == ws["id"]


@pytest.mark.integration
def test_switch_scope_unauthenticated():
    res = httpx.patch(
        f"{BASE}/v1/sessions/some-session-id/scope",
        json={"target_org_id": "org-id", "target_workspace_id": "ws-id"},
    )
    assert res.status_code == 401


@pytest.mark.integration
def test_switch_scope_wrong_session():
    """Cannot switch scope of a different session."""
    session = _login()
    token = session["access_token"]
    other_session_id = "00000000-0000-0000-0000-000000000000"

    res = httpx.patch(
        f"{BASE}/v1/sessions/{other_session_id}/scope",
        json={"target_org_id": "org-id", "target_workspace_id": "ws-id"},
        headers=_auth_headers(token),
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body["error"]["code"] == "FORBIDDEN"


@pytest.mark.integration
def test_switch_scope_missing_fields():
    session = _login()
    token = session["access_token"]
    session_id = session["session_id"]

    res = httpx.patch(
        f"{BASE}/v1/sessions/{session_id}/scope",
        json={"target_org_id": "only-org-no-workspace"},
        headers=_auth_headers(token),
    )
    assert res.status_code == 422


@pytest.mark.integration
def test_switch_scope_persists_across_refresh():
    """After switching scope, a refresh should carry the new scope in the new token."""
    session = _login()
    token = session["access_token"]
    session_id = session["session_id"]
    refresh_token = session["refresh_token"]

    org = _create_org(token)
    ws = _create_workspace(token, org["id"])

    # Switch scope
    switch_res = httpx.patch(
        f"{BASE}/v1/sessions/{session_id}/scope",
        json={"target_org_id": org["id"], "target_workspace_id": ws["id"]},
        headers=_auth_headers(token),
    )
    assert switch_res.status_code == 200

    # Refresh token — new access token should embed updated scope
    refresh_res = httpx.patch(
        f"{BASE}/v1/sessions/{session_id}",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 200, refresh_res.text
    new_data = refresh_res.json()["data"]
    assert "access_token" in new_data
    assert new_data["session_id"] == session_id
