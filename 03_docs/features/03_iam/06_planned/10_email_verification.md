## Planned: First Admin Email Verification

**Severity if unbuilt:** MEDIUM
**Depends on:** `06_notify` (email delivery), future password reset

## Problem

The install wizard accepts the admin email, validates it with Pydantic
`EmailStr`, and stores it. It never confirms the address is reachable. A
typo means future password reset emails go nowhere.

## Fix when built

At the end of Phase 3 of the install wizard, before writing `installed_at`
to `system_meta`:
1. Generate a one-time verification token (32-byte URL-safe random).
2. Send an email to the provided address with a link:
   `https://{host}/v1/auth/verify-email?token=<token>`.
3. Store the token hash in a new `email_verification_tokens` table (or as
   an EAV attr) with a 24h expiry.
4. Block `GET /v1/auth/login` (or return a warning banner) until the email
   is verified.
5. `GET /v1/auth/verify-email?token=<token>` — validates the token, sets
   `email_verified_at` on the user, writes `installed_at` to `system_meta`.

## Dependency note

Requires `06_notify` email delivery to be built first, or a simpler fallback
(print the verification URL to stdout during install for operators who don't
have email configured yet).
