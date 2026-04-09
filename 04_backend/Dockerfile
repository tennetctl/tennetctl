# syntax=docker/dockerfile:1.7
# tennetctl backend — Python 3.13 + FastAPI on uv
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# uv: fast, reproducible Python package manager
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

# Create non-root runtime user up-front so file ownership can be set
# during the COPY layers (avoids a post-install chown that bloats the image).
RUN groupadd --system --gid 10001 app \
    && useradd  --system --uid 10001 --gid 10001 --home /app --shell /sbin/nologin app

WORKDIR /app

# Install dependencies first for layer caching. We do not install the
# project itself with uv (the source dirs use numeric prefixes that are
# not legal Python package names — uvicorn loads them via --app-dir).
COPY --chown=app:app 04_backend/pyproject.toml 04_backend/README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv && \
    uv pip install \
        "fastapi>=0.115.0" \
        "uvicorn[standard]>=0.32.0" \
        "asyncpg>=0.30.0" \
        "pydantic>=2.9.0" \
        "pydantic-settings>=2.6.0" \
        "argon2-cffi>=23.1.0" \
        "redis>=5.2.0" \
        "cryptography>=43.0.0" \
    && chown -R app:app /app/.venv

# Copy source as the runtime user (read-only at runtime via compose).
COPY --chown=app:app 04_backend/01_core ./01_core
COPY --chown=app:app 04_backend/02_features ./02_features
# Copy scripts module needed by app imports (e.g. scripts.00_core._id)
COPY --chown=app:app scripts ./scripts

# Create the 04_backend namespace package directory structure so that
# importlib.import_module("04_backend.01_core.config") resolves correctly.
# The app code uses the full path prefix for local dev; in Docker we bridge
# the gap via symlinks.  /app is added to sys.path by the .pth file.
RUN mkdir -p /app/04_backend && \
    ln -s /app/01_core /app/04_backend/01_core && \
    ln -s /app/02_features /app/04_backend/02_features && \
    echo /app > /app/.venv/lib/python3.13/site-packages/tennetctl_app.pth

ENV PATH="/app/.venv/bin:$PATH"

USER app:app

EXPOSE 8000

# 01_core/ is on sys.path via --app-dir; modules import each other as
# top-level (no relative imports, no parent package).
CMD ["uvicorn", "app:app", "--app-dir", "01_core", "--host", "0.0.0.0", "--port", "8000"]
