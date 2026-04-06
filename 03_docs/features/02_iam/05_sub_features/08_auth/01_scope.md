# 08_auth — Scope

The Auth sub-feature handles user authentication: registration, login, session management, and the first-run setup wizard. It uses email/password with argon2id hashing and HS256 JWT tokens.

## In Scope
- **Registration**: Create user + credential + session, return JWT pair.
- **Login**: Verify email + password, create session, return JWT pair.
- **Token Refresh**: Rotate access/refresh tokens, revoke old session.
- **Logout**: Revoke current session by JTI.
- **Current User (/me)**: Decode JWT, return user profile.
- **First-Run Setup**: `/v1/auth/setup` — creates the initial admin user when no users exist.
- **Setup Status**: `/v1/auth/setup-status` — returns whether setup is needed.

## Out of Scope
- **OAuth**: Google/GitHub login deferred to future sub-feature.
- **MFA**: TOTP/backup codes deferred to `11_mfa` sub-feature.
- **Magic Links**: Deferred.
- **Password Reset**: Deferred.
- **Session Policies**: Max sessions, idle timeout deferred.

## Security
- Password hashing: argon2id via `argon2-cffi`
- JWT: HS256 with `JWT_SECRET` env var
- Access token TTL: 15 minutes (configurable)
- Refresh token TTL: 30 days (configurable)
- Setup endpoint locked after first user created (403)
- No open registration — admin creates users from dashboard
