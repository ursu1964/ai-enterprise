# P21 — R11 repository baseline

- R document: `1/r11.txt`
- R title: R11
- Specification hash: `5199114d845f689904c5d2bf9ba3f74dd62ff3044bcbc234a8ef97f973a27955`
- Repository baseline: existing AI-Enterprise architecture.
- Source root: `apps/api/src`.
- Rule: do not create a second root-level application source tree.

## Evidence summary

| Requirement area | Status | Evidence |
|---|---|---|
| source_specification | implemented | `1/r11.txt` |
| domain_or_runtime | implemented | `apps/api/src/ai_enterprise/application/bk_r11_evidence_audit_runtime.py`<br>`apps/api/src/ai_enterprise/application/bk_r11_persistence_service.py`<br>`apps/api/src/ai_enterprise/application/r11_uief_runtime.py`<br>`apps/api/src/ai_enterprise/domain/r11_uief.py` |
| api_contract | implemented | `apps/api/src/ai_enterprise/api/bk_r11_evidence_audit_schemas.py`<br>`apps/api/src/ai_enterprise/api/r11_uief_schemas.py` |
| api_route | implemented | `apps/api/src/ai_enterprise/api/routes/bk_r11_evidence_audit.py`<br>`apps/api/src/ai_enterprise/api/routes/r11_uief.py` |
| persistence_or_migration | implemented | `apps/api/src/ai_enterprise/infrastructure/bk_r11/__init__.py`<br>`apps/api/src/ai_enterprise/infrastructure/bk_r11/models.py`<br>`migrations/versions/a1d5e8f2b9c4_add_bk_r11_evidence_audit_records.py`<br>`migrations/versions/b2e6f9a3c8d1_add_bk_r11_archive_publication_records.py`<br>`migrations/versions/c4f7a9e2b6d1_add_r11_integration_records.py` |
| schema_or_registry | implemented | `apps/api/src/ai_enterprise/api/bk_r11_evidence_audit_schemas.py`<br>`apps/api/src/ai_enterprise/api/r11_uief_schemas.py`<br>`registry/evidence-audit/bk-r11-default.json` |
| tests | implemented | `apps/api/tests/test_bk_r11_evidence_audit_contracts.py`<br>`apps/api/tests/test_bk_r11_evidence_audit_persistence.py`<br>`apps/api/tests/test_bk_r11_evidence_audit_runtime.py`<br>`apps/api/tests/test_r11_uief_domain.py`<br>`apps/api/tests/test_r11_uief_persistence.py`<br>`apps/api/tests/test_r11_uief_runtime.py` |
| status_documentation | implemented | `docs/bk-r11-evidence-audit-engine-spec.md`<br>`implementation/r11/acceptance-evidence.md`<br>`implementation/r11/api-changes/README.md`<br>`implementation/r11/completion-report.md`<br>`implementation/r11/gap-analysis.md`<br>`implementation/r11/implementation-plan.md`<br>`implementation/r11/migration-plan/README.md`<br>`implementation/r11/repository-baseline.md`<br>`implementation/r11/requirement-matrix.md`<br>`implementation/r11/schema-changes/README.md`<br>`implementation/r11/security-review.md`<br>`implementation/r11/test-plan.md` |
