from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from ai_enterprise.application.r15_manifest_compiler_runtime import r15_compile_manifest
from ai_enterprise.application.r16_knowledge_graph_runtime import (
    GRAPH_LAYERS,
    GRAPH_MODEL_VERSION,
    NODE_TAXONOMY,
    RELATIONSHIP_MODEL,
    R16KnowledgeGraphModel,
    r16_apply_access_policy,
    r16_diff_graphs,
    r16_export_graph,
    r16_find_graph,
    r16_graph_backend_readiness,
    r16_load_graph,
    r16_ontology_contract,
    r16_propagate_impact,
    r16_publish_graph_to_backend,
    r16_query_graph,
    r16_traverse_graph,
    r16_validate_graph,
)
from ai_enterprise.main import app

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "schemas" / "Manifest.schema.json"
REGISTRY = ROOT / "registry"
VALID_MANIFEST = ROOT / "manifest" / "crm.r14.json"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _actor_headers() -> dict[str, str]:
    return {
        "X-Actor-ID": "local-dashboard-admin",
        "X-Actor-Type": "human",
        "X-Actor-Role": "platform-admin",
    }


def _r16_graph() -> R16KnowledgeGraphModel:
    result = r15_compile_manifest(_load_json(VALID_MANIFEST), SCHEMA, REGISTRY)
    assert result.success_status is True
    assert result.knowledge_graph is not None
    return r16_load_graph(
        result.knowledge_graph.model_dump(mode="json"),
        compilation_report=result.compilation_report.model_dump(mode="json"),
        registry_root=REGISTRY,
    )


def test_r16_ontology_contract_formalizes_layers_taxonomy_and_relationships() -> None:
    contract = r16_ontology_contract(REGISTRY)

    assert contract.graph_model_version == GRAPH_MODEL_VERSION
    assert contract.layers == GRAPH_LAYERS
    assert "entity" in contract.node_taxonomy
    assert "workflow" in contract.node_taxonomy
    assert "depends_on" in contract.relationship_model
    assert contract.relationship_model["constrains"].startswith("Source imposes")
    assert "property_graph" in contract.export_formats
    assert "custom_binary" in contract.export_formats
    assert contract.contract_hash


def test_r16_loads_r15_graph_into_immutable_semantic_model() -> None:
    graph = _r16_graph()

    assert graph.graph_model_version == GRAPH_MODEL_VERSION
    assert graph.immutable is True
    assert graph.layers == GRAPH_LAYERS
    assert graph.nodes
    assert graph.edges
    assert graph.partitions["business_structure"]
    assert graph.metadata["relationship_model"]["secures"].startswith("Source applies")
    assert all(node["type"] in NODE_TAXONOMY for node in graph.nodes)
    assert all(edge["relationship_type"] in RELATIONSHIP_MODEL for edge in graph.edges)
    assert all(node["traceability"]["manifest_origin"] for node in graph.nodes)
    assert all(
        isinstance(node["traceability"]["generated_artifacts"], list)
        for node in graph.nodes
    )
    assert graph.graph_hash


def test_r16_validation_rejects_unknown_types_relationships_and_missing_traceability() -> None:
    graph = _r16_graph()
    valid = r16_validate_graph(graph)
    assert valid.valid is True

    payload = graph.model_dump(mode="json")
    payload["nodes"][0]["type"] = "unknown"
    payload["edges"][0]["relationship_type"] = "undefined"
    payload["nodes"][1]["traceability"]["manifest_origin"] = ""
    del payload["nodes"][2]["traceability"]["generated_artifacts"]
    invalid = r16_validate_graph(R16KnowledgeGraphModel.model_validate(payload))

    assert invalid.valid is False
    codes = {item.code for item in invalid.diagnostics}
    assert "R16-UNKNOWN-NODE-TYPE" in codes
    assert "R16-UNKNOWN-RELATIONSHIP" in codes
    assert "R16-MISSING-TRACEABILITY" in codes
    assert "R16-MISSING-ARTIFACT-TRACEABILITY" in codes


def test_r16_query_find_traverse_and_export_are_deterministic() -> None:
    graph = _r16_graph()

    query = r16_query_graph(graph, {"node_type": "entity", "contains": "customer"})
    assert "customer" in [node["id"] for node in query.nodes]

    found = r16_find_graph(graph, node_id="qualify-lead")
    assert found.nodes[0]["type"] == "workflow"
    assert found.edges

    traversal = r16_traverse_graph(graph, start_node_id="qualify-lead", max_depth=2)
    assert "qualify-lead" in traversal.visited_node_ids
    assert traversal.traversed_edge_ids

    exported = r16_export_graph(graph, export_format="property_graph")
    assert exported.export_format == "property_graph"
    assert exported.document["vertices"]
    assert exported.export_hash

    custom_binary = r16_export_graph(graph, export_format="custom_binary")
    assert isinstance(custom_binary.document, str)
    assert custom_binary.document.startswith("aie-r16-binary:")


def test_r16_access_filter_and_policy_impact_propagation_are_deterministic() -> None:
    graph = _r16_graph()

    filtered = r16_apply_access_policy(
        graph,
        {
            "allowed_node_types": ["domain", "entity"],
            "allowed_relationship_types": ["has"],
            "include_metadata": False,
        },
    )
    assert {node["type"] for node in filtered.nodes} <= {"domain", "entity"}
    assert all(edge["relationship_type"] == "has" for edge in filtered.edges)
    assert all(node["metadata"] == {"redacted": True} for node in filtered.nodes)

    impact = r16_propagate_impact(graph, start_node_id="eu-data")
    assert "pipeline-dashboard" in impact.visited_node_ids
    assert "customer" in impact.visited_node_ids

    affected_reports = r16_query_graph(
        graph,
        {"node_type": "report", "affected_by": "eu-data"},
    )
    assert "pipeline-dashboard" in [node["id"] for node in affected_reports.nodes]


def test_r16_graph_backend_readiness_and_filesystem_publication(tmp_path: Path) -> None:
    graph = _r16_graph()
    settings = SimpleNamespace(
        r16_graph_backend="filesystem",
        r16_graph_filesystem_root=tmp_path / "graphs",
        r16_graph_backend_partition_strategy="layer",
    )

    readiness = r16_graph_backend_readiness(settings, repo_root=tmp_path)
    publication = r16_publish_graph_to_backend(
        graph,
        settings,
        dry_run=False,
        repo_root=tmp_path,
    )

    assert readiness.ready is True
    assert publication.ready is True
    assert publication.published is True
    assert publication.publication_ref.startswith("file://")
    assert (tmp_path / "graphs" / graph.graph_version / "graph.json").exists()


def test_r16_external_graph_backend_requires_real_configuration(tmp_path: Path) -> None:
    graph = _r16_graph()
    missing = SimpleNamespace(
        r16_graph_backend="neo4j",
        r16_graph_backend_partition_strategy="layer",
    )
    configured = SimpleNamespace(
        app_env="development",
        r16_graph_backend="neo4j",
        r16_graph_backend_endpoint="bolt://neo4j.example.test:7687",
        r16_graph_backend_database="ai_enterprise",
        r16_graph_backend_credentials_ref="secret://neo4j/r16",
        r16_graph_backend_partition_strategy="layer",
    )

    blocked = r16_graph_backend_readiness(missing, repo_root=tmp_path)
    ready = r16_graph_backend_readiness(configured, repo_root=tmp_path)
    publication = r16_publish_graph_to_backend(
        graph,
        configured,
        dry_run=True,
        repo_root=tmp_path,
    )

    assert blocked.ready is False
    assert "r16_graph_backend_endpoint" in blocked.checks[1].required
    assert ready.ready is True
    assert publication.ready is True
    assert publication.published is False
    assert publication.dry_run is True
    assert publication.command[0] == "cypher-shell"


def test_r16_production_external_backend_requires_operational_evidence_refs(
    tmp_path: Path,
) -> None:
    missing_evidence = SimpleNamespace(
        app_env="production",
        r16_graph_backend="neo4j",
        r16_graph_backend_endpoint="bolt://neo4j.example.test:7687",
        r16_graph_backend_database="ai_enterprise",
        r16_graph_backend_credentials_ref="secret://neo4j/r16",
        r16_graph_backend_partition_strategy="layer",
    )
    ready = SimpleNamespace(
        app_env="production",
        r16_graph_backend="neo4j",
        r16_graph_backend_endpoint="bolt://neo4j.example.test:7687",
        r16_graph_backend_database="ai_enterprise",
        r16_graph_backend_credentials_ref="secret://neo4j/r16",
        r16_graph_backend_deployment_evidence_ref="ticket://graph-deploy",
        r16_graph_backend_connectivity_evidence_ref="artifact://graph-connectivity",
        r16_graph_backend_restore_evidence_ref="artifact://graph-restore",
        r16_graph_backend_owner_approval_ref="approval://graph-owner",
        r16_graph_backend_partition_strategy="layer",
    )

    blocked = r16_graph_backend_readiness(missing_evidence, repo_root=tmp_path)
    allowed = r16_graph_backend_readiness(ready, repo_root=tmp_path)

    assert blocked.ready is False
    assert "r16_graph_backend_deployment_evidence_ref" in blocked.checks[1].required
    assert "r16_graph_backend_owner_approval_ref" in blocked.checks[1].required
    assert allowed.ready is True


def test_r16_graph_diff_detects_semantic_node_changes() -> None:
    previous = _r16_graph()
    changed_manifest = _load_json(VALID_MANIFEST)
    changed_manifest["businessEntities"][0]["meaning"] = "A buyer account."  # type: ignore[index]
    result = r15_compile_manifest(changed_manifest, SCHEMA, REGISTRY)
    assert result.success_status is True
    assert result.knowledge_graph is not None
    current = r16_load_graph(
        result.knowledge_graph.model_dump(mode="json"),
        compilation_report=result.compilation_report.model_dump(mode="json"),
    )

    diff = r16_diff_graphs(previous, current)

    assert "customer" in diff.changed_node_ids
    assert diff.diff_hash


def test_r16_api_is_exposed_for_graph_operations() -> None:
    graph = _r16_graph()
    client = TestClient(app)

    openapi = client.get("/openapi.json").json()
    assert "/api/v1/r16/ontology-contract" in openapi["paths"]
    assert "/api/v1/r16/graph/backend-readiness" in openapi["paths"]
    assert "/api/v1/r16/graph/query" in openapi["paths"]
    assert "/api/v1/r16/graph/export" in openapi["paths"]
    assert "/api/v1/r16/graph/publish" in openapi["paths"]

    response = client.post(
        "/api/v1/r16/graph/validate",
        headers=_actor_headers(),
        json={"graph": graph.model_dump(mode="json")},
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True
