# R15-IR-01 — AI-Enterprise Workflow and Process Engine Specification

Document ID: R15-IR-01  
Version: 1.0.0  
Status: IMPLEMENTATION READY  
Classification: Constitutional Platform Module  
Implementation Target: Future IR/P25 reconciliation  
Primary Dependencies: R2–R14-IR-01

## Purpose

R15-IR-01 defines the Workflow and Process Engine: the governed capability for
declaring, validating, executing, observing, pausing, resuming, compensating, and
auditing constitutional workflows across AI-Enterprise.

A workflow is not a loose script or background job. It is a policy-bound process
definition with explicit inputs, actors, agents, decisions, states, transitions,
gates, evidence obligations, failure handling, compensation behavior, and
completion criteria.

R15 provides the process layer that coordinates requirements, architecture,
planning, generation, implementation, verification, evidence, policy,
orchestration, agents, repositories, deployment, and operations without allowing
ad hoc execution to bypass constitutional controls.

## Architectural role

R15-IR-01 sits after R14-IR-01. R13 orchestrates AI operations, R14 defines
agent identity and capability, and R15 governs multi-step work as durable,
observable, policy-controlled processes.

Existing product-platform R15 remains the executable Manifest Compiler module.
This IR specification defines the constitutional workflow and process engine and
does not replace that R15 module.

R15-IR-01 SHALL reconcile with existing workflow, broker, transition-policy,
compiler, evidence, and orchestration components during future implementation.

## Constitutional requirements

- Every authoritative workflow has a stable definition, version, owner, purpose,
  policy scope, and lifecycle state.
- Every workflow execution binds to exact workflow definition, baseline,
  initiating command, actor, project, organization, input hashes, and
  correlation identifier.
- Transitions are explicit and policy-evaluated. A workflow SHALL NOT move to a
  privileged state by implicit side effect.
- Human, service, and agent participants execute only steps they are authorized
  to perform.
- Gates, approvals, reviews, waivers, and exception paths are first-class
  process states, not comments or external messages.
- Long-running workflows are durable and resumable from recorded state.
- Failed, cancelled, timed-out, blocked, retried, compensated, and superseded
  executions remain auditable.
- A retry creates a new attempt and SHALL NOT overwrite the prior attempt.
- Compensation is explicit, scoped, evidence-backed, and never assumed to have
  fully reversed effects without verification.
- Workflow evidence is captured through R11 and policy decisions are governed
  through R12.
- AI agents MAY perform workflow steps only through R14-defined agent authority.
- Workflow completion SHALL NOT imply requirement satisfaction, verification
  pass, release readiness, or production authorization unless the corresponding
  module emits the required verdict.

## Bounded context

Bounded Context: Workflow Definition, Process Execution, Gates, and
Compensation

Owning Authority: Process Runtime Authority

Primary aggregate root:

- `WorkflowDefinition`

Supporting aggregates:

- `WorkflowVersion`
- `WorkflowStep`
- `WorkflowTransition`
- `WorkflowGate`
- `WorkflowExecution`
- `WorkflowStepExecution`
- `WorkflowAttempt`
- `WorkflowDecision`
- `WorkflowApproval`
- `WorkflowException`
- `WorkflowCompensation`
- `WorkflowSchedule`
- `WorkflowSubscription`
- `WorkflowTimer`
- `WorkflowSignal`
- `WorkflowPolicyBinding`
- `WorkflowEvidenceBinding`
- `WorkflowProjection`

## Canonical domain model

### WorkflowDefinition

```yaml
WorkflowDefinition:
  workflow_definition_id: string
  organization_id: string
  canonical_name: string
  title: string
  description: string
  owner: ActorReference
  workflow_type: CONSTITUTIONAL | DELIVERY | VERIFICATION | RELEASE | OPERATIONS | INCIDENT | CUSTOM
  current_version_id: string
  lifecycle_status: DRAFT | VALIDATED | APPROVED | ACTIVE | SUSPENDED | DEPRECATED | RETIRED
  policy_scope: [string]
  evidence_requirements: [string]
  created_at: datetime
  updated_at: datetime
  content_hash: string
```

### WorkflowVersion

```yaml
WorkflowVersion:
  workflow_version_id: string
  workflow_definition_id: string
  semantic_version: string
  baseline_references: [string]
  step_ids: [string]
  transition_ids: [string]
  gate_ids: [string]
  input_schema: object
  output_schema: object
  compensation_strategy: string
  timeout_policy: object
  retry_policy: object
  concurrency_policy: object
  approval_reference: string | null
  status: DRAFT | VALIDATED | APPROVED | ACTIVE | SUPERSEDED | RETIRED
  content_hash: string
```

### WorkflowStep

```yaml
WorkflowStep:
  workflow_step_id: string
  workflow_version_id: string
  canonical_name: string
  step_type: COMMAND | QUERY | HUMAN_TASK | AGENT_TASK | SERVICE_TASK | GATE | TIMER | SIGNAL | SUBPROCESS | COMPENSATION
  participant_reference: ActorReference | AgentReference | ServiceReference | null
  input_mapping: object
  output_mapping: object
  required_authority: [string]
  required_evidence_types: [string]
  policy_checks: [string]
  timeout_policy: object
  retry_policy: object
  compensation_step_id: string | null
  idempotency_scope: string
```

### WorkflowTransition

```yaml
WorkflowTransition:
  workflow_transition_id: string
  workflow_version_id: string
  from_step_id: string
  to_step_id: string
  transition_type: NORMAL | CONDITIONAL | ERROR | COMPENSATION | ESCALATION | CANCELLATION | TIMEOUT
  condition_expression: string | null
  policy_checks: [string]
  required_evidence_types: [string]
  allowed_from_states: [string]
  resulting_state: string
```

### WorkflowExecution

```yaml
WorkflowExecution:
  workflow_execution_id: string
  workflow_definition_id: string
  workflow_version_id: string
  organization_id: string
  project_id: string | null
  initiated_by: ActorReference
  initiating_command_reference: string
  input_hash: string
  baseline_references: [string]
  status: REQUESTED | READY | RUNNING | WAITING | BLOCKED | SUSPENDED | COMPENSATING | COMPLETED | FAILED | CANCELLED | TIMED_OUT | SUPERSEDED
  current_step_ids: [string]
  attempt: integer
  correlation_id: string
  causation_id: string | null
  started_at: datetime | null
  completed_at: datetime | null
  content_hash: string
```

### WorkflowStepExecution

```yaml
WorkflowStepExecution:
  workflow_step_execution_id: string
  workflow_execution_id: string
  workflow_step_id: string
  attempt: integer
  executor: ActorReference | AgentReference | ServiceReference
  input_hash: string
  output_hash: string | null
  status: QUEUED | RUNNING | WAITING | PASSED | FAILED | ERROR | BLOCKED | SKIPPED | CANCELLED | TIMED_OUT
  policy_decision_references: [string]
  evidence_references: [EvidenceReference]
  started_at: datetime | null
  completed_at: datetime | null
```

### WorkflowGate

```yaml
WorkflowGate:
  workflow_gate_id: string
  workflow_version_id: string
  canonical_name: string
  gate_type: ENTRY | EXIT | APPROVAL | QUALITY | SECURITY | POLICY | EVIDENCE | RELEASE | CUSTOM
  required_verdicts: [string]
  required_approvers: [ActorReference]
  required_evidence_types: [string]
  failure_behavior: BLOCK | ESCALATE | COMPENSATE | CANCEL | DEFER
  waiver_allowed: boolean
  waiver_policy_reference: string | null
```

### WorkflowCompensation

```yaml
WorkflowCompensation:
  workflow_compensation_id: string
  workflow_execution_id: string
  triggering_step_execution_id: string
  compensation_plan: [string]
  status: PLANNED | RUNNING | COMPLETED | FAILED | PARTIAL | WAIVED
  residual_risk: string | null
  evidence_references: [EvidenceReference]
  approved_by: ActorReference | null
```

## Lifecycle and invariants

Workflow definition lifecycle:

```text
DRAFT → VALIDATED → APPROVED → ACTIVE → DEPRECATED → RETIRED
ACTIVE → SUSPENDED → ACTIVE
ACTIVE → SUPERSEDED
```

Workflow execution lifecycle:

```text
REQUESTED → READY → RUNNING → COMPLETED
REQUESTED → READY → RUNNING → WAITING → RUNNING
RUNNING → BLOCKED → RUNNING
RUNNING → SUSPENDED → RUNNING
RUNNING → COMPENSATING → FAILED
RUNNING → COMPENSATING → COMPLETED
RUNNING → FAILED
RUNNING → CANCELLED
RUNNING → TIMED_OUT
```

Forbidden transitions:

- `DRAFT → ACTIVE`
- `REQUESTED → COMPLETED`
- `FAILED → COMPLETED`
- `CANCELLED → RUNNING`
- `RETIRED → ACTIVE`
- `TIMED_OUT → COMPLETED` without explicit recovery execution

Core invariants:

- Every execution references one approved workflow version.
- Every step execution references one workflow execution and one workflow step.
- Every transition is validated against the workflow graph and policy context.
- Every privileged transition has an audit record.
- Every required gate has an explicit result.
- Every completed execution satisfies its declared exit criteria.
- Every failed execution records failure classification and evidence.
- Every compensation execution records residual effects and verification
  evidence where applicable.
- Every retry preserves previous attempts.
- Every agent step references an R14 agent session or run.
- Every policy-controlled step records R12 policy decision references.
- Every evidence-required step records R11 evidence references or an explicit
  evidence gap.

## Commands

R15-IR-01 SHALL define at least:

- `CreateWorkflowDefinition`
- `ValidateWorkflowDefinition`
- `ApproveWorkflowDefinition`
- `ActivateWorkflowDefinition`
- `SuspendWorkflowDefinition`
- `DeprecateWorkflowDefinition`
- `RetireWorkflowDefinition`
- `CreateWorkflowVersion`
- `RegisterWorkflowStep`
- `RegisterWorkflowTransition`
- `RegisterWorkflowGate`
- `StartWorkflowExecution`
- `ScheduleWorkflowExecution`
- `SignalWorkflowExecution`
- `ExecuteWorkflowStep`
- `RecordWorkflowDecision`
- `ApproveWorkflowGate`
- `RejectWorkflowGate`
- `BlockWorkflowExecution`
- `ResumeWorkflowExecution`
- `SuspendWorkflowExecution`
- `CancelWorkflowExecution`
- `RetryWorkflowStep`
- `StartWorkflowCompensation`
- `CompleteWorkflowCompensation`
- `CompleteWorkflowExecution`
- `FailWorkflowExecution`
- `SupersedeWorkflowExecution`

Every mutating command SHALL include authenticated actor, organization, project
where applicable, workflow reference, expected aggregate revision, idempotency
key, policy context, reason, and correlation identifier.

## Queries

R15-IR-01 SHALL provide:

- `GetWorkflowDefinition`
- `GetWorkflowVersion`
- `GetWorkflowExecution`
- `GetWorkflowStepExecution`
- `GetWorkflowGate`
- `GetWorkflowCompensation`
- `ListActiveWorkflowDefinitions`
- `ListWorkflowExecutions`
- `ListBlockedWorkflowExecutions`
- `ListWaitingWorkflowExecutions`
- `ListWorkflowExecutionsBySubject`
- `TraceWorkflowExecution`
- `TraceWorkflowToEvidence`
- `TraceWorkflowToPolicyDecisions`
- `FindWorkflowExecutionsMissingEvidence`
- `FindWorkflowExecutionsWithFailedCompensation`
- `CompareWorkflowVersions`
- `GetWorkflowExecutionHistory`

Queries SHALL be policy-filtered and SHALL NOT expose restricted evidence,
secret values, or unauthorized project data.

## Events

R15-IR-01 SHALL publish immutable domain events including:

- `WorkflowDefinitionCreated`
- `WorkflowDefinitionValidated`
- `WorkflowDefinitionApproved`
- `WorkflowDefinitionActivated`
- `WorkflowDefinitionSuspended`
- `WorkflowDefinitionDeprecated`
- `WorkflowDefinitionRetired`
- `WorkflowVersionCreated`
- `WorkflowStepRegistered`
- `WorkflowTransitionRegistered`
- `WorkflowGateRegistered`
- `WorkflowExecutionStarted`
- `WorkflowExecutionScheduled`
- `WorkflowExecutionSignaled`
- `WorkflowStepStarted`
- `WorkflowStepCompleted`
- `WorkflowStepFailed`
- `WorkflowGateApproved`
- `WorkflowGateRejected`
- `WorkflowExecutionBlocked`
- `WorkflowExecutionResumed`
- `WorkflowExecutionSuspended`
- `WorkflowExecutionCancelled`
- `WorkflowStepRetried`
- `WorkflowCompensationStarted`
- `WorkflowCompensationCompleted`
- `WorkflowCompensationFailed`
- `WorkflowExecutionCompleted`
- `WorkflowExecutionFailed`
- `WorkflowExecutionSuperseded`

Events SHALL include organization, project where applicable, workflow
definition, workflow version, execution, step, actor, policy, evidence,
correlation, causation, timestamp, and result references.

## Security and governance

R15-IR-01 SHALL enforce:

- strong identity for all human, service, workflow, and agent participants;
- role-, attribute-, and policy-based authorization;
- tenant and project isolation;
- deny-by-default step execution;
- least-privilege tool and data access;
- separation of duties for approval gates;
- explicit governance for destructive, privileged, deployment, production, and
  compensation steps;
- evidence capture for material transitions;
- auditability for denied and failed transitions;
- secret redaction in workflow inputs, outputs, events, logs, and evidence;
- controlled access to workflow projections and history;
- idempotency and replay safety for mutating commands;
- protection against agent self-escalation through workflow steps;
- protection against workflow definition tampering after approval.

AI may propose workflow definitions, classify failures, recommend retry scope,
summarize execution history, and detect missing gates.

AI SHALL NOT approve privileged gates, alter raw execution history, mark failed
steps as complete, hide compensation gaps, or bypass policy decisions.

## Cross-module contracts

R15-IR-01 integrates with:

- R2 for Manifest-driven project context.
- R3 and R4 for semantic and graph context.
- R5 for requirement workflow gates and satisfaction handoff.
- R6 for architecture decision and conformance workflows.
- R7 for planning and work-package workflow execution.
- R8 for artifact generation workflow steps.
- R9 for implementation and repository-change workflow steps.
- R10 for verification and validation gates.
- R11 for durable workflow evidence and audit records.
- R12 for transition, approval, exception, and access policy decisions.
- R13 for AI orchestration tasks.
- R14 for agent task execution and supervision boundaries.
- R16 for repository integration workflows.
- R17 for deployment and release workflows.
- R18 for workflow telemetry and operational observation.
- R19 for identity, delegation, and access enforcement.
- R20 for organizational process learning.
- R21 for platform administration workflows.
- R22 for constitutional evolution workflows.

R15 SHALL NOT directly mutate requirement satisfaction, verification verdict,
release authorization, or constitutional baseline state owned by other modules.

## Repository implementation mapping

Existing repository capabilities relevant to R15-IR-01 include:

- `apps/api/src/ai_enterprise/application/r15_manifest_compiler_runtime.py`
- `apps/api/src/ai_enterprise/api/routes/r15_manifest_compiler.py`
- `apps/api/src/ai_enterprise/api/r15_manifest_compiler_schemas.py`
- `apps/api/src/ai_enterprise/infrastructure/execution_broker/`
- `apps/api/src/ai_enterprise/api/routes/enterprise_evolution.py`
- `apps/api/src/ai_enterprise/application/enterprise_evolution_service.py`
- `packages/orchestration-contracts/`
- `docs/reference-architecture/07-workflows/`
- `apps/api/tests/test_r15_manifest_compiler_runtime.py`
- `apps/api/tests/test_execution_broker_runner.py`

Future implementation SHALL inventory these components before adding new
runtime code. The existing R15 Manifest Compiler remains a product-platform
module and shall be reconciled as an input/producer for workflow graph
definitions where appropriate instead of replacing it.

No new root-level Python source tree SHALL be created. Application code remains
under `apps/api/src`.

## Verification strategy

Unit tests SHALL cover:

- workflow definition validation;
- graph and transition rules;
- lifecycle invariants;
- gate evaluation;
- step authorization;
- idempotency and replay safety;
- retry preservation;
- compensation planning;
- evidence-gap behavior;
- policy denial behavior.

Contract tests SHALL cover:

- R11 evidence capture;
- R12 policy decision recording;
- R14 agent step execution boundary;
- R10 verification gate integration;
- R16/R17 repository and deployment step integration;
- command, query, event, and error schemas.

Integration tests SHALL cover:

- creating and activating a workflow definition;
- starting an execution from an approved version;
- executing service, human, agent, timer, signal, and gate steps;
- blocking and resuming execution;
- retrying failed steps without overwriting previous attempts;
- running compensation;
- completing with required evidence;
- tracing execution to evidence and policy decisions.

Security tests SHALL cover:

- unauthorized transition attempts;
- bypassed approval gates;
- cross-project workflow access;
- agent self-escalation through workflow steps;
- secret leakage in step payloads;
- tampered workflow definitions;
- replayed mutating commands;
- unauthorized compensation execution.

Resilience tests SHALL cover:

- worker crash during step execution;
- duplicate signal delivery;
- timer drift;
- evidence-store outage;
- policy-service outage;
- partial compensation;
- projection rebuild;
- event replay.

## Acceptance criteria

R15-IR-01 is implementation-ready when:

- Workflow definitions, versions, steps, transitions, gates, executions, step
  executions, and compensations have explicit schemas.
- Workflow definition and execution lifecycles are deterministic.
- Forbidden transitions are stated.
- Every execution binds to exact workflow version, actor, input hash, baseline
  references, and correlation identifier.
- Policy-controlled transitions record R12 policy decisions.
- Evidence-required transitions record R11 evidence or explicit evidence gaps.
- Agent steps are constrained by R14 authority.
- Human approvals and gates are first-class process records.
- Retry and compensation behavior is governed and auditable.
- Failure, cancellation, timeout, blocking, suspension, and supersession states
  remain distinct.
- Commands, queries, events, security rules, repository mapping, and verification
  strategy are defined.
- The document explicitly preserves the existing R15 Manifest Compiler module
  and does not create a second implementation architecture.

## Readiness verdict

| Gate | Status |
|---|---|
| Semantic completeness | PASS |
| Contract completeness | PASS |
| Governance completeness | PASS |
| Operational completeness | PASS |
| Repository compatibility | CONDITIONAL — requires IR/P25 reconciliation |
| Verification completeness | PASS |
| Cross-R consistency | PASS |

Overall status: IMPLEMENTATION READY.

R15-IR-01 is ready for Architecture Baseline v1.0 inclusion. Future
implementation should reconcile existing manifest compiler, execution broker,
workflow documentation, evidence, policy, and orchestration components into this
IR contract without duplicating workflow authority.
