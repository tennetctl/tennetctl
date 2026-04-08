*** Settings ***
Documentation     App shell — topbar module tabs, contextual sidebar, theme toggle.
...
...               Run: robot tests/e2e/shell/01_navigation.robot
Resource          ../resources/common.resource

Suite Setup       Run Keywords
...               New Browser    headless=true    AND
...               New Context    AND
...               New Page    ${FRONTEND_URL}
Suite Teardown    Close Browser

*** Test Cases ***

Home Page Loads With Module Cards
    [Tags]    shell
    Navigate And Wait    ${FRONTEND_URL}
    Get Element    text=tennetctl
    Get Element    text=Operator Console
    Get Element    text=IAM
    Get Element    text=Vault
    Get Element    text=Audit

Topbar Has Three Module Tabs
    [Tags]    shell
    Navigate And Wait    ${FRONTEND_URL}
    ${tabs}=    Get Elements    css=nav[aria-label="Modules"] a
    Length Should Be    ${tabs}    3

IAM Tab Navigates To IAM Page
    [Tags]    shell
    Navigate And Wait    ${FRONTEND_URL}
    Click    css=nav[aria-label="Modules"] a[href="/iam"]
    Wait For Load State    networkidle
    Get Element    text=Identity & Access

Vault Tab Navigates To Vault Page
    [Tags]    shell
    Navigate And Wait    ${FRONTEND_URL}
    Click    css=nav[aria-label="Modules"] a[href="/vault"]
    Wait For Load State    networkidle
    Get Element    text=Vault Status

Audit Tab Navigates To Audit Page
    [Tags]    shell
    Navigate And Wait    ${FRONTEND_URL}
    Click    css=nav[aria-label="Modules"] a[href="/audit"]
    Wait For Load State    networkidle
    Get Element    text=Audit Events

IAM Sidebar Shows Sub-Feature Links
    [Tags]    shell    sidebar
    Navigate And Wait    ${FRONTEND_URL}/iam
    Get Element    css=aside nav[aria-label="IAM sub-features"]
    Get Element    css=aside a[href="/iam/users"]
    Get Element    css=aside a[href="/iam/organizations"]
    Get Element    css=aside a[href="/iam/sessions"]

Vault Sidebar Shows Sub-Feature Links
    [Tags]    shell    sidebar
    Navigate And Wait    ${FRONTEND_URL}/vault
    Get Element    css=aside nav[aria-label="Vault sub-features"]
    Get Element    css=aside a[href="/vault/seal"]
    Get Element    css=aside a[href="/vault/unseal"]

Audit Sidebar Shows Sub-Feature Links
    [Tags]    shell    sidebar
    Navigate And Wait    ${FRONTEND_URL}/audit
    Get Element    css=aside nav[aria-label="Audit sub-features"]

Sidebar Footer Shows Active Scope
    [Tags]    shell    sidebar
    Navigate And Wait    ${FRONTEND_URL}/iam
    Get Element    text=Active Scope
    Get Element    text=tennetctl
    Get Element    text=default

Home Page Has No Sidebar
    [Tags]    shell    sidebar
    Navigate And Wait    ${FRONTEND_URL}
    ${has_sidebar}=    Run Keyword And Return Status    Get Element    css=aside
    Should Not Be True    ${has_sidebar}

Theme Toggle Is Present
    [Tags]    shell
    Navigate And Wait    ${FRONTEND_URL}
    Get Element    css=button[aria-label="Toggle theme"]
