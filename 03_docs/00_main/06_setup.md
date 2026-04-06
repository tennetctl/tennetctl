# Local Development Setup

Get tennetctl running locally in under 10 minutes.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Docker + Docker Compose | 24+ | https://docs.docker.com/get-docker/ |
| Python | 3.12+ | https://www.python.org/downloads/ |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | 20+ | https://nodejs.org/ |
| Git | any | pre-installed on most systems |

---

## Step 1: Clone the repository

```bash
git clone https://github.com/tennetctl/tennetctl.git
cd tennetctl/tennetctl
```

---

## Step 2: Start infrastructure

```bash
docker compose up -d postgres nats
```

This starts:
- **Postgres 16** on port `5432`
- **NATS 2.10 with JetStream** on port `4222`

Wait a few seconds for Postgres to be ready, then verify:

```bash
docker compose ps
# Both services should show "running"
```

---

## Step 3: Set up the backend

```bash
cd backend

# Install dependencies with uv
uv sync

# Copy environment file
cp .env.example .env
# Edit .env — the defaults work for local dev, no changes required

# Run database migrations
uv run python -m scripts.migrate up

# Start the API server
uv run uvicorn main:app --reload --port 51734
```

The API is now running at `http://localhost:51734`.

Verify: `curl http://localhost:51734/health` should return `{"status": "ok"}`.

---

## Step 4: Set up the frontend

```bash
cd frontend

# Install dependencies
npm install

# Copy environment file
cp .env.local.example .env.local
# Defaults work for local dev

# Start the Next.js dev server
npm run dev
```

The frontend is now running at `http://localhost:51735`.

---

## Step 5: Verify the setup

Open `http://localhost:51735` in your browser. You should see the tennetctl login page.

Default platform admin credentials (local dev only):
```
email:    admin@tennetctl.local
password: admin123
```

Change these immediately if you are running this anywhere other than `localhost`.

---

## Running with Docker Compose (full stack)

To run everything in Docker (closer to production):

```bash
docker compose up
```

This builds and starts all services: postgres, nats, api, frontend.

The API will be at `http://localhost:51734` and the frontend at `http://localhost:51735`.

---

## Environment Variables

The backend reads configuration from environment variables. All variables have safe defaults for local development. In production, set them explicitly.

### Required in production

| Variable | Description |
|----------|-------------|
| `APP_DATABASE_URL` | Postgres connection string |
| `NATS_URL` | NATS server URL |
| `JWT_PRIVATE_KEY_PEM` | RS256 private key for signing JWTs |
| `JWT_ISSUER` | OIDC issuer URL (e.g. `https://auth.yourdomain.com`) |
| `VAULT_MASTER_KEY` | 32-byte hex key for secret encryption |
| `ENCRYPTION_KEY` | Fernet key for token encryption |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `ACCESS_TOKEN_TTL_SECONDS` | `900` | Access token lifetime (15 min) |
| `REFRESH_TOKEN_TTL_DAYS` | `30` | Refresh token lifetime |
| `RATE_LIMIT_ENABLED` | `true` | Enable API rate limiting |
| `LOG_LEVEL` | `INFO` | Logging level |
| `CORS_ORIGINS` | `*` | Allowed CORS origins (restrict in production) |
| `CLICKHOUSE_URL` | `""` | ClickHouse connection (empty = disabled) |

Generate keys for production:

```bash
# JWT RS256 key pair
openssl genrsa -out jwt_private.pem 2048
openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem

# Vault master key
openssl rand -hex 32

# Fernet encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Running Tests

```bash
cd backend

# Run all tests
uv run pytest

# Run tests for a specific module
uv run pytest tests/02_iam/

# Run with coverage
uv run pytest --cov=. --cov-report=term-missing

# Run a specific test file
uv run pytest tests/02_iam/test_auth_login.py -v
```

Tests run against a real Postgres database. The test suite creates a separate `tennetctl_test` database and runs migrations before each test session. Tests are isolated via database transactions that are rolled back after each test.

There are no mocked database queries in the test suite.

---

## Database Migrations

```bash
cd backend

# Apply all pending migrations
uv run python -m scripts.migrate up

# Roll back the last migration
uv run python -m scripts.migrate down

# Show migration status
uv run python -m scripts.migrate status

# Create a new migration file
uv run python -m scripts.migrate new "description_of_change"
```

Migration files live in `01_sql_migrations/`. See `07_adding_a_feature.md` for the convention.

---

## Useful Commands

```bash
# Reset the database (drops and recreates tennetctl database)
docker compose exec postgres psql -U tennetctl -c "DROP DATABASE tennetctl; CREATE DATABASE tennetctl;"
uv run python -m scripts.migrate up

# Connect to Postgres directly
docker compose exec postgres psql -U tennetctl -d tennetctl

# Tail API logs
docker compose logs -f api

# Check NATS JetStream status
docker compose exec nats nats stream ls
```

---

## IDE Setup

### VS Code

Install the recommended extensions (`.vscode/extensions.json`):
- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- ESLint
- Prettier
- Tailwind CSS IntelliSense

### Cursor / Claude Code

The project includes a `CLAUDE.md` at the root of `tennetctl/` with conventions and workflows. Claude Code reads this automatically.

---

## Troubleshooting

**Postgres connection refused**
```bash
docker compose ps postgres
# If not running:
docker compose up -d postgres
```

**Migration fails with "relation already exists"**
```bash
# Check migration status
uv run python -m scripts.migrate status
# If migrations are out of sync, reset dev database (destroys data)
docker compose exec postgres psql -U tennetctl -c "DROP DATABASE tennetctl; CREATE DATABASE tennetctl;"
uv run python -m scripts.migrate up
```

**Frontend can't reach API**
Check `.env.local` — `NEXT_PUBLIC_API_URL` should be `http://localhost:51734`.

**NATS connection refused**
```bash
docker compose up -d nats
# Verify JetStream is enabled
docker compose exec nats nats account info
```
