# Rules

These are hard rules. They are not guidelines or suggestions. Every pull request is reviewed against them. A PR that violates a rule is not merged until the violation is fixed.

If you believe a rule is wrong, open a discussion issue. Do not work around it silently.

---

## Architecture Rules

### R-001: No ORM

All database access uses raw SQL with asyncpg. SQLAlchemy, Tortoise ORM, and similar tools are not used anywhere in the codebase.

**Why:** Raw SQL is explicit, auditable, and predictable. ORMs generate queries that are hard to reason about, difficult to optimize, and fight against the table naming conventions used in this project. Every query in tennetctl can be copied directly into a Postgres client and inspected.

### R-002: Modules communicate via events only

No module imports the service layer of another module. Cross-module logic is handled by emitting an event and handling it in the receiving module.

**Why:** Direct imports between modules create hidden coupling. A change to the IAM service layer should not require reading the monitoring module to understand the impact. The event contract is the public API between modules.

**Allowed exception:** Modules may import from `01_core` freely. `01_core` is shared infrastructure, not a feature module.

### R-003: All state lives in Postgres

NATS JetStream is a transport layer for high-volume ingestion. It is not durable storage. Consumer workers must write all data to Postgres before acknowledging a NATS message. If NATS data is lost, re-processing from Postgres must be possible.

**Why:** Operators trust Postgres. They know how to back it up, restore it, and inspect it. Durable state in NATS creates a second system of record that must be managed, backed up, and kept in sync.

### R-004: No required dependencies beyond Postgres and NATS

New features may not introduce new required services. ClickHouse, Redis, S3, and other services are supported as optional backends, but the system must function — with degraded performance, not broken behavior — without them.

**Why:** Every required dependency is a deployment blocker for a developer running tennetctl on a single server. The barrier to getting started must stay low.

### R-005: Each module owns exactly one Postgres schema

The IAM module reads and writes to the `"02_iam"` schema only. It does not issue queries against `"04_monitoring"` or any other module's schema.

**Why:** Schema-level isolation is the database equivalent of module isolation. It makes it possible to reason about data ownership and prevents accidental cross-module queries.

---

## Code Rules

### R-006: Every function has a docstring

Every function and method, without exception, has a docstring that describes what it does, its parameters, and its return value. One-liners are acceptable for simple functions.

**Why:** tennetctl is open-source. Contributors who read the code for the first time must be able to understand it without the original author explaining it.

### R-007: No silent error swallowing

Every error is either handled explicitly or propagated up the call stack. `except: pass`, bare `except Exception`, and logging-only error handlers without re-raising are not acceptable in production code paths.

**Why:** Silent failures are the hardest bugs to diagnose. In a control plane, an unhandled error in IAM or Vault can cause silent data loss or security failures.

### R-008: All user input validated at the boundary

Pydantic models validate all API request data before it reaches the service layer. The service layer never receives unvalidated input. Database queries never receive unvalidated input.

**Why:** Validation failures should surface at the API boundary with clear error messages, not deep in the service layer with cryptic exceptions.

### R-009: Files stay under 500 lines

No source file exceeds 500 lines. If a file is growing beyond this, split it into sub-modules.

**Why:** Large files are hard to review, hard to navigate, and usually a sign that a module is doing too much. The 5-file feature structure (schemas, repository, service, routes, constants) naturally distributes code across files.

### R-010: No hardcoded values

Configuration values, secrets, limits, and thresholds live in `01_core/config.py` as pydantic-settings fields with environment variable bindings. No hardcoded URLs, ports, limits, or credentials anywhere in feature code.

---

## Database Rules

### R-011: Every table and column has a COMMENT

```sql
-- REQUIRED
COMMENT ON TABLE "02_iam".fct_users IS 'Platform user accounts. One row per registered user.';
COMMENT ON COLUMN "02_iam".fct_users.status_id IS 'References 01_dim_user_statuses. Controls login access.';
```

**Why:** Contributors and operators reading the database directly must understand the schema without reading application code.

### R-012: All constraint names are explicit and prefixed

```sql
-- REQUIRED
CONSTRAINT pk_fct_users PRIMARY KEY (id),
CONSTRAINT fk_fct_users_status FOREIGN KEY (status_id) REFERENCES "02_iam".dim_user_statuses(id),
CONSTRAINT uq_fct_users_email UNIQUE (email),
CONSTRAINT chk_fct_users_email CHECK (email ~* '^[^@]+@[^@]+\.[^@]+$')
```

Prefixes: `pk_` (primary key), `fk_` (foreign key), `uq_` (unique), `idx_` (index), `chk_` (check constraint).

**Why:** Unnamed constraints generate random names in Postgres. Error messages referencing `$1` constraint are useless. Named constraints make error messages actionable.

### R-013: Every migration has UP and DOWN

Every migration file contains both an UP section (apply) and a DOWN section (revert). The DOWN section must genuinely revert the UP section — dropping tables, removing columns, restoring previous state.

**Why:** Rollback must be possible in production. A migration without a DOWN section is a one-way door.

### R-014: Table naming follows the convention

Tables are named `{nn}_{type}_{name}` where:
- `nn` is a two-digit sequence number within the schema
- `type` is one of: `dim` (dimension/lookup), `fct` (fact/entity), `lnk` (link/join), `adm` (admin/config), `evt` (event/log)
- `name` is a descriptive snake_case name

Example: `02_fct_users`, `01_dim_user_statuses`, `10_lnk_org_members`

---

## Security Rules

### R-015: No plaintext secrets anywhere

API keys are stored as BLAKE2b hashes. Passwords use argon2. OAuth client secrets, SSO tokens, and vault secrets use AES-256-GCM encryption. The only place encryption logic lives is `01_core/encryption.py`.

**Why:** If the database is ever read by an unauthorized party, no secret should be recoverable from it in plaintext.

### R-016: Every mutating operation emits an audit event

Any operation that creates, updates, or deletes data calls `emit_event()` within the same database transaction. The audit event is committed atomically with the data change.

**Why:** A control plane without a complete audit trail cannot be trusted. Operators and security teams must be able to answer "who did what and when" for any data in the system.

### R-017: Row-Level Security on all org-scoped tables

Every table with an `org_id` column has a Postgres RLS policy. The application sets `app.current_org_id` at the start of every tenant transaction. Platform/admin operations use a dedicated connection that bypasses RLS.

**Why:** Application-level access control can have bugs. RLS provides a defense-in-depth layer at the database that cannot be bypassed by application code.

---

## Documentation Rules

### R-018: No feature ships without docs

A feature PR must include:
- Updated `feature.manifest.yaml` with status `DONE`
- API documentation (auto-generated from Pydantic models and route docstrings)
- At least one entry in `docs/features/{feature}/` covering the design

**Why:** Undocumented features are unusable by contributors and operators who weren't involved in building them.

### R-019: Architectural decisions are recorded

Any decision that affects the overall architecture, cross-module contracts, or technology choices gets an ADR in `docs/00_main/08_decisions/`. ADRs are never deleted — only superseded by newer ADRs that reference them.

**Why:** Future contributors must understand why the system is the way it is before they can propose changes. "We tried that, here's why it didn't work" is information that should not live only in someone's memory.
