---
name: "Sub-Feature Build"
about: "Build a new sub-feature end-to-end (use this for every new sub-feature, including your own)"
labels: "feature, sub-feature"
---

## Sub-Feature: {module} / {nn}_{name}

**Module:** `{nn}_{module}` (e.g. `02_iam`)
**Sub-feature:** `{nn}_{name}` (e.g. `08_auth`)
**Owner:** @your-github-username

---

## Scope Lock

> **Write the scope here BEFORE doing anything else.**
> This section is the contract. If something is not listed here, it is not part of this issue.
> If scope changes, edit this section AND add a comment explaining why.

### In scope
- [ ] {Capability 1}
- [ ] {Capability 2}
- [ ] {Capability 3}

### Explicitly out of scope
- {Thing that sounds related but is NOT being built here}
- {Thing that belongs in a different sub-feature}
- {Thing that is a future enhancement, not this build}

### Acceptance criteria (how you know you're done)
- [ ] {Observable, testable outcome 1}
- [ ] {Observable, testable outcome 2}
- [ ] {Observable, testable outcome 3}

---

## Progress

### Phase 1: Docs (can be a separate PR)

- [ ] `01_scope.md` written
- [ ] `02_design.md` written
- [ ] `05_api_contract.yaml` written
- [ ] `sub_feature.manifest.yaml` created (status: `SCOPED`)
- [ ] **GATE: Re-read scope against vision/ethos. Does it belong?**

### Phase 2: Schema

- [ ] Migration SQL written
- [ ] Migration verified locally: `UP → DOWN → UP`
- [ ] Every table + column has `COMMENT`
- [ ] All constraints explicitly named
- [ ] Properties in `dtl_attrs`, not `fct_*` columns
- [ ] No triggers, ENUMs, stored procedures
- [ ] **GATE: Migration round-trips cleanly?**

### Phase 3: Cross-module check

- [ ] New events documented (or confirmed: none)
- [ ] Consumer modules identified (or confirmed: none)
- [ ] New entity_types / scope_types listed (or confirmed: none)

### Phase 4: Implementation

- [ ] Tests written (RED) — pytest + Robot Framework
- [ ] Backend implemented (GREEN) — schemas, repository, service, routes
- [ ] Frontend implemented (if applicable)
- [ ] All tests pass
- [ ] Coverage at 80%+

### Phase 5: Review & Ship

- [ ] Docs updated (scope, design, contract, worklog)
- [ ] Manifest status set to `DONE`
- [ ] Self-review checklist completed (see `09_maintainer_workflow.md`)
- [ ] PR opened with rollback plan
- [ ] PR merged

---

## Scope Creep Log

> If you discover something that needs doing but is NOT in the scope above,
> log it here with a new issue reference. Do NOT add it to this issue.

| Date | Discovery | Action |
| ---- | --------- | ------ |
| | | |

<!-- Example:
| 2026-04-06 | Need rate limiting on this endpoint | Opened #45 as enhancement |
| 2026-04-07 | Realized we need a new dim table for X | Opened #46 as sub-feature |
-->
