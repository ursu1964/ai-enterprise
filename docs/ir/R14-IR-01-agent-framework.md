# R14-IR-01 — AI-Enterprise Agent Framework Specification

Document ID: R14-IR-01  
Version: 1.0.0  
Status: IMPLEMENTATION READY  
Classification: Constitutional Platform Module  
Implementation Target: Future IR/P24 reconciliation  
Primary Dependencies: R2–R13-IR-01

## Purpose

R14-IR-01 defines the Agent Framework: the governed model for declaring,
registering, authorizing, executing, supervising, evaluating, and retiring AI
and non-AI agents in AI-Enterprise.

An agent is not just a prompt or a process. An agent is a governed runtime
participant with identity, authority, allowed skills, tool scope, memory
boundary, evidence obligations, policy constraints, and review requirements.

## Architectural role

R14-IR-01 is downstream of R13-IR-01 AI orchestration. R13 coordinates AI
operations; R14 defines agent identities and capabilities that participate in
those operations.

Existing product-platform R14 remains the executable manifest schema module.
This IR specification defines the constitutional agent framework and does not replace
that R14 module.

## Constitutional requirements

- Every agent has stable identity, version, owner, purpose, authority class, and
  lifecycle state.
- Agents operate under explicit policy decisions and delegated authority.
- Skills and tools are deny-by-default.
- Agent sessions are bounded by organization, project, subject, task, time,
  memory, tool, and evidence scope.
- Agents cannot grant themselves authority, install capabilities, approve their
  own critical outputs, bypass evidence capture, or silently escalate tools.
- Agent outputs are attributable, reviewable, and evidence-backed.
- Agent memory and context access are policy-filtered and auditable.
- Tool calls include authorization, input hash, output hash, result, evidence,
  and correlation identifiers.
- Agent failures, refusals, blocked actions, and policy denials remain auditable.
- Human handoff is required for critical decisions, ambiguous authority, unsafe
  outputs, or policy-defined escalation conditions.

## Bounded context

Bounded Context: Agent Identity, Capability, Session, Tool, and Supervision

Owning Authority: Agent Runtime Authority

Primary aggregate root:

- `AgentDefinition`

Supporting aggregates:

- `AgentVersion`
- `AgentCapability`
- `AgentSkill`
- `AgentToolGrant`
- `AgentSession`
- `AgentTask`
- `AgentRun`
- `AgentToolCall`
- `AgentMemoryScope`
- `AgentSupervisionPolicy`
- `AgentReview`
- `AgentIncident`
- `AgentEvaluation`
- `AgentRetirement`

## Canonical domain model

### AgentDefinition

```yaml
AgentDefinition:
  agent_definition_id: string
  organization_id: string
  canonical_name: string
  purpose: string
  owner: ActorReference
  authority_class: ADVISORY | OPERATOR_ASSISTED | TOOL_ACTING | GOVERNED_AUTONOMOUS | HUMAN_REQUIRED
  default_model_profile_id: string | null
  allowed_skill_ids: [string]
  allowed_tool_ids: [string]
  memory_policy_reference: string
  supervision_policy_id: string
  status: DRAFT | REVIEWED | APPROVED | ACTIVE | SUSPENDED | RETIRED
  version: string
  content_hash: string
  created_at: datetime
```

### AgentSession

```yaml
AgentSession:
  agent_session_id: string
  agent_definition_id: string
  agent_version: string
  organization_id: string
  project_id: string | null
  subject_type: string
  subject_id: string
  task_scope: string
  actor_supervisor: ActorReference | null
  policy_decision_id: string
  memory_scope_id: string
  tool_scope_id: string
  status: CREATED | AUTHORIZED | RUNNING | WAITING_REVIEW | COMPLETED | BLOCKED | FAILED | CANCELLED | EXPIRED
  started_at: datetime | null
  expires_at: datetime
  evidence_references: [EvidenceReference]
  correlation_id: string
```

### AgentToolCall

```yaml
AgentToolCall:
  agent_tool_call_id: string
  agent_session_id: string
  tool_id: string
  authorization_decision_id: string
  input_hash: string
  output_hash: string | null
  status: REQUESTED | AUTHORIZED | RUNNING | SUCCEEDED | DENIED | FAILED | TIMED_OUT
  destructive: boolean
  external_side_effect: boolean
  evidence_references: [EvidenceReference]
  called_at: datetime
```

### AgentEvaluation

```yaml
AgentEvaluation:
  agent_evaluation_id: string
  agent_definition_id: string
  agent_version: string
  evaluation_type: SAFETY | QUALITY | TOOL_USE | POLICY_COMPLIANCE | TASK_PERFORMANCE | REGRESSION
  dataset_reference: string | null
  result_reference: string
  verdict: PASS | PASS_WITH_CONDITIONS | FAIL | INCONCLUSIVE
  findings: [string]
  evidence_references: [EvidenceReference]
  evaluated_at: datetime
```

## Lifecycle and invariants

Agent definition lifecycle:

`DRAFT → REVIEWED → APPROVED → ACTIVE → RETIRED`

Alternative states:

- `ACTIVE → SUSPENDED`
- `SUSPENDED → ACTIVE`
- `DRAFT | REVIEWED | APPROVED → RETIRED`

Forbidden transitions:

- `DRAFT → ACTIVE`
- `RETIRED → ACTIVE`
- `SUSPENDED → RETIRED` without review evidence

Core invariants:

- Active agents have approved definitions and supervision policies.
- Every session references one agent definition version.
- Every tool call references one authorization decision.
- Tool calls outside scope are denied and audited.
- Destructive or external-side-effect actions require explicit policy approval.
- Agent memory access is bounded and policy-filtered.
- Agent evaluation failure can suspend activation where policy requires it.

## Commands

Required commands include:

- `CreateAgentDefinition`
- `ReviewAgentDefinition`
- `ApproveAgentDefinition`
- `ActivateAgentDefinition`
- `SuspendAgentDefinition`
- `RetireAgentDefinition`
- `RegisterAgentSkill`
- `GrantAgentTool`
- `RevokeAgentTool`
- `CreateAgentSession`
- `AuthorizeAgentSession`
- `StartAgentSession`
- `CreateAgentTask`
- `RecordAgentRun`
- `AuthorizeAgentToolCall`
- `RecordAgentToolCallResult`
- `RequestAgentReview`
- `ApproveAgentOutput`
- `RejectAgentOutput`
- `CreateAgentIncident`
- `EvaluateAgent`
- `ExpireAgentSession`

Every mutating command includes authenticated actor, organization, agent,
subject, policy decision, expected revision, idempotency key, reason, and
correlation identifier.

## Queries

Required queries include:

- `GetAgentDefinition`
- `ListActiveAgents`
- `GetAgentSession`
- `GetAgentToolCall`
- `ListAgentSessionsBySubject`
- `ListDeniedAgentToolCalls`
- `FindAgentsWithExpiredEvaluations`
- `FindSuspendedAgents`
- `TraceAgentOutputToInputs`
- `TraceAgentToolUse`
- `GetAgentEvaluationHistory`

Queries are policy-filtered and evidence-aware.

## Events

Required events include:

- `AgentDefinitionCreated`
- `AgentDefinitionReviewed`
- `AgentDefinitionApproved`
- `AgentDefinitionActivated`
- `AgentDefinitionSuspended`
- `AgentDefinitionRetired`
- `AgentSkillRegistered`
- `AgentToolGranted`
- `AgentToolRevoked`
- `AgentSessionCreated`
- `AgentSessionAuthorized`
- `AgentSessionStarted`
- `AgentTaskCreated`
- `AgentToolCallAuthorized`
- `AgentToolCallDenied`
- `AgentToolCallCompleted`
- `AgentReviewRequested`
- `AgentOutputApproved`
- `AgentOutputRejected`
- `AgentIncidentCreated`
- `AgentEvaluationCompleted`
- `AgentSessionExpired`

## Security and governance

R14-IR-01 enforces:

- agent identity and version binding;
- delegated authority validation;
- deny-by-default skills and tools;
- least-privilege tool access;
- project and tenant isolation;
- memory and context scoping;
- approval for destructive and external-side-effect actions;
- session expiration;
- evidence capture for tool calls and outputs;
- incident creation for unsafe behavior;
- separation between agent author, operator, reviewer, and approver where
  policy requires it.

## Cross-module contracts

R14-IR-01 integrates with:

- R12-IR policy decisions for authority and tool scope;
- R13-IR AI orchestration operations;
- R11-IR evidence and audit records;
- R10-IR verification and agent evaluation;
- R19 project memory and context boundaries;
- R21 execution orchestration;
- R22 artifact evidence graph.

## Repository implementation mapping

Existing repository evidence includes:

- Agent runtime API:
  `apps/api/src/ai_enterprise/api/routes/agent_runtime.py`
- Agent runtime schemas:
  `apps/api/src/ai_enterprise/api/agent_runtime_schemas.py`
- Agent runtime persistence:
  `apps/api/src/ai_enterprise/application/agent_runtime_persistence_service.py`
- Agent skill and tool domain:
  `apps/api/src/ai_enterprise/domain/agent_runtime/`
- Tool authorization:
  `apps/api/src/ai_enterprise/application/agent_runtime/tool_authorization_service.py`
- Tool gateway:
  `apps/api/src/ai_enterprise/infrastructure/agent_runtime/tools/gateway.py`
- Persistence models:
  `apps/api/src/ai_enterprise/infrastructure/agent_runtime/models.py`
- Tests:
  `apps/api/tests/test_agent_runtime_*.py`

Future implementation should reconcile agent definitions, sessions, tool calls,
reviews, incidents, and evaluations through these existing boundaries.

## Verification strategy

Tests must cover:

- agent lifecycle transitions;
- session authorization and expiry;
- deny-by-default tool behavior;
- delegated authority validation;
- destructive tool approval;
- memory-scope enforcement;
- tool-call evidence capture;
- unsafe output incident creation;
- agent evaluation and suspension;
- cross-project and cross-tenant access denial;
- replay and audit reconstruction.

## Acceptance criteria

R14-IR-01 is implementation-ready when:

- agent definitions, versions, capabilities, sessions, tasks, runs, tool calls,
  reviews, incidents, and evaluations are explicitly modeled;
- every session binds to exact agent version, policy decision, memory scope, and
  tool scope;
- tool use is deny-by-default and audited;
- destructive actions require explicit approval;
- agent output authority is enforced;
- session expiration prevents stale authority;
- agent evidence is recorded through R11-IR-01;
- policy decisions are recorded through R12-IR-01;
- AI/model orchestration is coordinated through R13-IR-01;
- agents cannot create or approve their own authority.

## Readiness verdict

Overall status: IMPLEMENTATION READY.

Repository reconciliation: conditional. Existing agent runtime components
provide a strong baseline; future implementation should consolidate them under
this IR contract without duplicating agent authority.
