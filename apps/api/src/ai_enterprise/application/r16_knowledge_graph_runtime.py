from __future__ import annotations

import base64
import json
from collections import deque
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from ai_enterprise.domain.specification.kernel import specification_hash

GRAPH_MODEL_VERSION = "knowledge-graph-model-1.0"

GRAPH_LAYERS: tuple[str, ...] = (
    "identity",
    "business_structure",
    "behavior",
    "policies",
    "dependencies",
    "execution_metadata",
    "traceability",
)

NODE_TAXONOMY: dict[str, str] = {
    "organization": "business_structure",
    "domain": "business_structure",
    "business_unit": "business_structure",
    "role": "business_structure",
    "actor": "business_structure",
    "entity": "business_structure",
    "attribute": "business_structure",
    "capability": "behavior",
    "workflow": "behavior",
    "step": "behavior",
    "policy": "policies",
    "business_rule": "policies",
    "rule": "policies",
    "constraint": "policies",
    "event": "behavior",
    "integration": "behavior",
    "report": "behavior",
    "document": "traceability",
    "notification": "behavior",
    "ui_view": "behavior",
    "api_contract": "behavior",
    "infrastructure_requirement": "dependencies",
    "quality": "policies",
    "security": "policies",
    "objective": "business_structure",
}

RELATIONSHIP_MODEL: dict[str, str] = {
    "has": "Source contains or aggregates target.",
    "belongs_to": "Source is scoped under target.",
    "uses": "Source uses target to fulfill behavior.",
    "produces": "Source produces target as a semantic output.",
    "consumes": "Source consumes target as a semantic input.",
    "owns": "Source owns or is accountable for target.",
    "references": "Source explicitly references target.",
    "depends_on": "Source cannot be realized before target.",
    "requires": "Source requires target as a business dependency.",
    "triggers": "Source triggers target.",
    "validates": "Source validates target.",
    "extends": "Source extends target semantics.",
    "implements": "Source implements target semantics.",
    "secures": "Source secures target.",
    "constrains": "Source constrains target.",
}

EXPORT_FORMATS: tuple[str, ...] = (
    "json",
    "property_graph",
    "rdf",
    "owl",
    "graphql",
    "neo4j",
    "custom_binary",
)


class R16GraphDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True)

    severity: str
    code: str
    message: str
    path: str


class R16OntologyContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    graph_model_version: str
    layers: tuple[str, ...]
    node_taxonomy: dict[str, str]
    relationship_model: dict[str, str]
    export_formats: tuple[str, ...]
    contract_hash: str


class R16KnowledgeGraphModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    graph_model_version: str
    source_graph_hash: str
    graph_version: str
    immutable: bool
    layers: tuple[str, ...]
    nodes: tuple[dict[str, Any], ...]
    edges: tuple[dict[str, Any], ...]
    partitions: dict[str, tuple[str, ...]]
    metadata: dict[str, Any]
    graph_hash: str


class R16GraphValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    diagnostics: tuple[R16GraphDiagnostic, ...]
    report_hash: str


class R16GraphQueryResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: dict[str, Any]
    nodes: tuple[dict[str, Any], ...]
    edges: tuple[dict[str, Any], ...]
    result_hash: str


class R16GraphTraversalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    start_node_id: str
    max_depth: int
    visited_node_ids: tuple[str, ...]
    traversed_edge_ids: tuple[str, ...]
    result_hash: str


class R16GraphDiffResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    added_node_ids: tuple[str, ...]
    removed_node_ids: tuple[str, ...]
    changed_node_ids: tuple[str, ...]
    added_edge_ids: tuple[str, ...]
    removed_edge_ids: tuple[str, ...]
    changed_edge_ids: tuple[str, ...]
    diff_hash: str


class R16GraphExportResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    export_format: str
    document: dict[str, Any] | str
    export_hash: str


class R16GraphBackendCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    configured: bool
    ready: bool
    detail: str
    required: tuple[str, ...] = ()


class R16GraphBackendReadiness(BaseModel):
    model_config = ConfigDict(frozen=True)

    backend: str
    ready: bool
    partition_strategy: str
    checks: tuple[R16GraphBackendCheck, ...]


class R16GraphBackendPublication(BaseModel):
    model_config = ConfigDict(frozen=True)

    backend: str
    graph_version: str
    graph_hash: str
    publication_ref: str
    ready: bool
    published: bool
    dry_run: bool
    detail: str
    command: tuple[str, ...] = ()


def r16_ontology_contract(registry_root: Path | None = None) -> R16OntologyContract:
    relationship_model = _relationship_model(registry_root)
    payload = {
        "graph_model_version": GRAPH_MODEL_VERSION,
        "layers": list(GRAPH_LAYERS),
        "node_taxonomy": NODE_TAXONOMY,
        "relationship_model": relationship_model,
        "export_formats": list(EXPORT_FORMATS),
    }
    return R16OntologyContract(**payload, contract_hash=specification_hash(payload))


def r16_load_graph(
    knowledge_graph: dict[str, Any],
    *,
    compilation_report: dict[str, Any] | None = None,
    registry_root: Path | None = None,
) -> R16KnowledgeGraphModel:
    relationship_model = _relationship_model(registry_root)
    base_nodes = tuple(
        _canonical_node(item, compilation_report)
        for item in _items(knowledge_graph, "nodes")
    )
    source_hash = str(knowledge_graph.get("graph_hash", specification_hash(knowledge_graph)))
    root_node = _root_node(source_hash, compilation_report)
    nodes = (root_node, *base_nodes)
    edges = (
        *tuple(
            _canonical_edge(item, relationship_model)
            for item in _items(knowledge_graph, "edges")
        ),
        *_root_edges(root_node["id"], base_nodes, relationship_model),
        *_governance_edges(base_nodes, relationship_model),
    )
    graph_version = _graph_version(compilation_report, source_hash)
    metadata = {
        "manifest_version": (compilation_report or {}).get("manifest_version"),
        "registry_version": (compilation_report or {}).get("registry_version"),
        "compiler_version": (compilation_report or {}).get("compiler_version"),
        "graph_model_version": GRAPH_MODEL_VERSION,
        "status": "compiled",
        "confidence": 1.0,
        "relationship_model": relationship_model,
    }
    payload = {
        "graph_model_version": GRAPH_MODEL_VERSION,
        "source_graph_hash": source_hash,
        "graph_version": graph_version,
        "immutable": True,
        "layers": list(GRAPH_LAYERS),
        "nodes": list(nodes),
        "edges": list(edges),
        "partitions": _partitions(nodes),
        "metadata": metadata,
    }
    return R16KnowledgeGraphModel(**payload, graph_hash=specification_hash(payload))


def r16_validate_graph(graph: R16KnowledgeGraphModel) -> R16GraphValidationReport:
    diagnostics: list[R16GraphDiagnostic] = []
    relationship_model = graph.metadata.get("relationship_model", RELATIONSHIP_MODEL)
    if not isinstance(relationship_model, dict):
        relationship_model = RELATIONSHIP_MODEL
    node_ids = [node["id"] for node in graph.nodes if isinstance(node.get("id"), str)]
    node_id_set = set(node_ids)
    if len(node_ids) != len(node_id_set):
        diagnostics.append(
            _diagnostic("fatal", "R16-DUPLICATE-NODE", "Duplicate node id.", "nodes")
        )
    for index, node in enumerate(graph.nodes):
        node_type = node.get("type")
        if node_type not in NODE_TAXONOMY:
            diagnostics.append(
                _diagnostic(
                    "fatal",
                    "R16-UNKNOWN-NODE-TYPE",
                    f"Unknown node type {node_type}.",
                    f"nodes/{index}/type",
                )
            )
        if not node.get("traceability", {}).get("manifest_origin"):
            diagnostics.append(
                _diagnostic(
                    "fatal",
                    "R16-MISSING-TRACEABILITY",
                    f"Node {node.get('id')} has no manifest origin.",
                    f"nodes/{index}/traceability",
                )
            )
        generated_artifacts = node.get("traceability", {}).get("generated_artifacts")
        if not isinstance(generated_artifacts, list | tuple):
            diagnostics.append(
                _diagnostic(
                    "fatal",
                    "R16-MISSING-ARTIFACT-TRACEABILITY",
                    f"Node {node.get('id')} has no generated artifact traceability hook.",
                    f"nodes/{index}/traceability/generated_artifacts",
                )
            )
    referenced_targets: set[str] = set()
    for index, edge in enumerate(graph.edges):
        relationship = edge.get("relationship_type")
        if relationship not in relationship_model:
            diagnostics.append(
                _diagnostic(
                    "fatal",
                    "R16-UNKNOWN-RELATIONSHIP",
                    f"Unknown relationship {relationship}.",
                    f"edges/{index}/relationship_type",
                )
            )
        source = edge.get("source")
        target = edge.get("target")
        if source not in node_id_set or target not in node_id_set:
            diagnostics.append(
                _diagnostic(
                    "fatal",
                    "R16-AMBIGUOUS-REFERENCE",
                    f"Edge {edge.get('id')} references an unknown node.",
                    f"edges/{index}",
                )
            )
        if isinstance(target, str):
            referenced_targets.add(target)
    orphan_ids = tuple(sorted(node_id_set - referenced_targets - _source_nodes(graph.edges)))
    if orphan_ids and len(graph.nodes) > 1:
        diagnostics.append(
            _diagnostic(
                "fatal",
                "R16-ORPHAN-NODE",
                f"Orphan nodes: {', '.join(orphan_ids)}.",
                "nodes",
            )
        )
    report_payload = {
        "valid": not any(item.severity == "fatal" for item in diagnostics),
        "diagnostics": [item.model_dump(mode="json") for item in diagnostics],
    }
    return R16GraphValidationReport(
        valid=report_payload["valid"],
        diagnostics=tuple(diagnostics),
        report_hash=specification_hash(report_payload),
    )


def r16_query_graph(
    graph: R16KnowledgeGraphModel,
    query: dict[str, Any],
) -> R16GraphQueryResult:
    node_type = query.get("node_type")
    contains = str(query.get("contains", "")).lower()
    relationship_type = query.get("relationship_type")
    affected_by = query.get("affected_by")
    nodes = tuple(
        node
        for node in graph.nodes
        if (not node_type or node.get("type") == node_type)
        and (not contains or contains in _searchable_node_text(node))
    )
    if isinstance(affected_by, str):
        impacted_ids = set(
            r16_propagate_impact(graph, start_node_id=affected_by).visited_node_ids
        )
        nodes = tuple(node for node in graph.nodes if node["id"] in impacted_ids)
    node_ids = {node["id"] for node in nodes}
    edges = tuple(
        edge
        for edge in graph.edges
        if (
            not relationship_type
            or edge.get("relationship_type") == relationship_type
        )
        and (
            not node_ids
            or edge.get("source") in node_ids
            or edge.get("target") in node_ids
        )
    )
    payload = {"query": query, "nodes": list(nodes), "edges": list(edges)}
    return R16GraphQueryResult(**payload, result_hash=specification_hash(payload))


def r16_apply_access_policy(
    graph: R16KnowledgeGraphModel,
    policy: dict[str, Any],
) -> R16KnowledgeGraphModel:
    allowed_node_types = _optional_set(policy.get("allowed_node_types"))
    denied_node_ids = _optional_set(policy.get("denied_node_ids")) or frozenset()
    allowed_relationship_types = _optional_set(policy.get("allowed_relationship_types"))
    allowed_domains = _optional_set(policy.get("allowed_domains"))
    allowed_graph_versions = _optional_set(policy.get("allowed_graph_versions"))
    include_metadata = policy.get("include_metadata", True) is True
    if allowed_graph_versions and graph.graph_version not in allowed_graph_versions:
        nodes: tuple[dict[str, Any], ...] = ()
    else:
        nodes = tuple(
            _redact_node_metadata(node) if not include_metadata else node
            for node in graph.nodes
            if node["id"] not in denied_node_ids
            and (allowed_node_types is None or node["type"] in allowed_node_types)
            and (
                allowed_domains is None
                or node.get("metadata", {}).get("domain") in allowed_domains
                or node["id"] == "semantic-root"
            )
        )
    node_ids = {node["id"] for node in nodes}
    edges = tuple(
        edge
        for edge in graph.edges
        if edge["source"] in node_ids
        and edge["target"] in node_ids
        and (
            allowed_relationship_types is None
            or edge["relationship_type"] in allowed_relationship_types
        )
    )
    metadata = dict(graph.metadata) if include_metadata else {"redacted": True}
    metadata["access_policy_hash"] = specification_hash(policy)
    payload = {
        **graph.model_dump(mode="json"),
        "nodes": list(nodes),
        "edges": list(edges),
        "partitions": _partitions(nodes),
        "metadata": metadata,
    }
    payload["graph_hash"] = specification_hash(
        {key: value for key, value in payload.items() if key != "graph_hash"}
    )
    return R16KnowledgeGraphModel.model_validate(payload)


def r16_find_graph(
    graph: R16KnowledgeGraphModel,
    *,
    node_id: str | None = None,
    node_type: str | None = None,
) -> R16GraphQueryResult:
    query = {"node_id": node_id, "node_type": node_type}
    nodes = tuple(
        node
        for node in graph.nodes
        if (node_id is None or node["id"] == node_id)
        and (node_type is None or node["type"] == node_type)
    )
    node_ids = {node["id"] for node in nodes}
    edges = tuple(
        edge
        for edge in graph.edges
        if edge.get("source") in node_ids or edge.get("target") in node_ids
    )
    payload = {"query": query, "nodes": list(nodes), "edges": list(edges)}
    return R16GraphQueryResult(**payload, result_hash=specification_hash(payload))


def r16_traverse_graph(
    graph: R16KnowledgeGraphModel,
    *,
    start_node_id: str,
    max_depth: int = 2,
) -> R16GraphTraversalResult:
    adjacency: dict[str, list[dict[str, Any]]] = {}
    for edge in graph.edges:
        adjacency.setdefault(str(edge["source"]), []).append(edge)
    visited = {start_node_id}
    traversed: list[str] = []
    queue: deque[tuple[str, int]] = deque([(start_node_id, 0)])
    while queue:
        node_id, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for edge in sorted(adjacency.get(node_id, []), key=lambda item: str(item["id"])):
            traversed.append(str(edge["id"]))
            target = str(edge["target"])
            if target not in visited:
                visited.add(target)
                queue.append((target, depth + 1))
    payload = {
        "start_node_id": start_node_id,
        "max_depth": max_depth,
        "visited_node_ids": tuple(sorted(visited)),
        "traversed_edge_ids": tuple(sorted(traversed)),
    }
    return R16GraphTraversalResult(**payload, result_hash=specification_hash(payload))


def r16_propagate_impact(
    graph: R16KnowledgeGraphModel,
    *,
    start_node_id: str,
    max_depth: int = 99,
) -> R16GraphTraversalResult:
    forward = r16_traverse_graph(graph, start_node_id=start_node_id, max_depth=max_depth)
    reverse_edges = tuple(
        {**edge, "source": edge["target"], "target": edge["source"]}
        for edge in graph.edges
    )
    reverse_graph = graph.model_copy(update={"edges": reverse_edges})
    reverse = r16_traverse_graph(
        reverse_graph,
        start_node_id=start_node_id,
        max_depth=max_depth,
    )
    payload = {
        "start_node_id": start_node_id,
        "max_depth": max_depth,
        "visited_node_ids": tuple(
            sorted(set(forward.visited_node_ids) | set(reverse.visited_node_ids))
        ),
        "traversed_edge_ids": tuple(
            sorted(set(forward.traversed_edge_ids) | set(reverse.traversed_edge_ids))
        ),
    }
    return R16GraphTraversalResult(**payload, result_hash=specification_hash(payload))


def r16_diff_graphs(
    previous: R16KnowledgeGraphModel,
    current: R16KnowledgeGraphModel,
) -> R16GraphDiffResult:
    previous_nodes = _hashed_by_id(previous.nodes)
    current_nodes = _hashed_by_id(current.nodes)
    previous_edges = _hashed_by_id(previous.edges)
    current_edges = _hashed_by_id(current.edges)
    payload = {
        "added_node_ids": tuple(sorted(set(current_nodes) - set(previous_nodes))),
        "removed_node_ids": tuple(sorted(set(previous_nodes) - set(current_nodes))),
        "changed_node_ids": tuple(
            sorted(
                key
                for key in set(previous_nodes) & set(current_nodes)
                if previous_nodes[key] != current_nodes[key]
            )
        ),
        "added_edge_ids": tuple(sorted(set(current_edges) - set(previous_edges))),
        "removed_edge_ids": tuple(sorted(set(previous_edges) - set(current_edges))),
        "changed_edge_ids": tuple(
            sorted(
                key
                for key in set(previous_edges) & set(current_edges)
                if previous_edges[key] != current_edges[key]
            )
        ),
    }
    return R16GraphDiffResult(**payload, diff_hash=specification_hash(payload))


def r16_export_graph(
    graph: R16KnowledgeGraphModel,
    *,
    export_format: str,
) -> R16GraphExportResult:
    if export_format not in EXPORT_FORMATS:
        document: dict[str, Any] | str = {
            "error": f"Unsupported export format {export_format}.",
            "supported": list(EXPORT_FORMATS),
        }
    elif export_format == "json":
        document = graph.model_dump(mode="json")
    elif export_format == "property_graph":
        document = {
            "vertices": list(graph.nodes),
            "edges": list(graph.edges),
            "metadata": graph.metadata,
        }
    elif export_format in {"rdf", "owl"}:
        document = "\n".join(
            f"<kg:{edge['source']}> <kg:{edge['relationship_type']}> <kg:{edge['target']}> ."
            for edge in graph.edges
        )
    elif export_format == "graphql":
        document = {
            "type": "KnowledgeGraph",
            "nodes": list(graph.nodes),
            "edges": list(graph.edges),
        }
    elif export_format == "neo4j":
        document = {
            "statements": [
                {
                    "source": edge["source"],
                    "relationship": edge["relationship_type"],
                    "target": edge["target"],
                }
                for edge in graph.edges
            ]
        }
    else:
        document = (
            "aie-r16-binary:"
            + base64.b64encode(
                json.dumps(graph.model_dump(mode="json"), sort_keys=True).encode()
            ).decode()
        )
    payload = {"export_format": export_format, "document": document}
    return R16GraphExportResult(
        export_format=export_format,
        document=document,
        export_hash=specification_hash(payload),
    )


def r16_graph_backend_readiness(
    settings: object,
    *,
    repo_root: Path | None = None,
) -> R16GraphBackendReadiness:
    backend = str(getattr(settings, "r16_graph_backend", "in_process"))
    partition_strategy = str(getattr(settings, "r16_graph_backend_partition_strategy", "layer"))
    checks = (
        _partition_strategy_check(partition_strategy),
        _backend_configuration_check(settings, backend, repo_root=repo_root),
    )
    return R16GraphBackendReadiness(
        backend=backend,
        ready=all(check.ready for check in checks),
        partition_strategy=partition_strategy,
        checks=checks,
    )


def r16_publish_graph_to_backend(
    graph: R16KnowledgeGraphModel,
    settings: object,
    *,
    dry_run: bool = True,
    repo_root: Path | None = None,
) -> R16GraphBackendPublication:
    readiness = r16_graph_backend_readiness(settings, repo_root=repo_root)
    backend = readiness.backend
    if not readiness.ready:
        return R16GraphBackendPublication(
            backend=backend,
            graph_version=graph.graph_version,
            graph_hash=graph.graph_hash,
            publication_ref="",
            ready=False,
            published=False,
            dry_run=dry_run,
            detail="R16 graph backend is not ready; inspect readiness checks.",
        )
    if backend in {"in_process", "filesystem"}:
        root = _filesystem_backend_root(settings, repo_root=repo_root)
        graph_root = root / graph.graph_version
        graph_ref = graph_root / "graph.json"
        if not dry_run:
            graph_root.mkdir(parents=True, exist_ok=True)
            graph_ref.write_text(
                json.dumps(graph.model_dump(mode="json"), sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
        return R16GraphBackendPublication(
            backend=backend,
            graph_version=graph.graph_version,
            graph_hash=graph.graph_hash,
            publication_ref=f"file://{graph_ref}",
            ready=True,
            published=not dry_run,
            dry_run=dry_run,
            detail=(
                "Graph backend publication is materialized on filesystem."
                if not dry_run
                else "Graph backend filesystem publication validated in dry-run mode."
            ),
        )
    endpoint = str(getattr(settings, "r16_graph_backend_endpoint", "") or "")
    database = str(getattr(settings, "r16_graph_backend_database", "") or "")
    command = _external_backend_command(backend, endpoint, database, graph.graph_version)
    return R16GraphBackendPublication(
        backend=backend,
        graph_version=graph.graph_version,
        graph_hash=graph.graph_hash,
        publication_ref=f"{backend}://{database or endpoint}/{graph.graph_version}",
        ready=True,
        published=False,
        dry_run=True,
        command=command,
        detail=(
            "External graph backend configuration is ready. Publication remains dry-run "
            "until production credentials and backend client execution are enabled."
        ),
    )


def _canonical_node(
    node: dict[str, Any],
    compilation_report: dict[str, Any] | None,
) -> dict[str, Any]:
    node_type = str(node.get("type", "unknown"))
    metadata = dict(node.get("metadata", {}))
    return {
        "id": str(node.get("id")),
        "stable_identifier": f"KG-{node_type.upper().replace('_', '-')}-{node.get('id')}",
        "type": node_type,
        "layer": NODE_TAXONOMY.get(node_type, "unknown"),
        "name": metadata.get("manifest", {}).get("name", node.get("id")),
        "description": (
            metadata.get("manifest", {}).get("description")
            or metadata.get("manifest", {}).get("meaning")
            or metadata.get("manifest", {}).get("purpose")
            or metadata.get("manifest", {}).get("requirement")
            or ""
        ),
        "registry_reference": node.get("registry_reference"),
        "relationships": tuple(node.get("relationships", ())),
        "metadata": {
            **metadata,
            "manifest_version": (compilation_report or {}).get("manifest_version"),
            "registry_version": (compilation_report or {}).get("registry_version"),
            "compiler_version": (compilation_report or {}).get("compiler_version"),
            "graph_model_version": GRAPH_MODEL_VERSION,
            "status": node.get("status", "resolved"),
            "confidence": 1.0,
            "domain": metadata.get("manifest", {}).get("domain"),
        },
        "traceability": {
            "manifest_origin": node.get("manifest_origin"),
            "registry_reference": node.get("registry_reference"),
            "compiler_pass": "r15_manifest_compiler",
            "execution_node": None,
            "generated_artifacts": [],
        },
        "version": node.get("version"),
        "status": node.get("status", "resolved"),
    }


def _partition_strategy_check(partition_strategy: str) -> R16GraphBackendCheck:
    if partition_strategy in {"layer", "domain", "node_type"}:
        return R16GraphBackendCheck(
            name="partition_strategy",
            configured=True,
            ready=True,
            detail=f"Partition strategy {partition_strategy} is supported.",
        )
    return R16GraphBackendCheck(
        name="partition_strategy",
        configured=False,
        ready=False,
        detail=f"Unsupported partition strategy {partition_strategy}.",
        required=("layer", "domain", "node_type"),
    )


def _backend_configuration_check(
    settings: object,
    backend: str,
    *,
    repo_root: Path | None,
) -> R16GraphBackendCheck:
    if backend == "in_process":
        return R16GraphBackendCheck(
            name="graph_backend",
            configured=True,
            ready=True,
            detail="In-process R16 graph backend is ready for deterministic local operation.",
        )
    if backend == "filesystem":
        root = _filesystem_backend_root(settings, repo_root=repo_root)
        return R16GraphBackendCheck(
            name="graph_backend",
            configured=True,
            ready=True,
            detail=f"Filesystem graph backend root is configured at {root}.",
        )
    endpoint = getattr(settings, "r16_graph_backend_endpoint", None)
    database = getattr(settings, "r16_graph_backend_database", None)
    credentials_ref = getattr(settings, "r16_graph_backend_credentials_ref", None)
    app_env = str(getattr(settings, "app_env", "development")).lower()
    missing = [
        name
        for name, value in (
            ("r16_graph_backend_endpoint", endpoint),
            ("r16_graph_backend_database", database),
            ("r16_graph_backend_credentials_ref", credentials_ref),
        )
        if not value
    ]
    if app_env == "production":
        missing.extend(
            name
            for name, value in (
                (
                    "r16_graph_backend_deployment_evidence_ref",
                    getattr(settings, "r16_graph_backend_deployment_evidence_ref", None),
                ),
                (
                    "r16_graph_backend_connectivity_evidence_ref",
                    getattr(settings, "r16_graph_backend_connectivity_evidence_ref", None),
                ),
                (
                    "r16_graph_backend_restore_evidence_ref",
                    getattr(settings, "r16_graph_backend_restore_evidence_ref", None),
                ),
                (
                    "r16_graph_backend_owner_approval_ref",
                    getattr(settings, "r16_graph_backend_owner_approval_ref", None),
                ),
            )
            if not value
        )
    if backend not in {"neo4j", "rdf", "custom"}:
        missing.append("supported backend: in_process, filesystem, neo4j, rdf, custom")
    return R16GraphBackendCheck(
        name="graph_backend",
        configured=not missing,
        ready=not missing,
        detail=(
            f"External {backend} graph backend is configured."
            if not missing
            else f"External {backend} graph backend missing: {', '.join(missing)}."
        ),
        required=tuple(missing),
    )


def _filesystem_backend_root(
    settings: object,
    *,
    repo_root: Path | None,
) -> Path:
    configured = Path(
        getattr(settings, "r16_graph_filesystem_root", "./runtime-data/r16-knowledge-graphs")
    )
    if configured.is_absolute() or repo_root is None:
        return configured
    return repo_root / configured


def _external_backend_command(
    backend: str,
    endpoint: str,
    database: str,
    graph_version: str,
) -> tuple[str, ...]:
    if backend == "neo4j":
        return ("cypher-shell", "-a", endpoint, "-d", database, ":source", graph_version)
    if backend == "rdf":
        return ("rdf-loader", "--endpoint", endpoint, "--repository", database, graph_version)
    return ("graph-backend-publish", "--endpoint", endpoint, "--database", database, graph_version)


def _root_node(
    source_hash: str,
    compilation_report: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "id": "semantic-root",
        "stable_identifier": f"KG-DOMAIN-{source_hash[:12]}",
        "type": "domain",
        "layer": NODE_TAXONOMY["domain"],
        "name": "Compiled Enterprise Semantic Model",
        "description": "Root node for the immutable compiled Knowledge Graph version.",
        "registry_reference": f"compiled-knowledge-graph:{source_hash}",
        "relationships": (),
        "metadata": {
            "manifest_version": (compilation_report or {}).get("manifest_version"),
            "registry_version": (compilation_report or {}).get("registry_version"),
            "compiler_version": (compilation_report or {}).get("compiler_version"),
            "graph_model_version": GRAPH_MODEL_VERSION,
            "status": "compiled",
            "confidence": 1.0,
            "domain": "compiled-enterprise",
        },
        "traceability": {
            "manifest_origin": "compiled-knowledge-graph",
            "registry_reference": f"compiled-knowledge-graph:{source_hash}",
            "compiler_pass": "r16_knowledge_graph_loader",
            "execution_node": None,
            "generated_artifacts": [],
        },
        "version": (compilation_report or {}).get("manifest_version"),
        "status": "resolved",
    }


def _root_edges(
    root_node_id: str,
    nodes: tuple[dict[str, Any], ...],
    relationship_model: dict[str, str],
) -> tuple[dict[str, Any], ...]:
    return tuple(
        _canonical_edge(
            {
                "source": root_node_id,
                "target": node["id"],
                "relationship_type": "has",
                "constraint": "r16.semantic_root",
                "trace_identifier": specification_hash(
                    {"source": root_node_id, "target": node["id"], "relationship_type": "has"}
                ),
            },
            relationship_model,
        )
        for node in nodes
    )


def _governance_edges(
    nodes: tuple[dict[str, Any], ...],
    relationship_model: dict[str, str],
) -> tuple[dict[str, Any], ...]:
    governance_nodes = tuple(
        node for node in nodes if node["type"] in {"constraint", "policy", "security"}
    )
    governed_nodes = tuple(
        node
        for node in nodes
        if node["type"] in {"entity", "capability", "workflow", "report", "integration"}
    )
    edges: list[dict[str, Any]] = []
    for governance_node in governance_nodes:
        relationship = "secures" if governance_node["type"] == "security" else "constrains"
        for governed_node in governed_nodes:
            edges.append(
                _canonical_edge(
                    {
                        "source": governance_node["id"],
                        "target": governed_node["id"],
                        "relationship_type": relationship,
                        "constraint": "r16.governance_propagation",
                        "trace_identifier": specification_hash(
                            {
                                "source": governance_node["id"],
                                "target": governed_node["id"],
                                "relationship_type": relationship,
                            }
                        ),
                    },
                    relationship_model,
                )
            )
    return tuple(edges)


def _canonical_edge(
    edge: dict[str, Any],
    relationship_model: dict[str, str],
) -> dict[str, Any]:
    relationship = str(edge.get("relationship_type", "")).lower()
    if relationship == "requires":
        relationship = "depends_on"
    payload = {
        "source": edge.get("source"),
        "target": edge.get("target"),
        "relationship_type": relationship,
        "constraint": edge.get("constraint"),
        "trace_identifier": edge.get("trace_identifier"),
    }
    return {
        "id": str(edge.get("trace_identifier", specification_hash(payload))),
        **payload,
        "semantics": relationship_model.get(relationship, "undefined"),
    }


def _items(payload: dict[str, Any], key: str) -> tuple[dict[str, Any], ...]:
    value = payload.get(key, ())
    if not isinstance(value, list | tuple):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def _graph_version(compilation_report: dict[str, Any] | None, source_hash: str) -> str:
    version = (compilation_report or {}).get("manifest_version")
    return f"kg-{version or source_hash[:12]}"


def _relationship_model(registry_root: Path | None) -> dict[str, str]:
    model = dict(RELATIONSHIP_MODEL)
    if registry_root is None:
        return model
    relationship_root = registry_root / "Relationships"
    for candidate in sorted(relationship_root.glob("*.json")):
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        identifier = payload.get("id")
        semantics = payload.get("semantics")
        if isinstance(identifier, str) and isinstance(semantics, str):
            model[identifier.lower()] = semantics
    return model


def _partitions(nodes: tuple[dict[str, Any], ...]) -> dict[str, tuple[str, ...]]:
    partitions: dict[str, list[str]] = {}
    for node in nodes:
        partitions.setdefault(str(node.get("layer")), []).append(str(node["id"]))
    return {key: tuple(sorted(value)) for key, value in sorted(partitions.items())}


def _optional_set(value: object) -> frozenset[str] | None:
    if value is None:
        return None
    if not isinstance(value, list | tuple | set):
        return frozenset()
    return frozenset(str(item) for item in value)


def _redact_node_metadata(node: dict[str, Any]) -> dict[str, Any]:
    return {**node, "metadata": {"redacted": True}}


def _diagnostic(
    severity: str,
    code: str,
    message: str,
    path: str,
) -> R16GraphDiagnostic:
    return R16GraphDiagnostic(severity=severity, code=code, message=message, path=path)


def _source_nodes(edges: tuple[dict[str, Any], ...]) -> set[str]:
    return {str(edge["source"]) for edge in edges if isinstance(edge.get("source"), str)}


def _searchable_node_text(node: dict[str, Any]) -> str:
    return " ".join(
        str(value).lower()
        for value in (node.get("id"), node.get("name"), node.get("description"), node.get("type"))
    )


def _hashed_by_id(items: tuple[dict[str, Any], ...]) -> dict[str, str]:
    return {
        str(item["id"]): specification_hash(item)
        for item in items
        if isinstance(item.get("id"), str)
    }
