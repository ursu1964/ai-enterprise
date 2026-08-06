# R13-IR-01 — AI-Enterprise AI Orchestration Engine Specification

Document ID: R13-IR-01  
Version: 1.0.0  
Status: IMPLEMENTATION READY  
Classification: Constitutional Platform Module  
Implementation Target: Future IR/P23 reconciliation  
Primary Dependencies: R2–R12-IR-01

## Purpose

R13-IR-01 defines the AI Orchestration Engine as the constitutional capability
for safely planning, routing, supervising, evaluating, and constraining AI model
and agent participation inside AI-Enterprise.

It ensures AI is useful without becoming an ungoverned authority. AI may
propose, transform, summarize, classify, draft, evaluate, and recommend. AI
does not independently approve constitutional actions, fabricate evidence,
override policies, or conceal uncertainty.

## Architectural role

R13-IR-01 coordinates AI execution across constitutional modules and consumes:

- policy decisions from R12-IR-01;
- evidence and audit services from R11-IR-01;
- verification obligations from R10-IR-01;
- existing manifest, graph, artifact, runtime, and orchestration contracts.

Existing product-platform R13 remains the repository bootstrap module. This IR
specification defines AI orchestration governance and does not replace that R13
module.

## Constitutional requirements

- Every AI operation binds to an exact purpose, subject, policy context, model
  configuration, prompt/context version, tool scope, and evidence plan.
- AI outputs are classified by authority level: advisory, proposed,
  review-required, or prohibited.
- AI cannot approve its own high-risk output.
- AI cannot silently mutate authoritative state.
- AI cannot access tools, evidence, secrets, repositories, or production systems
  outside an explicit policy-approved tool scope.
- AI uncertainty, fallback, refusal, and escalation behavior are explicit.
- Prompt, context, tool, model, and adapter versions are recorded.
- Model/provider failures produce governed failure states, not fabricated
  outputs.
- Human review is required where policy, criticality, regulated impact, or
  separation of duties demands it.
- AI-generated evidence is derived evidence and cannot replace raw evidence.

## Bounded context

Bounded Context: AI Orchestration, Model Governance, and Tool-Bounded Autonomy

Owning Authority: AI Orchestration Authority

Primary aggregate root:

- `AIOperation`

Supporting aggregates:

- `AIOrchestrationPlan`
- `ModelProviderProfile`
- `ModelInvocation`
- `PromptContract`
- `ContextPackage`
- `ToolScope`
- `AIOutput`
- `AIReview`
- `AIQualityAssessment`
- `AIExecutionPolicy`
- `AIIncident`
- `AIEscalation`
- `AIUsageBudget`
- `AIReplayRecord`

## Canonical domain model

### AIOperation

```yaml
AIOperation:
  ai_operation_id: string
  organization_id: string
  project_id: string | null
  subject_type: string
  subject_id: string
  operation_type: INTERPRET | GENERATE | CLASSIFY | SUMMARIZE | PLAN | REVIEW | VERIFY | RECOMMEND | ROUTE | EXPLAIN
  authority_level: ADVISORY | PROPOSED_CHANGE | REVIEW_REQUIRED | PROHIBITED_DIRECT_AUTHORITY
  orchestration_plan_id: string
  policy_decision_id: string
  model_provider_profile_id: string
  prompt_contract_id: string
  context_package_id: string
  tool_scope_id: string | null
  status: PLANNED | AUTHORIZED | RUNNING | OUTPUT_READY | REVIEWING | ACCEPTED | REJECTED | BLOCKED | FAILED | CANCELLED
  evidence_references: [EvidenceReference]
  content_hash: string
  created_at: datetime
  created_by: ActorReference
```

### ModelProviderProfile

```yaml
ModelProviderProfile:
  model_provider_profile_id: string
  provider: OPENAI | ANTHROPIC | GOOGLE | LOCAL | CUSTOM_HTTP | MOCK
  model: string
  endpoint_reference: string | null
  credential_reference: string | null
  timeout_seconds: integer
  retry_policy_reference: string
  data_boundary: string
  retention_policy_reference: string
  production_enabled: boolean
  status: DRAFT | APPROVED | ACTIVE | DISABLED | RETIRED
```

### ModelInvocation

```yaml
ModelInvocation:
  model_invocation_id: string
  ai_operation_id: string
  provider_profile_id: string
  prompt_hash: string
  context_hash: string
  tool_scope_hash: string | null
  request_reference: string
  response_reference: string | null
  token_usage: object | null
  latency_ms: integer | null
  status: QUEUED | RUNNING | SUCCEEDED | FAILED | TIMED_OUT | BLOCKED | CANCELLED
  error_code: string | null
  evidence_references: [EvidenceReference]
  invoked_at: datetime
```

### PromptContract

```yaml
PromptContract:
  prompt_contract_id: string
  purpose: string
  system_instruction_version: string
  task_instruction_version: string
  allowed_inputs: [string]
  prohibited_inputs: [string]
  expected_output_schema: string
  safety_constraints: [string]
  refusal_rules: [string]
  escalation_rules: [string]
  content_hash: string
  status: DRAFT | REVIEWED | APPROVED | ACTIVE | SUPERSEDED | RETIRED
```

### ToolScope

```yaml
ToolScope:
  tool_scope_id: string
  ai_operation_id: string
  allowed_tools: [string]
  denied_tools: [string]
  allowed_resources: [string]
  denied_resources: [string]
  destructive_actions_allowed: boolean
  external_network_allowed: boolean
  credential_access_allowed: boolean
  approval_required_for: [string]
  policy_decision_id: string
  content_hash: string
```

### AIOutput

```yaml
AIOutput:
  ai_output_id: string
  ai_operation_id: string
  output_type: TEXT | JSON | PATCH | PLAN | CLASSIFICATION | SUMMARY | TEST_CASE | FINDING | RECOMMENDATION
  output_reference: string
  output_hash: string
  schema_validation_status: VALID | INVALID | NOT_APPLICABLE
  confidence: number | null
  uncertainty_notes: [string]
  proposed_state_changes: [string]
  requires_human_review: boolean
  prohibited_authority_detected: boolean
  evidence_references: [EvidenceReference]
  created_at: datetime
```

## Lifecycle and invariants

AI operation lifecycle:

`PLANNED → AUTHORIZED → RUNNING → OUTPUT_READY → REVIEWING → ACCEPTED`

Alternative terminal states:

- `REJECTED`
- `BLOCKED`
- `FAILED`
- `CANCELLED`

Forbidden transitions:

- `PLANNED → RUNNING`
- `RUNNING → ACCEPTED`
- `OUTPUT_READY → ACCEPTED` when review is required
- `FAILED → ACCEPTED`
- `BLOCKED → ACCEPTED`

Core invariants:

- Every AI operation has a policy decision before model invocation.
- Every provider invocation records provider, model, prompt, context, and tool
  scope hashes.
- Production AI calls require non-mock provider profile, credential reference,
  endpoint where applicable, timeout, retry, and data-boundary policy.
- Tool use is deny-by-default.
- AI output cannot directly mutate authoritative state unless the operation
  type and authority level explicitly permit a proposed change followed by
  governed review.
- Raw model request and response references are preserved through R11-IR-01
  according to classification.

## Commands

Required commands include:

- `CreateAIOrchestrationPlan`
- `RegisterModelProviderProfile`
- `ApproveModelProviderProfile`
- `CreatePromptContract`
- `ApprovePromptContract`
- `BuildContextPackage`
- `AuthorizeAIOperation`
- `StartAIOperation`
- `InvokeModel`
- `RecordModelOutput`
- `ValidateAIOutput`
- `RequestAIReview`
- `ApproveAIOutput`
- `RejectAIOutput`
- `EscalateAIOperation`
- `BlockAIOperation`
- `CancelAIOperation`
- `CreateAIIncident`
- `ReplayAIOperation`
- `AssessAIQuality`

Every mutating command includes authenticated actor, organization, subject,
policy decision, evidence plan, idempotency key, reason, and correlation
identifier.

## Queries

Required queries include:

- `GetAIOperation`
- `GetModelInvocation`
- `GetPromptContract`
- `GetContextPackage`
- `GetToolScope`
- `GetAIOutput`
- `ListBlockedAIOperations`
- `ListAIOutputsAwaitingReview`
- `TraceAIOutputToInputs`
- `FindModelInvocationsByProvider`
- `FindAIIncidents`
- `ComparePromptContracts`
- `GetAIUsageByProject`

Queries are policy-filtered and evidence access is classification-aware.

## Events

Required events include:

- `AIOrchestrationPlanCreated`
- `ModelProviderProfileRegistered`
- `ModelProviderProfileApproved`
- `PromptContractCreated`
- `PromptContractApproved`
- `ContextPackageBuilt`
- `AIOperationAuthorized`
- `AIOperationStarted`
- `ModelInvocationStarted`
- `ModelInvocationSucceeded`
- `ModelInvocationFailed`
- `AIOutputRecorded`
- `AIOutputValidationFailed`
- `AIReviewRequested`
- `AIOutputApproved`
- `AIOutputRejected`
- `AIOperationEscalated`
- `AIOperationBlocked`
- `AIIncidentCreated`
- `AIQualityAssessmentCompleted`

## Security and governance

R13-IR-01 enforces:

- provider credential references instead of inline secrets;
- production fail-closed behavior for mock/disabled providers;
- prompt-injection and tool-abuse boundaries;
- deny-by-default tool scopes;
- tenant, project, evidence, and repository isolation;
- human review for critical output;
- data-retention and data-boundary controls;
- audit of model requests, responses, tool calls, refusals, and failures;
- budget and rate controls;
- explicit incident handling for unsafe output or policy bypass attempts.

## Cross-module contracts

R13-IR-01 integrates with:

- R4 AI interpretation and extraction;
- R10-IR verification of AI behavior;
- R11-IR evidence capture of prompts, contexts, outputs, and reviews;
- R12-IR policy decisions for model, tool, data, and approval authority;
- R18 generator orchestration provider adapters;
- R21 execution orchestration;
- R22 artifact evidence graph.

## Repository implementation mapping

Existing repository evidence includes:

- R4 AI provider/retry/security infrastructure:
  `apps/api/src/ai_enterprise/infrastructure/r4_ai/`
- R18 generator orchestration runtime:
  `apps/api/src/ai_enterprise/application/r18_generator_orchestration_runtime.py`
- R18 live provider smoke tests:
  `apps/api/tests/test_r18_live_provider_smoke.py`
- local activation security:
  `apps/api/src/ai_enterprise/infrastructure/security/local_activation.py`
- execution broker policy/runner components:
  `apps/api/src/ai_enterprise/infrastructure/execution_broker/`

Future implementation should reconcile AI orchestration through these existing
provider, policy, evidence, and execution boundaries.

## Verification strategy

Tests must cover:

- provider profile approval and production fail-closed behavior;
- prompt contract lifecycle;
- context package hashing;
- deny-by-default tool scopes;
- model invocation success/failure recording;
- output schema validation;
- required human review;
- AI incident creation;
- replay with fixed inputs;
- credential redaction;
- prompt-injection and tool-abuse rejection;
- classification-aware evidence capture.

## Acceptance criteria

R13-IR-01 is implementation-ready when:

- AI operations, provider profiles, prompt contracts, context packages, tool
  scopes, invocations, outputs, reviews, incidents, and quality assessments are
  explicitly modeled;
- every AI invocation binds to policy, prompt, context, provider, model, and
  tool scope versions;
- production provider calls fail closed without configured credentials and
  endpoint references;
- model failures are preserved as governed failures;
- AI output authority levels are enforced;
- human review gates are deterministic;
- AI evidence is recorded through R11-IR-01;
- AI policy decisions are recorded through R12-IR-01;
- AI remains advisory unless a governed workflow accepts a proposed output.

## Readiness verdict

Overall status: IMPLEMENTATION READY.

Repository reconciliation: conditional. Existing R4/R18 provider and execution
boundaries provide a baseline; future implementation should consolidate them
under this IR contract without duplicating AI authority.
