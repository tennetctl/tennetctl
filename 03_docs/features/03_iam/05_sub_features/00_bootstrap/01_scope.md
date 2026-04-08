## IAM Bootstrap — Scope

## What it does

Creates the entire `"03_iam"` Postgres schema in one migration. Every
table IAM will ever touch in v1 — `10_fct_users`, `20_fct_sessions`,
the dim tables, the EAV tables — lands in this single file. All dim
rows (`default_admin`, `username_password`, etc.) are seeded inline so
the runtime auth code and the install wizard both find the FKs they
expect.

This sub-feature ships no backend code. It is a schema-only migration
that must land before:

- `00_setup.03_first_admin` (which inserts the first admin row)
- `03_iam.01_auth` (which reads and writes sessions)

## Tables

### `06_dim_entity_types`

Entity-type registry for EAV. Seeded with two rows:

| code         | label      |
| ------------ | ---------- |
| `iam_user`   | IAM User   |
| `iam_session`| IAM Session|

### `06_dim_account_types`

User role/category. Seeded with two rows:

| code            | label            | description                              |
| --------------- | ---------------- | ---------------------------------------- |
| `default_admin` | Default Admin    | Full access — used by the first admin    |
| `default_user`  | Default User     | Non-admin (stub for v2; unused in v1)    |

### `07_dim_auth_types`

Authentication method. V1 seeds one row; future auth methods append
new rows without modifying this one.

| code                | label                |
| ------------------- | -------------------- |
| `username_password` | Username + Password  |

### `07_dim_token_types`

Token type registry. Used to scope audit events to the right token kind.

| code      | label         | description                                                                |
| --------- | ------------- | -------------------------------------------------------------------------- |
| `access`  | Access Token  | Short-lived signed JWT (15 min). Verified statelessly.                     |
| `refresh` | Refresh Token | Long-lived opaque rotation token (7d). Verified against DB hash + prefix.  |

### `07_dim_attr_defs`

EAV attribute registry. Seeded with eight rows:

| entity_type | code             | value_column |
| ----------- | ---------------- | ------------ |
| iam_user    | `username`       | key_text     |
| iam_user    | `email`          | key_text     |
| iam_user    | `password_hash`  | key_text     |
| iam_session | `token_hash`     | key_text     |
| iam_session | `ip_address`     | key_text     |
| iam_session | `user_agent`     | key_text     |
| iam_session | `refresh`        | key_text     |
| iam_session | `jti`            | key_text     |

### `08_dim_session_statuses`

Session lifecycle status. Seeded with three rows:

| code    | label   |
| ------- | ------- |
| active  | Active  |
| revoked | Revoked |
| expired | Expired |

### `10_fct_users`

User identity. UUID v7 primary key, FK-only columns, no strings.

Columns:

- `id VARCHAR(36)` — UUID v7
- `org_id VARCHAR(36)` — the user's organisation (reflexive for first admin)
- `account_type_id SMALLINT` → `06_dim_account_types`
- `auth_type_id SMALLINT` → `07_dim_auth_types`
- `is_active BOOLEAN` — standard fct_* metadata
- `is_test BOOLEAN`
- `deleted_at TIMESTAMP`
- `created_by VARCHAR(36)` — FK to this same table (users create users)
- `updated_by VARCHAR(36)`
- `created_at TIMESTAMP`
- `updated_at TIMESTAMP`

### `20_fct_sessions`

Session identity. UUID v7 primary key. Four token fast-path columns are
promoted out of EAV because they are read on every authenticated request
and every token refresh — an EAV join on those hot paths is too expensive.

Columns:

- `id VARCHAR(36)` — UUID v7
- `user_id VARCHAR(36)` → `10_fct_users.id`
- `status_id SMALLINT` → `08_dim_session_statuses`
- `token_prefix CHAR(16)` — first 16 chars of raw access token; index predicate before Argon2id verify
- `refresh_token_hash TEXT` — Argon2id PHC hash of the opaque refresh token
- `refresh_token_prefix CHAR(16)` — first 16 chars of raw refresh token; index predicate
- `refresh_expires_at TIMESTAMP` — hard expiry for the refresh token (7d from login)
- `expires_at TIMESTAMP NOT NULL` — mirrors `refresh_expires_at` for JWT sessions
- `absolute_expires_at TIMESTAMP NOT NULL` — hard cap (30d from login); never extended
- `last_seen_at TIMESTAMP` — updated by the session middleware
- `is_active BOOLEAN`
- `is_test BOOLEAN`
- `deleted_at TIMESTAMP`
- `created_by VARCHAR(36)` → `10_fct_users.id`
- `updated_by VARCHAR(36)` → `10_fct_users.id`
- `created_at TIMESTAMP`
- `updated_at TIMESTAMP`

The full access token hash, IP address, user-agent, and JTI live in
`20_dtl_attrs` as EAV rows. The four `token_prefix` / `refresh_*`
columns are the deliberate exception.

### `20_dtl_attrs`

Standard IAM EAV attribute table. One row per (entity, attr_def) pair.

Columns:

- `id VARCHAR(36)` — UUID v7
- `entity_type_id SMALLINT` → `06_dim_entity_types`
- `entity_id VARCHAR(36)` — references `10_fct_users.id` or
  `20_fct_sessions.id` depending on `entity_type_id` (no FK because
  the target varies)
- `attr_def_id SMALLINT` → `07_dim_attr_defs`
- `key_text TEXT` — for string values (the only value column used in v1)
- `key_jsonb JSONB` — reserved for future JSONB attributes
- `key_smallint SMALLINT` — reserved for future dim-FK attributes
- `created_at TIMESTAMP`
- `updated_at TIMESTAMP`

CHECK constraint: exactly one of `key_text`, `key_jsonb`, `key_smallint`
is non-NULL.

## Views

### `v_users`

```sql
SELECT
    u.id,
    u.org_id,
    a.code               AS account_type,
    t.code               AS auth_type,
    un.key_text          AS username,
    em.key_text          AS email,
    u.is_active,
    (u.deleted_at IS NOT NULL) AS is_deleted,
    u.created_at,
    u.updated_at
FROM "03_iam"."10_fct_users" u
JOIN "03_iam"."06_dim_account_types" a ON u.account_type_id = a.id
JOIN "03_iam"."07_dim_auth_types"    t ON u.auth_type_id = t.id
LEFT JOIN "03_iam"."20_dtl_attrs" un
       ON un.entity_id = u.id
      AND un.attr_def_id = (
          SELECT id FROM "03_iam"."07_dim_attr_defs"
           WHERE code = 'username'
             AND entity_type_id = (
                 SELECT id FROM "03_iam"."06_dim_entity_types"
                  WHERE code = 'iam_user')
      )
LEFT JOIN "03_iam"."20_dtl_attrs" em
       ON em.entity_id = u.id
      AND em.attr_def_id = (
          SELECT id FROM "03_iam"."07_dim_attr_defs"
           WHERE code = 'email'
             AND entity_type_id = (
                 SELECT id FROM "03_iam"."06_dim_entity_types"
                  WHERE code = 'iam_user')
      );
```

`password_hash` is deliberately **not** in `v_users`. The login repository
fetches it via a dedicated query that joins directly; the view does not
expose it so a careless `SELECT * FROM v_users` never leaks a hash to logs.

### `v_sessions`

```sql
SELECT
    s.id,
    s.user_id,
    st.code                    AS status,
    s.token_prefix,
    s.refresh_token_prefix,
    s.refresh_expires_at,
    s.expires_at,
    s.absolute_expires_at,
    s.last_seen_at,
    (s.deleted_at IS NOT NULL) AS is_deleted,
    s.created_by,
    s.updated_by,
    s.created_at,
    s.updated_at
FROM "03_iam"."20_fct_sessions" s
JOIN "03_iam"."08_dim_session_statuses" st ON s.status_id = st.id;
```

Exposes `token_prefix` and `refresh_token_prefix` for index-based
candidate filtering. `refresh_token_hash` and the EAV `token_hash` are
deliberately excluded — the middleware fetches them via specific queries
after narrowing by prefix.

## In scope

- Schema creation (`CREATE SCHEMA "03_iam"`)
- All dim tables with their seed rows, including `07_dim_token_types`
- `07_dim_attr_defs` rows for username, email, password_hash (iam_user)
  and token_hash, ip_address, user_agent, refresh, jti (iam_session)
- `10_fct_users` table — UUID + FK columns only, no strings
- `20_fct_sessions` table with the four token fast-path columns
  (`token_prefix`, `refresh_token_hash`, `refresh_token_prefix`,
  `refresh_expires_at`) and prefix partial indexes
- `20_dtl_attrs` table with the three value-column CHECK constraint
- `v_users` and `v_sessions` views (v_sessions exposes prefix columns)
- Full UP and DOWN sections
- `COMMENT ON` every table and column
- Grants: `SELECT` on all tables + views to `tennetctl_read`;
  `SELECT, INSERT, UPDATE, DELETE` on tables to `tennetctl_write`;
  `USAGE` on schema to both roles

## Out of scope

- Backend code (lives in `01_auth`)
- HTTP routes
- The `default_user` account type being referenced anywhere in v1 code
  (it exists as a stub so v2 doesn't need a dim renumbering)
- Any `lnk_*` or `evt_*` tables for IAM (v1 audit events go via the
  event bus, not a local evt_* table; that's handled by `04_audit`)
- User-management API (`POST /v1/users`, etc.) — future sub-feature

## Acceptance criteria

- [ ] Migration file at
      `09_sql_migrations/02_in_progress/20260408_003_iam_bootstrap.sql`
      with UP and DOWN sections
- [ ] `migration.yaml` declares sequence 3 and `depends_on: [2]`
- [ ] Schema `"03_iam"` is created in UP and dropped in DOWN
- [ ] All seven dim tables exist with the documented seed rows
      (`06_dim_entity_types`, `06_dim_account_types`, `07_dim_auth_types`,
      `07_dim_token_types`, `07_dim_attr_defs`, `08_dim_session_statuses`)
- [ ] `07_dim_attr_defs` has rows for all eight attributes (3 iam_user + 5 iam_session)
- [ ] `10_fct_users` has no string or JSONB columns
- [ ] `20_fct_sessions` has `token_prefix`, `refresh_token_hash`,
      `refresh_token_prefix`, `refresh_expires_at` columns plus partial
      indexes `idx_iam_fct_sessions_token_prefix` and
      `idx_iam_fct_sessions_refresh_prefix`
- [ ] `20_dtl_attrs` has a CHECK constraint enforcing exactly one
      `key_*` column non-NULL
- [ ] `v_users` excludes `password_hash` entirely
- [ ] `v_sessions` exposes `token_prefix` and `refresh_token_prefix`
      but excludes `refresh_token_hash` and the EAV `token_hash`
- [ ] Every constraint is explicitly named
- [ ] Every table and every column has a `COMMENT ON`
- [ ] Grants exist for `tennetctl_read` and `tennetctl_write` on
      all tables and views
- [ ] UP → DOWN → UP round-trips cleanly on a dev Postgres
- [ ] Running the migration against a Postgres with `02_vault` applied
      does not interfere with the vault schema

## Dependencies

- Depends on: `02_vault.01_setup` (`sequence: 2`) — not a data
  dependency, just an ordering dependency (the migrator runs in
  sequence order and IAM's number is 3)
- Depended on by: `00_setup.03_first_admin` (inserts into these tables),
  `03_iam.01_auth` (reads and writes these tables at runtime)
