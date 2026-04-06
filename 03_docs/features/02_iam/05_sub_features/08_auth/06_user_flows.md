# 08_auth — User Flows

## 1. First-Run Setup
1. User navigates to tennetctl for the first time
2. Frontend checks `GET /v1/auth/setup-status` → `{needs_setup: true}`
3. Redirects to `/setup` page
4. User fills in: name, email, password, confirm password
5. Frontend calls `POST /v1/auth/setup`
6. Backend validates zero users exist, creates user + credential + session
7. Returns JWT pair → stored in localStorage
8. Redirects to `/iam/orgs` dashboard

## 2. Login
1. User navigates to `/login`
2. Frontend checks setup-status → `{needs_setup: false}` → shows login form
3. User enters email + password
4. Frontend calls `POST /v1/auth/login`
5. Backend verifies credentials, creates session, emits audit event
6. Returns JWT pair → stored in localStorage
7. Redirects to `/iam/orgs`

## 3. Token Refresh
1. Access token expires (15 min TTL)
2. Client sends `POST /v1/auth/refresh` with refresh_token
3. Backend decodes refresh JWT, verifies session not revoked
4. Revokes old session, creates new session
5. Returns new JWT pair

## 4. Logout
1. Client sends `POST /v1/auth/logout` with Authorization header
2. Backend decodes access JWT, revokes session by JTI
3. Client clears localStorage tokens

## 5. Failed Login (Audited)
1. User enters wrong password
2. Backend emits audit event with outcome=failure
3. Returns 401 "Invalid email or password"
4. No information leakage (same error for wrong email or wrong password)
