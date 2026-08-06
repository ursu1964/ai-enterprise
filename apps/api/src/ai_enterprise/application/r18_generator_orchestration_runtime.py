from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict

from ai_enterprise.application.r16_knowledge_graph_runtime import R16KnowledgeGraphModel
from ai_enterprise.application.r17_execution_planner_runtime import (
    R17ExecutionPlan,
    r17_validate_execution_plan,
)
from ai_enterprise.domain.specification.kernel import specification_hash

ORCHESTRATOR_VERSION = "generator-orchestrator-1.0"
DETERMINISTIC_EXECUTION_TIMESTAMP = "1970-01-01T00:00:00Z"


class R18GeneratorDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    generator_id: str
    generator_name: str
    category: str
    supported_task_types: tuple[str, ...]
    capabilities: tuple[str, ...]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    version: str
    execution_policies: dict[str, Any]
    dependencies: tuple[str, ...]
    performance_profile: dict[str, int]
    model_provider: str
    model_version: str
    prompt_version: str


class R18ArtifactRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: str
    generator_id: str
    generator_version: str
    model_version: str
    prompt_version: str
    execution_task_id: str
    knowledge_node_id: str
    knowledge_node_type: str
    registry_reference: str
    manifest_origin: str
    execution_plan_version: str
    knowledge_graph_version: str
    artifact_type: str
    logical_path: str
    generated_content: dict[str, Any]
    content_hash: str
    metadata_hash: str
    immutable: bool


class R18MaterializedArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: str
    logical_path: str
    physical_path: str
    content_hash: str
    materialization_hash: str


class R18ProviderReadiness(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    configured: bool
    credential_reference: str | None
    endpoint_reference: str | None
    model_reference: str | None
    supports_live_execution: bool
    diagnostics: tuple[dict[str, str], ...]
    readiness_hash: str


class R18GeneratedArtifactPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_type: str
    logical_path: str | None = None
    content: dict[str, Any]
    diagnostics: tuple[dict[str, str], ...] = ()


class R18ProviderGenerationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifacts: tuple[R18GeneratedArtifactPayload, ...]
    diagnostics: tuple[dict[str, str], ...]
    metrics: dict[str, int]


class R18ProviderGenerationError(RuntimeError):
    pass


class R18GeneratorProviderAdapter(Protocol):
    def generate(
        self,
        *,
        task: Any,
        graph_context: dict[str, Any],
        generator: R18GeneratorDefinition,
        provider_config: dict[str, Any],
    ) -> R18ProviderGenerationResult: ...


class R18RuleEngineGeneratorAdapter:
    def generate(
        self,
        *,
        task: Any,
        graph_context: dict[str, Any],
        generator: R18GeneratorDefinition,
        provider_config: dict[str, Any],
    ) -> R18ProviderGenerationResult:
        artifacts = tuple(
            R18GeneratedArtifactPayload(
                artifact_type=str(output),
                content=_rule_engine_content(task, graph_context, generator, str(output)),
            )
            for output in task.outputs
        )
        return R18ProviderGenerationResult(
            artifacts=artifacts,
            diagnostics=(),
            metrics={
                "provider_calls": 0,
                "provider_tokens_input": 0,
                "provider_tokens_output": 0,
            },
        )


class R18MockOpenAICompatibleAdapter:
    def __init__(self, outputs: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.outputs = outputs or {}

    def generate(
        self,
        *,
        task: Any,
        graph_context: dict[str, Any],
        generator: R18GeneratorDefinition,
        provider_config: dict[str, Any],
    ) -> R18ProviderGenerationResult:
        configured = self.outputs.get(str(task.task_id))
        payloads = configured or [
            {
                "artifact_type": output,
                "content": {
                    "provider": generator.model_provider,
                    "model": provider_config.get("model_reference", generator.model_version),
                    "task_id": task.task_id,
                    "knowledge_node_id": task.knowledge_node_id,
                    "generated_text": f"Mock provider output for {task.task_id}::{output}",
                },
            }
            for output in task.outputs
        ]
        return R18ProviderGenerationResult(
            artifacts=tuple(R18GeneratedArtifactPayload.model_validate(item) for item in payloads),
            diagnostics=(),
            metrics={
                "provider_calls": 1,
                "provider_tokens_input": len(json.dumps(graph_context, sort_keys=True)),
                "provider_tokens_output": len(json.dumps(payloads, sort_keys=True)),
            },
        )


class R18HTTPModelProviderAdapter:
    def __init__(
        self,
        *,
        provider: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.provider = provider
        self.transport = transport

    def generate(
        self,
        *,
        task: Any,
        graph_context: dict[str, Any],
        generator: R18GeneratorDefinition,
        provider_config: dict[str, Any],
    ) -> R18ProviderGenerationResult:
        request = _provider_request(task, graph_context, generator, provider_config)
        timeout = float(provider_config.get("timeout_seconds", 120))
        with httpx.Client(timeout=timeout, transport=self.transport) as client:
            response = client.post(
                request["url"],
                headers=request["headers"],
                json=request["json"],
            )
            response.raise_for_status()
            payload = response.json()
        artifacts = _provider_response_artifacts(
            task,
            generator,
            payload,
            fallback_text=_extract_provider_text(payload),
        )
        return R18ProviderGenerationResult(
            artifacts=artifacts,
            diagnostics=(),
            metrics={
                "provider_calls": 1,
                "provider_tokens_input": int(request["metrics"]["estimated_input"]),
                "provider_tokens_output": len(json.dumps(payload, sort_keys=True)),
            },
        )


class R18ValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    validation_rule: str
    diagnostics: tuple[dict[str, str], ...]
    report_hash: str


class R18ExecutionMetric(BaseModel):
    model_config = ConfigDict(frozen=True)

    execution_time_ms: int
    tokens_consumed: int
    memory_mb: int
    artifacts_produced: int
    validation_errors: int
    retry_count: int
    provider_calls: int = 0
    provider_tokens_input: int = 0
    provider_tokens_output: int = 0


class R18LifecycleEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    generator_id: str
    task_id: str
    status: str
    timestamp: str
    event_hash: str


class R18TaskExecutionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: str
    generator_id: str
    status: str
    lifecycle: tuple[R18LifecycleEvent, ...]
    artifacts: tuple[R18ArtifactRecord, ...]
    validation_report: R18ValidationReport
    metrics: R18ExecutionMetric
    diagnostics: tuple[dict[str, str], ...]
    retry_count: int
    execution_record_hash: str


class R18ArtifactRepositorySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    repository_id: str
    artifact_count: int
    immutable_stage_ids: tuple[str, ...]
    artifact_hashes: tuple[str, ...]
    materialized_artifacts: tuple[R18MaterializedArtifact, ...]
    repository_hash: str


class R18OrchestrationDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True)

    severity: str
    category: str
    code: str
    message: str
    path: str


class R18ExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    execution_id: str
    orchestrator_version: str
    plan_id: str
    plan_hash: str
    graph_version: str
    status: str
    generator_registry_hash: str
    provider_readiness: tuple[R18ProviderReadiness, ...]
    artifact_repository: R18ArtifactRepositorySnapshot
    task_records: tuple[R18TaskExecutionRecord, ...]
    execution_history: tuple[R18LifecycleEvent, ...]
    validation_results: tuple[R18ValidationReport, ...]
    metrics: dict[str, int]
    diagnostics: tuple[R18OrchestrationDiagnostic, ...]
    result_hash: str
    execution_signature: str


class R18GeneratorRegistryValidation(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    diagnostics: tuple[R18OrchestrationDiagnostic, ...]
    registry_hash: str


BUILTIN_GENERATOR_REGISTRY: tuple[R18GeneratorDefinition, ...] = (
    R18GeneratorDefinition(
        generator_id="planner.foundation",
        generator_name="Foundation Project Generator",
        category="foundation",
        supported_task_types=("foundation.setup",),
        capabilities=("project-structure", "configuration", "dependency-baseline"),
        input_schema={"required": ("execution_task", "knowledge_context")},
        output_schema={"artifacts": ("project-foundation",)},
        version="1.0.0",
        execution_policies={"isolation": "sandboxed", "writes": "foundation-only"},
        dependencies=(),
        performance_profile={"base_ms": 10, "token_multiplier": 1, "memory_mb": 128},
        model_provider="rule-engine",
        model_version="deterministic-1",
        prompt_version="r18-foundation-1",
    ),
    R18GeneratorDefinition(
        generator_id="generator.database",
        generator_name="Database Generator",
        category="domain",
        supported_task_types=("domain.model",),
        capabilities=("schema", "repository-contract", "migration-plan"),
        input_schema={"required": ("execution_task", "knowledge_context")},
        output_schema={"artifacts": ("schema", "repository-contract")},
        version="1.0.0",
        execution_policies={"isolation": "sandboxed", "writes": "domain-only"},
        dependencies=(),
        performance_profile={"base_ms": 18, "token_multiplier": 2, "memory_mb": 256},
        model_provider="rule-engine",
        model_version="deterministic-1",
        prompt_version="r18-database-1",
    ),
    R18GeneratorDefinition(
        generator_id="generator.backend",
        generator_name="Backend Generator",
        category="application",
        supported_task_types=("backend.service",),
        capabilities=("service", "api-contract", "workflow-coordination"),
        input_schema={"required": ("execution_task", "knowledge_context")},
        output_schema={"artifacts": ("service", "api-contract")},
        version="1.0.0",
        execution_policies={"isolation": "sandboxed", "writes": "backend-only"},
        dependencies=("generator.database",),
        performance_profile={"base_ms": 24, "token_multiplier": 3, "memory_mb": 384},
        model_provider="rule-engine",
        model_version="deterministic-1",
        prompt_version="r18-backend-1",
    ),
    R18GeneratorDefinition(
        generator_id="generator.frontend",
        generator_name="Frontend Generator",
        category="application",
        supported_task_types=("frontend.surface",),
        capabilities=("ui-view", "report-surface", "notification-surface"),
        input_schema={"required": ("execution_task", "knowledge_context")},
        output_schema={"artifacts": ("ui-view", "report-surface")},
        version="1.0.0",
        execution_policies={"isolation": "sandboxed", "writes": "frontend-only"},
        dependencies=("generator.backend",),
        performance_profile={"base_ms": 22, "token_multiplier": 3, "memory_mb": 384},
        model_provider="rule-engine",
        model_version="deterministic-1",
        prompt_version="r18-frontend-1",
    ),
    R18GeneratorDefinition(
        generator_id="generator.infrastructure",
        generator_name="Infrastructure Generator",
        category="infrastructure",
        supported_task_types=("infrastructure.policy",),
        capabilities=("policy-as-code", "infrastructure-requirement", "monitoring"),
        input_schema={"required": ("execution_task", "knowledge_context")},
        output_schema={"artifacts": ("policy-as-code", "infrastructure-requirement")},
        version="1.0.0",
        execution_policies={"isolation": "privileged-plan-only", "writes": "infra-only"},
        dependencies=(),
        performance_profile={"base_ms": 28, "token_multiplier": 2, "memory_mb": 512},
        model_provider="rule-engine",
        model_version="deterministic-1",
        prompt_version="r18-infrastructure-1",
    ),
    R18GeneratorDefinition(
        generator_id="validator.quality",
        generator_name="Quality Validation Generator",
        category="quality",
        supported_task_types=("quality.validation",),
        capabilities=("unit-test-plan", "integration-test-plan", "security-checks"),
        input_schema={"required": ("execution_task", "knowledge_context", "artifacts")},
        output_schema={"artifacts": ("validation-evidence",)},
        version="1.0.0",
        execution_policies={"isolation": "read-only-validation", "writes": "quality-only"},
        dependencies=(),
        performance_profile={"base_ms": 14, "token_multiplier": 1, "memory_mb": 256},
        model_provider="rule-engine",
        model_version="deterministic-1",
        prompt_version="r18-quality-1",
    ),
    R18GeneratorDefinition(
        generator_id="generator.deployment",
        generator_name="Deployment Generator",
        category="infrastructure",
        supported_task_types=("deployment.package",),
        capabilities=("deployment-package", "release-manifest", "rollback-plan"),
        input_schema={"required": ("execution_task", "knowledge_context", "approvals")},
        output_schema={"artifacts": ("deployment-package",)},
        version="1.0.0",
        execution_policies={"isolation": "privileged-plan-only", "writes": "deployment-only"},
        dependencies=("validator.quality",),
        performance_profile={"base_ms": 30, "token_multiplier": 2, "memory_mb": 512},
        model_provider="rule-engine",
        model_version="deterministic-1",
        prompt_version="r18-deployment-1",
    ),
)


def r18_orchestrate_execution(
    plan: dict[str, Any] | R17ExecutionPlan,
    graph: dict[str, Any] | R16KnowledgeGraphModel,
    *,
    generator_registry: list[dict[str, Any]] | tuple[R18GeneratorDefinition, ...] | None = None,
    orchestration_options: dict[str, Any] | None = None,
) -> R18ExecutionResult:
    options = orchestration_options or {}
    plan_model = (
        plan if isinstance(plan, R17ExecutionPlan) else R17ExecutionPlan.model_validate(plan)
    )
    graph_model = (
        graph
        if isinstance(graph, R16KnowledgeGraphModel)
        else R16KnowledgeGraphModel.model_validate(graph)
    )
    registry = _registry(generator_registry)
    registry_validation = r18_validate_generator_registry(registry)
    diagnostics: list[R18OrchestrationDiagnostic] = list(registry_validation.diagnostics)
    provider_readiness = r18_check_provider_readiness(registry, options)
    diagnostics.extend(_provider_diagnostics(provider_readiness, options))

    plan_validation = r17_validate_execution_plan(plan_model)
    if not plan_validation.valid:
        diagnostics.extend(
            _diag("fatal", "planning", "R18-INVALID-EXECUTION-PLAN", item.path)
            for item in plan_validation.diagnostics
        )
    diagnostics.extend(_plan_generator_diagnostics(plan_model, registry))

    missing_approvals = _missing_approvals(plan_model, options.get("approvals", {}))
    diagnostics.extend(missing_approvals)

    task_records: list[R18TaskExecutionRecord] = []
    artifacts: list[R18ArtifactRecord] = []
    history: list[R18LifecycleEvent] = []
    validation_results: list[R18ValidationReport] = []
    immutable_stage_ids: list[str] = []

    if not diagnostics:
        tasks_by_id = {task.task_id: task for task in plan_model.tasks}
        for stage in plan_model.stages:
            stage_blocked = False
            for task_id in stage.task_ids:
                task = tasks_by_id[task_id]
                record = _execute_task(
                    task,
                    plan_model,
                    graph_model,
                    registry,
                    options,
                    previous_artifacts=tuple(artifacts),
                )
                task_records.append(record)
                artifacts.extend(record.artifacts)
                history.extend(record.lifecycle)
                validation_results.append(record.validation_report)
                if record.status != "completed":
                    stage_blocked = True
                    break
            if stage_blocked:
                diagnostics.append(_diag("fatal", "execution", "R18-STAGE-HALTED", stage.stage_id))
                break
            immutable_stage_ids.append(stage.stage_id)
            conflict_diagnostics = _conflict_diagnostics(tuple(artifacts))
            if conflict_diagnostics:
                diagnostics.extend(conflict_diagnostics)
                break

    materialized_artifacts = _materialize_artifacts(tuple(artifacts), options)
    repository = _artifact_repository(
        plan_model,
        tuple(artifacts),
        tuple(immutable_stage_ids),
        materialized_artifacts,
    )
    metrics = _aggregate_metrics(tuple(task_records), tuple(artifacts))
    status = "completed" if not diagnostics and task_records else "blocked"
    unsigned = {
        "orchestrator_version": ORCHESTRATOR_VERSION,
        "plan_id": plan_model.plan_id,
        "plan_hash": plan_model.plan_hash,
        "graph_version": graph_model.graph_version,
        "status": status,
        "generator_registry_hash": registry_validation.registry_hash,
        "provider_readiness": [item.model_dump(mode="json") for item in provider_readiness],
        "artifact_repository": repository.model_dump(mode="json"),
        "task_records": [item.model_dump(mode="json") for item in task_records],
        "execution_history": [item.model_dump(mode="json") for item in history],
        "validation_results": [item.model_dump(mode="json") for item in validation_results],
        "metrics": metrics,
        "diagnostics": [item.model_dump(mode="json") for item in diagnostics],
    }
    result_hash = specification_hash(unsigned)
    return R18ExecutionResult(
        execution_id=f"exec-{plan_model.plan_id}-{result_hash[:12]}",
        result_hash=result_hash,
        execution_signature=specification_hash(
            {
                "result_hash": result_hash,
                "orchestrator_version": ORCHESTRATOR_VERSION,
            }
        ),
        **unsigned,
    )


def r18_validate_generator_registry(
    generator_registry: list[dict[str, Any]] | tuple[R18GeneratorDefinition, ...] | None = None,
) -> R18GeneratorRegistryValidation:
    registry = _registry(generator_registry)
    diagnostics: list[R18OrchestrationDiagnostic] = []
    generator_ids = [item.generator_id for item in registry]
    duplicate_ids = sorted({item for item in generator_ids if generator_ids.count(item) > 1})
    for generator_id in duplicate_ids:
        diagnostics.append(_diag("fatal", "registry", "R18-DUPLICATE-GENERATOR-ID", generator_id))
    supported = {
        task_type for generator in registry for task_type in generator.supported_task_types
    }
    required = {
        "foundation.setup",
        "domain.model",
        "backend.service",
        "frontend.surface",
        "infrastructure.policy",
        "quality.validation",
        "deployment.package",
    }
    for task_type in sorted(required - supported):
        diagnostics.append(_diag("fatal", "registry", "R18-GENERATOR-TASK-MISSING", task_type))
    for generator in registry:
        for dependency in generator.dependencies:
            if dependency not in generator_ids:
                diagnostics.append(
                    _diag("fatal", "registry", "R18-GENERATOR-DEPENDENCY-MISSING", dependency)
                )
    payload = [item.model_dump(mode="json") for item in registry]
    return R18GeneratorRegistryValidation(
        valid=not diagnostics,
        diagnostics=tuple(sorted(diagnostics, key=lambda item: (item.code, item.path))),
        registry_hash=specification_hash(payload),
    )


def r18_check_provider_readiness(
    generator_registry: list[dict[str, Any]] | tuple[R18GeneratorDefinition, ...] | None = None,
    orchestration_options: dict[str, Any] | None = None,
) -> tuple[R18ProviderReadiness, ...]:
    registry = _registry(generator_registry)
    options = orchestration_options or {}
    provider_configs = options.get("provider_configs", {})
    provider_map = provider_configs if isinstance(provider_configs, dict) else {}
    providers = sorted({generator.model_provider for generator in registry})
    readiness: list[R18ProviderReadiness] = []
    for provider in providers:
        config = provider_map.get(provider, {})
        config_map = config if isinstance(config, dict) else {}
        credential_reference = _optional_str(config_map.get("credential_reference"))
        api_key_present = _optional_str(config_map.get("api_key")) is not None
        endpoint_reference = _optional_str(config_map.get("endpoint_reference"))
        model_reference = _optional_str(config_map.get("model_reference"))
        supports_live_execution = provider == "rule-engine" or (
            (credential_reference is not None or api_key_present)
            and model_reference is not None
            and (provider in {"openai", "anthropic", "google"} or endpoint_reference is not None)
        )
        diagnostics: list[dict[str, str]] = []
        if provider != "rule-engine":
            if credential_reference is None and not api_key_present:
                diagnostics.append(
                    {
                        "severity": "fatal",
                        "code": "R18-PROVIDER-CREDENTIAL-MISSING",
                        "message": f"{provider} requires credential_reference.",
                    }
                )
            if model_reference is None:
                diagnostics.append(
                    {
                        "severity": "fatal",
                        "code": "R18-PROVIDER-MODEL-MISSING",
                        "message": f"{provider} requires model_reference.",
                    }
                )
            if provider not in {"openai", "anthropic", "google"} and endpoint_reference is None:
                diagnostics.append(
                    {
                        "severity": "fatal",
                        "code": "R18-PROVIDER-ENDPOINT-MISSING",
                        "message": f"{provider} requires endpoint_reference.",
                    }
                )
        payload = {
            "provider": provider,
            "configured": not diagnostics,
            "credential_reference": credential_reference,
            "endpoint_reference": endpoint_reference,
            "model_reference": model_reference,
            "supports_live_execution": supports_live_execution,
            "diagnostics": diagnostics,
        }
        readiness.append(
            R18ProviderReadiness(
                **payload,
                readiness_hash=specification_hash(payload),
            )
        )
    return tuple(readiness)


def r18_persist_execution_result(
    result: R18ExecutionResult,
    history_path: Path,
    *,
    actor_id: str,
) -> str:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": "r18-execution-history-1.0",
        "actor_id": actor_id,
        "execution_id": result.execution_id,
        "plan_id": result.plan_id,
        "plan_hash": result.plan_hash,
        "result_hash": result.result_hash,
        "execution_signature": result.execution_signature,
        "status": result.status,
        "artifact_count": result.artifact_repository.artifact_count,
    }
    record_hash = specification_hash(record)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({**record, "record_hash": record_hash}, sort_keys=True))
        handle.write("\n")
    return record_hash


def r18_read_execution_history(history_path: Path) -> tuple[dict[str, Any], ...]:
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


def _registry(
    generator_registry: list[dict[str, Any]] | tuple[R18GeneratorDefinition, ...] | None,
) -> tuple[R18GeneratorDefinition, ...]:
    if generator_registry is None:
        return BUILTIN_GENERATOR_REGISTRY
    return tuple(
        sorted(
            (
                item
                if isinstance(item, R18GeneratorDefinition)
                else R18GeneratorDefinition.model_validate(item)
                for item in generator_registry
            ),
            key=lambda item: item.generator_id,
        )
    )


def _missing_approvals(
    plan: R17ExecutionPlan,
    approvals: object,
) -> tuple[R18OrchestrationDiagnostic, ...]:
    approval_map = approvals if isinstance(approvals, dict) else {}
    diagnostics: list[R18OrchestrationDiagnostic] = []
    for gate in plan.approval_gates:
        if gate.manual and approval_map.get(gate.approval_id) is not True:
            diagnostics.append(_diag("fatal", "approval", "R18-APPROVAL-MISSING", gate.approval_id))
    return tuple(diagnostics)


def _provider_diagnostics(
    readiness: tuple[R18ProviderReadiness, ...],
    options: dict[str, Any],
) -> tuple[R18OrchestrationDiagnostic, ...]:
    strict = options.get("require_external_provider_readiness", True) is True
    if not strict:
        return ()
    diagnostics: list[R18OrchestrationDiagnostic] = []
    for provider in readiness:
        if provider.provider == "rule-engine":
            continue
        if not provider.configured or not provider.supports_live_execution:
            diagnostics.append(
                _diag(
                    "fatal",
                    "provider",
                    "R18-EXTERNAL-PROVIDER-NOT-READY",
                    provider.provider,
                )
            )
    return tuple(diagnostics)


def _execute_task(
    task: Any,
    plan: R17ExecutionPlan,
    graph: R16KnowledgeGraphModel,
    registry: tuple[R18GeneratorDefinition, ...],
    options: dict[str, Any],
    *,
    previous_artifacts: tuple[R18ArtifactRecord, ...],
) -> R18TaskExecutionRecord:
    generator = _generator_for_task(task, registry)
    lifecycle_statuses = ["registered", "available", "assigned", "executing"]
    diagnostics: list[dict[str, str]] = []
    retry_count = 0
    transient_failures = set(str(item) for item in options.get("transient_fail_task_ids", ()))
    permanent_failures = set(str(item) for item in options.get("fail_task_ids", ()))
    max_attempts = max(1, int(task.retry_policy.get("max_attempts", 1)))
    if task.task_id in permanent_failures:
        diagnostics.append(
            {
                "severity": "fatal",
                "code": "R18-GENERATOR-EXECUTION-FAILED",
                "message": f"Generator failed for {task.task_id}.",
            }
        )
        status = "failed"
        lifecycle_statuses.append("failed")
    elif task.task_id in transient_failures and max_attempts > 1:
        retry_count = 1
        lifecycle_statuses.extend(("retry_eligible", "executing"))
        status = "completed"
        lifecycle_statuses.extend(("validated", "completed", "archived"))
    else:
        status = "completed"
        lifecycle_statuses.extend(("validated", "completed", "archived"))

    generation_result = R18ProviderGenerationResult(
        artifacts=(),
        diagnostics=(),
        metrics={"provider_calls": 0, "provider_tokens_input": 0, "provider_tokens_output": 0},
    )
    if status == "completed":
        try:
            generation_result = _generate_with_provider(task, plan, graph, generator, options)
        except (R18ProviderGenerationError, httpx.HTTPError, ValueError) as exc:
            status = "failed"
            lifecycle_statuses.append("failed")
            diagnostics.append(
                {
                    "severity": "fatal",
                    "code": "R18-PROVIDER-GENERATION-FAILED",
                    "message": str(exc),
                }
            )
    artifact_tuple = (
        tuple(
            _artifact(task, plan, graph, generator, generated)
            for generated in generation_result.artifacts
        )
        if status == "completed"
        else ()
    )
    validation = _validate_artifacts(task, generator, artifact_tuple, previous_artifacts)
    if not validation.valid:
        status = "failed"
        diagnostics.extend(validation.diagnostics)
    diagnostics.extend(generation_result.diagnostics)

    lifecycle = tuple(
        _event(generator.generator_id, task.task_id, status_name)
        for status_name in lifecycle_statuses
    )
    metrics = R18ExecutionMetric(
        execution_time_ms=generator.performance_profile["base_ms"] + task.estimated_cost["seconds"],
        tokens_consumed=task.estimated_cost["ai_tokens"]
        * generator.performance_profile["token_multiplier"],
        memory_mb=generator.performance_profile["memory_mb"],
        artifacts_produced=len(artifact_tuple),
        validation_errors=0 if validation.valid else len(validation.diagnostics),
        retry_count=retry_count,
        provider_calls=generation_result.metrics.get("provider_calls", 0),
        provider_tokens_input=generation_result.metrics.get("provider_tokens_input", 0),
        provider_tokens_output=generation_result.metrics.get("provider_tokens_output", 0),
    )
    unsigned = {
        "task_id": task.task_id,
        "generator_id": generator.generator_id,
        "status": status,
        "lifecycle": [item.model_dump(mode="json") for item in lifecycle],
        "artifacts": [item.model_dump(mode="json") for item in artifact_tuple],
        "validation_report": validation.model_dump(mode="json"),
        "metrics": metrics.model_dump(mode="json"),
        "diagnostics": diagnostics,
        "retry_count": retry_count,
    }
    return R18TaskExecutionRecord(
        execution_record_hash=specification_hash(unsigned),
        **unsigned,
    )


def _generator_for_task(
    task: Any,
    registry: tuple[R18GeneratorDefinition, ...],
) -> R18GeneratorDefinition:
    matches = [
        item
        for item in registry
        if item.generator_id == task.generator and task.task_type in item.supported_task_types
    ]
    if not matches:
        raise ValueError(f"No R18 generator supports task {task.task_type}")
    return matches[0]


def _generate_with_provider(
    task: Any,
    plan: R17ExecutionPlan,
    graph: R16KnowledgeGraphModel,
    generator: R18GeneratorDefinition,
    options: dict[str, Any],
) -> R18ProviderGenerationResult:
    graph_context = _graph_context(task, plan, graph)
    provider_config = _provider_config(generator.model_provider, generator, options)
    adapter = _adapter_for_provider(generator.model_provider, options)
    return adapter.generate(
        task=task,
        graph_context=graph_context,
        generator=generator,
        provider_config=provider_config,
    )


def _adapter_for_provider(
    provider: str,
    options: dict[str, Any],
) -> R18GeneratorProviderAdapter:
    adapters = options.get("provider_adapters", {})
    if isinstance(adapters, dict) and provider in adapters:
        adapter = adapters[provider]
        if hasattr(adapter, "generate"):
            return adapter
        raise R18ProviderGenerationError(f"Configured adapter for {provider} is invalid.")
    if provider == "rule-engine":
        return R18RuleEngineGeneratorAdapter()
    if options.get("enable_live_provider_calls") is not True:
        raise R18ProviderGenerationError(
            f"Live provider calls for {provider} are disabled. "
            "Set enable_live_provider_calls=true or inject a test adapter."
        )
    return R18HTTPModelProviderAdapter(
        provider=provider,
        transport=options.get("http_transport"),
    )


def _provider_config(
    provider: str,
    generator: R18GeneratorDefinition,
    options: dict[str, Any],
) -> dict[str, Any]:
    configs = options.get("provider_configs", {})
    config = configs.get(provider, {}) if isinstance(configs, dict) else {}
    config_map = dict(config) if isinstance(config, dict) else {}
    config_map.setdefault("model_reference", generator.model_version)
    if provider == "openai":
        config_map.setdefault("endpoint_reference", "https://api.openai.com/v1/responses")
    elif provider == "anthropic":
        config_map.setdefault("endpoint_reference", "https://api.anthropic.com/v1/messages")
    elif provider == "google":
        model = str(config_map.get("model_reference", generator.model_version))
        config_map.setdefault(
            "endpoint_reference",
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        )
    _resolve_credential(provider, config_map)
    return config_map


def _resolve_credential(provider: str, config: dict[str, Any]) -> None:
    if isinstance(config.get("api_key"), str) and config["api_key"]:
        return
    credential_reference = _optional_str(config.get("credential_reference"))
    if credential_reference and credential_reference.startswith("env:"):
        env_name = credential_reference.removeprefix("env:")
        value = os.environ.get(env_name)
        if value:
            config["api_key"] = value
            return
    default_env = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
    }.get(provider)
    if default_env and os.environ.get(default_env):
        config["api_key"] = os.environ[default_env]


def _provider_request(
    task: Any,
    graph_context: dict[str, Any],
    generator: R18GeneratorDefinition,
    provider_config: dict[str, Any],
) -> dict[str, Any]:
    provider = generator.model_provider
    endpoint = _optional_str(provider_config.get("endpoint_reference"))
    api_key = _optional_str(provider_config.get("api_key"))
    model = _optional_str(provider_config.get("model_reference")) or generator.model_version
    if endpoint is None:
        raise R18ProviderGenerationError(f"{provider} endpoint_reference is required.")
    if api_key is None:
        raise R18ProviderGenerationError(f"{provider} api key is required.")
    prompt = _provider_prompt(task, graph_context, generator)
    if provider == "openai":
        return {
            "url": endpoint,
            "headers": {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            "json": {
                "model": model,
                "input": [
                    {
                        "role": "system",
                        "content": (
                            "You are an AI-Enterprise generator. Return JSON artifacts only."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            },
            "metrics": {"estimated_input": len(prompt)},
        }
    if provider == "anthropic":
        return {
            "url": endpoint,
            "headers": {
                "x-api-key": api_key,
                "anthropic-version": str(provider_config.get("anthropic_version", "2023-06-01")),
                "Content-Type": "application/json",
            },
            "json": {
                "model": model,
                "max_tokens": int(provider_config.get("max_tokens", 4096)),
                "messages": [{"role": "user", "content": prompt}],
            },
            "metrics": {"estimated_input": len(prompt)},
        }
    if provider == "google":
        return {
            "url": f"{endpoint}?key={api_key}",
            "headers": {"Content-Type": "application/json"},
            "json": {"contents": [{"parts": [{"text": prompt}]}]},
            "metrics": {"estimated_input": len(prompt)},
        }
    return {
        "url": endpoint,
        "headers": {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        "json": {
            "model": model,
            "task": task.model_dump(mode="json") if hasattr(task, "model_dump") else dict(task),
            "context": graph_context,
            "required_outputs": list(task.outputs),
        },
        "metrics": {"estimated_input": len(prompt)},
    }


def _provider_prompt(
    task: Any,
    graph_context: dict[str, Any],
    generator: R18GeneratorDefinition,
) -> str:
    payload = {
        "instruction": (
            "Generate artifacts for the assigned task. Return either JSON with an "
            "'artifacts' array or plain text that can be stored as provider output."
        ),
        "generator": generator.model_dump(mode="json"),
        "task": task.model_dump(mode="json") if hasattr(task, "model_dump") else dict(task),
        "graph_context": graph_context,
        "required_outputs": list(task.outputs),
    }
    return json.dumps(payload, sort_keys=True)


def _provider_response_artifacts(
    task: Any,
    generator: R18GeneratorDefinition,
    payload: dict[str, Any],
    *,
    fallback_text: str,
) -> tuple[R18GeneratedArtifactPayload, ...]:
    candidate = payload
    text = fallback_text.strip()
    if text.startswith("{"):
        try:
            candidate = json.loads(text)
        except json.JSONDecodeError:
            candidate = payload
    artifacts = candidate.get("artifacts") if isinstance(candidate, dict) else None
    if isinstance(artifacts, list) and artifacts:
        return tuple(
            R18GeneratedArtifactPayload(
                artifact_type=str(
                    item.get("artifact_type", task.outputs[index % len(task.outputs)])
                ),
                logical_path=_optional_str(item.get("logical_path")),
                content={
                    "provider": generator.model_provider,
                    "model": generator.model_version,
                    **(item.get("content") if isinstance(item.get("content"), dict) else item),
                },
            )
            for index, item in enumerate(artifacts)
            if isinstance(item, dict)
        )
    return tuple(
        R18GeneratedArtifactPayload(
            artifact_type=str(output),
            content={
                "provider": generator.model_provider,
                "model": generator.model_version,
                "task_id": task.task_id,
                "generated_text": text or json.dumps(payload, sort_keys=True),
            },
        )
        for output in task.outputs
    )


def _extract_provider_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return output_text
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str):
            return content
    content = payload.get("content")
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict) and isinstance(first.get("text"), str):
            return first["text"]
    candidates = payload.get("candidates")
    if isinstance(candidates, list) and candidates:
        content_obj = candidates[0].get("content") if isinstance(candidates[0], dict) else None
        parts = content_obj.get("parts") if isinstance(content_obj, dict) else None
        if isinstance(parts, list) and parts:
            first = parts[0]
            if isinstance(first, dict) and isinstance(first.get("text"), str):
                return first["text"]
    return json.dumps(payload, sort_keys=True)


def _graph_context(
    task: Any,
    plan: R17ExecutionPlan,
    graph: R16KnowledgeGraphModel,
) -> dict[str, Any]:
    node = _node(graph, task.knowledge_node_id)
    return {
        "node": node,
        "related_edges": [
            edge
            for edge in graph.edges
            if str(edge["source"]) == task.knowledge_node_id
            or str(edge["target"]) == task.knowledge_node_id
        ],
        "graph_hash": graph.graph_hash,
        "graph_version": graph.graph_version,
        "plan_id": plan.plan_id,
        "plan_hash": plan.plan_hash,
    }


def _rule_engine_content(
    task: Any,
    graph_context: dict[str, Any],
    generator: R18GeneratorDefinition,
    output: str,
) -> dict[str, Any]:
    node = graph_context["node"]
    return {
        "artifact_type": output,
        "producer": generator.generator_id,
        "generator_version": generator.version,
        "model_provider": generator.model_provider,
        "model_version": generator.model_version,
        "prompt_version": generator.prompt_version,
        "task": {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "stage_id": task.stage_id,
            "validation_rule": task.validation_rule,
        },
        "semantic_context": {
            "knowledge_node_id": task.knowledge_node_id,
            "knowledge_node_type": task.knowledge_node_type,
            "knowledge_node_name": node.get("name"),
            "relationship_count": len(graph_context["related_edges"]),
        },
        "generated_text": (
            f"{generator.generator_name} produced {output} for "
            f"{task.knowledge_node_type} {task.knowledge_node_id}."
        ),
        "traceability": {
            "manifest_origin": node["traceability"]["manifest_origin"],
            "registry_reference": node["traceability"]["registry_reference"],
            "graph_hash": graph_context["graph_hash"],
            "plan_hash": graph_context["plan_hash"],
        },
    }


def _plan_generator_diagnostics(
    plan: R17ExecutionPlan,
    registry: tuple[R18GeneratorDefinition, ...],
) -> tuple[R18OrchestrationDiagnostic, ...]:
    supported = {
        (generator.generator_id, task_type)
        for generator in registry
        for task_type in generator.supported_task_types
    }
    diagnostics: list[R18OrchestrationDiagnostic] = []
    for task in plan.tasks:
        if (task.generator, task.task_type) not in supported:
            diagnostics.append(
                _diag(
                    "fatal",
                    "registry",
                    "R18-ASSIGNED-GENERATOR-UNAVAILABLE",
                    task.task_id,
                )
            )
    return tuple(diagnostics)


def _artifact(
    task: Any,
    plan: R17ExecutionPlan,
    graph: R16KnowledgeGraphModel,
    generator: R18GeneratorDefinition,
    generated: R18GeneratedArtifactPayload,
) -> R18ArtifactRecord:
    node = _node(graph, task.knowledge_node_id)
    artifact_type = generated.artifact_type
    logical_path = generated.logical_path or (
        f"{task.stage_id}/{_safe(task.knowledge_node_id)}/"
        f"{_safe(task.task_type)}.{_safe(artifact_type)}.artifact.json"
    )
    payload = {
        "generator_id": generator.generator_id,
        "task_id": task.task_id,
        "knowledge_node_id": task.knowledge_node_id,
        "knowledge_node_type": task.knowledge_node_type,
        "artifact_type": artifact_type,
        "generated_content": generated.content,
        "plan_hash": plan.plan_hash,
        "graph_hash": graph.graph_hash,
    }
    content_hash = specification_hash(payload)
    metadata = {
        "generator_version": generator.version,
        "model_version": generator.model_version,
        "prompt_version": generator.prompt_version,
        "execution_plan_version": plan.execution_version,
        "knowledge_graph_version": graph.graph_version,
    }
    return R18ArtifactRecord(
        artifact_id=f"artifact-{content_hash[:16]}",
        generator_id=generator.generator_id,
        generator_version=generator.version,
        model_version=generator.model_version,
        prompt_version=generator.prompt_version,
        execution_task_id=task.task_id,
        knowledge_node_id=task.knowledge_node_id,
        knowledge_node_type=task.knowledge_node_type,
        registry_reference=str(node["traceability"]["registry_reference"]),
        manifest_origin=str(node["traceability"]["manifest_origin"]),
        execution_plan_version=plan.execution_version,
        knowledge_graph_version=graph.graph_version,
        artifact_type=artifact_type,
        logical_path=logical_path,
        generated_content=generated.content,
        content_hash=content_hash,
        metadata_hash=specification_hash(metadata),
        immutable=True,
    )


def _validate_artifacts(
    task: Any,
    generator: R18GeneratorDefinition,
    artifacts: tuple[R18ArtifactRecord, ...],
    previous_artifacts: tuple[R18ArtifactRecord, ...],
) -> R18ValidationReport:
    diagnostics: list[dict[str, str]] = []
    supported_outputs = set(generator.output_schema.get("artifacts", ()))
    required_outputs = set(task.outputs)
    produced_outputs = [artifact.artifact_type for artifact in artifacts]
    for output in sorted(required_outputs - set(produced_outputs)):
        diagnostics.append(
            {
                "severity": "fatal",
                "code": "R18-ARTIFACT-OUTPUT-MISSING",
                "message": f"{task.task_id} did not produce required output {output}.",
            }
        )
    duplicate_outputs = sorted(
        {output for output in produced_outputs if produced_outputs.count(output) > 1}
    )
    for output in duplicate_outputs:
        diagnostics.append(
            {
                "severity": "fatal",
                "code": "R18-ARTIFACT-OUTPUT-DUPLICATE",
                "message": f"{task.task_id} produced duplicate output {output}.",
            }
        )
    for artifact in artifacts:
        if artifact.artifact_type not in required_outputs:
            diagnostics.append(
                {
                    "severity": "fatal",
                    "code": "R18-ARTIFACT-UNREQUESTED-OUTPUT",
                    "message": (f"{artifact.artifact_type} was not requested by {task.task_id}."),
                }
            )
        if artifact.artifact_type not in supported_outputs:
            diagnostics.append(
                {
                    "severity": "fatal",
                    "code": "R18-ARTIFACT-OUTPUT-SCHEMA-MISMATCH",
                    "message": (
                        f"{artifact.artifact_type} is not emitted by {generator.generator_id}."
                    ),
                }
            )
        if not artifact.generated_content:
            diagnostics.append(
                {
                    "severity": "fatal",
                    "code": "R18-ARTIFACT-CONTENT-EMPTY",
                    "message": f"{artifact.artifact_id} has empty generated_content.",
                }
            )
    duplicate_paths = {
        artifact.logical_path
        for artifact in (*previous_artifacts, *artifacts)
        if [item.logical_path for item in (*previous_artifacts, *artifacts)].count(
            artifact.logical_path
        )
        > 1
    }
    for path in sorted(duplicate_paths):
        diagnostics.append(
            {
                "severity": "fatal",
                "code": "R18-DUPLICATE-ARTIFACT-PATH",
                "message": f"Duplicate artifact path {path}.",
            }
        )
    payload = {
        "valid": not diagnostics,
        "validation_rule": task.validation_rule,
        "diagnostics": diagnostics,
    }
    return R18ValidationReport(
        valid=not diagnostics,
        validation_rule=task.validation_rule,
        diagnostics=tuple(diagnostics),
        report_hash=specification_hash(payload),
    )


def _conflict_diagnostics(
    artifacts: tuple[R18ArtifactRecord, ...],
) -> tuple[R18OrchestrationDiagnostic, ...]:
    logical_paths = [item.logical_path for item in artifacts]
    duplicate_paths = sorted({path for path in logical_paths if logical_paths.count(path) > 1})
    return tuple(
        _diag("fatal", "artifact", "R18-DUPLICATE-ARTIFACT-PATH", path) for path in duplicate_paths
    )


def _artifact_repository(
    plan: R17ExecutionPlan,
    artifacts: tuple[R18ArtifactRecord, ...],
    immutable_stage_ids: tuple[str, ...],
    materialized_artifacts: tuple[R18MaterializedArtifact, ...],
) -> R18ArtifactRepositorySnapshot:
    artifact_hashes = tuple(sorted(item.content_hash for item in artifacts))
    payload = {
        "plan_id": plan.plan_id,
        "artifact_hashes": artifact_hashes,
        "immutable_stage_ids": immutable_stage_ids,
        "materialized_artifacts": [item.model_dump(mode="json") for item in materialized_artifacts],
    }
    return R18ArtifactRepositorySnapshot(
        repository_id=f"repo-{plan.plan_id}",
        artifact_count=len(artifacts),
        immutable_stage_ids=immutable_stage_ids,
        artifact_hashes=artifact_hashes,
        materialized_artifacts=materialized_artifacts,
        repository_hash=specification_hash(payload),
    )


def _materialize_artifacts(
    artifacts: tuple[R18ArtifactRecord, ...],
    options: dict[str, Any],
) -> tuple[R18MaterializedArtifact, ...]:
    if options.get("materialize_artifacts") is not True:
        return ()
    root_option = options.get("artifact_root")
    if not isinstance(root_option, str) or not root_option.strip():
        return ()
    root = Path(root_option).resolve()
    materialized: list[R18MaterializedArtifact] = []
    for artifact in artifacts:
        target = (root / "r18-generated-artifacts" / artifact.logical_path).resolve()
        if not target.is_relative_to(root):
            raise ValueError("R18 artifact materialization target escapes artifact_root")
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "artifact": artifact.model_dump(mode="json"),
            "generated_content": artifact.generated_content,
        }
        target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        materialization_payload = {
            "artifact_id": artifact.artifact_id,
            "logical_path": artifact.logical_path,
            "physical_path": str(target),
            "content_hash": artifact.content_hash,
        }
        materialized.append(
            R18MaterializedArtifact(
                **materialization_payload,
                materialization_hash=specification_hash(materialization_payload),
            )
        )
    return tuple(materialized)


def _aggregate_metrics(
    records: tuple[R18TaskExecutionRecord, ...],
    artifacts: tuple[R18ArtifactRecord, ...],
) -> dict[str, int]:
    return {
        "task_count": len(records),
        "completed_task_count": sum(1 for item in records if item.status == "completed"),
        "failed_task_count": sum(1 for item in records if item.status == "failed"),
        "artifact_count": len(artifacts),
        "execution_time_ms": sum(item.metrics.execution_time_ms for item in records),
        "tokens_consumed": sum(item.metrics.tokens_consumed for item in records),
        "memory_mb_peak": max((item.metrics.memory_mb for item in records), default=0),
        "validation_error_count": sum(item.metrics.validation_errors for item in records),
        "retry_count": sum(item.retry_count for item in records),
        "provider_call_count": sum(item.metrics.provider_calls for item in records),
        "provider_tokens_input": sum(item.metrics.provider_tokens_input for item in records),
        "provider_tokens_output": sum(item.metrics.provider_tokens_output for item in records),
    }


def _event(generator_id: str, task_id: str, status: str) -> R18LifecycleEvent:
    payload = {
        "generator_id": generator_id,
        "task_id": task_id,
        "status": status,
        "timestamp": DETERMINISTIC_EXECUTION_TIMESTAMP,
    }
    return R18LifecycleEvent(
        event_id=f"event-{specification_hash(payload)[:16]}",
        event_hash=specification_hash(payload),
        **payload,
    )


def _node(graph: R16KnowledgeGraphModel, node_id: str) -> dict[str, Any]:
    for node in graph.nodes:
        if str(node["id"]) == node_id:
            return node
    raise ValueError(f"Knowledge node {node_id} does not exist")


def _safe(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)


def _optional_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _diag(
    severity: str,
    category: str,
    code: str,
    path: str,
) -> R18OrchestrationDiagnostic:
    return R18OrchestrationDiagnostic(
        severity=severity,
        category=category,
        code=code,
        message=f"{code} at {path}",
        path=path,
    )
