# P14 — R4 acceptance evidence

- R document: `1/r4.txt`
- Evidence package: `implementation/r04`
- Required verification command: `rtk make check-release`.
- Completion rule: all core requirement areas have repository evidence and release gates pass.
- Current package status: complete.
- Clause-level verification: `implementation/r04/clause-verification.md`.
- Focused verification command:
  `cd apps/api && .venv/bin/pytest -q tests/test_r4_interpretation_domain.py tests/test_r4_provider_retry_security.py tests/test_r4_interpretation_api.py tests/test_r4_interpretation_persistence.py tests/test_r4_evaluation_runner.py tests/test_aepm_interpretation.py`
- Latest focused verification result: `31 passed`.
