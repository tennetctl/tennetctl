# 04_backend

tennetctl FastAPI backend service. Python 3.13.

Layout per `.claude/rules/common/architecture.md`:

```text
04_backend/
├── 01_core/          # config, db pool, errors, response envelope, middleware
└── 02_features/      # one dir per feature (vault, iam, audit, ...)
    └── {feature}/
        └── {sub_feature}/
            ├── schemas.py     # Pydantic v2
            ├── repository.py  # asyncpg raw SQL
            ├── service.py     # business logic
            └── routes.py      # FastAPI APIRouter
```

## Run locally (without Docker)

```bash
cd 04_backend
uv sync
DATABASE_URL=postgresql://tennetctl_write:tennetctl_write_dev@localhost:55432/tennetctl \
  uv run uvicorn 01_core.app:app --reload
```

## Run via docker compose

```bash
docker compose up backend
# → http://localhost:8000/healthz
```
