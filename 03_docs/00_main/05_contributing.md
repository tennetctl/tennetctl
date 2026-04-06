# Contributing to tennetctl

tennetctl is an open-source project and contributions are welcome. This document explains how the project works, how decisions are made, and how to contribute effectively.

Read `01_vision.md`, `02_ethos.md`, and `03_rules.md` before contributing. Understanding why the project exists and what it values will save you from building the wrong thing.

---

## Code of Conduct

tennetctl follows a simple standard: be direct, be respectful, be constructive.

- Critique code and ideas, not people
- If you disagree with a decision, explain why and propose an alternative
- If you are new, ask questions — there are no stupid questions in good-faith learning
- If a conversation becomes unproductive, step away

Contributors who are consistently disrespectful, dismissive, or bad-faith actors will be removed from the project.

---

## Ways to Contribute

### Report bugs

Open a GitHub issue with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- tennetctl version and environment (OS, Docker version, Postgres version)

### Fix bugs

If you want to fix a reported bug:
1. Comment on the issue to say you're working on it (avoids duplicate work)
2. Follow the setup guide: `06_setup.md`
3. Write a failing test that reproduces the bug
4. Fix the bug
5. Verify the test passes
6. Open a PR referencing the issue

### Add a feature

Features that are on the roadmap are the priority. If you want to work on one:
1. Check `04_roadmap.md` — find a sub-feature that isn't marked `BUILDING` or `DONE`
2. Open an issue saying you want to work on it
3. Follow the feature development workflow in `07_adding_a_feature.md`
4. Open a PR when complete

If you want to add a feature that is not on the roadmap, open a discussion issue first. Describe the use case, the proposed design, and which module it belongs in. Features that do not fit the vision or violate the ethos will not be merged regardless of implementation quality.

### Improve documentation

Documentation PRs are always welcome. If something is unclear, incomplete, or wrong, fix it. Documentation lives alongside the code — a PR that changes behavior must also update the relevant docs.

### Review pull requests

Code review is valuable contribution. If you understand an area of the codebase, review open PRs in that area. Focus on correctness, rule compliance, and clarity — not style preferences.

---

## Development Workflow

### Step 1: Set up your environment

See `06_setup.md` for the full local development setup.

### Step 2: Create a branch

```bash
git checkout -b {type}/{description}
# Examples:
git checkout -b feat/iam-passkeys
git checkout -b fix/session-refresh-race
git checkout -b docs/vault-rotation-guide
```

Branch types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

### Step 3: Follow the feature workflow

See `07_adding_a_feature.md`. In brief:
1. Write the feature doc and get it reviewed before writing code
2. Write tests first (TDD)
3. Implement the feature
4. Run the full test suite
5. Update documentation

### Step 4: Open a pull request

PR title format: `{type}: {short description}`

Examples:
```
feat: add passkey registration and authentication
fix: prevent refresh token reuse after family rotation
docs: add vault secret injection guide
```

PR body must include:
- What this PR does (2-3 sentences)
- Why it's needed (link to issue or context)
- How to test it
- Screenshots if it changes the UI

### Step 5: Address review feedback

- Respond to every comment (either fix it or explain why you disagree)
- Push new commits rather than force-pushing (makes it easier to see what changed)
- Request re-review when you've addressed all feedback

### Step 6: Merge

PRs are merged by maintainers once:
- All review feedback is addressed
- CI is green (lint, type check, tests)
- At least one maintainer has approved

---

## Pull Request Review Checklist

Reviewers check PRs against the following:

**Architecture**
- [ ] No module imports another module's service layer (R-002)
- [ ] No new required dependencies introduced (R-004)
- [ ] Module only queries its own Postgres schema (R-005)

**Code quality**
- [ ] Every new function has a docstring (R-006)
- [ ] No silent error swallowing (R-007)
- [ ] All user input validated at the boundary (R-008)
- [ ] No file exceeds 500 lines (R-009)
- [ ] No hardcoded values (R-010)

**Database**
- [ ] Every new table and column has a COMMENT (R-011)
- [ ] All constraint names are explicit and prefixed (R-012)
- [ ] Migration has both UP and DOWN (R-013)
- [ ] Table naming follows `{nn}_{type}_{name}` convention (R-014)

**Security**
- [ ] No plaintext secrets (R-015)
- [ ] Mutating operations emit audit events (R-016)
- [ ] RLS policies on org-scoped tables (R-017)

**Documentation**
- [ ] Feature manifest updated (R-018)
- [ ] Architectural decisions recorded if applicable (R-019)

---

## Proposing Architecture Changes

Architecture changes that affect multiple modules, cross-module contracts, or technology choices require an Architecture Decision Record (ADR) before implementation.

To propose an architecture change:
1. Open an issue titled `[ADR] {topic}` describing the proposal
2. Wait for discussion and rough consensus before writing an ADR
3. Write the ADR following the format in `08_decisions/`
4. Once the ADR is merged, implementation can begin

Do not implement architecture changes before the ADR is accepted. Code that assumes an unaccepted architectural direction will not be merged.

---

## Commit Message Format

```
{type}: {short description}

{optional body — explain why, not what}

{optional footer — issue references}
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`

Examples:
```
feat: implement passkey registration with WebAuthn

Users can now register passkeys as a primary or secondary authentication method.
Credential is stored in 05_fct_passkeys with public key and sign count.

Closes #142
```

```
fix: revoke entire token family on refresh token reuse

Previously, presenting a revoked refresh token only revoked that token.
A compromised token could be used once before detection. Now, reuse
detection revokes all tokens in the family, forcing re-authentication.

Closes #189
```

---

## Questions

If you have questions about how something works or where something should go, open a GitHub Discussion. Do not open an issue for questions — issues are for bugs and feature proposals.

If you are unsure whether a feature belongs in tennetctl, ask before building it. Building something that won't be merged is a waste of your time.
