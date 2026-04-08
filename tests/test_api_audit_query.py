"""Integration tests for audit query endpoints.

GET  /v1/audit/events       — list events
GET  /v1/audit/events/{id}  — get single event

Requires:
  - Backend running at http://localhost:8000
  - First admin user: username=admin, password=ChangeMe123!
  - At least a login event present (login itself generates one)

Run with:
  pytest tests/test_api_audit_query.py -v -m integration
"""

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


@pytest.mark.integration
def test_list_events_requires_auth():
    res = httpx.get(f"{BASE}/v1/audit/events")
    assert res.status_code == 401


@pytest.mark.integration
def test_list_events_returns_page():
    session = _login()
    token = session["access_token"]

    res = httpx.get(f"{BASE}/v1/audit/events", headers=_auth_headers(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert isinstance(data["items"], list)
    assert data["total"] >= 1  # at least the login we just did


@pytest.mark.integration
def test_list_events_item_shape():
    session = _login()
    token = session["access_token"]

    res = httpx.get(
        f"{BASE}/v1/audit/events",
        params={"limit": 1},
        headers=_auth_headers(token),
    )
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    assert len(items) >= 1
    event = items[0]
    assert "id" in event
    assert "category" in event
    assert "action" in event
    assert "outcome" in event
    assert "created_at" in event


@pytest.mark.integration
def test_list_events_filter_by_user():
    session = _login()
    token = session["access_token"]

    # Get our own user_id
    me_res = httpx.get(f"{BASE}/v1/sessions/me", headers=_auth_headers(token))
    user_id = me_res.json()["data"]["user_id"]

    res = httpx.get(
        f"{BASE}/v1/audit/events",
        params={"user_id": user_id},
        headers=_auth_headers(token),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["data"]["total"] >= 1
    for item in body["data"]["items"]:
        assert item["user_id"] == user_id


@pytest.mark.integration
def test_list_events_filter_by_session():
    session = _login()
    token = session["access_token"]
    session_id = session["session_id"]

    res = httpx.get(
        f"{BASE}/v1/audit/events",
        params={"session_id": session_id},
        headers=_auth_headers(token),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["data"]["total"] >= 1
    for item in body["data"]["items"]:
        assert item["session_id"] == session_id


@pytest.mark.integration
def test_list_events_filter_by_category():
    session = _login()
    token = session["access_token"]

    res = httpx.get(
        f"{BASE}/v1/audit/events",
        params={"category": "iam"},
        headers=_auth_headers(token),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["data"]["total"] >= 1
    for item in body["data"]["items"]:
        assert item["category"] == "iam"


@pytest.mark.integration
def test_list_events_filter_by_action():
    session = _login()
    token = session["access_token"]

    res = httpx.get(
        f"{BASE}/v1/audit/events",
        params={"action": "session.login"},
        headers=_auth_headers(token),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["data"]["total"] >= 1
    for item in body["data"]["items"]:
        assert item["action"] == "session.login"


@pytest.mark.integration
def test_list_events_filter_by_outcome():
    session = _login()
    token = session["access_token"]

    res = httpx.get(
        f"{BASE}/v1/audit/events",
        params={"outcome": "success"},
        headers=_auth_headers(token),
    )
    assert res.status_code == 200
    body = res.json()
    for item in body["data"]["items"]:
        assert item["outcome"] == "success"


@pytest.mark.integration
def test_list_events_pagination():
    session = _login()
    token = session["access_token"]

    res_p1 = httpx.get(
        f"{BASE}/v1/audit/events",
        params={"limit": 1, "offset": 0},
        headers=_auth_headers(token),
    )
    res_p2 = httpx.get(
        f"{BASE}/v1/audit/events",
        params={"limit": 1, "offset": 1},
        headers=_auth_headers(token),
    )
    assert res_p1.status_code == 200
    assert res_p2.status_code == 200

    ids_p1 = [e["id"] for e in res_p1.json()["data"]["items"]]
    ids_p2 = [e["id"] for e in res_p2.json()["data"]["items"]]
    # Pages must not overlap
    assert not set(ids_p1) & set(ids_p2)


@pytest.mark.integration
def test_get_event_by_id():
    session = _login()
    token = session["access_token"]

    # Grab first event from the list
    list_res = httpx.get(
        f"{BASE}/v1/audit/events",
        params={"limit": 1},
        headers=_auth_headers(token),
    )
    event_id = list_res.json()["data"]["items"][0]["id"]

    res = httpx.get(
        f"{BASE}/v1/audit/events/{event_id}",
        headers=_auth_headers(token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["id"] == event_id


@pytest.mark.integration
def test_get_event_not_found():
    session = _login()
    token = session["access_token"]

    res = httpx.get(
        f"{BASE}/v1/audit/events/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(token),
    )
    assert res.status_code == 404
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "AUDIT_EVENT_NOT_FOUND"


@pytest.mark.integration
def test_login_generates_audit_event():
    """A fresh login must produce a session.login audit event."""
    session = _login()
    token = session["access_token"]
    session_id = session["session_id"]

    res = httpx.get(
        f"{BASE}/v1/audit/events",
        params={"session_id": session_id, "action": "session.login"},
        headers=_auth_headers(token),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["data"]["total"] >= 1
    event = body["data"]["items"][0]
    assert event["action"] == "session.login"
    assert event["outcome"] == "success"
    assert event["session_id"] == session_id
