## Planned: Password Reset + Email Verification

**Severity if unbuilt:** CRITICAL (users have no self-service recovery path)
**Depends on:** notifications module (email delivery), email_verification already has
a partial plan in 10_email_verification.md — this extends it with reset

## Problem

No password reset flow exists. If an admin forgets their password, recovery
requires direct DB intervention. Email addresses are stored but never
verified, so they cannot be trusted for reset links.

## Scope when built

### Password reset

```
POST /v1/auth/forgot-password
  Body: { "email": "..." }
  Effect: Generate a short-lived (15min) BLAKE2b-hashed reset token,
          store in dtl_attrs, fire email via notifications module.
  Response: 202 always (no user enumeration)

POST /v1/auth/reset-password
  Body: { "token": "...", "new_password": "..." }
  Effect: Validate token (expiry + hash), hash new password with Argon2id,
          upsert password_hash attr, invalidate all sessions, delete token.
  Response: 200 on success, 400 on bad/expired token
```

### Email verification

```
POST /v1/auth/verify-email
  Body: { "token": "..." }
  Effect: Mark email_verified attr = true, delete token.

POST /v1/auth/resend-verification
  Body: { "email": "..." }
  Effect: Re-fire verification email. Rate-limited (1 per 60s per email).
  Response: 202 always
```

### Token storage

Reset and verification tokens stored as EAV attrs on the user:
- `password_reset_token_hash` (BLAKE2b-256 of the raw token)
- `password_reset_expires_at` (TIMESTAMP)
- `email_verification_token_hash`
- `email_verification_expires_at`

### Security rules

- Raw token is 32 bytes from `secrets.token_bytes(32)`, URL-safe base64 encoded.
- Only the hash is stored — same pattern as refresh tokens.
- Token is single-use: deleted immediately after first valid consumption.
- Expiry checked in constant time alongside hash comparison.
- Every password reset emits an audit event (`iam.user.password_reset`).
- Reset invalidates all active sessions for the user.

## Not in scope here

- Magic-link (passwordless) login — separate item
- SMS OTP reset — requires SMS provider integration
