# syntax=docker/dockerfile:1
# =============================================================================
#  FreeShop API - multi-stage build, non-root runtime
# =============================================================================

# ---- Stage 1: build the virtualenv -----------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Build deps for argon2-cffi / Pillow wheels that lack a manylinux build.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libffi-dev \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app

RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip setuptools wheel \
 && /opt/venv/bin/pip install .

# ---- Stage 2: runtime ------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# sqlite3 CLI is needed by the backup profile ('sqlite3 .backup' is the only
# safe way to copy a live WAL database - see plan.md 12.3).
RUN apt-get update \
 && apt-get install -y --no-install-recommends sqlite3 curl \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser seeds ./seeds
COPY --chown=appuser:appuser alembic.ini docker-entrypoint.sh ./

RUN chmod +x docker-entrypoint.sh \
 && mkdir -p /app/data /app/static/uploads \
 && chown -R appuser:appuser /app/data /app/static

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/v1/healthz || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
