# IAM Auth — Design

## File layout

```text
backend/02_features/iam/auth/
├── __init__.py           — exports router + middleware factory
├── schemas.py            — Pydantic v2 request/response models
├── repository.py         — asyncpg raw SQL
├── service.py            — login / logout / refresh / me business logic
└── routes.py             — FastAPI APIRouter (4 endpoints)

backend/01_core/
└── jwt_middleware.py     — installed by 01_core/app.py on every request
```

## Schemas (Pydantic v2)

```python
# backend/02_features/iam/auth/schemas.py

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=1024)


class UserSummary(BaseModel):
    id:           str
    username:     str
    email:        EmailStr
    account_type: str          # e.g. "default_admin"


class SessionSummary(BaseModel):
    id:                  str
    refresh_expires_at:  datetime
    absolute_expires_at: datetime


class LoginData(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         UserSummary


class RefreshData(BaseModel):
    access_token: str
    token_type:   str = "bearer"


class MeData(BaseModel):
    user:    UserSummary
    session: SessionSummary
```

## Repository

```python
# backend/02_features/iam/auth/repository.py

from datetime import datetime, timedelta
from typing import NamedTuple

from backend.core.ids import new_uuid_v7


class UserRow(NamedTuple):
    id:           str
    username:     str
    email:        str
    account_type: str


class SessionRow(NamedTuple):
    id:                  str
    user_id:             str
    refresh_token_hash:  str
    refresh_expires_at:  datetime
    absolute_expires_at: datetime


async def get_user_by_username(conn, username: str) -> UserRow | None:
    row = await conn.fetchrow(
        '''SELECT id, username, email, account_type
             FROM "03_iam".v_users
            WHERE username = $1
              AND is_deleted = FALSE
              AND is_active  = TRUE''',
        username,
    )
    if row is None:
        return None
    return UserRow(**row)


async def get_user_by_id(conn, user_id: str) -> UserRow | None:
    row = await conn.fetchrow(
        '''SELECT id, username, email, account_type
             FROM "03_iam".v_users
            WHERE id = $1
              AND is_deleted = FALSE
              AND is_active  = TRUE''',
        user_id,
    )
    if row is None:
        return None
    return UserRow(**row)


async def get_password_hash(conn, user_id: str) -> str | None:
    return await conn.fetchval(
        '''SELECT a.key_text
             FROM "03_iam"."20_dtl_attrs" a
             JOIN "03_iam"."07_dim_attr_defs" d ON a.attr_def_id = d.id
            WHERE a.entity_id = $1
              AND d.code = 'password_hash' ''',
        user_id,
    )


async def create_session(
    conn,
    *,
    user_id:              str,
    token_prefix:         str,
    access_token_hash:    str,
    refresh_token_hash:   str,
    refresh_token_prefix: str,
    jti:                  str,
    ip_address:           str | None,
    user_agent:           str | None,
) -> tuple[str, datetime, datetime]:
    """Insert session row + EAV attrs. Returns (session_id, refresh_expires_at,
    absolute_expires_at)."""

    now                 = datetime.utcnow()
    refresh_expires_at  = now + timedelta(days=7)
    absolute_expires_at = now + timedelta(days=30)
    session_id          = new_uuid_v7()

    active_id = await conn.fetchval(
        'SELECT id FROM "03_iam"."08_dim_session_statuses" WHERE code = $1',
        'active',
    )

    await conn.execute(
        '''INSERT INTO "03_iam"."20_fct_sessions"
               (id, user_id, status_id,
                token_prefix, refresh_token_hash, refresh_token_prefix,
                refresh_expires_at, expires_at, absolute_expires_at,
                last_seen_at, created_by, updated_by)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$2,$2)''',
        session_id, user_id, active_id,
        token_prefix, refresh_token_hash, refresh_token_prefix,
        refresh_expires_at,
        refresh_expires_at,   # expires_at mirrors refresh_expires_at
        absolute_expires_at,
        now,
    )

    # EAV attrs for audit (token_hash, jti, optional ip/ua)
    session_et_id = await conn.fetchval(
        'SELECT id FROM "03_iam"."06_dim_entity_types" WHERE code = $1',
        'iam_session',
    )

    async def _attr(code: str, value: str) -> None:
        attr_id = await conn.fetchval(
            '''SELECT d.id FROM "03_iam"."07_dim_attr_defs" d
                WHERE d.code = $1
                  AND d.entity_type_id = $2''',
            code, session_et_id,
        )
        await conn.execute(
            '''INSERT INTO "03_iam"."20_dtl_attrs"
                   (id, entity_type_id, entity_id, attr_def_id, key_text)
               VALUES ($1,$2,$3,$4,$5)''',
            new_uuid_v7(), session_et_id, session_id, attr_id, value,
        )

    await _attr('token_hash', access_token_hash)
    await _attr('jti', jti)
    if ip_address:
        await _attr('ip_address', ip_address)
    if user_agent:
        await _attr('user_agent', user_agent[:1024])

    return session_id, refresh_expires_at, absolute_expires_at


async def find_session_by_refresh_prefix(
    conn, prefix: str
) -> SessionRow | None:
    """Find the active session whose refresh_token_prefix matches.
    Returns None if not found. Caller must Argon2id-verify the full hash."""
    row = await conn.fetchrow(
        '''SELECT id, user_id, refresh_token_hash,
                  refresh_expires_at, absolute_expires_at
             FROM "03_iam"."20_fct_sessions"
            WHERE refresh_token_prefix = $1
              AND deleted_at IS NULL
              AND status_id = (
                  SELECT id FROM "03_iam"."08_dim_session_statuses"
                   WHERE code = 'active'
              )''',
        prefix,
    )
    if row is None:
        return None
    return SessionRow(**row)


async def rotate_refresh_token(
    conn,
    session_id:           str,
    new_refresh_hash:     str,
    new_refresh_prefix:   str,
    new_jti:              str,
    new_access_token_hash: str,
) -> None:
    """Atomically replace the refresh token hash + prefix and update the
    jti EAV attr. Called inside a transaction."""
    await conn.execute(
        '''UPDATE "03_iam"."20_fct_sessions"
              SET refresh_token_hash   = $1,
                  refresh_token_prefix = $2,
                  last_seen_at         = CURRENT_TIMESTAMP,
                  updated_at           = CURRENT_TIMESTAMP
            WHERE id = $3''',
        new_refresh_hash, new_refresh_prefix, session_id,
    )
    # Update jti EAV attr for audit correlation
    session_et_id = await conn.fetchval(
        'SELECT id FROM "03_iam"."06_dim_entity_types" WHERE code = $1',
        'iam_session',
    )
    jti_attr_id = await conn.fetchval(
        '''SELECT id FROM "03_iam"."07_dim_attr_defs"
            WHERE code = 'jti' AND entity_type_id = $1''',
        session_et_id,
    )
    await conn.execute(
        '''UPDATE "03_iam"."20_dtl_attrs"
              SET key_text   = $1,
                  updated_at = CURRENT_TIMESTAMP
            WHERE entity_id = $2 AND attr_def_id = $3''',
        new_jti, session_id, jti_attr_id,
    )


async def revoke_session(conn, session_id: str) -> None:
    revoked_id = await conn.fetchval(
        'SELECT id FROM "03_iam"."08_dim_session_statuses" WHERE code = $1',
        'revoked',
    )
    await conn.execute(
        '''UPDATE "03_iam"."20_fct_sessions"
              SET status_id  = $1,
                  deleted_at = CURRENT_TIMESTAMP,
                  updated_at = CURRENT_TIMESTAMP
            WHERE id = $2''',
        revoked_id, session_id,
    )


async def get_session_summary(conn, session_id: str) -> SessionRow | None:
    row = await conn.fetchrow(
        '''SELECT id, user_id, refresh_token_hash,
                  refresh_expires_at, absolute_expires_at
             FROM "03_iam"."20_fct_sessions"
            WHERE id = $1 AND deleted_at IS NULL''',
        session_id,
    )
    if row is None:
        return None
    return SessionRow(**row)
```

## Service — login with timing equalisation

```python
# backend/02_features/iam/auth/service.py

import secrets
from datetime import datetime, timedelta
from typing import NamedTuple

from backend.core.ids import new_uuid_v7
from backend.core.password import hash_password, verify_password
from backend.core.events import emit_event
from backend.core.jwt import build_jwt           # wraps python-jose
from . import repository as repo


_DUMMY_HASH = hash_password("tennetctl-timing-dummy-do-not-use")


class LoginResult(NamedTuple):
    session_id:          str
    access_token:        str   # raw JWT — returned once, never persisted
    refresh_token:       str   # raw opaque — returned once, never persisted
    user:                repo.UserRow
    refresh_expires_at:  datetime
    absolute_expires_at: datetime


async def login(
    conn,
    *,
    username:   str,
    password:   str,
    ip_address: str | None,
    user_agent: str | None,
    jwt_secret: str,
    jwt_expiry: int,           # seconds, from config
) -> LoginResult:
    user = await repo.get_user_by_username(conn, username)

    if user is None:
        verify_password(_DUMMY_HASH, password)   # equalise latency
        await emit_event("iam.login.failed",
                         {"username": username, "reason": "user_not_found",
                          "ip": ip_address})
        raise InvalidCredentials()

    stored_hash = await repo.get_password_hash(conn, user.id)
    if stored_hash is None:
        verify_password(_DUMMY_HASH, password)
        await emit_event("iam.login.failed",
                         {"username": username, "reason": "no_hash",
                          "ip": ip_address})
        raise InvalidCredentials()

    if not verify_password(stored_hash, password):
        await emit_event("iam.login.failed",
                         {"username": username, "reason": "wrong_password",
                          "ip": ip_address})
        raise InvalidCredentials()

    # Generate tokens
    jti           = new_uuid_v7()
    access_token  = build_jwt(sub=user.id, sid=None,   # sid filled after insert
                               jti=jti, secret=jwt_secret, expiry=jwt_expiry)
    refresh_raw   = secrets.token_urlsafe(48)

    token_prefix         = access_token[:16]
    access_token_hash    = hash_password(access_token)   # audit only
    refresh_token_hash   = hash_password(refresh_raw)
    refresh_token_prefix = refresh_raw[:16]

    session_id, refresh_expires_at, absolute_expires_at = await repo.create_session(
        conn,
        user_id              = user.id,
        token_prefix         = token_prefix,
        access_token_hash    = access_token_hash,
        refresh_token_hash   = refresh_token_hash,
        refresh_token_prefix = refresh_token_prefix,
        jti                  = jti,
        ip_address           = ip_address,
        user_agent           = user_agent,
    )

    # Re-issue JWT now that we have session_id for the sid claim
    access_token = build_jwt(sub=user.id, sid=session_id,
                              jti=jti, secret=jwt_secret, expiry=jwt_expiry)

    await emit_event("iam.user.logged_in",
                     {"user_id": user.id, "session_id": session_id,
                      "ip": ip_address})

    return LoginResult(
        session_id          = session_id,
        access_token        = access_token,
        refresh_token       = refresh_raw,
        user                = user,
        refresh_expires_at  = refresh_expires_at,
        absolute_expires_at = absolute_expires_at,
    )
```

## Service — refresh

```python
async def refresh(
    conn,
    *,
    refresh_cookie: str,
    jwt_secret:     str,
    jwt_expiry:     int,
) -> tuple[str, str]:
    """Rotate refresh token, issue new JWT.
    Returns (new_access_token, new_refresh_raw)."""

    prefix = refresh_cookie[:16]
    session = await repo.find_session_by_refresh_prefix(conn, prefix)

    if session is None or not verify_password(session.refresh_token_hash, refresh_cookie):
        raise InvalidRefreshToken()

    now = datetime.utcnow()
    if now > session.refresh_expires_at:
        raise RefreshTokenExpired()
    if now > session.absolute_expires_at:
        raise SessionExpired()

    new_refresh_raw    = secrets.token_urlsafe(48)
    new_refresh_hash   = hash_password(new_refresh_raw)
    new_refresh_prefix = new_refresh_raw[:16]
    new_jti            = new_uuid_v7()
    new_access_token   = build_jwt(sub=session.user_id, sid=session.id,
                                    jti=new_jti, secret=jwt_secret, expiry=jwt_expiry)
    new_access_hash    = hash_password(new_access_token)

    async with conn.transaction():
        await repo.rotate_refresh_token(
            conn,
            session_id            = session.id,
            new_refresh_hash      = new_refresh_hash,
            new_refresh_prefix    = new_refresh_prefix,
            new_jti               = new_jti,
            new_access_token_hash = new_access_hash,
        )

    return new_access_token, new_refresh_raw
```

## Service — logout + me

```python
async def logout(conn, *, session_id: str, user_id: str) -> None:
    await repo.revoke_session(conn, session_id)
    await emit_event("iam.user.logged_out",
                     {"user_id": user_id, "session_id": session_id})


async def me(conn, *, user_id: str, session_id: str) -> MeData:
    user    = await repo.get_user_by_id(conn, user_id)
    session = await repo.get_session_summary(conn, session_id)
    return MeData(
        user    = UserSummary(**user._asdict()),
        session = SessionSummary(
            id                  = session.id,
            refresh_expires_at  = session.refresh_expires_at,
            absolute_expires_at = session.absolute_expires_at,
        ),
    )
```

## Routes

```python
# backend/02_features/iam/auth/routes.py

router = APIRouter(prefix="/v1/auth", tags=["auth"])

_REFRESH_COOKIE = "tcc_refresh"
_REFRESH_TTL    = 7 * 24 * 3600   # 604800 seconds


@router.post("/login")
async def login_route(req: s.LoginRequest, request: Request, response: Response):
    cfg = request.app.state.config
    async with request.app.state.db_pool.acquire() as conn:
        try:
            result = await service.login(
                conn,
                username   = req.username,
                password   = req.password,
                ip_address = request.client.host if request.client else None,
                user_agent = request.headers.get("user-agent"),
                jwt_secret = cfg.jwt_secret,
                jwt_expiry = cfg.jwt_expiry_seconds,
            )
        except service.InvalidCredentials:
            return err("INVALID_CREDENTIALS", "Invalid username or password", 401)

    response.set_cookie(
        key      = _REFRESH_COOKIE,
        value    = result.refresh_token,
        max_age  = _REFRESH_TTL,
        httponly = True,
        secure   = cfg.cookie_secure,
        samesite = "strict",
        path     = "/v1/auth",
    )
    return ok(s.LoginData(
        access_token = result.access_token,
        user         = s.UserSummary(**result.user._asdict()),
    ))


@router.post("/refresh")
async def refresh_route(request: Request, response: Response):
    cfg            = request.app.state.config
    refresh_cookie = request.cookies.get(_REFRESH_COOKIE)
    if not refresh_cookie:
        return err("REFRESH_TOKEN_REQUIRED", "Refresh token required", 401)

    async with request.app.state.db_pool.acquire() as conn:
        try:
            new_access, new_refresh = await service.refresh(
                conn,
                refresh_cookie = refresh_cookie,
                jwt_secret     = cfg.jwt_secret,
                jwt_expiry     = cfg.jwt_expiry_seconds,
            )
        except service.InvalidRefreshToken:
            return err("INVALID_REFRESH_TOKEN", "Invalid refresh token", 401)
        except service.RefreshTokenExpired:
            return err("REFRESH_TOKEN_EXPIRED", "Refresh token expired", 401)
        except service.SessionExpired:
            return err("SESSION_EXPIRED", "Session expired, please log in again", 401)

    response.set_cookie(
        key=_REFRESH_COOKIE, value=new_refresh, max_age=_REFRESH_TTL,
        httponly=True, secure=cfg.cookie_secure, samesite="strict",
        path="/v1/auth",
    )
    return ok(s.RefreshData(access_token=new_access))


@router.post("/logout", status_code=204)
async def logout_route(request: Request, response: Response):
    async with request.app.state.db_pool.acquire() as conn:
        await service.logout(
            conn,
            session_id = request.state.session_id,
            user_id    = request.state.user_id,
        )
    response.delete_cookie(_REFRESH_COOKIE, path="/v1/auth")
    return Response(status_code=204)


@router.get("/me")
async def me_route(request: Request):
    async with request.app.state.db_pool.acquire() as conn:
        data = await service.me(
            conn,
            user_id    = request.state.user_id,
            session_id = request.state.session_id,
        )
    return ok(data)
```

## JWT middleware

```python
# backend/01_core/jwt_middleware.py

from jose import JWTError, jwt as jose_jwt

EXEMPT_PATHS = {
    "/healthz",
    "/v1/auth/login",
    "/v1/auth/refresh",
    "/v1/vault/status",
    "/v1/vault/unseal",
    "/v1/vault/seal",
}


async def jwt_middleware(request: Request, call_next):
    if request.url.path in EXEMPT_PATHS:
        return await call_next(request)

    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return err("TOKEN_REQUIRED", "Authentication required", 401)

    token = auth.removeprefix("Bearer ")
    cfg   = request.app.state.config

    try:
        payload = jose_jwt.decode(token, cfg.jwt_secret, algorithms=["HS256"])
    except JWTError:
        return err("INVALID_TOKEN", "Invalid or expired token", 401)

    session_id = payload.get("sid")
    user_id    = payload.get("sub")

    # Single PK lookup to confirm the session has not been revoked
    async with request.app.state.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            '''SELECT status_id, deleted_at
                 FROM "03_iam"."20_fct_sessions"
                WHERE id = $1''',
            session_id,
        )

    if row is None or row["deleted_at"] is not None:
        return err("SESSION_REVOKED", "Session has been revoked", 401)

    request.state.user_id    = user_id
    request.state.session_id = session_id
    return await call_next(request)
```

`python-jose[cryptography]` handles HS256 signature verification and `exp`
/ `nbf` claim checking. The `algorithms=["HS256"]` argument locks the
algorithm — no alg confusion is possible.

## JWT helper

```python
# backend/01_core/jwt.py

from datetime import datetime, timedelta
from jose import jwt as jose_jwt


def build_jwt(
    *,
    sub:    str,
    sid:    str | None,
    jti:    str,
    secret: str,
    expiry: int,
) -> str:
    now = datetime.utcnow()
    claims = {
        "sub": sub,
        "sid": sid,
        "jti": jti,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(seconds=expiry),
    }
    return jose_jwt.encode(claims, secret, algorithm="HS256")
```

## Testing strategy

- **Unit tests** for `service.login`: valid credentials, wrong password,
  unknown username, missing password_hash attr.
- **Timing test**: "user not found" vs "wrong password" latency within 10%
  over 50 trials.
- **Unit tests** for `service.refresh`: valid rotate, stale token rejected,
  past `refresh_expires_at`, past `absolute_expires_at`.
- **Middleware tests** with FastAPI `TestClient`:
  - missing header → 401 `TOKEN_REQUIRED`
  - invalid signature → 401 `INVALID_TOKEN`
  - expired JWT → 401 `INVALID_TOKEN` (jose raises on exp)
  - revoked session → 401 `SESSION_REVOKED`
  - valid JWT → handler runs, state populated
  - exempt paths → no auth check
- **Integration test**: install → login → /me → refresh → /me → logout → /me (401).

## Security notes

- `python-jose` with `algorithms=["HS256"]` — no alg confusion possible.
- Refresh token raw value exists in memory only for the duration of the
  login/refresh response. After the response is sent, only the Argon2id
  hash remains.
- `secrets.token_urlsafe(48)` gives 384 bits of entropy for the refresh
  token — well above any practical brute-force threshold.
- The refresh cookie path is `/v1/auth` not `/` — it is only sent to
  auth endpoints, reducing its exposure surface.
- Access token is returned in the response body, not a cookie — the
  frontend must store it in memory. If stored in localStorage or
  sessionStorage it is accessible to XSS. Document this in the frontend
  integration guide.
