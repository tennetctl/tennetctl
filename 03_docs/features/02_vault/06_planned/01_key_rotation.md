## Planned: Key Rotation

**Severity if unbuilt:** HIGH (long-lived keys are a breach amplifier)
**Depends on:** vault sub-feature (built), JWT RS256 plan (03_iam/06_planned/19_jwt_rs256.md)

## Problem

Three long-lived keys exist with no rotation mechanism:

1. **MDK** (master data key) — encrypts all vault secrets
2. **wrap_key** — derived from DB password + unseal_salt, encrypts MDK at rest
3. **JWT signing key** — signs all access tokens

If any of these leaks, all encrypted data or all active sessions are
compromised indefinitely.

## Scope when built

### 1. JWT key rotation

- Store JWT key pair in vault as versioned secrets:
  `tennetctl/iam/jwt_signing_key/v{N}` (private) and `.../jwt_verify_key/v{N}` (public).
- Add `kid` (key ID) claim to JWTs: `kid = "v{N}"`.
- `verify_token` tries current version first, falls back to previous version
  for a configurable overlap window (default 24h).
- Admin endpoint: `POST /v1/vault/rotate/jwt-key` — generates new key pair,
  bumps version, stores both, starts overlap window.

### 2. MDK re-encryption

- MDK is encrypted with wrap_key. Rotating wrap_key means re-encrypting MDK.
- `POST /v1/vault/rotate/wrap-key`:
  1. Derive new wrap_key from new salt (stored in system_meta).
  2. Decrypt MDK with old wrap_key.
  3. Re-encrypt MDK with new wrap_key.
  4. Update vault row atomically.
  5. Wipe old wrap_key from memory.

### 3. Secret re-encryption (full MDK rotation)

- `POST /v1/vault/rotate/mdk` (admin only):
  1. Generate new MDK.
  2. Re-encrypt every secret in `02_vault.10_fct_secrets` with new MDK
     (one-by-one in a transaction per batch of 100).
  3. Swap MDK in memory and in vault row atomically.
  4. Old MDK is zeroed from memory.

### Rules

- All rotation endpoints require platform_admin role.
- Every rotation emits a `vault.key_rotation` audit event.
- Rotation is non-destructive: old key not deleted until overlap window closes.
- Rotation is idempotent: re-running is safe.

### Settings keys

```
vault.jwt_key_overlap_hours      default: 24
vault.rotation_batch_size        default: 100
```

## Not in scope here

- KMS integration (Azure Key Vault, AWS KMS, GCP KMS) — external key management
- Hardware Security Module (HSM) support
- Automatic scheduled rotation (rotation daemon)
