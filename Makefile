manifest ?= docs/enterprise/enterprise-manifest.example.json

.PHONY: build up down restart logs ps migrate migration enterprise-start test lint format typecheck secret-scan check check-fast check-ci check-release shell db-shell compose-check migration-check engineering-static evolution-check federation-check intelligence-check etra-check engineering-full

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

migration-check:
	cd apps/api && .venv/bin/alembic heads
	cd apps/api && .venv/bin/alembic upgrade head --sql >/dev/null

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

check-fast: lint typecheck test

check-ci: engineering-static evolution-check federation-check intelligence-check engineering-full etra-check

check-release: compose-check migration-check secret-scan check-ci

check: compose-check migration-check lint typecheck test

shell:
	docker compose run --rm api /bin/sh

db-shell:
	docker compose exec postgres sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'
