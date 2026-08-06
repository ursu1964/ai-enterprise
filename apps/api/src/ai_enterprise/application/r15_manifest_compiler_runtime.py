from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from ai_enterprise.application.r14_manifest_schema_runtime import r14_validate_manifest
from ai_enterprise.domain.specification.kernel import specification_hash

COMPILER_VERSION = "manifest-compiler-1.1"
DETERMINISTIC_COMPILATION_TIMESTAMP = "1970-01-01T00:00:00Z"

COMPILATION_STAGES: tuple[str, ...] = (
    "manifest_loading",
    "schema_validation",
    "semantic_resolution",
    "registry_expansion",
    "relationship_resolution",
    "dependency_analysis",
    "knowledge_graph_construction",
    "execution_graph_construction",
    "compilation_report",
)

COMPILATION_PASSES: tuple[str, ...] = (
    "semantic_integrity_pass",
    "relationship_enrichment_pass",
    "dependency_validation_pass",
    "incremental_impact_pass",
)


class R15CompilationDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True)

    severity: str
    category: str
    code: str
    message: str
    path: str


class R15KnowledgeGraphNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    type: str
    registry_reference: str
    manifest_origin: str
    version: str
    metadata: dict[str, Any]
    relationships: tuple[str, ...]
    status: str


class R15KnowledgeGraphEdge(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    target: str
    relationship_type: str
    constraint: str | None
    trace_identifier: str


class R15KnowledgeGraph(BaseModel):
    model_config = ConfigDict(frozen=True)

    nodes: tuple[R15KnowledgeGraphNode, ...]
    edges: tuple[R15KnowledgeGraphEdge, ...]
    graph_hash: str


class R15DependencyGraphNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    depends_on: tuple[str, ...]
    dependents: tuple[str, ...]
    trace_node_id: str


class R15DependencyGraphEdge(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    target: str
    relationship_type: str
    trace_identifier: str


class R15DependencyGraph(BaseModel):
    model_config = ConfigDict(frozen=True)

    directed: bool
    acyclic: bool
    nodes: tuple[R15DependencyGraphNode, ...]
    edges: tuple[R15DependencyGraphEdge, ...]
    graph_hash: str


class R15ExecutionGraphNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    depends_on: tuple[str, ...]
    trace_node_ids: tuple[str, ...]
    status: str


class R15ExecutionGraphEdge(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    target: str
    relationship_type: str
    trace_identifier: str


class R15ExecutionGraph(BaseModel):
    model_config = ConfigDict(frozen=True)

    directed: bool
    acyclic: bool
    version: str
    incrementally_updateable: bool
    nodes: tuple[R15ExecutionGraphNode, ...]
    edges: tuple[R15ExecutionGraphEdge, ...]
    graph_hash: str


class R15CompilationPassReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    status: str
    emitted_diagnostics: int
    output_hash: str


class R15IncrementalCompilationImpact(BaseModel):
    model_config = ConfigDict(frozen=True)

    previous_result_hash: str | None
    changed_node_ids: tuple[str, ...]
    changed_edge_ids: tuple[str, ...]
    reusable_node_ids: tuple[str, ...]
    affected_execution_step_ids: tuple[str, ...]
    impact_hash: str


class R15CompilationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    manifest_version: str | None
    registry_version: str | None
    compiler_version: str
    compilation_timestamp: str
    stages: tuple[str, ...]
    passes: tuple[str, ...]
    expanded_object_count: int
    resolved_dependency_count: int
    warning_count: int
    error_count: int
    graph_statistics: dict[str, int]
    execution_plan_summary: tuple[str, ...]
    report_hash: str


class R15CompilationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    success_status: bool
    knowledge_graph: R15KnowledgeGraph | None
    dependency_graph: R15DependencyGraph | None
    execution_graph: R15ExecutionGraph | None
    incremental_impact: R15IncrementalCompilationImpact
    pass_reports: tuple[R15CompilationPassReport, ...]
    compilation_report: R15CompilationReport
    diagnostics: tuple[R15CompilationDiagnostic, ...]
    result_hash: str


CompilationPass = Callable[
    [
        dict[str, Any],
        tuple[R15KnowledgeGraphNode, ...],
        tuple[R15KnowledgeGraphEdge, ...],
    ],
    tuple[tuple[R15KnowledgeGraphEdge, ...], tuple[R15CompilationDiagnostic, ...]],
]


def r15_compile_manifest(
    manifest: dict[str, Any],
    schema_path: Path,
    registry_root: Path,
    *,
    compiler_options: dict[str, Any] | None = None,
) -> R15CompilationResult:
    options = compiler_options or {}
    timestamp = str(options.get("compilation_timestamp", DETERMINISTIC_COMPILATION_TIMESTAMP))
    previous_result = options.get("previous_result")

    validation = r14_validate_manifest(manifest, schema_path, registry_root)
    validation_diagnostics = tuple(
        R15CompilationDiagnostic(
            severity=item.severity,
            category="validation",
            code=item.code,
            message=item.detail,
            path=item.path,
        )
        for item in validation.findings
    )
    semantic_diagnostics = _semantic_diagnostics(manifest)
    diagnostics = validation_diagnostics + semantic_diagnostics
    if not validation.valid:
        impact = _incremental_impact(None, None, previous_result)
        report = _report(manifest, None, None, None, diagnostics, timestamp, ())
        return _result(False, None, None, None, impact, (), report, diagnostics)

    registry = _load_registry(registry_root)
    nodes, node_diagnostics = _knowledge_nodes(manifest, registry)
    edges = _knowledge_edges(manifest)
    edges, pass_reports, pass_diagnostics = _run_compilation_passes(manifest, nodes, edges)
    dependency_graph = _dependency_graph(nodes, edges)
    dependency_diagnostics = _dependency_diagnostics(dependency_graph)
    diagnostics = (
        diagnostics
        + node_diagnostics
        + pass_diagnostics
        + dependency_diagnostics
    )

    if any(item.severity == "fatal" for item in diagnostics):
        impact = _incremental_impact(None, dependency_graph, previous_result)
        report = _report(
            manifest,
            None,
            dependency_graph,
            None,
            diagnostics,
            timestamp,
            pass_reports,
        )
        return _result(
            False,
            None,
            dependency_graph,
            None,
            impact,
            pass_reports,
            report,
            diagnostics,
        )

    knowledge_graph = _knowledge_graph(nodes, edges)
    execution_graph = _execution_graph(knowledge_graph)
    impact = _incremental_impact(knowledge_graph, dependency_graph, previous_result)
    report = _report(
        manifest,
        knowledge_graph,
        dependency_graph,
        execution_graph,
        diagnostics,
        timestamp,
        pass_reports,
    )
    return _result(
        True,
        knowledge_graph,
        dependency_graph,
        execution_graph,
        impact,
        pass_reports,
        report,
        diagnostics,
    )


def r15_persist_compilation_history(
    result: R15CompilationResult,
    history_path: Path,
    *,
    actor_id: str,
) -> str:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": "r15-compilation-history-1.0",
        "compiler_version": COMPILER_VERSION,
        "actor_id": actor_id,
        "success_status": result.success_status,
        "result_hash": result.result_hash,
        "manifest_version": result.compilation_report.manifest_version,
        "registry_version": result.compilation_report.registry_version,
        "knowledge_graph_hash": (
            result.knowledge_graph.graph_hash if result.knowledge_graph else None
        ),
        "dependency_graph_hash": (
            result.dependency_graph.graph_hash if result.dependency_graph else None
        ),
        "execution_graph_hash": (
            result.execution_graph.graph_hash if result.execution_graph else None
        ),
        "diagnostic_codes": [item.code for item in result.diagnostics],
        "report_hash": result.compilation_report.report_hash,
    }
    record_hash = specification_hash(record)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({**record, "record_hash": record_hash}, sort_keys=True))
        handle.write("\n")
    return record_hash


def r15_read_compilation_history(history_path: Path) -> tuple[dict[str, Any], ...]:
    if not history_path.exists():
        return ()
    records: list[dict[str, Any]] = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return tuple(records)


def _load_registry(root: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for candidate in sorted(root.glob("*/*.json")):
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("id"), str):
            records[payload["id"]] = {
                **payload,
                "_registry_reference": str(candidate.relative_to(root.parent)),
            }
    return records


def _semantic_diagnostics(
    manifest: dict[str, Any],
) -> tuple[R15CompilationDiagnostic, ...]:
    diagnostics: list[R15CompilationDiagnostic] = []
    seen: dict[str, str] = {}
    for section in _node_sections():
        value = manifest.get(section)
        if not isinstance(value, list):
            continue
        for index, item in enumerate(value):
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            identifier = item["id"]
            path = f"{section}/{index}/id"
            if identifier in seen:
                diagnostics.append(
                    R15CompilationDiagnostic(
                        severity="fatal",
                        category="semantic",
                        code="R15-DUPLICATE-ID",
                        message=f"Duplicate semantic identifier {identifier}.",
                        path=path,
                    )
                )
            else:
                seen[identifier] = path
    known_ids = frozenset(seen)
    diagnostics.extend(_dependency_reference_diagnostics(manifest, known_ids))
    diagnostics.extend(_dependency_cycle_diagnostics_from_manifest(manifest, known_ids))
    diagnostics.extend(_workflow_reference_diagnostics(manifest, known_ids))
    diagnostics.extend(_advisory_diagnostics(manifest))
    return tuple(sorted(diagnostics, key=lambda item: (item.severity, item.code, item.path)))


def _dependency_reference_diagnostics(
    manifest: dict[str, Any],
    known_ids: frozenset[str],
) -> tuple[R15CompilationDiagnostic, ...]:
    diagnostics: list[R15CompilationDiagnostic] = []
    for section in _node_sections():
        value = manifest.get(section)
        if not isinstance(value, list):
            continue
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                continue
            for dependency_index, dependency in enumerate(item.get("dependsOn", [])):
                if isinstance(dependency, str) and dependency not in known_ids:
                    diagnostics.append(
                        R15CompilationDiagnostic(
                            severity="fatal",
                            category="semantic",
                            code="R15-UNDEFINED-DEPENDENCY",
                            message=f"Dependency {dependency} is not defined in the Manifest.",
                            path=f"{section}/{index}/dependsOn/{dependency_index}",
                        )
                    )
    return tuple(diagnostics)


def _dependency_cycle_diagnostics_from_manifest(
    manifest: dict[str, Any],
    known_ids: frozenset[str],
) -> tuple[R15CompilationDiagnostic, ...]:
    graph: dict[str, set[str]] = {identifier: set() for identifier in known_ids}
    for section in _node_sections():
        value = manifest.get(section)
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            graph.setdefault(item["id"], set()).update(
                dependency
                for dependency in item.get("dependsOn", [])
                if isinstance(dependency, str) and dependency in known_ids
            )
    return tuple(
        R15CompilationDiagnostic(
            severity="fatal",
            category="dependency",
            code="R15-CIRCULAR-DEPENDENCY",
            message=f"Circular dependency detected: {' -> '.join(cycle)}.",
            path="dependsOn",
        )
        for cycle in _dependency_cycles(graph)
    )


def _workflow_reference_diagnostics(
    manifest: dict[str, Any],
    known_ids: frozenset[str],
) -> tuple[R15CompilationDiagnostic, ...]:
    diagnostics: list[R15CompilationDiagnostic] = []
    workflows = manifest.get("workflows", [])
    if not isinstance(workflows, list):
        return ()
    for workflow_index, workflow in enumerate(workflows):
        if not isinstance(workflow, dict):
            continue
        steps = workflow.get("steps", [])
        if not isinstance(steps, list):
            continue
        for step_index, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            capability_id = step.get("capabilityId")
            if isinstance(capability_id, str) and capability_id not in known_ids:
                diagnostics.append(
                    R15CompilationDiagnostic(
                        severity="fatal",
                        category="semantic",
                        code="R15-UNDEFINED-WORKFLOW-CAPABILITY",
                        message=f"Workflow capability {capability_id} is not defined.",
                        path=f"workflows/{workflow_index}/steps/{step_index}/capabilityId",
                    )
                )
            for entity_index, entity_id in enumerate(step.get("entityIds", [])):
                if isinstance(entity_id, str) and entity_id not in known_ids:
                    diagnostics.append(
                        R15CompilationDiagnostic(
                            severity="fatal",
                            category="semantic",
                            code="R15-UNDEFINED-WORKFLOW-ENTITY",
                            message=f"Workflow entity {entity_id} is not defined.",
                            path=(
                                f"workflows/{workflow_index}/steps/"
                                f"{step_index}/entityIds/{entity_index}"
                            ),
                        )
                    )
    return tuple(diagnostics)


def _advisory_diagnostics(manifest: dict[str, Any]) -> tuple[R15CompilationDiagnostic, ...]:
    used_capabilities = {
        step.get("capabilityId")
        for workflow in manifest.get("workflows", [])
        if isinstance(workflow, dict)
        for step in workflow.get("steps", [])
        if isinstance(step, dict)
    }
    diagnostics: list[R15CompilationDiagnostic] = []
    capabilities = manifest.get("capabilities", [])
    if isinstance(capabilities, list):
        for index, capability in enumerate(capabilities):
            if (
                isinstance(capability, dict)
                and isinstance(capability.get("id"), str)
                and capability["id"] not in used_capabilities
            ):
                diagnostics.append(
                    R15CompilationDiagnostic(
                        severity="advisory",
                        category="semantic",
                        code="R15-UNUSED-CAPABILITY",
                        message=f"Capability {capability['id']} is not used by any workflow.",
                        path=f"capabilities/{index}/id",
                    )
                )
    return tuple(diagnostics)


def _knowledge_nodes(
    manifest: dict[str, Any],
    registry: dict[str, dict[str, Any]],
) -> tuple[tuple[R15KnowledgeGraphNode, ...], tuple[R15CompilationDiagnostic, ...]]:
    diagnostics: list[R15CompilationDiagnostic] = []
    nodes: list[R15KnowledgeGraphNode] = []
    version = _manifest_version(manifest) or "unknown"
    for section, node_type in _node_sections().items():
        value = manifest.get(section)
        if not isinstance(value, list):
            continue
        for index, item in enumerate(value):
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            identifier = item["id"]
            registry_record = registry.get(identifier)
            if registry_record is None:
                diagnostics.append(
                    R15CompilationDiagnostic(
                        severity="fatal",
                        category="registry",
                        code="R15-MISSING-REGISTRY",
                        message=f"Registry object is missing for {identifier}.",
                        path=f"{section}/{index}/id",
                    )
                )
                continue
            nodes.append(
                R15KnowledgeGraphNode(
                    id=identifier,
                    type=node_type,
                    registry_reference=str(registry_record["_registry_reference"]),
                    manifest_origin=f"{section}/{index}",
                    version=version,
                    metadata=_node_metadata(item, registry_record),
                    relationships=tuple(_relationships(item)),
                    status="resolved",
                )
            )
    return tuple(sorted(nodes, key=lambda item: (item.type, item.id))), tuple(diagnostics)


def _knowledge_edges(manifest: dict[str, Any]) -> tuple[R15KnowledgeGraphEdge, ...]:
    edges: list[R15KnowledgeGraphEdge] = []
    workflows = manifest.get("workflows", [])
    if isinstance(workflows, list):
        for workflow in workflows:
            if not isinstance(workflow, dict) or not isinstance(workflow.get("id"), str):
                continue
            workflow_id = workflow["id"]
            for step_index, step in enumerate(workflow.get("steps", [])):
                if not isinstance(step, dict):
                    continue
                capability_id = step.get("capabilityId")
                if isinstance(capability_id, str):
                    edges.append(_edge(workflow_id, capability_id, "uses"))
                    edges.append(
                        _edge(
                            workflow_id,
                            capability_id,
                            "triggers",
                            constraint=f"workflow.steps[{step_index}]",
                        )
                    )
                for entity_id in step.get("entityIds", []):
                    if isinstance(entity_id, str):
                        edges.append(_edge(workflow_id, entity_id, "references"))
                        if isinstance(capability_id, str):
                            edges.append(_edge(capability_id, entity_id, "consumes"))
    capabilities = manifest.get("capabilities", [])
    if isinstance(capabilities, list):
        for capability in capabilities:
            if not isinstance(capability, dict) or not isinstance(capability.get("id"), str):
                continue
            for user_id in capability.get("userIds", []):
                if isinstance(user_id, str):
                    edges.append(_edge(user_id, capability["id"], "owns"))
    for section in _node_sections():
        value = manifest.get(section)
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            for dependency in item.get("dependsOn", []):
                if isinstance(dependency, str):
                    edges.append(_edge(item["id"], dependency, "requires"))
    return _unique_edges(edges)


def _run_compilation_passes(
    manifest: dict[str, Any],
    nodes: tuple[R15KnowledgeGraphNode, ...],
    edges: tuple[R15KnowledgeGraphEdge, ...],
) -> tuple[
    tuple[R15KnowledgeGraphEdge, ...],
    tuple[R15CompilationPassReport, ...],
    tuple[R15CompilationDiagnostic, ...],
]:
    diagnostics: list[R15CompilationDiagnostic] = []
    pass_reports: list[R15CompilationPassReport] = []
    current_edges = edges
    for name, compilation_pass in _compilation_passes():
        before = len(diagnostics)
        current_edges, emitted = compilation_pass(manifest, nodes, current_edges)
        diagnostics.extend(emitted)
        payload = {
            "name": name,
            "nodes": [item.model_dump(mode="json") for item in nodes],
            "edges": [item.model_dump(mode="json") for item in current_edges],
            "diagnostics": [item.model_dump(mode="json") for item in emitted],
        }
        pass_reports.append(
            R15CompilationPassReport(
                name=name,
                status="completed",
                emitted_diagnostics=len(diagnostics) - before,
                output_hash=specification_hash(payload),
            )
        )
    return current_edges, tuple(pass_reports), tuple(diagnostics)


def _compilation_passes() -> tuple[tuple[str, CompilationPass], ...]:
    return (
        ("semantic_integrity_pass", _semantic_integrity_pass),
        ("relationship_enrichment_pass", _relationship_enrichment_pass),
        ("dependency_validation_pass", _dependency_validation_pass),
        ("incremental_impact_pass", _incremental_impact_pass),
    )


def _semantic_integrity_pass(
    manifest: dict[str, Any],
    nodes: tuple[R15KnowledgeGraphNode, ...],
    edges: tuple[R15KnowledgeGraphEdge, ...],
) -> tuple[tuple[R15KnowledgeGraphEdge, ...], tuple[R15CompilationDiagnostic, ...]]:
    del manifest, nodes
    return edges, ()


def _relationship_enrichment_pass(
    manifest: dict[str, Any],
    nodes: tuple[R15KnowledgeGraphNode, ...],
    edges: tuple[R15KnowledgeGraphEdge, ...],
) -> tuple[tuple[R15KnowledgeGraphEdge, ...], tuple[R15CompilationDiagnostic, ...]]:
    del manifest
    enriched = list(edges)
    entities = tuple(node for node in nodes if node.type == "entity")
    reports = tuple(node for node in nodes if node.type == "report")
    for report in reports:
        for entity in entities:
            enriched.append(_edge(report.id, entity.id, "produces"))
    policies = tuple(node for node in nodes if node.type == "policy")
    constraints = tuple(node for node in nodes if node.type == "constraint")
    for policy in policies:
        for constraint in constraints:
            enriched.append(_edge(policy.id, constraint.id, "implements"))
    return _unique_edges(enriched), ()


def _dependency_validation_pass(
    manifest: dict[str, Any],
    nodes: tuple[R15KnowledgeGraphNode, ...],
    edges: tuple[R15KnowledgeGraphEdge, ...],
) -> tuple[tuple[R15KnowledgeGraphEdge, ...], tuple[R15CompilationDiagnostic, ...]]:
    del manifest, nodes
    return edges, ()


def _incremental_impact_pass(
    manifest: dict[str, Any],
    nodes: tuple[R15KnowledgeGraphNode, ...],
    edges: tuple[R15KnowledgeGraphEdge, ...],
) -> tuple[tuple[R15KnowledgeGraphEdge, ...], tuple[R15CompilationDiagnostic, ...]]:
    del manifest, nodes
    return edges, ()


def _dependency_graph(
    nodes: tuple[R15KnowledgeGraphNode, ...],
    edges: tuple[R15KnowledgeGraphEdge, ...],
) -> R15DependencyGraph:
    dependency_edges = tuple(edge for edge in edges if edge.relationship_type == "requires")
    depends_on: dict[str, set[str]] = {node.id: set() for node in nodes}
    dependents: dict[str, set[str]] = {node.id: set() for node in nodes}
    for edge in dependency_edges:
        depends_on.setdefault(edge.source, set()).add(edge.target)
        dependents.setdefault(edge.target, set()).add(edge.source)
    graph_nodes = tuple(
        R15DependencyGraphNode(
            id=node_id,
            depends_on=tuple(sorted(depends_on[node_id])),
            dependents=tuple(sorted(dependents[node_id])),
            trace_node_id=node_id,
        )
        for node_id in sorted(depends_on)
    )
    graph_edges = tuple(
        R15DependencyGraphEdge(
            source=edge.source,
            target=edge.target,
            relationship_type="depends_on",
            trace_identifier=edge.trace_identifier,
        )
        for edge in dependency_edges
    )
    payload = {
        "nodes": [item.model_dump(mode="json") for item in graph_nodes],
        "edges": [item.model_dump(mode="json") for item in graph_edges],
    }
    return R15DependencyGraph(
        directed=True,
        acyclic=not _dependency_cycles(depends_on),
        nodes=graph_nodes,
        edges=graph_edges,
        graph_hash=specification_hash(payload),
    )


def _dependency_diagnostics(
    dependency_graph: R15DependencyGraph,
) -> tuple[R15CompilationDiagnostic, ...]:
    depends_on = {node.id: set(node.depends_on) for node in dependency_graph.nodes}
    return tuple(
        R15CompilationDiagnostic(
            severity="fatal",
            category="dependency",
            code="R15-CIRCULAR-DEPENDENCY",
            message=f"Circular dependency detected: {' -> '.join(cycle)}.",
            path="dependsOn",
        )
        for cycle in _dependency_cycles(depends_on)
    )


def _dependency_cycles(graph: dict[str, set[str]]) -> tuple[tuple[str, ...], ...]:
    cycles: set[tuple[str, ...]] = set()
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            start = visiting.index(node)
            cycle = tuple(visiting[start:] + [node])
            normalized = min(
                tuple(cycle[index:-1] + cycle[:index] + (cycle[index],))
                for index in range(len(cycle) - 1)
            )
            cycles.add(normalized)
            return
        if node in visited:
            return
        visiting.append(node)
        for dependency in sorted(graph.get(node, set())):
            if dependency in graph:
                visit(dependency)
        visiting.pop()
        visited.add(node)

    for node in sorted(graph):
        visit(node)
    return tuple(sorted(cycles))


def _knowledge_graph(
    nodes: tuple[R15KnowledgeGraphNode, ...],
    edges: tuple[R15KnowledgeGraphEdge, ...],
) -> R15KnowledgeGraph:
    payload = {
        "nodes": [item.model_dump(mode="json") for item in nodes],
        "edges": [item.model_dump(mode="json") for item in edges],
    }
    return R15KnowledgeGraph(nodes=nodes, edges=edges, graph_hash=specification_hash(payload))


def _execution_graph(knowledge_graph: R15KnowledgeGraph) -> R15ExecutionGraph:
    node_ids = {item.id for item in knowledge_graph.nodes}
    execution_nodes = (
        R15ExecutionGraphNode(
            id="create-business-entities",
            name="Create Entities",
            depends_on=(),
            trace_node_ids=_trace_nodes(knowledge_graph, "entity"),
            status="pending",
        ),
        R15ExecutionGraphNode(
            id="generate-database",
            name="Generate Database",
            depends_on=("create-business-entities",),
            trace_node_ids=_trace_nodes(knowledge_graph, "entity"),
            status="pending",
        ),
        R15ExecutionGraphNode(
            id="generate-apis",
            name="Generate APIs",
            depends_on=("generate-database",),
            trace_node_ids=_trace_nodes(knowledge_graph, "capability"),
            status="pending",
        ),
        R15ExecutionGraphNode(
            id="generate-backend",
            name="Generate Backend",
            depends_on=("generate-apis",),
            trace_node_ids=_trace_nodes(knowledge_graph, "workflow"),
            status="pending",
        ),
        R15ExecutionGraphNode(
            id="generate-ui",
            name="Generate UI",
            depends_on=("generate-backend",),
            trace_node_ids=_trace_nodes(knowledge_graph, "role"),
            status="pending",
        ),
        R15ExecutionGraphNode(
            id="generate-tests",
            name="Generate Tests",
            depends_on=("generate-ui",),
            trace_node_ids=tuple(sorted(node_ids)),
            status="pending",
        ),
        R15ExecutionGraphNode(
            id="generate-documentation",
            name="Generate Documentation",
            depends_on=("generate-tests",),
            trace_node_ids=tuple(sorted(node_ids)),
            status="pending",
        ),
        R15ExecutionGraphNode(
            id="package-system",
            name="Package System",
            depends_on=("generate-documentation",),
            trace_node_ids=tuple(sorted(node_ids)),
            status="pending",
        ),
    )
    execution_edges = tuple(
        R15ExecutionGraphEdge(
            source=dependency,
            target=node.id,
            relationship_type="precedes",
            trace_identifier=specification_hash({"source": dependency, "target": node.id}),
        )
        for node in execution_nodes
        for dependency in node.depends_on
    )
    payload = {
        "nodes": [item.model_dump(mode="json") for item in execution_nodes],
        "edges": [item.model_dump(mode="json") for item in execution_edges],
    }
    return R15ExecutionGraph(
        directed=True,
        acyclic=True,
        version=COMPILER_VERSION,
        incrementally_updateable=True,
        nodes=execution_nodes,
        edges=execution_edges,
        graph_hash=specification_hash(payload),
    )


def _incremental_impact(
    knowledge_graph: R15KnowledgeGraph | None,
    dependency_graph: R15DependencyGraph | None,
    previous_result: object,
) -> R15IncrementalCompilationImpact:
    previous = previous_result if isinstance(previous_result, dict) else {}
    previous_nodes = _previous_nodes(previous)
    previous_edges = _previous_edges(previous)
    current_nodes = (
        {
            node.id: specification_hash(node.model_dump(mode="json"))
            for node in knowledge_graph.nodes
        }
        if knowledge_graph
        else {}
    )
    current_edges = (
        {
            edge.trace_identifier: specification_hash(edge.model_dump(mode="json"))
            for edge in dependency_graph.edges
        }
        if dependency_graph
        else {}
    )
    changed_nodes = tuple(
        sorted(
            node_id
            for node_id, node_hash in current_nodes.items()
            if previous_nodes.get(node_id) != node_hash
        )
    )
    changed_edges = tuple(
        sorted(
            edge_id
            for edge_id, edge_hash in current_edges.items()
            if previous_edges.get(edge_id) != edge_hash
        )
    )
    reusable_nodes = tuple(
        sorted(
            node_id
            for node_id, node_hash in current_nodes.items()
            if previous_nodes.get(node_id) == node_hash
        )
    )
    affected_steps = _affected_execution_steps(changed_nodes) if knowledge_graph else ()
    payload = {
        "previous_result_hash": previous.get("result_hash"),
        "changed_node_ids": changed_nodes,
        "changed_edge_ids": changed_edges,
        "reusable_node_ids": reusable_nodes,
        "affected_execution_step_ids": affected_steps,
    }
    return R15IncrementalCompilationImpact(
        previous_result_hash=previous.get("result_hash"),
        changed_node_ids=changed_nodes,
        changed_edge_ids=changed_edges,
        reusable_node_ids=reusable_nodes,
        affected_execution_step_ids=affected_steps,
        impact_hash=specification_hash(payload),
    )


def _previous_nodes(previous: dict[str, Any]) -> dict[str, str]:
    graph = previous.get("knowledge_graph")
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list):
        return {}
    nodes: dict[str, str] = {}
    for item in graph["nodes"]:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            nodes[item["id"]] = specification_hash(item)
    return nodes


def _previous_edges(previous: dict[str, Any]) -> dict[str, str]:
    graph = previous.get("dependency_graph")
    if not isinstance(graph, dict) or not isinstance(graph.get("edges"), list):
        return {}
    edges: dict[str, str] = {}
    for item in graph["edges"]:
        if isinstance(item, dict) and isinstance(item.get("trace_identifier"), str):
            edges[item["trace_identifier"]] = specification_hash(item)
    return edges


def _affected_execution_steps(changed_node_ids: tuple[str, ...]) -> tuple[str, ...]:
    if not changed_node_ids:
        return ()
    return (
        "create-business-entities",
        "generate-database",
        "generate-apis",
        "generate-backend",
        "generate-ui",
        "generate-tests",
        "generate-documentation",
        "package-system",
    )


def _trace_nodes(
    knowledge_graph: R15KnowledgeGraph,
    node_type: str,
) -> tuple[str, ...]:
    return tuple(sorted(item.id for item in knowledge_graph.nodes if item.type == node_type))


def _report(
    manifest: dict[str, Any],
    knowledge_graph: R15KnowledgeGraph | None,
    dependency_graph: R15DependencyGraph | None,
    execution_graph: R15ExecutionGraph | None,
    diagnostics: tuple[R15CompilationDiagnostic, ...],
    timestamp: str,
    pass_reports: tuple[R15CompilationPassReport, ...],
) -> R15CompilationReport:
    statistics = {
        "knowledge_nodes": len(knowledge_graph.nodes) if knowledge_graph else 0,
        "knowledge_edges": len(knowledge_graph.edges) if knowledge_graph else 0,
        "dependency_nodes": len(dependency_graph.nodes) if dependency_graph else 0,
        "dependency_edges": len(dependency_graph.edges) if dependency_graph else 0,
        "execution_nodes": len(execution_graph.nodes) if execution_graph else 0,
        "execution_edges": len(execution_graph.edges) if execution_graph else 0,
        "diagnostics": len(diagnostics),
    }
    summary = tuple(node.name for node in execution_graph.nodes) if execution_graph else ()
    payload = {
        "manifest_version": _manifest_version(manifest),
        "registry_version": _registry_version(manifest),
        "compiler_version": COMPILER_VERSION,
        "compilation_timestamp": timestamp,
        "stages": list(COMPILATION_STAGES),
        "passes": [item.name for item in pass_reports],
        "graph_statistics": statistics,
        "execution_plan_summary": list(summary),
    }
    return R15CompilationReport(
        manifest_version=_manifest_version(manifest),
        registry_version=_registry_version(manifest),
        compiler_version=COMPILER_VERSION,
        compilation_timestamp=timestamp,
        stages=COMPILATION_STAGES,
        passes=tuple(item.name for item in pass_reports),
        expanded_object_count=statistics["knowledge_nodes"],
        resolved_dependency_count=statistics["dependency_edges"],
        warning_count=sum(1 for item in diagnostics if item.severity == "advisory"),
        error_count=sum(1 for item in diagnostics if item.severity in {"error", "fatal"}),
        graph_statistics=statistics,
        execution_plan_summary=summary,
        report_hash=specification_hash(payload),
    )


def _result(
    success: bool,
    knowledge_graph: R15KnowledgeGraph | None,
    dependency_graph: R15DependencyGraph | None,
    execution_graph: R15ExecutionGraph | None,
    impact: R15IncrementalCompilationImpact,
    pass_reports: tuple[R15CompilationPassReport, ...],
    report: R15CompilationReport,
    diagnostics: tuple[R15CompilationDiagnostic, ...],
) -> R15CompilationResult:
    payload = {
        "success_status": success,
        "knowledge_graph": knowledge_graph.model_dump(mode="json") if knowledge_graph else None,
        "dependency_graph": dependency_graph.model_dump(mode="json") if dependency_graph else None,
        "execution_graph": execution_graph.model_dump(mode="json") if execution_graph else None,
        "incremental_impact": impact.model_dump(mode="json"),
        "pass_reports": [item.model_dump(mode="json") for item in pass_reports],
        "compilation_report": report.model_dump(mode="json"),
        "diagnostics": [item.model_dump(mode="json") for item in diagnostics],
    }
    return R15CompilationResult(
        success_status=success,
        knowledge_graph=knowledge_graph,
        dependency_graph=dependency_graph,
        execution_graph=execution_graph,
        incremental_impact=impact,
        pass_reports=pass_reports,
        compilation_report=report,
        diagnostics=diagnostics,
        result_hash=specification_hash(payload),
    )


def _node_sections() -> dict[str, str]:
    return {
        "objectives": "objective",
        "users": "role",
        "businessEntities": "entity",
        "capabilities": "capability",
        "workflows": "workflow",
        "businessRules": "business_rule",
        "policies": "policy",
        "integrations": "integration",
        "reporting": "report",
        "security": "security",
        "quality": "quality",
        "constraints": "constraint",
    }


def _node_metadata(item: dict[str, Any], registry_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "manifest": {key: value for key, value in item.items() if key not in {"dependsOn"}},
        "registry": {
            key: value for key, value in registry_record.items() if not key.startswith("_")
        },
    }


def _relationships(item: dict[str, Any]) -> list[str]:
    relationships: list[str] = []
    for dependency in item.get("dependsOn", []):
        if isinstance(dependency, str):
            relationships.append(dependency)
    return sorted(relationships)


def _unique_edges(
    edges: list[R15KnowledgeGraphEdge],
) -> tuple[R15KnowledgeGraphEdge, ...]:
    unique_edges = {
        (item.source, item.target, item.relationship_type, item.constraint): item
        for item in edges
    }
    return tuple(unique_edges[key] for key in sorted(unique_edges))


def _edge(
    source: str,
    target: str,
    relationship_type: str,
    *,
    constraint: str | None = None,
) -> R15KnowledgeGraphEdge:
    return R15KnowledgeGraphEdge(
        source=source,
        target=target,
        relationship_type=relationship_type,
        constraint=constraint,
        trace_identifier=specification_hash(
            {
                "source": source,
                "target": target,
                "relationship_type": relationship_type,
                "constraint": constraint,
            }
        ),
    )


def _manifest_version(manifest: dict[str, Any]) -> str | None:
    version = manifest.get("version")
    if isinstance(version, dict) and isinstance(version.get("manifestVersion"), str):
        return version["manifestVersion"]
    return None


def _registry_version(manifest: dict[str, Any]) -> str | None:
    version = manifest.get("version")
    if isinstance(version, dict) and isinstance(version.get("registryVersion"), str):
        return version["registryVersion"]
    return None
