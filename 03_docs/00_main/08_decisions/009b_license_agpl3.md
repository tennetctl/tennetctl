# ADR-009b: Change License from MIT to AGPL-3.0

**Status:** Accepted — supersedes ADR-009
**Date:** 2026-04-04

---

## Context

ADR-009 chose MIT when the project was first open-sourced. The rationale at the time was to maximize adoption and minimize friction for corporate contributors.

The project's goals have since sharpened: ss-factory aims to be the canonical all-in-one platform that replaces 30–40 separate SaaS tools. At this scale and ambition, MIT creates a structural problem — any company can take the code, run it as a competing hosted service, and never contribute back. This is exactly what happened to Redis, Elasticsearch, and MongoDB.

---

## Decision

**Change license from MIT to AGPL-3.0.**

---

## Rationale

**Why AGPL-3.0 over MIT:**
MIT permits SaaS freeloading. A company can take ss-factory, host it as "SaaS Factory Pro", charge for access, and have zero obligation to contribute back. AGPL-3.0 closes this: anyone who runs a modified version over a network must release their modifications under AGPL-3.0. Self-hosting and internal use remain unrestricted.

**Why AGPL-3.0 over BSL:**
BSL is not OSI-approved open source. It creates legal ambiguity that discourages contributors and enterprise adoption. ADR-009 correctly identified this. AGPL-3.0 is genuine open source with a strong copyleft.

**Why AGPL-3.0 over Apache 2.0:**
Apache 2.0 is permissive like MIT — it does not prevent SaaS freeloading.

**Corporate use is not blocked:**
Companies can use ss-factory internally without any AGPL obligations. The obligation only triggers when they distribute or serve a modified version to external users. This is the same model that Nextcloud, Grafana (originally), and many successful open-source companies use.

**Sustainability model unchanged:**
The project sustains itself through commercial hosting, support contracts, and enterprise services. AGPL-3.0 strengthens this model by ensuring that anyone offering a competing hosted service must contribute their improvements back to the community.

---

## Consequences

- `LICENSE` updated to AGPL-3.0 text.
- `README.md` badge and license section updated.
- All future contributions are licensed under AGPL-3.0.
- Existing MIT contributions from before this date: contributors are asked (but not legally required) to relicense. Given the small contributor base at this point, this is low risk.
- Commercial forks that self-host internally are permitted.
- Commercial forks that offer the software as a network service must open-source their modifications.
