# Governed Assurance Control and Decision Contracts

Status: accepted architecture note

Scope: post-R22 semantic contract model, authorized by ADR-0008

## Purpose

This document captures the post-R22 semantic contract layer for controls, authority extensions, and
decisions. It does not create a new R-series module. It defines the terms a future implementation
must preserve when AI-Enterprise reasons about evidence-backed control effectiveness, institutional
authority, and durable enterprise decisions.

The central chain is:

```text
Requirement
-> Control objective
-> Control requirement
-> Control definition
-> Implementation
-> Execution
-> Evidence
-> Effectiveness
-> Authority requirement
-> Decision
-> Effects
-> Observation
-> Review / appeal / supersession
```

The governing principle is:

```text
Declared control != operating control
Operating control != effective control
Approval flag != decision
Technical permission != institutional authority
```

## 5462-5629. Control Contract Model

The Control Contract Model establishes which governed mechanism is intended to ensure, preserve,
detect, correct, recover, or prove an enterprise condition.

A control is not effective because it is documented, configured, assigned, or declared. A control is
effective only when current attributable evidence demonstrates that the governed mechanism operated
as required, covered the required population, and achieved the intended objective.

The model distinguishes:

- `ControlDefinition`: semantic declaration of the control.
- `ControlObjective`: condition or outcome the control protects.
- `ControlRequirement`: what the mechanism must guarantee.
- `ControlApplicability`: population and scope to which the control applies.
- `ControlImplementation`: where and how the control is realized.
- `ControlExecution`: one attributable operation of an implementation.
- `ControlResult`: execution status, evaluation outcome, and enforcement outcome.
- `ControlCoverage`: expected population versus evaluated, passed, failed, unknown, exempt, and missing population.
- `ControlEvidenceRequirement`: evidence schema, attribution, freshness, integrity, and retention.
- `ControlEffectivenessAssessment`: design, operating, coverage, dependency, evidence, and freshness conclusion.
- `ControlTestDefinition` and `ControlTestExecution`: governed assurance procedures and results.
- `ControlException`: explicit, scoped, authorized, bounded deviation from the normal requirement.
- `ControlDeficiency`: known weakness affecting design, operation, evidence, coverage, dependency, or testing.
- `CompensatingControl`: scoped temporary mitigation that reduces residual risk but does not erase the deficiency.
- `ControlMonitoring`: operational telemetry for health, latency, errors, evidence completeness, and coverage.
- `ControlRemediation`: governed correction plan with evidence-backed closure criteria.
- `ControlAttestation`: authorized assertion that may contribute evidence but is not itself effectiveness truth.

Control definitions must keep separate:

```text
DESIGNED != IMPLEMENTED != ENABLED != EXECUTED != PASSED != EFFECTIVE
```

For preventive controls, a subject can fail evaluation while the control operates correctly:

```text
executionStatus = SUCCEEDED
evaluationOutcome = FAIL
enforcementOutcome = BLOCKED
```

For control malfunction:

```text
executionStatus = FAILED
evaluationOutcome = UNKNOWN
enforcementOutcome = BLOCKED or ESCALATED according to failure policy
```

Critical controls should fail closed unless an explicit business-continuity policy authorizes a
bounded alternative. Missing execution is never silently treated as `PASS`. Once applicability and
trigger are established:

```text
required execution + no execution = MISSING
```

Effectiveness is computed truth:

```text
ControlEffective(C, t)
= DesignEffective(C, t)
  and OperatingEffective(C, t)
  and CoverageSufficient(C, t)
  and EvidenceSufficient(C, t)
  and DependenciesSufficient(C, t)
  and no material unresolved deficiency
  and AssessmentFresh(C, t)
```

Control validation should expose errors such as:

- `CONTROL_OBJECTIVE_MISSING`
- `CONTROL_OWNER_MISSING`
- `CONTROL_IMPLEMENTATION_MISSING`
- `CONTROL_APPLICABILITY_MISSING`
- `CONTROL_TRIGGER_MISSING`
- `CONTROL_EVIDENCE_REQUIREMENT_MISSING`
- `CONTROL_EXECUTION_MISSING`
- `CONTROL_EVIDENCE_STALE`
- `CONTROL_BYPASS_DETECTED`
- `CONTROL_COVERAGE_INSUFFICIENT`
- `CONTROL_EFFECTIVENESS_EXPIRED`

AI boundaries:

- AI may explain, inspect, propose, test, or operate controls only when explicitly authorized.
- AI must not infer effectiveness from documentation alone.
- AI must not convert `UNKNOWN`, `NOT_TESTED`, `STALE`, or `MISSING` into green status.
- AI-operated controls must produce the same governed evidence as any other executor.
- Critical controls must not be self-certified by the same AI system that built or operated them.

## 5877-6044. Authority Extensions

The Authority Contract Model must distinguish ordinary approval from formal certification,
attestation, collective authority, independence, emergency authority, break-glass authority, and
authority continuity.

Certification differs from approval:

```text
Approval = authorization to proceed
Certification = formal assertion that criteria have been satisfied
```

Attestation is a governed assertion by an authorized principal. Valid attestation authority does not
make the proposition factually correct.

Collective authority requires:

- quorum definition;
- eligible participants;
- roles held at decision time;
- vote values: `YES`, `NO`, `ABSTAIN`, `RECUSED`, `NOT_PRESENT`;
- voting rule such as `UNANIMOUS`, `SIMPLE_MAJORITY`, `SUPERMAJORITY`, `ROLE_VETO`, or `WEIGHTED`;
- evidence of quorum and outcome.

The system must distinguish:

```text
QuorumSatisfied != DecisionApproved
```

Authority independence is contextual:

```text
Independent(principal, decision, context, time)
```

It is not a permanent attribute of the principal.

Authority extensions include:

- `CertificationAuthority`
- `AttestationAuthority`
- `AuthorityQuorum`
- `AuthorityVotingRule`
- `AuthorityIndependence`
- `ConflictOfInterest`
- `AuthoritySeparationOfDuties`
- `AuthorityThreshold`
- `CompositeAuthorityRequirement`
- `AuthorityVeto`
- `AuthorityOverride`
- `AuthorityJurisdiction`
- `AuthorityMandate`
- `AuthorityResolution`
- `AuthorityDecision`
- `EmergencyAuthority`
- `EmergencyDeclaration`
- `BreakGlassAuthority`
- `AuthorityEscalationPath`
- `AuthorityPrecedence`
- `DecisionRevocation`
- `AuthorityRecertification`
- `AuthorityCoverage`
- `AuthorityContinuityPlan`
- `AuthorityDrift`

Effective authority is:

```text
EffectiveAuthority(P, Cap, S, t)
= ValidSource
  and ValidGrant
  and HolderBinding(P)
  and CapabilityIncludes(Cap)
  and ScopeIncludes(S)
  and TemporalValidity(t)
  and DelegationValidity
  and ConstraintSatisfaction
  and IndependenceSatisfaction
  and ConflictSatisfaction
  and QuorumSatisfaction when applicable
```

AI has no institutional authority by default. Technical capability, model confidence, prior
behavior, or tool access do not create authority. AI principals cannot self-grant, self-expand, or
self-validate critical authority without an independent governed control path.

## 6045-6089. Decision Contract Model

The Decision Contract Model defines what exactly constitutes an enterprise decision.

A decision is not an approval flag. It is a governed conclusion over:

- a defined question;
- a resolvable subject;
- subject version or digest where mutable;
- available options and alternatives;
- evidence set;
- criteria and rules;
- policy, risk, control, and authority context;
- outcome;
- conditions;
- validity interval;
- effect set.

Core primitives:

- `DecisionDefinition`
- `DecisionType`
- `DecisionSubject`
- `DecisionQuestion`
- `DecisionOption`
- `DecisionAlternative`
- `DecisionRequest`
- `DecisionProposal`
- `DecisionInput`
- `DecisionContext`
- `DecisionEvidenceRequirement`
- `DecisionEvidenceSet`
- `DecisionCriterion`
- `DecisionRule`
- `DecisionPolicy`
- `DecisionAuthorityRequirement`
- `DecisionEvaluation`
- `DecisionRecommendation`
- `DecisionOutcome`
- `DecisionApproval`
- `DecisionRejection`
- `DecisionDeferral`
- `DecisionAbstention`
- `DecisionEscalation`
- `DecisionCondition`

The model must preserve:

```text
DecisionRequested != DecisionApproved
Proposal != Decision
Recommendation != Decision
ConditionEvaluation != Decision
Approved != Executed
CorrectOutcome + InvalidAuthority = InvalidDecision
```

Decision conditions must specify when they must hold:

- `AT_DECISION`
- `BEFORE_EXECUTION`
- `DURING_EXECUTION`
- `AFTER_EXECUTION`
- `CONTINUOUSLY`
- `UNTIL_EXPIRY`

## 6090. Decision Reassessment

Decision reassessment occurs when a material input, condition, authority basis, evidence set, risk
state, control state, subject version, or policy context changes after the decision was made.

Reassessment does not rewrite the original decision. It creates a new governed evaluation over the
changed context.

Possible reassessment effects:

- `DECISION_REMAINS_VALID`
- `DECISION_SUSPENDED`
- `DECISION_INVALIDATED`
- `DECISION_REEVALUATION_REQUIRED`
- `DECISION_SUPERSEDED`
- `EXECUTION_BLOCKED`
- `ESCALATION_REQUIRED`

## 6091. Decision Validity

Introduce `DecisionValidity`.

Decision validity determines whether a recorded decision may currently be relied upon.

Example:

```yaml
kind: DecisionValidity
metadata:
  id: decision-validity.release-9187.current
spec:
  decisionRef:
    id: decision.release-9187
  evaluatedAt: 2026-08-08T12:00:00Z
  result: VALID
  checks:
    subjectBinding: PASS
    authority: PASS
    evidenceFreshness: PASS
    conditions: PASS
    policyContext: PASS
    expiry: PASS
```

Validity is distinct from outcome:

```text
DecisionOutcome = APPROVED
DecisionValidity = INVALID
```

is possible when an approval expired, authority was invalidated, or the subject materially changed.

## 6092. Decision Binding

Introduce `DecisionBinding`.

A decision must bind to the exact evaluated material inputs:

- subject identity and version;
- subject digest where available;
- evidence set digest;
- policy version;
- risk assessment version;
- control assessment version;
- authority resolution version;
- decision rule version;
- context snapshot.

The binding prevents an approval for one state from authorizing a materially different state.

## 6093. Decision Expiration

Decisions should declare temporal validity.

Examples:

- deployment approval valid for two hours;
- control exception valid until a timestamp;
- risk acceptance valid until quarter end;
- emergency override valid until incident resolution or maximum duration.

An expired decision cannot support new execution unless a renewal or new decision is made under
governed authority.

## 6094. Decision Supersession

Introduce `DecisionSupersession`.

Supersession records that a later valid decision replaces an earlier decision for future reliance.
It does not delete the earlier decision.

```text
Decision A
-> supersededBy
Decision B
```

The supersession record should identify:

- prior decision;
- new decision;
- authority exercise;
- reason;
- effective time;
- changed evidence or context;
- downstream effects.

## 6095. Decision Revocation

Decision revocation withdraws or invalidates a previous decision.

It requires explicit revocation authority and must preserve:

- revoked decision;
- revoking principal;
- authority exercise;
- reason;
- effective time;
- scope;
- affected executions;
- required notifications or remediation.

Revocation of authority is not the same as revocation of decisions already made.

## 6096. Decision Appeal

Introduce `DecisionAppeal`.

Appeal allows an authorized requester to challenge a decision through a defined path.

Appeal semantics should specify:

- who may appeal;
- allowed grounds;
- deadline;
- required evidence;
- appeal authority;
- whether execution is stayed;
- possible outcomes.

Possible appeal outcomes:

- `UPHELD`
- `OVERTURNED`
- `MODIFIED`
- `REMANDED`
- `DISMISSED`
- `ESCALATED`

## 6097. Decision Review

Introduce `DecisionReview`.

Review assesses whether a decision was valid, appropriate, and evidence-backed.

Reviews may be periodic, event-driven, post-incident, audit-driven, or required by an exception or
emergency authority policy.

Review conclusions must distinguish:

```text
Decision was valid when made
Decision remains valid now
Decision produced desired effects
Decision should be superseded or revoked
```

## 6098. Decision Execution

Introduce `DecisionExecution`.

Decision execution is the downstream action taken because a decision was relied upon.

```text
DecisionApproved != ActionExecuted
```

Execution must validate:

- decision identity;
- validity;
- scope;
- subject binding;
- freshness;
- conditions;
- authority chain;
- control requirements.

## 6099. Decision Effect

Introduce `DecisionEffect`.

Effects define what a valid decision permits, requires, blocks, changes, escalates, or records.

Examples:

- permit deployment;
- block release;
- require remediation;
- accept residual risk;
- create obligation;
- activate exception;
- supersede prior decision;
- trigger notification.

Effects must be explicit so downstream systems do not infer broad permission from a narrow decision.

## 6100. Decision Observation

Introduce `DecisionObservation`.

Observation records what happened after the decision:

- was the decision executed;
- were conditions maintained;
- did expected effects occur;
- did unintended effects occur;
- did evidence arrive late;
- did reassessment become necessary.

Observation closes the feedback loop between decision and enterprise state.

## 6101. Decision Rationale

Introduce `DecisionRationale`.

Rationale is a structured explanation of why the outcome was selected. It should reference:

- decisive criteria;
- material evidence;
- rejected alternatives;
- policy constraints;
- risk and control state;
- authority basis;
- uncertainty and dissent where applicable.

For AI-generated rationale, preserve model identity, version, input evidence, and confidence where
defined. No private chain-of-thought is required; structured decision provenance is sufficient.

## 6102. Decision Record

Introduce `DecisionRecord`.

A DecisionRecord is the durable package containing:

- definition;
- request;
- subject binding;
- evidence set;
- context snapshot;
- evaluation;
- recommendation if any;
- authority validation;
- outcome;
- conditions;
- validity;
- effects;
- rationale;
- audit metadata.

Decision records should be append-only or tamper-evident for material decisions.

## 6103. Decision Audit

Decision audit must answer:

- what was decided;
- who requested it;
- who recommended it;
- who decided it;
- under what authority;
- over what subject version;
- using what evidence;
- against what criteria and policy;
- with what conditions;
- for what validity interval;
- with what downstream effects.

## 6104. Decision Validation Errors

Canonical validation errors include:

- `DECISION_DEFINITION_NOT_FOUND`
- `DECISION_SUBJECT_UNRESOLVED`
- `DECISION_SUBJECT_BINDING_MISSING`
- `DECISION_EVIDENCE_INCOMPLETE`
- `DECISION_EVIDENCE_STALE`
- `DECISION_POLICY_CONFLICT`
- `DECISION_AUTHORITY_REQUIRED`
- `DECISION_AUTHORITY_INVALID`
- `DECISION_CONDITION_UNSATISFIED`
- `DECISION_OUTCOME_NOT_ALLOWED`
- `DECISION_VALIDITY_EXPIRED`
- `DECISION_SUBJECT_CHANGED`
- `DECISION_APPEAL_INVALID`
- `DECISION_SUPERSESSION_INVALID`
- `DECISION_REVOCATION_UNAUTHORIZED`

## 6105. Decision Invariants

`CDEC-001` Every material decision must identify a DecisionDefinition.

`CDEC-002` A decision must answer an explicit question.

`CDEC-003` A decision must bind to a resolvable subject.

`CDEC-004` Mutable subjects require version or digest binding.

`CDEC-005` A request is not a decision.

`CDEC-006` A recommendation is not a decision.

`CDEC-007` An approval flag is not a decision record.

`CDEC-008` Decision evidence must be explicit and attributable.

`CDEC-009` Missing evidence must follow defined semantics.

`CDEC-010` Mandatory criteria cannot be ignored by convenience workflow.

`CDEC-011` Authority is required for institutional validity.

`CDEC-012` Decision conditions must declare timing.

`CDEC-013` Decision validity is distinct from decision outcome.

`CDEC-014` Expired decisions cannot authorize new execution.

`CDEC-015` Subject material change requires reassessment according to policy.

`CDEC-016` Supersession and revocation preserve history.

`CDEC-017` Appeals and reviews are governed records, not edits.

`CDEC-018` Downstream execution must validate the decision it relies on.

`CDEC-019` AI recommendations must not masquerade as authorized decisions.

`CDEC-020` Every material decision must be historically reconstructible.

## 6106. Strong Decision Invariant

No material enterprise decision may be represented only as a mutable status field, approval flag, or
unstructured comment. Every material decision must preserve a governed record of the question,
subject, alternatives, evidence, criteria, policies, risk and control context, authority, outcome,
conditions, validity, effects, rationale, and audit provenance.

## 6107. Architectural Result

With Control, Authority, and Decision contracts together, AI-Enterprise can answer:

```text
What had to be true?
Which mechanism was supposed to ensure it?
Did that mechanism operate?
Was evidence sufficient?
Who had authority to decide?
What exactly was decided?
Can downstream execution validly rely on that decision now?
What happened after reliance?
```

This turns approval workflow state into a governed assurance graph.
