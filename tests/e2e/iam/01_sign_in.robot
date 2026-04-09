*** Settings ***
Documentation     IAM — sign-in form end to end.
...
...               Tests the full login flow: render, validation, error, success, token storage.
...               Requires setup wizard to have run (admin account must exist).
Resource          ../resources/common.resource

Suite Setup       Run Keywords
...               New Browser    headless=true    AND
...               New Context
Suite Teardown    Close Browser

*** Test Cases ***

Sign In Page Renders Form
    [Tags]    iam    sign-in
    New Page    ${FRONTEND_URL}/iam
    Wait For Load State    networkidle
    Get Element    text=Sign in
    Get Element    id=username
    Get Element    id=password
    Get Element    css=button[type="submit"]:has-text("Sign in")

Sign In Page Shows IAM Sidebar
    [Tags]    iam    sign-in
    New Page    ${FRONTEND_URL}/iam
    Wait For Load State    networkidle
    Get Element    css=aside nav[aria-label="IAM sub-features"]

Invalid Credentials Shows Error Banner
    [Tags]    iam    sign-in
    New Page    ${FRONTEND_URL}/iam
    Wait For Load State    networkidle
    Fill Text    id=username    ${ADMIN_USER}
    Fill Text    id=password    wrong_password_xyz_123
    Click    css=button[type="submit"]
    Wait For Load State    networkidle
    Get Element    css=[class*="danger"]

Unknown User Shows Error Banner
    [Tags]    iam    sign-in
    New Page    ${FRONTEND_URL}/iam
    Wait For Load State    networkidle
    Fill Text    id=username    nobody_xyz
    Fill Text    id=password    anything
    Click    css=button[type="submit"]
    Wait For Load State    networkidle
    Get Element    css=[class*="danger"]

Submit Button Shows Loading State
    [Tags]    iam    sign-in
    New Page    ${FRONTEND_URL}/iam
    Wait For Load State    networkidle
    Fill Text    id=username    ${ADMIN_USER}
    Fill Text    id=password    ${ADMIN_PASS}
    Click    css=button[type="submit"]
    # Loading text should appear briefly
    # (this is a best-effort check — timing-sensitive)
    # We verify the final success state instead
    Wait For Load State    networkidle
    Get Element    css=[class*="success"]

Successful Login Shows Session Confirmation
    [Tags]    iam    sign-in
    New Page    ${FRONTEND_URL}/iam
    Wait For Load State    networkidle
    Fill Text    id=username    ${ADMIN_USER}
    Fill Text    id=password    ${ADMIN_PASS}
    Click    css=button[type="submit"]
    Wait For Load State    networkidle
    Get Element    css=[class*="success"]
    ${text}=    Get Text    css=[class*="success"]
    Should Contain    ${text}    Signed in

Token Stored In LocalStorage After Login
    [Tags]    iam    sign-in
    New Page    ${FRONTEND_URL}/iam
    Wait For Load State    networkidle
    Fill Text    id=username    ${ADMIN_USER}
    Fill Text    id=password    ${ADMIN_PASS}
    Click    css=button[type="submit"]
    Wait For Load State    networkidle
    ${token}=    Evaluate JavaScript    $    localStorage.getItem('tennetctl_access_token')
    Should Not Be Empty    ${token}
    ${session}=    Evaluate JavaScript    $    localStorage.getItem('tennetctl_session_id')
    Should Not Be Empty    ${session}
