# 08_auth — Decisions

## ADR-001: argon2id for Password Hashing

**Decision**: Use argon2id via `argon2-cffi` for all password hashing.

**Rationale**: OWASP #1 recommendation for 2025/2026. Memory-hard (resists GPU attacks). Won the Password Hashing Competition. The `id` variant is recommended for server-side use.

**Rejected**: bcrypt (72-byte limit, not memory-hard), scrypt (harder to tune), PBKDF2 (not memory-hard).

## ADR-002: HS256 JWT with Single Secret

**Decision**: Use HS256 algorithm with a single `JWT_SECRET` environment variable.

**Rationale**: Simplest secure option for MVP. No key rotation complexity. Adequate for single-instance deployment. Can upgrade to RS256 with key pairs when multi-service JWT validation is needed.

## ADR-003: No Open Registration

**Decision**: Remove public `/register` page. Only the first user is created via `/setup`. Additional users are created by admins via the user management UI.

**Rationale**: tennetctl is an admin-controlled platform, not a self-service SaaS. Open registration would be a security risk for on-premise deployments.

## ADR-004: First-User-Is-Admin Pattern

**Decision**: The first user created via `/setup` is automatically the administrator. The setup endpoint returns 403 after the first user exists.

**Rationale**: Common pattern in open-source admin tools (Grafana, Metabase, Gitea). Zero-config onboarding — deploy, navigate to URL, create admin, done.

## ADR-005: Session Revoke-Not-Delete Lifecycle

**Decision**: Sessions have `revoked_at` instead of `deleted_at`. Sessions are never deleted from the database.

**Rationale**: Audit trail integrity — you can always see when a session was created and when it was revoked. No data loss on logout.
