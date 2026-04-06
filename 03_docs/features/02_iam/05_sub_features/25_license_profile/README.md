# 25 — License Profiles

Per-org and per-workspace license tier assignment with feature flag entitlements.

## Tables
- `08_dim_license_tiers` — lookup: free, starter, pro, enterprise, internal (from migration 014)
- `58_fct_license_profiles` — specific limit configurations per tier (feature_limits JSONB)
- `59_lnk_org_license` — one active profile per org (upsert on org_id)
- `60_lnk_workspace_license` — optional per-workspace override (falls back to org)
- `61_lnk_license_flag_entitlements` — which flags each tier grants (with optional value override)
- `v_org_licenses` — view resolving org → profile → tier
- `v_license_flag_entitlements` — view resolving tier → flag with COALESCE(flag_value, default_value)

## API

### Profiles
- `GET/POST /v1/license-profiles` — list/create
- `GET/PATCH/DELETE /v1/license-profiles/{id}` — CRUD

### Org License
- `GET /v1/orgs/{org_id}/license` — get org's current license
- `PUT /v1/orgs/{org_id}/license` — assign profile to org
- `DELETE /v1/orgs/{org_id}/license` — remove
- `GET /v1/orgs/{org_id}/license/entitlements` — resolved flag entitlements

### Workspace License
- `GET/PUT/DELETE /v1/workspaces/{ws_id}/license` — same pattern

### Tier Entitlements
- `GET /v1/license-tiers/{tier_id}/flags` — flags granted by tier
- `POST /v1/license-tiers/{tier_id}/flags` — link flag to tier
- `DELETE /v1/license-tiers/{tier_id}/flags/{flag_id}` — unlink

## How It Works

1. Create profiles with tier + feature_limits JSONB
2. Assign profile to org (`PUT /v1/orgs/{id}/license`)
3. Link flags to tiers (`POST /v1/license-tiers/{tier_id}/flags`)
4. Query entitlements: `GET /v1/orgs/{id}/license/entitlements` returns resolved flag values
5. Metered flags check quota via `POST /v1/feature-flags/{id}/usage`

## Seeded Data
- 4 default profiles (Free/Starter/Pro/Enterprise) with limits
- Free: 5 users, 2 workspaces, 10 flags, no SSO
- Enterprise: unlimited everything, SSO, MFA, custom roles

## Migration
`20260404_015_iam_license_profiles.sql`
