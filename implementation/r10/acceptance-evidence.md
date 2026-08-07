# P20 — R10 acceptance evidence

- R document: `1/r10.txt`
- Evidence package: `implementation/r10`
- Required verification command: `rtk make check-release`.
- Completion rule: all core requirement areas have repository evidence and release gates pass.
- Current package status: complete.
- Clause-level verification: `implementation/r10/clause-verification.md`.
- Focused verification command:
  `cd apps/api && .venv/bin/pytest -q tests/test_r10_ueif_domain.py tests/test_r10_ueif_persistence.py tests/test_bk_r10_verification_contracts.py tests/test_bk_r10_verification_persistence.py tests/test_bk_r10_verification_runtime.py tests/test_traceability.py`
- Latest focused verification result: `45 passed`.
