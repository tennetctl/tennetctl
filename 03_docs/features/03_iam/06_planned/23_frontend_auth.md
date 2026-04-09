## Planned: Frontend Auth — httpOnly Cookies + CSRF

**Severity if unbuilt:** HIGH (tokens in localStorage are readable by any XSS payload)
**Depends on:** security headers middleware (implemented in A3), backend CORS config (implemented in A2)

## Problem

Access and refresh tokens are stored in `localStorage` via `src/lib/api.ts`.
Any JavaScript injected via XSS can read them. httpOnly cookies cannot be
read by JavaScript, eliminating this attack surface.

## Scope when built

### Backend changes

1. Login response sets two cookies instead of (or in addition to) returning
   tokens in the body:
   - `access_token` — httpOnly, SameSite=Strict, Secure (prod), Path=/v1, MaxAge=900
   - `refresh_token` — httpOnly, SameSite=Strict, Secure (prod), Path=/v1/sessions, MaxAge=604800
2. Auth middleware (`04_backend/01_core/auth.py`) reads token from cookie if
   no `Authorization` header is present.
3. Logout clears both cookies by setting MaxAge=0.
4. CSRF double-submit: on login, also set a non-httpOnly `csrf_token` cookie.
   All mutating requests (POST/PATCH/DELETE) must include matching
   `X-CSRF-Token` header. Backend middleware validates match.
5. New middleware: `CsrfMiddleware` — skips GET/HEAD/OPTIONS, rejects
   mutations missing the header.

### Frontend changes

1. Remove `localStorage.setItem('access_token', ...)` from `src/lib/api.ts`.
2. API client sends `credentials: 'include'` on all fetch calls.
3. On login success, read `csrf_token` from non-httpOnly cookie and store in
   memory (not localStorage).
4. Attach `X-CSRF-Token: {value}` header on all mutating requests.
5. Add Next.js `middleware.ts` route guard: redirect to `/login` if no
   valid session (check `GET /v1/sessions/me`).

### Auth guard pattern

```typescript
// middleware.ts
export async function middleware(request: NextRequest) {
  const hasToken = request.cookies.has('access_token')
  if (!hasToken && !request.nextUrl.pathname.startsWith('/login')) {
    return NextResponse.redirect(new URL('/login', request.url))
  }
}
```

## Not in scope here

- OAuth2 social login flows (those use redirect-based auth, different cookie strategy)
- Mobile clients (cookies don't apply — they continue using bearer tokens)
