# 08_auth — User Guide

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/auth/setup-status` | Check if first-run setup is needed |
| POST | `/v1/auth/setup` | Create initial admin (only when zero users) |
| POST | `/v1/auth/register` | Register new user with email + password |
| POST | `/v1/auth/login` | Login with email + password |
| POST | `/v1/auth/refresh` | Rotate JWT tokens |
| POST | `/v1/auth/logout` | Revoke current session |
| GET | `/v1/auth/me` | Get current user from JWT |

## First-Run Setup

```bash
# Check if setup is needed
curl http://localhost:18000/v1/auth/setup-status
# → {"ok": true, "data": {"needs_setup": true, "user_count": 0}}

# Create admin
curl -X POST http://localhost:18000/v1/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "SecurePass123!", "display_name": "Admin"}'
```

## Login

```bash
curl -X POST http://localhost:18000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "SecurePass123!"}'
```

Response:
```json
{
  "ok": true,
  "data": {
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "bearer",
    "expires_in": 900
  }
}
```

## Authenticated Request

```bash
curl -H "Authorization: Bearer <access_token>" http://localhost:18000/v1/auth/me
```

## Frontend Pages

- `/setup` — First-run wizard (shield icon, name + email + password + confirm)
- `/login` — Sign in form (auto-redirects to /setup if no users)
