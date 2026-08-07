# P28 — R18 acceptance evidence

- R document: `1/r18.txt`
- Exact clause verification: `implementation/r18/clause-verification.md`
- Evidence package: `implementation/r18`
- Product-platform scope: Generator Orchestration Framework.
- Related IR scope: `docs/ir/R18-IR-01-observability-telemetry-engine.md` is preserved as a separate Observability and Telemetry Engine contract and does not replace product-platform R18.
- Focused verification command: `rtk bash -lc 'cd apps/api && .venv/bin/pytest -q tests/test_r18_generator_orchestration_runtime.py tests/test_r18_live_provider_smoke.py tests/test_traceability.py'`.
- Full verification command: `rtk make check`.
- Release verification command: `rtk make check-release`.
- Completion rule: every R18 Generator Orchestration clause maps to repository evidence and release gates pass with clean provenance.
- Operational boundary: real live provider execution requires explicit credentials/configuration and is fail-closed by default.
- Current package status: complete after verification.
