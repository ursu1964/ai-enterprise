# R12-IR-01 — AI-Enterprise Policy and Governance Engine Specification

Document ID: R12-IR-01  
Version: 1.0.0  
Status: IMPLEMENTATION READY  
Classification: Constitutional Platform Module  
Implementation Target: Future IR/P22 reconciliation  
Primary Dependencies: R2–R11-IR-01

## Purpose

R12-IR-01 defines the Policy and Governance Engine as the constitutional
authority for deciding whether a proposed action, transition, exception,
evidence access, verification waiver, deployment authorization, identity
delegation, or platform evolution is permitted.

It separates policy decision-making from business execution. Other modules ask
R12-IR-01 for governed decisions; they do not embed their own parallel
constitutional authority.

The engine answers:

- who or what is acting;
- under which authority;
- against which subject;
- in which organization, project, environment, and lifecycle state;
- under which policy baseline;
- with which required evidence;
- with which result, conditions, exceptions, or denials.

## Architectural role

R12-IR-01 consumes evidence from R11-IR-01 and produces governed decisions for
all constitutional modules.

It does not author source requirements, execute implementation, store raw
evidence as the evidence authority, or bypass identity controls. It evaluates
policy and records the decision context required for audit.

Existing product-platform R12 remains the implementation/bootstrap runtime
module. This IR specification is a constitutional governance specification and
does not replace that existing R12 module.

## Constitutional requirements

- Every material authorization decision binds to an exact policy baseline.
- A policy decision identifies actor, delegated authority, subject, action,
  scope, environment, evidence inputs, and result.
- Denied decisions are auditable and cannot be silently suppressed.
- Exceptions require authorized approval, justification, risk, scope,
  expiration, compensating controls, and evidence.
- A missing mandatory evidence input fails closed unless a policy explicitly
  permits deferred evidence capture.
- Policy evaluation is deterministic for identical inputs, policy versions, and
  context.
- Policies are versioned, reviewable, testable, and traceable to constitutional
  requirements.
- Emergency and break-glass actions are explicit, time-bounded, high-audit
  events.
- AI may recommend policies, classify risk, explain decisions, and detect
  conflicts. AI cannot grant authority, approve high-risk exceptions, fabricate
  policy evidence, or override deterministic policy evaluation.

## Bounded context

Bounded Context: Policy, Authority, Governance, and Exception Control

Owning Authority: Governance Authority

Primary aggregate root:

- `PolicyBaseline`

Supporting aggregates:

- `PolicyRule`
- `PolicyDecision`
- `AuthorityGrant`
- `DelegatedAuthority`
- `GovernanceControl`
- `PolicyException`
- `RiskAcceptance`
- `CompensatingControl`
- `ApprovalRequirement`
- `SeparationOfDutiesRule`
- `GovernanceReview`
- `PolicyEvaluationContext`
- `PolicyConflict`
- `PolicySimulation`
- `EmergencyAccessSession`
- `GovernanceFinding`

## Canonical domain model

### PolicyBaseline

```yaml
PolicyBaseline:
  policy_baseline_id: string
  organization_id: string
  version: string
  status: DRAFT | REVIEWED | APPROVED | ACTIVE | SUPERSEDED | RETIRED
  policy_rule_ids: [string]
  authority_model_version: string
  evidence_requirements_version: string
  approval_reference: string | null
  content_hash: string
  created_at: datetime
  created_by: ActorReference
```

### PolicyRule

```yaml
PolicyRule:
  policy_rule_id: string
  policy_baseline_id: string
  rule_type: AUTHORIZATION | EVIDENCE_REQUIRED | SEPARATION_OF_DUTIES | RETENTION | DISCLOSURE | WAIVER | DEPLOYMENT | AI_BOUNDARY | EXCEPTION
  subject_types: [string]
  action_types: [string]
  condition_expression: string
  effect: ALLOW | DENY | REQUIRE_APPROVAL | REQUIRE_EVIDENCE | REQUIRE_EXCEPTION | REQUIRE_REVIEW
  criticality: LOW | MEDIUM | HIGH | CRITICAL | CONSTITUTIONAL
  required_evidence_types: [string]
  required_authorities: [string]
  expiry_rule: string | null
  version: string
  content_hash: string
```

### PolicyDecision

```yaml
PolicyDecision:
  policy_decision_id: string
  policy_baseline_id: string
  organization_id: string
  project_id: string | null
  actor: ActorReference
  delegated_authority: ActorReference | null
  subject_type: string
  subject_id: string
  action_type: string
  evaluation_context_hash: string
  matched_rule_ids: [string]
  missing_evidence_types: [string]
  required_approval_ids: [string]
  exception_references: [string]
  result: ALLOWED | DENIED | CONDITIONALLY_ALLOWED | BLOCKED | INCONCLUSIVE
  conditions: [string]
  reason: string
  evidence_references: [EvidenceReference]
  decided_at: datetime
  correlation_id: string
```

### PolicyException

```yaml
PolicyException:
  policy_exception_id: string
  policy_rule_id: string
  subject_scope: object
  reason: string
  risk_assessment: object
  compensating_controls: [string]
  requested_by: ActorReference
  approved_by: ActorReference | null
  valid_from: datetime
  valid_until: datetime
  status: REQUESTED | APPROVED | REJECTED | EXPIRED | REVOKED
  evidence_reference: string
```

## Lifecycle and invariants

Policy baseline lifecycle:

`DRAFT → REVIEWED → APPROVED → ACTIVE → SUPERSEDED → RETIRED`

Forbidden transitions:

- `DRAFT → ACTIVE`
- `RETIRED → ACTIVE`
- `SUPERSEDED → ACTIVE`
- `ACTIVE → DRAFT`

Core invariants:

- Every material decision references one exact active policy baseline.
- Every denial, exception, break-glass action, and policy conflict is auditable.
- Exceptions cannot outlive their validity window.
- Separation-of-duties failures cannot be converted to approval by the same
  actor.
- Policy changes do not rewrite historical decisions.
- Emergency access cannot become normal authority.
- Evidence-access policy and administrator authority remain separable.

## Commands

Required commands include:

- `CreatePolicyBaseline`
- `RegisterPolicyRule`
- `ReviewPolicyBaseline`
- `ApprovePolicyBaseline`
- `ActivatePolicyBaseline`
- `RetirePolicyBaseline`
- `EvaluatePolicy`
- `RecordPolicyDecision`
- `RequestPolicyException`
- `ApprovePolicyException`
- `RejectPolicyException`
- `RevokePolicyException`
- `CreateRiskAcceptance`
- `RegisterCompensatingControl`
- `ValidateSeparationOfDuties`
- `OpenEmergencyAccessSession`
- `CloseEmergencyAccessSession`
- `RunPolicySimulation`
- `DetectPolicyConflict`
- `CreateGovernanceFinding`

Every mutating command includes authenticated actor, organization, subject,
expected aggregate revision, idempotency key, policy context, reason, and
correlation identifier.

## Queries

Required queries include:

- `GetPolicyBaseline`
- `ListActivePolicyRules`
- `GetPolicyDecision`
- `TraceDecisionToPolicy`
- `ListDeniedActions`
- `ListOpenPolicyExceptions`
- `FindExpiredExceptions`
- `FindMissingEvidenceDecisions`
- `FindSeparationOfDutiesViolations`
- `FindEmergencyAccessSessions`
- `ComparePolicyBaselines`
- `GetGovernanceHistory`

Queries are policy-filtered and audited according to classification.

## Events

Required events include:

- `PolicyBaselineCreated`
- `PolicyBaselineReviewed`
- `PolicyBaselineApproved`
- `PolicyBaselineActivated`
- `PolicyBaselineSuperseded`
- `PolicyRuleRegistered`
- `PolicyDecisionRecorded`
- `PolicyDecisionDenied`
- `PolicyExceptionRequested`
- `PolicyExceptionApproved`
- `PolicyExceptionRejected`
- `PolicyExceptionExpired`
- `RiskAcceptanceCreated`
- `CompensatingControlRegistered`
- `SeparationOfDutiesViolationDetected`
- `EmergencyAccessOpened`
- `EmergencyAccessClosed`
- `PolicyConflictDetected`
- `GovernanceFindingCreated`

## Security and governance

R12-IR-01 enforces:

- strong identity and delegated authority validation;
- role, attribute, and policy-based authorization;
- tenant and project isolation;
- separation of duties;
- exception expiry;
- dual control for constitutional and high-risk actions;
- immutable decision audit;
- least-privilege evidence access;
- break-glass governance;
- policy simulation before activation;
- denied-action preservation.

## Cross-module contracts

R12-IR-01 provides decisions to:

- R2 manifest approval and activation;
- R5 requirement baselining and satisfaction;
- R7 planning gates and work acceptance;
- R9 repository operations;
- R10-IR verification waivers and verdict release;
- R11-IR evidence access, disclosure, retention, legal hold, and erasure;
- R16 graph backend operation;
- R18 provider and generator execution;
- R21 orchestration authority;
- R22 artifact promotion and evidence graph policy.

## Repository implementation mapping

Existing repository evidence includes:

- R12 bootstrap governance runtime:
  `apps/api/src/ai_enterprise/application/r12_bootstrap_runtime.py`
- R12 governance API:
  `apps/api/src/ai_enterprise/api/routes/r12_bootstrap.py`
- Architecture governance service:
  `apps/api/src/ai_enterprise/application/architecture_service.py`
- Architecture governance API:
  `apps/api/src/ai_enterprise/api/routes/architecture_governance.py`
- Policy and control-plane tests under `apps/api/tests`.

Future implementation work should extend these existing boundaries and must not
create a second root-level application source tree.

## Verification strategy

Tests must cover:

- policy baseline lifecycle;
- deterministic decision evaluation;
- required evidence failures;
- exception approval and expiry;
- separation-of-duties violations;
- emergency access audit;
- policy conflict detection;
- cross-project access denial;
- historical decision reconstruction;
- AI recommendation non-authority.

## Acceptance criteria

R12-IR-01 is implementation-ready when:

- policy baselines, rules, decisions, exceptions, and authority grants are
  explicitly modeled;
- every material decision binds to an exact policy baseline;
- missing mandatory evidence fails closed;
- denied decisions are auditable;
- exceptions are scoped, approved, expiring, and evidence-backed;
- separation of duties is enforced;
- break-glass sessions are time-bounded and audited;
- policy decisions integrate with R10-IR and R11-IR;
- historical policy decisions remain reconstructable after policy changes;
- AI remains advisory and non-authoritative.

## Readiness verdict

Overall status: IMPLEMENTATION READY.

Repository reconciliation: conditional. Existing governance and R12 bootstrap
components provide a baseline; future implementation should reconcile exact
policy aggregates through the existing architecture.
