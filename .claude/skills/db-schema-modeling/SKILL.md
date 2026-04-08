---
name: db-schema-modeling
description: Design database schemas with discipline. Use when creating tables, writing migrations, or deciding how to store new data.
origin: custom
---

# Database Schema Modeling

Every table must justify its existence. Prefer extending over creating. Keep schemas lean, extensible, and auditable from day one.

## When to Activate

- Designing new database tables
- Writing SQL migrations
- Deciding how to store a new entity or attribute
- Extending an existing entity with new properties

## Decision Gate: Do I Need a New Table?

Walk through these gates in order before creating anything:

1. Does an existing table already serve this purpose? → Use it.
2. Can this be a column on an existing entity table? → Add the column.
3. Can this be a CHECK constraint instead of a lookup table? (≤7 static values, no metadata) → Use CHECK.
4. Can this be a key-value extension row (EAV)? → Add attribute rows instead of a column.
5. None of the above → Create the table, justify it in the migration comment.

## Table Type Patterns

There are five recurring patterns. Match the right one before writing DDL:

**Lookup tables** — Seeded at creation, rarely changed. Primary key is a `code` (TEXT), not a surrogate ID. Shared across domains. Never delete rows — use `deprecated_at`.

**Entity tables** — Core business objects. Structural columns only (identity, relationships, status). Columns that vary or grow go in extension tables. Standard audit columns: `id`, `is_active`, `deleted_at`, `created_by`, `updated_by`, `created_at`, `updated_at`.

**Extension tables (EAV)** — Key-value pairs that extend an entity without schema changes. One extension table per entity. Adding a new attribute means inserting a row, not a migration.

**Junction tables** — Many-to-many relationships. Composite PK on the two FK columns. Immutable rows — no `updated_at`. Include `created_at` and `created_by` for traceability.

**Event/audit tables** — Append-only logs. Never UPDATE or DELETE. No `updated_at`, no `deleted_at`. Partition by `created_at` for large tables.

## Schema Organization

One schema per bounded context. Shared lookups live in a `shared` schema. Audit logs live in a dedicated schema. Never duplicate shared lookups across domain schemas.

## EAV Pattern

Extension tables store attributes as typed value columns: `value_text`, `value_int`, `value_bool`, `value_date`, `value_json`. Register attributes in a central attribute registry before use — track data type, domain, PII classification, and whether required.

When choosing between a new column, EAV, or JSONB: default to EAV for properties that grow or vary per instance. JSONB for truly schemaless blobs. Columns only for stable, universal properties.

## Views

Views flatten entity + extension tables for API consumption. Services query views, not raw tables. Always filter `WHERE deleted_at IS NULL`. Never put business logic in views.

## Migration Rules

- File format: `YYYYMMDD_{NNN}_{description}.sql` with UP and DOWN sections
- DOWN must completely revert UP
- Seed lookup data in the same migration as the table
- Comment on every table and column
- Name all constraints explicitly: `pk_`, `fk_`, `uq_`, `chk_`, `idx_`, `trg_`
