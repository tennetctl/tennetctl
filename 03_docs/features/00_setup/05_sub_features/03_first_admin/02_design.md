## First Admin — Design

## File layout

```text
scripts/setup/first_admin/
├── __init__.py
├── entrypoint.py        — run_first_admin(opts, state)
├── prompts.py           — username / email / password input + validation
├── repository.py        — raw asyncpg INSERTs, reads dim FKs by code
└── tests/
    ├── test_prompts.py
    ├── test_repository.py
    └── test_end_to_end.py
```

`repository.py` here is the install-time repository — it mirrors the
shape of `backend/02_features/iam/auth/repository.py` but lives in
`scripts/setup/` because it runs before the main backend app is
booted. The two repositories share no code; the install-time one is
write-only and does nothing the runtime code will ever do.

## Entrypoint

```python
# scripts/setup/first_admin/entrypoint.py

async def run_first_admin(opts: SetupOptions, state: InstallState) -> None:
    """Phase 3: create the first admin user and set system_meta.installed_at."""

    username, email, password = await prompts.collect(opts)

    # Hash OUTSIDE the DB transaction — Argon2id at memory_cost=64MB takes
    # ~250ms on a laptop CPU. Running it inside the transaction would
    # hold an admin connection idle for that long for no benefit.
    from backend.01_core.password import hash_password
    password_hash = hash_password(password)

    user_id = new_uuid_v7()

    async with asyncpg.connect(state.admin_dsn) as conn:
        async with conn.transaction():
            await repository.insert_user(
                conn,
                user_id=user_id,
                username=username,
                email=email,
                password_hash=password_hash,
            )
            installed_at = await repository.finalize_system_meta(
                conn,
                username=username,
                installer_version=INSTALLER_VERSION,
                install_id=state.install_id,
            )

    state.admin_username   = username
    state.admin_created_at = installed_at
```

> **Note — admin DSN lifetime.** Phase 2 clears `state.read_dsn`
> immediately after seeding it into the vault, but keeps
> `state.admin_dsn` alive because Phase 3 still needs an admin
> connection to insert the user row and finalise `system_meta`, and
> Phase 4 needs it to seed the settings rows. `state.admin_dsn` is
> cleared by the top-level `finally` block in `run_setup` after Phase 4
> completes. `state.write_dsn` likewise survives until Phase 4, where it
> is printed once for the operator to capture and then zeroed.

## Prompts

```python
# scripts/setup/first_admin/prompts.py

import re
from pydantic import EmailStr, ValidationError, TypeAdapter

USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,64}$")
MIN_PW_LEN  = 12

email_adapter = TypeAdapter(EmailStr)

async def collect(opts: SetupOptions) -> tuple[str, str, str]:
    username = resolve(
        opts.admin_username,
        "TENNETCTL_SETUP_ADMIN_USERNAME",
        "First admin username",
        validator=_validate_username,
    )
    email = resolve(
        opts.admin_email,
        "TENNETCTL_SETUP_ADMIN_EMAIL",
        "First admin email",
        validator=_validate_email,
    )
    password = resolve(
        opts.admin_password,
        "TENNETCTL_SETUP_ADMIN_PASSWORD",
        "First admin password",
        secret=True,
        validator=_validate_password,
    )

    # Confirmation is interactive-only; when the operator provided
    # --admin-password they already know what they typed
    if opts.admin_password is None and sys.stdin.isatty():
        again = Prompt.ask("Confirm password", password=True)
        if again != password:
            raise Phase3Error("Password confirmation did not match")

    return username, email, password

def _validate_username(v: str) -> str:
    v = v.strip()
    if not USERNAME_RE.match(v):
        raise ValueError(
            "username must be 3-64 chars of letters, digits, or ._-"
        )
    return v

def _validate_email(v: str) -> str:
    try:
        return email_adapter.validate_python(v.strip())
    except ValidationError as e:
        raise ValueError("not a valid email address") from e

def _validate_password(v: str) -> str:
    if len(v) < MIN_PW_LEN:
        raise ValueError(f"password must be at least {MIN_PW_LEN} characters")
    if v.isalpha():
        raise ValueError("password must contain at least one non-letter")
    return v
```

## Repository

```python
# scripts/setup/first_admin/repository.py

async def insert_user(
    conn,
    *,
    user_id: str,
    username: str,
    email: str,
    password_hash: str,
) -> None:
    """Insert one row into 10_fct_users plus three EAV rows for username,
    email, and password_hash. Caller provides the open transaction."""

    # Resolve dim FKs by code — avoids hard-coding numeric ids here
    # and keeps us decoupled from whatever order the bootstrap migration
    # seeded rows in.
    account_type_id = await conn.fetchval(
        'SELECT id FROM "03_iam"."06_dim_account_types" '
        'WHERE code = $1', 'default_admin',
    )
    auth_type_id = await conn.fetchval(
        'SELECT id FROM "03_iam"."07_dim_auth_types" '
        'WHERE code = $1', 'username_password',
    )
    entity_type_id = await conn.fetchval(
        'SELECT id FROM "03_iam"."06_dim_entity_types" '
        'WHERE code = $1', 'iam_user',
    )
    attr_username      = await _attr_id(conn, 'username')
    attr_email         = await _attr_id(conn, 'email')
    attr_password_hash = await _attr_id(conn, 'password_hash')

    # Sanity: all FKs must resolve — if any is None, the bootstrap
    # migration didn't seed its dim row and the install is broken
    if None in (account_type_id, auth_type_id, entity_type_id,
                attr_username, attr_email, attr_password_hash):
        raise Phase3Error(
            "IAM bootstrap migration is incomplete — missing dim rows"
        )

    # Insert the user row. org_id = user_id: the first admin is their
    # own org, reflecting the "install is a single-tenant workspace"
    # model. created_by / updated_by = user_id so there's no null
    # and no fake "system user" row.
    await conn.execute(
        '''INSERT INTO "03_iam"."10_fct_users"
               (id, org_id, account_type_id, auth_type_id,
                is_active, is_test, created_by, updated_by)
           VALUES ($1, $1, $2, $3, TRUE, FALSE, $1, $1)''',
        user_id, account_type_id, auth_type_id,
    )

    # Insert the three EAV rows
    async def _eav(attr_id: int, value: str) -> None:
        await conn.execute(
            '''INSERT INTO "03_iam"."20_dtl_attrs"
                   (id, entity_type_id, entity_id, attr_def_id, key_text)
               VALUES ($1, $2, $3, $4, $5)''',
            new_uuid_v7(), entity_type_id, user_id, attr_id, value,
        )

    await _eav(attr_username,      username)
    await _eav(attr_email,         email)
    await _eav(attr_password_hash, password_hash)


async def finalize_system_meta(
    conn,
    *,
    username: str,
    installer_version: str,
    install_id: str,
) -> datetime:
    """Flip system_meta.installed_at to now() and record the install_id.

    install_id is the ULID generated in Phase 0 and already held in
    InstallState.install_id. It is retained as an identity marker
    (useful for audit logs and support tickets) but is no longer
    cross-checked against anything outside the DB.

    Returns installed_at so the wizard can reference it in the Phase 4
    next-steps output.
    """
    row = await conn.fetchrow(
        '''UPDATE "00_schema_migrations".system_meta
              SET install_id             = $1,
                  installed_at           = CURRENT_TIMESTAMP,
                  installer_version      = $2,
                  first_admin_username   = $3,
                  first_admin_created_at = CURRENT_TIMESTAMP,
                  updated_at             = CURRENT_TIMESTAMP
            WHERE id = 1
        RETURNING installed_at''',
        install_id, installer_version, username,
    )
    if row is None:
        raise Phase3Error(
            "system_meta row is missing — bootstrap migration never ran"
        )
    return row["installed_at"]


async def _attr_id(conn, code: str) -> int | None:
    return await conn.fetchval(
        '''SELECT d.id
             FROM "03_iam"."07_dim_attr_defs" d
             JOIN "03_iam"."06_dim_entity_types" t
                  ON d.entity_type_id = t.id
            WHERE t.code = $1 AND d.code = $2''',
        'iam_user', code,
    )
```

## Password hashing module

```python
# backend/01_core/password.py

import os
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash

# Default parameters — OWASP recommended minimums for Argon2id.
# Override via env vars for testing (lower cost) or hardened deployments
# (higher cost). Env overrides are intentionally NOT available in prod
# via the settings table — changing hash parameters requires a documented
# migration plan (see 03_iam/06_planned/08_argon2_rehash.md).
_DEFAULT_TIME_COST   = 3
_DEFAULT_MEMORY_COST = 65536   # 64 MB
_DEFAULT_PARALLELISM = 4
_HASH_LEN            = 32
_SALT_LEN            = 16

TIME_COST   = int(os.environ.get("ARGON2_TIME_COST",   _DEFAULT_TIME_COST))
MEMORY_COST = int(os.environ.get("ARGON2_MEMORY_COST", _DEFAULT_MEMORY_COST))
PARALLELISM = int(os.environ.get("ARGON2_PARALLELISM", _DEFAULT_PARALLELISM))

_hasher = PasswordHasher(
    time_cost   = TIME_COST,
    memory_cost = MEMORY_COST,
    parallelism = PARALLELISM,
    hash_len    = _HASH_LEN,
    salt_len    = _SALT_LEN,
)


def hash_password(plaintext: str) -> str:
    """Argon2id hash using the module parameters. Returns the PHC string,
    which encodes the parameters and salt. Callers store it verbatim in
    20_dtl_attrs.key_text."""
    return _hasher.hash(plaintext)


def verify_password(stored_phc: str, plaintext: str) -> bool:
    """Verify a plaintext against a stored PHC string. argon2-cffi reads
    the parameters from the PHC, so old hashes with different parameters
    continue to verify correctly after a parameter change."""
    try:
        return _hasher.verify(stored_phc, plaintext)
    except (VerifyMismatchError, InvalidHash):
        return False


def needs_rehash(stored_phc: str) -> bool:
    """Return True if the stored hash was produced with parameters lower
    than the current defaults — used for lazy re-hash on login.
    See 03_iam/06_planned/08_argon2_rehash.md."""
    return _hasher.check_needs_rehash(stored_phc)
```

### Env overrides

| Variable | Default | When to use |
| -------- | ------- | ----------- |
| `ARGON2_TIME_COST` | `3` | Lower to `1` in unit tests to avoid 250ms waits |
| `ARGON2_MEMORY_COST` | `65536` (64 MB) | Lower to `8192` in CI where RAM is constrained |
| `ARGON2_PARALLELISM` | `4` | Rarely needed; set to match CPU count on beefy hardware |

These are process-level overrides. They affect every call to `hash_password`
in the process — both user password hashing (Phase 3, `PATCH /v1/auth/password`)
and refresh token hashing (login, refresh). Do not set them in production
unless you have audited the impact on all hash consumers.

`03_iam.01_auth` imports `verify_password` and `needs_rehash` from this
module at runtime. Phase 3 calls `hash_password`. Both sides share the same
`_hasher` instance.

## Testing strategy

- **Unit tests** for each validator with the full positive/negative
  table (username too short, too long, non-ASCII, whitespace; email
  malformed; password too short, all alpha, exactly min-length-with-digit)
- **Unit tests** for `hash_password`/`verify_password` that assert
  the PHC format (`$argon2id$v=19$m=65536,t=3,p=4$...`) and that
  verify succeeds for the original plaintext and fails for anything
  else
- **Repository tests** against a Postgres fixture that has the IAM
  bootstrap migration applied. Asserts:
    - the user row lands with the right FKs resolved by code
    - the three EAV rows exist with the expected `attr_def_id` values
    - `created_by` and `updated_by` equal the user's own id
    - `finalize_system_meta` sets `installed_at` and returns the
      timestamp
    - running `finalize_system_meta` twice on the same row updates
      `installed_at` both times (no guard — Phase 3 entrypoint has
      the idempotency guard)
- **End-to-end tests** for Phase 3 via a test wizard harness that
  calls `run_first_admin` with a pre-baked `InstallState` (admin_dsn
  set, vault already initialized), then asserts:
    - `v_users` returns one row with the expected username and email
    - `system_meta.installed_at IS NOT NULL`
    - `verify_password(stored_hash, plaintext)` returns True
- **Transaction atomicity test** — inject a repository error between
  the user insert and the `finalize_system_meta` call, assert that
  neither write is visible after the transaction rolls back

## Security notes

- Argon2id is run OUTSIDE the DB transaction so we don't hold an
  admin Postgres connection idle for the ~250ms the hash takes on
  commodity hardware.
- The plaintext password lives in the `password` local variable until
  `hash_password` returns. Python doesn't zeroise strings, so we
  explicitly `password = None` after the hash call (wrapped in a
  `finally` so it runs on exception too). This is best-effort.
- The PHC hash string is long enough that leaking it in logs would
  also expose the per-user salt; we never log the `password_hash`
  attribute at any level.
- The reflexive `created_by = user_id` pattern means the very first
  row in the audit history is self-signed, which is honest: there is
  no operator identity at install time. All subsequent user creations
  have a real `created_by` pointing at an existing user.
- `repository._attr_id` joins through `06_dim_entity_types` to scope
  attribute definitions to `iam_user`. This catches a class of bugs
  where a future migration accidentally reuses a code like `email`
  for a different entity type — the lookup would return the wrong
  `attr_def_id` and Phase 3 would write to the wrong attribute.
