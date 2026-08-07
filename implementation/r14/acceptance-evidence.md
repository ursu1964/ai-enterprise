# P24 — R14 acceptance evidence

- R document: `1/r14.txt`
- Exact clause verification: `implementation/r14/clause-verification.md`
- Evidence package: `implementation/r14`
- Product-platform scope: Executable Manifest Schema.
- Related IR scope: `docs/ir/R14-IR-01-agent-framework.md` is preserved as a separate Agent Framework contract and does not replace product-platform R14.
- Focused verification command: `rtk bash -lc 'cd apps/api && .venv/bin/pytest -q tests/test_r14_manifest_schema_runtime.py tests/test_traceability.py'`.
- Full verification command: `rtk make check`.
- Release verification command: `rtk make check-release`.
- Completion rule: every R14 strict-canonical Manifest Schema clause maps to repository evidence and release gates pass with clean provenance.
- Accepted boundary: minimal intake remains deferred to a normalization layer and is explicitly rejected by the R14 strict-canonical validator.
- Current package status: complete after verification.
