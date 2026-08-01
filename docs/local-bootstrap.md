# Local activation

1. Copy `.env.example` to `.env` and adjust repository paths.
2. Apply migrations: `cd apps/api && .venv/bin/alembic upgrade head`.
3. Run `PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m ai_enterprise.bootstrap`.
4. Source `runtime-data/dev-secrets.env` into the API environment when testing trusted-proxy assertions.

The command is idempotent. It creates bounded runtime directories, a bare repository at
`runtime-data/remotes/ai-enterprise.git`, prints its `file://` URL, generates mode-0600 development
HMAC/signing secrets, and seeds a local region, Ollama provider/model, actor, and grants. Generated
state is ignored by Git. `NoCredentialsBroker` supports this explicitly unauthenticated local remote;
production remotes continue to require the restricted SSH broker.

Run the containerized variant with `docker compose --profile dev-bootstrap run --rm bootstrap` after
the database is healthy. Check `/ready` for the database and `/api/v1/providers/readiness` for seeded
provider governance records. Provider readiness proves configuration, not live model inference.
