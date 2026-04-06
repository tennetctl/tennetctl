# IAM P0 Gaps — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all P0 IAM gaps identified in `03_docs/00_main/11_gap_analysis.md` — auth middleware, password reset, email verification, social login (Google/GitHub), pagination fixes, RBAC user/group role assignment, and related missing endpoints.

**Architecture:** All changes are surgical additions to existing sub-features in `01_backend/02_features/02_iam/`. No new modules. Auth middleware becomes a shared FastAPI `Depends` in `01_core/`. Social login uses OAuth2 authorization code flow, storing tokens in existing session infrastructure.

**Tech Stack:** FastAPI Depends, asyncpg, JWT (python-jose), itsdangerous (signed tokens for reset/verify), httpx (OAuth2 token exchange), existing notify module for email delivery.

---

## Critical Patterns (read before every task)

```python
# Import pattern for numeric dirs
import importlib
_db = importlib.import_module("01_backend.01_core.database")
_resp = importlib.import_module("01_backend.01_core.response")

# Response envelope
_resp.ok(data)            # {"ok": true, "data": ...}
_resp.error("CODE", "message")  # {"ok": false, "error": {...}}

# Connection pattern
pool = await _db.get_pool()
async with pool.acquire() as conn:
    result = await _svc.some_fn(conn, ...)
```

---

## Task 1: Auth Middleware — FastAPI `Depends(current_user)`

**Problem:** Every route does manual Bearer header parsing. This is P0 because without a shared middleware, org-scoped auth context can't propagate and every new route reinvents auth.

**Files:**
- Create: `01_backend/01_core/auth.py`
- Modify: `01_backend/02_features/02_iam/08_auth/routes.py` (remove manual Bearer parsing, use new dep)
- Create: `01_backend/tests/01_core/test_auth_middleware.py`

- [ ] **Step 1: Write failing test**

```python
# 01_backend/tests/01_core/test_auth_middleware.py
import importlib
import pytest

async def test_valid_token_returns_user_context():
    auth = importlib.import_module("01_backend.01_core.auth")
    # Use a real JWT signed with test secret
    token = _make_test_jwt(user_id="user-001", org_id="org-001")
    ctx = await auth.decode_token(token)
    assert ctx["user_id"] == "user-001"
    assert ctx["org_id"] == "org-001"

async def test_expired_token_raises():
    auth = importlib.import_module("01_backend.01_core.auth")
    token = _make_test_jwt(user_id="user-001", expired=True)
    with pytest.raises(Exception, match="expired"):
        await auth.decode_token(token)

async def test_invalid_token_raises():
    auth = importlib.import_module("01_backend.01_core.auth")
    with pytest.raises(Exception):
        await auth.decode_token("not.a.valid.token")

def _make_test_jwt(user_id: str, org_id: str = "org-001", expired: bool = False):
    from jose import jwt
    from datetime import datetime, timezone, timedelta
    exp = datetime.now(timezone.utc) + (timedelta(seconds=-1) if expired else timedelta(hours=1))
    return jwt.encode({"sub": user_id, "org_id": org_id, "exp": exp},
                      "test-secret", algorithm="HS256")
```

Run: `cd tennetctl && .venv/bin/python -m pytest 01_backend/tests/01_core/test_auth_middleware.py -v`
Expected: FAIL

- [ ] **Step 2: Write `01_backend/01_core/auth.py`**

```python
# 01_backend/01_core/auth.py
import importlib
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends
from jose import jwt, JWTError

_cfg = importlib.import_module("01_backend.01_core.config")
_bearer = HTTPBearer(auto_error=False)

async def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, _cfg.JWT_SECRET, algorithms=["HS256"])
        return payload
    except JWTError as e:
        if "expired" in str(e).lower():
            raise ValueError("Token expired")
        raise ValueError(f"Invalid token: {e}")

async def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer)
) -> dict:
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Missing authorization header")
    try:
        return await decode_token(creds.credentials)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
```

- [ ] **Step 3: Run tests, then update 08_auth routes to use `Depends(current_user)`**

In `08_auth/routes.py`, replace manual Bearer parsing on protected endpoints:
```python
# Before:
async def get_me(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    ...

# After:
_auth = importlib.import_module("01_backend.01_core.auth")

async def get_me(user: dict = Depends(_auth.current_user)):
    return _resp.ok(user)
```

- [ ] **Step 4: Run all auth tests, commit**

```bash
cd tennetctl && .venv/bin/python -m pytest 01_backend/tests/ -k "auth" -v
git add 01_backend/01_core/auth.py 01_backend/02_features/02_iam/08_auth/routes.py 01_backend/tests/01_core/test_auth_middleware.py
git commit -m "feat(iam): auth middleware — FastAPI Depends(current_user) shared dependency"
```

---

## Task 2: Pagination — Add `offset` to `01_org` and `02_user` list endpoints

**Files:**
- Modify: `01_backend/02_features/02_iam/01_org/schemas.py`
- Modify: `01_backend/02_features/02_iam/01_org/repository.py`
- Modify: `01_backend/02_features/02_iam/02_user/schemas.py`
- Modify: `01_backend/02_features/02_iam/02_user/repository.py`
- Modify: `01_backend/02_features/02_iam/06_group_member/schemas.py`
- Modify: `01_backend/02_features/02_iam/06_group_member/repository.py`
- Create: `01_backend/tests/02_iam/test_pagination.py`

- [ ] **Step 1: Write failing test**

```python
# 01_backend/tests/02_iam/test_pagination.py
import pytest, importlib

async def test_org_list_pagination(pool):
    repo = importlib.import_module("01_backend.02_features.02_iam.01_org.repository")
    async with pool.acquire() as conn:
        # Create 3 orgs
        for i in range(3):
            await repo.create_org(conn, {"slug": f"org-{i}", "display_name": f"Org {i}"})
        page1 = await repo.list_orgs(conn, limit=2, offset=0, include_deleted=False)
        page2 = await repo.list_orgs(conn, limit=2, offset=2, include_deleted=False)
    assert len(page1) == 2
    assert len(page2) >= 1
    assert page1[0]["id"] != page2[0]["id"]

async def test_user_list_pagination(pool):
    repo = importlib.import_module("01_backend.02_features.02_iam.02_user.repository")
    async with pool.acquire() as conn:
        for i in range(3):
            await repo.create_user(conn, {"email": f"user{i}@test.com", "display_name": f"User {i}"})
        page1 = await repo.list_users(conn, limit=2, offset=0, include_deleted=False)
        page2 = await repo.list_users(conn, limit=2, offset=2, include_deleted=False)
    assert len(page1) == 2
```

Run: Expected FAIL (offset param doesn't exist)

- [ ] **Step 2: Add `offset` to `01_org/repository.py` list query**

```python
async def list_orgs(conn, limit: int = 50, offset: int = 0,
                    include_deleted: bool = False) -> list[dict]:
    where = [] if include_deleted else ["is_deleted = FALSE"]
    sql = f"""SELECT * FROM fct_org
              {'WHERE ' + ' AND '.join(where) if where else ''}
              ORDER BY created_at DESC
              LIMIT $1 OFFSET $2"""
    rows = await conn.fetch(sql, limit, offset)
    return [dict(r) for r in rows]
```

- [ ] **Step 3: Same pattern for `02_user/repository.py` and `06_group_member/repository.py`**

Add `offset: int = 0` parameter to list functions. Update corresponding schemas to include `offset: int = 0` in list request/query models.

- [ ] **Step 4: Run tests, commit**

```bash
cd tennetctl && .venv/bin/python -m pytest 01_backend/tests/02_iam/test_pagination.py -v
git add 01_backend/02_features/02_iam/01_org/ 01_backend/02_features/02_iam/02_user/ 01_backend/02_features/02_iam/06_group_member/ 01_backend/tests/02_iam/test_pagination.py
git commit -m "fix(iam): add offset pagination to 01_org, 02_user, 06_group_member list endpoints"
```

---

## Task 3: Password Reset Flow

**Files:**
- Create: `01_backend/02_features/02_iam/08_auth/reset.py` (token generation + verification)
- Modify: `01_backend/02_features/02_iam/08_auth/routes.py` (add 2 new routes)
- Modify: `01_backend/02_features/02_iam/08_auth/service.py` (add reset logic)
- Create: `01_backend/tests/02_iam/test_password_reset.py`

- [ ] **Step 1: Write failing test**

```python
# 01_backend/tests/02_iam/test_password_reset.py
import importlib, pytest

async def test_generate_reset_token_is_deterministic(pool):
    reset = importlib.import_module("01_backend.02_features.02_iam.08_auth.reset")
    token = reset.generate_reset_token(user_id="user-001", email="a@b.com")
    assert len(token) > 20

async def test_verify_valid_reset_token():
    reset = importlib.import_module("01_backend.02_features.02_iam.08_auth.reset")
    token = reset.generate_reset_token(user_id="user-001", email="a@b.com")
    payload = reset.verify_reset_token(token)
    assert payload["user_id"] == "user-001"

async def test_verify_tampered_token_raises():
    reset = importlib.import_module("01_backend.02_features.02_iam.08_auth.reset")
    with pytest.raises(Exception):
        reset.verify_reset_token("tampered-token-value")

async def test_full_reset_flow(pool):
    svc = importlib.import_module("01_backend.02_features.02_iam.08_auth.service")
    user_repo = importlib.import_module("01_backend.02_features.02_iam.02_user.repository")
    async with pool.acquire() as conn:
        user = await user_repo.create_user(conn, {"email": "reset@test.com", "display_name": "Test"})
        token = await svc.request_password_reset(conn, email="reset@test.com")
        assert token is not None
        ok = await svc.confirm_password_reset(conn, token=token, new_password="NewPass123!")
    assert ok is True
```

Run: Expected FAIL

- [ ] **Step 2: Write `08_auth/reset.py`**

```python
# 01_backend/02_features/02_iam/08_auth/reset.py
import importlib
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

_cfg = importlib.import_module("01_backend.01_core.config")
_SALT = "password-reset"
_MAX_AGE = 3600  # 1 hour

def _serializer():
    return URLSafeTimedSerializer(_cfg.JWT_SECRET)

def generate_reset_token(user_id: str, email: str) -> str:
    return _serializer().dumps({"user_id": user_id, "email": email}, salt=_SALT)

def verify_reset_token(token: str) -> dict:
    try:
        return _serializer().loads(token, salt=_SALT, max_age=_MAX_AGE)
    except SignatureExpired:
        raise ValueError("Reset token has expired")
    except BadSignature:
        raise ValueError("Invalid reset token")
```

- [ ] **Step 3: Add reset service methods to `08_auth/service.py`**

```python
async def request_password_reset(conn, email: str) -> str | None:
    """Returns signed token (caller sends via email). Returns None if user not found."""
    _reset = importlib.import_module("01_backend.02_features.02_iam.08_auth.reset")
    user = await _user_repo.get_user_by_email(conn, email)
    if not user:
        return None  # Silent — don't reveal whether email exists
    return _reset.generate_reset_token(user_id=str(user["id"]), email=email)

async def confirm_password_reset(conn, token: str, new_password: str) -> bool:
    _reset = importlib.import_module("01_backend.02_features.02_iam.08_auth.reset")
    payload = _reset.verify_reset_token(token)  # raises on invalid/expired
    hashed = _hash_password(new_password)
    await _user_repo.update_password(conn, user_id=payload["user_id"], password_hash=hashed)
    return True
```

- [ ] **Step 4: Add routes to `08_auth/routes.py`**

```python
@router.post("/v1/auth/forgot-password")
async def forgot_password(body: _sch.ForgotPasswordRequest):
    """Sends reset email. Always returns ok=true to prevent email enumeration."""
    pool = await _db.get_pool()
    async with pool.acquire() as conn:
        token = await _svc.request_password_reset(conn, email=body.email)
    if token:
        # Send via notify module (fire-and-forget)
        asyncio.create_task(_send_reset_email(body.email, token))
    return _resp.ok({"message": "If that email exists, a reset link has been sent"})

@router.post("/v1/auth/reset-password")
async def reset_password(body: _sch.ResetPasswordRequest):
    pool = await _db.get_pool()
    async with pool.acquire() as conn:
        await _svc.confirm_password_reset(conn, token=body.token, new_password=body.new_password)
    return _resp.ok({"message": "Password updated"})
```

Schemas:
```python
class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
```

- [ ] **Step 5: Run tests, commit**

```bash
cd tennetctl && .venv/bin/python -m pytest 01_backend/tests/02_iam/test_password_reset.py -v
git add 01_backend/02_features/02_iam/08_auth/ 01_backend/tests/02_iam/test_password_reset.py
git commit -m "feat(iam): password reset flow — forgot-password + reset-password endpoints"
```

---

## Task 4: Email Verification Flow

**Files:**
- Create: `01_backend/02_features/02_iam/08_auth/verify.py`
- Modify: `01_backend/02_features/02_iam/08_auth/routes.py`
- Modify: `01_backend/02_features/02_iam/08_auth/service.py`
- Modify: `01_backend/01_sql_migrations/` (add `email_verified_at` column to users)
- Create: `01_backend/tests/02_iam/test_email_verification.py`

- [ ] **Step 1: Write migration**

```sql
-- 20260404_user_email_verified.sql
ALTER TABLE fct_user ADD COLUMN IF NOT EXISTS
    email_verified_at TIMESTAMPTZ;
```

- [ ] **Step 2: Write failing test**

```python
# 01_backend/tests/02_iam/test_email_verification.py
import importlib, pytest

async def test_generate_verify_token():
    verify = importlib.import_module("01_backend.02_features.02_iam.08_auth.verify")
    token = verify.generate_verify_token(user_id="u1", email="a@b.com")
    assert len(token) > 20

async def test_verify_valid_token():
    verify = importlib.import_module("01_backend.02_features.02_iam.08_auth.verify")
    token = verify.generate_verify_token(user_id="u1", email="a@b.com")
    payload = verify.verify_token(token)
    assert payload["user_id"] == "u1"

async def test_confirm_email_sets_verified_at(pool):
    svc = importlib.import_module("01_backend.02_features.02_iam.08_auth.service")
    user_repo = importlib.import_module("01_backend.02_features.02_iam.02_user.repository")
    async with pool.acquire() as conn:
        user = await user_repo.create_user(conn, {"email": "verify@test.com", "display_name": "V"})
        token = await svc.send_email_verification(conn, user_id=str(user["id"]), email="verify@test.com")
        await svc.confirm_email_verification(conn, token=token)
        updated = await user_repo.get_user(conn, str(user["id"]))
    assert updated["email_verified_at"] is not None
```

- [ ] **Step 3: Write `08_auth/verify.py`**

```python
# 01_backend/02_features/02_iam/08_auth/verify.py
import importlib
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

_cfg = importlib.import_module("01_backend.01_core.config")
_SALT = "email-verification"
_MAX_AGE = 86400  # 24 hours

def _serializer():
    return URLSafeTimedSerializer(_cfg.JWT_SECRET)

def generate_verify_token(user_id: str, email: str) -> str:
    return _serializer().dumps({"user_id": user_id, "email": email}, salt=_SALT)

def verify_token(token: str) -> dict:
    try:
        return _serializer().loads(token, salt=_SALT, max_age=_MAX_AGE)
    except SignatureExpired:
        raise ValueError("Verification link has expired")
    except BadSignature:
        raise ValueError("Invalid verification link")
```

- [ ] **Step 4: Add service methods and routes**

Service:
```python
async def send_email_verification(conn, user_id: str, email: str) -> str:
    _verify = importlib.import_module("01_backend.02_features.02_iam.08_auth.verify")
    token = _verify.generate_verify_token(user_id=user_id, email=email)
    # Fire-and-forget email via notify
    asyncio.create_task(_send_verification_email(email, token))
    return token

async def confirm_email_verification(conn, token: str) -> bool:
    _verify = importlib.import_module("01_backend.02_features.02_iam.08_auth.verify")
    payload = _verify.verify_token(token)
    await conn.execute(
        "UPDATE fct_user SET email_verified_at = NOW() WHERE id = $1",
        payload["user_id"]
    )
    return True
```

Routes:
```python
@router.post("/v1/auth/send-verification")
async def send_verification(user: dict = Depends(_auth.current_user)):
    pool = await _db.get_pool()
    async with pool.acquire() as conn:
        await _svc.send_email_verification(conn, user_id=user["sub"], email=user["email"])
    return _resp.ok({"message": "Verification email sent"})

@router.post("/v1/auth/verify-email")
async def verify_email(body: _sch.VerifyEmailRequest):
    pool = await _db.get_pool()
    async with pool.acquire() as conn:
        await _svc.confirm_email_verification(conn, token=body.token)
    return _resp.ok({"message": "Email verified"})
```

- [ ] **Step 5: Run tests, commit**

```bash
cd tennetctl && .venv/bin/python -m pytest 01_backend/tests/02_iam/test_email_verification.py -v
git add 01_backend/02_features/02_iam/08_auth/ 01_backend/01_sql_migrations/20260404_user_email_verified.sql 01_backend/tests/02_iam/test_email_verification.py
git commit -m "feat(iam): email verification flow — send-verification + verify-email endpoints"
```

---

## Task 5: Social Login — Google + GitHub OAuth2

**Files:**
- Create: `01_backend/02_features/02_iam/08_auth/oauth.py`
- Modify: `01_backend/02_features/02_iam/08_auth/routes.py`
- Modify: `01_backend/02_features/02_iam/08_auth/service.py`
- Create: `01_backend/01_sql_migrations/20260404_oauth_identity.sql`
- Create: `01_backend/tests/02_iam/test_oauth.py`

- [ ] **Step 1: Write migration**

```sql
-- 20260404_oauth_identity.sql
CREATE TABLE IF NOT EXISTS fct_oauth_identity (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES fct_user(id),
    provider     TEXT NOT NULL,      -- 'google' | 'github'
    provider_id  TEXT NOT NULL,      -- provider's user ID
    access_token TEXT,               -- stored encrypted in production
    refresh_token TEXT,
    profile      JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, provider_id)
);
```

- [ ] **Step 2: Write failing test**

```python
# 01_backend/tests/02_iam/test_oauth.py
import importlib, pytest

async def test_oauth_callback_creates_user_and_identity(pool):
    svc = importlib.import_module("01_backend.02_features.02_iam.08_auth.service")
    async with pool.acquire() as conn:
        result = await svc.handle_oauth_callback(conn,
            provider="github",
            provider_id="gh-12345",
            email="gh@user.com",
            display_name="GH User",
            profile={"login": "ghuser", "avatar_url": "https://..."}
        )
    assert result["user"]["email"] == "gh@user.com"
    assert result["access_token"] is not None

async def test_oauth_callback_returns_existing_user(pool):
    svc = importlib.import_module("01_backend.02_features.02_iam.08_auth.service")
    async with pool.acquire() as conn:
        r1 = await svc.handle_oauth_callback(conn, provider="github",
            provider_id="gh-99999", email="existing@user.com",
            display_name="Existing", profile={})
        r2 = await svc.handle_oauth_callback(conn, provider="github",
            provider_id="gh-99999", email="existing@user.com",
            display_name="Existing", profile={})
    assert r1["user"]["id"] == r2["user"]["id"]  # Same user returned
```

- [ ] **Step 3: Write `08_auth/oauth.py`**

```python
# 01_backend/02_features/02_iam/08_auth/oauth.py
import importlib, httpx

_cfg = importlib.import_module("01_backend.01_core.config")

PROVIDERS = {
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "scope": "openid email profile",
    },
    "github": {
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "scope": "read:user user:email",
    },
}

def get_authorization_url(provider: str, state: str) -> str:
    p = PROVIDERS[provider]
    client_id = getattr(_cfg, f"OAUTH_{provider.upper()}_CLIENT_ID")
    redirect_uri = getattr(_cfg, f"OAUTH_{provider.upper()}_REDIRECT_URI")
    return (f"{p['auth_url']}?client_id={client_id}"
            f"&redirect_uri={redirect_uri}&scope={p['scope']}"
            f"&state={state}&response_type=code")

async def exchange_code(provider: str, code: str) -> dict:
    """Exchange authorization code for access token + user profile."""
    p = PROVIDERS[provider]
    client_id = getattr(_cfg, f"OAUTH_{provider.upper()}_CLIENT_ID")
    client_secret = getattr(_cfg, f"OAUTH_{provider.upper()}_CLIENT_SECRET")
    redirect_uri = getattr(_cfg, f"OAUTH_{provider.upper()}_REDIRECT_URI")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(p["token_url"], data={
            "client_id": client_id, "client_secret": client_secret,
            "code": code, "redirect_uri": redirect_uri, "grant_type": "authorization_code"
        }, headers={"Accept": "application/json"})
        token_data = token_resp.json()
        access_token = token_data["access_token"]

        profile_resp = await client.get(p["userinfo_url"],
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"})
        profile = profile_resp.json()

    email = profile.get("email") or profile.get("emails", [{}])[0].get("email", "")
    name = profile.get("name") or profile.get("login") or email
    provider_id = str(profile.get("id") or profile.get("sub"))

    return {"provider_id": provider_id, "email": email,
            "display_name": name, "profile": profile, "access_token": access_token}
```

- [ ] **Step 4: Add service method `handle_oauth_callback`**

```python
async def handle_oauth_callback(conn, provider: str, provider_id: str,
                                 email: str, display_name: str, profile: dict) -> dict:
    # Find or create identity
    identity = await conn.fetchrow(
        "SELECT * FROM fct_oauth_identity WHERE provider = $1 AND provider_id = $2",
        provider, provider_id
    )
    if identity:
        user = await _user_repo.get_user(conn, str(identity["user_id"]))
    else:
        # Find existing user by email or create new one
        user = await _user_repo.get_user_by_email(conn, email)
        if not user:
            user = await _user_repo.create_user(conn, {
                "email": email, "display_name": display_name,
                "email_verified_at": "NOW()"  # OAuth emails are pre-verified
            })
        await conn.execute(
            """INSERT INTO fct_oauth_identity (user_id, provider, provider_id, profile)
               VALUES ($1, $2, $3, $4::jsonb)""",
            user["id"], provider, provider_id, json.dumps(profile)
        )
    tokens = _issue_tokens(user)
    return {"user": dict(user), **tokens}
```

- [ ] **Step 5: Add OAuth routes**

```python
@router.get("/v1/auth/{provider}/authorize")
async def oauth_authorize(provider: str):
    if provider not in ("google", "github"):
        raise HTTPException(400, "Unsupported provider")
    import secrets
    state = secrets.token_urlsafe(16)
    url = _oauth.get_authorization_url(provider, state)
    return _resp.ok({"url": url, "state": state})

@router.get("/v1/auth/{provider}/callback")
async def oauth_callback(provider: str, code: str, state: str):
    if provider not in ("google", "github"):
        raise HTTPException(400, "Unsupported provider")
    profile_data = await _oauth.exchange_code(provider, code)
    pool = await _db.get_pool()
    async with pool.acquire() as conn:
        result = await _svc.handle_oauth_callback(conn, provider=provider, **profile_data)
    return _resp.ok(result)
```

- [ ] **Step 6: Add env vars to config**

In `01_backend/01_core/config.py` add:
```python
OAUTH_GOOGLE_CLIENT_ID     = os.getenv("OAUTH_GOOGLE_CLIENT_ID", "")
OAUTH_GOOGLE_CLIENT_SECRET = os.getenv("OAUTH_GOOGLE_CLIENT_SECRET", "")
OAUTH_GOOGLE_REDIRECT_URI  = os.getenv("OAUTH_GOOGLE_REDIRECT_URI", "http://localhost:18000/v1/auth/google/callback")
OAUTH_GITHUB_CLIENT_ID     = os.getenv("OAUTH_GITHUB_CLIENT_ID", "")
OAUTH_GITHUB_CLIENT_SECRET = os.getenv("OAUTH_GITHUB_CLIENT_SECRET", "")
OAUTH_GITHUB_REDIRECT_URI  = os.getenv("OAUTH_GITHUB_REDIRECT_URI", "http://localhost:18000/v1/auth/github/callback")
```

- [ ] **Step 7: Run tests, commit**

```bash
cd tennetctl && .venv/bin/python -m pytest 01_backend/tests/02_iam/test_oauth.py -v
git add 01_backend/02_features/02_iam/08_auth/ 01_backend/01_sql_migrations/20260404_oauth_identity.sql 01_backend/tests/02_iam/test_oauth.py 01_backend/01_core/config.py
git commit -m "feat(iam): social login — Google + GitHub OAuth2 authorization code flow"
```

---

## Task 6: RBAC — User-Role and Group-Role Assignment APIs

**Files:**
- Modify: `01_backend/02_features/02_iam/19_rbac/routes.py`
- Modify: `01_backend/02_features/02_iam/19_rbac/service.py`
- Modify: `01_backend/02_features/02_iam/19_rbac/repository.py`
- Modify: `01_backend/02_features/02_iam/19_rbac/schemas.py`
- Create: `01_backend/tests/02_iam/test_rbac_assignments.py`

- [ ] **Step 1: Write failing test**

```python
# 01_backend/tests/02_iam/test_rbac_assignments.py
import importlib, pytest

async def _setup(conn):
    role_repo = importlib.import_module("01_backend.02_features.02_iam.19_rbac.repository")
    role = await role_repo.create_role(conn, {"name": "editor", "scope": "org"})
    return role

async def test_assign_role_to_user(pool):
    repo = importlib.import_module("01_backend.02_features.02_iam.19_rbac.repository")
    async with pool.acquire() as conn:
        role = await _setup(conn)
        await repo.assign_role_to_user(conn, user_id="user-001", role_id=str(role["id"]),
                                       org_id="org-001")
        assignments = await repo.list_user_roles(conn, user_id="user-001", org_id="org-001")
    assert any(a["role_id"] == role["id"] for a in assignments)

async def test_list_user_effective_permissions(pool):
    repo = importlib.import_module("01_backend.02_features.02_iam.19_rbac.repository")
    async with pool.acquire() as conn:
        role = await _setup(conn)
        # Assign permission to role first
        perm = await repo.create_permission(conn, {"name": "orgs:read", "description": ""})
        await repo.assign_permission_to_role(conn, role_id=str(role["id"]), permission_id=str(perm["id"]))
        await repo.assign_role_to_user(conn, user_id="user-002", role_id=str(role["id"]), org_id="org-001")
        perms = await repo.get_user_effective_permissions(conn, user_id="user-002", org_id="org-001")
    assert any(p["name"] == "orgs:read" for p in perms)
```

- [ ] **Step 2: Add to `19_rbac/repository.py`**

```python
async def assign_role_to_user(conn, user_id: str, role_id: str, org_id: str) -> dict:
    row = await conn.fetchrow(
        """INSERT INTO lnk_user_role (user_id, role_id, org_id)
           VALUES ($1, $2, $3) ON CONFLICT DO NOTHING RETURNING *""",
        user_id, role_id, org_id
    )
    return dict(row) if row else {}

async def revoke_role_from_user(conn, user_id: str, role_id: str, org_id: str) -> bool:
    result = await conn.execute(
        "DELETE FROM lnk_user_role WHERE user_id=$1 AND role_id=$2 AND org_id=$3",
        user_id, role_id, org_id
    )
    return result == "DELETE 1"

async def list_user_roles(conn, user_id: str, org_id: str) -> list[dict]:
    rows = await conn.fetch(
        """SELECT r.* FROM fct_role r
           JOIN lnk_user_role ur ON r.id = ur.role_id
           WHERE ur.user_id = $1 AND ur.org_id = $2 AND r.is_deleted = FALSE""",
        user_id, org_id
    )
    return [dict(r) for r in rows]

async def assign_role_to_group(conn, group_id: str, role_id: str, org_id: str) -> dict:
    row = await conn.fetchrow(
        """INSERT INTO lnk_group_role (group_id, role_id, org_id)
           VALUES ($1, $2, $3) ON CONFLICT DO NOTHING RETURNING *""",
        group_id, role_id, org_id
    )
    return dict(row) if row else {}

async def get_user_effective_permissions(conn, user_id: str, org_id: str) -> list[dict]:
    rows = await conn.fetch(
        """SELECT DISTINCT p.* FROM fct_permission p
           JOIN lnk_role_permission rp ON p.id = rp.permission_id
           JOIN lnk_user_role ur ON rp.role_id = ur.role_id
           WHERE ur.user_id = $1 AND ur.org_id = $2""",
        user_id, org_id
    )
    return [dict(r) for r in rows]
```

- [ ] **Step 3: Add routes to `19_rbac/routes.py`**

```python
# User role assignments
@router.get("/v1/users/{user_id}/roles")
async def list_user_roles(user_id: str, org_id: str):
    ...

@router.post("/v1/users/{user_id}/roles")
async def assign_role_to_user(user_id: str, body: AssignRoleRequest):
    ...

@router.delete("/v1/users/{user_id}/roles/{role_id}")
async def revoke_role_from_user(user_id: str, role_id: str, org_id: str):
    ...

@router.get("/v1/users/{user_id}/permissions")
async def get_user_permissions(user_id: str, org_id: str):
    ...

# Group role assignments
@router.post("/v1/groups/{group_id}/roles")
async def assign_role_to_group(group_id: str, body: AssignRoleRequest):
    ...

@router.delete("/v1/groups/{group_id}/roles/{role_id}")
async def revoke_role_from_group(group_id: str, role_id: str, org_id: str):
    ...
```

- [ ] **Step 4: Check migration — ensure `lnk_user_role` and `lnk_group_role` tables exist**

If not in existing migrations, create:
```sql
-- 20260404_rbac_assignments.sql
CREATE TABLE IF NOT EXISTS lnk_user_role (
    user_id  TEXT NOT NULL,
    role_id  UUID NOT NULL REFERENCES fct_role(id),
    org_id   TEXT NOT NULL,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id, org_id)
);
CREATE TABLE IF NOT EXISTS lnk_group_role (
    group_id UUID NOT NULL,
    role_id  UUID NOT NULL REFERENCES fct_role(id),
    org_id   TEXT NOT NULL,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (group_id, role_id, org_id)
);
```

- [ ] **Step 5: Run tests, commit**

```bash
cd tennetctl && .venv/bin/python -m pytest 01_backend/tests/02_iam/test_rbac_assignments.py -v
git add 01_backend/02_features/02_iam/19_rbac/ 01_backend/tests/02_iam/test_rbac_assignments.py
git commit -m "feat(iam): RBAC user-role + group-role assignment APIs + effective permissions endpoint"
```

---

## Task 7: Route the Existing `logout_all` Function

**Files:**
- Modify: `01_backend/02_features/02_iam/08_auth/routes.py` (add 1 route)

- [ ] **Step 1: Check service.py for `logout_all` signature**

```bash
grep -n "logout_all" tennetctl/01_backend/02_features/02_iam/08_auth/service.py
```

- [ ] **Step 2: Add route**

```python
@router.post("/v1/auth/logout-all")
async def logout_all(user: dict = Depends(_auth.current_user)):
    pool = await _db.get_pool()
    async with pool.acquire() as conn:
        count = await _svc.logout_all(conn, user_id=user["sub"])
    return _resp.ok({"revoked_sessions": count})
```

- [ ] **Step 3: Commit**

```bash
git add 01_backend/02_features/02_iam/08_auth/routes.py
git commit -m "fix(iam): expose existing logout_all as POST /v1/auth/logout-all"
```

---

## Task 8: User Search

**Files:**
- Modify: `01_backend/02_features/02_iam/02_user/repository.py`
- Modify: `01_backend/02_features/02_iam/02_user/routes.py`

- [ ] **Step 1: Add `search_users` to repository**

```python
async def search_users(conn, query: str, limit: int = 20) -> list[dict]:
    rows = await conn.fetch(
        """SELECT * FROM fct_user
           WHERE is_deleted = FALSE
             AND (email ILIKE $1 OR display_name ILIKE $1)
           ORDER BY created_at DESC LIMIT $2""",
        f"%{query}%", limit
    )
    return [dict(r) for r in rows]
```

- [ ] **Step 2: Add route**

```python
@router.get("/v1/users/search")
async def search_users(q: str, limit: int = 20):
    pool = await _db.get_pool()
    async with pool.acquire() as conn:
        result = await _svc.search_users(conn, query=q, limit=limit)
    return _resp.ok(result)
```

- [ ] **Step 3: Commit**

```bash
git add 01_backend/02_features/02_iam/02_user/
git commit -m "feat(iam): user search by email/display_name — GET /v1/users/search"
```

---

## Task 9: License Entitlement Check Endpoint

**Files:**
- Modify: `01_backend/02_features/02_iam/25_license_profile/routes.py`
- Modify: `01_backend/02_features/02_iam/25_license_profile/repository.py`

- [ ] **Step 1: Add repository method**

```python
async def check_entitlement(conn, org_id: str, feature_key: str) -> bool:
    """Returns True if org's license includes the feature."""
    row = await conn.fetchrow(
        """SELECT lp.feature_limits->$2 AS entitled
           FROM fct_org_license ol
           JOIN dim_license_profile lp ON ol.profile_id = lp.id
           WHERE ol.org_id = $1 AND ol.is_deleted = FALSE
           LIMIT 1""",
        org_id, feature_key
    )
    if not row:
        return False
    val = row["entitled"]
    return bool(val) and val != "false" and val != "0"
```

- [ ] **Step 2: Add route**

```python
@router.get("/v1/orgs/{org_id}/license/check/{feature_key}")
async def check_entitlement(org_id: str, feature_key: str):
    pool = await _db.get_pool()
    async with pool.acquire() as conn:
        entitled = await _repo.check_entitlement(conn, org_id=org_id, feature_key=feature_key)
    return _resp.ok({"entitled": entitled, "feature": feature_key})
```

- [ ] **Step 3: Commit**

```bash
git add 01_backend/02_features/02_iam/25_license_profile/
git commit -m "feat(iam): license entitlement check — GET /v1/orgs/{org_id}/license/check/{feature_key}"
```

---

## Verification Checklist

- [ ] `POST /v1/auth/forgot-password` — returns ok=true, token generated
- [ ] `POST /v1/auth/reset-password` — with valid token, updates password hash
- [ ] `POST /v1/auth/send-verification` — token generated (authenticated)
- [ ] `POST /v1/auth/verify-email` — with valid token, sets `email_verified_at`
- [ ] `GET /v1/auth/google/authorize` — returns redirect URL with state
- [ ] `GET /v1/auth/github/authorize` — returns redirect URL with state
- [ ] `GET /v1/orgs?limit=2&offset=0` — returns first page
- [ ] `GET /v1/orgs?limit=2&offset=2` — returns different page
- [ ] `GET /v1/users?limit=2&offset=0` — paginated
- [ ] `GET /v1/groups/{id}/members?limit=2&offset=0` — paginated
- [ ] `POST /v1/users/{id}/roles` — assigns role, visible in `GET /v1/users/{id}/permissions`
- [ ] `POST /v1/groups/{id}/roles` — assigns role to group
- [ ] `POST /v1/auth/logout-all` — revokes all sessions
- [ ] `GET /v1/users/search?q=test` — returns matching users
- [ ] `GET /v1/orgs/{id}/license/check/analytics` — returns entitled boolean
- [ ] FastAPI `Depends(current_user)` on protected routes — 401 without token, 200 with valid token
- [ ] `pytest 01_backend/tests/` — all new tests pass
