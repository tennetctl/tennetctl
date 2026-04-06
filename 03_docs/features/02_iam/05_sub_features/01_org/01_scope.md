# 01_org — Scope

The Org (Organisation) sub-feature serves as the root tenant entity in tennetctl. It provides the foundation for multi-tenancy, resource isolation, and billing boundaries.

## In Scope
- **Tenant Management**: Creating, updating, and soft-deleting organisations.
- **Identity Isolation**: Ensuring all resources are scoped to a specific `org_id`.
- **Lifecycle Tracking**: Managing org states (active, trialing, suspended, deleted).
- **Settings Storage**: Providing a flexible JSONB schema for org-level configuration.

## Out of Scope
- **Membership**: Handled by the `org_member` sub-feature.
- **Resource Ownership**: Handled by individual feature-level `fct_*` tables.

## Acceptance Criteria
- [ ] Slugs must be unique across all non-deleted organisations.
- [ ] Deletion must be soft (updating `deleted_at` and `status`).
- [ ] All writes must emit an audit event.
