# P27 — R17 acceptance evidence

- R document: `1/r17.txt`
- Exact clause verification: `implementation/r17/clause-verification.md`
- Evidence package: `implementation/r17`
- Product-platform scope: Execution Planning Engine Specification.
- Related IR scope: `docs/ir/R17-IR-01-deployment-runtime-engine.md` is preserved as a separate Deployment and Runtime Engine contract and does not replace product-platform R17.
- Focused verification command: `rtk bash -lc 'cd apps/api && .venv/bin/pytest -q tests/test_r17_execution_planner_runtime.py tests/test_traceability.py'`.
- Full verification command: `rtk make check`.
- Release verification command: `rtk make check-release`.
- Completion rule: every R17 Execution Planning clause maps to repository evidence and release gates pass with clean provenance.
- Operational boundary: real distributed planner fleet deployment is runtime infrastructure, not a missing R17 planner implementation.
- Current package status: complete after verification.
