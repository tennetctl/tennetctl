# Testing Standards

tennetctl uses **pytest** for Python function/integration tests and **Robot Framework** for API and frontend E2E tests. Both are mandatory.

---

## Testing Pyramid

```
         ┌──────────────┐
         │   E2E Tests   │  Robot Framework + Playwright Browser
         │  (few, slow)  │
         ├──────────────┤
         │  API Tests    │  Robot Framework (HTTP requests)
         │  (moderate)   │
         ├──────────────┤
         │  Integration  │  pytest (real Postgres, no mocks)
         │  (many, fast) │
         ├──────────────┤
         │  Unit Tests   │  pytest (pure functions)
         │  (many, fast) │
         └──────────────┘
```

---

## 1. pytest — Python Functions and Integration Tests

### File Location

```
backend/tests/{module}/{sub_feature}/test_{description}.py
```

Example:
```
backend/tests/02_iam/01_org/test_create_org.py
backend/tests/02_iam/01_org/test_list_orgs.py
backend/tests/02_iam/08_auth/test_login.py
```

### Test Naming

```python
async def test_{action}_{scenario}(fixtures):
    """One-line description of what this test verifies."""
```

Examples:
```python
async def test_create_org_success(client, seeded_user):
    """Creating an org with valid data returns 201."""

async def test_create_org_duplicate_slug(client, seeded_org):
    """Creating an org with an existing slug returns 409."""

async def test_login_wrong_password(client, seeded_user):
    """Wrong password returns 401 with UNAUTHORIZED code."""

async def test_list_orgs_excludes_deleted(client, seeded_org, deleted_org):
    """Soft-deleted orgs are not returned in the list."""
```

### Test Structure (AAA Pattern)

```python
async def test_create_org_success(client, seeded_user):
    """Creating an org with valid data returns 201 with org data."""
    # Arrange — set up test data (usually via fixtures)

    # Act — perform the operation
    response = await client.post("/api/v1/orgs", json={
        "name": "Acme Corp",
        "slug": "acme-corp",
    })

    # Assert — verify the result
    assert response.status_code == 201
    data = response.json()
    assert data["ok"] is True
    assert data["data"]["name"] == "Acme Corp"
    assert data["data"]["slug"] == "acme-corp"
```

### No Mocks — Real Database

Tests run against a real Postgres database. No mocked queries.

```python
# Correct — tests against real DB
async def test_get_org_returns_attributes(client, seeded_org):
    response = await client.get(f"/api/v1/orgs/{seeded_org.id}")
    assert response.json()["data"]["name"] == seeded_org.name

# WRONG — never mock the database
async def test_get_org(mock_db):
    mock_db.fetchrow.return_value = {"id": "fake", "name": "Fake"}
    # This tests nothing useful
```

### Test Isolation

Each test runs in a database transaction that is rolled back after the test. Tests do not affect each other.

### Fixtures

```python
# conftest.py
import pytest

@pytest.fixture
async def seeded_org(conn):
    """Create a test org with standard attributes."""
    org_id = generate_uuid7()
    await repo.create_org(conn, org_id=org_id, status_id=1, actor_id=SYSTEM_ACTOR)
    await repo.set_org_attrs(conn, org_id=org_id, attrs={
        "name": "Test Org",
        "slug": "test-org",
    }, actor_id=SYSTEM_ACTOR)
    return await repo.get_org_by_id(conn, org_id)
```

### What to Test

| Layer | What to test | Example |
|-------|-------------|---------|
| Repository | Query correctness | `test_get_org_by_slug_returns_correct_org` |
| Service | Business rules | `test_create_org_rejects_duplicate_slug` |
| Service | Edge cases | `test_soft_delete_cascades_to_members` |
| Service | Error conditions | `test_get_nonexistent_org_raises_not_found` |
| Routes | Status codes | `test_create_org_returns_201` |
| Routes | Response shape | `test_org_response_has_envelope` |
| Routes | Validation | `test_create_org_rejects_empty_name` |
| Routes | Auth | `test_create_org_requires_auth` |

### Running Tests

```bash
cd backend

# Run all tests
uv run pytest

# Run tests for a module
uv run pytest tests/02_iam/

# Run a specific test file
uv run pytest tests/02_iam/01_org/test_create_org.py -v

# Run with coverage
uv run pytest --cov=. --cov-report=term-missing

# Run a single test
uv run pytest tests/02_iam/01_org/test_create_org.py::test_create_org_success -v
```

### Coverage Requirement

Minimum **80% coverage** on all new code. PRs below this threshold are not merged.

---

## 2. Robot Framework — API Tests

### File Location

```
tests/e2e/{feature}/{nn}_{description}.robot
```

Example:
```
tests/e2e/02_iam/01_create_org.robot
tests/e2e/02_iam/02_login.robot
tests/e2e/05_notify/01_send_notification.robot
```

### Robot Framework API Test Example

```robot
*** Settings ***
Library    RequestsLibrary
Library    Collections
Suite Setup    Create Session    api    http://localhost:51734    verify=${False}

*** Variables ***
${BASE_URL}    /api/v1

*** Test Cases ***
Create Organisation Successfully
    [Documentation]    POST /v1/orgs creates a new org and returns 201
    ${body}=    Create Dictionary    name=Test Org    slug=test-org-rf
    ${response}=    POST On Session    api    ${BASE_URL}/orgs    json=${body}
    Status Should Be    201    ${response}
    ${json}=    Set Variable    ${response.json()}
    Should Be True    ${json}[ok]
    Should Be Equal    ${json}[data][name]    Test Org
    Should Be Equal    ${json}[data][slug]    test-org-rf

Create Organisation With Duplicate Slug Fails
    [Documentation]    POST /v1/orgs with existing slug returns 409
    ${body}=    Create Dictionary    name=Duplicate    slug=test-org-rf
    ${response}=    POST On Session    api    ${BASE_URL}/orgs
    ...    json=${body}    expected_status=409
    ${json}=    Set Variable    ${response.json()}
    Should Not Be True    ${json}[ok]
    Should Be Equal    ${json}[error][code]    ORG_SLUG_EXISTS

Get Organisation By ID
    [Documentation]    GET /v1/orgs/{id} returns the org
    ${response}=    GET On Session    api    ${BASE_URL}/orgs/${ORG_ID}
    Status Should Be    200    ${response}
    ${json}=    Set Variable    ${response.json()}
    Should Be True    ${json}[ok]
```

### What API Tests Cover

- Full request/response cycle through the real API
- Authentication and authorization
- Input validation at the API boundary
- Response envelope structure
- Error codes and messages
- Multi-step workflows (create → read → update → delete)

---

## 3. Robot Framework — Frontend E2E Tests

### File Location

```
tests/e2e/{feature}/{nn}_{description}.robot
```

### E2E Test Example (Playwright Browser Library)

```robot
*** Settings ***
Library    Browser
Suite Setup    New Browser    headless=true
Suite Teardown    Close Browser

*** Variables ***
${BASE_URL}    http://localhost:51735

*** Test Cases ***
Login With Valid Credentials
    [Documentation]    User can log in and see the dashboard
    New Page    ${BASE_URL}/login
    Fill Text    input[name="email"]    admin@tennetctl.local
    Fill Text    input[name="password"]    admin123
    Click    button[type="submit"]
    Wait For Elements State    text=Dashboard    visible    timeout=5s

Create Organisation Via UI
    [Documentation]    Admin can create an org from the UI
    Click    text=Organisations
    Click    text=Create Organisation
    Fill Text    input[name="name"]    E2E Test Org
    Fill Text    input[name="slug"]    e2e-test-org
    Click    button[type="submit"]
    Wait For Elements State    text=E2E Test Org    visible    timeout=5s
```

### Important: Never Use @playwright/test

tennetctl uses **Robot Framework + Playwright Browser library** for all E2E tests. Never use `@playwright/test` or `.spec.ts` files.

---

## TDD Workflow Reminder

```
1. Write the test (RED)     → test fails because implementation doesn't exist
2. Implement (GREEN)         → write minimal code to make the test pass
3. Refactor (IMPROVE)        → clean up without changing behavior
4. Verify coverage (80%+)   → uv run pytest --cov=.
```

Fix the implementation, not the test (unless the test is wrong).

---

## Checklist — Before Every PR

- [ ] Tests written BEFORE implementation (TDD)
- [ ] pytest tests for all Python functions (service, repository)
- [ ] Robot Framework API tests for all endpoints
- [ ] Robot Framework E2E tests for UI workflows
- [ ] All tests pass: `uv run pytest` and `robot tests/e2e/`
- [ ] Coverage at 80%+ for new code
- [ ] No mocked database queries
- [ ] Test names follow `test_{action}_{scenario}` convention
- [ ] Every test has a docstring
