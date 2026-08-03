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
COPY tools/migration_verify.py /app/tools/migration_verify.py
COPY tools/backup_verify.py /app/tools/backup_verify.py
COPY tools/generate_server_secrets.py /app/tools/generate_server_secrets.py
COPY tools/sign_proxy_assertion.py /app/tools/sign_proxy_assertion.py
COPY tools/model_endpoint_verify.py /app/tools/model_endpoint_verify.py
COPY tools/deployment_blueprint.py /app/tools/deployment_blueprint.py
COPY tools/infrastructure_choices.py /app/tools/infrastructure_choices.py
COPY tools/dashboard_verify.py /app/tools/dashboard_verify.py
COPY apps/api/alembic.ini /app/apps/api/alembic.ini
COPY docker-compose.server.example.yml /app/docker-compose.server.example.yml
COPY docker-compose.observability.yml /app/docker-compose.observability.yml
COPY .env.server.example /app/.env.server.example
COPY docker/observability /app/docker/observability
COPY docker/reverse-proxy /app/docker/reverse-proxy
COPY deploy/systemd /app/deploy/systemd
COPY deploy/kubernetes /app/deploy/kubernetes
COPY templates/project-foundry /app/templates/project-foundry
COPY docs/enterprise/deployment-blueprint-module.md /app/docs/enterprise/deployment-blueprint-module.md
COPY docs/enterprise/real-world-infrastructure-decisions.template.json /app/docs/enterprise/real-world-infrastructure-decisions.template.json
COPY docs/enterprise/operator-startup-guide.md /app/docs/enterprise/operator-startup-guide.md
COPY docs/enterprise/project-execution-walkthrough.md /app/docs/enterprise/project-execution-walkthrough.md
COPY docs/enterprise/working-method.md /app/docs/enterprise/working-method.md
COPY docs/enterprise/real-world-infrastructure-choices.md /app/docs/enterprise/real-world-infrastructure-choices.md

ARG UV_SYNC_ARGS="--no-dev"
RUN uv sync --frozen ${UV_SYNC_ARGS}

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

RUN mkdir -p /app/artifacts /app/runtime-data \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "ai_enterprise.main:app", "--host", "0.0.0.0", "--port", "8000"]
