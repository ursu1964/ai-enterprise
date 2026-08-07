# P31 — R21 acceptance evidence

- R document: `1/r21.txt`
- Evidence package: `implementation/r21`
- Required verification command: `rtk make check-release`.
- Completion rule: all core requirement areas have repository evidence and release gates pass.
- Clause verification: `implementation/r21/clause-verification.md`.
- Focused verification:
  `rtk bash -lc 'cd apps/api && .venv/bin/pytest -q tests/test_r21_execution_orchestrator_runtime.py tests/test_traceability.py'`.
- Full verification: `rtk make check`.
- Release verification: `rtk make check-release`.
- Current package status: complete.
