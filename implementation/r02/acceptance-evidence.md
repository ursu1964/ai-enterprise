# P12 — R2 acceptance evidence

- R document: `1/r2.txt`
- Evidence package: `implementation/r02`
- Required verification command: `rtk make check-release`.
- Completion rule: all core requirement areas have repository evidence and release gates pass.
- Current package status: complete.
- Clause-level verification: `implementation/r02/clause-verification.md`.
- Focused verification command:
  `cd apps/api && .venv/bin/pytest -q tests/test_r2_specification_contracts.py tests/test_aeir_model.py tests/test_aepm_manifest.py tests/test_aepm_validation.py tests/test_aepm_interpretation.py tests/test_project_formation.py tests/test_traceability.py`
- Latest focused verification result: `61 passed`.
