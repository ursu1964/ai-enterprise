from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from ai_enterprise.application.r15_manifest_compiler_runtime import r15_compile_manifest
from ai_enterprise.application.r16_knowledge_graph_runtime import r16_load_graph
from ai_enterprise.application.r17_execution_planner_runtime import r17_create_execution_plan
from ai_enterprise.domain.specification.kernel import specification_hash

EXECUTION_ORCHESTRATOR_VERSION = "execution-orchestrator-1.0"
DETERMINISTIC_ORCHESTRATION_TIMESTAMP = "1970-01-01T00:00:00Z"

PROJECT_STATES: tuple[str, ...] = (
    "DRAFT",
    "VALIDATING",
    "REJECTED",
    "COMPILED",
    "PLANNED",
    "AWAITING_AUTHORIZATION",
    "EXECUTING",
    "PAUSED",
    "BLOCKED",
    "FAILED",
    "VALIDATING_OUTPUT",
    "REMEDIATION_REQUIRED",
    "AWAITING_ACCEPTANCE",
    "REJECTED_OUTPUT",
    "COMPLETED",
    "ARCHIVED",
)

WORK_PACKAGE_STATES: tuple[str, ...] = (
    "PENDING",
    "READY",
    "QUEUED",
    "RUNNING",
    "WAITING_FOR_INPUT",
    "WAITING_FOR_APPROVAL",
    "VALIDATING",
    "RETRY_SCHEDULED",
    "BLOCKED",
    "FAILED",
    "CANCELLED",
    "COMPLETED",
    "SUPERSEDED",
)

ARTIFACT_PROMOTION_LEVELS: tuple[str, ...] = (
    "GENERATED",
    "SCHEMA_VALIDATED",
    "TECHNICALLY_VALIDATED",
    "POLICY_VALIDATED",
    "REVIEWED",
    "APPROVED",
    "RELEASE_CANDIDATE",
    "RELEASED",
)

WORKER_TYPES: tuple[str, ...] = (
    "requirements_compiler",
    "api_contract_worker",
    "backend_implementation_worker",
    "test_generation_worker",
    "container_worker",
    "build_validation_worker",
    "approval_coordinator",
    "delivery_packager",
)


class R21Diagnostic(BaseModel):
    model_config = ConfigDict(frozen=True)

    severity: str
    category: str
    code: str
    message: str
    path: str


class R21TraceSource(BaseModel):
    model_config = ConfigDict(frozen=True)

    object_id: str
    object_type: str
    relationship: str


class R21ManifestTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    manifest_version: str
    source_objects: tuple[R21TraceSource, ...]
    trace_hash: str


class R21WorkPackagePermissions(BaseModel):
    model_config = ConfigDict(frozen=True)

    tools: tuple[str, ...]
    repositories: tuple[str, ...]
    network_access: str
    destructive_operations: str


class R21ExpectedOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_type: str
    schema_uri: str


class R21WorkPackage(BaseModel):
    model_config = ConfigDict(frozen=True)

    work_package_id: str
    project_id: str
    version: int
    title: str
    purpose: str
    manifest_trace: R21ManifestTrace
    requires: tuple[str, ...]
    required_by: tuple[str, ...]
    worker_type: str
    execution_mode: str
    priority: int
    timeout_seconds: int
    maximum_attempts: int
    permissions: R21WorkPackagePermissions
    inputs: tuple[str, ...]
    expected_outputs: tuple[R21ExpectedOutput, ...]
    validators: tuple[str, ...]
    completion_criteria: dict[str, Any]
    required_approvals: tuple[str, ...]
    idempotency_key: str
    package_hash: str


class R21ExecutionPhase(BaseModel):
    model_config = ConfigDict(frozen=True)

    phase_id: str
    name: str
    work_package_ids: tuple[str, ...]
    phase_hash: str


class R21ApprovalRequirement(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: str
    minimum_approvals: int


class R21ApprovalDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_id: str
    gate_id: str
    decision: str
    actor_role: str
    actor_id: str
    bound_artifact_hashes: tuple[str, ...]
    decided_at: str
    decision_hash: str


class R21ApprovalGate(BaseModel):
    model_config = ConfigDict(frozen=True)

    gate_id: str
    project_id: str
    gate_type: str
    occurs_before: str
    subject_work_package_ids: tuple[str, ...]
    required_approvers: tuple[R21ApprovalRequirement, ...]
    evidence_required: tuple[str, ...]
    decisions: tuple[R21ApprovalDecision, ...]
    status: str
    gate_hash: str


class R21ExecutionPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    execution_plan_id: str
    project_id: str
    manifest_hash: str
    manifest_version: str
    registry_snapshot: str
    policy_snapshot: str
    orchestrator_version: str
    strategy: dict[str, Any]
    phases: tuple[R21ExecutionPhase, ...]
    work_packages: tuple[R21WorkPackage, ...]
    approval_gates: tuple[R21ApprovalGate, ...]
    dependency_edges: tuple[dict[str, str], ...]
    parallel_groups: tuple[tuple[str, ...], ...]
    diagnostics: tuple[R21Diagnostic, ...]
    plan_hash: str


class R21ProjectCompilation(BaseModel):
    model_config = ConfigDict(frozen=True)

    compilation_id: str
    project_id: str
    manifest_hash: str
    manifest_version: str
    schema_valid: bool
    compiler_result_hash: str | None
    graph_hash: str | None
    r17_plan_hash: str | None
    compiled_model: dict[str, Any]
    diagnostics: tuple[R21Diagnostic, ...]
    status: str
    compilation_hash: str


class R21WorkerRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: str
    execution_id: str
    work_package_id: str
    worker_type: str
    worker_version: str
    instructions: dict[str, Any]
    context: dict[str, Any]
    output_contract: dict[str, Any]
    authorization: dict[str, Any]
    request_hash: str


class R21ArtifactVersion(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: str
    work_package_id: str
    artifact_type: str
    version: int
    uri: str
    checksum: str
    promotion_level: str
    manifest_trace_hash: str
    provenance_hash: str
    artifact_hash: str


class R21ValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    validation_id: str
    work_package_id: str
    artifact_ids: tuple[str, ...]
    validators: tuple[str, ...]
    passed: bool
    findings: tuple[dict[str, str], ...]
    validation_hash: str


class R21EvidenceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    entity_type: str
    entity_id: str
    evidence_type: str
    uri: str
    checksum: str
    evidence_hash: str


class R21ExecutionEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    event_type: str
    event_version: int
    occurred_at: str
    project_id: str
    execution_id: str
    correlation_id: str
    causation_id: str | None
    actor: dict[str, str]
    subject: dict[str, str]
    payload: dict[str, Any]
    checksum: str


class R21StateTransition(BaseModel):
    model_config = ConfigDict(frozen=True)

    transition_id: str
    entity_id: str
    entity_type: str
    from_state: str | None
    to_state: str
    triggered_by: dict[str, str]
    event_type: str
    occurred_at: str
    correlation_id: str
    evidence: tuple[str, ...]
    transition_hash: str


class R21WorkPackageRuntimeState(BaseModel):
    model_config = ConfigDict(frozen=True)

    work_package_id: str
    state: str
    attempt: int
    lease_id: str | None
    retry_reason: str | None
    state_hash: str


class R21RetryRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    work_package_id: str
    attempt: int
    maximum_attempts: int
    retry_reason: str
    previous_execution_id: str
    scheduled_at: str
    backoff_seconds: int
    retry_hash: str


class R21Contradiction(BaseModel):
    model_config = ConfigDict(frozen=True)

    contradiction_id: str
    severity: str
    status: str
    sources: tuple[dict[str, str], ...]
    affected_work_packages: tuple[str, ...]
    required_role: str
    allowed_actions: tuple[str, ...]
    contradiction_hash: str


class R21Checkpoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    checkpoint_id: str
    execution_id: str
    created_at: str
    project_state: str
    manifest_hash: str
    completed_work_packages: tuple[str, ...]
    running_work_packages: tuple[str, ...]
    blocked_work_packages: tuple[str, ...]
    pending_approvals: tuple[str, ...]
    produced_artifacts: tuple[str, ...]
    retry_counters: dict[str, int]
    scheduler_state: dict[str, Any]
    last_event_sequence: int
    checkpoint_hash: str


class R21DeliveryPackage(BaseModel):
    model_config = ConfigDict(frozen=True)

    package_id: str
    project_id: str
    execution_id: str
    artifact_ids: tuple[str, ...]
    validation_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    traceability_hash: str
    provenance_hash: str
    delivery_status: str
    package_hash: str


class R21Execution(BaseModel):
    model_config = ConfigDict(frozen=True)

    execution_id: str
    project_id: str
    execution_plan_id: str
    project_state: str
    work_package_states: tuple[R21WorkPackageRuntimeState, ...]
    worker_requests: tuple[R21WorkerRequest, ...]
    artifacts: tuple[R21ArtifactVersion, ...]
    validations: tuple[R21ValidationResult, ...]
    evidence: tuple[R21EvidenceRecord, ...]
    approval_gates: tuple[R21ApprovalGate, ...]
    retries: tuple[R21RetryRecord, ...]
    contradictions: tuple[R21Contradiction, ...]
    events: tuple[R21ExecutionEvent, ...]
    transitions: tuple[R21StateTransition, ...]
    checkpoints: tuple[R21Checkpoint, ...]
    delivery_package: R21DeliveryPackage | None
    diagnostics: tuple[R21Diagnostic, ...]
    execution_hash: str


class R21ImpactAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    impact_class: str
    changed_manifest_hash: str
    affected_work_package_ids: tuple[str, ...]
    invalidated_artifact_ids: tuple[str, ...]
    invalidated_gate_ids: tuple[str, ...]
    plan_regeneration_required: bool
    analysis_hash: str


def r21_compile_project(
    manifest: dict[str, Any],
    schema_path: Path,
    registry_root: Path,
) -> R21ProjectCompilation:
    manifest_hash = specification_hash(manifest)
    project_id = str(manifest.get("metadata", {}).get("id", "unknown-project"))
    manifest_version = str(manifest.get("version", {}).get("manifestVersion", "0.0.0"))
    compilation = r15_compile_manifest(manifest, schema_path, registry_root)
    diagnostics = tuple(
        R21Diagnostic(
            severity="fatal" if item.severity in {"error", "fatal"} else item.severity,
            category=item.category,
            code=item.code,
            message=item.message,
            path=item.path,
        )
        for item in compilation.diagnostics
    )
    graph_hash: str | None = None
    r17_plan_hash: str | None = None
    compiled_model: dict[str, Any] = {}
    if compilation.success_status and compilation.knowledge_graph is not None:
        graph = r16_load_graph(
            compilation.knowledge_graph.model_dump(mode="json"),
            compilation_report=compilation.compilation_report.model_dump(mode="json"),
            registry_root=registry_root,
        )
        plan = r17_create_execution_plan(graph.model_dump(mode="json"))
        graph_hash = graph.graph_hash
        r17_plan_hash = plan.plan_hash
        compiled_model = _compiled_model(
            manifest, compilation.result_hash, graph_hash, plan.plan_hash
        )
    status = "COMPILED" if compilation.success_status and not diagnostics else "REJECTED"
    payload = {
        "project_id": project_id,
        "manifest_hash": manifest_hash,
        "manifest_version": manifest_version,
        "schema_valid": compilation.success_status,
        "compiler_result_hash": compilation.result_hash,
        "graph_hash": graph_hash,
        "r17_plan_hash": r17_plan_hash,
        "compiled_model": compiled_model,
        "diagnostics": [item.model_dump(mode="json") for item in diagnostics],
        "status": status,
    }
    return R21ProjectCompilation(
        compilation_id=f"r21-compilation-{manifest_hash[:16]}",
        compilation_hash=specification_hash(payload),
        **payload,
    )


def r21_create_execution_plan(
    manifest: dict[str, Any],
    compilation: dict[str, Any] | R21ProjectCompilation,
) -> R21ExecutionPlan:
    compiled = _coerce_compilation(compilation)
    diagnostics: tuple[R21Diagnostic, ...] = compiled.diagnostics
    if compiled.status != "COMPILED":
        diagnostics = (
            *diagnostics,
            _diag("fatal", "manifest", "R21-MANIFEST-NOT-COMPILED", compiled.project_id),
        )
    work_packages = _work_packages(manifest, compiled)
    contradictions = _detect_manifest_contradictions(manifest, work_packages)
    if contradictions:
        diagnostics = (
            *diagnostics,
            _diag("fatal", "contradiction", "R21-CONTRADICTION-UNRESOLVED", compiled.project_id),
        )
    phases = _phases(work_packages)
    gates = (_approval_gate(compiled.project_id, work_packages),)
    dependency_edges = tuple(
        {"source": source, "target": package.work_package_id, "reason": "requires"}
        for package in work_packages
        for source in package.requires
    )
    strategy = {
        "execution_mode": "controlled_parallel",
        "optimization_target": "balanced",
        "maximum_parallel_tasks": 3,
        "failure_policy": "pause_affected_branch",
        "approval_policy": "explicit",
    }
    payload = {
        "project_id": compiled.project_id,
        "manifest_hash": compiled.manifest_hash,
        "manifest_version": compiled.manifest_version,
        "registry_snapshot": compiled.compiled_model.get("registry_version", "unknown"),
        "policy_snapshot": "r21.default.policy",
        "orchestrator_version": EXECUTION_ORCHESTRATOR_VERSION,
        "strategy": strategy,
        "phases": [item.model_dump(mode="json") for item in phases],
        "work_packages": [item.model_dump(mode="json") for item in work_packages],
        "approval_gates": [item.model_dump(mode="json") for item in gates],
        "dependency_edges": dependency_edges,
        "parallel_groups": _parallel_groups(work_packages),
        "diagnostics": [item.model_dump(mode="json") for item in diagnostics],
    }
    return R21ExecutionPlan(
        execution_plan_id=f"r21-plan-{compiled.project_id}-{compiled.manifest_version}",
        plan_hash=specification_hash(payload),
        **payload,
    )


def r21_start_execution(
    plan: dict[str, Any] | R21ExecutionPlan,
    *,
    options: dict[str, Any] | None = None,
) -> R21Execution:
    execution_plan = _coerce_plan(plan)
    opts = options or {}
    execution_id = str(opts.get("execution_id", f"r21-exec-{execution_plan.plan_hash[:16]}"))
    if execution_plan.diagnostics:
        return _initial_execution(
            execution_plan, execution_id, "BLOCKED", execution_plan.diagnostics
        )
    states = {
        package.work_package_id: _wp_state(package.work_package_id, "PENDING", 0, None, None)
        for package in execution_plan.work_packages
    }
    return _run_until_blocked_or_complete(
        execution_plan,
        _initial_execution(execution_plan, execution_id, "EXECUTING", ()),
        states,
        options=opts,
    )


def r21_apply_approval(
    execution: dict[str, Any] | R21Execution,
    *,
    gate_id: str,
    decision: str,
    actor_role: str,
    actor_id: str,
) -> R21Execution:
    current = _coerce_execution(execution)
    gate = next((item for item in current.approval_gates if item.gate_id == gate_id), None)
    if gate is None:
        return _with_diagnostic(current, "fatal", "approval", "R21-APPROVAL-GATE-MISSING", gate_id)
    required_roles = {item.role for item in gate.required_approvers}
    if actor_role not in required_roles:
        return _with_diagnostic(
            current, "fatal", "approval", "R21-APPROVER-ROLE-DENIED", actor_role
        )
    bound_hashes = tuple(
        artifact.artifact_hash
        for artifact in current.artifacts
        if artifact.work_package_id in gate.subject_work_package_ids
    )
    if decision not in {"approve", "approve_with_conditions", "reject", "request_revision"}:
        return _with_diagnostic(
            current, "fatal", "approval", "R21-APPROVAL-DECISION-INVALID", decision
        )
    approval = _approval_decision(gate_id, decision, actor_role, actor_id, bound_hashes)
    updated_gate = _gate_with_decision(gate, approval, decision)
    gate_status = updated_gate.status
    gates = tuple(
        updated_gate if item.gate_id == gate_id else item for item in current.approval_gates
    )
    event_type = "approval.granted" if gate_status == "approved" else "approval.rejected"
    event = _event(
        execution_id=current.execution_id,
        project_id=current.project_id,
        event_type=event_type,
        causation_id=current.events[-1].event_id if current.events else None,
        subject_type="approval_gate",
        subject_id=gate_id,
        payload={
            "decision": decision,
            "actor_role": actor_role,
            "bound_artifact_hashes": bound_hashes,
        },
    )
    transition = _transition(
        entity_id=current.execution_id,
        entity_type="project_execution",
        from_state=current.project_state,
        to_state="EXECUTING" if gate_status == "approved" else current.project_state,
        event_type=event_type,
        correlation_id=current.execution_id,
        evidence=bound_hashes,
        actor_type="human",
        actor_id=actor_id,
    )
    return _execution(
        current,
        project_state=(
            "EXECUTING"
            if gate_status == "approved"
            else "REJECTED_OUTPUT"
            if gate_status == "rejected"
            else current.project_state
        ),
        approval_gates=gates,
        events=(*current.events, event),
        transitions=(*current.transitions, transition),
        checkpoints=(
            *current.checkpoints,
            _checkpoint(
                current,
                "EXECUTING" if gate_status == "approved" else current.project_state,
                gates=gates,
            ),
        ),
    )


def r21_resume_execution(
    plan: dict[str, Any] | R21ExecutionPlan,
    execution: dict[str, Any] | R21Execution,
    *,
    options: dict[str, Any] | None = None,
) -> R21Execution:
    execution_plan = _coerce_plan(plan)
    current = _coerce_execution(execution)
    if current.project_state not in {"EXECUTING", "PAUSED", "AWAITING_AUTHORIZATION"}:
        return current
    states = {item.work_package_id: item for item in current.work_package_states}
    return _run_until_blocked_or_complete(execution_plan, current, states, options=options or {})


def r21_pause_execution(execution: dict[str, Any] | R21Execution, reason: str) -> R21Execution:
    current = _coerce_execution(execution)
    event = _event(
        execution_id=current.execution_id,
        project_id=current.project_id,
        event_type="execution.paused",
        causation_id=current.events[-1].event_id if current.events else None,
        subject_type="execution",
        subject_id=current.execution_id,
        payload={"reason": reason},
    )
    return _execution(
        current,
        project_state="PAUSED",
        events=(*current.events, event),
        checkpoints=(*current.checkpoints, _checkpoint(current, "PAUSED")),
    )


def r21_cancel_execution(
    execution: dict[str, Any] | R21Execution,
    *,
    reason: str,
    actor_id: str = "api",
) -> R21Execution:
    current = _coerce_execution(execution)
    cancelled_states = tuple(
        _wp_state(item.work_package_id, "CANCELLED", item.attempt, None, reason)
        if item.state not in {"COMPLETED", "CANCELLED", "SUPERSEDED"}
        else item
        for item in current.work_package_states
    )
    event = _event(
        execution_id=current.execution_id,
        project_id=current.project_id,
        event_type="execution.cancelled",
        causation_id=current.events[-1].event_id if current.events else None,
        subject_type="execution",
        subject_id=current.execution_id,
        payload={"reason": reason},
    )
    transition = _transition(
        entity_id=current.execution_id,
        entity_type="project_execution",
        from_state=current.project_state,
        to_state="FAILED",
        event_type="execution.cancelled",
        correlation_id=current.execution_id,
        evidence=(),
        actor_type="human",
        actor_id=actor_id,
    )
    return _execution(
        current,
        project_state="FAILED",
        work_package_states=cancelled_states,
        events=(*current.events, event),
        transitions=(*current.transitions, transition),
        checkpoints=(
            *current.checkpoints,
            _checkpoint(current, "FAILED", work_package_states=cancelled_states),
        ),
    )


def r21_retry_work_package(
    execution: dict[str, Any] | R21Execution,
    *,
    work_package_id: str,
    reason: str = "operator-retry",
    actor_id: str = "api",
) -> R21Execution:
    current = _coerce_execution(execution)
    return _mutate_work_package_state(
        current,
        work_package_id=work_package_id,
        target_state="PENDING",
        event_type="work_package.retry_scheduled",
        reason=reason,
        actor_id=actor_id,
        allowed_current_states={"RETRY_SCHEDULED", "FAILED", "BLOCKED"},
        project_state="EXECUTING",
    )


def r21_cancel_work_package(
    execution: dict[str, Any] | R21Execution,
    *,
    work_package_id: str,
    reason: str = "operator-cancel",
    actor_id: str = "api",
) -> R21Execution:
    current = _coerce_execution(execution)
    return _mutate_work_package_state(
        current,
        work_package_id=work_package_id,
        target_state="CANCELLED",
        event_type="work_package.cancelled",
        reason=reason,
        actor_id=actor_id,
        allowed_current_states=set(WORK_PACKAGE_STATES) - {"COMPLETED", "SUPERSEDED"},
        project_state="BLOCKED",
    )


def r21_remediate_work_package(
    execution: dict[str, Any] | R21Execution,
    *,
    work_package_id: str,
    reason: str = "operator-remediation",
    actor_id: str = "api",
) -> R21Execution:
    current = _coerce_execution(execution)
    return _mutate_work_package_state(
        current,
        work_package_id=work_package_id,
        target_state="PENDING",
        event_type="work_package.remediation_requested",
        reason=reason,
        actor_id=actor_id,
        allowed_current_states={"FAILED", "BLOCKED", "RETRY_SCHEDULED", "CANCELLED"},
        project_state="EXECUTING",
    )


def r21_recover_execution(checkpoint: dict[str, Any] | R21Checkpoint) -> dict[str, Any]:
    current = (
        checkpoint
        if isinstance(checkpoint, R21Checkpoint)
        else R21Checkpoint.model_validate(checkpoint)
    )
    return {
        "execution_id": current.execution_id,
        "project_state": current.project_state,
        "completed_work_packages": list(current.completed_work_packages),
        "blocked_work_packages": list(current.blocked_work_packages),
        "pending_approvals": list(current.pending_approvals),
        "produced_artifacts": list(current.produced_artifacts),
        "last_event_sequence": current.last_event_sequence,
        "recovery_hash": specification_hash(current.model_dump(mode="json")),
    }


def r21_analyze_manifest_change(
    previous_manifest: dict[str, Any],
    current_manifest: dict[str, Any],
    plan: dict[str, Any] | R21ExecutionPlan,
    execution: dict[str, Any] | R21Execution,
) -> R21ImpactAnalysis:
    execution_plan = _coerce_plan(plan)
    current_execution = _coerce_execution(execution)
    previous_hash = specification_hash(previous_manifest)
    current_hash = specification_hash(current_manifest)
    changed_ids = _changed_manifest_object_ids(previous_manifest, current_manifest)
    affected = tuple(
        package.work_package_id
        for package in execution_plan.work_packages
        if any(source.object_id in changed_ids for source in package.manifest_trace.source_objects)
    )
    invalidated_artifacts = tuple(
        artifact.artifact_id
        for artifact in current_execution.artifacts
        if artifact.work_package_id in affected
    )
    invalidated_gates = tuple(
        gate.gate_id
        for gate in current_execution.approval_gates
        if any(work_package_id in affected for work_package_id in gate.subject_work_package_ids)
    )
    impact_class = (
        "NONE" if previous_hash == current_hash else "LOCAL" if affected else "DOCUMENTATION_ONLY"
    )
    payload = {
        "impact_class": impact_class,
        "changed_manifest_hash": current_hash,
        "affected_work_package_ids": affected,
        "invalidated_artifact_ids": invalidated_artifacts,
        "invalidated_gate_ids": invalidated_gates,
        "plan_regeneration_required": impact_class not in {"NONE", "DOCUMENTATION_ONLY"},
    }
    return R21ImpactAnalysis(**payload, analysis_hash=specification_hash(payload))


def r21_write_execution(execution: dict[str, Any] | R21Execution, path: Path) -> str:
    current = _coerce_execution(execution)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(current.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return current.execution_hash


def r21_write_compilation(
    compilation: dict[str, Any] | R21ProjectCompilation,
    path: Path,
) -> str:
    current = _coerce_compilation(compilation)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(current.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return current.compilation_hash


def r21_read_compilation(path: Path) -> R21ProjectCompilation | None:
    if not path.exists():
        return None
    return R21ProjectCompilation.model_validate(json.loads(path.read_text(encoding="utf-8")))


def r21_write_execution_plan(
    plan: dict[str, Any] | R21ExecutionPlan,
    path: Path,
) -> str:
    current = _coerce_plan(plan)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(current.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return current.plan_hash


def r21_read_execution_plan(path: Path) -> R21ExecutionPlan | None:
    if not path.exists():
        return None
    return R21ExecutionPlan.model_validate(json.loads(path.read_text(encoding="utf-8")))


def r21_read_execution(path: Path) -> R21Execution | None:
    if not path.exists():
        return None
    return R21Execution.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _run_until_blocked_or_complete(
    plan: R21ExecutionPlan,
    execution: R21Execution,
    states: dict[str, R21WorkPackageRuntimeState],
    *,
    options: dict[str, Any],
) -> R21Execution:
    current = execution
    validation_failures = set(
        str(item) for item in options.get("validation_fail_work_package_ids", ())
    )
    prohibited_tools = set(str(item) for item in options.get("prohibited_tool_attempts", ()))
    progress = True
    while progress:
        progress = False
        for package in sorted(
            plan.work_packages, key=lambda item: (item.priority, item.work_package_id)
        ):
            state = states[package.work_package_id]
            if state.state in {"COMPLETED", "BLOCKED", "FAILED", "RETRY_SCHEDULED"}:
                continue
            if not all(states[dependency].state == "COMPLETED" for dependency in package.requires):
                continue
            if package.required_approvals and not _approval_satisfied(
                current, package.required_approvals
            ):
                states[package.work_package_id] = _wp_state(
                    package.work_package_id, "WAITING_FOR_APPROVAL", state.attempt, None, None
                )
                current = _request_approval(current, package)
                return _execution(
                    current,
                    project_state="AWAITING_AUTHORIZATION",
                    work_package_states=tuple(states.values()),
                    checkpoints=(
                        *current.checkpoints,
                        _checkpoint(
                            current,
                            "AWAITING_AUTHORIZATION",
                            work_package_states=tuple(states.values()),
                        ),
                    ),
                )
            if prohibited_tools & set(package.permissions.tools):
                states[package.work_package_id] = _wp_state(
                    package.work_package_id, "BLOCKED", state.attempt, None, "policy_violation"
                )
                current = _blocked(
                    current, package, "R21-POLICY-VIOLATION", "policy.violation.detected"
                )
                return _execution(
                    current,
                    project_state="BLOCKED",
                    work_package_states=tuple(states.values()),
                    checkpoints=(
                        *current.checkpoints,
                        _checkpoint(current, "BLOCKED", work_package_states=tuple(states.values())),
                    ),
                )
            if package.work_package_id in validation_failures:
                attempt = state.attempt + 1
                next_state = "RETRY_SCHEDULED" if attempt < package.maximum_attempts else "FAILED"
                states[package.work_package_id] = _wp_state(
                    package.work_package_id, next_state, attempt, None, "validation_failed"
                )
                current = _validation_failed(current, package, attempt, next_state)
                return _execution(
                    current,
                    project_state="REMEDIATION_REQUIRED" if next_state == "FAILED" else "BLOCKED",
                    work_package_states=tuple(states.values()),
                    checkpoints=(
                        *current.checkpoints,
                        _checkpoint(current, "BLOCKED", work_package_states=tuple(states.values())),
                    ),
                )
            states[package.work_package_id] = _wp_state(
                package.work_package_id, "COMPLETED", state.attempt + 1, None, None
            )
            current = _complete_package(current, package)
            progress = True
    if all(item.state == "COMPLETED" for item in states.values()):
        delivery = _delivery_package(current)
        event = _event(
            execution_id=current.execution_id,
            project_id=current.project_id,
            event_type="execution.completed",
            causation_id=current.events[-1].event_id if current.events else None,
            subject_type="execution",
            subject_id=current.execution_id,
            payload={"delivery_package_id": delivery.package_id},
        )
        return _execution(
            current,
            project_state="COMPLETED",
            work_package_states=tuple(states.values()),
            delivery_package=delivery,
            events=(*current.events, event),
            checkpoints=(
                *current.checkpoints,
                _checkpoint(current, "COMPLETED", work_package_states=tuple(states.values())),
            ),
        )
    return _execution(current, work_package_states=tuple(states.values()))


def _mutate_work_package_state(
    execution: R21Execution,
    *,
    work_package_id: str,
    target_state: str,
    event_type: str,
    reason: str,
    actor_id: str,
    allowed_current_states: set[str],
    project_state: str,
) -> R21Execution:
    current_state = next(
        (item for item in execution.work_package_states if item.work_package_id == work_package_id),
        None,
    )
    if current_state is None:
        return _with_diagnostic(
            execution,
            "fatal",
            "work_package",
            "R21-WORK-PACKAGE-MISSING",
            work_package_id,
        )
    if current_state.state not in allowed_current_states:
        return _with_diagnostic(
            execution,
            "fatal",
            "work_package",
            "R21-WORK-PACKAGE-TRANSITION-DENIED",
            work_package_id,
        )
    mutated_state = _wp_state(
        work_package_id,
        target_state,
        current_state.attempt,
        None,
        None if target_state == "PENDING" else reason,
    )
    states = tuple(
        mutated_state if item.work_package_id == work_package_id else item
        for item in execution.work_package_states
    )
    event = _event(
        execution_id=execution.execution_id,
        project_id=execution.project_id,
        event_type=event_type,
        causation_id=execution.events[-1].event_id if execution.events else None,
        subject_type="work_package",
        subject_id=work_package_id,
        payload={"reason": reason, "from_state": current_state.state, "to_state": target_state},
    )
    transition = _transition(
        entity_id=work_package_id,
        entity_type="work_package",
        from_state=current_state.state,
        to_state=target_state,
        event_type=event_type,
        correlation_id=execution.execution_id,
        evidence=(),
        actor_type="human",
        actor_id=actor_id,
    )
    return _execution(
        execution,
        project_state=project_state,
        work_package_states=states,
        events=(*execution.events, event),
        transitions=(*execution.transitions, transition),
        checkpoints=(
            *execution.checkpoints,
            _checkpoint(execution, project_state, work_package_states=states),
        ),
    )


def _initial_execution(
    plan: R21ExecutionPlan,
    execution_id: str,
    state: str,
    diagnostics: tuple[R21Diagnostic, ...],
) -> R21Execution:
    states = tuple(
        _wp_state(item.work_package_id, "PENDING", 0, None, None) for item in plan.work_packages
    )
    event = _event(
        execution_id=execution_id,
        project_id=plan.project_id,
        event_type="execution.started" if state == "EXECUTING" else "execution.blocked",
        causation_id=None,
        subject_type="execution",
        subject_id=execution_id,
        payload={"execution_plan_id": plan.execution_plan_id},
    )
    payload = {
        "execution_id": execution_id,
        "project_id": plan.project_id,
        "execution_plan_id": plan.execution_plan_id,
        "project_state": state,
        "work_package_states": [item.model_dump(mode="json") for item in states],
        "worker_requests": [],
        "artifacts": [],
        "validations": [],
        "evidence": [],
        "approval_gates": [item.model_dump(mode="json") for item in plan.approval_gates],
        "retries": [],
        "contradictions": [],
        "events": [event.model_dump(mode="json")],
        "transitions": [],
        "checkpoints": [],
        "delivery_package": None,
        "diagnostics": [item.model_dump(mode="json") for item in diagnostics],
    }
    return R21Execution(**payload, execution_hash=specification_hash(payload))


def _complete_package(execution: R21Execution, package: R21WorkPackage) -> R21Execution:
    request = _worker_request(execution.execution_id, package)
    artifacts = tuple(_artifact(package, expected) for expected in package.expected_outputs)
    validation = _validation(package, artifacts, True, ())
    evidence = (
        _evidence(
            "work_package", package.work_package_id, "validation_report", validation.validation_id
        ),
    )
    event = _event(
        execution_id=execution.execution_id,
        project_id=execution.project_id,
        event_type="work_package.completed",
        causation_id=execution.events[-1].event_id if execution.events else None,
        subject_type="work_package",
        subject_id=package.work_package_id,
        payload={"artifact_ids": [item.artifact_id for item in artifacts]},
    )
    transition = _transition(
        entity_id=package.work_package_id,
        entity_type="work_package",
        from_state="RUNNING",
        to_state="COMPLETED",
        event_type="work_package.completed",
        correlation_id=execution.execution_id,
        evidence=tuple(item.evidence_hash for item in evidence),
        actor_type="worker",
        actor_id=package.worker_type,
    )
    return _execution(
        execution,
        worker_requests=(*execution.worker_requests, request),
        artifacts=(*execution.artifacts, *artifacts),
        validations=(*execution.validations, validation),
        evidence=(*execution.evidence, *evidence),
        events=(*execution.events, event),
        transitions=(*execution.transitions, transition),
    )


def _request_approval(execution: R21Execution, package: R21WorkPackage) -> R21Execution:
    event = _event(
        execution_id=execution.execution_id,
        project_id=execution.project_id,
        event_type="approval.requested",
        causation_id=execution.events[-1].event_id if execution.events else None,
        subject_type="work_package",
        subject_id=package.work_package_id,
        payload={"required_approvals": package.required_approvals},
    )
    return _execution(execution, events=(*execution.events, event))


def _blocked(
    execution: R21Execution,
    package: R21WorkPackage,
    code: str,
    event_type: str,
) -> R21Execution:
    diagnostic = _diag("fatal", "policy", code, package.work_package_id)
    event = _event(
        execution_id=execution.execution_id,
        project_id=execution.project_id,
        event_type=event_type,
        causation_id=execution.events[-1].event_id if execution.events else None,
        subject_type="work_package",
        subject_id=package.work_package_id,
        payload={"diagnostic": diagnostic.model_dump(mode="json")},
    )
    return _execution(
        execution,
        diagnostics=(*execution.diagnostics, diagnostic),
        events=(*execution.events, event),
    )


def _validation_failed(
    execution: R21Execution,
    package: R21WorkPackage,
    attempt: int,
    next_state: str,
) -> R21Execution:
    validation = _validation(
        package,
        (),
        False,
        ({"code": "R21-ARTIFACT-SCHEMA-VALIDATION-FAILED", "severity": "fatal"},),
    )
    retry = _retry(package, attempt, execution.execution_id)
    event = _event(
        execution_id=execution.execution_id,
        project_id=execution.project_id,
        event_type="work_package.validation_failed",
        causation_id=execution.events[-1].event_id if execution.events else None,
        subject_type="work_package",
        subject_id=package.work_package_id,
        payload={"next_state": next_state, "attempt": attempt},
    )
    diagnostic = _diag(
        "fatal", "validation", "R21-WORKER-OUTPUT-VALIDATION-FAILED", package.work_package_id
    )
    return _execution(
        execution,
        validations=(*execution.validations, validation),
        retries=(*execution.retries, retry),
        diagnostics=(*execution.diagnostics, diagnostic),
        events=(*execution.events, event),
    )


def _execution(execution: R21Execution, **changes: Any) -> R21Execution:
    payload = execution.model_dump(mode="json")
    payload.pop("execution_hash")
    payload.update(
        {
            key: [
                item.model_dump(mode="json") if isinstance(item, BaseModel) else item
                for item in value
            ]
            if isinstance(value, tuple)
            else value.model_dump(mode="json")
            if isinstance(value, BaseModel)
            else value
            for key, value in changes.items()
        }
    )
    return R21Execution(**payload, execution_hash=specification_hash(payload))


def _compiled_model(
    manifest: dict[str, Any],
    compiler_hash: str,
    graph_hash: str,
    r17_plan_hash: str,
) -> dict[str, Any]:
    return {
        "project_metadata": manifest.get("metadata", {}),
        "stakeholders": manifest.get("users", ()),
        "objectives": manifest.get("objectives", ()),
        "capabilities": manifest.get("capabilities", ()),
        "requirements": {
            "business_rules": manifest.get("businessRules", ()),
            "security": manifest.get("security", ()),
            "quality": manifest.get("quality", ()),
        },
        "constraints": manifest.get("constraints", ()),
        "policies": manifest.get("policies", ()),
        "architectural_objects": manifest.get("businessEntities", ()),
        "deliverables": _deliverables(),
        "work_package_templates": [item[0] for item in _work_package_specs()],
        "dependencies": [item[4] for item in _work_package_specs()],
        "acceptance_tests": manifest.get("quality", ()),
        "approval_gates": ("gate-release",),
        "evidence_requirements": ("validation_report", "traceability_report", "provenance_record"),
        "execution_permissions": ("least-privilege", "network-denied-by-default"),
        "compiler_hash": compiler_hash,
        "graph_hash": graph_hash,
        "r17_plan_hash": r17_plan_hash,
        "registry_version": manifest.get("version", {}).get("registryVersion", "unknown"),
    }


def _work_package_specs() -> tuple[
    tuple[str, str, str, str, tuple[str, ...], tuple[str, ...]], ...
]:
    return (
        (
            "wp-requirements-001",
            "Compile requirements",
            "requirements_compiler",
            "Definition",
            (),
            ("compiled_requirement_specification",),
        ),
        (
            "wp-api-contract-001",
            "Generate OpenAPI contract",
            "api_contract_worker",
            "API",
            ("wp-requirements-001",),
            ("openapi_contract",),
        ),
        (
            "wp-service-code-001",
            "Generate service source code",
            "backend_implementation_worker",
            "Implementation",
            ("wp-api-contract-001",),
            ("service_source_code",),
        ),
        (
            "wp-test-generation-001",
            "Generate tests",
            "test_generation_worker",
            "Implementation",
            ("wp-api-contract-001",),
            ("unit_tests", "integration_tests"),
        ),
        (
            "wp-container-001",
            "Generate container definition",
            "container_worker",
            "Implementation",
            ("wp-service-code-001",),
            ("container_definition", "build_instructions"),
        ),
        (
            "wp-build-validation-001",
            "Validate build",
            "build_validation_worker",
            "Validation",
            ("wp-service-code-001", "wp-test-generation-001", "wp-container-001"),
            ("validation_report", "traceability_report", "provenance_record"),
        ),
        (
            "wp-release-approval-001",
            "Collect human release approval",
            "approval_coordinator",
            "Approval",
            ("wp-build-validation-001",),
            ("approval_record",),
        ),
        (
            "wp-delivery-package-001",
            "Create delivery package",
            "delivery_packager",
            "Delivery",
            ("wp-release-approval-001",),
            ("delivery_archive",),
        ),
    )


def _work_packages(
    manifest: dict[str, Any],
    compilation: R21ProjectCompilation,
) -> tuple[R21WorkPackage, ...]:
    sources = _manifest_sources(manifest)
    required_by: dict[str, list[str]] = {}
    for package_id, _, _, _, dependencies, _ in _work_package_specs():
        for dependency in dependencies:
            required_by.setdefault(dependency, []).append(package_id)
    packages: list[R21WorkPackage] = []
    for index, (package_id, title, worker, phase, dependencies, outputs) in enumerate(
        _work_package_specs(),
        start=1,
    ):
        trace = _trace(compilation.project_id, compilation.manifest_version, sources)
        permissions = R21WorkPackagePermissions(
            tools=("registry.read", "artifact.read", "artifact.write", "validation.run"),
            repositories=(f"{compilation.project_id}-{phase.lower()}",),
            network_access="denied",
            destructive_operations="denied",
        )
        payload = {
            "work_package_id": package_id,
            "project_id": compilation.project_id,
            "version": 1,
            "title": title,
            "purpose": f"{title} for the approved Manifest.",
            "manifest_trace": trace.model_dump(mode="json"),
            "requires": dependencies,
            "required_by": tuple(required_by.get(package_id, ())),
            "worker_type": worker,
            "execution_mode": "deterministic_worker",
            "priority": index,
            "timeout_seconds": 3600,
            "maximum_attempts": 3,
            "permissions": permissions.model_dump(mode="json"),
            "inputs": tuple(f"artifact://{dependency}/output" for dependency in dependencies),
            "expected_outputs": [
                {"artifact_type": output, "schema_uri": f"registry://schemas/{output}/v1"}
                for output in outputs
            ],
            "validators": ("schema_validator", "traceability_validator", "policy_validator"),
            "completion_criteria": {
                "all_outputs_present": True,
                "all_validators_pass": True,
                "unresolved_critical_findings": 0,
            },
            "required_approvals": ("gate-release",)
            if package_id == "wp-release-approval-001"
            else (),
            "idempotency_key": f"{compilation.project_id}:{package_id}:v1:attempt-1",
        }
        packages.append(R21WorkPackage(**payload, package_hash=specification_hash(payload)))
    return tuple(packages)


def _phases(work_packages: tuple[R21WorkPackage, ...]) -> tuple[R21ExecutionPhase, ...]:
    phase_specs = (
        ("phase-01", "Definition compilation", ("wp-requirements-001",)),
        ("phase-02", "API contract", ("wp-api-contract-001",)),
        (
            "phase-03",
            "Implementation",
            ("wp-service-code-001", "wp-test-generation-001", "wp-container-001"),
        ),
        ("phase-04", "Validation", ("wp-build-validation-001",)),
        ("phase-05", "Delivery", ("wp-release-approval-001", "wp-delivery-package-001")),
    )
    existing = {item.work_package_id for item in work_packages}
    phases: list[R21ExecutionPhase] = []
    for phase_id, name, package_ids in phase_specs:
        selected = tuple(item for item in package_ids if item in existing)
        payload = {"phase_id": phase_id, "name": name, "work_package_ids": selected}
        phases.append(R21ExecutionPhase(**payload, phase_hash=specification_hash(payload)))
    return tuple(phases)


def _approval_gate(project_id: str, work_packages: tuple[R21WorkPackage, ...]) -> R21ApprovalGate:
    subjects = tuple(
        item.work_package_id
        for item in work_packages
        if item.work_package_id in {"wp-build-validation-001", "wp-release-approval-001"}
    )
    requirements = (
        R21ApprovalRequirement(role="project_owner", minimum_approvals=1),
        R21ApprovalRequirement(role="release_authority", minimum_approvals=1),
    )
    payload = {
        "gate_id": "gate-release",
        "project_id": project_id,
        "gate_type": "release_approval",
        "occurs_before": "COMPLETED",
        "subject_work_package_ids": subjects,
        "required_approvers": [item.model_dump(mode="json") for item in requirements],
        "evidence_required": ("validation_report", "traceability_report", "provenance_record"),
        "decisions": [],
        "status": "pending",
    }
    return R21ApprovalGate(**payload, gate_hash=specification_hash(payload))


def _parallel_groups(work_packages: tuple[R21WorkPackage, ...]) -> tuple[tuple[str, ...], ...]:
    remaining = {item.work_package_id: set(item.requires) for item in work_packages}
    completed: set[str] = set()
    groups: list[tuple[str, ...]] = []
    while remaining:
        ready = tuple(sorted(item for item, deps in remaining.items() if deps <= completed))
        if not ready:
            return (*groups, tuple(sorted(remaining)))
        groups.append(ready)
        completed.update(ready)
        for item in ready:
            remaining.pop(item)
    return tuple(groups)


def _manifest_sources(manifest: dict[str, Any]) -> tuple[R21TraceSource, ...]:
    sections = {
        "objectives": "objective",
        "capabilities": "capability",
        "businessEntities": "entity",
        "workflows": "workflow",
        "businessRules": "business_rule",
        "policies": "policy",
        "integrations": "integration",
        "security": "security_requirement",
        "quality": "quality_requirement",
        "constraints": "constraint",
    }
    sources: list[R21TraceSource] = []
    for section, object_type in sections.items():
        for item in manifest.get(section, ()):
            object_id = item.get("id")
            if object_id:
                sources.append(
                    R21TraceSource(
                        object_id=str(object_id),
                        object_type=object_type,
                        relationship="drives",
                    )
                )
    return tuple(sorted(sources, key=lambda item: (item.object_type, item.object_id)))


def _trace(
    project_id: str, manifest_version: str, sources: tuple[R21TraceSource, ...]
) -> R21ManifestTrace:
    payload = {
        "project_id": project_id,
        "manifest_version": manifest_version,
        "source_objects": [item.model_dump(mode="json") for item in sources],
    }
    return R21ManifestTrace(**payload, trace_hash=specification_hash(payload))


def _worker_request(execution_id: str, package: R21WorkPackage) -> R21WorkerRequest:
    payload = {
        "execution_id": execution_id,
        "work_package_id": package.work_package_id,
        "worker_type": package.worker_type,
        "worker_version": "1.0.0",
        "instructions": {
            "objective": package.purpose,
            "constraints": (
                "Do not change project scope.",
                "Do not invent unavailable requirements.",
                "Use only approved Registry objects.",
            ),
        },
        "context": {
            "manifest_trace": package.manifest_trace.model_dump(mode="json"),
            "input_artifacts": package.inputs,
        },
        "output_contract": {
            "required_artifacts": [item.artifact_type for item in package.expected_outputs],
            "response_schema": "registry://schemas/worker-response/v1",
        },
        "authorization": {
            "capability_token": f"capability://{package.work_package_id}",
            "expires_at": DETERMINISTIC_ORCHESTRATION_TIMESTAMP,
            "tools": package.permissions.tools,
        },
    }
    request_hash = specification_hash(payload)
    return R21WorkerRequest(
        request_id=f"r21-worker-request-{request_hash[:16]}",
        request_hash=request_hash,
        **payload,
    )


def _artifact(package: R21WorkPackage, expected: R21ExpectedOutput) -> R21ArtifactVersion:
    content = {
        "work_package_id": package.work_package_id,
        "artifact_type": expected.artifact_type,
        "manifest_trace_hash": package.manifest_trace.trace_hash,
        "schema": expected.schema_uri,
    }
    checksum = specification_hash(content)
    payload = {
        "work_package_id": package.work_package_id,
        "artifact_type": expected.artifact_type,
        "version": 1,
        "uri": f"artifact://r21/{package.work_package_id}/{expected.artifact_type}/v1",
        "checksum": f"sha256:{checksum}",
        "promotion_level": "POLICY_VALIDATED",
        "manifest_trace_hash": package.manifest_trace.trace_hash,
        "provenance_hash": specification_hash(
            {
                "worker_type": package.worker_type,
                "idempotency_key": package.idempotency_key,
                "content_hash": checksum,
            }
        ),
    }
    artifact_hash = specification_hash(payload)
    return R21ArtifactVersion(
        artifact_id=f"r21-artifact-{artifact_hash[:16]}",
        artifact_hash=artifact_hash,
        **payload,
    )


def _validation(
    package: R21WorkPackage,
    artifacts: tuple[R21ArtifactVersion, ...],
    passed: bool,
    findings: tuple[dict[str, str], ...],
) -> R21ValidationResult:
    payload = {
        "work_package_id": package.work_package_id,
        "artifact_ids": tuple(item.artifact_id for item in artifacts),
        "validators": package.validators,
        "passed": passed,
        "findings": findings,
    }
    validation_hash = specification_hash(payload)
    return R21ValidationResult(
        validation_id=f"r21-validation-{validation_hash[:16]}",
        validation_hash=validation_hash,
        **payload,
    )


def _evidence(
    entity_type: str, entity_id: str, evidence_type: str, reference: str
) -> R21EvidenceRecord:
    payload = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "evidence_type": evidence_type,
        "uri": f"evidence://r21/{entity_type}/{entity_id}/{evidence_type}",
        "checksum": f"sha256:{specification_hash({'reference': reference})}",
    }
    evidence_hash = specification_hash(payload)
    return R21EvidenceRecord(
        evidence_id=f"r21-evidence-{evidence_hash[:16]}",
        evidence_hash=evidence_hash,
        **payload,
    )


def _delivery_package(execution: R21Execution) -> R21DeliveryPackage:
    traceability_payload = {
        artifact.artifact_id: artifact.manifest_trace_hash for artifact in execution.artifacts
    }
    provenance_payload = {
        artifact.artifact_id: artifact.provenance_hash for artifact in execution.artifacts
    }
    payload = {
        "project_id": execution.project_id,
        "execution_id": execution.execution_id,
        "artifact_ids": tuple(item.artifact_id for item in execution.artifacts),
        "validation_ids": tuple(item.validation_id for item in execution.validations),
        "evidence_ids": tuple(item.evidence_id for item in execution.evidence),
        "traceability_hash": specification_hash(traceability_payload),
        "provenance_hash": specification_hash(provenance_payload),
        "delivery_status": "evidence_backed",
    }
    package_hash = specification_hash(payload)
    return R21DeliveryPackage(
        package_id=f"r21-delivery-{package_hash[:16]}",
        package_hash=package_hash,
        **payload,
    )


def _checkpoint(
    execution: R21Execution,
    state: str,
    *,
    gates: tuple[R21ApprovalGate, ...] | None = None,
    work_package_states: tuple[R21WorkPackageRuntimeState, ...] | None = None,
) -> R21Checkpoint:
    work_states = work_package_states or execution.work_package_states
    approval_gates = gates or execution.approval_gates
    payload = {
        "execution_id": execution.execution_id,
        "created_at": DETERMINISTIC_ORCHESTRATION_TIMESTAMP,
        "project_state": state,
        "manifest_hash": execution.execution_plan_id,
        "completed_work_packages": tuple(
            item.work_package_id for item in work_states if item.state == "COMPLETED"
        ),
        "running_work_packages": tuple(
            item.work_package_id for item in work_states if item.state == "RUNNING"
        ),
        "blocked_work_packages": tuple(
            item.work_package_id for item in work_states if item.state in {"BLOCKED", "FAILED"}
        ),
        "pending_approvals": tuple(
            item.gate_id for item in approval_gates if item.status == "pending"
        ),
        "produced_artifacts": tuple(item.artifact_id for item in execution.artifacts),
        "retry_counters": {item.work_package_id: item.attempt for item in work_states},
        "scheduler_state": {"event_position": len(execution.events)},
        "last_event_sequence": len(execution.events),
    }
    checkpoint_hash = specification_hash(payload)
    return R21Checkpoint(
        checkpoint_id=f"r21-checkpoint-{checkpoint_hash[:16]}",
        checkpoint_hash=checkpoint_hash,
        **payload,
    )


def _approval_decision(
    gate_id: str,
    decision: str,
    actor_role: str,
    actor_id: str,
    bound_artifact_hashes: tuple[str, ...],
) -> R21ApprovalDecision:
    payload = {
        "gate_id": gate_id,
        "decision": decision,
        "actor_role": actor_role,
        "actor_id": actor_id,
        "bound_artifact_hashes": bound_artifact_hashes,
        "decided_at": DETERMINISTIC_ORCHESTRATION_TIMESTAMP,
    }
    decision_hash = specification_hash(payload)
    return R21ApprovalDecision(
        decision_id=f"r21-approval-{decision_hash[:16]}",
        decision_hash=decision_hash,
        **payload,
    )


def _gate_with_decision(
    gate: R21ApprovalGate,
    decision: R21ApprovalDecision,
    decision_value: str,
) -> R21ApprovalGate:
    payload = gate.model_dump(mode="json")
    payload.pop("gate_hash")
    payload["decisions"] = [*payload["decisions"], decision.model_dump(mode="json")]
    if decision_value in {"reject", "request_revision"}:
        payload["status"] = "rejected"
    else:
        approved_roles = {
            item["actor_role"]
            for item in payload["decisions"]
            if item["decision"] in {"approve", "approve_with_conditions"}
        }
        required_roles = {item["role"] for item in payload["required_approvers"]}
        payload["status"] = "approved" if required_roles <= approved_roles else "pending"
    return R21ApprovalGate(**payload, gate_hash=specification_hash(payload))


def _approval_satisfied(execution: R21Execution, approvals: tuple[str, ...]) -> bool:
    approved = {item.gate_id for item in execution.approval_gates if item.status == "approved"}
    return set(approvals) <= approved


def _event(
    *,
    execution_id: str,
    project_id: str,
    event_type: str,
    causation_id: str | None,
    subject_type: str,
    subject_id: str,
    payload: dict[str, Any],
) -> R21ExecutionEvent:
    unsigned = {
        "event_type": event_type,
        "event_version": 1,
        "occurred_at": DETERMINISTIC_ORCHESTRATION_TIMESTAMP,
        "project_id": project_id,
        "execution_id": execution_id,
        "correlation_id": execution_id,
        "causation_id": causation_id,
        "actor": {"actor_type": "orchestrator", "actor_id": "r21-orchestrator"},
        "subject": {"entity_type": subject_type, "entity_id": subject_id},
        "payload": payload,
    }
    checksum = specification_hash(unsigned)
    return R21ExecutionEvent(
        event_id=f"r21-event-{checksum[:16]}",
        checksum=f"sha256:{checksum}",
        **unsigned,
    )


def _transition(
    *,
    entity_id: str,
    entity_type: str,
    from_state: str | None,
    to_state: str,
    event_type: str,
    correlation_id: str,
    evidence: tuple[str, ...],
    actor_type: str,
    actor_id: str,
) -> R21StateTransition:
    payload = {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "from_state": from_state,
        "to_state": to_state,
        "triggered_by": {"actor_type": actor_type, "actor_id": actor_id},
        "event_type": event_type,
        "occurred_at": DETERMINISTIC_ORCHESTRATION_TIMESTAMP,
        "correlation_id": correlation_id,
        "evidence": evidence,
    }
    transition_hash = specification_hash(payload)
    return R21StateTransition(
        transition_id=f"r21-transition-{transition_hash[:16]}",
        transition_hash=transition_hash,
        **payload,
    )


def _wp_state(
    work_package_id: str,
    state: str,
    attempt: int,
    lease_id: str | None,
    retry_reason: str | None,
) -> R21WorkPackageRuntimeState:
    payload = {
        "work_package_id": work_package_id,
        "state": state,
        "attempt": attempt,
        "lease_id": lease_id,
        "retry_reason": retry_reason,
    }
    return R21WorkPackageRuntimeState(**payload, state_hash=specification_hash(payload))


def _retry(package: R21WorkPackage, attempt: int, execution_id: str) -> R21RetryRecord:
    payload = {
        "work_package_id": package.work_package_id,
        "attempt": attempt,
        "maximum_attempts": package.maximum_attempts,
        "retry_reason": "validator_timeout",
        "previous_execution_id": execution_id,
        "scheduled_at": DETERMINISTIC_ORCHESTRATION_TIMESTAMP,
        "backoff_seconds": 120 * attempt,
    }
    return R21RetryRecord(**payload, retry_hash=specification_hash(payload))


def _detect_manifest_contradictions(
    manifest: dict[str, Any],
    work_packages: tuple[R21WorkPackage, ...],
) -> tuple[R21Contradiction, ...]:
    constraints = manifest.get("constraints", ())
    integrations = manifest.get("integrations", ())
    private_constraints = [
        item for item in constraints if "private network" in item.get("description", "").lower()
    ]
    public_integrations = [
        item
        for item in integrations
        if "public" in item.get("purpose", "").lower()
        or "external" in item.get("purpose", "").lower()
    ]
    if not private_constraints or not public_integrations:
        return ()
    affected = tuple(
        item.work_package_id
        for item in work_packages
        if item.worker_type in {"api_contract_worker", "container_worker"}
    )
    payload = {
        "severity": "high",
        "status": "unresolved",
        "sources": (
            {
                "object_id": str(private_constraints[0].get("id")),
                "statement": str(private_constraints[0].get("description")),
            },
            {
                "object_id": str(public_integrations[0].get("id")),
                "statement": str(public_integrations[0].get("purpose")),
            },
        ),
        "affected_work_packages": affected,
        "required_role": "project_owner",
        "allowed_actions": (
            "amend_manifest",
            "remove_integration",
            "approve_architecture_exception",
        ),
    }
    contradiction_hash = specification_hash(payload)
    return (
        R21Contradiction(
            contradiction_id=f"r21-contradiction-{contradiction_hash[:16]}",
            contradiction_hash=contradiction_hash,
            **payload,
        ),
    )


def _changed_manifest_object_ids(
    previous_manifest: dict[str, Any],
    current_manifest: dict[str, Any],
) -> set[str]:
    previous = _manifest_object_hashes(previous_manifest)
    current = _manifest_object_hashes(current_manifest)
    return {
        object_id
        for object_id, current_hash in current.items()
        if previous.get(object_id) != current_hash
    } | {object_id for object_id in previous if object_id not in current}


def _manifest_object_hashes(manifest: dict[str, Any]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for section in (
        "objectives",
        "capabilities",
        "businessEntities",
        "workflows",
        "businessRules",
        "policies",
        "integrations",
        "security",
        "quality",
        "constraints",
    ):
        for item in manifest.get(section, ()):
            if "id" in item:
                hashes[str(item["id"])] = specification_hash(item)
    return hashes


def _deliverables() -> tuple[str, ...]:
    return (
        "compiled_requirement_specification",
        "openapi_contract",
        "service_source_code",
        "unit_tests",
        "integration_tests",
        "container_definition",
        "build_instructions",
        "validation_report",
        "traceability_report",
        "provenance_record",
        "delivery_archive",
    )


def _coerce_compilation(
    compilation: dict[str, Any] | R21ProjectCompilation,
) -> R21ProjectCompilation:
    return (
        compilation
        if isinstance(compilation, R21ProjectCompilation)
        else R21ProjectCompilation.model_validate(compilation)
    )


def _coerce_plan(plan: dict[str, Any] | R21ExecutionPlan) -> R21ExecutionPlan:
    return plan if isinstance(plan, R21ExecutionPlan) else R21ExecutionPlan.model_validate(plan)


def _coerce_execution(execution: dict[str, Any] | R21Execution) -> R21Execution:
    return (
        execution if isinstance(execution, R21Execution) else R21Execution.model_validate(execution)
    )


def _with_diagnostic(
    execution: R21Execution,
    severity: str,
    category: str,
    code: str,
    path: str,
) -> R21Execution:
    return _execution(
        execution, diagnostics=(*execution.diagnostics, _diag(severity, category, code, path))
    )


def _diag(severity: str, category: str, code: str, path: str) -> R21Diagnostic:
    return R21Diagnostic(
        severity=severity,
        category=category,
        code=code,
        message=f"{code} at {path}",
        path=path,
    )
