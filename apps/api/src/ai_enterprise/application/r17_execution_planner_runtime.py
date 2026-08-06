from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from ai_enterprise.application.r16_knowledge_graph_runtime import R16KnowledgeGraphModel
from ai_enterprise.domain.specification.kernel import specification_hash

PLANNER_VERSION = "execution-planner-1.0"
DETERMINISTIC_PLAN_TIMESTAMP = "1970-01-01T00:00:00Z"
DEFAULT_RESOURCE_LIMITS = {
    "cpu": 64,
    "memory": 131072,
    "storage": 100000,
    "ai_tokens": 2000000,
    "seconds": 86400,
}

PLANNING_STAGES: tuple[tuple[str, str], ...] = (
    ("foundation", "Foundation"),
    ("domain", "Domain"),
    ("backend", "Backend"),
    ("frontend", "Frontend"),
    ("infrastructure", "Infrastructure"),
    ("quality", "Quality"),
    ("deployment", "Deployment"),
)

GENERATOR_CATALOG: dict[str, dict[str, Any]] = {
    "foundation.setup": {
        "generator": "planner.foundation",
        "node_types": ("domain",),
        "outputs": ("project-foundation",),
    },
    "domain.model": {
        "generator": "generator.database",
        "node_types": ("entity", "attribute"),
        "outputs": ("schema", "repository-contract"),
    },
    "backend.service": {
        "generator": "generator.backend",
        "node_types": ("capability", "workflow", "integration"),
        "outputs": ("service", "api-contract"),
    },
    "frontend.surface": {
        "generator": "generator.frontend",
        "node_types": ("role", "report", "ui_view", "notification"),
        "outputs": ("ui-view", "report-surface"),
    },
    "infrastructure.policy": {
        "generator": "generator.infrastructure",
        "node_types": ("policy", "business_rule", "rule", "constraint", "security", "quality"),
        "outputs": ("policy-as-code", "infrastructure-requirement"),
    },
    "quality.validation": {
        "generator": "validator.quality",
        "node_types": ("domain", "entity", "capability", "workflow", "report"),
        "outputs": ("validation-evidence",),
    },
    "deployment.package": {
        "generator": "generator.deployment",
        "node_types": ("domain",),
        "outputs": ("deployment-package",),
    },
}


class R17PlanningDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True)

    severity: str
    category: str
    code: str
    message: str
    path: str


class R17ExecutionTask(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: str
    task_type: str
    stage_id: str
    generator: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    dependencies: tuple[str, ...]
    estimated_cost: dict[str, int]
    priority: int
    retry_policy: dict[str, int]
    validation_rule: str
    knowledge_node_id: str
    knowledge_node_type: str
    required_permissions: tuple[str, ...]
    execution_context: dict[str, str]
    explainability: dict[str, Any]


class R17ExecutionStage(BaseModel):
    model_config = ConfigDict(frozen=True)

    stage_id: str
    name: str
    task_ids: tuple[str, ...]
    depends_on: tuple[str, ...]
    synchronization_barrier: str
    completion_criteria: tuple[str, ...]


class R17ExecutionDependency(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_task_id: str
    target_task_id: str
    reason: str
    trace_edge_id: str | None


class R17ValidationGate(BaseModel):
    model_config = ConfigDict(frozen=True)

    gate_id: str
    stage_id: str
    required_task_ids: tuple[str, ...]
    validation_rule: str
    blocks_downstream: bool


class R17ParallelGroup(BaseModel):
    model_config = ConfigDict(frozen=True)

    group_id: str
    stage_id: str
    task_ids: tuple[str, ...]
    max_parallel_jobs: int


class R17RollbackPoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    rollback_id: str
    stage_id: str
    checkpoint_name: str
    restore_task_ids: tuple[str, ...]
    audit_required: bool


class R17ApprovalGate(BaseModel):
    model_config = ConfigDict(frozen=True)

    approval_id: str
    stage_id: str
    approval_type: str
    required_before: str
    required_task_ids: tuple[str, ...]
    policy_reference: str
    manual: bool


class R17GeneratorPermission(BaseModel):
    model_config = ConfigDict(frozen=True)

    generator: str
    allowed_task_types: tuple[str, ...]
    allowed_node_types: tuple[str, ...]
    allowed_stages: tuple[str, ...]
    allowed_outputs: tuple[str, ...]
    isolation_profile: str


class R17ExecutionPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy_id: str
    max_parallel_jobs: int
    require_manual_deployment_approval: bool
    require_security_review: bool
    resource_limits: dict[str, int]
    scheduling_strategy: str
    distributed_planning_enabled: bool


class R17ResourceSchedule(BaseModel):
    model_config = ConfigDict(frozen=True)

    stage_id: str
    task_ids: tuple[str, ...]
    max_parallel_jobs: int
    estimated_resources: dict[str, int]
    resource_limits: dict[str, int]
    capacity_exceeded: bool
    scheduling_strategy: str


class R17DecisionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_id: str
    category: str
    subject: str
    rationale: str
    evidence: dict[str, Any]


class R17DistributedPlanningProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool
    partition_count: int
    partition_strategy: str
    deterministic_merge_key: str
    max_partition_task_count: int


class R17IncrementalPlanImpact(BaseModel):
    model_config = ConfigDict(frozen=True)

    previous_plan_hash: str | None
    added_task_ids: tuple[str, ...]
    removed_task_ids: tuple[str, ...]
    changed_task_ids: tuple[str, ...]
    reusable_task_ids: tuple[str, ...]
    impact_hash: str


class R17ExecutionPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    plan_id: str
    planner_version: str
    execution_version: str
    compiler_version: str | None
    graph_version: str
    registry_version: str | None
    created_at: str
    stages: tuple[R17ExecutionStage, ...]
    tasks: tuple[R17ExecutionTask, ...]
    dependencies: tuple[R17ExecutionDependency, ...]
    validation_gates: tuple[R17ValidationGate, ...]
    parallel_groups: tuple[R17ParallelGroup, ...]
    rollback_points: tuple[R17RollbackPoint, ...]
    approval_gates: tuple[R17ApprovalGate, ...]
    generator_permissions: tuple[R17GeneratorPermission, ...]
    execution_policy: R17ExecutionPolicy
    resource_schedule: tuple[R17ResourceSchedule, ...]
    distributed_planning: R17DistributedPlanningProfile
    decision_log: tuple[R17DecisionRecord, ...]
    outputs: tuple[str, ...]
    metrics: dict[str, int]
    incremental_impact: R17IncrementalPlanImpact
    diagnostics: tuple[R17PlanningDiagnostic, ...]
    plan_hash: str
    plan_signature: str


class R17PlanValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    diagnostics: tuple[R17PlanningDiagnostic, ...]
    report_hash: str


def r17_create_execution_plan(
    graph: dict[str, Any] | R16KnowledgeGraphModel,
    *,
    planning_options: dict[str, Any] | None = None,
) -> R17ExecutionPlan:
    options = planning_options or {}
    model = (
        graph
        if isinstance(graph, R16KnowledgeGraphModel)
        else R16KnowledgeGraphModel.model_validate(graph)
    )
    execution_policy = _execution_policy(options)
    generator_permissions = _generator_permissions(options)
    max_parallel_jobs = execution_policy.max_parallel_jobs
    timestamp = str(options.get("planning_timestamp", DETERMINISTIC_PLAN_TIMESTAMP))
    tasks = _tasks(model, options, generator_permissions)
    dependencies = _dependencies(model, tasks)
    stages = _stages(tasks)
    gates = _validation_gates(stages)
    parallel_groups = _parallel_groups(stages, max_parallel_jobs)
    rollback_points = _rollback_points(stages)
    approval_gates = _approval_gates(stages, tasks, execution_policy)
    resource_schedule = _resource_schedule(stages, tasks, execution_policy)
    distributed_planning = _distributed_planning_profile(tasks, execution_policy, options)
    decision_log = _decision_log(
        tasks,
        dependencies,
        gates,
        rollback_points,
        approval_gates,
        resource_schedule,
        execution_policy,
        distributed_planning,
    )
    diagnostics = _diagnostics(
        tasks,
        dependencies,
        gates,
        rollback_points,
        approval_gates,
        generator_permissions,
        execution_policy,
        resource_schedule,
    )
    impact = _incremental_impact(tasks, options.get("previous_plan"))
    metrics = {
        "stage_count": len(stages),
        "task_count": len(tasks),
        "dependency_count": len(dependencies),
        "parallel_group_count": len(parallel_groups),
        "validation_gate_count": len(gates),
        "rollback_point_count": len(rollback_points),
        "estimated_cpu": sum(task.estimated_cost["cpu"] for task in tasks),
        "estimated_memory": sum(task.estimated_cost["memory"] for task in tasks),
        "estimated_storage": sum(task.estimated_cost["storage"] for task in tasks),
        "estimated_ai_tokens": sum(task.estimated_cost["ai_tokens"] for task in tasks),
        "estimated_seconds": sum(task.estimated_cost["seconds"] for task in tasks),
    }
    unsigned = {
        "planner_version": PLANNER_VERSION,
        "execution_version": str(options.get("execution_version", "1.0.0")),
        "compiler_version": model.metadata.get("compiler_version"),
        "graph_version": model.graph_version,
        "registry_version": model.metadata.get("registry_version"),
        "created_at": timestamp,
        "stages": [item.model_dump(mode="json") for item in stages],
        "tasks": [item.model_dump(mode="json") for item in tasks],
        "dependencies": [item.model_dump(mode="json") for item in dependencies],
        "validation_gates": [item.model_dump(mode="json") for item in gates],
        "parallel_groups": [item.model_dump(mode="json") for item in parallel_groups],
        "rollback_points": [item.model_dump(mode="json") for item in rollback_points],
        "approval_gates": [item.model_dump(mode="json") for item in approval_gates],
        "generator_permissions": [item.model_dump(mode="json") for item in generator_permissions],
        "execution_policy": execution_policy.model_dump(mode="json"),
        "resource_schedule": [item.model_dump(mode="json") for item in resource_schedule],
        "distributed_planning": distributed_planning.model_dump(mode="json"),
        "decision_log": [item.model_dump(mode="json") for item in decision_log],
        "outputs": sorted({output for task in tasks for output in task.outputs}),
        "metrics": metrics,
        "incremental_impact": impact.model_dump(mode="json"),
        "diagnostics": [item.model_dump(mode="json") for item in diagnostics],
    }
    plan_hash = specification_hash(unsigned)
    return R17ExecutionPlan(
        plan_id=f"plan-{model.graph_version}-{plan_hash[:12]}",
        plan_hash=plan_hash,
        plan_signature=specification_hash(
            {"plan_hash": plan_hash, "planner_version": PLANNER_VERSION}
        ),
        **unsigned,
    )


def r17_validate_execution_plan(plan: R17ExecutionPlan) -> R17PlanValidationReport:
    diagnostics = _diagnostics(
        plan.tasks,
        plan.dependencies,
        plan.validation_gates,
        plan.rollback_points,
        plan.approval_gates,
        plan.generator_permissions,
        plan.execution_policy,
        plan.resource_schedule,
    )
    actual_hash = specification_hash(_unsigned_payload(plan))
    if plan.plan_hash != actual_hash:
        diagnostics = (
            *diagnostics,
            R17PlanningDiagnostic(
                severity="fatal",
                category="security",
                code="R17-PLAN-HASH-MISMATCH",
                message="Execution plan hash does not match the plan body.",
                path="plan_hash",
            ),
        )
    expected_signature = specification_hash(
        {"plan_hash": plan.plan_hash, "planner_version": plan.planner_version}
    )
    if plan.plan_signature != expected_signature:
        diagnostics = (
            *diagnostics,
            R17PlanningDiagnostic(
                severity="fatal",
                category="security",
                code="R17-INVALID-SIGNATURE",
                message="Execution plan signature does not match the plan hash.",
                path="plan_signature",
            ),
        )
    payload = {
        "valid": not diagnostics,
        "diagnostics": [item.model_dump(mode="json") for item in diagnostics],
    }
    return R17PlanValidationReport(
        valid=not diagnostics,
        diagnostics=tuple(diagnostics),
        report_hash=specification_hash(payload),
    )


def r17_persist_execution_plan(
    plan: R17ExecutionPlan,
    history_path: Path,
    *,
    actor_id: str,
) -> str:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": "r17-execution-plan-history-1.0",
        "actor_id": actor_id,
        "plan_id": plan.plan_id,
        "plan_hash": plan.plan_hash,
        "plan_signature": plan.plan_signature,
        "graph_version": plan.graph_version,
        "task_count": len(plan.tasks),
    }
    record_hash = specification_hash(record)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({**record, "record_hash": record_hash}, sort_keys=True))
        handle.write("\n")
    return record_hash


def r17_read_execution_plan_history(history_path: Path) -> tuple[dict[str, Any], ...]:
    if not history_path.exists():
        return ()
    records: list[dict[str, Any]] = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            records.append(item)
    return tuple(records)


def _execution_policy(options: dict[str, Any]) -> R17ExecutionPolicy:
    resource_limits = {
        **DEFAULT_RESOURCE_LIMITS,
        **{
            str(key): int(value)
            for key, value in dict(options.get("resource_limits", {})).items()
            if str(key) in DEFAULT_RESOURCE_LIMITS
        },
    }
    max_parallel_jobs = max(1, int(options.get("max_parallel_jobs", 4)))
    return R17ExecutionPolicy(
        policy_id=str(options.get("policy_id", "r17.default.enterprise")),
        max_parallel_jobs=max_parallel_jobs,
        require_manual_deployment_approval=options.get("require_manual_deployment_approval", True)
        is True,
        require_security_review=options.get("require_security_review", True) is True,
        resource_limits=resource_limits,
        scheduling_strategy=str(options.get("scheduling_strategy", "stage-resource-bounded")),
        distributed_planning_enabled=options.get("distributed_planning_enabled", False) is True,
    )


def _generator_permissions(
    options: dict[str, Any],
) -> tuple[R17GeneratorPermission, ...]:
    custom_permissions = options.get("generator_permissions")
    if isinstance(custom_permissions, list):
        return tuple(
            sorted(
                (
                    R17GeneratorPermission.model_validate(item)
                    for item in custom_permissions
                    if isinstance(item, dict)
                ),
                key=lambda item: item.generator,
            )
        )

    permissions: dict[str, dict[str, set[str]]] = {}
    for task_type, spec in GENERATOR_CATALOG.items():
        generator = str(spec["generator"])
        entry = permissions.setdefault(
            generator,
            {
                "allowed_task_types": set(),
                "allowed_node_types": set(),
                "allowed_stages": set(),
                "allowed_outputs": set(),
            },
        )
        entry["allowed_task_types"].add(task_type)
        entry["allowed_node_types"].update(str(item) for item in spec["node_types"])
        entry["allowed_stages"].add(_stage_for_task_type(task_type))
        entry["allowed_outputs"].update(str(item) for item in spec["outputs"])

    return tuple(
        R17GeneratorPermission(
            generator=generator,
            allowed_task_types=tuple(sorted(entry["allowed_task_types"])),
            allowed_node_types=tuple(sorted(entry["allowed_node_types"])),
            allowed_stages=tuple(sorted(entry["allowed_stages"], key=_stage_index)),
            allowed_outputs=tuple(sorted(entry["allowed_outputs"])),
            isolation_profile=_isolation_profile(generator),
        )
        for generator, entry in sorted(permissions.items())
    )


def _unsigned_payload(plan: R17ExecutionPlan) -> dict[str, Any]:
    return {
        "planner_version": plan.planner_version,
        "execution_version": plan.execution_version,
        "compiler_version": plan.compiler_version,
        "graph_version": plan.graph_version,
        "registry_version": plan.registry_version,
        "created_at": plan.created_at,
        "stages": [item.model_dump(mode="json") for item in plan.stages],
        "tasks": [item.model_dump(mode="json") for item in plan.tasks],
        "dependencies": [item.model_dump(mode="json") for item in plan.dependencies],
        "validation_gates": [item.model_dump(mode="json") for item in plan.validation_gates],
        "parallel_groups": [item.model_dump(mode="json") for item in plan.parallel_groups],
        "rollback_points": [item.model_dump(mode="json") for item in plan.rollback_points],
        "approval_gates": [item.model_dump(mode="json") for item in plan.approval_gates],
        "generator_permissions": [
            item.model_dump(mode="json") for item in plan.generator_permissions
        ],
        "execution_policy": plan.execution_policy.model_dump(mode="json"),
        "resource_schedule": [item.model_dump(mode="json") for item in plan.resource_schedule],
        "distributed_planning": plan.distributed_planning.model_dump(mode="json"),
        "decision_log": [item.model_dump(mode="json") for item in plan.decision_log],
        "outputs": list(plan.outputs),
        "metrics": plan.metrics,
        "incremental_impact": plan.incremental_impact.model_dump(mode="json"),
        "diagnostics": [item.model_dump(mode="json") for item in plan.diagnostics],
    }


def _tasks(
    graph: R16KnowledgeGraphModel,
    options: dict[str, Any],
    generator_permissions: tuple[R17GeneratorPermission, ...],
) -> tuple[R17ExecutionTask, ...]:
    security_first = options.get("security_first", True) is True
    permissions_by_generator = {item.generator: item for item in generator_permissions}
    tasks: list[R17ExecutionTask] = []
    for node in sorted(graph.nodes, key=lambda item: (str(item["type"]), str(item["id"]))):
        node_type = str(node["type"])
        for task_type, spec in GENERATOR_CATALOG.items():
            if node_type not in spec["node_types"]:
                continue
            stage_id = _stage_for_task_type(task_type)
            priority = _priority(stage_id, node_type, security_first)
            task_id = f"{stage_id}:{task_type}:{node['id']}"
            knowledge_node_hash = specification_hash(node)
            generator = str(spec["generator"])
            permission = permissions_by_generator[generator]
            tasks.append(
                R17ExecutionTask(
                    task_id=task_id,
                    task_type=task_type,
                    stage_id=stage_id,
                    generator=generator,
                    inputs=(str(node["id"]), graph.graph_hash, knowledge_node_hash),
                    outputs=tuple(str(output) for output in spec["outputs"]),
                    dependencies=(),
                    estimated_cost=_estimated_cost(node_type, task_type),
                    priority=priority,
                    retry_policy={"max_attempts": 2, "backoff_seconds": 30},
                    validation_rule=f"validate.{stage_id}.{node_type}",
                    knowledge_node_id=str(node["id"]),
                    knowledge_node_type=node_type,
                    required_permissions=(
                        f"generator:{generator}",
                        f"stage:{stage_id}",
                        f"node:{node_type}",
                    ),
                    execution_context={
                        "isolation_profile": permission.isolation_profile,
                        "network_policy": "deny-by-default",
                        "workspace_scope": f"task:{task_id}",
                    },
                    explainability={
                        "why": f"Create {task_type} output for {node_type} {node['id']}.",
                        "manifest_origin": node["traceability"]["manifest_origin"],
                        "registry_reference": node["traceability"]["registry_reference"],
                        "knowledge_node_id": node["id"],
                        "knowledge_node_hash": knowledge_node_hash,
                        "generator": spec["generator"],
                        "artifacts": list(spec["outputs"]),
                    },
                )
            )
    return tuple(sorted(tasks, key=lambda item: (item.stage_id, item.priority, item.task_id)))


def _dependencies(
    graph: R16KnowledgeGraphModel,
    tasks: tuple[R17ExecutionTask, ...],
) -> tuple[R17ExecutionDependency, ...]:
    by_node_stage = {(task.knowledge_node_id, task.stage_id): task for task in tasks}
    node_tasks = {}
    for task in tasks:
        node_tasks.setdefault(task.knowledge_node_id, []).append(task)
    dependencies: list[R17ExecutionDependency] = []
    for stage, next_stage in zip(_stage_ids(), _stage_ids()[1:], strict=False):
        for task in (item for item in tasks if item.stage_id == next_stage):
            previous = by_node_stage.get((task.knowledge_node_id, stage))
            if previous:
                dependencies.append(
                    _dependency(previous.task_id, task.task_id, "stage_order", None)
                )
    for edge in graph.edges:
        if edge["relationship_type"] not in {
            "depends_on",
            "uses",
            "consumes",
            "constrains",
            "secures",
        }:
            continue
        source_tasks = node_tasks.get(str(edge["source"]), [])
        target_tasks = node_tasks.get(str(edge["target"]), [])
        for source in source_tasks:
            for target in target_tasks:
                if _stage_index(source.stage_id) > _stage_index(target.stage_id):
                    dependencies.append(
                        _dependency(
                            target.task_id,
                            source.task_id,
                            f"knowledge_edge:{edge['relationship_type']}",
                            str(edge["id"]),
                        )
                    )
    return _unique_dependencies(dependencies)


def _stages(tasks: tuple[R17ExecutionTask, ...]) -> tuple[R17ExecutionStage, ...]:
    stage_dependencies: dict[str, set[str]] = {stage: set() for stage in _stage_ids()}
    for stage, next_stage in zip(_stage_ids(), _stage_ids()[1:], strict=False):
        stage_dependencies[next_stage].add(stage)
    return tuple(
        R17ExecutionStage(
            stage_id=stage_id,
            name=name,
            task_ids=tuple(task.task_id for task in tasks if task.stage_id == stage_id),
            depends_on=tuple(sorted(stage_dependencies[stage_id])),
            synchronization_barrier=f"{stage_id}.complete",
            completion_criteria=(f"all {stage_id} tasks succeeded",),
        )
        for stage_id, name in PLANNING_STAGES
    )


def _validation_gates(stages: tuple[R17ExecutionStage, ...]) -> tuple[R17ValidationGate, ...]:
    return tuple(
        R17ValidationGate(
            gate_id=f"gate:{stage.stage_id}",
            stage_id=stage.stage_id,
            required_task_ids=stage.task_ids,
            validation_rule=f"validate.stage.{stage.stage_id}",
            blocks_downstream=True,
        )
        for stage in stages
    )


def _parallel_groups(
    stages: tuple[R17ExecutionStage, ...],
    max_parallel_jobs: int,
) -> tuple[R17ParallelGroup, ...]:
    return tuple(
        R17ParallelGroup(
            group_id=f"parallel:{stage.stage_id}",
            stage_id=stage.stage_id,
            task_ids=stage.task_ids,
            max_parallel_jobs=max(1, min(max_parallel_jobs, len(stage.task_ids) or 1)),
        )
        for stage in stages
    )


def _rollback_points(stages: tuple[R17ExecutionStage, ...]) -> tuple[R17RollbackPoint, ...]:
    return tuple(
        R17RollbackPoint(
            rollback_id=f"rollback:{stage.stage_id}",
            stage_id=stage.stage_id,
            checkpoint_name=f"{stage.name} Checkpoint",
            restore_task_ids=stage.task_ids,
            audit_required=True,
        )
        for stage in stages
    )


def _approval_gates(
    stages: tuple[R17ExecutionStage, ...],
    tasks: tuple[R17ExecutionTask, ...],
    policy: R17ExecutionPolicy,
) -> tuple[R17ApprovalGate, ...]:
    gates: list[R17ApprovalGate] = []
    tasks_by_stage = {
        stage.stage_id: tuple(task.task_id for task in tasks if task.stage_id == stage.stage_id)
        for stage in stages
    }
    if policy.require_security_review:
        security_tasks = tuple(
            task.task_id
            for task in tasks
            if task.knowledge_node_type in {"security", "constraint", "policy"}
        )
        if security_tasks:
            gates.append(
                R17ApprovalGate(
                    approval_id="approval:security-review",
                    stage_id="infrastructure",
                    approval_type="security_review",
                    required_before="deployment",
                    required_task_ids=security_tasks,
                    policy_reference=policy.policy_id,
                    manual=True,
                )
            )
    if policy.require_manual_deployment_approval and tasks_by_stage.get("deployment"):
        gates.append(
            R17ApprovalGate(
                approval_id="approval:deployment-release",
                stage_id="deployment",
                approval_type="manual_deployment_release",
                required_before="deployment.execute",
                required_task_ids=tasks_by_stage["deployment"],
                policy_reference=policy.policy_id,
                manual=True,
            )
        )
    return tuple(sorted(gates, key=lambda item: item.approval_id))


def _resource_schedule(
    stages: tuple[R17ExecutionStage, ...],
    tasks: tuple[R17ExecutionTask, ...],
    policy: R17ExecutionPolicy,
) -> tuple[R17ResourceSchedule, ...]:
    by_id = {task.task_id: task for task in tasks}
    schedules: list[R17ResourceSchedule] = []
    for stage in stages:
        stage_tasks = tuple(by_id[task_id] for task_id in stage.task_ids if task_id in by_id)
        estimated = {
            key: sum(task.estimated_cost.get(key, 0) for task in stage_tasks)
            for key in policy.resource_limits
        }
        capacity_exceeded = any(
            estimated[key] > policy.resource_limits[key] for key in policy.resource_limits
        )
        schedules.append(
            R17ResourceSchedule(
                stage_id=stage.stage_id,
                task_ids=stage.task_ids,
                max_parallel_jobs=max(1, min(policy.max_parallel_jobs, len(stage.task_ids) or 1)),
                estimated_resources=estimated,
                resource_limits=policy.resource_limits,
                capacity_exceeded=capacity_exceeded,
                scheduling_strategy=policy.scheduling_strategy,
            )
        )
    return tuple(schedules)


def _distributed_planning_profile(
    tasks: tuple[R17ExecutionTask, ...],
    policy: R17ExecutionPolicy,
    options: dict[str, Any],
) -> R17DistributedPlanningProfile:
    max_partition_task_count = max(1, int(options.get("max_partition_task_count", 250)))
    partition_count = max(
        1, (len(tasks) + max_partition_task_count - 1) // max_partition_task_count
    )
    return R17DistributedPlanningProfile(
        enabled=policy.distributed_planning_enabled,
        partition_count=partition_count,
        partition_strategy=str(options.get("partition_strategy", "stage-then-task-id")),
        deterministic_merge_key="stage_id:priority:task_id",
        max_partition_task_count=max_partition_task_count,
    )


def _decision_log(
    tasks: tuple[R17ExecutionTask, ...],
    dependencies: tuple[R17ExecutionDependency, ...],
    gates: tuple[R17ValidationGate, ...],
    rollback_points: tuple[R17RollbackPoint, ...],
    approval_gates: tuple[R17ApprovalGate, ...],
    resource_schedule: tuple[R17ResourceSchedule, ...],
    policy: R17ExecutionPolicy,
    distributed_planning: R17DistributedPlanningProfile,
) -> tuple[R17DecisionRecord, ...]:
    records = (
        R17DecisionRecord(
            decision_id="decision:generator-assignment",
            category="generator",
            subject="all_tasks",
            rationale=(
                "Tasks are assigned from the immutable R17 generator catalog "
                "by knowledge node type."
            ),
            evidence={"task_count": len(tasks), "catalog_size": len(GENERATOR_CATALOG)},
        ),
        R17DecisionRecord(
            decision_id="decision:dependency-ordering",
            category="planning",
            subject="execution_dag",
            rationale=(
                "Stage-order and knowledge-graph edges define deterministic task dependencies."
            ),
            evidence={"dependency_count": len(dependencies)},
        ),
        R17DecisionRecord(
            decision_id="decision:validation-and-rollback",
            category="policy",
            subject="stage_boundaries",
            rationale=(
                "Every populated stage receives a blocking validation gate and rollback checkpoint."
            ),
            evidence={
                "validation_gate_count": len(gates),
                "rollback_point_count": len(rollback_points),
            },
        ),
        R17DecisionRecord(
            decision_id="decision:approval-policy",
            category="approval",
            subject=policy.policy_id,
            rationale=(
                "Manual approval gates are derived from execution policy "
                "before sensitive release stages."
            ),
            evidence={"approval_gate_count": len(approval_gates)},
        ),
        R17DecisionRecord(
            decision_id="decision:resource-schedule",
            category="scheduling",
            subject=policy.scheduling_strategy,
            rationale=(
                "Stage schedules are bounded by policy max parallelism "
                "and declared resource limits."
            ),
            evidence={
                "schedule_count": len(resource_schedule),
                "max_parallel_jobs": policy.max_parallel_jobs,
            },
        ),
        R17DecisionRecord(
            decision_id="decision:distributed-profile",
            category="planning",
            subject="distributed_planning",
            rationale=(
                "Distributed planning metadata is deterministic and partitioned "
                "without changing semantics."
            ),
            evidence=distributed_planning.model_dump(mode="json"),
        ),
    )
    return tuple(records)


def _diagnostics(
    tasks: tuple[R17ExecutionTask, ...],
    dependencies: tuple[R17ExecutionDependency, ...],
    gates: tuple[R17ValidationGate, ...],
    rollback_points: tuple[R17RollbackPoint, ...],
    approval_gates: tuple[R17ApprovalGate, ...],
    generator_permissions: tuple[R17GeneratorPermission, ...],
    execution_policy: R17ExecutionPolicy,
    resource_schedule: tuple[R17ResourceSchedule, ...],
) -> tuple[R17PlanningDiagnostic, ...]:
    diagnostics: list[R17PlanningDiagnostic] = []
    task_ids = {task.task_id for task in tasks}
    catalog_by_task_type = GENERATOR_CATALOG
    permissions_by_generator = {item.generator: item for item in generator_permissions}
    for task in tasks:
        catalog_spec = catalog_by_task_type.get(task.task_type)
        if catalog_spec is None:
            diagnostics.append(_diag("fatal", "generator", "R17-TASK-TYPE-UNKNOWN", task.task_id))
            continue
        if task.generator != catalog_spec["generator"]:
            diagnostics.append(_diag("fatal", "generator", "R17-GENERATOR-MISMATCH", task.task_id))
        if task.generator not in {spec["generator"] for spec in GENERATOR_CATALOG.values()}:
            diagnostics.append(_diag("fatal", "generator", "R17-GENERATOR-MISSING", task.task_id))
        permission = permissions_by_generator.get(task.generator)
        if permission is None:
            diagnostics.append(
                _diag("fatal", "security", "R17-GENERATOR-PERMISSION-MISSING", task.task_id)
            )
            continue
        if (
            task.task_type not in permission.allowed_task_types
            or task.knowledge_node_type not in permission.allowed_node_types
            or task.stage_id not in permission.allowed_stages
            or not set(task.outputs).issubset(set(permission.allowed_outputs))
        ):
            diagnostics.append(
                _diag("fatal", "security", "R17-GENERATOR-PERMISSION-DENIED", task.task_id)
            )
        if task.execution_context.get("isolation_profile") != permission.isolation_profile:
            diagnostics.append(
                _diag("fatal", "security", "R17-EXECUTION-ISOLATION-MISMATCH", task.task_id)
            )
        if not set(task.required_permissions).issuperset(
            {
                f"generator:{task.generator}",
                f"stage:{task.stage_id}",
                f"node:{task.knowledge_node_type}",
            }
        ):
            diagnostics.append(
                _diag("fatal", "security", "R17-REQUIRED-PERMISSION-MISSING", task.task_id)
            )
    for dependency in dependencies:
        if dependency.source_task_id not in task_ids or dependency.target_task_id not in task_ids:
            diagnostics.append(
                _diag(
                    "fatal",
                    "planning",
                    "R17-DEPENDENCY-MISSING",
                    dependency.target_task_id,
                )
            )
    if _task_cycles(dependencies):
        diagnostics.append(_diag("fatal", "planning", "R17-CIRCULAR-EXECUTION", "dependencies"))
    gate_stages = {gate.stage_id for gate in gates if gate.required_task_ids}
    missing_gate_stages = {task.stage_id for task in tasks} - gate_stages
    for stage_id in sorted(missing_gate_stages):
        diagnostics.append(_diag("fatal", "policy", "R17-GATE-MISSING", stage_id))
    rollback_stages = {item.stage_id for item in rollback_points}
    for stage_id in sorted({task.stage_id for task in tasks} - rollback_stages):
        diagnostics.append(_diag("fatal", "planning", "R17-ROLLBACK-MISSING", stage_id))
    if execution_policy.require_manual_deployment_approval:
        deployment_tasks = {task.task_id for task in tasks if task.stage_id == "deployment"}
        deployment_approvals = {
            task_id
            for gate in approval_gates
            if gate.approval_type == "manual_deployment_release"
            for task_id in gate.required_task_ids
        }
        if deployment_tasks and not deployment_tasks.issubset(deployment_approvals):
            diagnostics.append(
                _diag("fatal", "policy", "R17-DEPLOYMENT-APPROVAL-MISSING", "deployment")
            )
    if execution_policy.require_security_review:
        security_tasks = {
            task.task_id
            for task in tasks
            if task.knowledge_node_type in {"security", "constraint", "policy"}
        }
        security_approvals = {
            task_id
            for gate in approval_gates
            if gate.approval_type == "security_review"
            for task_id in gate.required_task_ids
        }
        if security_tasks and not security_tasks.issubset(security_approvals):
            diagnostics.append(
                _diag("fatal", "policy", "R17-SECURITY-APPROVAL-MISSING", "security")
            )
    for schedule in resource_schedule:
        if schedule.max_parallel_jobs > execution_policy.max_parallel_jobs:
            diagnostics.append(
                _diag("fatal", "scheduling", "R17-PARALLEL-LIMIT-EXCEEDED", schedule.stage_id)
            )
        if schedule.capacity_exceeded:
            diagnostics.append(
                _diag("fatal", "scheduling", "R17-RESOURCE-BUDGET-EXCEEDED", schedule.stage_id)
            )
    return tuple(sorted(diagnostics, key=lambda item: (item.code, item.path)))


def _incremental_impact(
    tasks: tuple[R17ExecutionTask, ...],
    previous_plan: object,
) -> R17IncrementalPlanImpact:
    previous = previous_plan if isinstance(previous_plan, dict) else {}
    previous_tasks = {
        str(task["task_id"]): specification_hash(task)
        for task in previous.get("tasks", [])
        if isinstance(task, dict) and isinstance(task.get("task_id"), str)
    }
    current_tasks = {
        task.task_id: specification_hash(task.model_dump(mode="json")) for task in tasks
    }
    payload = {
        "previous_plan_hash": previous.get("plan_hash"),
        "added_task_ids": tuple(sorted(set(current_tasks) - set(previous_tasks))),
        "removed_task_ids": tuple(sorted(set(previous_tasks) - set(current_tasks))),
        "changed_task_ids": tuple(
            sorted(
                key
                for key in set(previous_tasks) & set(current_tasks)
                if previous_tasks[key] != current_tasks[key]
            )
        ),
        "reusable_task_ids": tuple(
            sorted(
                key
                for key in set(previous_tasks) & set(current_tasks)
                if previous_tasks[key] == current_tasks[key]
            )
        ),
    }
    return R17IncrementalPlanImpact(**payload, impact_hash=specification_hash(payload))


def _dependency(
    source: str,
    target: str,
    reason: str,
    trace_edge_id: str | None,
) -> R17ExecutionDependency:
    return R17ExecutionDependency(
        source_task_id=source,
        target_task_id=target,
        reason=reason,
        trace_edge_id=trace_edge_id,
    )


def _unique_dependencies(
    dependencies: list[R17ExecutionDependency],
) -> tuple[R17ExecutionDependency, ...]:
    unique = {
        (item.source_task_id, item.target_task_id, item.reason): item
        for item in dependencies
        if item.source_task_id != item.target_task_id
    }
    return tuple(unique[key] for key in sorted(unique))


def _task_cycles(dependencies: tuple[R17ExecutionDependency, ...]) -> tuple[tuple[str, ...], ...]:
    graph: dict[str, set[str]] = {}
    for item in dependencies:
        graph.setdefault(item.source_task_id, set()).add(item.target_task_id)
        graph.setdefault(item.target_task_id, set())
    cycles: set[tuple[str, ...]] = set()
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            start = visiting.index(node)
            cycles.add(tuple(visiting[start:] + [node]))
            return
        if node in visited:
            return
        visiting.append(node)
        for target in sorted(graph.get(node, set())):
            visit(target)
        visiting.pop()
        visited.add(node)

    for node in sorted(graph):
        visit(node)
    return tuple(sorted(cycles))


def _stage_for_task_type(task_type: str) -> str:
    return {
        "foundation.setup": "foundation",
        "domain.model": "domain",
        "backend.service": "backend",
        "frontend.surface": "frontend",
        "infrastructure.policy": "infrastructure",
        "quality.validation": "quality",
        "deployment.package": "deployment",
    }[task_type]


def _stage_ids() -> tuple[str, ...]:
    return tuple(stage_id for stage_id, _ in PLANNING_STAGES)


def _stage_index(stage_id: str) -> int:
    return _stage_ids().index(stage_id)


def _priority(stage_id: str, node_type: str, security_first: bool) -> int:
    base = (_stage_index(stage_id) + 1) * 100
    if security_first and node_type in {"security", "constraint", "policy"}:
        return base - 10
    return base


def _isolation_profile(generator: str) -> str:
    if generator in {"generator.infrastructure", "generator.deployment"}:
        return "privileged-plan-only"
    if generator == "validator.quality":
        return "read-only-validation"
    return "sandboxed-generator"


def _estimated_cost(node_type: str, task_type: str) -> dict[str, int]:
    weight = len(node_type) + len(task_type)
    return {
        "cpu": 1 + weight % 4,
        "memory": 256 + (weight % 5) * 128,
        "storage": 10 + weight,
        "ai_tokens": 256 + weight * 32,
        "seconds": 10 + weight,
    }


def _diag(
    severity: str,
    category: str,
    code: str,
    path: str,
) -> R17PlanningDiagnostic:
    return R17PlanningDiagnostic(
        severity=severity,
        category=category,
        code=code,
        message=f"{code} at {path}",
        path=path,
    )
