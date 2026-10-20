# Stage 1 — builder: uv, compile bytecode, install locked deps then the app
FROM python:3.13-slim@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /uvx /bin/

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
FROM python:3.13-slim@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f AS final

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home appuser
WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app /app
USER appuser

# One worker: jobs run in-process (ADR 0005). Railway injects $PORT; `exec` makes
# uvicorn PID 1 so it receives SIGTERM on redeploys.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
