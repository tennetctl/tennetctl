# ADR-009: Open Source Under MIT License

**Status:** Accepted
**Date:** 2026-03-29

---

## Context

tennetctl has been under private development. The codebase is now mature enough across IAM, Audit, Vault, and Monitoring to be useful to the broader developer community. The question was whether to open source it, and if so under which license.

Options considered:
1. **MIT** — permissive, no conditions on use
2. **Apache 2.0** — permissive with explicit patent grant
3. **AGPL** — copyleft, requires derivative works to be open source
4. **BSL (Business Source License)** — delayed open source (converts to open source after N years)
5. **Source-available** — public but not open source (non-commercial clause)

---

## Decision

**Open source under MIT.**

---

## Rationale

**Why open source at all:**
tennetctl solves a universal problem. Solo developers and small teams everywhere are assembling the same 20-tool stack. Keeping the solution proprietary means fewer people benefit from it and fewer people improve it. The network effects of an open community outweigh any revenue protection that closed-source provides at this stage.

**Why MIT over AGPL:**
AGPL requires derivative works that are served over a network to be open sourced. This would prevent companies from hosting tennetctl as a service without open-sourcing their modifications. While this sounds protective, in practice it discourages corporate adoption and contribution. The ethos of tennetctl is that the community benefits from working together — including companies. MIT removes that friction.

**Why MIT over Apache 2.0:**
Both are permissive. Apache 2.0 adds an explicit patent grant, which matters at large scale. For a project at this stage, MIT is simpler and more universally understood. If patent exposure becomes a real concern, the license can be changed before it matters.

**Why MIT over BSL:**
BSL is marketed as open source but is not recognized as such by OSI. It confuses contributors and creates legal ambiguity. tennetctl's ethos (see `02_ethos.md`) commits to genuinely open. BSL is not genuine open source.

**Sustainability model:**
The project sustains itself through commercial hosting, support contracts, and enterprise services — not through paywalled features or a dual-license. This is the model that has worked for PostgreSQL, Redis (pre-license change), and Grafana. Features shipped in the open source version will never be moved to a commercial edition.

---

## Consequences

- `LICENSE` (MIT) added to repository root.
- `README.md` added to repository root with badge, quick start, and contribution guide.
- All contributions going forward are licensed under MIT.
- Commercial forks are permitted. We consider this acceptable — the community and ecosystem benefits outweigh the risk of a fork outcompeting the original.
- The project GitHub will be public once the repository is transferred/created.
