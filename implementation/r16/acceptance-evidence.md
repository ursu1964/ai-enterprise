# P26 — R16 acceptance evidence

- R document: `1/r16.txt`
- Exact clause verification: `implementation/r16/clause-verification.md`
- Evidence package: `implementation/r16`
- Product-platform scope: Knowledge Graph Specification.
- Related IR scope: `docs/ir/R16-IR-01-repository-integration-engine.md` is preserved as a separate Repository Integration Engine contract and does not replace product-platform R16.
- Focused verification command: `rtk bash -lc 'cd apps/api && .venv/bin/pytest -q tests/test_r16_knowledge_graph_runtime.py tests/test_traceability.py'`.
- Full verification command: `rtk make check`.
- Release verification command: `rtk make check-release`.
- Completion rule: every R16 Knowledge Graph clause maps to repository evidence and release gates pass with clean provenance.
- Operational boundary: high-scale external graph backends require real deployment/configuration/evidence; application readiness gates fail closed until those are supplied.
- Current package status: complete after verification.
