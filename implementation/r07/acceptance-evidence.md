# P17 — R7 acceptance evidence

- R document: `1/r7.txt`
- Evidence package: `implementation/r07`
- Required verification command: `rtk make check-release`.
- Completion rule: all core requirement areas have repository evidence and release gates pass.
- Current package status: complete.
- Clause-level verification: `implementation/r07/clause-verification.md`.
- Focused verification command:
  `cd apps/api && .venv/bin/pytest -q tests/test_r7_uerm_domain.py tests/test_r7_uerm_persistence.py tests/test_traceability.py`
- Latest focused verification result: `21 passed`.
