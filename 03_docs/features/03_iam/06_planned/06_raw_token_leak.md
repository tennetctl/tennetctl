## Planned: Zero Raw Token After Cookie Is Set

**Severity if unbuilt:** CRITICAL (theoretical — requires exception + log access)
**Affects:** `backend/02_features/iam/auth/routes.py`

## Problem

In `login_route`, `result.raw_token` (the `secrets.token_urlsafe(32)`
string) stays alive in the stack frame while the response is built. If an
unhandled exception is raised during response serialization (e.g., Pydantic
validation of `LoginData`), the exception traceback that ends up in the log
may include local variable values, including `result.raw_token`. Anyone with
log access gets a valid session token.

## Fix when built

Wrap the response-building block in `login_route` in a `try/finally` that
explicitly overwrites the token reference:

```python
raw = result.raw_token
try:
    response.set_cookie(key="tcc_session", value=raw, ...)
    return ok(LoginData(...))
finally:
    # Python strings are immutable so we can't zero the bytes, but we can
    # drop the reference so the GC collects it as early as possible.
    del raw
    result = None  # type: ignore
```

Note: Python strings are immutable — we cannot zero the underlying bytes.
This fix reduces the window (drops references immediately) but does not
eliminate the theoretical risk of a memory dump. That risk is accepted for
v1 (see `09_password_policy.md` for the same reasoning on password bytes).
A full fix requires `bytearray` throughout the login flow, which is
significant refactor work.
