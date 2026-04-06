# 03_workspace — Decisions

## ADR-001: Org-Scoped Routes

**Decision**: Workspace routes are nested under `/v1/orgs/{org_id}/workspaces`.

**Rationale**: Workspaces belong to exactly one org. Nesting under the org path makes the ownership explicit in the URL and prevents cross-org access.

## ADR-002: Slug Uniqueness in Service Layer

**Decision**: Workspace slug uniqueness within an org is enforced in the service layer, not via a DB index.

**Rationale**: The slug is stored in EAV (`21_dtl_ws_attrs`) but org_id is on the fct table (`12_fct_ws_workspaces`). A partial unique index would need to span both tables, which isn't possible. The service checks `get_workspace_by_slug(conn, org_id, slug)` before creating.

## ADR-003: No Workspace Status Dimension

**Decision**: Workspaces use only `is_active` boolean. No status lifecycle dimension table.

**Rationale**: Workspaces have a simpler lifecycle than orgs or users. Active/inactive is sufficient. If needed later, a `dim_ws_statuses` can be added without breaking changes.
