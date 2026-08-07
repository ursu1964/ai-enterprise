# P15 — R5 acceptance evidence

- R document: `1/r5.txt`
- Evidence package: `implementation/r05`
- Required verification command: `rtk make check-release`.
- Completion rule: all core requirement areas have repository evidence and release gates pass.
- Current package status: complete.
- Clause-level verification: `implementation/r05/clause-verification.md`.
- Focused verification command:
  `cd apps/api && .venv/bin/pytest -q tests/test_r5_umte_domain.py tests/test_r5_umte_persistence.py tests/test_traceability.py tests/test_r3_foundation_api.py`
- Latest focused verification result: `24 passed`.
