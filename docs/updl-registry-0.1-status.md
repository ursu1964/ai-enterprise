# UPDL Registry v0.1 Status

Status: implemented as an executable bootstrap kernel.

Implemented scope:

- Canonical object envelope with API version, metadata, spec, governance,
  provenance, epistemics, lifecycle, and validation status.
- Canonical identifier and namespace validation.
- Namespace registration with parent validation, cycle detection, active-state
  enforcement, and reserved-root protection.
- System-managed revision, timestamps, actor attribution, and content hashes.
- TypeDefinition-backed object creation.
- Deterministic `ValidationResult` output for type-schema validation, including
  machine-readable errors, warnings, property paths, schema version, validation
  timestamp, and validator version.
- Required, enum, primitive, nullable, list, map, and reference property
  validation.
- TypeDefinition `additional_properties` policy with `forbid`, `warn`, and
  `allow` behavior.
- Type-safe reference resolution with structured resolution status.
- Object revisions with optimistic concurrency through `expected_revision`.
- Direct lifecycle/system-field mutation protection on ordinary updates.
- RelationshipType registration with source/target kind validation, versioned
  canonical contract metadata, lifecycle state, symmetric kind validation,
  cardinality semantics, and required evidence declarations.
- Type-safe relationship creation that records canonical relationship identity
  on the source object, resolves evidence references, enforces declared
  cardinality, and rejects source types that explicitly exclude the
  relationship.
- Relationship changes create a new source-object revision and ordinary updates
  preserve existing relationships.
- Relationship creation audit records with relationship contract version,
  source/target revision movement, actor, evidence types, and timestamp.
- SemanticConditionDefinition registration for deterministic reusable
  propositions over object kind, lifecycle state, spec values, and governed
  relationship existence/count.
- Structured ConditionEvaluation results with
  `SATISFIED | NOT_SATISFIED | UNKNOWN | EXEMPTED` outcomes, stable findings,
  explicit proof inputs, and proof hashes.
- ConstraintDefinition registration for governed boundaries over condition
  results, including `MUST_HOLD`, `MUST_NOT_HOLD`, `MUST_REMAIN`,
  `MUST_BECOME`, and `MUST_CEASE` requirements, subject-kind scope, severity,
  status, and condition compatibility validation.
- ConstraintEvaluation results that preserve condition evaluation proof,
  propagate `UNKNOWN`/`EXEMPTED`, distinguish satisfied from violated
  constraints, and create idempotent open ConstraintViolation records with
  immutable constraint id/version, subject reference, severity, proof hash, and
  detection time.
- TaskDefinition registration and TaskInstance runtime support for defined and
  ad-hoc tasks with canonical lifecycle states, assignee, goal reference,
  subject binding, completion condition, allowed actions, inherited constraint
  envelope, dependencies, budget ceiling, declared outputs, and provenance-backed
  output values.
- Governed task lifecycle transitions for `CREATED -> READY -> IN_PROGRESS`,
  blocking, suspension, cancellation, failure, and condition-backed completion;
  task completion is evaluated through a ConditionEvaluation and remains
  separate from parent goal success.
- Task dependency validation with `START_AFTER`, `COMPLETE_AFTER`,
  `REQUIRES_SUCCESS`, `REQUIRES_OUTPUT`, and `REQUIRES_EVIDENCE` semantics,
  including cycle rejection and dependency-satisfaction checks before task start.
- PlanInstance runtime support with goal/planner binding, task graph membership,
  expected outcome reference, validation result, versioned revisions, and
  supersession links so material plan changes do not overwrite prior versions.
- PriorityDefinition, ReservationDefinition, ReservationInstance, and
  PreemptionDefinition support for governed reservation displacement semantics,
  including explicit priority rank/class, reservation preemption mode,
  structural eligibility checks, priority-delta enforcement, optional condition
  evaluation, immutable PreemptionDecision proof records, and atomic transition
  from target `ACTIVE` to `PREEMPTED` with a replacement `ACTIVE` reservation.
- DecisionDefinition registration for explicit governed decisions over a
  resource action, required conditions, selected policies, and a declared
  combining algorithm, with optional constraints, advice, and validity windows.
- Explicit DecisionRequest evaluation that binds request identity, requested
  action, actor, resource, and context into the decision proof.
- Structured DecisionEvaluation results with normalized decision effects,
  domain outcomes, condition evaluations, policy contributions, obligations,
  constraints, advice, evaluation status, validity, findings, proof inputs, and
  proof hashes.
- ObligationDefinition registration for decision-triggered governed duties with
  explicit trigger effect, applicability condition, subject binding, duty,
  responsibility, timing, required evidence, fulfillment condition, breach
  condition, and waiver policy references.
- Idempotent obligation activation from DecisionEvaluation results, preserving
  immutable definition id/version, source decision reference, bound subject,
  assignee, activation key, activation time, due time, and lifecycle state.
- ObligationInstance evidence attachment and fulfillment evaluation with
  required-evidence checks, optional fulfillment condition evaluation, breach
  condition/deadline handling, structured findings, proof inputs, and proof
  hashes.
- StateMachineDefinition registration with applies-to-kind validation, unique
  state validation, initial-state validation, transition endpoint validation,
  terminal-state protection, and version metadata.
- Non-mutating lifecycle transition evaluation with structured denial reasons.
- Governed lifecycle transition execution that requires a declared transition,
  matching source state, optional action binding, expected revision, and creates
  a new object revision with the target lifecycle state.
- Canonical state-transition event records for successful lifecycle changes,
  including event sequence, object revision movement, state-machine version,
  transition identity, actor, action binding, and timestamp.
- State-transition audit records linked to transition events and preserving the
  evaluated decision, previous/new state, previous/new revision, actor, action,
  and state-machine version.
- Policy evaluation with deterministic effect precedence:
  `DENY > ESCALATE > REQUIRE > WARN > ALLOW`.
- Policy obligation accumulation across matched policies.

Intentionally deferred:

- Persistent storage.
- Snapshot materialization.
- Independent relationship-object revisioning, relationship removal, relationship
  lifecycle transitions, inverse materialization, and graph traversal APIs.
- Transition guards, required evidence, transition-specific authorization,
  entry/exit conditions, postconditions, side effects, persistent audit storage,
  external event publication, and idempotency.
- Full invariant language, arbitrary expression evaluation, condition
  composition beyond conjunction, temporal condition semantics, condition audit
  events, and direct policy/state-machine guard integration.
- Full constraint temporal operators, continuous monitoring, constraint-set
  composition, preflight over predicted state trajectories, prohibition-specific
  enforcement reactions, violation resolution workflows, historical constraint
  evaluation, and direct action/plan execution integration.
- Full GoalDefinition/GoalInstance semantics, autonomy envelopes, task
  reassignment/handoff, task evidence dependencies, task audit events, plan
  approval policy, material-change classification, predicted state trajectory
  simulation, plan risk ranking, goal evaluation, subgoal hierarchy, goal
  conflict arbitration, and autonomous execution integration.
- Full semantic consistency/concurrency layer, reservation capacity accounting,
  semantic locks, fencing tokens, conflict sets, preemption impact graphs,
  starvation prevention, compensation workflows, break-glass preemption review,
  and scheduler/runtime integration.
- Full decision domains, decision persistence, decision audit events, human
  approval/escalation, conflict objects, policy applicability records, reusable
  decision snapshots, and action/state/reaction enforcement integration.
- Full obligation lifecycle state-machine integration, obligation persistence,
  obligation audit events, recurrence, suspension, waivers as separate governed
  records, obligation dependency graphs, reassignment, escalation reactions,
  historical obligation evaluation, and action/reaction enforcement integration.
- Full command/event store.
- Authorization adapters.
- Cross-registry reference resolution.

Verification:

```bash
cd apps/api
.venv/bin/pytest -q tests/test_updl_registry_kernel.py
.venv/bin/ruff check src/ai_enterprise/domain/updl_registry.py tests/test_updl_registry_kernel.py
.venv/bin/mypy src/ai_enterprise/domain/updl_registry.py
```
