"""Integration tests for IAM groups endpoints.

POST   /v1/groups                          create group (org-scoped)
GET    /v1/groups                          list groups (filter by org_id)
GET    /v1/groups/{id}                     get group
PATCH  /v1/groups/{id}                     update group (name/slug/description)
DELETE /v1/groups/{id}                     soft-delete group

POST   /v1/groups/{id}/members             add user to group
GET    /v1/groups/{id}/members             list members
DELETE /v1/groups/{id}/members/{user_id}   remove member

Requires:
  - Backend running at http://localhost:8000
  - First admin user: username=admin, password=ChangeMe123!

Run with:
  pytest tests/test_api_groups.py -v -m integration
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


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _unique_slug() -> str:
    return f"test-grp-{uuid.uuid4().hex[:8]}"


def _get_user_id(token: str) -> str:
    res = httpx.get(f"{BASE}/v1/sessions/me", headers=_auth_headers(token))
    assert res.status_code == 200
    return res.json()["data"]["user_id"]


def _create_org(token: str) -> dict:
    res = httpx.post(
        f"{BASE}/v1/orgs",
        json={
            "name": f"Group Test Org {uuid.uuid4().hex[:6]}",
            "slug": f"grp-test-org-{uuid.uuid4().hex[:8]}",
            "owner_id": "",
        },
        headers=_auth_headers(token),
    )
    assert res.status_code == 201, f"Org create failed: {res.text}"
    return res.json()["data"]


def _create_group(token: str, org_id: str, slug: str | None = None) -> dict:
    res = httpx.post(
        f"{BASE}/v1/groups",
        json={
            "name": "Test Group",
            "slug": slug or _unique_slug(),
            "org_id": org_id,
        },
        headers=_auth_headers(token),
    )
    assert res.status_code == 201, f"Group create failed: {res.text}"
    return res.json()["data"]


# ---------------------------------------------------------------------------
# Create group
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_create_group_success(auth_token):
    org = _create_org(auth_token)
    slug = _unique_slug()

    res = httpx.post(
        f"{BASE}/v1/groups",
        json={"name": "My Group", "slug": slug, "org_id": org["id"]},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["name"] == "My Group"
    assert data["slug"] == slug
    assert data["org_id"] == org["id"]
    assert data["is_system"] is False
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.integration
def test_create_group_with_description(auth_token):
    org = _create_org(auth_token)

    res = httpx.post(
        f"{BASE}/v1/groups",
        json={
            "name": "Group With Desc",
            "slug": _unique_slug(),
            "org_id": org["id"],
            "description": "A test description",
        },
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["description"] == "A test description"


@pytest.mark.integration
def test_create_group_duplicate_slug_same_org_returns_409(auth_token):
    org = _create_org(auth_token)
    slug = _unique_slug()

    # Create first time
    res1 = httpx.post(
        f"{BASE}/v1/groups",
        json={"name": "Group 1", "slug": slug, "org_id": org["id"]},
        headers=_auth_headers(auth_token),
    )
    assert res1.status_code == 201

    # Create duplicate slug in same org — should 409
    res2 = httpx.post(
        f"{BASE}/v1/groups",
        json={"name": "Group 2", "slug": slug, "org_id": org["id"]},
        headers=_auth_headers(auth_token),
    )
    assert res2.status_code == 409, res2.text
    body = res2.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "GROUP_SLUG_CONFLICT"


@pytest.mark.integration
def test_create_group_same_slug_different_org_ok(auth_token):
    org1 = _create_org(auth_token)
    org2 = _create_org(auth_token)
    slug = _unique_slug()

    res1 = httpx.post(
        f"{BASE}/v1/groups",
        json={"name": "Group A", "slug": slug, "org_id": org1["id"]},
        headers=_auth_headers(auth_token),
    )
    assert res1.status_code == 201

    # Same slug, different org — OK
    res2 = httpx.post(
        f"{BASE}/v1/groups",
        json={"name": "Group B", "slug": slug, "org_id": org2["id"]},
        headers=_auth_headers(auth_token),
    )
    assert res2.status_code == 201, res2.text


@pytest.mark.integration
def test_create_group_missing_org_id_returns_422(auth_token):

    res = httpx.post(
        f"{BASE}/v1/groups",
        json={"name": "No Org Group", "slug": _unique_slug()},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 422


@pytest.mark.integration
def test_create_group_unauthenticated(auth_token):
    res = httpx.post(
        f"{BASE}/v1/groups",
        json={"name": "Unauth Group", "slug": _unique_slug(), "org_id": "any"},
    )
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# List groups
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_list_groups_empty_org(auth_token):
    org = _create_org(auth_token)

    res = httpx.get(
        f"{BASE}/v1/groups",
        params={"org_id": org["id"]},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert "items" in data
    assert "total" in data
    # New org may have "everyone" system group auto-created
    # so we just check the structure is correct
    assert isinstance(data["items"], list)


@pytest.mark.integration
def test_list_groups_with_results(auth_token):
    org = _create_org(auth_token)

    _create_group(auth_token, org["id"])
    _create_group(auth_token, org["id"])

    res = httpx.get(
        f"{BASE}/v1/groups",
        params={"org_id": org["id"]},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    # At least 2 (plus possible everyone group)
    assert data["total"] >= 2
    assert len(data["items"]) >= 2


@pytest.mark.integration
def test_list_groups_filter_by_org_id(auth_token):
    org1 = _create_org(auth_token)
    org2 = _create_org(auth_token)

    _create_group(auth_token, org1["id"])
    _create_group(auth_token, org2["id"])

    res = httpx.get(
        f"{BASE}/v1/groups",
        params={"org_id": org1["id"]},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    for item in items:
        assert item["org_id"] == org1["id"]


@pytest.mark.integration
def test_list_groups_unauthenticated(auth_token):
    res = httpx.get(f"{BASE}/v1/groups", params={"org_id": "any"})
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Get group
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_get_group_found(auth_token):
    org = _create_org(auth_token)
    group = _create_group(auth_token, org["id"])

    res = httpx.get(
        f"{BASE}/v1/groups/{group['id']}",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["id"] == group["id"]
    assert body["data"]["org_id"] == org["id"]


@pytest.mark.integration
def test_get_group_not_found(auth_token):

    res = httpx.get(
        f"{BASE}/v1/groups/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "GROUP_NOT_FOUND"


# ---------------------------------------------------------------------------
# Update group
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_update_group_success(auth_token):
    org = _create_org(auth_token)
    group = _create_group(auth_token, org["id"])

    new_name = f"Updated {uuid.uuid4().hex[:4]}"
    res = httpx.patch(
        f"{BASE}/v1/groups/{group['id']}",
        json={"name": new_name},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["name"] == new_name


@pytest.mark.integration
def test_update_group_not_found(auth_token):

    res = httpx.patch(
        f"{BASE}/v1/groups/00000000-0000-0000-0000-000000000000",
        json={"name": "Nope"},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "GROUP_NOT_FOUND"


@pytest.mark.integration
def test_update_group_description(auth_token):
    org = _create_org(auth_token)
    group = _create_group(auth_token, org["id"])

    res = httpx.patch(
        f"{BASE}/v1/groups/{group['id']}",
        json={"description": "Updated description"},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["description"] == "Updated description"


# ---------------------------------------------------------------------------
# Delete group (soft-delete)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_delete_group_success(auth_token):
    org = _create_org(auth_token)
    group = _create_group(auth_token, org["id"])

    res = httpx.delete(
        f"{BASE}/v1/groups/{group['id']}",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 204, res.text


@pytest.mark.integration
def test_delete_group_idempotent(auth_token):
    """Deleting a soft-deleted group again should return 204 (idempotent)."""
    org = _create_org(auth_token)
    group = _create_group(auth_token, org["id"])

    res1 = httpx.delete(
        f"{BASE}/v1/groups/{group['id']}",
        headers=_auth_headers(auth_token),
    )
    assert res1.status_code == 204

    res2 = httpx.delete(
        f"{BASE}/v1/groups/{group['id']}",
        headers=_auth_headers(auth_token),
    )
    assert res2.status_code == 204


@pytest.mark.integration
def test_delete_group_not_found(auth_token):

    res = httpx.delete(
        f"{BASE}/v1/groups/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "GROUP_NOT_FOUND"


# ---------------------------------------------------------------------------
# Add member
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_add_member_success(auth_token):
    user_id = _get_user_id(auth_token)
    org = _create_org(auth_token)
    group = _create_group(auth_token, org["id"])

    res = httpx.post(
        f"{BASE}/v1/groups/{group['id']}/members",
        json={"user_id": user_id},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["group_id"] == group["id"]
    assert data["user_id"] == user_id
    assert data["is_active"] is True


@pytest.mark.integration
def test_add_member_duplicate_returns_409(auth_token):
    user_id = _get_user_id(auth_token)
    org = _create_org(auth_token)
    group = _create_group(auth_token, org["id"])

    # Add first time
    res1 = httpx.post(
        f"{BASE}/v1/groups/{group['id']}/members",
        json={"user_id": user_id},
        headers=_auth_headers(auth_token),
    )
    assert res1.status_code == 201

    # Add again — should 409
    res2 = httpx.post(
        f"{BASE}/v1/groups/{group['id']}/members",
        json={"user_id": user_id},
        headers=_auth_headers(auth_token),
    )
    assert res2.status_code == 409, res2.text
    body = res2.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "MEMBER_ALREADY_EXISTS"


@pytest.mark.integration
def test_add_member_user_not_found_returns_404(auth_token):
    org = _create_org(auth_token)
    group = _create_group(auth_token, org["id"])

    res = httpx.post(
        f"{BASE}/v1/groups/{group['id']}/members",
        json={"user_id": "00000000-0000-0000-0000-000000000000"},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404, res.text
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "USER_NOT_FOUND"


@pytest.mark.integration
def test_add_member_group_not_found_returns_404(auth_token):
    user_id = _get_user_id(auth_token)

    res = httpx.post(
        f"{BASE}/v1/groups/00000000-0000-0000-0000-000000000000/members",
        json={"user_id": user_id},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404, res.text
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "GROUP_NOT_FOUND"


# ---------------------------------------------------------------------------
# List members
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_list_members_empty(auth_token):
    org = _create_org(auth_token)
    group = _create_group(auth_token, org["id"])

    res = httpx.get(
        f"{BASE}/v1/groups/{group['id']}/members",
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
def test_list_members_with_members(auth_token):
    user_id = _get_user_id(auth_token)
    org = _create_org(auth_token)
    group = _create_group(auth_token, org["id"])

    # Add the admin user
    httpx.post(
        f"{BASE}/v1/groups/{group['id']}/members",
        json={"user_id": user_id},
        headers=_auth_headers(auth_token),
    )

    res = httpx.get(
        f"{BASE}/v1/groups/{group['id']}/members",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["total"] >= 1
    user_ids = [m["user_id"] for m in data["items"]]
    assert user_id in user_ids


# ---------------------------------------------------------------------------
# Remove member
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_remove_member_success(auth_token):
    user_id = _get_user_id(auth_token)
    org = _create_org(auth_token)
    group = _create_group(auth_token, org["id"])

    # Add
    httpx.post(
        f"{BASE}/v1/groups/{group['id']}/members",
        json={"user_id": user_id},
        headers=_auth_headers(auth_token),
    )

    # Remove
    res = httpx.delete(
        f"{BASE}/v1/groups/{group['id']}/members/{user_id}",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 204, res.text


@pytest.mark.integration
def test_remove_member_not_found(auth_token):
    org = _create_org(auth_token)
    group = _create_group(auth_token, org["id"])

    res = httpx.delete(
        f"{BASE}/v1/groups/{group['id']}/members/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404, res.text
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "MEMBER_NOT_FOUND"


@pytest.mark.integration
def test_remove_member_group_not_found(auth_token):
    user_id = _get_user_id(auth_token)

    res = httpx.delete(
        f"{BASE}/v1/groups/00000000-0000-0000-0000-000000000000/members/{user_id}",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404, res.text
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "GROUP_NOT_FOUND"


# ---------------------------------------------------------------------------
# Auto-create everyone group on org creation
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_create_org_auto_creates_everyone_group(auth_token):
    org = _create_org(auth_token)

    res = httpx.get(
        f"{BASE}/v1/groups",
        params={"org_id": org["id"]},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    system_groups = [g for g in items if g["is_system"] is True]
    assert len(system_groups) >= 1
    slugs = [g["slug"] for g in system_groups]
    assert "everyone" in slugs
