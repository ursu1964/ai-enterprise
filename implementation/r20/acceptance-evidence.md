# P30 — R20 acceptance evidence

- R document: `1/r20.txt`
- Evidence package: `implementation/r20`
- Required verification command: `rtk make check-release`.
- Completion rule: all core requirement areas have repository evidence and release gates pass.
- Clause verification: `implementation/r20/clause-verification.md`.
- Focused verification:
  `rtk bash -lc 'cd apps/api && .venv/bin/pytest -q tests/test_r20_runtime_kernel_runtime.py tests/test_traceability.py'`.
- Full verification: `rtk make check`.
- Release verification: `rtk make check-release`.
- Current package status: complete.
