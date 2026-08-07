manifest ?= docs/enterprise/enterprise-manifest.example.json

.PHONY: build up down restart logs ps migrate migration enterprise-start laptop-worker-up laptop-compose-check local-executor-env local-executor-check local-executor-worker demo-preview demo-reset runtime-baseline test docker-test lint format typecheck tooling-invariants secret-scan semantic-platform-generate architecture-baseline-manifest roadmap-sequence-gate check check-fast check-ci check-release check-production-release shell db-shell compose-check docker-smoke dashboard-verify dashboard-browser-install dashboard-browser-verify migration-check migration-verify server-secrets model-verify server-readiness-template server-readiness infrastructure-choices-template infrastructure-choices-verify backup-verify deployment-blueprint production-evidence-init production-readiness-contracts production-evidence-status production-evidence-plan production-readiness observability-check observability-up observability-down engineering-static evolution-check federation-check intelligence-check etra-check engineering-full release-gate-evidence-fast release-gate-evidence-ci release-gate-evidence-release release-artifact release-artifact-verify release-evidence-bundle production-release-artifact production-release-artifact-verify production-release-evidence-bundle

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

laptop-worker-up:
	docker compose -f docker-compose.yml -f docker-compose.laptop.yml up -d --no-deps --force-recreate worker

laptop-compose-check:
	docker compose -f docker-compose.yml -f docker-compose.laptop.yml config --quiet

local-executor-env:
	python tools/configure_local_executor.py

local-executor-check:
	apps/api/.venv/bin/python tools/local_executor_worker.py --json

local-executor-worker:
	apps/api/.venv/bin/python tools/local_executor_worker.py --run

demo-preview:
	python tools/demo_lifecycle.py

demo-reset:
	python tools/demo_lifecycle.py --execute

runtime-baseline:
	python tools/runtime_baseline.py --output artifacts/runtime-baseline.json

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

tooling-invariants:
	cd apps/api && .venv/bin/ruff check --ignore E501 ../../tools
	python tools/check_tooling_invariants.py
	python -m compileall -q tools

secret-scan:
	python tools/secret_scan.py --all

semantic-platform-generate:
	PYTHONPATH=apps/api/src python tools/semantic_platform_generate.py --output-root generated/semantic-platform-0.4

architecture-baseline-manifest:
	python tools/architecture_baseline_manifest.py --output artifacts/architecture-baseline-manifest.json

roadmap-sequence-gate:
	python tools/roadmap_sequence_gate.py --output artifacts/roadmap-sequence-gate.json

compose-check:
	docker compose config --quiet

docker-smoke:
	docker compose up --build -d api worker
	python tools/docker_smoke.py --require-worker

dashboard-verify:
	python tools/dashboard_verify.py --base-url "$${DASHBOARD_BASE_URL:-http://127.0.0.1:8000}"

dashboard-browser-install:
	cd apps/api && .venv/bin/playwright install chromium

dashboard-browser-verify:
	apps/api/.venv/bin/python tools/dashboard_browser_verify.py --base-url "$${DASHBOARD_BASE_URL:-http://127.0.0.1:8000}"

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

production-evidence-init:
	python tools/production_evidence_init.py --output artifacts/production-evidence-init.json

production-readiness-contracts:
	python tools/production_readiness_contracts.py --output artifacts/production-readiness-contracts.json

production-evidence-status:
	python tools/production_evidence_status.py --output artifacts/production-evidence-status.json --markdown-output artifacts/production-evidence-status.md

production-evidence-plan:
	python tools/production_evidence_plan.py --output artifacts/production-evidence-plan.json

production-readiness:
	python tools/production_readiness.py --output artifacts/production-readiness.json

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
	python tools/release_artifact.py --evidence-file artifacts/gate-evidence.json --require-evidence-for compose-check,migration-check,lint,typecheck,test,secret-scan,docker-smoke,architecture-baseline-manifest,roadmap-sequence-gate,dashboard-verify,dashboard-browser-verify,engineering-static,evolution-check,federation-check,intelligence-check,engineering-full,etra-check --output artifacts/release-verification.json --markdown-output artifacts/release-verification.md

release-artifact-verify:
	python tools/release_artifact.py --verify-json artifacts/release-verification.json --verify-markdown artifacts/release-verification.md --verify-output artifacts/release-verification-check.json

release-evidence-bundle:
	python tools/release_evidence_bundle.py --output artifacts/release-evidence-bundle.json

production-release-artifact:
	python tools/release_artifact.py --production --evidence-file artifacts/gate-evidence.json --require-evidence-for compose-check,migration-check,lint,typecheck,test,secret-scan,docker-smoke,architecture-baseline-manifest,roadmap-sequence-gate,dashboard-verify,dashboard-browser-verify,engineering-static,evolution-check,federation-check,intelligence-check,engineering-full,etra-check --output artifacts/production-release-verification.json --markdown-output artifacts/production-release-verification.md

production-release-artifact-verify:
	python tools/release_artifact.py --verify-json artifacts/production-release-verification.json --verify-markdown artifacts/production-release-verification.md --verify-output artifacts/production-release-verification-check.json

production-release-evidence-bundle:
	python tools/release_evidence_bundle.py --production --output artifacts/production-release-evidence-bundle.json

release-gate-evidence-fast:
	python tools/release_gate_evidence.py --output artifacts/gate-evidence.json --profile fast

release-gate-evidence-ci:
	python tools/release_gate_evidence.py --output artifacts/gate-evidence.json --profile ci

release-gate-evidence-release:
	python tools/release_gate_evidence.py --output artifacts/gate-evidence.json --profile release

check-fast: tooling-invariants lint typecheck test

check-ci: roadmap-sequence-gate engineering-static evolution-check federation-check intelligence-check engineering-full etra-check

check-release: release-gate-evidence-release release-artifact release-artifact-verify release-evidence-bundle

check-production-release: production-evidence-plan production-readiness-contracts production-readiness production-evidence-status release-gate-evidence-release production-release-artifact production-release-artifact-verify production-release-evidence-bundle

check: compose-check migration-check lint typecheck test

shell:
	docker compose run --rm api /bin/sh

db-shell:
	docker compose exec postgres sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'
