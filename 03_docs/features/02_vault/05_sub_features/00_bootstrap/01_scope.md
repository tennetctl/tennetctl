# T-Vault Bootstrap — Scope

## What it does

Creates the `"02_vault"` Postgres schema and the three shared tables every
other vault sub-feature depends on:

- `06_dim_entity_types` — entity type registry (vault, project, environment, secret, api_key)
- `07_dim_attr_defs` — EAV attribute definitions for all entity types
- `20_dtl_attrs` — EAV attribute values (one row per attribute per entity)

## In scope

- `CREATE SCHEMA "02_vault"`
- Create the three shared tables with all constraints, indexes, and `COMMENT ON` docs
- Seed `06_dim_entity_types` with the five entity types this feature will use
- Seed `07_dim_attr_defs` with the initial known attributes per entity type
- Grant schema permissions to `tennetctl_read` and `tennetctl_write` roles
- Matching DOWN section that drops everything cleanly

## Out of scope

- Any `fct_*`, `dim_*` (other than the three EAV tables), `lnk_*`, or `evt_*` tables
  (those belong to individual sub-features)
- Any backend Python code
- Any API endpoints
- Any business logic

## Acceptance criteria

- [ ] `\dt+ "02_vault".*` shows exactly three tables: `06_dim_entity_types`,
      `07_dim_attr_defs`, `20_dtl_attrs`
- [ ] `\dn` shows `02_vault` schema
- [ ] Migration round-trips cleanly: UP → DOWN → UP on a fresh database
- [ ] DOWN completely removes the schema (no orphan objects)
