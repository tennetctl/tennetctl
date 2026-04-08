## Planned: Feature Registry

**Severity if unbuilt:** MEDIUM (nothing is broken without it, but introspection and cross-referencing break at scale)
**Depends on:** Foundation sprint (`27_products_catalog.md`, `29_categories_and_scopes.md`)
**Part of:** Foundation sprint (Sprint 2 of the revised plan)

## Problem

Features today exist only as markdown folders under
`03_docs/features/*/05_sub_features/`. Nothing is queryable. When feature
flags, roles, and products need to reference a specific feature ("which
feature does this flag gate?", "which features are workspace-scoped in
product X?"), there is no canonical table to FK to. Build a registry so
every feature and sub-feature is declared with product, scope, category,
and metadata.

## Design

Every feature belongs to exactly one product, has exactly one scope
(`platform`, `org`, or `workspace`), and exactly one category. Sub-features
are modelled as self-references via `parent_id`. Codes are dotted and
unique per product (e.g. `iam.groups`, `vault.secrets.rotate`).

### DB table

```sql
-- 10_fct_features
id            VARCHAR(36) PRIMARY KEY         -- UUID v7
product_id    VARCHAR(36) NOT NULL REFERENCES fct_products(id)
parent_id     VARCHAR(36)     NULL REFERENCES fct_features(id)
code          VARCHAR(96) NOT NULL             -- e.g. 'iam.groups'
name          VARCHAR(160) NOT NULL
scope_id      VARCHAR(36) NOT NULL REFERENCES dim_scopes(id)
category_id   VARCHAR(36) NOT NULL REFERENCES dim_categories(id)
                                               -- category_type='feature'
is_active     BOOLEAN NOT NULL DEFAULT TRUE
deleted_at    TIMESTAMPTZ NULL
created_at    TIMESTAMPTZ NOT NULL
created_by    VARCHAR(36) NOT NULL
updated_at    TIMESTAMPTZ NOT NULL
updated_by    VARCHAR(36) NOT NULL

UNIQUE (product_id, code)
```

### EAV attrs

Under `entity_type='platform_feature'` via `dim_attr_defs` +
`dtl_attrs`:

- `description` — long-form summary
- `status` — `planned | in_progress | ga | deprecated`
- `doc_url` — link to canonical markdown under `03_docs/features/...`
- `owner_user_id` — FK `fct_users`
- `version_introduced` — semver string
- `jira_epic` — external tracker reference

No business columns on `10_fct_features` beyond the ones above; everything
else goes through EAV.

### Endpoints

```
# CRUD
POST   /v1/features
GET    /v1/features                    # filters: product_id, scope_id,
                                       #          category_id, status,
                                       #          parent_id
GET    /v1/features/{id}
PATCH  /v1/features/{id}
DELETE /v1/features/{id}

# Relations
GET    /v1/products/{id}/features      # all features in a product
GET    /v1/features/{id}/children      # sub-features (parent_id = id)
GET    /v1/features/{id}/flags         # flags referencing this feature
```

### Seeded categories

From `dim_categories` where `category_type='feature'`:

`iam`, `vault`, `audit`, `billing`, `observability`, `maps`, `rbac`,
`sessions`, `platform_ops`.

Categories are seeded alongside `29_categories_and_scopes.md`.

### Seed script

On install, walk `03_docs/features/*/05_sub_features/` and auto-register
each sub-feature into `10_fct_features`, rooted under the
`tennetctl_core` product seeded by `27_products_catalog.md`. The folder
name maps to `code`, the parent feature folder maps to `parent_id`, and
`scope_id` / `category_id` default from a small lookup table maintained
next to the seed script.

Future products register their own features via the API; the seed script
only runs for `tennetctl_core`.

## Not in scope

- Dependency graph between features
- Automated feature lifecycle state machine
- Feature-level metrics and usage telemetry
