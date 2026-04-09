## Planned: MFA / TOTP

**Severity if unbuilt:** HIGH (no second factor for admin accounts)
**Depends on:** auth sub-feature (sessions), settings (to make MFA mandatory per org)

## Problem

Authentication is single-factor (password only). A compromised password
gives full account access. TOTP is the minimum viable second factor for
admin-level accounts.

## Scope when built

### DB tables (new sub-feature `11_mfa` under `03_iam`)

- `10_fct_mfa_devices` — id, user_id, type_id, is_active, verified_at, deleted_at, ...
- `06_dim_mfa_types` — totp, backup_code, webauthn (future)
- `20_dtl_attrs` — totp_secret (encrypted), backup_codes (hashed list)

### Endpoints

```
POST   /v1/auth/mfa/enroll          — generate TOTP secret, return QR URI
POST   /v1/auth/mfa/verify-enroll   — confirm first TOTP code to activate
GET    /v1/auth/mfa/devices         — list enrolled devices for calling user
DELETE /v1/auth/mfa/devices/{id}    — remove device

POST   /v1/auth/mfa/challenge       — after password OK, return { mfa_required: true, challenge_token }
POST   /v1/auth/mfa/respond         — submit TOTP code + challenge_token → full session token

POST   /v1/auth/mfa/backup-codes    — regenerate backup codes (invalidates old set)
POST   /v1/auth/mfa/backup-codes/use — consume one backup code
```

### Login flow change

1. `POST /v1/sessions` — if user has an active MFA device, return
   `{ "mfa_required": true, "challenge_token": "..." }` (short-lived, 5min).
2. `POST /v1/auth/mfa/respond` — validate TOTP + challenge_token → return
   full access_token + refresh_token pair.

### TOTP secret storage

TOTP secret encrypted with MDK via AES-256-GCM (same pattern as vault secrets).
Never returned in plaintext after enroll.

### Backup codes

10 codes generated as `secrets.token_hex(8)`. Each stored as BLAKE2b hash.
Single-use, marked consumed on use. Regenerating invalidates all old codes.

### Settings keys

```
iam.mfa_required_for_platform_admin   default: false (enable before GA)
iam.mfa_required_for_org_admin        default: false
```

## Not in scope here

- WebAuthn / FIDO2 passkeys
- SMS OTP
- Hardware security keys (FIDO U2F)
