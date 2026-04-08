*** Settings ***
Documentation     Vault — status page, seal page, unseal page end to end.
...
...               Vault status is public — no auth required.
Resource          ../resources/common.resource

Suite Setup       Run Keywords
...               New Browser    headless=true    AND
...               New Context
Suite Teardown    Close Browser

*** Test Cases ***

Vault Status Page Renders Header
    [Tags]    vault    status
    New Page    ${FRONTEND_URL}/vault
    Wait For Load State    networkidle
    Get Element    text=Vault Status
    Get Element    text=Seal state, initialization, and unseal mode.

Vault Status Card Appears
    [Tags]    vault    status
    New Page    ${FRONTEND_URL}/vault
    Wait For Load State    networkidle
    # Wait for either card data (dl) or error banner — not a blank page
    Wait For Elements State
    ...    css=dl, css=[class*="danger"], text=Network error
    ...    visible    timeout=10s
    ${has_card}=    Run Keyword And Return Status    Get Element    css=dl
    ${has_error}=    Run Keyword And Return Status    Get Element    css=[class*="danger"]
    Should Be True    ${has_card} or ${has_error}

Vault Status Card Shows Initialized
    [Tags]    vault    status
    New Page    ${FRONTEND_URL}/vault
    Wait For Load State    networkidle
    Wait For Elements State    css=dl    visible    timeout=10s
    Get Element    text=Initialized

Vault Status Card Shows Unseal Mode
    [Tags]    vault    status
    New Page    ${FRONTEND_URL}/vault
    Wait For Load State    networkidle
    Wait For Elements State    css=dl    visible    timeout=10s
    Get Element    text=Unseal mode

Vault Status Shows Unsealed Badge
    [Tags]    vault    status
    New Page    ${FRONTEND_URL}/vault
    Wait For Load State    networkidle
    Wait For Elements State    css=dl    visible    timeout=10s
    # After setup, vault must be unsealed
    Get Element    text=unsealed

Refresh Button Reloads Status
    [Tags]    vault    status
    New Page    ${FRONTEND_URL}/vault
    Wait For Load State    networkidle
    Get Element    css=button:has-text("Refresh")
    Click    css=button:has-text("Refresh")
    Wait For Load State    networkidle
    # Verify card is still shown (not error) after refresh
    Wait For Elements State    css=dl    visible    timeout=10s

Vault Seal Page Renders Header
    [Tags]    vault    seal
    New Page    ${FRONTEND_URL}/vault/seal
    Wait For Load State    networkidle
    Get Element    text=Seal Vault

Vault Seal Page Shows Placeholder With Disabled Button
    [Tags]    vault    seal
    New Page    ${FRONTEND_URL}/vault/seal
    Wait For Load State    networkidle
    Get Element    text=Seal operation not wired yet
    ${btn}=    Get Element    css=button:has-text("Seal vault")
    ${disabled}=    Get Property    ${btn}    disabled
    Should Be True    ${disabled}

Vault Unseal Page Renders Header
    [Tags]    vault    unseal
    New Page    ${FRONTEND_URL}/vault/unseal
    Wait For Load State    networkidle
    Get Element    text=Unseal Vault

Vault Unseal Page Shows Placeholder With Disabled Button
    [Tags]    vault    unseal
    New Page    ${FRONTEND_URL}/vault/unseal
    Wait For Load State    networkidle
    Get Element    text=Unseal flow not wired yet
    ${btn}=    Get Element    css=button:has-text("Begin unseal")
    ${disabled}=    Get Property    ${btn}    disabled
    Should Be True    ${disabled}
