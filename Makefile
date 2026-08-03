manifest ?= docs/enterprise/enterprise-manifest.example.json

.PHONY: build up down restart logs ps migrate migration enterprise-start test docker-test lint format typecheck secret-scan check check-fast check-ci check-release shell db-shell compose-check docker-smoke migration-check migration-verify server-secrets model-verify server-readiness-template server-readiness infrastructure-choices-template infrastructure-choices-verify backup-verify deployment-blueprint observability-check observability-up observability-down engineering-static evolution-check federation-check intelligence-check etra-check engineering-full release-gate-evidence-fast release-gate-evidence-ci release-artifact

build:
	docker compose build

up:
	docker compose up --build -d

down:
	docker compose down

restart: down up

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

migrate:
	docker compose run --rm migrate alembic -c apps/api/alembic.ini upgrade head

migration:
	docker compose run --rm migrate alembic -c apps/api/alembic.ini revision --autogenerate -m "$(name)"

enterprise-start:
	python scripts/enterprise_autostart.py --manifest "$(manifest)"

test:
	cd apps/api && .venv/bin/pytest -q

docker-test:
	docker compose -f docker-compose.yml -f docker-compose.test.yml --profile test run --rm api-test

lint:
	cd apps/api && .venv/bin/ruff check src tests ../../migrations

format:
	cd apps/api && .venv/bin/ruff format src tests ../../migrations

typecheck:
	cd apps/api && .venv/bin/mypy src

secret-scan:
	python tools/secret_scan.py --all

compose-check:
	docker compose config --quiet

docker-smoke:
	docker compose up --build -d api worker
	python tools/docker_smoke.py --require-worker

migration-check:
	cd apps/api && .venv/bin/alembic heads
	cd apps/api && .venv/bin/alembic upgrade head --sql >/dev/null
	python tools/migration_verify.py --json

migration-verify:
	python tools/migration_verify.py --json

server-secrets:
	python tools/generate_server_secrets.py --output .env.server.generated

model-verify:
	python tools/model_endpoint_verify.py --base-url "$${OLLAMA_BASE_URL}" --model "$${OLLAMA_MODEL}" --json

server-readiness-template:
	python tools/migration_verify.py --server-readiness --env-file .env.server.example --allow-placeholders --json

server-readiness:
	python tools/migration_verify.py --server-readiness --env-file .env.server --json

infrastructure-choices-template:
	python tools/infrastructure_choices.py --choices docs/enterprise/real-world-infrastructure-decisions.template.json --allow-placeholders --json

infrastructure-choices-verify:
	python tools/infrastructure_choices.py --choices docs/enterprise/real-world-infrastructure-decisions.json --json

backup-verify:
	python tools/backup_verify.py --json

deployment-blueprint:
	python tools/deployment_blueprint.py --json

observability-check:
	docker compose -f docker-compose.yml -f docker-compose.observability.yml config --quiet

observability-up:
	docker compose -f docker-compose.yml -f docker-compose.observability.yml up -d prometheus grafana

observability-down:
	docker compose -f docker-compose.yml -f docker-compose.observability.yml stop prometheus grafana

engineering-static:
	python tools/engineering_verify.py --static --json

evolution-check:
	python tools/evolution_verify.py --json

federation-check:
	python tools/federation_verify.py --json

intelligence-check:
	python tools/intelligence_verify.py --json

etra-check:
	python tools/etra_conformance.py --root . --json

engineering-full:
	python tools/engineering_verify.py --full --json

release-artifact:
	python tools/release_artifact.py --evidence-file artifacts/gate-evidence.json --require-evidence-for lint,typecheck,test,docker-smoke,engineering-static,evolution-check,federation-check,intelligence-check,engineering-full,etra-check --output artifacts/release-verification.json

release-gate-evidence-fast:
	python tools/release_gate_evidence.py --output artifacts/gate-evidence.json --gate-command 'lint=cd apps/api && .venv/bin/ruff check src tests ../../migrations' --gate-command 'typecheck=cd apps/api && .venv/bin/mypy src' --gate-command 'test=cd apps/api && .venv/bin/pytest -q'

release-gate-evidence-ci:
	python tools/release_gate_evidence.py --output artifacts/gate-evidence.json --gate-command 'lint=cd apps/api && .venv/bin/ruff check src tests ../../migrations' --gate-command 'typecheck=cd apps/api && .venv/bin/mypy src' --gate-command 'test=cd apps/api && .venv/bin/pytest -q' --gate-command 'docker-smoke=python tools/docker_smoke.py --require-worker' --gate-command 'engineering-static=python tools/engineering_verify.py --static --json' --gate-command 'evolution-check=python tools/evolution_verify.py --json' --gate-command 'federation-check=python tools/federation_verify.py --json' --gate-command 'intelligence-check=python tools/intelligence_verify.py --json' --gate-command 'engineering-full=python tools/engineering_verify.py --full --json' --gate-command 'etra-check=python tools/etra_conformance.py --root . --json'

check-fast: lint typecheck test

check-ci: engineering-static evolution-check federation-check intelligence-check engineering-full etra-check

check-release: compose-check migration-check check-fast secret-scan docker-smoke check-ci release-gate-evidence-ci release-artifact

check: compose-check migration-check lint typecheck test

shell:
	docker compose run --rm api /bin/sh

db-shell:
	docker compose exec postgres sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'
