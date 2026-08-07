# P13 — R3 acceptance evidence

- R document: `1/r3.txt`
- Evidence package: `implementation/r03`
- Required verification command: `rtk make check-release`.
- Completion rule: all core requirement areas have repository evidence and release gates pass.
- Current package status: complete.
- Clause-level verification: `implementation/r03/clause-verification.md`.
- Focused verification command:
  `cd apps/api && .venv/bin/pytest -q tests/test_r3_foundation_specification.py tests/test_r3_foundation_api.py tests/test_project_formation.py tests/test_aeir_knowledge_storage.py tests/test_aeir_model.py tests/test_aepm_manifest.py tests/test_aepm_validation.py`
- Latest focused verification result: `56 passed`.
