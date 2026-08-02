manifest ?= docs/enterprise/enterprise-manifest.example.json

.PHONY: build up down restart logs ps migrate migration enterprise-start test lint format typecheck check shell db-shell compose-check migration-check

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

compose-check:
	docker compose config --quiet

migration-check:
	cd apps/api && .venv/bin/alembic heads
	cd apps/api && .venv/bin/alembic upgrade head --sql >/dev/null

check: compose-check migration-check lint typecheck test

shell:
	docker compose run --rm api /bin/sh

db-shell:
	docker compose exec postgres sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'
