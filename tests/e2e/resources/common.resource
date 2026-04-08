*** Settings ***
Documentation     Shared keywords and variables for all tennetctl E2E tests.
...
...               Prerequisites:
...                 1. Run: 11_infra/dev.sh start  (starts infra + backend:58000 + frontend:53000)
...                 2. If fresh DB: DATABASE_URL=... python -m scripts.01_migrator up
...                    then: tennetctl setup --env dev --mode a (interactive, once per DB)
...
...               All tests are idempotent and safe to run multiple times.
Library           Browser
Library           RequestsLibrary

*** Variables ***
${FRONTEND_URL}   http://localhost:53000
${API_URL}        http://localhost:58000
${ADMIN_USER}     admin
${ADMIN_PASS}     ChangeMe123!

*** Keywords ***

Ensure Backend Is Reachable
    [Documentation]    Fail fast with a clear message if backend is not running.
    ${resp}=    GET    ${API_URL}/healthz    expected_status=200
    Should Be Equal    ${resp.json()["data"]["status"]}    ok

Login Via API And Store Token
    [Documentation]    POST /v1/sessions, seed token into current page localStorage.
    ...                Must be called after New Page so localStorage scope exists.
    ${resp}=    POST    ${API_URL}/v1/sessions
    ...    json={"username": "${ADMIN_USER}", "password": "${ADMIN_PASS}"}
    ...    expected_status=201
    ${body}=    Set Variable    ${resp.json()}
    ${token}=    Set Variable    ${body["data"]["access_token"]}
    ${session}=    Set Variable    ${body["data"]["session_id"]}
    Evaluate JavaScript    $
    ...    localStorage.setItem('tennetctl_access_token', '${token}');
    ...    localStorage.setItem('tennetctl_session_id', '${session}');
    [Return]    ${token}

Clear Token From Storage
    [Documentation]    Remove token from localStorage on current page.
    Evaluate JavaScript    $    localStorage.clear()

Navigate And Wait
    [Documentation]    Navigate to URL and wait for full page load.
    [Arguments]    ${url}
    Go To    ${url}
    Wait For Load State    networkidle

Assert Page Title Contains
    [Documentation]    Check a heading h1 is visible on the current page.
    [Arguments]    ${title}
    Get Element    css=h1:text-is("${title}")

Assert Toast Or Banner Contains
    [Documentation]    Check for a visible success or error message.
    [Arguments]    ${text}
    Get Element    css=[class*="success"]:has-text("${text}"), css=[class*="danger"]:has-text("${text}")
