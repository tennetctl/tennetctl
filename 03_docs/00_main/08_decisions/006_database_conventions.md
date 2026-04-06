# ADR-006: Database Schema Structure and Naming Conventions

**Status:** Accepted
**Date:** 2026-03-29
**Last updated:** 2026-03-29

---

## Context

tennetctl has eight modules, each with dozens of tables, maintained by multiple contributors over time. Without a strict convention, the schema becomes inconsistent and impossible to reason about without reading application code.

Every table, column, constraint, index, and view must follow a convention that can be learned once and applied everywhere.

---

## Portability Principle

The schema is written to be portable across any standard SQL database (Postgres, MySQL, SQLite, CockroachDB, SQL Server). This means:

- **No stored procedures, functions, or triggers.** Logic lives in the application.
- **No database extensions** (no `uuid-ossp`, no `pgcrypto`, no `pg_partman`).
- **No ENUMs.** Use `dim_*` lookup tables instead.
- **No cross-database-specific constructs** unless documented as optional Postgres enhancements.

**Allowed:** `TABLES`, `VIEWS`, `MATERIALIZED VIEWS`, standard column types, standard constraints, standard indexes.

**Not allowed:** Triggers, stored procedures, functions, extensions, ENUMs.

---

## Quick Reference

| Question | Answer |
|----------|--------|
| Which schema does my table go in? | The module's schema — never `public` |
| How do I name a table? | `{nn}_{type}_{name}` — e.g. `11_fct_orgs` |
| Where do names, emails, strings go? | `dtl_attrs` EAV — never in `fct_*` |
| How do I soft-delete? | Set `deleted_at = CURRENT_TIMESTAMP` — never a boolean |
| How do I query live records? | `WHERE deleted_at IS NULL` — always, no exceptions |
| Who sets `updated_at`? | The application — always explicitly in every UPDATE |
| Do I use ENUMs? | Never. Use a `dim_*` table. |
| Can I write triggers? | No. Logic lives in the application layer. |
| Can I join across schemas in app code? | No. Event bus or `01_core/` service interfaces. |
| How do I add a new property? | Insert into `dim_attr_defs` + insert into `dtl_attrs`. No `ALTER TABLE`. |

---

## 1. Schema Per Module

Each module owns exactly one Postgres schema:

| Module | Schema |
|--------|--------|
| IAM | `"02_iam"` |
| Audit | `"03_audit"` |
| Monitoring | `"04_monitoring"` |
| Notifications | `"05_notify"` |
| Product Ops | `"06_ops"` |
| Vault | `"07_vault"` |
| LLM Ops | `"08_llmops"` |

Schemas are created once in the bootstrap migration. No runtime schema creation.

**Rules:**
- Never create tables in `public`.
- A module only queries its own schema in application code.
- Cross-module data access uses the event bus or service interfaces in `01_core/`.
- `created_by` / `updated_by` audit columns reference `fct_users` by UUID — no FK enforced (cross-schema FK constraint would violate isolation). See Section 7.

---

## 2. Table Naming

```
{nn}_{type}_{name}
```

| Type | Full name | Purpose |
|------|-----------|---------|
| `dim` | Dimension | Lookups / enumerations. SMALLINT PK, seeded in migration. |
| `fct` | Fact | Pure identity. UUID PK + FK references only. No descriptive data. |
| `dtl` | Detail | Descriptive attributes. EAV: `key_text` + `key_jsonb`. |
| `adm` | Admin | Platform/operator configuration. |
| `lnk` | Link | Many-to-many associations. FKs only, immutable rows. |
| `evt` | Event | Append-only. Never updated or deleted. |

| Range | Type |
|-------|------|
| 01–09 | `dim` |
| 10–19 | `fct` |
| 20–29 | `dtl` — paired with fct: `10_fct_users` → `20_dtl_attrs` |
| 30–39 | `adm` |
| 40–59 | `lnk` |
| 60–79 | `evt` |
| 80–99 | reserved |

### ENUM vs dim — always dim

- Postgres ENUMs require DDL to extend. A dim table row does not.
- Dim tables carry metadata: label, description, deprecated_at.
- Dim tables are zero cost at normal scale.
- Never use `CREATE TYPE ... AS ENUM`.

---

## 3. The fct / dtl(EAV) / dim Pattern

### fct — pure identity

Contains only: UUID PK, SMALLINT FKs to dim tables, BOOLEAN operational flags, TIMESTAMP audit columns, VARCHAR(36) audit actor columns.

No names. No emails. No strings. No JSONB. Those go in `dtl_attrs`.

### dtl — EAV descriptive attributes

One row per attribute per entity. Two value columns:

- `key_text TEXT` — simple string values (email, name, slug, url)
- `key_jsonb JSONB` (or `JSON` on MySQL) — structured values (settings, config)

Every key must be declared in `07_dim_attr_defs` before it can be used.

### Adding a new property — zero schema changes

```sql
-- 1. Register the key
INSERT INTO "02_iam".07_dim_attr_defs
    (id, entity_type_id, code, label, value_type, is_required, is_unique, description)
VALUES (8, 1, 'department', 'Department', 'text', false, false, 'User department.');

-- 2. Store the value
INSERT INTO "02_iam".20_dtl_attrs (entity_type_id, entity_id, attr_def_id, key_text, created_by)
VALUES (1, '<user-uuid>', 8, 'Engineering', '<actor-uuid>');
```

No `ALTER TABLE`. No migration. No deploy window.

---

## 4. Standard Column Templates

Copy these exactly. Deviation requires an explanation comment in the migration.

### dim_*

```sql
CREATE TABLE "{schema}".{nn}_dim_{name} (
    id            SMALLINT    NOT NULL,
    code          TEXT        NOT NULL,
    label         TEXT        NOT NULL,
    description   TEXT        NOT NULL DEFAULT '',
    deprecated_at TIMESTAMP,           -- NULL=active | SET=retired. Never delete dim rows.

    CONSTRAINT pk_{name}      PRIMARY KEY (id),
    CONSTRAINT uq_{name}_code UNIQUE (code)
);
```

- `SMALLINT` PK — never UUID
- No `updated_at`, no `created_by` — dim rows are seeded facts
- Never delete: set `deprecated_at` to retire a code

---

### fct_* — the standard audit column set

```sql
CREATE TABLE "{schema}".{nn}_fct_{name} (
    id          VARCHAR(36) NOT NULL,  -- UUID v7 generated by application
    -- FK columns (SMALLINT for dim refs, VARCHAR(36) for entity refs)
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    is_test     BOOLEAN     NOT NULL DEFAULT FALSE,
    deleted_at  TIMESTAMP,             -- NULL=live | SET=soft-deleted timestamp
    created_by  VARCHAR(36),           -- actor UUID — not FK-enforced (cross-schema)
    updated_by  VARCHAR(36),           -- actor UUID — not FK-enforced
    created_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_{name} PRIMARY KEY (id)
);
```

> **Note on `updated_at`:** There are no database triggers. The application **must** explicitly set `updated_at = CURRENT_TIMESTAMP` in every UPDATE statement. This is enforced by the repository layer, not the database. Every `UPDATE` in every repository function must include `updated_at = CURRENT_TIMESTAMP, updated_by = $actor_id`.

Mandatory indexes on every `fct_*` table:

```sql
-- Live-record fast path (most common query pattern)
CREATE INDEX idx_{name}_live ON {table} (created_at DESC)
    WHERE deleted_at IS NULL;         -- Postgres / SQL Server only

-- For other databases, use a regular index and filter in the query:
CREATE INDEX idx_{name}_deleted_at ON {table} (deleted_at);
```

---

### dtl_* (EAV)

```sql
CREATE TABLE "{schema}".{nn}_dtl_{name} (
    entity_type_id  SMALLINT    NOT NULL,
    entity_id       VARCHAR(36) NOT NULL,
    attr_def_id     SMALLINT    NOT NULL,
    key_text        TEXT,
    key_jsonb       TEXT,              -- JSON stored as TEXT for max portability
    created_by      VARCHAR(36),
    updated_by      VARCHAR(36),
    created_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_{name}            PRIMARY KEY (entity_type_id, entity_id, attr_def_id),
    CONSTRAINT fk_{name}_entity     FOREIGN KEY (entity_type_id)
        REFERENCES "{schema}".06_dim_entity_types(id),
    CONSTRAINT fk_{name}_attr       FOREIGN KEY (attr_def_id)
        REFERENCES "{schema}".07_dim_attr_defs(id),
    CONSTRAINT chk_{name}_one_value CHECK (
        (key_text IS NOT NULL AND key_jsonb IS NULL) OR
        (key_jsonb IS NOT NULL AND key_text IS NULL)
    )
);

CREATE INDEX idx_{name}_entity ON {table} (entity_type_id, entity_id);
```

On Postgres, declare `key_jsonb` as `JSONB` for native query operators. On other databases use `TEXT` and parse in the application.

---

### adm_* (mutable config — same audit columns as fct_*)

```sql
CREATE TABLE "{schema}".{nn}_adm_{name} (
    id          VARCHAR(36) NOT NULL,
    -- columns
    deleted_at  TIMESTAMP,
    created_by  VARCHAR(36),
    updated_by  VARCHAR(36),
    created_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_{name} PRIMARY KEY (id)
);
```

---

### lnk_* (immutable associations)

```sql
CREATE TABLE "{schema}".{nn}_lnk_{name} (
    id          VARCHAR(36) NOT NULL,
    org_id      VARCHAR(36) NOT NULL,  -- denormalised for tenant filtering
    -- FK columns
    created_by  VARCHAR(36),
    created_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- NO updated_at — lnk rows are immutable; change = delete + re-insert

    CONSTRAINT pk_{name}    PRIMARY KEY (id),
    CONSTRAINT uq_{name}_association UNIQUE (...)
);
```

---

### evt_* (append-only)

```sql
CREATE TABLE "{schema}".{nn}_evt_{name} (
    id          VARCHAR(36) NOT NULL,
    org_id      VARCHAR(36),
    actor_id    VARCHAR(36),
    ip_address  VARCHAR(45),           -- TEXT not INET — portable across databases
    metadata    TEXT        NOT NULL DEFAULT '{}',  -- JSON string
    created_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- NO updated_at, NO deleted_at, NO updated_by — events are immutable facts

    CONSTRAINT pk_{name} PRIMARY KEY (id)
);
```

---

## 5. `updated_at` — Application Responsibility

There are no triggers. The application is responsible for setting `updated_at`.

**Every repository UPDATE must follow this pattern:**

```python
# Every UPDATE must explicitly include these two columns
await conn.execute(
    """
    UPDATE "02_iam"."11_fct_orgs"
    SET is_active = $1,
        updated_by = $2,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = $3
    """,
    is_active, actor_id, org_id,
)
```

A repository UPDATE that does not include `updated_at = CURRENT_TIMESTAMP` and `updated_by = $actor_id` is a bug. Code review must catch this.

**Why no trigger?**
- Triggers are Postgres-specific procedural code
- Keeping logic in the application makes the database portable and the code explicit
- `grep "updated_at"` in app code shows every place it is set — impossible with hidden triggers

---

## 6. Soft Delete Pattern

**Always `deleted_at TIMESTAMP`, never `is_deleted BOOLEAN`.**

| Pattern | Problem |
|---------|---------|
| `is_deleted BOOLEAN` | No deletion timestamp. Two sources of truth if combined with status. |
| `status = 'deleted'` alone | Requires JOIN to check; can't index on `status != deleted` cleanly. |
| `deleted_at TIMESTAMP` ✓ | One column. Carries timestamp. `WHERE deleted_at IS NULL` indexes efficiently. |

### Live record queries — always this pattern

```sql
WHERE deleted_at IS NULL
```

Never:
```sql
WHERE is_deleted = false     -- wrong
WHERE status != 'deleted'    -- wrong
WHERE status_id != 3         -- wrong
```

### Soft-delete cascades in the service layer

```python
async def delete_org(conn, org_id, *, actor_id):
    # Service layer cascades explicitly — no DB-level cascades
    await repo.soft_delete_org(conn, org_id, deleted_by=actor_id)
    await repo.soft_delete_org_workspaces(conn, org_id, deleted_by=actor_id)
    await repo.soft_delete_org_groups(conn, org_id, deleted_by=actor_id)
    await emit_event(conn, event_type="org.deleted", ...)
```

DB cascades are invisible in application code. Service-layer cascades can emit events, audit each deletion, and halt on validation failures.

---

## 7. Audit Columns and Cross-Module FKs

`created_by` and `updated_by` conceptually reference `"02_iam".fct_users.id`.

FK constraints across schemas violate module isolation. These columns are stored as `VARCHAR(36)` (UUID string) with no FK constraint enforced. The application guarantees validity.

Document this in every COMMENT:

```sql
COMMENT ON COLUMN "02_iam"."11_fct_orgs".created_by IS
    'UUID of creating user. NULL=system. References fct_users.id — '
    'FK not enforced to preserve schema isolation.';
```

---

## 8. Views

### Read/write split — the rule

```
GET  → view (v_{entity})
POST / PATCH / DELETE → tables directly
```

### Naming

```
v_{plural_entity}
```

Examples: `v_orgs`, `v_users`, `v_workspaces`, `v_sessions`

### What a view must do

- Resolve dim FK → human code string (never expose raw `status_id` — expose `status`)
- Derive `is_deleted = (deleted_at IS NOT NULL)`
- `COALESCE(settings, '{}')` — JSON settings never null in the API
- Left-join `dtl_attrs` to materialize named attributes flat

### Materialized views

Use materialized views for expensive aggregations that are queried frequently
(e.g., org member counts, permission sets). Refresh on a schedule or on write.

```sql
CREATE MATERIALIZED VIEW "02_iam".mv_org_member_counts AS
SELECT org_id, COUNT(*) AS member_count
FROM "02_iam".40_lnk_org_members
WHERE ...
GROUP BY org_id;

CREATE UNIQUE INDEX ON "02_iam".mv_org_member_counts (org_id);

-- Refresh after writes:
REFRESH MATERIALIZED VIEW CONCURRENTLY "02_iam".mv_org_member_counts;
```

---

## 9. `is_test` Filter Rule

All production queries must exclude test data:

```sql
-- Billing, metrics, user-facing counts
WHERE deleted_at IS NULL AND is_test = FALSE

-- List API endpoints — expose include_test param, default false
```

Test orgs are never deleted. They accumulate in the DB and are filtered out by `is_test = FALSE`.

---

## 10. GDPR / Right-to-Erasure

```
Delete  →  dtl_attrs rows for entity_type_id=user  (removes all PII)
Keep    →  fct_users row as tombstone               (UUID referenced by audit logs)
Keep    →  all evt_* rows                           (legal records)
Keep    →  org dtl_attrs rows                       (organisational data, not personal)
```

```sql
-- 1. Erase all user PII
DELETE FROM "02_iam"."20_dtl_attrs"
WHERE entity_type_id = 1 AND entity_id = $1;

-- 2. Tombstone the identity record
UPDATE "02_iam"."10_fct_users"
SET deleted_at = CURRENT_TIMESTAMP, updated_by = $2, updated_at = CURRENT_TIMESTAMP
WHERE id = $1;
```

---

## 11. Constraint and Object Naming

Never rely on database-generated names.

```
PRIMARY KEY    pk_{table}
FOREIGN KEY    fk_{table}_{referenced_table}
UNIQUE         uq_{table}_{columns}
CHECK          chk_{table}_{description}
INDEX          idx_{table}_{columns}
PARTIAL INDEX  idx_{table}_{column}_{condition}
RLS POLICY     rls_{table}_{scope}
VIEW           v_{plural_entity}
MAT VIEW       mv_{description}
```

---

## 12. COMMENT on Everything

Every table and column must have a `COMMENT`. No exceptions.

Document:
- What the table/column stores
- What `NULL` means (e.g. `NULL = live, SET = soft-deleted timestamp`)
- Non-obvious behavior
- Cross-module references (without FK constraint, the COMMENT is the documentation)

---

## 13. Row-Level Security (Postgres Only — Optional Enhancement)

RLS is a Postgres-specific feature. The application must also enforce tenant isolation at the query level so the system works without RLS on other databases.

If running on Postgres, add RLS as a defence-in-depth layer:

```sql
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
CREATE POLICY rls_{table}_tenant ON {table}
    USING (org_id = current_setting('app.current_org_id', true)::UUID);
```

- `dim_*` tables: no RLS
- `fct_*` with `org_id`: RLS if on Postgres
- `evt_*` tenant-scoped: RLS if on Postgres

---

## 14. Migration File Structure

```sql
-- =============================================================================
-- Migration: YYYYMMDD_{NNN}_{description}.sql
-- Module:    {module_name}
-- Description: {one-line summary}
-- =============================================================================

-- UP ==========================================================================

{CREATE TABLE, ALTER TABLE, CREATE VIEW, CREATE INDEX, INSERT (seed data)...}
-- No triggers. No functions. No procedures.

-- DOWN ========================================================================

{DROP VIEW, DROP TABLE, DROP INDEX...}
-- Must completely revert UP.
```

`{NNN}` is a **global** three-digit sequence number across all modules. It determines application order. Two files with the same NNN is a hard error.

Files live in `docs/features/{feature}/09_sql_migrations/02_in_progress/` until applied.

---

## 15. Checklist — Before Every Migration PR

- [ ] Table in correct schema (never `public`)
- [ ] Name follows `{nn}_{type}_{name}`
- [ ] `fct_*` has all standard audit columns: `is_active`, `is_test`, `deleted_at`, `created_by`, `updated_by`, `created_at`, `updated_at`
- [ ] No triggers, functions, procedures, extensions, or ENUMs
- [ ] `lnk_*` has no `updated_at` (immutable rows)
- [ ] `evt_*` has no `updated_at`, no `deleted_at`
- [ ] All constraints explicitly named
- [ ] Every table and column has a `COMMENT`
- [ ] DOWN genuinely reverts UP
- [ ] No strings in `fct_*` columns (use `dtl_attrs`)
- [ ] No cross-schema JOINs in views
- [ ] RLS added if on Postgres (optional enhancement, not a hard requirement)
