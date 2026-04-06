# 02_user — Scope

The User sub-feature manages platform user accounts. Every human, service account, or bot that interacts with tennetctl is a user entity with EAV-based attributes and full lifecycle management.

## In Scope
- **User CRUD**: Create, read, update, soft-delete user accounts.
- **EAV Attributes**: email, display_name, avatar_url, phone, settings — all stored as rows in `20_dtl_user_attrs`.
- **Account Types**: human (default), service_account, bot — via `03_dim_account_types`.
- **Status Lifecycle**: active, inactive, suspended, pending_verification, deleted — via `02_dim_user_statuses`.
- **Snapshot Versioning**: Every mutation captures full user state in `92_dtl_iam_snapshots`.
- **Audit Events**: Every create/update/delete emits to `90_fct_iam_audit_events`.

## Out of Scope
- **Authentication**: Handled by `08_auth` sub-feature (credentials, sessions, JWT).
- **Org Membership**: Handled by future `05_org_member` sub-feature.
- **RBAC Roles**: Deferred to future sub-feature.

## Dependencies
- `01_dim_org_entity_types` (entity_type_id=1 for user)
- `90_audit` feature (audit event emission)
- `92_dtl_iam_snapshots` (snapshot versioning)

## Acceptance Criteria
- [x] Email must be globally unique (enforced by partial unique index).
- [x] Deletion is soft (sets `deleted_at` + status=deleted).
- [x] All mutations emit audit events with snapshot.
- [x] EAV pattern — no business columns on `fct_user_users`.
