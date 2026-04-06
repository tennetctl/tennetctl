# 02_user — User Flows

## 1. Create User
1. Client sends POST /v1/users with {email, display_name}
2. Service checks email uniqueness via `get_user_by_email()`
3. Generate UUID v7 for user_id
4. INSERT into `10_fct_user_users` (identity row)
5. UPSERT email + display_name into `20_dtl_user_attrs`
6. Read back full user via `v_10_user_users` view
7. Emit audit event (ACTION_CREATE) + capture snapshot (version 1)
8. Return user JSON

## 2. Update User (e.g. Suspend)
1. Client sends PATCH /v1/users/{id} with {status: "suspended"}
2. Service looks up user, validates status code exists in dim
3. UPDATE `10_fct_user_users` SET status_id = 3
4. Read back updated user
5. Emit audit event (ACTION_UPDATE) + capture snapshot (version N+1)
6. Return updated user JSON

## 3. Soft-Delete User
1. Client sends DELETE /v1/users/{id}
2. Service looks up user (404 if not found)
3. UPDATE `10_fct_user_users` SET deleted_at, status_id=5
4. Read back deleted user state
5. Emit audit event (ACTION_DELETE) + capture final snapshot
6. Return 204

## 4. View Version History
1. Client sends GET /v1/users/{id}/versions
2. Query `92_dtl_iam_snapshots` WHERE entity_type_id=1 AND entity_id=id
3. Return list of {version, changed_by, created_at} ordered by version DESC

## 5. View Specific Version
1. Client sends GET /v1/users/{id}/versions/1
2. Query snapshot row for version=1
3. Return full entity JSON as it was at that point in time
