# 02_user — Decisions

## ADR-001: EAV over Columns for User Attributes

**Decision**: Store email, display_name, avatar_url, phone, settings as EAV rows in `20_dtl_user_attrs`, not as columns on `10_fct_user_users`.

**Rationale**: Adding new user properties (e.g. timezone, locale, company) requires only an INSERT into `05_dim_user_attr_defs`. Zero schema migration. The `v_10_user_users` view pivots system attrs into named columns for ergonomic reads.

**Trade-off**: Slightly more complex writes (UPSERT per attr). Mitigated by helper functions in repository.py.

## ADR-002: Snapshot Versioning

**Decision**: Every user mutation captures a full JSON snapshot in `92_dtl_iam_snapshots`.

**Rationale**: Point-in-time reconstruction is a core tennetctl requirement. Snapshots are cheaper than event sourcing replay and provide instant "view as of" capability.

**Format**: Each snapshot is the full user dict as returned by `v_10_user_users` at mutation time.

## ADR-003: Email Uniqueness via Partial Index

**Decision**: Enforce email uniqueness with a partial unique index on `20_dtl_user_attrs (key_text) WHERE attr_def_id=1`.

**Rationale**: Email lives in EAV, not on the fct table. A partial unique index on the EAV table enforces global uniqueness without adding a column to the fact table.

## ADR-004: Account Types as Dimension Table

**Decision**: Use `03_dim_account_types` (human, service_account, bot) instead of a string column.

**Rationale**: Dimension tables are extensible without schema changes, provide consistent FK validation, and enable efficient queries by account type.
