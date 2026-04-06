# Contributing to tennetctl

tennetctl is open source and contributions are very welcome — whether that's a bug report, a fix, a new feature, or improved documentation.

Every change to this project goes through a pull request. That includes changes from the maintainer. No exceptions.

---

## Before you start

Read these three documents first. They are short and will save you from building the wrong thing or having a PR rejected:

- [Vision](03_docs/00_main/01_vision.md) — why tennetctl exists and what it will never become
- [Ethos](03_docs/00_main/02_ethos.md) — the principles behind every design decision
- [Rules](03_docs/00_main/03_rules.md) — hard rules that every PR is checked against

---

## Ways to contribute

### Report a bug

Open a [GitHub Issue](https://github.com/tennetctl/tennetctl/issues/new?template=bug_report.md) using the bug report template. Include steps to reproduce, what you expected, and what actually happened.

### Fix a bug

1. Comment on the issue so nobody duplicates the work
2. Follow the [setup guide](03_docs/00_main/06_setup.md) to get running locally
3. Write a failing test that reproduces the bug
4. Fix it, verify the test passes
5. Open a PR referencing the issue

### Add a feature

1. Check the [roadmap](03_docs/00_main/04_roadmap.md) — pick a sub-feature not yet marked `BUILDING` or `DONE`
2. Open an issue to say you're working on it
3. Follow the [feature workflow](03_docs/00_main/07_adding_a_feature.md)
4. Open a PR when complete

If your idea isn't on the roadmap, open a discussion issue first. Features that don't fit the vision won't be merged regardless of implementation quality — better to find that out before writing code.

### Improve docs

Documentation PRs are always welcome. If something is unclear, incomplete, or wrong — fix it. A PR that changes behaviour must also update the relevant docs.

---

## Development workflow

```bash
# 1. Fork and clone
git clone https://github.com/YOUR_USERNAME/tennetctl.git
cd tennetctl

# 2. Create a branch
git checkout -b feat/your-feature
# Branch types: feat, fix, docs, refactor, test, chore

# 3. Write a failing test first (TDD)
uv run pytest tests/your_module/ -v

# 4. Implement, make it pass, refactor
uv run pytest --cov=. --cov-report=term-missing

# 5. Open a PR
```

Full setup: [03_docs/00_main/06_setup.md](03_docs/00_main/06_setup.md)
Full feature workflow: [03_docs/00_main/07_adding_a_feature.md](03_docs/00_main/07_adding_a_feature.md)

---

## Commit format

```
type: short description

Optional body explaining why, not what.

Closes #123
```

Types: `feat` `fix` `refactor` `docs` `test` `chore` `perf` `ci`

Examples:
```
feat: add passkey registration with WebAuthn
fix: revoke entire token family on refresh token reuse
docs: add vault secret rotation guide
test: cover soft-delete edge case in audit log
```

Rules: lowercase, present tense, no period at the end, under 72 characters.

---

## Pull request checklist

Every PR — including maintainer PRs — is reviewed against the checklist in `.github/PULL_REQUEST_TEMPLATE.md`. The full review criteria are in [03_docs/00_main/05_contributing.md](03_docs/00_main/05_contributing.md).

Key things that will block a merge:

- Tests not written first (TDD is required, not optional)
- Coverage below 80%
- Mutating state in place (always return new objects)
- Skipping the response envelope (`{ "ok": true, "data": {} }`)
- Missing audit event on a mutating operation
- New required dependency introduced (R-004)
- Module importing another module's service layer (R-002)

---

## Review process

This project currently uses self-review. The maintainer opens PRs for every change, reads the diff carefully, and works through the checklist before merging.

As the contributor community grows, peer review will be added. The PR process is already in place so that transition will be seamless.

---

## Questions

Open a [GitHub Discussion](https://github.com/tennetctl/tennetctl/discussions) for questions about how something works or where something belongs. Don't open an issue for questions — issues are for bugs and feature proposals.
