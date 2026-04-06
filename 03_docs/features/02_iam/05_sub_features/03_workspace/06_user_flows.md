# 03_workspace — User Flows

## 1. Create Workspace
1. User navigates to `/iam/workspaces`, clicks "New Workspace"
2. Fills in slug + display_name in dialog
3. Frontend calls POST `/v1/orgs/{org_id}/workspaces`
4. Backend validates org exists, slug unique within org
5. INSERT into fct + dtl tables, emit audit + snapshot
6. Workspace appears in list

## 2. View Workspace Detail
1. Click workspace slug in list
2. Detail page shows: display_name, slug, active status, org, created/updated times
3. Activity timeline shows all audit events for this workspace

## 3. Delete Workspace
1. Click "Delete" button on detail page
2. Confirmation dialog appears
3. Confirm → soft-delete (sets deleted_at)
4. Redirect to workspace list
