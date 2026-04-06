# Security Policy

tennetctl is a control plane that handles authentication, secrets, and audit trails. We take security seriously.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, report vulnerabilities privately:

1. Go to [Security Advisories](https://github.com/tennetctl/tennetctl/security/advisories/new) and create a new draft advisory
2. Or email **security@tennetctl.dev** with:
   - Description of the vulnerability
   - Steps to reproduce
   - Impact assessment (what an attacker could do)
   - Affected module (IAM, Vault, Audit, etc.)

## What to expect

- **Acknowledgement** within 48 hours
- **Assessment** within 7 days — we'll confirm whether it's a valid issue and its severity
- **Fix timeline** based on severity:
  - Critical (auth bypass, secret leak, RCE): patch within 72 hours
  - High (privilege escalation, data exposure): patch within 14 days
  - Medium/Low: next scheduled release

## What counts as a security issue

- Authentication or authorization bypass
- Plaintext secret exposure (in logs, responses, or database)
- SQL injection or command injection
- Cross-module data leakage (bypassing schema isolation or RLS)
- Audit trail tampering or gaps in audit event emission
- JWT/token vulnerabilities (forgery, reuse after revocation)
- Cryptographic weaknesses in Vault encryption

## What does NOT count

- Denial of service on a local dev setup
- Issues that require physical access to the server
- Vulnerabilities in dependencies (report those upstream, but let us know so we can update)
- Missing rate limiting on non-sensitive endpoints

## Credit

We will credit reporters in the security advisory and release notes unless you prefer to remain anonymous.

## Supported Versions

tennetctl is pre-1.0. Security fixes are applied to the `main` branch only. There are no backported patches to older versions yet.
