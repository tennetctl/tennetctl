*** Settings ***
Documentation     Audit — events page: filter form, table columns, auth guard, filter logic.
Resource          ../resources/common.resource

Suite Setup       Run Keywords
...               New Browser    headless=true    AND
...               New Context
Suite Teardown    Close Browser

*** Test Cases ***

Audit Page Renders Header
    [Tags]    audit
    New Page    ${FRONTEND_URL}/audit
    Wait For Load State    networkidle
    Get Element    text=Audit Events
    Get Element    text=Append-only event log

Audit Page Without Token Shows Error
    [Tags]    audit
    New Page    ${FRONTEND_URL}/audit
    Wait For Load State    networkidle
    Clear Token From Storage
    Reload
    Wait For Load State    networkidle
    Get Element    text=Not signed in

Audit Filter Form Has All Fields
    [Tags]    audit    filters
    New Page    ${FRONTEND_URL}/audit
    Wait For Load State    networkidle
    Get Element    text=Category
    Get Element    text=Action
    Get Element    text=Outcome
    Get Element    text=User ID
    Get Element    text=Session ID
    Get Element    css=button:has-text("Apply")
    Get Element    css=button:has-text("Clear")

Audit Table Loads With Auth
    [Tags]    audit    table
    New Page    ${FRONTEND_URL}/audit
    Wait For Load State    networkidle
    Login Via API And Store Token
    Reload
    Wait For Load State    networkidle
    Wait For Elements State
    ...    css=table, text=No events, text=Not signed in, text=Could not load
    ...    visible    timeout=10s
    ${has_table}=    Run Keyword And Return Status    Get Element    css=table
    ${has_empty}=    Run Keyword And Return Status    Get Element    text=No events
    Should Be True    ${has_table} or ${has_empty}

Audit Table Has Correct Columns
    [Tags]    audit    table
    New Page    ${FRONTEND_URL}/audit
    Wait For Load State    networkidle
    Login Via API And Store Token
    Reload
    Wait For Load State    networkidle
    Wait For Elements State    css=table    visible    timeout=10s
    Get Element    text=When
    Get Element    text=Category
    Get Element    text=Action
    Get Element    text=Outcome
    Get Element    text=Target
    Get Element    text=User

Login Action Creates Audit Event
    [Tags]    audit    table
    [Documentation]    Login via UI generates an audit event; it appears in the events table.
    # Sign in via IAM page (generates iam audit event)
    New Page    ${FRONTEND_URL}/iam
    Wait For Load State    networkidle
    Fill Text    id=username    ${ADMIN_USER}
    Fill Text    id=password    ${ADMIN_PASS}
    Click    css=button[type="submit"]
    Wait For Load State    networkidle
    Get Element    css=[class*="success"]
    # Navigate to audit page — token is now in localStorage
    New Page    ${FRONTEND_URL}/audit
    Wait For Load State    networkidle
    Login Via API And Store Token
    Reload
    Wait For Load State    networkidle
    Wait For Elements State    css=tbody tr    visible    timeout=10s
    Get Element    css=tbody tr

Filter By Category IAM
    [Tags]    audit    filters
    New Page    ${FRONTEND_URL}/audit
    Wait For Load State    networkidle
    Login Via API And Store Token
    Reload
    Wait For Load State    networkidle
    Fill Text    css=input[placeholder="iam, vault, audit…"]    iam
    Click    css=button:has-text("Apply")
    Wait For Load State    networkidle
    ${has_rows}=    Run Keyword And Return Status    Get Element    css=tbody tr
    ${has_empty}=    Run Keyword And Return Status    Get Element    text=No events
    Should Be True    ${has_rows} or ${has_empty}

Clear Filters Resets Form
    [Tags]    audit    filters
    New Page    ${FRONTEND_URL}/audit
    Wait For Load State    networkidle
    Login Via API And Store Token
    Reload
    Wait For Load State    networkidle
    Fill Text    css=input[placeholder="iam, vault, audit…"]    iam
    Fill Text    css=input[placeholder="success / failure"]    success
    Click    css=button:has-text("Clear")
    Wait For Load State    networkidle
    ${cat}=    Get Property    css=input[placeholder="iam, vault, audit…"]    value
    Should Be Equal    ${cat}    ${EMPTY}
    ${outcome}=    Get Property    css=input[placeholder="success / failure"]    value
    Should Be Equal    ${outcome}    ${EMPTY}

Filter By Outcome Failure Shows Only Failure Rows
    [Tags]    audit    filters
    New Page    ${FRONTEND_URL}/audit
    Wait For Load State    networkidle
    Login Via API And Store Token
    Reload
    Wait For Load State    networkidle
    Fill Text    css=input[placeholder="success / failure"]    failure
    Click    css=button:has-text("Apply")
    Wait For Load State    networkidle
    ${rows}=    Get Elements    css=tbody tr
    IF    len($rows) > 0
        ${success_badges}=    Get Elements    css=tbody td:has-text("success")
        Length Should Be    ${success_badges}    0
    END

Event Rows Show Category Badge
    [Tags]    audit    table
    New Page    ${FRONTEND_URL}/audit
    Wait For Load State    networkidle
    Login Via API And Store Token
    Reload
    Wait For Load State    networkidle
    Wait For Elements State    css=tbody tr    visible    timeout=10s
    Get Element    css=tbody tr:first-child td:nth-child(2) span
