---
name: security-review
description: Review code for security vulnerabilities. Use when adding auth, handling user input, creating API endpoints, or working with sensitive data.
origin: custom
---

# Security Review

Review changed code for vulnerabilities. Focus on what's actually in the diff, not generic checklists. Claude already knows OWASP Top 10 — this skill covers high-value rules that are easy to miss in practice.

## When to Activate

- Implementing authentication or authorization
- Handling user input or file uploads
- Creating new API endpoints
- Working with secrets or credentials
- Storing or transmitting sensitive data

## Key Security Rules

**SQL injection:** All queries must be parameterized. Never interpolate user input into SQL strings.

**Authentication:** Every route that handles sensitive data must have auth middleware/guards explicitly declared. No implicit protection.

**Secrets:** Environment variables only, validated at application startup. Never hardcoded, never in git, never logged.

**Audit logging:** Every state-changing operation on sensitive data should produce an audit trail. No silent mutations.

**Error handling:** Error messages returned to clients must not leak internal state, stack traces, or database details.

**Data classification:** PII must be masked in all log output. Sensitive fields should be tagged with classification comments in the schema.

**Rate limiting:** All public-facing auth and mutation endpoints must have rate limiting.

**Input validation:** All user input validated at the boundary (entry point of the system). Never trust raw input deeper in the stack.

## Severity Levels

- **CRITICAL:** Exploitable now (SQL injection, exposed secrets, missing auth on sensitive endpoint). Stop everything and fix immediately.
- **HIGH:** Significant risk (missing rate limiting on auth endpoint, PII in logs). Fix before merge.
- **MEDIUM:** Should be addressed (missing input validation on non-sensitive field). Fix in this PR if easy, otherwise track.
- **LOW:** Best practice improvement. Note for future.
