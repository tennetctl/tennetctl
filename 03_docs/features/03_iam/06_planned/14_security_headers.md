## Planned: HTTP Security Headers

**Severity if unbuilt:** LOW
**Affects:** `backend/01_core/app.py` (global middleware)

## Headers to add

```
Cache-Control: private, no-store     — on all auth-related responses
Vary: Cookie                         — signals proxy/CDN response is user-specific
X-Content-Type-Options: nosniff      — prevents MIME-type sniffing
X-Frame-Options: DENY                — prevents clickjacking
Referrer-Policy: no-referrer         — don't leak URL to third parties
```

## Implementation

A single `@app.middleware("http")` that injects these headers on every
response. Exempt nothing — even healthz benefits from `X-Content-Type-Options`.

`Cache-Control: private, no-store` should only be set on auth endpoints,
not globally, to avoid breaking future CDN-cacheable public routes. Use
a path prefix check (`/v1/auth/`).

## CSP (future)

Content-Security-Policy is deferred until the Next.js frontend is served
by or proxied through the backend. API-only responses don't need CSP.
