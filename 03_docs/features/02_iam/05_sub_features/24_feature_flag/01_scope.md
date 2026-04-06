# Feature Flags — Scope

## What it does

A complete feature flag system that controls feature rollout, A/B testing, and targeting across orgs, users, and environments. Replaces LaunchDarkly with a self-hosted, deterministic evaluation engine supporting 22 operators, reusable segments, multivariate variants, and per-environment configs.

## In scope

- Flag CRUD with value types (boolean, int, string, json)
- Deterministic rollout hashing (SHA-256 sticky bucketing)
- Reusable audience segments with typed condition operators
- Targeting rules with priority ordering and scheduled activation
- Multivariate A/B/n variants with weighted distribution
- Per-environment configs (dev/staging/prod)
- Org-level and user-level flag overrides
- Identity targets (include/exclude specific entities)
- Flag prerequisites with circular dependency detection
- Daily evaluation analytics (true/false/total counts)
- Tags for flag organisation
- Bulk evaluation endpoint for SDK bootstrap
- Debug mode showing full resolution trace
- Stale flag detection for hygiene

## Out of scope

- Server-side SDKs (separate sub-feature)
- Browser SDK (separate sub-feature)
- Webhook delivery on flag changes
- ClickHouse analytics backend
- License-gated flags (depends on billing module)

## Acceptance criteria

- [ ] Flags can be created, updated, soft-deleted, and listed with pagination
- [ ] Evaluation engine resolves flags through 7 priority layers
- [ ] Segments support 22 operators including semver and regex
- [ ] Rules can be scheduled with on/off timestamps
- [ ] Variants distribute traffic with weighted bucketing
- [ ] Environment configs override defaults per-env
- [ ] Bootstrap endpoint returns all active flags in one call
- [ ] Debug mode traces full evaluation path
- [ ] Stale flags are surfaced via dedicated endpoint
- [ ] Daily eval counts are tracked and queryable
- [ ] All mutations emit audit events
- [ ] Frontend has list page + 8-tab detail page

## Dependencies

- Depends on: 01_org (org_id FK), 02_user (user_id FK), 90_audit (audit events)
- Depended on by: future SDK sub-features, conditional access policies
