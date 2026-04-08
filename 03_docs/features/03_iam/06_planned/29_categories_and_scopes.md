## Planned: Categories and Scopes (Shared Enums)

Severity: HIGH — every role, feature, flag, and product depends on these two tables; must be seeded first.
Depends on: nothing (root of the foundation sprint).
Part of: Foundation sprint (Sprint 2 of revised plan) — build this before products, feature registry, or anything downstream.

## Problem

Today the codebase uses `scope` loosely. `org_id` and `workspace_id` are stamped onto JWTs but there is no first-class scope enum. Similarly, "category" is not a concept at all. Without shared, seeded, FK-enforced enums, every downstream table (roles, features, flags, products) either duplicates the enum values as CHECK constraints or, worse, stores them as free-text strings that drift over time. Build both as real dim tables.

## Design

### Scopes (06_dim_scopes)

```
06_dim_scopes
  scope_id    SMALLINT IDENTITY PK
  code        VARCHAR(24) UNIQUE
  label       VARCHAR(64)
  description TEXT
```

Seeded with exactly three rows: `platform`, `org`, `workspace`. No other values will ever be added — this set is closed by design. Every table that needs a scope references it via `scope_id SMALLINT FK dim_scopes`, never a VARCHAR column.

### Categories (06_dim_categories)

```
06_dim_categories
  category_id   SMALLINT IDENTITY PK
  category_type VARCHAR(16)   -- 'role' | 'feature' | 'flag' | 'product'
  code          VARCHAR(64)
  label         VARCHAR(128)
  description   TEXT
  is_active     BOOLEAN
  UNIQUE (category_type, code)
```

Discriminator column `category_type` lets one table serve all four domains (role / feature / flag / product). Every `fct_*` table that carries a category uses a CHECK or service-layer guard to ensure `category_id` resolves to the correct `category_type`.

### Seeded categories

role:

```
system, security, billing, content, support, ops
```

feature:

```
iam, vault, audit, billing, observability, maps, rbac, sessions, platform_ops
```

flag:

```
kill_switch, rollout, experiment, ops, permission_gate
```

product:

```
core_platform, saas_app, internal_tool, library
```

## Endpoints

Read-only catalog endpoints since these enums are seed-managed.

```
GET /v1/scopes                                       # list all three scopes
GET /v1/categories?category_type=role|feature|flag|product  # filtered list
```

No write endpoints in phase 1. Seeds are managed via migration files only.

## Enforcement rules

- Every new `fct_*` table that carries a scope MUST reference `dim_scopes.scope_id`, never a VARCHAR column.
- Every new `fct_*` table that carries a category MUST reference `dim_categories.category_id` AND validate (via CHECK or service) that the category's `category_type` matches the host table.
- New scope values require a platform-wide decision (the set is closed at three today).
- New category values can be added via migration as needed.

## Not in scope

- Hierarchical categories (parent/child).
- Localized labels.
- Category versioning.
- User-defined custom categories.
