## Planned: Stronger Password Policy

**Severity if unbuilt:** MEDIUM
**Affects:** `00_setup/03_first_admin` wizard + future `PATCH /v1/auth/password`

## Problem

Current minimum is 12 characters with at least one non-letter. `aaaaaaaaaaaa1`
passes. No check for dictionary words, keyboard walks, or common patterns.

## Fix when built

- Raise minimum to **16 characters**.
- Add `zxcvbn` (Python port: `zxcvbn-python`) to score the password.
  Reject scores 0–2 ("too weak"). Show the failure reason to the user
  (e.g., "This looks like a common pattern — try adding unrelated words").
- Apply the same rules in the install wizard and `PATCH /v1/auth/password`.
- Store the policy version in `system_meta` so future audits can identify
  accounts created under old rules.

## Not in scope

Mandatory periodic password rotation (NIST SP 800-63B explicitly advises
against forced rotation without evidence of compromise — not implementing).
