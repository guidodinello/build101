# Stage 1 — builder: uv, compile bytecode, install locked deps then the app
FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170 AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.29@sha256:eb2843a1e56fd9e30c7276ce1a52cba86e64c7b385f5e3279a0e08e02dd058fc /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# app/ includes the prompt .md files read at runtime; migrations/ and alembic.ini
# are needed by the pre-deploy `alembic upgrade head`.
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY alembic.ini ./
RUN uv sync --frozen --no-dev


# Stage 2 — final: no uv, no build tools, just the venv and source
FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170 AS final

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home appuser
WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app /app
USER appuser

# One worker: jobs run in-process (ADR 0005). Railway injects $PORT; `exec` makes
# uvicorn PID 1 so it receives SIGTERM on redeploys. After it, requests get 10 s to
# finish, then the background work SHUTDOWN_TIMEOUT_S: together under Railway's
# RAILWAY_DEPLOYMENT_DRAINING_SECONDS (README.md § Deploys and work in flight).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --timeout-graceful-shutdown 10"]
