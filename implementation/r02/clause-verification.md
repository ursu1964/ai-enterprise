# P12 — R2 exact clause verification

Authoritative R source: `1/r2.txt`

This document records the recovered R2 contract against current repository
symbols. It exists to close the previous CODE-01 blocker without creating R23
or a parallel architecture.

| R2 clause | Status | Repository evidence |
|---|---|---|
| Freeze MVP success condition: one valid AEPM produces a validated canonical model, unresolved gaps, human corrections, and traceable artifacts. | implemented | `docs/ir/R02-IR-01-foundational-domain-manifest-concepts.md`; `apps/api/src/ai_enterprise/application/project_formation_service.py`; `apps/api/tests/test_project_formation.py`; `apps/api/tests/test_r2_specification_contracts.py` |
| Define AEPM v0.1 precisely with required/optional fields, types, identifiers, validation, versioning, extension policy, and examples. | implemented | `specifications/aepm/AEPM-0.1.schema.json`; `specifications/AEPM-0.1.schema.json`; `examples/sample-project/aepm-0.1.json`; `apps/api/src/ai_enterprise/domain/aepm.py`; `apps/api/tests/test_aepm_manifest.py` |
| Separate lifecycle status from truth status and approval status. | implemented | `apps/api/src/ai_enterprise/domain/aeir.py`; `specifications/aeir/AEIR-0.1.schema.json`; `specifications/aeir/RELATIONSHIP-0.1.schema.json`; `apps/api/tests/test_aeir_model.py`; `apps/api/tests/test_r2_specification_contracts.py` |
| Strengthen canonical object model with identity, type, source refs, evidence refs, relationship refs, confidence, version, actor/timestamp metadata, attributes, and metadata. | implemented | `apps/api/src/ai_enterprise/domain/aeir.py`; `specifications/aeir/AEIR-0.1.schema.json`; `apps/api/tests/test_aeir_model.py` |
| Define relationships as first-class records rather than redundant embedded objects. | implemented | `apps/api/src/ai_enterprise/domain/aeir.py`; `specifications/aeir/RELATIONSHIP-0.1.schema.json`; `apps/api/tests/test_r2_specification_contracts.py::test_relationship_schema_is_first_class_and_not_embedded_only` |
| Distinguish validation categories and findings with rule id, severity, category, blocking flag, object refs, and suggested action. | implemented | `apps/api/src/ai_enterprise/domain/aepm_validation.py`; `specifications/validation/VALIDATION-FINDING-0.1.schema.json`; `apps/api/tests/test_aepm_validation.py` |
| Define deterministic logic vs AI interpretation boundary. | implemented | `specifications/ai/DETERMINISTIC-AI-BOUNDARY-0.1.md`; `apps/api/src/ai_enterprise/domain/aepm_validation.py`; `apps/api/src/ai_enterprise/domain/aepm_interpretation.py`; `apps/api/tests/test_r2_specification_contracts.py::test_deterministic_ai_boundary_is_explicitly_specified` |
| Add provenance to every AI-created or AI-modified object. | implemented | `apps/api/src/ai_enterprise/domain/aeir.py`; `apps/api/src/ai_enterprise/domain/aepm_interpretation.py`; `specifications/ai/AI-OPERATION-0.1.schema.json`; `apps/api/tests/test_r2_specification_contracts.py::test_ai_operation_schema_requires_reviewable_hash_bound_provenance` |

## Focused verification

Command:

```bash
cd apps/api && .venv/bin/pytest -q \
  tests/test_r2_specification_contracts.py \
  tests/test_aeir_model.py \
  tests/test_aepm_manifest.py \
  tests/test_aepm_validation.py \
  tests/test_aepm_interpretation.py \
  tests/test_project_formation.py \
  tests/test_traceability.py
```

Result:

```text
61 passed
```

## Verdict

P12/R2 is implemented. No exact R2 clause remains blocked or missing in the
current repository baseline.
