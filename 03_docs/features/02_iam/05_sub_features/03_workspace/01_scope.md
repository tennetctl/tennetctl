# 03_workspace — Scope

The Workspace sub-feature provides isolation boundaries within organisations. Each workspace is org-scoped and can represent a department, team, project, or environment.

## In Scope
- **Workspace CRUD**: Create, list, get, update, soft-delete workspaces.
- **Org-Scoped**: Every workspace belongs to exactly one org.
- **EAV Attributes**: slug, display_name, settings — stored in `21_dtl_ws_attrs`.
- **Slug Uniqueness**: Slugs are unique within an org (enforced in service layer).
- **Snapshot Versioning**: Every mutation captures full workspace state.
- **Audit Events**: Every create/update/delete emits to audit log.

## Out of Scope
- **Workspace Members**: User-to-workspace assignment deferred to `07_workspace_member`.
- **Workspace Roles**: Viewer/editor/admin roles deferred.
- **Resource Scoping**: Feature-level resources scoped to workspace deferred.

## Dependencies
- `01_org` (workspace.org_id references an org)
- `01_dim_org_entity_types` (entity_type_id=3 for workspace)
- `90_audit` feature (audit event emission)

## Acceptance Criteria
- [x] Slugs unique within an org.
- [x] Workspace creation validates org exists (404 if not).
- [x] Deletion is soft (sets deleted_at).
- [x] All mutations emit audit events with snapshot.
