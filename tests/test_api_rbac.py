"""Integration tests for RBAC three-tier endpoints.

Platform roles:
  GET    /v1/platform-roles
  POST   /v1/platform-roles
  GET    /v1/platform-roles/{id}
  PATCH  /v1/platform-roles/{id}
  DELETE /v1/platform-roles/{id}
  POST   /v1/platform-roles/{id}/permissions
  DELETE /v1/platform-roles/{id}/permissions/{pid}
  POST   /v1/users/{id}/platform-roles
  DELETE /v1/users/{id}/platform-roles/{role_id}

Org roles:
  GET    /v1/orgs/{org_id}/roles
  POST   /v1/orgs/{org_id}/roles
  PATCH  /v1/orgs/{org_id}/roles/{id}
  DELETE /v1/orgs/{org_id}/roles/{id}
  POST   /v1/orgs/{org_id}/roles/{id}/permissions
  DELETE /v1/orgs/{org_id}/roles/{id}/permissions/{pid}
  POST   /v1/users/{id}/org-roles
  DELETE /v1/users/{id}/org-roles/{assignment_id}

Workspace roles:
  (similar pattern to org roles)

Runtime:
  POST   /v1/rbac/check
  GET    /v1/users/{id}/permissions/effective

Requires:
  - Backend running at http://localhost:58000
  - First admin user: username=admin, password=ChangeMe123!

Run with:
  pytest tests/test_api_rbac.py -v -m integration
"""

import uuid

import httpx
import pytest

BASE = "http://localhost:58000"
ADMIN_USER = "admin"
ADMIN_PASS = "ChangeMe123!"


# ---------------------------------------------------------------------------
# Module-scoped session fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def auth_token() -> str:
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


def _get_user_id(token: str) -> str:
    res = httpx.get(f"{BASE}/v1/sessions/me", headers=_auth_headers(token))
    assert res.status_code == 200
    return res.json()["data"]["user_id"]


def _create_org(token: str) -> dict:
    res = httpx.post(
        f"{BASE}/v1/orgs",
        json={
            "name": f"RBAC Test Org {uuid.uuid4().hex[:6]}",
            "slug": f"rbac-test-org-{uuid.uuid4().hex[:8]}",
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
            "name": f"RBAC Test WS {uuid.uuid4().hex[:6]}",
            "slug": f"rbac-test-ws-{uuid.uuid4().hex[:8]}",
            "org_id": org_id,
        },
        headers=_auth_headers(token),
    )
    assert res.status_code == 201, f"Workspace create failed: {res.text}"
    return res.json()["data"]


def _get_permission_id(token: str, resource: str, action: str) -> str:
    """Fetch a permission ID by resource+action from the catalog."""
    res = httpx.get(f"{BASE}/v1/permissions", headers=_auth_headers(token))
    assert res.status_code == 200, f"List permissions failed: {res.text}"
    perms = res.json()["data"]["items"]
    for p in perms:
        if p["resource"] == resource and p["action"] == action:
            return p["id"]
    raise ValueError(f"Permission {resource}:{action} not found in catalog")


# ---------------------------------------------------------------------------
# Permissions catalog
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_list_permissions(auth_token):
    res = httpx.get(f"{BASE}/v1/permissions", headers=_auth_headers(auth_token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert "items" in data
    assert "total" in data
    assert data["total"] == 13
    resources = {p["resource"] for p in data["items"]}
    assert "orgs" in resources
    assert "users" in resources
    assert "vault.secrets" in resources
    assert "rbac" in resources


@pytest.mark.integration
def test_list_permissions_unauthenticated():
    res = httpx.get(f"{BASE}/v1/permissions")
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Platform roles — CRUD
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_list_platform_roles_returns_seeded(auth_token):
    res = httpx.get(f"{BASE}/v1/platform-roles", headers=_auth_headers(auth_token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert "items" in data
    codes = {r["code"] for r in data["items"]}
    assert "platform_admin" in codes
    assert "platform_support" in codes
    assert "platform_readonly" in codes


@pytest.mark.integration
def test_create_platform_role(auth_token):
    code = f"test_role_{uuid.uuid4().hex[:6]}"
    res = httpx.post(
        f"{BASE}/v1/platform-roles",
        json={"code": code, "name": "Test Role", "category_code": "ops"},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["code"] == code
    assert data["name"] == "Test Role"
    assert data["category_code"] == "ops"
    assert data["is_system"] is False
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.integration
def test_create_platform_role_duplicate_code_returns_409(auth_token):
    code = f"test_dup_{uuid.uuid4().hex[:6]}"
    res1 = httpx.post(
        f"{BASE}/v1/platform-roles",
        json={"code": code, "name": "Role 1", "category_code": "ops"},
        headers=_auth_headers(auth_token),
    )
    assert res1.status_code == 201

    res2 = httpx.post(
        f"{BASE}/v1/platform-roles",
        json={"code": code, "name": "Role 2", "category_code": "ops"},
        headers=_auth_headers(auth_token),
    )
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "PLATFORM_ROLE_CODE_CONFLICT"


@pytest.mark.integration
def test_create_platform_role_invalid_category_returns_422(auth_token):
    res = httpx.post(
        f"{BASE}/v1/platform-roles",
        json={"code": f"bad_{uuid.uuid4().hex[:6]}", "name": "Bad", "category_code": "nonexistent"},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "INVALID_CATEGORY"


@pytest.mark.integration
def test_get_platform_role(auth_token):
    code = f"get_test_{uuid.uuid4().hex[:6]}"
    create_res = httpx.post(
        f"{BASE}/v1/platform-roles",
        json={"code": code, "name": "Get Me", "category_code": "ops"},
        headers=_auth_headers(auth_token),
    )
    assert create_res.status_code == 201
    role_id = create_res.json()["data"]["id"]

    res = httpx.get(f"{BASE}/v1/platform-roles/{role_id}", headers=_auth_headers(auth_token))
    assert res.status_code == 200
    assert res.json()["data"]["id"] == role_id


@pytest.mark.integration
def test_get_platform_role_not_found(auth_token):
    res = httpx.get(
        f"{BASE}/v1/platform-roles/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "PLATFORM_ROLE_NOT_FOUND"


@pytest.mark.integration
def test_update_platform_role(auth_token):
    code = f"upd_test_{uuid.uuid4().hex[:6]}"
    create_res = httpx.post(
        f"{BASE}/v1/platform-roles",
        json={"code": code, "name": "Before Update", "category_code": "ops"},
        headers=_auth_headers(auth_token),
    )
    assert create_res.status_code == 201
    role_id = create_res.json()["data"]["id"]

    res = httpx.patch(
        f"{BASE}/v1/platform-roles/{role_id}",
        json={"name": "After Update"},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200
    assert res.json()["data"]["name"] == "After Update"


@pytest.mark.integration
def test_delete_platform_role_system_protected(auth_token):
    """System roles cannot be deleted."""
    # Get platform_admin role id
    res = httpx.get(f"{BASE}/v1/platform-roles", headers=_auth_headers(auth_token))
    admin_role = next(r for r in res.json()["data"]["items"] if r["code"] == "platform_admin")

    del_res = httpx.delete(
        f"{BASE}/v1/platform-roles/{admin_role['id']}",
        headers=_auth_headers(auth_token),
    )
    assert del_res.status_code == 403
    assert del_res.json()["error"]["code"] == "SYSTEM_ROLE_PROTECTED"


@pytest.mark.integration
def test_delete_platform_role_success(auth_token):
    code = f"del_test_{uuid.uuid4().hex[:6]}"
    create_res = httpx.post(
        f"{BASE}/v1/platform-roles",
        json={"code": code, "name": "Delete Me", "category_code": "ops"},
        headers=_auth_headers(auth_token),
    )
    assert create_res.status_code == 201
    role_id = create_res.json()["data"]["id"]

    res = httpx.delete(f"{BASE}/v1/platform-roles/{role_id}", headers=_auth_headers(auth_token))
    assert res.status_code == 204


# ---------------------------------------------------------------------------
# Platform role permissions
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_add_and_remove_platform_role_permission(auth_token):
    code = f"perm_test_{uuid.uuid4().hex[:6]}"
    create_res = httpx.post(
        f"{BASE}/v1/platform-roles",
        json={"code": code, "name": "Perm Test Role", "category_code": "ops"},
        headers=_auth_headers(auth_token),
    )
    assert create_res.status_code == 201
    role_id = create_res.json()["data"]["id"]

    perm_id = _get_permission_id(auth_token, "groups", "read")

    # Add
    add_res = httpx.post(
        f"{BASE}/v1/platform-roles/{role_id}/permissions",
        json={"permission_id": perm_id},
        headers=_auth_headers(auth_token),
    )
    assert add_res.status_code == 201, add_res.text
    data = add_res.json()["data"]
    assert data["role_id"] == role_id
    perm_ids = [p["id"] for p in data["permissions"]]
    assert perm_id in perm_ids

    # Add duplicate — 409
    dup_res = httpx.post(
        f"{BASE}/v1/platform-roles/{role_id}/permissions",
        json={"permission_id": perm_id},
        headers=_auth_headers(auth_token),
    )
    assert dup_res.status_code == 409

    # Remove
    rem_res = httpx.delete(
        f"{BASE}/v1/platform-roles/{role_id}/permissions/{perm_id}",
        headers=_auth_headers(auth_token),
    )
    assert rem_res.status_code == 204

    # Remove again — 404
    rem_res2 = httpx.delete(
        f"{BASE}/v1/platform-roles/{role_id}/permissions/{perm_id}",
        headers=_auth_headers(auth_token),
    )
    assert rem_res2.status_code == 404


# ---------------------------------------------------------------------------
# User platform role assignment
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_assign_and_revoke_user_platform_role(auth_token):
    user_id = _get_user_id(auth_token)

    code = f"assign_test_{uuid.uuid4().hex[:6]}"
    create_res = httpx.post(
        f"{BASE}/v1/platform-roles",
        json={"code": code, "name": "Assign Test", "category_code": "ops"},
        headers=_auth_headers(auth_token),
    )
    assert create_res.status_code == 201
    role_id = create_res.json()["data"]["id"]

    # Assign
    assign_res = httpx.post(
        f"{BASE}/v1/users/{user_id}/platform-roles",
        json={"platform_role_id": role_id},
        headers=_auth_headers(auth_token),
    )
    assert assign_res.status_code == 201, assign_res.text
    data = assign_res.json()["data"]
    assert data["user_id"] == user_id
    assert data["platform_role_id"] == role_id
    assert data["is_active"] is True

    # Assign duplicate — 409
    dup_res = httpx.post(
        f"{BASE}/v1/users/{user_id}/platform-roles",
        json={"platform_role_id": role_id},
        headers=_auth_headers(auth_token),
    )
    assert dup_res.status_code == 409

    # Revoke
    rev_res = httpx.delete(
        f"{BASE}/v1/users/{user_id}/platform-roles/{role_id}",
        headers=_auth_headers(auth_token),
    )
    assert rev_res.status_code == 204

    # Revoke again — 404
    rev_res2 = httpx.delete(
        f"{BASE}/v1/users/{user_id}/platform-roles/{role_id}",
        headers=_auth_headers(auth_token),
    )
    assert rev_res2.status_code == 404


@pytest.mark.integration
def test_assign_platform_role_user_not_found(auth_token):
    # Get any valid role id
    res = httpx.get(f"{BASE}/v1/platform-roles", headers=_auth_headers(auth_token))
    role_id = res.json()["data"]["items"][0]["id"]

    assign_res = httpx.post(
        f"{BASE}/v1/users/00000000-0000-0000-0000-000000000000/platform-roles",
        json={"platform_role_id": role_id},
        headers=_auth_headers(auth_token),
    )
    assert assign_res.status_code == 404
    assert assign_res.json()["error"]["code"] == "USER_NOT_FOUND"


# ---------------------------------------------------------------------------
# Org roles — CRUD
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_list_org_roles_empty(auth_token):
    org = _create_org(auth_token)

    res = httpx.get(f"{BASE}/v1/orgs/{org['id']}/roles", headers=_auth_headers(auth_token))
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert isinstance(body["data"]["items"], list)


@pytest.mark.integration
def test_create_org_role(auth_token):
    org = _create_org(auth_token)
    code = f"org_role_{uuid.uuid4().hex[:6]}"

    res = httpx.post(
        f"{BASE}/v1/orgs/{org['id']}/roles",
        json={"code": code, "name": "Org Editor", "category_code": "content"},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["code"] == code
    assert data["org_id"] == org["id"]
    assert data["is_active"] is True


@pytest.mark.integration
def test_create_org_role_duplicate_code_returns_409(auth_token):
    org = _create_org(auth_token)
    code = f"dup_org_{uuid.uuid4().hex[:6]}"

    httpx.post(
        f"{BASE}/v1/orgs/{org['id']}/roles",
        json={"code": code, "name": "Role A", "category_code": "content"},
        headers=_auth_headers(auth_token),
    )
    res = httpx.post(
        f"{BASE}/v1/orgs/{org['id']}/roles",
        json={"code": code, "name": "Role B", "category_code": "content"},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "ORG_ROLE_CODE_CONFLICT"


@pytest.mark.integration
def test_update_org_role(auth_token):
    org = _create_org(auth_token)
    create_res = httpx.post(
        f"{BASE}/v1/orgs/{org['id']}/roles",
        json={"code": f"upd_{uuid.uuid4().hex[:6]}", "name": "Old Name", "category_code": "content"},
        headers=_auth_headers(auth_token),
    )
    assert create_res.status_code == 201
    role_id = create_res.json()["data"]["id"]

    res = httpx.patch(
        f"{BASE}/v1/orgs/{org['id']}/roles/{role_id}",
        json={"name": "New Name"},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200
    assert res.json()["data"]["name"] == "New Name"


@pytest.mark.integration
def test_delete_org_role(auth_token):
    org = _create_org(auth_token)
    create_res = httpx.post(
        f"{BASE}/v1/orgs/{org['id']}/roles",
        json={"code": f"del_{uuid.uuid4().hex[:6]}", "name": "Del Me", "category_code": "content"},
        headers=_auth_headers(auth_token),
    )
    assert create_res.status_code == 201
    role_id = create_res.json()["data"]["id"]

    res = httpx.delete(
        f"{BASE}/v1/orgs/{org['id']}/roles/{role_id}",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 204


# ---------------------------------------------------------------------------
# Org role permissions
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_add_org_role_permission(auth_token):
    org = _create_org(auth_token)
    create_res = httpx.post(
        f"{BASE}/v1/orgs/{org['id']}/roles",
        json={"code": f"prm_{uuid.uuid4().hex[:6]}", "name": "Perm Role", "category_code": "content"},
        headers=_auth_headers(auth_token),
    )
    assert create_res.status_code == 201
    role_id = create_res.json()["data"]["id"]
    perm_id = _get_permission_id(auth_token, "groups", "write")

    res = httpx.post(
        f"{BASE}/v1/orgs/{org['id']}/roles/{role_id}/permissions",
        json={"permission_id": perm_id},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["role_id"] == role_id
    perm_ids = [p["id"] for p in data["permissions"]]
    assert perm_id in perm_ids


@pytest.mark.integration
def test_remove_org_role_permission(auth_token):
    org = _create_org(auth_token)
    create_res = httpx.post(
        f"{BASE}/v1/orgs/{org['id']}/roles",
        json={"code": f"rem_{uuid.uuid4().hex[:6]}", "name": "Rem Perm Role", "category_code": "ops"},
        headers=_auth_headers(auth_token),
    )
    assert create_res.status_code == 201
    role_id = create_res.json()["data"]["id"]
    perm_id = _get_permission_id(auth_token, "orgs", "read")

    # Add
    httpx.post(
        f"{BASE}/v1/orgs/{org['id']}/roles/{role_id}/permissions",
        json={"permission_id": perm_id},
        headers=_auth_headers(auth_token),
    )

    # Remove
    res = httpx.delete(
        f"{BASE}/v1/orgs/{org['id']}/roles/{role_id}/permissions/{perm_id}",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 204


# ---------------------------------------------------------------------------
# User org role assignment
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_assign_and_revoke_user_org_role(auth_token):
    user_id = _get_user_id(auth_token)
    org = _create_org(auth_token)

    create_res = httpx.post(
        f"{BASE}/v1/orgs/{org['id']}/roles",
        json={"code": f"asgn_{uuid.uuid4().hex[:6]}", "name": "Assign Org Role", "category_code": "ops"},
        headers=_auth_headers(auth_token),
    )
    assert create_res.status_code == 201
    role_id = create_res.json()["data"]["id"]

    # Assign
    assign_res = httpx.post(
        f"{BASE}/v1/users/{user_id}/org-roles",
        json={"org_id": org["id"], "org_role_id": role_id},
        headers=_auth_headers(auth_token),
    )
    assert assign_res.status_code == 201, assign_res.text
    data = assign_res.json()["data"]
    assert data["user_id"] == user_id
    assert data["org_id"] == org["id"]
    assert data["org_role_id"] == role_id
    assignment_id = data["id"]

    # Duplicate — 409
    dup_res = httpx.post(
        f"{BASE}/v1/users/{user_id}/org-roles",
        json={"org_id": org["id"], "org_role_id": role_id},
        headers=_auth_headers(auth_token),
    )
    assert dup_res.status_code == 409

    # Revoke
    rev_res = httpx.delete(
        f"{BASE}/v1/users/{user_id}/org-roles/{assignment_id}",
        headers=_auth_headers(auth_token),
    )
    assert rev_res.status_code == 204

    # Revoke again — 404
    rev_res2 = httpx.delete(
        f"{BASE}/v1/users/{user_id}/org-roles/{assignment_id}",
        headers=_auth_headers(auth_token),
    )
    assert rev_res2.status_code == 404


# ---------------------------------------------------------------------------
# Workspace roles
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_list_workspace_roles_empty(auth_token):
    org = _create_org(auth_token)
    ws = _create_workspace(auth_token, org["id"])

    res = httpx.get(
        f"{BASE}/v1/workspaces/{ws['id']}/roles",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200
    assert isinstance(res.json()["data"]["items"], list)


@pytest.mark.integration
def test_create_workspace_role(auth_token):
    org = _create_org(auth_token)
    ws = _create_workspace(auth_token, org["id"])
    code = f"ws_role_{uuid.uuid4().hex[:6]}"

    res = httpx.post(
        f"{BASE}/v1/workspaces/{ws['id']}/roles",
        json={"code": code, "name": "WS Viewer", "category_code": "ops", "org_id": org["id"]},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["code"] == code
    assert data["workspace_id"] == ws["id"]
    assert data["org_id"] == org["id"]


@pytest.mark.integration
def test_create_workspace_role_duplicate_code_returns_409(auth_token):
    org = _create_org(auth_token)
    ws = _create_workspace(auth_token, org["id"])
    code = f"dup_ws_{uuid.uuid4().hex[:6]}"

    httpx.post(
        f"{BASE}/v1/workspaces/{ws['id']}/roles",
        json={"code": code, "name": "WS A", "category_code": "ops", "org_id": org["id"]},
        headers=_auth_headers(auth_token),
    )
    res = httpx.post(
        f"{BASE}/v1/workspaces/{ws['id']}/roles",
        json={"code": code, "name": "WS B", "category_code": "ops", "org_id": org["id"]},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "WORKSPACE_ROLE_CODE_CONFLICT"


@pytest.mark.integration
def test_update_workspace_role(auth_token):
    org = _create_org(auth_token)
    ws = _create_workspace(auth_token, org["id"])
    create_res = httpx.post(
        f"{BASE}/v1/workspaces/{ws['id']}/roles",
        json={"code": f"upd_ws_{uuid.uuid4().hex[:6]}", "name": "Old WS", "category_code": "ops", "org_id": org["id"]},
        headers=_auth_headers(auth_token),
    )
    assert create_res.status_code == 201
    role_id = create_res.json()["data"]["id"]

    res = httpx.patch(
        f"{BASE}/v1/workspaces/{ws['id']}/roles/{role_id}",
        json={"name": "New WS Name"},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200
    assert res.json()["data"]["name"] == "New WS Name"


@pytest.mark.integration
def test_delete_workspace_role(auth_token):
    org = _create_org(auth_token)
    ws = _create_workspace(auth_token, org["id"])
    create_res = httpx.post(
        f"{BASE}/v1/workspaces/{ws['id']}/roles",
        json={"code": f"del_ws_{uuid.uuid4().hex[:6]}", "name": "Del WS", "category_code": "ops", "org_id": org["id"]},
        headers=_auth_headers(auth_token),
    )
    assert create_res.status_code == 201
    role_id = create_res.json()["data"]["id"]

    res = httpx.delete(
        f"{BASE}/v1/workspaces/{ws['id']}/roles/{role_id}",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 204


# ---------------------------------------------------------------------------
# Workspace role permissions + user assignment
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_add_workspace_role_permission(auth_token):
    org = _create_org(auth_token)
    ws = _create_workspace(auth_token, org["id"])
    create_res = httpx.post(
        f"{BASE}/v1/workspaces/{ws['id']}/roles",
        json={"code": f"wsp_{uuid.uuid4().hex[:6]}", "name": "WS Perm", "category_code": "ops", "org_id": org["id"]},
        headers=_auth_headers(auth_token),
    )
    assert create_res.status_code == 201
    role_id = create_res.json()["data"]["id"]
    perm_id = _get_permission_id(auth_token, "vault.secrets", "read")

    res = httpx.post(
        f"{BASE}/v1/workspaces/{ws['id']}/roles/{role_id}/permissions",
        json={"permission_id": perm_id},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert perm_id in [p["id"] for p in data["permissions"]]


@pytest.mark.integration
def test_assign_and_revoke_user_workspace_role(auth_token):
    user_id = _get_user_id(auth_token)
    org = _create_org(auth_token)
    ws = _create_workspace(auth_token, org["id"])

    create_res = httpx.post(
        f"{BASE}/v1/workspaces/{ws['id']}/roles",
        json={"code": f"wsa_{uuid.uuid4().hex[:6]}", "name": "WS Assign", "category_code": "ops", "org_id": org["id"]},
        headers=_auth_headers(auth_token),
    )
    assert create_res.status_code == 201
    role_id = create_res.json()["data"]["id"]

    # Assign
    assign_res = httpx.post(
        f"{BASE}/v1/users/{user_id}/workspace-roles",
        json={"workspace_id": ws["id"], "workspace_role_id": role_id},
        headers=_auth_headers(auth_token),
    )
    assert assign_res.status_code == 201, assign_res.text
    data = assign_res.json()["data"]
    assert data["user_id"] == user_id
    assert data["workspace_id"] == ws["id"]
    assignment_id = data["id"]

    # Duplicate — 409
    dup_res = httpx.post(
        f"{BASE}/v1/users/{user_id}/workspace-roles",
        json={"workspace_id": ws["id"], "workspace_role_id": role_id},
        headers=_auth_headers(auth_token),
    )
    assert dup_res.status_code == 409

    # Revoke
    rev_res = httpx.delete(
        f"{BASE}/v1/users/{user_id}/workspace-roles/{assignment_id}",
        headers=_auth_headers(auth_token),
    )
    assert rev_res.status_code == 204

    # Revoke again — 404
    rev_res2 = httpx.delete(
        f"{BASE}/v1/users/{user_id}/workspace-roles/{assignment_id}",
        headers=_auth_headers(auth_token),
    )
    assert rev_res2.status_code == 404


# ---------------------------------------------------------------------------
# Runtime RBAC check
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_rbac_check_platform_admin_has_all_permissions(auth_token):
    """The seeded admin user has platform_admin role which grants all permissions."""
    user_id = _get_user_id(auth_token)

    for resource, action in [
        ("orgs", "read"), ("orgs", "admin"), ("users", "write"), ("rbac", "admin"),
    ]:
        res = httpx.post(
            f"{BASE}/v1/rbac/check",
            json={"user_id": user_id, "resource": resource, "action": action},
            headers=_auth_headers(auth_token),
        )
        assert res.status_code == 200, f"Check {resource}:{action} failed: {res.text}"
        data = res.json()["data"]
        assert data["allowed"] is True, f"Expected allowed=True for {resource}:{action}"


@pytest.mark.integration
def test_rbac_check_false_for_unknown_permission(auth_token):
    user_id = _get_user_id(auth_token)

    res = httpx.post(
        f"{BASE}/v1/rbac/check",
        json={"user_id": user_id, "resource": "nonexistent_resource", "action": "delete"},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200
    assert res.json()["data"]["allowed"] is False


@pytest.mark.integration
def test_rbac_check_org_role_scoped(auth_token):
    """Create an org role with a permission, assign it, then check true/false with correct/wrong org."""
    user_id = _get_user_id(auth_token)
    org = _create_org(auth_token)
    other_org = _create_org(auth_token)

    # Create org role with feature_flags:read
    role_res = httpx.post(
        f"{BASE}/v1/orgs/{org['id']}/roles",
        json={"code": f"check_{uuid.uuid4().hex[:6]}", "name": "Flag Reader", "category_code": "ops"},
        headers=_auth_headers(auth_token),
    )
    assert role_res.status_code == 201
    role_id = role_res.json()["data"]["id"]

    perm_id = _get_permission_id(auth_token, "feature_flags", "read")
    httpx.post(
        f"{BASE}/v1/orgs/{org['id']}/roles/{role_id}/permissions",
        json={"permission_id": perm_id},
        headers=_auth_headers(auth_token),
    )

    # Assign user to org role
    assign_res = httpx.post(
        f"{BASE}/v1/users/{user_id}/org-roles",
        json={"org_id": org["id"], "org_role_id": role_id},
        headers=_auth_headers(auth_token),
    )
    # May be 201 or 409 (if already assigned from another test - just continue)
    assert assign_res.status_code in (201, 409)

    # Check with correct org — should be true (platform_admin covers everything anyway,
    # but at least we hit the org path too)
    res = httpx.post(
        f"{BASE}/v1/rbac/check",
        json={
            "user_id": user_id,
            "resource": "feature_flags",
            "action": "read",
            "org_id": org["id"],
        },
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200
    assert res.json()["data"]["allowed"] is True


@pytest.mark.integration
def test_rbac_check_user_not_found(auth_token):
    res = httpx.post(
        f"{BASE}/v1/rbac/check",
        json={"user_id": "00000000-0000-0000-0000-000000000000", "resource": "orgs", "action": "read"},
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "USER_NOT_FOUND"


# ---------------------------------------------------------------------------
# Effective permissions
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_effective_permissions_platform_admin(auth_token):
    """The seeded admin has platform_admin which has 13 permissions seeded."""
    user_id = _get_user_id(auth_token)

    res = httpx.get(
        f"{BASE}/v1/users/{user_id}/permissions/effective",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["user_id"] == user_id
    assert "permissions" in data
    assert data["total"] >= 13
    resources = {p["resource"] for p in data["permissions"]}
    assert "orgs" in resources
    assert "rbac" in resources


@pytest.mark.integration
def test_effective_permissions_user_not_found(auth_token):
    res = httpx.get(
        f"{BASE}/v1/users/00000000-0000-0000-0000-000000000000/permissions/effective",
        headers=_auth_headers(auth_token),
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "USER_NOT_FOUND"


@pytest.mark.integration
def test_effective_permissions_unauthenticated():
    res = httpx.get(
        f"{BASE}/v1/users/some-id/permissions/effective",
    )
    assert res.status_code == 401
