#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root/apps/api"

.venv/bin/ruff check src/ai_enterprise/application/architecture_operations \
  tests/test_architecture_operations.py tests/test_architecture_m4_acceptance.py
.venv/bin/mypy src/ai_enterprise/application/architecture_operations
.venv/bin/pytest -q tests/test_architecture_operations.py tests/test_architecture_m4_acceptance.py \
  tests/test_trusted_architecture_execution.py
