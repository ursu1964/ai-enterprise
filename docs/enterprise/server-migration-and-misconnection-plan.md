# AI Enterprise Server Migration And Misconnection Plan

## Current Verified State

AI Enterprise is healthy on the laptop: the API readiness check passes, the database is reachable, the worker services are running, `/dashboard` is available, `/dashboard/graphify` serves the code graph, and `/api/v1/query/dashboard-manager` returns the live factory read model.

The current dashboard state still reports attention required because the database contains unresolved failed or dead-letter work. That signal is valid operating evidence, not a visual defect.

## Problems Solved In This Pass

The dashboard read-model contract now supports both `/api/v1/query/dashboard-manager` and `/api/v1/query/dashboard-read-model`. This removes endpoint-name drift for dashboards, scripts, and documentation that still use the older route name.

The local development dashboard actor now has enough authority to read the manager model and manage operator jobs. Production and staging still require trusted proxy authentication and durable authority grants.

The stale dead-letter job records from the mock factory demo were reviewed and acknowledged through the operator API. The runtime snapshot directory is writable now, the affected workflows are already in execution state, and the dashboard operating picture now reports active work with zero current problem tasks.

A server deployment profile was added as `docker-compose.server.example.yml`, with `.env.server.example` documenting the required production variables. The active laptop compose file remains unchanged so the current local factory keeps working.

The migration verifier now has a server-readiness mode. Use `make server-readiness-template` to validate the checked-in server template, then create `.env.server` and run `make server-readiness` before moving from laptop to server.

The dashboard now includes a Server Readiness panel under Metrics. It explains storage, trusted proxy, model service, graph, and deployment-template readiness in operator language.

A containerized test path now exists. The production API image still installs runtime dependencies only, while `docker-compose.test.yml` builds the same Dockerfile with development dependencies and runs `pytest -q` through `make docker-test`.

The later server phases now have first implementation artifacts:

- Reverse proxy and TLS template: `docker/reverse-proxy/nginx.conf.example`.
- Backup readiness verifier: `tools/backup_verify.py` and `make backup-verify`.
- Server secret generator: `tools/generate_server_secrets.py` and `make server-secrets`.
- Trusted proxy signature test helper: `tools/sign_proxy_assertion.py`.
- Production model endpoint verifier: `tools/model_endpoint_verify.py` and `make model-verify`.
- Scheduled backup templates: `deploy/systemd/ai-enterprise-backup.service` and `deploy/systemd/ai-enterprise-backup.timer`.
- Managed infrastructure hooks: `MANAGED_POSTGRES_URL` and `OBJECT_STORAGE_*` variables in `.env.server.example`.
- Multi-server rollout templates: `deploy/kubernetes/api-deployment.yaml` and `deploy/kubernetes/worker-deployment.yaml`.
- GitHub integration hooks: `LOCAL_GIT_REMOTE_URL`, `GITHUB_INTEGRATION_MODE`, `GITHUB_APP_ID`, `GITHUB_APP_INSTALLATION_ID`, `GITHUB_PRIVATE_KEY_PATH`, and `GITHUB_TOKEN_FILE`.
- Production alert rules: `docker/observability/alert_rules.yml`.
- Reusable deployment blueprint module: `tools/deployment_blueprint.py`, `make deployment-blueprint`, and `/dashboard/deployment-blueprint`.
- Real infrastructure decision gate: `tools/infrastructure_choices.py`, `docs/enterprise/real-world-infrastructure-decisions.template.json`, `make infrastructure-choices-verify`, and `/dashboard/infrastructure-choices`.
- Prometheus and Grafana stack: `docker-compose.observability.yml`, `docker/observability/prometheus.yml`, and the Grafana overview dashboard.
- Observability commands: `make observability-check`, `make observability-up`, and `make observability-down`.

## Remaining Server Risks

The local compose file is intentionally laptop-only. It uses local bind addresses, development database credentials, `/home/user/projects`, and `host.docker.internal` for the model service.

The server profile must be used with real secrets, durable server paths, reverse proxy authentication, TLS, backups, and monitored model service health before exposing the dashboard to users.

## Server Migration Path

Phase 1: local stabilization. Resolve or acknowledge problem jobs, verify dashboard read-model freshness, and confirm workers are online. This phase is now complete for the current laptop state: unresolved problem jobs are zero and telemetry is nominal.

Phase 2: single-server deployment. Create `/srv/ai-enterprise/workspaces`, `/srv/ai-enterprise/artifacts`, and `/srv/ai-enterprise/runtime-data`; copy `.env.server.example` to `.env.server`; replace every secret; then run the server compose profile behind a reverse proxy.

Verification commands for this phase:

```bash
make server-readiness-template
make server-secrets
cp .env.server.generated .env.server
# edit .env.server and replace provider URLs, database host, model endpoint, domain, and storage choices
make server-readiness
docker compose --env-file .env.server -f docker-compose.server.example.yml config --quiet
```

Phase 3: production hardening. Add HTTPS, trusted proxy HMAC signing, database backups, Prometheus scraping, Grafana dashboards, log retention, and model-service alerts.

Initial hardening artifacts are now present. Before production exposure, adapt `docker/reverse-proxy/nginx.conf.example` to the real domain and identity service, generate real HMAC signatures for `X-Proxy-Signature`, verify the production model endpoint, run `make backup-verify`, install the backup timer, and run `make observability-check`.

Trusted proxy signature test:

```bash
python tools/sign_proxy_assertion.py \
  --secret "$TRUSTED_PROXY_HMAC_SECRET" \
  --actor-id platform-admin \
  --actor-type human \
  --actor-role platform-admin \
  --json
```

Production model endpoint test:

```bash
OLLAMA_BASE_URL=http://model-service:11434 OLLAMA_MODEL=llama3.1:8b make model-verify
```

Scheduled backup installation, after copying the repository to `/srv/ai-enterprise/app`:

```bash
sudo cp deploy/systemd/ai-enterprise-backup.service /etc/systemd/system/
sudo cp deploy/systemd/ai-enterprise-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ai-enterprise-backup.timer
systemctl list-timers ai-enterprise-backup.timer
```

Local observability startup:

```bash
make observability-check
make observability-up
```

Prometheus will be available on `http://localhost:9090`. Grafana will be available on `http://localhost:3000` and is provisioned with the AI Enterprise overview dashboard.

Phase 4: scalable factory. Move Postgres to managed or dedicated infrastructure, artifacts to object storage, workers to separate nodes or Kubernetes jobs, and project execution into isolated workspaces.

This phase still requires infrastructure decisions, but the codebase now has a concrete starting point. Use `deploy/kubernetes/namespace.yaml`, `deploy/kubernetes/api-deployment.yaml`, `deploy/kubernetes/worker-deployment.yaml`, and `deploy/kubernetes/service.yaml` after replacing the image registry, Kubernetes secret, ingress/TLS configuration, storage class, model endpoint, and managed database connection.

Blueprint verification:

```bash
make deployment-blueprint
curl -fsS http://localhost:8000/dashboard/deployment-blueprint
```

The blueprint is the reusable installation memory for future enterprise deployments. It explains each migration phase, the gate that must pass, the proof command or artifact, and the next operator action.

Real infrastructure choice verification:

```bash
make infrastructure-choices-template
cp docs/enterprise/real-world-infrastructure-decisions.template.json docs/enterprise/real-world-infrastructure-decisions.json
# replace every placeholder with real provider values
make infrastructure-choices-verify
curl -fsS http://localhost:8000/dashboard/infrastructure-choices
```

This gate solves the ambiguity around domain, TLS, identity, model endpoint, GitHub access, database, object storage, Kubernetes, backup restore drills, and alert routing. The application cannot choose those values for the operator, but it now requires them to be recorded and verified before production.

## Innovation Direction

The Server Readiness dashboard now includes storage, auth, model service, graph, deployment templates, migration gate, GitHub hooks, Prometheus/Grafana state, alert rules, backup schedule templates, Kubernetes rollout templates, deployment blueprint proof, and the real infrastructure choices gate.

The migration verifier command now fails clearly when server secrets, storage roots, trusted proxy settings, model endpoint, server compose assumptions, GitHub hooks, observability alerts, Kubernetes templates, or deployment blueprint artifacts are missing.

Backup verification has local root checks, Postgres schema dump verification, and a systemd schedule template. The remaining operator step is to run recurring backups on the real server and perform restore drills against a separate database before production data is trusted.
