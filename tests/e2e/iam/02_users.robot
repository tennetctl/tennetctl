*** Settings ***
Documentation     IAM — users table, organizations, sessions pages end to end.
Resource          ../resources/common.resource

Suite Setup       Run Keywords
...               New Browser    headless=true    AND
...               New Context
Suite Teardown    Close Browser

*** Test Cases ***

Users Page Without Token Shows Error
    [Tags]    iam    users
    New Page    ${FRONTEND_URL}/iam/users
    Wait For Load State    networkidle
    Clear Token From Storage
    Reload
    Wait For Load State    networkidle
    Get Element    text=Not signed in

Users Page Renders Page Header
    [Tags]    iam    users
    New Page    ${FRONTEND_URL}/iam/users
    Wait For Load State    networkidle
    Get Element    text=Users

Users Table Loads After Auth
    [Tags]    iam    users
    New Page    ${FRONTEND_URL}/iam/users
    Wait For Load State    networkidle
    Login Via API And Store Token
    Reload
    Wait For Load State    networkidle
    Wait For Elements State    css=table, text=Not signed in, text=Could not load    visible    timeout=10s
    Get Element    css=table

Users Table Has Correct Column Headers
    [Tags]    iam    users
    New Page    ${FRONTEND_URL}/iam/users
    Wait For Load State    networkidle
    Login Via API And Store Token
    Reload
    Wait For Load State    networkidle
    Wait For Elements State    css=table    visible    timeout=10s
    Get Element    text=Username
    Get Element    text=Email
    Get Element    text=Account
    Get Element    text=Auth
    Get Element    text=Status
    Get Element    text=Created

Users Table Shows At Least One Row
    [Tags]    iam    users
    [Documentation]    Admin account created by setup wizard must appear.
    New Page    ${FRONTEND_URL}/iam/users
    Wait For Load State    networkidle
    Login Via API And Store Token
    Reload
    Wait For Load State    networkidle
    Wait For Elements State    css=tbody tr    visible    timeout=10s
    Get Element    css=tbody tr

Users Table Active Badge Visible
    [Tags]    iam    users
    New Page    ${FRONTEND_URL}/iam/users
    Wait For Load State    networkidle
    Login Via API And Store Token
    Reload
    Wait For Load State    networkidle
    Wait For Elements State    css=tbody    visible    timeout=10s
    Get Element    css=tbody td:has-text("active")

Organizations Page Shows Header And Placeholder
    [Tags]    iam    organizations
    New Page    ${FRONTEND_URL}/iam/organizations
    Wait For Load State    networkidle
    Get Element    text=Organizations
    Get Element    text=Orgs endpoint not wired yet

Sessions Page Shows Header And Placeholder
    [Tags]    iam    sessions
    New Page    ${FRONTEND_URL}/iam/sessions
    Wait For Load State    networkidle
    Get Element    text=Active Sessions
    Get Element    text=Sessions list endpoint pending
