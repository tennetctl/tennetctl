## Planned: Password Change

**Severity if unbuilt:** CRITICAL (post-install the admin password is immutable)
**Depends on:** v1 auth (login, session middleware)

## Problem

After install the first admin's password can only be changed by deleting the
`password_hash` EAV row and re-running `tennetctl setup --resume`. There is
no HTTP endpoint. If the password is compromised the operator has no
self-service recovery path.

## Scope when built

### Endpoint

`PATCH /v1/auth/password`

Request body:
```json
{ "current_password": "...", "new_password": "..." }
```

Response: 204 on success.

### Rules

- Requires a valid session (session middleware enforces this).
- Verify `current_password` against the stored Argon2id hash before
  accepting the change — prevents an attacker with a stolen session from
  locking the real user out.
- Hash `new_password` with current Argon2id params.
- Update the `password_hash` EAV row for the user (`20_dtl_attrs` where
  `attr_def.code = 'password_hash'`).
- Revoke ALL other active sessions for this user immediately after the
  change (force re-login on all other devices). Keep the current session
  alive so the operator is not instantly logged out.
- Emit `iam.user.password_changed` audit event (no password material in
  the event payload).

### Validation

- `new_password` min length: same as install-time policy (see
  `09_password_policy.md`).
- `new_password` must differ from `current_password`.

### Admin reset (future)

Admin-forced password reset (`PATCH /v1/users/{id}/password` with
`{ "new_password": "..." }`) lives in the future `03_iam.02_users`
sub-feature, not here.
