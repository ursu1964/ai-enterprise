# P22 — R12 acceptance evidence

- R document: `1/r12.txt`
- Evidence package: `implementation/r12`
- Required verification command: `rtk make check-release`.
- Completion rule: all core requirement areas have repository evidence and release gates pass.
- Current package status: complete.
- Clause-level verification: `implementation/r12/clause-verification.md`.
- Focused verification command:
  `cd apps/api && .venv/bin/pytest -q tests/test_local_bootstrap.py tests/test_r12_bootstrap_runtime.py tests/test_r13_repository_bootstrap_runtime.py tests/test_traceability.py`
- Latest focused verification result: `57 passed`.
