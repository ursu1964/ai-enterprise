# P20 — R10 repository baseline

- R document: `1/r10.txt`
- R title: R10 — Universal Experience & Interaction Framework (UEIF)
- Specification hash: `aae36e317c0e33507d010fddf36489adc46f8bec76803fea31cb565facb5da6d`
- Repository baseline: existing AI-Enterprise architecture.
- Source root: `apps/api/src`.
- Rule: do not create a second root-level application source tree.

## Evidence summary

| Requirement area | Status | Evidence |
|---|---|---|
| source_specification | implemented | `1/r10.txt` |
| domain_or_runtime | implemented | `apps/api/src/ai_enterprise/application/bk_r10_persistence_service.py`<br>`apps/api/src/ai_enterprise/application/bk_r10_verification_runtime.py`<br>`apps/api/src/ai_enterprise/domain/r10_ueif.py` |
| api_contract | implemented | `apps/api/src/ai_enterprise/api/bk_r10_verification_schemas.py`<br>`apps/api/src/ai_enterprise/api/r10_ueif_schemas.py` |
| api_route | implemented | `apps/api/src/ai_enterprise/api/routes/bk_r10_verification.py`<br>`apps/api/src/ai_enterprise/api/routes/r10_ueif.py` |
| persistence_or_migration | implemented | `apps/api/src/ai_enterprise/infrastructure/bk_r10/__init__.py`<br>`apps/api/src/ai_enterprise/infrastructure/bk_r10/models.py`<br>`migrations/versions/b3e6f9a1c4d7_add_r10_experience_records.py`<br>`migrations/versions/f8a6c2d4e9b1_add_bk_r10_verification_records.py` |
| schema_or_registry | implemented | `apps/api/src/ai_enterprise/api/bk_r10_verification_schemas.py`<br>`apps/api/src/ai_enterprise/api/r10_ueif_schemas.py`<br>`registry/verification-backends/bk-r10-default.json`<br>`registry/verification-methods/bk-r10-default.json`<br>`registry/verification-policies/bk-r10-default.json` |
| tests | implemented | `apps/api/tests/test_bk_r10_verification_contracts.py`<br>`apps/api/tests/test_bk_r10_verification_persistence.py`<br>`apps/api/tests/test_bk_r10_verification_runtime.py`<br>`apps/api/tests/test_r10_ueif_domain.py`<br>`apps/api/tests/test_r10_ueif_persistence.py` |
| status_documentation | implemented | `docs/bk-r10-verification-validation-engine-status.md`<br>`docs/ir/R10-IR-01-verification-validation-engine.md`<br>`implementation/r10/acceptance-evidence.md`<br>`implementation/r10/api-changes/README.md`<br>`implementation/r10/completion-report.md`<br>`implementation/r10/gap-analysis.md`<br>`implementation/r10/implementation-plan.md`<br>`implementation/r10/migration-plan/README.md`<br>`implementation/r10/repository-baseline.md`<br>`implementation/r10/requirement-matrix.md`<br>`implementation/r10/schema-changes/README.md`<br>`implementation/r10/security-review.md`<br>... 1 more |
