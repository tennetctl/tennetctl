## Planned: Secondary CSRF Protection

**Severity if unbuilt:** LOW
**Affects:** all state-changing endpoints

## Problem

`SameSite=Strict` on the session cookie is the primary CSRF mitigation and
covers the vast majority of attacks. The remaining gap is a same-site
attacker (unlikely but possible) and defence-in-depth best practice.

## Fix when built

Enforce `Content-Type: application/json` on all state-changing routes
(`POST`, `PATCH`, `DELETE`). HTML forms cannot set `Content-Type:
application/json`, so a CSRF form submission is rejected before it reaches
the route handler.

FastAPI already rejects non-JSON bodies for routes with Pydantic request
models. The remaining gap is routes with no request body (e.g., `POST
/v1/auth/logout`). Add a FastAPI dependency for those:

```python
async def require_json_content_type(request: Request):
    ct = request.headers.get("content-type", "")
    if not ct.startswith("application/json"):
        raise HTTPException(415, "Content-Type must be application/json")
```

Apply as `Depends(require_json_content_type)` on bodyless mutations.
