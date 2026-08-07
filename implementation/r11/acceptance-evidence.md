# P21 — R11 acceptance evidence

- R document: `1/r11.txt`
- Evidence package: `implementation/r11`
- Required verification command: `rtk make check-release`.
- Completion rule: all core requirement areas have repository evidence and release gates pass.
- Current package status: complete.
- Clause-level verification: `implementation/r11/clause-verification.md`.
- Focused verification command:
  `cd apps/api && .venv/bin/pytest -q tests/test_r11_uief_domain.py tests/test_r11_uief_persistence.py tests/test_r11_uief_runtime.py tests/test_bk_r11_evidence_audit_contracts.py tests/test_bk_r11_evidence_audit_persistence.py tests/test_bk_r11_evidence_audit_runtime.py tests/test_traceability.py`
- Latest focused verification result: `52 passed`.
