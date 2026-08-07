# P19 — R9 acceptance evidence

- R document: `1/r9.txt`
- Evidence package: `implementation/r09`
- Required verification command: `rtk make check-release`.
- Completion rule: all core requirement areas have repository evidence and release gates pass.
- Current package status: complete.
- Clause-level verification: `implementation/r09/clause-verification.md`.
- Focused verification command:
  `cd apps/api && .venv/bin/pytest -q tests/test_r9_uak_domain.py tests/test_r9_uak_persistence.py tests/test_r9_uak_runtime.py tests/test_traceability.py`
- Latest focused verification result: `28 passed`.
