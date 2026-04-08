## Settings — Scope

## What it does

Introduces a `00_setup."10_fct_settings"` table that stores all mutable
runtime configuration as rows in the database. This replaces `config.toml`
as the source of truth for settings that can change after install without
redeployment.

The hard rule on bootstrap is: **only two settings come from env vars —
`DATABASE_URL` (write DSN) and `TENNETCTL_ENV` (`dev | staging | prod`).
Everything else lives in the DB.** The install wizard writes the initial
settings rows; the app reads them on startup and caches them.

## Why not config.toml

`config.toml` is written once by the wizard and never updated. Any setting
change requires restarting the process with a hand-edited file. Settings in
the DB can be changed via the admin API (future) or a single SQL update
without touching disk or redeploying. They are also transactional, auditable
via the standard `created_at` / `updated_at` columns, and visible to all
nodes in a multi-replica deployment simultaneously.

## Table: `00_setup."10_fct_settings"`

Lives in `00_schema_migrations` schema (the bootstrap schema) so it is
available before any feature schema is created. The `00_setup` feature owns
it; no other feature writes to it directly.

### Schema

```sql
CREATE TABLE "00_schema_migrations"."10_fct_settings" (
    id           VARCHAR(36)  NOT NULL,
    scope        TEXT         NOT NULL,   -- 'global' | feature code e.g. '03_iam'
    key          TEXT         NOT NULL,
    value        TEXT,
    value_secret BOOLEAN      NOT NULL DEFAULT FALSE,
    description  TEXT,
    created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_settings            PRIMARY KEY (id),
    CONSTRAINT uq_settings_scope_key  UNIQUE (scope, key),
    CONSTRAINT chk_settings_scope     CHECK (scope ~ '^[0-9a-z_]+$')
);
```

### Columns

| Column         | Type         | Notes                                                         |
| -------------- | ------------ | ------------------------------------------------------------- |
| `id`           | VARCHAR(36)  | UUID v7 primary key                                           |
| `scope`        | TEXT         | `'global'` or feature code (`'03_iam'`, `'02_vault'`, …)     |
| `key`          | TEXT         | Setting name within its scope (e.g. `jwt_expiry_seconds`)    |
| `value`        | TEXT         | Setting value as a string. NULL means "use code default".    |
| `value_secret` | BOOLEAN      | True if the value should be redacted from logs and API reads |
| `description`  | TEXT         | Human-readable explanation of the setting                    |
| `created_at`   | TIMESTAMP    | Row creation timestamp (UTC)                                 |
| `updated_at`   | TIMESTAMP    | Last update timestamp (UTC)                                  |

`value` is always TEXT — the app is responsible for parsing to the correct
type (int, bool, duration, etc.). This avoids a polymorphic column nightmare.

`value_secret = TRUE` does not encrypt the value at rest — it is a hint to
the app and API layer to redact it from responses and logs. Truly sensitive
values (DSNs, API keys) must go in the vault, not here.

### Uniqueness

`(scope, key)` is unique. There is no concept of "override" rows — if you
want to change a setting you UPDATE the existing row. No versioning in v1.

### No `fct_*` audit columns

This table is deliberately minimal: no `is_active`, `is_test`,
`deleted_at`, `created_by`, `updated_by`. It is not a user-facing entity
— it is config infrastructure. Settings rows are never soft-deleted; they
are updated in-place or removed.

## V1 seed rows

The wizard writes these rows on first install:

| scope    | key                    | value   | value_secret | description                                     |
| -------- | ---------------------- | ------- | ------------ | ----------------------------------------------- |
| `global` | `env`                  | `dev`   | false        | Deployment environment (dev / staging / prod)   |
| `03_iam` | `jwt_expiry_seconds`   | `900`   | false        | JWT access token TTL in seconds (default 15 min)|
| `03_iam` | `cookie_secure`        | `false` | false        | Set Secure flag on tcc_refresh cookie (false in dev) |
| `03_iam` | `refresh_token_ttl_days` | `7`   | false        | Refresh token lifetime in days                  |
| `03_iam` | `session_absolute_ttl_days` | `30` | false      | Hard session cap in days                        |

`env` is seeded from `TENNETCTL_ENV` at install time — after that it lives
in the DB and the env var is no longer needed.

## App startup behaviour

On startup the app:

1. Reads `DATABASE_URL` from env — the only DSN ever passed via env.
2. Opens the connection pool.
3. `SELECT scope, key, value FROM "00_schema_migrations"."10_fct_settings"`
   — loads all rows into an in-memory dict keyed by `(scope, key)`.
4. Validates that mandatory keys are present; raises `StartupError` if any
   are missing.
5. Makes the settings dict available at `app.state.settings`.

Settings are not reloaded at runtime in v1 — a restart is required for
changes to take effect. Live-reload is a v2 feature.

## Bootstrap ordering

`10_fct_settings` must exist before the wizard writes its seed rows. The
table is created in the `00_bootstrap` migration (alongside `system_meta`
and `applied_migrations`), so it is available from the very first migration
run. The wizard's Phase 4 **is** the settings seeder — it seeds the
mandatory runtime rows via `ON CONFLICT (scope, key) DO NOTHING` so
re-runs are idempotent.

## In scope

- `10_fct_settings` table in `"00_schema_migrations"` schema
- V1 seed rows for `global.env` and the five IAM runtime settings
- App startup loading into `app.state.settings`
- `COMMENT ON` every table and column
- Grants: `SELECT` to `tennetctl_read`; `SELECT, INSERT, UPDATE, DELETE`
  to `tennetctl_write`

## Out of scope

- Admin API for reading or writing settings (`GET /v1/settings`,
  `PATCH /v1/settings/:key`) — future sub-feature
- Encryption of secret settings at rest — secrets go in the vault
- Live-reload without restart — v2
- Per-organisation or per-user settings overrides — v2
- Soft-delete or audit history for settings changes — not needed in v1;
  `updated_at` is the extent of the audit trail

## Acceptance criteria

- [ ] Migration file in
      `00_bootstrap/09_sql_migrations/02_in_progress/` adds
      `10_fct_settings` to the `"00_schema_migrations"` schema
- [ ] `(scope, key)` unique constraint prevents duplicate settings
- [ ] `chk_settings_scope` rejects scopes that don't match `^[0-9a-z_]+$`
- [ ] V1 seed rows are present after migration apply
- [ ] Wizard Phase 4 seeds mandatory settings rows via
      `ON CONFLICT (scope, key) DO NOTHING`
- [ ] App startup loads all settings into `app.state.settings` and fails
      fast if any mandatory key is absent
- [ ] `value_secret = TRUE` rows are redacted in any log or API response
      that exposes settings (enforced at the app layer)

## Dependencies

- Depends on: `01_sql_migrator.00_bootstrap` (adds to the same migration
  file or a new 000-series migration)
- Depended on by: `00_setup.00_wizard` Phase 4 (writes seed rows)
- Depended on by: every feature's startup path (reads settings on boot)
