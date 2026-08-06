from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ai_enterprise.application.r17_execution_planner_runtime import R17ExecutionPlan
from ai_enterprise.application.r18_generator_orchestration_runtime import R18ExecutionResult
from ai_enterprise.application.r19_project_memory_runtime import R19MemoryStore
from ai_enterprise.domain.specification.kernel import specification_hash

RUNTIME_KERNEL_VERSION = "runtime-kernel-1.0"
DETERMINISTIC_RUNTIME_TIMESTAMP = "1970-01-01T00:00:00Z"

LIFECYCLE_PHASES: tuple[str, ...] = (
    "boot",
    "initialize",
    "load_registry",
    "compile",
    "plan",
    "execute",
    "validate",
    "deploy",
    "monitor",
    "shutdown",
)

TASK_STATES: tuple[str, ...] = (
    "created",
    "scheduled",
    "assigned",
    "executing",
    "validating",
    "completed",
    "failed",
    "retry",
    "cancelled",
)

SERVICE_INTERFACES: tuple[str, ...] = (
    "ICompiler",
    "IKnowledgeGraph",
    "IPlanner",
    "IGenerator",
    "IMemory",
    "IValidator",
    "IDeployment",
    "IMonitor",
)

MODULES: tuple[str, ...] = (
    "lifecycle_manager",
    "scheduler",
    "event_bus",
    "state_manager",
    "policy_engine",
    "service_registry",
    "health_monitor",
    "security_manager",
    "resource_manager",
    "execution_supervisor",
    "recovery_manager",
    "runtime_api",
)


class R20KernelDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True)

    severity: str
    category: str
    code: str
    message: str
    path: str


class R20RuntimeEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    event_type: str
    timestamp: str
    source: str
    target: str
    payload: dict[str, Any]
    correlation_id: str
    execution_id: str | None
    previous_event_hash: str | None
    event_hash: str


class R20LifecycleSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    phase: str
    previous_phase: str | None
    transition_allowed: bool
    snapshot_hash: str


class R20ServiceRegistration(BaseModel):
    model_config = ConfigDict(frozen=True)

    service_id: str
    service_name: str
    interface: str
    version: str
    status: str
    health_endpoint: str | None = None
    capabilities: tuple[str, ...]
    service_hash: str


class R20TaskState(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: str
    generator: str
    state: str
    dependencies: tuple[str, ...]
    retry_count: int
    priority: int
    task_hash: str


class R20ScheduleItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    schedule_id: str
    task_id: str
    generator: str
    stage_id: str
    order: int
    dependency_ids: tuple[str, ...]
    resource_claim: dict[str, int]
    policy_refs: tuple[str, ...]
    dispatchable: bool
    schedule_hash: str


class R20PolicyDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_id: str
    subject: str
    policy_type: str
    allowed: bool
    reasons: tuple[dict[str, str], ...]
    decision_hash: str


class R20ResourceAllocation(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    max_parallel_tasks: int
    ai_model_capacity: int
    compute_units: int
    storage_mb: int
    cache_mb: int
    execution_slots: int
    temporary_workspace_ref: str
    allocation_hash: str


class R20HealthSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    cpu_units: int
    memory_mb: int
    storage_mb: int
    queue_size: int
    generator_available_count: int
    execution_latency_ms: int
    failure_rate_basis_points: int
    ready: bool
    health_hash: str


class R20RecoveryAction(BaseModel):
    model_config = ConfigDict(frozen=True)

    recovery_id: str
    failure_category: str
    target_id: str
    action: str
    deterministic: bool
    recovery_hash: str


class R20RuntimeState(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    manifest_hash: str | None
    graph_hash: str | None
    plan_hash: str | None
    running_tasks: tuple[str, ...]
    completed_tasks: tuple[str, ...]
    failed_tasks: tuple[str, ...]
    pending_reviews: tuple[str, ...]
    deployment_status: str
    state_version: int
    state_hash: str


class R20ObservabilitySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    metrics: dict[str, int]
    traces: tuple[dict[str, str], ...]
    logs: tuple[dict[str, str], ...]
    execution_timeline: tuple[str, ...]
    dependency_graph_hash: str
    generator_utilization: dict[str, int]
    queue_statistics: dict[str, int]
    observability_hash: str


class R20KernelConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_parallel_tasks: int = Field(default=4, ge=1, le=10_000)
    retry_limit: int = Field(default=2, ge=0, le=20)
    execution_timeout_seconds: int = Field(default=1800, ge=1)
    ai_provider_priorities: tuple[str, ...] = ("rule-engine", "openai", "anthropic", "google")
    resource_quotas: dict[str, int] = Field(
        default_factory=lambda: {
            "ai_model_capacity": 100,
            "compute_units": 100,
            "storage_mb": 1_000_000,
            "cache_mb": 100_000,
            "execution_slots": 16,
        }
    )
    approval_policies: tuple[str, ...] = ("manual-deployment-approval", "security-review")
    policy_refs: tuple[str, ...] = ("r20.default.policy",)


class R20KernelSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    kernel_version: str
    lifecycle: R20LifecycleSnapshot
    config: R20KernelConfig
    service_registry: tuple[R20ServiceRegistration, ...]
    event_history: tuple[R20RuntimeEvent, ...]
    state: R20RuntimeState
    schedule: tuple[R20ScheduleItem, ...]
    task_states: tuple[R20TaskState, ...]
    policy_decisions: tuple[R20PolicyDecision, ...]
    resource_allocation: R20ResourceAllocation
    health: R20HealthSnapshot
    recovery_actions: tuple[R20RecoveryAction, ...]
    observability: R20ObservabilitySnapshot
    diagnostics: tuple[R20KernelDiagnostic, ...]
    kernel_hash: str


class R20KernelValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    diagnostics: tuple[R20KernelDiagnostic, ...]
    report_hash: str


def r20_boot_kernel(
    *,
    project_id: str,
    manifest_hash: str | None = None,
    graph: dict[str, Any] | None = None,
    plan: dict[str, Any] | R17ExecutionPlan | None = None,
    execution_result: dict[str, Any] | R18ExecutionResult | None = None,
    memory_store: dict[str, Any] | R19MemoryStore | None = None,
    config: dict[str, Any] | R20KernelConfig | None = None,
) -> R20KernelSnapshot:
    kernel_config = (
        config
        if isinstance(config, R20KernelConfig)
        else R20KernelConfig.model_validate(config or {})
    )
    plan_model = (
        plan
        if isinstance(plan, R17ExecutionPlan)
        else R17ExecutionPlan.model_validate(plan)
        if isinstance(plan, dict)
        else None
    )
    execution_model = (
        execution_result
        if isinstance(execution_result, R18ExecutionResult)
        else R18ExecutionResult.model_validate(execution_result)
        if isinstance(execution_result, dict)
        else None
    )
    memory_model = (
        memory_store
        if isinstance(memory_store, R19MemoryStore)
        else R19MemoryStore.model_validate(memory_store)
        if isinstance(memory_store, dict)
        else None
    )
    lifecycle = _lifecycle("boot", None)
    services = _service_registry()
    diagnostics = _invariant_diagnostics(manifest_hash, graph, plan_model, execution_model)
    task_states = _task_states(plan_model, execution_model, kernel_config)
    schedule = _schedule(plan_model, task_states, kernel_config)
    policy_decisions = _policy_decisions(
        manifest_hash,
        graph,
        plan_model,
        execution_model,
        memory_model,
    )
    allocation = _resource_allocation(project_id, kernel_config)
    events = _events(project_id, lifecycle, services, plan_model, execution_model, memory_model)
    state = _state(project_id, manifest_hash, graph, plan_model, execution_model, task_states)
    health = _health(schedule, task_states, services)
    recovery = _recovery_actions(task_states, services)
    observability = _observability(events, schedule, task_states, services)
    return _snapshot(
        lifecycle=lifecycle,
        config=kernel_config,
        service_registry=services,
        event_history=events,
        state=state,
        schedule=schedule,
        task_states=task_states,
        policy_decisions=policy_decisions,
        resource_allocation=allocation,
        health=health,
        recovery_actions=recovery,
        observability=observability,
        diagnostics=tuple(sorted(diagnostics, key=lambda item: (item.code, item.path))),
    )


def r20_transition_lifecycle(
    snapshot: dict[str, Any] | R20KernelSnapshot,
    next_phase: str,
) -> R20KernelSnapshot:
    current = _coerce_snapshot(snapshot)
    lifecycle = _lifecycle(next_phase, current.lifecycle.phase)
    diagnostics = current.diagnostics
    if not lifecycle.transition_allowed:
        diagnostics = (
            *diagnostics,
            _diag("fatal", "lifecycle", "R20-LIFECYCLE-TRANSITION-DENIED", next_phase),
        )
    event = _event(
        event_type=f"runtime.{next_phase}",
        source="runtime-kernel",
        target="lifecycle-manager",
        payload={"previous_phase": current.lifecycle.phase, "next_phase": next_phase},
        correlation_id=current.state.project_id,
        execution_id=None,
        previous_event_hash=(
            current.event_history[-1].event_hash if current.event_history else None
        ),
    )
    return _snapshot(
        lifecycle=lifecycle,
        config=current.config,
        service_registry=current.service_registry,
        event_history=(*current.event_history, event),
        state=_state_with_version(current.state, current.state.state_version + 1),
        schedule=current.schedule,
        task_states=current.task_states,
        policy_decisions=current.policy_decisions,
        resource_allocation=current.resource_allocation,
        health=current.health,
        recovery_actions=current.recovery_actions,
        observability=_observability(
            (*current.event_history, event),
            current.schedule,
            current.task_states,
            current.service_registry,
        ),
        diagnostics=diagnostics,
    )


def r20_validate_kernel(snapshot: dict[str, Any] | R20KernelSnapshot) -> R20KernelValidationReport:
    current = _coerce_snapshot(snapshot)
    diagnostics: list[R20KernelDiagnostic] = list(current.diagnostics)
    if current.kernel_version != RUNTIME_KERNEL_VERSION:
        diagnostics.append(
            _diag("fatal", "kernel", "R20-KERNEL-VERSION-MISMATCH", "kernel_version")
        )
    service_interfaces = {item.interface for item in current.service_registry}
    for interface in SERVICE_INTERFACES:
        if interface not in service_interfaces:
            diagnostics.append(_diag("fatal", "service", "R20-SERVICE-MISSING", interface))
    event_hashes: set[str] = set()
    for event in current.event_history:
        if event.previous_event_hash and event.previous_event_hash not in event_hashes:
            diagnostics.append(_diag("fatal", "event", "R20-EVENT-CHAIN-BROKEN", event.event_id))
        if event.event_hash != _event_hash(event):
            diagnostics.append(_diag("fatal", "event", "R20-EVENT-HASH-MISMATCH", event.event_id))
        event_hashes.add(event.event_hash)
    if current.state.state_hash != _state_hash(current.state):
        diagnostics.append(_diag("fatal", "state", "R20-STATE-HASH-MISMATCH", "state"))
    task_ids = {item.task_id for item in current.task_states}
    for item in current.schedule:
        if item.task_id not in task_ids:
            diagnostics.append(
                _diag("fatal", "scheduler", "R20-SCHEDULE-TASK-MISSING", item.task_id)
            )
    if any(decision.allowed is False for decision in current.policy_decisions):
        diagnostics.append(_diag("fatal", "policy", "R20-POLICY-DENIED", "policy_decisions"))
    payload = {
        "valid": not any(item.severity == "fatal" for item in diagnostics),
        "diagnostics": [item.model_dump(mode="json") for item in diagnostics],
    }
    return R20KernelValidationReport(
        valid=not any(item.severity == "fatal" for item in diagnostics),
        diagnostics=tuple(sorted(diagnostics, key=lambda item: (item.code, item.path))),
        report_hash=specification_hash(payload),
    )


def r20_recover_kernel(snapshot: dict[str, Any] | R20KernelSnapshot) -> R20KernelSnapshot:
    current = _coerce_snapshot(snapshot)
    recovered_tasks = tuple(
        _task_state(item, "retry" if item.retry_count < current.config.retry_limit else "failed")
        if item.state == "failed"
        else item
        for item in current.task_states
    )
    recovery_actions = _recovery_actions(recovered_tasks, current.service_registry)
    event = _event(
        event_type="runtime.recovery",
        source="runtime-kernel",
        target="recovery-manager",
        payload={"recovery_action_count": len(recovery_actions)},
        correlation_id=current.state.project_id,
        execution_id=None,
        previous_event_hash=(
            current.event_history[-1].event_hash if current.event_history else None
        ),
    )
    state = _state_from_tasks(current.state, recovered_tasks)
    return _snapshot(
        lifecycle=current.lifecycle,
        config=current.config,
        service_registry=current.service_registry,
        event_history=(*current.event_history, event),
        state=state,
        schedule=current.schedule,
        task_states=recovered_tasks,
        policy_decisions=current.policy_decisions,
        resource_allocation=current.resource_allocation,
        health=_health(current.schedule, recovered_tasks, current.service_registry),
        recovery_actions=recovery_actions,
        observability=_observability(
            (*current.event_history, event),
            current.schedule,
            recovered_tasks,
            current.service_registry,
        ),
        diagnostics=tuple(item for item in current.diagnostics if item.code != "R20-TASK-FAILED"),
    )


def r20_write_kernel(snapshot: dict[str, Any] | R20KernelSnapshot, path: Path) -> str:
    current = _coerce_snapshot(snapshot)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(current.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return current.kernel_hash


def r20_read_kernel(path: Path) -> R20KernelSnapshot | None:
    if not path.exists():
        return None
    return R20KernelSnapshot.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _service_registry() -> tuple[R20ServiceRegistration, ...]:
    specs = (
        ("compiler", "Manifest Compiler", "ICompiler", ("compile", "validate-manifest")),
        ("knowledge-graph", "Knowledge Graph", "IKnowledgeGraph", ("load-graph", "query-graph")),
        ("planner", "Execution Planner", "IPlanner", ("create-plan", "validate-plan")),
        (
            "generator",
            "Generator Orchestrator",
            "IGenerator",
            ("execute-plan", "validate-artifacts"),
        ),
        ("memory", "Project Memory", "IMemory", ("store", "query", "context")),
        ("validator", "Validation Service", "IValidator", ("validate", "report")),
        ("deployment", "Deployment Service", "IDeployment", ("package", "deploy", "rollback")),
        ("monitor", "Runtime Monitor", "IMonitor", ("metrics", "health", "events")),
    )
    services: list[R20ServiceRegistration] = []
    for service_id, name, interface, capabilities in specs:
        payload = {
            "service_id": service_id,
            "service_name": name,
            "interface": interface,
            "version": "1.0.0",
            "status": "available",
            "health_endpoint": f"/api/v1/r20/services/{service_id}/health",
            "capabilities": tuple(capabilities),
        }
        services.append(R20ServiceRegistration(**payload, service_hash=specification_hash(payload)))
    return tuple(services)


def _lifecycle(phase: str, previous: str | None) -> R20LifecycleSnapshot:
    allowed = phase in LIFECYCLE_PHASES and (
        previous is None
        or (
            previous in LIFECYCLE_PHASES
            and LIFECYCLE_PHASES.index(phase) >= LIFECYCLE_PHASES.index(previous)
        )
    )
    payload = {
        "phase": phase,
        "previous_phase": previous,
        "transition_allowed": allowed,
    }
    return R20LifecycleSnapshot(**payload, snapshot_hash=specification_hash(payload))


def _events(
    project_id: str,
    lifecycle: R20LifecycleSnapshot,
    services: tuple[R20ServiceRegistration, ...],
    plan: R17ExecutionPlan | None,
    result: R18ExecutionResult | None,
    memory: R19MemoryStore | None,
) -> tuple[R20RuntimeEvent, ...]:
    events: list[R20RuntimeEvent] = []
    previous: str | None = None
    for event_type, target, payload in (
        ("runtime.booted", "lifecycle-manager", {"phase": lifecycle.phase}),
        ("runtime.services_registered", "service-registry", {"service_count": len(services)}),
        ("runtime.plan_loaded", "scheduler", {"plan_id": plan.plan_id if plan else None}),
        (
            "runtime.execution_observed",
            "execution-supervisor",
            {"execution_id": result.execution_id if result else None},
        ),
        (
            "runtime.memory_attached",
            "memory-engine",
            {"store_hash": memory.store_hash if memory else None},
        ),
    ):
        event = _event(
            event_type=event_type,
            source="runtime-kernel",
            target=target,
            payload=payload,
            correlation_id=project_id,
            execution_id=result.execution_id if result else None,
            previous_event_hash=previous,
        )
        events.append(event)
        previous = event.event_hash
    return tuple(events)


def _event(
    *,
    event_type: str,
    source: str,
    target: str,
    payload: dict[str, Any],
    correlation_id: str,
    execution_id: str | None,
    previous_event_hash: str | None,
) -> R20RuntimeEvent:
    unsigned = {
        "event_type": event_type,
        "timestamp": DETERMINISTIC_RUNTIME_TIMESTAMP,
        "source": source,
        "target": target,
        "payload": payload,
        "correlation_id": correlation_id,
        "execution_id": execution_id,
        "previous_event_hash": previous_event_hash,
    }
    event_hash = specification_hash(unsigned)
    return R20RuntimeEvent(
        event_id=f"r20-event-{event_hash[:16]}",
        event_hash=event_hash,
        **unsigned,
    )


def _event_hash(event: R20RuntimeEvent) -> str:
    payload = event.model_dump(mode="json")
    payload.pop("event_id")
    payload.pop("event_hash")
    return specification_hash(payload)


def _task_states(
    plan: R17ExecutionPlan | None,
    result: R18ExecutionResult | None,
    config: R20KernelConfig,
) -> tuple[R20TaskState, ...]:
    if plan is None:
        return ()
    completed = (
        {record.task_id for record in result.task_records if record.status == "completed"}
        if result is not None
        else set()
    )
    failed = (
        {record.task_id for record in result.task_records if record.status == "failed"}
        if result is not None
        else set()
    )
    states: list[R20TaskState] = []
    for task in plan.tasks:
        if task.task_id in completed:
            state = "completed"
        elif task.task_id in failed:
            state = "failed"
        else:
            state = "created"
        states.append(
            R20TaskState(
                task_id=task.task_id,
                generator=task.generator,
                state=state,
                dependencies=task.dependencies,
                retry_count=0 if state != "failed" else min(1, config.retry_limit),
                priority=task.priority,
                task_hash=specification_hash(task.model_dump(mode="json")),
            )
        )
    return tuple(sorted(states, key=lambda item: (item.priority, item.task_id)))


def _task_state(task: R20TaskState, state: str) -> R20TaskState:
    return R20TaskState(
        task_id=task.task_id,
        generator=task.generator,
        state=state,
        dependencies=task.dependencies,
        retry_count=task.retry_count + 1 if state == "retry" else task.retry_count,
        priority=task.priority,
        task_hash=task.task_hash,
    )


def _schedule(
    plan: R17ExecutionPlan | None,
    task_states: tuple[R20TaskState, ...],
    config: R20KernelConfig,
) -> tuple[R20ScheduleItem, ...]:
    if plan is None:
        return ()
    by_task = {task.task_id: task for task in plan.tasks}
    states = {item.task_id: item for item in task_states}
    items: list[R20ScheduleItem] = []
    for order, state in enumerate(task_states, start=1):
        task = by_task[state.task_id]
        dependencies_completed = all(
            states.get(dependency, state).state == "completed" for dependency in task.dependencies
        )
        dispatchable = state.state in {"created", "retry"} and dependencies_completed
        resource_claim = {
            "compute_units": task.estimated_cost.get("cpu", 1),
            "storage_mb": task.estimated_cost.get("storage", 1),
            "ai_model_capacity": max(1, task.estimated_cost.get("ai_tokens", 0) // 1000),
            "execution_slots": 1,
        }
        payload = {
            "task_id": task.task_id,
            "generator": task.generator,
            "stage_id": task.stage_id,
            "order": order,
            "dependency_ids": task.dependencies,
            "resource_claim": resource_claim,
            "policy_refs": config.policy_refs,
            "dispatchable": dispatchable,
        }
        items.append(
            R20ScheduleItem(
                schedule_id=f"r20-schedule-{specification_hash(payload)[:16]}",
                schedule_hash=specification_hash(payload),
                **payload,
            )
        )
    return tuple(items)


def _policy_decisions(
    manifest_hash: str | None,
    graph: dict[str, Any] | None,
    plan: R17ExecutionPlan | None,
    result: R18ExecutionResult | None,
    memory: R19MemoryStore | None,
) -> tuple[R20PolicyDecision, ...]:
    checks = (
        ("manifest", "validated_manifest_required", manifest_hash is not None),
        ("knowledge_graph", "graph_required", graph is not None and bool(graph.get("graph_hash"))),
        ("execution_plan", "approved_plan_required", plan is not None and not plan.diagnostics),
        (
            "artifacts",
            "traceability_required",
            result is None
            or all(
                artifact.manifest_origin and artifact.registry_reference
                for record in result.task_records
                for artifact in record.artifacts
            ),
        ),
        ("memory", "memory_store_hash_required", memory is None or bool(memory.store_hash)),
    )
    decisions: list[R20PolicyDecision] = []
    for subject, policy_type, allowed in checks:
        reasons = () if allowed else ({"code": f"{policy_type}.missing", "subject": subject},)
        payload = {
            "subject": subject,
            "policy_type": policy_type,
            "allowed": allowed,
            "reasons": reasons,
        }
        decision_hash = specification_hash(payload)
        decisions.append(
            R20PolicyDecision(
                decision_id=f"r20-policy-{decision_hash[:16]}",
                decision_hash=decision_hash,
                **payload,
            )
        )
    return tuple(decisions)


def _resource_allocation(project_id: str, config: R20KernelConfig) -> R20ResourceAllocation:
    payload = {
        "project_id": project_id,
        "max_parallel_tasks": config.max_parallel_tasks,
        "ai_model_capacity": config.resource_quotas.get("ai_model_capacity", 0),
        "compute_units": config.resource_quotas.get("compute_units", 0),
        "storage_mb": config.resource_quotas.get("storage_mb", 0),
        "cache_mb": config.resource_quotas.get("cache_mb", 0),
        "execution_slots": config.resource_quotas.get("execution_slots", 0),
        "temporary_workspace_ref": f"runtime://{project_id}/tmp",
    }
    return R20ResourceAllocation(**payload, allocation_hash=specification_hash(payload))


def _state(
    project_id: str,
    manifest_hash: str | None,
    graph: dict[str, Any] | None,
    plan: R17ExecutionPlan | None,
    result: R18ExecutionResult | None,
    task_states: tuple[R20TaskState, ...],
) -> R20RuntimeState:
    payload = {
        "project_id": project_id,
        "manifest_hash": manifest_hash,
        "graph_hash": str(graph.get("graph_hash")) if graph else None,
        "plan_hash": plan.plan_hash if plan else None,
        "running_tasks": tuple(item.task_id for item in task_states if item.state == "executing"),
        "completed_tasks": tuple(item.task_id for item in task_states if item.state == "completed"),
        "failed_tasks": tuple(item.task_id for item in task_states if item.state == "failed"),
        "pending_reviews": (
            tuple(gate.approval_id for gate in plan.approval_gates) if plan else ()
        ),
        "deployment_status": "observed" if result and result.status == "completed" else "pending",
        "state_version": 1,
    }
    return R20RuntimeState(**payload, state_hash=specification_hash(payload))


def _state_with_version(state: R20RuntimeState, version: int) -> R20RuntimeState:
    payload = state.model_dump(mode="json")
    payload.pop("state_hash")
    payload["state_version"] = version
    return R20RuntimeState(**payload, state_hash=specification_hash(payload))


def _state_from_tasks(
    state: R20RuntimeState,
    task_states: tuple[R20TaskState, ...],
) -> R20RuntimeState:
    payload = state.model_dump(mode="json")
    payload.pop("state_hash")
    payload["running_tasks"] = tuple(
        item.task_id for item in task_states if item.state == "executing"
    )
    payload["completed_tasks"] = tuple(
        item.task_id for item in task_states if item.state == "completed"
    )
    payload["failed_tasks"] = tuple(item.task_id for item in task_states if item.state == "failed")
    payload["state_version"] = int(payload["state_version"]) + 1
    return R20RuntimeState(**payload, state_hash=specification_hash(payload))


def _state_hash(state: R20RuntimeState) -> str:
    payload = state.model_dump(mode="json")
    payload.pop("state_hash")
    return specification_hash(payload)


def _health(
    schedule: tuple[R20ScheduleItem, ...],
    task_states: tuple[R20TaskState, ...],
    services: tuple[R20ServiceRegistration, ...],
) -> R20HealthSnapshot:
    failed = sum(1 for item in task_states if item.state == "failed")
    total = max(1, len(task_states))
    payload = {
        "cpu_units": sum(item.resource_claim.get("compute_units", 0) for item in schedule),
        "memory_mb": 0,
        "storage_mb": sum(item.resource_claim.get("storage_mb", 0) for item in schedule),
        "queue_size": sum(1 for item in schedule if item.dispatchable),
        "generator_available_count": sum(1 for item in services if item.interface == "IGenerator"),
        "execution_latency_ms": len(schedule) * 10,
        "failure_rate_basis_points": int((failed / total) * 10_000),
        "ready": failed == 0 and all(item.status == "available" for item in services),
    }
    return R20HealthSnapshot(**payload, health_hash=specification_hash(payload))


def _recovery_actions(
    task_states: tuple[R20TaskState, ...],
    services: tuple[R20ServiceRegistration, ...],
) -> tuple[R20RecoveryAction, ...]:
    actions: list[R20RecoveryAction] = []
    for task in task_states:
        if task.state == "failed":
            actions.append(_recovery("generator_failure", task.task_id, "retry_generator"))
    for service in services:
        if service.status != "available":
            actions.append(_recovery("service_failure", service.service_id, "restart_service"))
    return tuple(actions)


def _recovery(failure_category: str, target_id: str, action: str) -> R20RecoveryAction:
    payload = {
        "failure_category": failure_category,
        "target_id": target_id,
        "action": action,
        "deterministic": True,
    }
    recovery_hash = specification_hash(payload)
    return R20RecoveryAction(
        recovery_id=f"r20-recovery-{recovery_hash[:16]}",
        recovery_hash=recovery_hash,
        **payload,
    )


def _observability(
    events: tuple[R20RuntimeEvent, ...],
    schedule: tuple[R20ScheduleItem, ...],
    task_states: tuple[R20TaskState, ...],
    services: tuple[R20ServiceRegistration, ...],
) -> R20ObservabilitySnapshot:
    generator_utilization: dict[str, int] = {}
    for task in task_states:
        generator_utilization[task.generator] = generator_utilization.get(task.generator, 0) + 1
    metrics = {
        "event_count": len(events),
        "scheduled_task_count": len(schedule),
        "completed_task_count": sum(1 for item in task_states if item.state == "completed"),
        "failed_task_count": sum(1 for item in task_states if item.state == "failed"),
        "service_count": len(services),
    }
    payload = {
        "metrics": metrics,
        "traces": tuple(
            {"event_id": event.event_id, "event_type": event.event_type} for event in events
        ),
        "logs": tuple(
            {"event_hash": event.event_hash, "message": event.event_type} for event in events
        ),
        "execution_timeline": tuple(event.event_type for event in events),
        "dependency_graph_hash": specification_hash(
            {"schedule": [item.model_dump(mode="json") for item in schedule]}
        ),
        "generator_utilization": dict(sorted(generator_utilization.items())),
        "queue_statistics": {
            "dispatchable": sum(1 for item in schedule if item.dispatchable),
            "blocked": sum(1 for item in schedule if not item.dispatchable),
        },
    }
    return R20ObservabilitySnapshot(**payload, observability_hash=specification_hash(payload))


def _invariant_diagnostics(
    manifest_hash: str | None,
    graph: dict[str, Any] | None,
    plan: R17ExecutionPlan | None,
    result: R18ExecutionResult | None,
) -> tuple[R20KernelDiagnostic, ...]:
    diagnostics: list[R20KernelDiagnostic] = []
    if manifest_hash is None:
        diagnostics.append(_diag("fatal", "policy", "R20-MANIFEST-MISSING", "manifest_hash"))
    if graph is None or not graph.get("graph_hash"):
        diagnostics.append(_diag("fatal", "policy", "R20-GRAPH-MISSING", "graph"))
    if plan is None:
        diagnostics.append(_diag("fatal", "policy", "R20-PLAN-MISSING", "plan"))
    elif plan.diagnostics:
        diagnostics.append(_diag("fatal", "policy", "R20-PLAN-HAS-DIAGNOSTICS", plan.plan_id))
    if result is not None and result.status != "completed":
        diagnostics.append(
            _diag("fatal", "execution", "R20-EXECUTION-INCOMPLETE", result.execution_id)
        )
    return tuple(diagnostics)


def _snapshot(
    *,
    lifecycle: R20LifecycleSnapshot,
    config: R20KernelConfig,
    service_registry: tuple[R20ServiceRegistration, ...],
    event_history: tuple[R20RuntimeEvent, ...],
    state: R20RuntimeState,
    schedule: tuple[R20ScheduleItem, ...],
    task_states: tuple[R20TaskState, ...],
    policy_decisions: tuple[R20PolicyDecision, ...],
    resource_allocation: R20ResourceAllocation,
    health: R20HealthSnapshot,
    recovery_actions: tuple[R20RecoveryAction, ...],
    observability: R20ObservabilitySnapshot,
    diagnostics: tuple[R20KernelDiagnostic, ...],
) -> R20KernelSnapshot:
    payload = {
        "kernel_version": RUNTIME_KERNEL_VERSION,
        "lifecycle": lifecycle.model_dump(mode="json"),
        "config": config.model_dump(mode="json"),
        "service_registry": [item.model_dump(mode="json") for item in service_registry],
        "event_history": [item.model_dump(mode="json") for item in event_history],
        "state": state.model_dump(mode="json"),
        "schedule": [item.model_dump(mode="json") for item in schedule],
        "task_states": [item.model_dump(mode="json") for item in task_states],
        "policy_decisions": [item.model_dump(mode="json") for item in policy_decisions],
        "resource_allocation": resource_allocation.model_dump(mode="json"),
        "health": health.model_dump(mode="json"),
        "recovery_actions": [item.model_dump(mode="json") for item in recovery_actions],
        "observability": observability.model_dump(mode="json"),
        "diagnostics": [item.model_dump(mode="json") for item in diagnostics],
    }
    return R20KernelSnapshot(**payload, kernel_hash=specification_hash(payload))


def _coerce_snapshot(snapshot: dict[str, Any] | R20KernelSnapshot) -> R20KernelSnapshot:
    return (
        snapshot
        if isinstance(snapshot, R20KernelSnapshot)
        else R20KernelSnapshot.model_validate(snapshot)
    )


def _diag(
    severity: str,
    category: str,
    code: str,
    path: str,
) -> R20KernelDiagnostic:
    return R20KernelDiagnostic(
        severity=severity,
        category=category,
        code=code,
        message=f"{code} at {path}",
        path=path,
    )
