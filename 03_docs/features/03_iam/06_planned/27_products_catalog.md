## Planned: Products Catalog

**Severity if unbuilt:** HIGH for product strategy (cannot distinguish which product a workspace uses; cannot sell multiple products on one platform)
**Depends on:** Foundation sprint (`29_categories_and_scopes.md`)
**Part of:** Foundation sprint (Sprint 2 of revised plan)

## Problem

tennetctl is being built as a control plane that will host **multiple
products** over time (Vault, a MapBuilder on Isis base, future SaaS apps,
internal tools). Today there is no concept of "product" at all. Without it:

- We cannot say which product a workspace is using.
- Feature flags cannot be scoped to a product.
- The feature registry has nothing to root itself in.
- Billing, licensing, and product-level analytics are impossible.

## Design

Products are a **platform-level catalog**. Each product is a sellable (or
internal) unit built on tennetctl. Workspaces subscribe to products via a
many-to-many link (`40_lnk_workspace_products`), so one workspace can use
multiple products and one product can serve many workspaces.

## Scope when built

### DB tables

New sub-feature (likely `28_products` under `03_iam` initially, graduating
to `05_product_ops` later — see note in `26_feature_flags.md`):

**Core product**

```
10_fct_products
  id              VARCHAR(36) PK        -- UUID v7
  code            VARCHAR(64) UNIQUE    -- 'vault', 'mapbuilder', 'isis_core'
  name            VARCHAR(128)
  category_id     SMALLINT FK dim_categories  -- category_type='product'
  is_sellable     BOOLEAN               -- false for internal tools
  is_active       BOOLEAN
  deleted_at, created_by, updated_by, created_at, updated_at
```

EAV attrs (entity_type = `platform_product`):
`description, slug, pricing_tier, website_url, icon, version, status (draft|ga|deprecated|archived), documentation_url, repo_url, owner_user_id`.

**Workspace ↔ Product (many-to-many)**

```
40_lnk_workspace_products
  id              VARCHAR(36) PK
  workspace_id    VARCHAR(36) FK fct_workspaces
  product_id      VARCHAR(36) FK fct_products
  subscribed_at   TIMESTAMPTZ
  subscribed_by   VARCHAR(36) FK fct_users
  is_active       BOOLEAN
  UNIQUE (workspace_id, product_id)
```

### Endpoints

```
# Product catalog (platform-admin only for write)
POST   /v1/products                     — create product
GET    /v1/products                     — list (filters: category_id, is_sellable, status)
GET    /v1/products/{id}
PATCH  /v1/products/{id}
DELETE /v1/products/{id}                — soft-delete

# Workspace subscriptions
GET    /v1/workspaces/{ws_id}/products         — list products the workspace is subscribed to
POST   /v1/workspaces/{ws_id}/products         — { product_id } subscribe
DELETE /v1/workspaces/{ws_id}/products/{id}    — unsubscribe

# Reverse lookup
GET    /v1/products/{id}/workspaces             — which workspaces use this product
```

### Seeded categories (from `dim_categories` where `category_type='product'`)

`core_platform`, `saas_app`, `internal_tool`, `library`

### Seed data

At install time, seed a single internal product row:

- `code='tennetctl_core'`, `name='tennetctl Core Platform'`, `category='core_platform'`, `is_sellable=false`

All existing workspaces are auto-subscribed to `tennetctl_core` at migration
time so nothing breaks.

## Not in scope here

- Billing / subscription management (pricing, invoices, Stripe)
- License key issuance
- Per-product usage metering
- Product-level API quotas
