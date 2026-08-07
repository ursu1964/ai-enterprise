# P25 — R15 acceptance evidence

- R document: `1/r15.txt`
- Exact clause verification: `implementation/r15/clause-verification.md`
- Evidence package: `implementation/r15`
- Product-platform scope: Manifest Compiler Specification.
- Related IR scope: `docs/ir/R15-IR-01-workflow-process-engine.md` is preserved as a separate Workflow and Process Engine contract and does not replace product-platform R15.
- Focused verification command: `rtk bash -lc 'cd apps/api && .venv/bin/pytest -q tests/test_r15_manifest_compiler_runtime.py tests/test_traceability.py'`.
- Full verification command: `rtk make check`.
- Release verification command: `rtk make check-release`.
- Completion rule: every R15 Manifest Compiler clause maps to repository evidence and release gates pass with clean provenance.
- Current package status: complete after verification.
