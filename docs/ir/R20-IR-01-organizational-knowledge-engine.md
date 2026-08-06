# R20-IR-01 — AI-Enterprise Organizational Knowledge Engine Specification

Document ID: R20-IR-01  
Version: 1.0.0  
Status: IMPLEMENTATION READY  
Classification: Constitutional Platform Module  
Implementation Target: Future IR/P30 reconciliation  
Primary Dependencies: R2–R19-IR-01

## Purpose

R20-IR-01 defines the Organizational Knowledge Engine: the governed capability
for capturing, curating, retrieving, validating, preserving, and applying
organizational knowledge across AI-Enterprise.

Organizational knowledge is not a pile of notes or vector embeddings. It is a
policy-controlled knowledge system with source provenance, scope, classification,
trust level, temporal validity, ontology alignment, evidence links, retrieval
constraints, curation workflow, and learning feedback.

R20 enables the platform to remember decisions, lessons, patterns, failures,
operational history, requirements rationale, architecture knowledge, runtime
incidents, and organizational practices without allowing stale, unauthorized, or
unverified knowledge to silently drive future work.

## Architectural role

R20-IR-01 follows R19-IR-01. R19 controls who can access knowledge; R20 governs
what knowledge exists, how it is trusted, how it is retrieved, and how it evolves
over time.

Existing product-platform R20 remains the Runtime Kernel module. This IR
specification defines the constitutional organizational knowledge engine and
does not replace that R20 module.

R20-IR-01 SHALL reconcile with existing knowledge directories, knowledge
retrieval, project memory, graph ontology, runtime kernel, organizational
learning, change observations, and evidence/audit components during future
implementation.

## Constitutional requirements

- Every authoritative knowledge item SHALL have identity, owner, scope,
  classification, source, provenance, trust level, temporal status, evidence,
  and content hash.
- Derived indexes, embeddings, summaries, and caches are non-authoritative and
  SHALL remain rebuildable from governed knowledge items.
- Retrieval SHALL be policy-filtered before semantic providers or ranking logic
  receive candidate content.
- Knowledge access SHALL enforce tenant, project, scope, classification, and
  purpose restrictions from R19 and R12.
- Stale, disputed, superseded, withdrawn, expired, and unverified knowledge SHALL
  be represented explicitly.
- AI-generated summaries and hypotheses are derived knowledge, not raw evidence
  or authoritative fact.
- Organizational learning SHALL produce hypotheses and recommendations, not
  automatic governance changes.
- Knowledge used for decisions SHALL be traceable to source items and evidence.
- Missing required organizational knowledge SHALL be represented as a knowledge
  gap.
- Curation, correction, supersession, archival, and deletion SHALL preserve audit
  and evidence continuity.

## Bounded context

Bounded Context: Organizational Knowledge, Curation, Retrieval, Ontology,
Learning, and Knowledge Governance

Owning Authority: Organizational Knowledge Authority

Primary aggregate root:

- `KnowledgeItem`

Supporting aggregates:

- `KnowledgeSource`
- `KnowledgeCollection`
- `KnowledgeItemVersion`
- `KnowledgeProvenance`
- `KnowledgeEvidenceLink`
- `KnowledgeClassification`
- `KnowledgeTrustAssessment`
- `KnowledgeCurationTask`
- `KnowledgeCorrection`
- `KnowledgeSupersession`
- `KnowledgeRetrievalSession`
- `KnowledgeRetrievalResult`
- `KnowledgeIndex`
- `EmbeddingRecord`
- `OntologyConcept`
- `OntologyRelationship`
- `KnowledgeGap`
- `LearningObservation`
- `LearningHypothesis`
- `EngineeringRecommendation`
- `KnowledgeExport`

## Canonical domain model

### KnowledgeItem

```yaml
KnowledgeItem:
  knowledge_item_id: string
  organization_id: string
  project_id: string | null
  knowledge_key: string
  item_type: DECISION | LESSON | REQUIREMENT_RATIONALE | ARCHITECTURE_PATTERN | RUNBOOK | INCIDENT_LEARNING | POLICY_GUIDANCE | DOMAIN_FACT | OPERATIONAL_FACT | CUSTOM
  title: string
  statement: string
  scope_type: ORGANIZATION | TENANT | PROJECT | REPOSITORY | RUNTIME | AGENT | WORKFLOW | DOMAIN | CUSTOM
  scope_id: string
  classification: PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED | HIGHLY_RESTRICTED
  trust_level: UNVERIFIED | OBSERVED | REVIEWED | VERIFIED | CERTIFIED
  temporal_status: CURRENT | STALE | DISPUTED | SUPERSEDED | WITHDRAWN | EXPIRED
  owner: ActorReference
  source_ids: [string]
  evidence_references: [EvidenceReference]
  valid_from: datetime
  valid_until: datetime | null
  content_hash: string
```

### KnowledgeSource

```yaml
KnowledgeSource:
  knowledge_source_id: string
  organization_id: string
  source_type: MANUAL_ENTRY | REQUIREMENT | ARCHITECTURE_DECISION | VERIFICATION_RESULT | INCIDENT | RUNTIME_OBSERVATION | REPOSITORY | EXTERNAL_DOCUMENT | AI_DERIVED | CUSTOM
  source_reference: string
  producer: ActorReference | AgentReference | ServiceReference | null
  provenance_hash: string
  reliability_rating: LOW | MEDIUM | HIGH | AUTHORITATIVE
  ingestion_status: RECEIVED | VALIDATED | ACCEPTED | REJECTED | QUARANTINED
  evidence_references: [EvidenceReference]
```

### KnowledgeItemVersion

```yaml
KnowledgeItemVersion:
  knowledge_item_version_id: string
  knowledge_item_id: string
  version_number: integer
  statement: string
  change_summary: string
  changed_by: ActorReference
  previous_version_id: string | null
  status: DRAFT | REVIEWED | APPROVED | CURRENT | SUPERSEDED | WITHDRAWN
  created_at: datetime
  content_hash: string
```

### KnowledgeCurationTask

```yaml
KnowledgeCurationTask:
  knowledge_curation_task_id: string
  knowledge_item_id: string | null
  task_type: REVIEW | VERIFY | CORRECT | CLASSIFY | SUPERSEDE | WITHDRAW | ARCHIVE | MERGE | SPLIT
  reason: string
  assigned_to: ActorReference
  required_evidence_types: [string]
  status: OPEN | IN_REVIEW | COMPLETED | REJECTED | CANCELLED
  due_at: datetime | null
  evidence_references: [EvidenceReference]
```

### KnowledgeRetrievalSession

```yaml
KnowledgeRetrievalSession:
  knowledge_retrieval_session_id: string
  organization_id: string
  project_id: string | null
  runtime_session_id: string
  actor_id: string
  assignment_id: string | null
  query_hash: string
  policy_version: string
  authorized_scope_references: [string]
  maximum_classification: string
  status: STARTED | COMPLETED | DENIED | FAILED | PARTIAL
  started_at: datetime
  completed_at: datetime | null
  evidence_reference: string | null
```

### KnowledgeRetrievalResult

```yaml
KnowledgeRetrievalResult:
  knowledge_retrieval_result_id: string
  knowledge_retrieval_session_id: string
  knowledge_item_id: string
  knowledge_item_version_id: string
  rank: integer
  score: number
  lexical_score: number
  semantic_score: number | null
  trust_score: number
  freshness_score: number
  token_count: integer
  included: boolean
  exclusion_reason: string | null
```

### KnowledgeIndex

```yaml
KnowledgeIndex:
  knowledge_index_id: string
  organization_id: string
  project_id: string | null
  index_type: LEXICAL | SEMANTIC | HYBRID | GRAPH | CUSTOM
  item_set_hash: string
  embedding_model_version: string | null
  tokenizer_version: string
  policy_version: string
  status: BUILDING | ACTIVE | STALE | FAILED | RETIRED
  built_at: datetime
  rebuildable: boolean
```

### OntologyConcept

```yaml
OntologyConcept:
  ontology_concept_id: string
  organization_id: string
  canonical_name: string
  concept_type: DOMAIN | PROCESS | ROLE | ARTIFACT | POLICY | RISK | CONTROL | SYSTEM | CUSTOM
  definition: string
  aliases: [string]
  owner: ActorReference
  status: DRAFT | APPROVED | ACTIVE | DEPRECATED | RETIRED
  evidence_references: [EvidenceReference]
```

### LearningHypothesis

```yaml
LearningHypothesis:
  learning_hypothesis_id: string
  organization_id: string
  project_id: string | null
  source_observation_ids: [string]
  hypothesis_statement: string
  confidence: number
  affected_systems: [string]
  recommended_validation: [string]
  status: PROPOSED | REVIEWED | VALIDATED | REJECTED | SUPERSEDED
  evidence_references: [EvidenceReference]
```

### KnowledgeGap

```yaml
KnowledgeGap:
  knowledge_gap_id: string
  organization_id: string
  project_id: string | null
  subject_type: string
  subject_id: string
  required_knowledge_type: string
  reason: string
  severity: LOW | MEDIUM | HIGH | CRITICAL
  blocking: boolean
  owner: ActorReference
  status: OPEN | RESOLVING | RESOLVED | WAIVED | ACCEPTED_RISK
```

## Lifecycle and invariants

Knowledge item lifecycle:

```text
DRAFT → REVIEWED → APPROVED → CURRENT
CURRENT → STALE
CURRENT → DISPUTED
CURRENT → SUPERSEDED
CURRENT → WITHDRAWN
CURRENT → EXPIRED
```

Curation lifecycle:

```text
OPEN → IN_REVIEW → COMPLETED
OPEN → REJECTED
OPEN → CANCELLED
```

Learning lifecycle:

```text
PROPOSED → REVIEWED → VALIDATED
PROPOSED → REVIEWED → REJECTED
VALIDATED → SUPERSEDED
```

Core invariants:

- Every authoritative knowledge item has provenance and content hash.
- Every retrieval session records policy version and authorized scopes.
- Unauthorized knowledge is filtered before ranking or embedding providers see
  it.
- Derived indexes are rebuildable and non-authoritative.
- Every AI-derived item is labeled as derived and links to source material.
- Stale or disputed knowledge cannot be silently treated as current.
- Knowledge used in a governed decision is traceable to retrieved item versions.
- Curation corrections preserve prior versions.
- Knowledge deletion or withdrawal preserves audit/evidence continuity.

## Commands

R20-IR-01 SHALL define at least:

- `RegisterKnowledgeSource`
- `IngestKnowledgeItem`
- `ValidateKnowledgeItem`
- `ApproveKnowledgeItem`
- `ClassifyKnowledgeItem`
- `MarkKnowledgeStale`
- `DisputeKnowledgeItem`
- `CorrectKnowledgeItem`
- `SupersedeKnowledgeItem`
- `WithdrawKnowledgeItem`
- `ArchiveKnowledgeItem`
- `CreateKnowledgeCollection`
- `CreateKnowledgeCurationTask`
- `CompleteKnowledgeCurationTask`
- `BuildKnowledgeIndex`
- `RebuildKnowledgeIndex`
- `StartKnowledgeRetrievalSession`
- `RecordKnowledgeRetrievalResult`
- `RegisterOntologyConcept`
- `RegisterOntologyRelationship`
- `CreateLearningObservation`
- `CreateLearningHypothesis`
- `CreateEngineeringRecommendation`
- `CreateKnowledgeGap`
- `ResolveKnowledgeGap`
- `ExportKnowledgePackage`

Every mutating command SHALL include authenticated actor, organization, project
where applicable, scope, expected aggregate revision, idempotency key, policy
context, reason, and correlation identifier.

## Queries

R20-IR-01 SHALL provide:

- `GetKnowledgeItem`
- `GetKnowledgeItemVersion`
- `GetKnowledgeSource`
- `GetKnowledgeCollection`
- `GetKnowledgeCurationTask`
- `GetKnowledgeIndex`
- `GetKnowledgeRetrievalSession`
- `GetOntologyConcept`
- `GetLearningHypothesis`
- `GetEngineeringRecommendation`
- `ListKnowledgeItems`
- `ListStaleKnowledge`
- `ListDisputedKnowledge`
- `ListKnowledgeGaps`
- `SearchKnowledge`
- `RetrieveAuthorizedKnowledge`
- `TraceKnowledgeToEvidence`
- `TraceKnowledgeToSource`
- `TraceDecisionToKnowledge`
- `FindKnowledgeWithoutEvidence`
- `FindExpiredKnowledge`
- `FindUnauthorizedRetrievalAttempts`

Queries SHALL be policy-filtered and SHALL not expose unauthorized knowledge,
restricted evidence, private project memory, sensitive operational details, or
derived AI summaries that would leak restricted source material.

## Events

R20-IR-01 SHALL publish immutable domain events including:

- `KnowledgeSourceRegistered`
- `KnowledgeItemIngested`
- `KnowledgeItemValidated`
- `KnowledgeItemApproved`
- `KnowledgeItemClassified`
- `KnowledgeMarkedStale`
- `KnowledgeItemDisputed`
- `KnowledgeItemCorrected`
- `KnowledgeItemSuperseded`
- `KnowledgeItemWithdrawn`
- `KnowledgeItemArchived`
- `KnowledgeCollectionCreated`
- `KnowledgeCurationTaskCreated`
- `KnowledgeCurationTaskCompleted`
- `KnowledgeIndexBuilt`
- `KnowledgeIndexRebuilt`
- `KnowledgeRetrievalStarted`
- `KnowledgeRetrievalCompleted`
- `KnowledgeRetrievalDenied`
- `OntologyConceptRegistered`
- `OntologyRelationshipRegistered`
- `LearningObservationCreated`
- `LearningHypothesisCreated`
- `EngineeringRecommendationCreated`
- `KnowledgeGapDetected`
- `KnowledgeGapResolved`
- `KnowledgePackageExported`

Events SHALL include organization, project where applicable, knowledge item,
scope, actor, policy, evidence, correlation, causation, timestamp, and
classification references.

## Security and governance

R20-IR-01 SHALL enforce:

- tenant, project, scope, classification, and purpose-limited access;
- R19 authorization before retrieval;
- policy-filtering before semantic ranking or embedding;
- derived-index non-authority;
- source provenance and evidence requirements;
- classification and trust-level governance;
- curation review for authoritative knowledge;
- protection against stale/disputed knowledge misuse;
- redaction for exports and summaries;
- retention, archival, and withdrawal policy;
- audit/evidence capture for curation and access decisions;
- prevention of cross-project memory leakage;
- protection against AI-generated hallucinated organizational facts.

AI may propose summaries, identify similar knowledge, detect gaps, suggest
ontology links, create hypotheses, and recommend improvements.

AI SHALL NOT create authoritative knowledge without curation, access
unauthorized knowledge, replace evidence, silently resolve disputes, or turn
hypotheses into governance changes without approval.

## Cross-module contracts

R20-IR-01 integrates with:

- R2 for project and manifest context.
- R3 and R4 for semantic and graph ontology context.
- R5 for requirements rationale and satisfaction history.
- R6 for architecture decisions and patterns.
- R7 for planning lessons and delivery history.
- R8 for artifact-generation knowledge.
- R9 for implementation outcomes.
- R10 for verification results and quality lessons.
- R11 for evidence and audit linkage.
- R12 for knowledge access, retention, export, and curation policies.
- R13 for AI orchestration context.
- R14 for agent knowledge access boundaries.
- R15 for workflow knowledge usage.
- R16 for repository knowledge and change history.
- R17 for deployment and operations history.
- R18 for telemetry, incidents, and runtime observations.
- R19 for identity, authorization, classification, and access control.
- R21 for platform administration knowledge.
- R22 for constitutional evolution history.

R20 SHALL NOT replace R11 evidence, R19 authorization, R12 policy, or R22
constitutional authority.

## Repository implementation mapping

Existing repository capabilities relevant to R20-IR-01 include:

- `knowledge/`
- `apps/api/src/ai_enterprise/domain/knowledge/retrieval.py`
- `apps/api/src/ai_enterprise/infrastructure/knowledge/retrieval.py`
- `apps/api/src/ai_enterprise/api/routes/r19_project_memory.py`
- `apps/api/src/ai_enterprise/application/r19_project_memory_runtime.py`
- `apps/api/src/ai_enterprise/application/r20_runtime_kernel_runtime.py`
- `apps/api/src/ai_enterprise/api/routes/r20_runtime_kernel.py`
- `apps/api/src/ai_enterprise/api/routes/r16_knowledge_graph.py`
- `apps/api/src/ai_enterprise/application/evolution/learning_service.py`
- `apps/api/src/ai_enterprise/domain/evolution/organizational.py`
- `apps/api/src/ai_enterprise/application/change_management/service.py`
- `apps/api/tests/test_knowledge_retrieval_context.py`
- `apps/api/tests/test_r19_project_memory_runtime.py`
- `apps/api/tests/test_r20_runtime_kernel_runtime.py`
- `docs/r20-runtime-kernel-status.md`
- `docs/reference-architecture/`
- `runtime/`

Future implementation SHALL inventory these components before adding new
runtime code. The existing R20 runtime kernel remains a product-platform module
and shall be reconciled as an organizational knowledge consumer and producer
where appropriate instead of replacing it.

No new root-level Python source tree SHALL be created. Application code remains
under `apps/api/src`.

## Verification strategy

Unit tests SHALL cover:

- knowledge item lifecycle;
- source provenance validation;
- classification and trust levels;
- stale/disputed/superseded state behavior;
- curation tasks;
- retrieval authorization;
- pre-ranking filtering;
- index rebuildability;
- ontology concept validation;
- learning hypothesis constraints;
- knowledge-gap behavior.

Contract tests SHALL cover:

- R11 evidence links;
- R12 curation and retrieval policies;
- R14 agent knowledge access;
- R19 authorization boundaries;
- R18 incident/telemetry learning inputs;
- command, query, event, and error schemas.

Integration tests SHALL cover:

- ingesting knowledge with evidence;
- retrieving project-scoped knowledge;
- denying cross-project retrieval;
- building and rebuilding an index;
- creating AI-derived summaries as non-authoritative derived knowledge;
- converting incident observations into learning hypotheses;
- exporting redacted knowledge packages.

Security tests SHALL cover:

- unauthorized knowledge retrieval;
- restricted-classification leakage;
- embedding provider receiving unauthorized items;
- stale/disputed knowledge used without warning;
- AI summary leaking restricted source material;
- cross-tenant memory access;
- forged provenance.

Resilience tests SHALL cover:

- index corruption and rebuild;
- semantic provider outage;
- evidence-store outage;
- curation workflow interruption;
- delayed source ingestion;
- duplicate knowledge ingestion;
- export failure and recovery.

## Acceptance criteria

R20-IR-01 is implementation-ready when:

- Knowledge items, sources, versions, provenance, curation tasks, retrieval
  sessions, results, indexes, ontology concepts, learning hypotheses,
  recommendations, and gaps have explicit schemas.
- Retrieval is policy-filtered before ranking or embedding.
- Derived indexes and summaries are non-authoritative and rebuildable.
- Stale, disputed, superseded, withdrawn, expired, and unverified states are
  explicit.
- Knowledge used in governed decisions is traceable to source item versions and
  evidence.
- Curation, correction, supersession, withdrawal, archival, export, and deletion
  preserve audit continuity.
- Commands, queries, events, security rules, repository mapping, and verification
  strategy are defined.
- The document explicitly preserves the existing R20 runtime kernel module and
  does not create a second implementation architecture.

## Readiness verdict

| Gate | Status |
|---|---|
| Semantic completeness | PASS |
| Contract completeness | PASS |
| Governance completeness | PASS |
| Operational completeness | PASS |
| Repository compatibility | CONDITIONAL — requires IR/P30 reconciliation |
| Verification completeness | PASS |
| Cross-R consistency | PASS |

Overall status: IMPLEMENTATION READY.

R20-IR-01 is ready for Architecture Baseline v1.0 inclusion. Future
implementation should reconcile existing knowledge storage, retrieval, project
memory, graph ontology, runtime kernel, organizational learning, change
observations, evidence, and audit components into this IR contract without
duplicating organizational knowledge authority.
