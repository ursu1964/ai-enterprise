# P23 — R13 acceptance evidence

- R document: `1/r13.txt`
- Exact clause verification: `implementation/r13/clause-verification.md`
- Evidence package: `implementation/r13`
- Product-platform scope: Repository Bootstrap Specification.
- Related IR scope: `docs/ir/R13-IR-01-ai-orchestration-engine.md` is preserved as a separate AI orchestration contract and does not replace product-platform R13.
- Focused verification command: `rtk bash -lc 'cd apps/api && .venv/bin/pytest -q tests/test_r13_repository_bootstrap_runtime.py tests/test_traceability.py'`.
- Full verification command: `rtk make check`.
- Release verification command: `rtk make check-release`.
- Completion rule: every R13 bootstrap clause maps to repository evidence and release gates pass with clean provenance.
- Current package status: complete after verification.
