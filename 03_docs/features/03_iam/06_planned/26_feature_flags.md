## Planned: Feature Flags — Scoped, Categorized, Product-Linked

**Severity if unbuilt:** LOW for security; HIGH for product (no controlled rollouts)
**Depends on:** Foundation sprint (scopes + categories + products + feature registry — see `27_products_catalog.md`, `28_feature_registry.md`, `29_categories_and_scopes.md`), RBAC (`16_rbac.md`)

## Problem

Every code change ships to 100% of users simultaneously — no staged
rollouts, no kill switches, no A/B tests. Additionally, flags must be
introspectable: given a product, we must be able to answer "which flags
affect it?", "which are at workspace scope?", "which are experiments vs
kill switches?", "what's the rollout status in prod?".

## Design

A feature flag carries **every dimension the platform cares about**:

- **Product** (`product_id` FK) — which product owns the flag
- **Feature** (`feature_id` FK, optional) — the specific feature in the registry that this flag gates
- **Scope** (`scope_id` FK `dim_scopes`) — platform / org / workspace
- **Category** (`category_id` FK `dim_categories` type=flag) — kill_switch / rollout / experiment / ops / permission_gate
- **Type** (`flag_type`) — boolean / percentage / variant / kill_switch / experiment
- **Status** (`status`) — draft / active / deprecated / archived
- **Environment** (via `40_lnk_flag_environments`) — dev / staging / prod overrides

## Scope when built

### DB tables

New sub-feature (likely `30_feature_flags` under `03_iam`, or graduate to a
new top-level module `05_product_ops` — see note at end):

#### Core flag

```
10_fct_feature_flags
  id              VARCHAR(36) PK         -- UUID v7
  code            VARCHAR(96) UNIQUE     -- 'vault.new_cipher_ui'
  name            VARCHAR(128)
  product_id      VARCHAR(36) FK fct_products        NOT NULL
  feature_id      VARCHAR(36) FK fct_features        NULL
  scope_id        SMALLINT   FK dim_scopes           NOT NULL
  category_id     SMALLINT   FK dim_categories       NOT NULL  -- category_type='flag'
  flag_type       VARCHAR(24)   -- 'boolean' | 'percentage' | 'variant' | 'kill_switch' | 'experiment'
  status          VARCHAR(16)   -- 'draft' | 'active' | 'deprecated' | 'archived'
  default_value   JSONB         -- fallback when no targeting matches
  is_active, deleted_at, created_by, updated_by, created_at, updated_at
```

EAV attrs (entity_type = `platform_feature_flag`):
`description, owner_user_id, jira_ticket, launch_date, sunset_date, rollout_percentage, notes`.

#### Environments

```
06_dim_environments
  environment_id SMALLINT IDENTITY PK
  code           VARCHAR(24) UNIQUE  -- 'dev' | 'staging' | 'prod'
  label          VARCHAR(64)

40_lnk_flag_environments
  id              VARCHAR(36) PK
  flag_id         VARCHAR(36) FK fct_feature_flags
  environment_id  SMALLINT   FK dim_environments
  enabled         BOOLEAN
  value           JSONB
  UNIQUE (flag_id, environment_id)
```

#### Targeting — three tables, one per scope

```
40_lnk_flag_platform_targets
  id, flag_id, value JSONB, created_at

40_lnk_flag_org_targets
  id, flag_id, org_id, value JSONB, created_at
  UNIQUE (flag_id, org_id)

40_lnk_flag_workspace_targets
  id, flag_id, org_id, workspace_id, value JSONB, created_at
  UNIQUE (flag_id, workspace_id)
```

Only the table matching the flag's `scope_id` may receive rows. Enforcement is service-layer (simpler than a multi-table CHECK trigger).

### Endpoints

```
# Flag CRUD
POST   /v1/feature-flags                   — create (requires product_id, scope_id, category_id)
GET    /v1/feature-flags                   — list (filters: product_id, scope_id, category_id, status, flag_type)
GET    /v1/feature-flags/{id}
PATCH  /v1/feature-flags/{id}
DELETE /v1/feature-flags/{id}              — soft-delete

# Environment values
GET    /v1/feature-flags/{id}/environments
PUT    /v1/feature-flags/{id}/environments/{env_code}    — { enabled, value }

# Targeting
GET    /v1/feature-flags/{id}/targets
POST   /v1/feature-flags/{id}/targets      — body varies by scope
DELETE /v1/feature-flags/{id}/targets/{target_id}

# Evaluation
POST   /v1/feature-flags/eval
    body: { flag_code, context: { user_id, org_id?, workspace_id?, environment } }
GET    /v1/feature-flags/bootstrap?environment=prod&workspace_id=...

# Introspection
GET    /v1/feature-flags/by-product/{product_id}
GET    /v1/feature-flags/by-feature/{feature_id}
```

### Seeded categories (from `dim_categories` where `category_type='flag'`)

`kill_switch`, `rollout`, `experiment`, `ops`, `permission_gate`

### Build order

1. **Phase 1 — Core**: flag CRUD with product + scope + category required, default_value, bootstrap endpoint, environment overrides.
2. **Phase 2 — Targeting**: three targeting tables, eval endpoint with percentage rollout (consistent hash), identity targets.
3. **Phase 3 — Advanced**: variants, segments, change history, SDK tokens, webhooks on change, approval workflows.

## Note on module ownership

Feature flags, products, and the feature registry together form a natural
"product operations" module. On build, consider graduating these three out
of IAM into a new top-level module `05_product_ops`. IAM is already large
and these concerns are cross-cutting. Decision deferred to implementation
sprint.

## Not in scope here

- A/B experiment statistical analysis
- Streaming / SSE real-time flag updates
- Client-side SDK npm package
- Cross-environment promotion workflows
