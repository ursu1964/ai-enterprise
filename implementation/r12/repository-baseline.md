# P22 — R12 repository baseline

- R document: `1/r12.txt`
- R title: R12 — AI-Enterprise Implementation & Bootstrap Specification
- Specification hash: `7f9c2cba072e2e731062b475edb5a1e46f4f188ee4d1cbfdb562ce99182368f1`
- Repository baseline: existing AI-Enterprise architecture.
- Source root: `apps/api/src`.
- Rule: do not create a second root-level application source tree.

## Evidence summary

| Requirement area | Status | Evidence |
|---|---|---|
| source_specification | implemented | `1/r12.txt` |
| domain_or_runtime | implemented | `apps/api/src/ai_enterprise/application/r12_bootstrap_runtime.py`<br>`apps/api/src/ai_enterprise/application/r13_repository_bootstrap_runtime.py` |
| api_contract | implemented | `apps/api/src/ai_enterprise/api/r12_bootstrap_schemas.py`<br>`apps/api/src/ai_enterprise/api/r13_repository_bootstrap_schemas.py` |
| api_route | implemented | `apps/api/src/ai_enterprise/api/routes/r12_bootstrap.py`<br>`apps/api/src/ai_enterprise/api/routes/r13_repository_bootstrap.py` |
| persistence_or_migration | verified_not_applicable | No separate repository artifact required; verified as not applicable. |
| schema_or_registry | implemented | `apps/api/src/ai_enterprise/api/r12_bootstrap_schemas.py`<br>`apps/api/src/ai_enterprise/api/r13_repository_bootstrap_schemas.py` |
| tests | implemented | `apps/api/tests/test_local_bootstrap.py`<br>`apps/api/tests/test_r12_bootstrap_runtime.py`<br>`apps/api/tests/test_r13_repository_bootstrap_runtime.py` |
| status_documentation | implemented | `docs/ir/R12-IR-01-policy-governance-engine.md`<br>`docs/local-bootstrap.md`<br>`docs/r13-repository-bootstrap-status.md`<br>`implementation/r12/acceptance-evidence.md`<br>`implementation/r12/api-changes/README.md`<br>`implementation/r12/completion-report.md`<br>`implementation/r12/gap-analysis.md`<br>`implementation/r12/implementation-plan.md`<br>`implementation/r12/migration-plan/README.md`<br>`implementation/r12/repository-baseline.md`<br>`implementation/r12/requirement-matrix.md`<br>`implementation/r12/schema-changes/README.md`<br>... 2 more |
