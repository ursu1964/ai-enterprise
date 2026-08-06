# R04-IR-01 — AI-Enterprise Controlled AI Participation Specification

Document ID: R04-IR-01  
Version: 1.0.0  
Status: IMPLEMENTATION READY  
Classification: Constitutional Platform Module  
Implementation Target: P14 reconciliation  
Primary Dependencies: R2–R3

## Purpose

R04-IR-01 defines how AI participates in manifest interpretation, extraction,
candidate creation, evidence recording, and canonical promotion.

The module keeps AI output non-authoritative until validated and promoted by
governed application logic.

This IR specification does not replace `1/r4.txt`; it records the implemented
R4 controlled-AI boundary.

## Constitutional requirements

- AI interpretation output is stored as candidate evidence, not canonical truth.
- Candidate objects and candidate relationships retain prompt, source, model,
  and extraction provenance.
- Promotion to canonical records is explicit, audited, and policy controlled.
- AI failures, uncertainty, contradictions, and missing evidence remain visible.
- Secrets and sensitive source material are redacted before unsafe exposure.
- Mock and live provider paths use the same validation boundary.

## Canonical domain model

The module owns these contracts:

- `AIOperation`
- `AIInterpretation`
- `AIProvenance`
- `CandidateObject`
- `CandidateRelationship`
- `ProbableContradiction`
- `ExtractionEvidence`
- `CanonicalPromotionRequest`
- `CanonicalPromotionResult`

## Commands

Required commands include:

- `CreateAIOperation`
- `RecordAIInterpretation`
- `RecordCandidateObject`
- `RecordCandidateRelationship`
- `DetectProbableContradiction`
- `ValidateCandidateEvidence`
- `PromoteCandidateToCanonical`
- `RejectCandidate`

Every mutating command includes actor or agent identity, provider reference,
organization, project, source references, idempotency key, policy context, and
correlation identifier.

## Events

Required events include:

- `AIOperationCreated`
- `AIInterpretationRecorded`
- `CandidateObjectRecorded`
- `CandidateRelationshipRecorded`
- `ProbableContradictionDetected`
- `CandidatePromoted`
- `CandidateRejected`

## Security and governance

R04-IR-01 enforces AI authority boundaries, source classification, secret
redaction, provider configuration validation, prompt/output provenance, and
promotion review. AI cannot approve its own high-risk canonical writes.

## Repository implementation mapping

This IR specification is implemented through the existing R4 AI interpretation
boundary:

- Runtime/domain: `apps/api/src/ai_enterprise/application/r4_ai_interpretation.py`
- API routes: `apps/api/src/ai_enterprise/api/routes/r4_ai_interpretation.py`
- API schemas: `apps/api/src/ai_enterprise/api/r4_ai_interpretation_schemas.py`
- Migrations: `migrations/versions/*r4*.py`
- Schemas: `specifications/AI-INTERPRETATION-0.1.md`
- Evidence package: `implementation/r04`
- Tests: `apps/api/tests/test_r4*.py`

## Acceptance criteria

R04-IR-01 is implementation-ready when:

- AI operations produce traceable evidence;
- candidate objects and relationships are persisted separately from canonical
  records;
- contradictions and uncertainty are represented;
- promotion is explicit and governed;
- sensitive data policy is enforced before provider exposure;
- R5 can consume promoted canonical manifest concepts.

## Readiness verdict

Overall status: IMPLEMENTATION READY.

Repository reconciliation: complete through P14 and `implementation/r04`.
