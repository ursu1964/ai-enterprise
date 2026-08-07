# P16 — R6 acceptance evidence

- R document: `1/r6.txt`
- Evidence package: `implementation/r06`
- Required verification command: `rtk make check-release`.
- Completion rule: all core requirement areas have repository evidence and release gates pass.
- Current package status: complete.
- Clause-level verification: `implementation/r06/clause-verification.md`.
- Focused verification command:
  `cd apps/api && .venv/bin/pytest -q tests/test_r6_uagf_domain.py tests/test_r6_uagf_persistence.py tests/test_traceability.py`
- Latest focused verification result: `30 passed`.
