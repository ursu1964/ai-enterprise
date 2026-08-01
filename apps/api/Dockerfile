FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --gid 10001 appgroup \
    && useradd --uid 10001 --gid appgroup --create-home --shell /usr/sbin/nologin appuser

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY apps/api/pyproject.toml /app/pyproject.toml
COPY apps/api/uv.lock /app/uv.lock
COPY apps/api/src /app/src
COPY migrations /app/migrations
COPY apps/api/alembic.ini /app/alembic.ini

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

RUN mkdir -p /app/artifacts /app/runtime-data \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "ai_enterprise.main:app", "--host", "0.0.0.0", "--port", "8000"]
