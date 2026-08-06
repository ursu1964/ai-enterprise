from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from ai_enterprise.application.r15_manifest_compiler_runtime import (
    COMPILATION_PASSES,
    COMPILATION_STAGES,
    COMPILER_VERSION,
    r15_compile_manifest,
    r15_persist_compilation_history,
    r15_read_compilation_history,
)
from ai_enterprise.main import app

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "schemas" / "Manifest.schema.json"
REGISTRY = ROOT / "registry"
VALID_MANIFEST = ROOT / "manifest" / "crm.r14.json"
INVALID_TECHNICAL_MANIFEST = ROOT / "manifest" / "invalid-technical.r14.json"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _actor_headers() -> dict[str, str]:
    return {
        "X-Actor-ID": "local-dashboard-admin",
        "X-Actor-Type": "human",
        "X-Actor-Role": "platform-admin",
    }


def test_r15_compiler_produces_deterministic_knowledge_and_execution_graphs() -> None:
    manifest = _load_json(VALID_MANIFEST)

    first = r15_compile_manifest(manifest, SCHEMA, REGISTRY)
    second = r15_compile_manifest(manifest, SCHEMA, REGISTRY)

    assert first.success_status is True
    assert second.success_status is True
    assert first.result_hash == second.result_hash
    assert first.diagnostics == ()
    assert first.knowledge_graph is not None
    assert first.dependency_graph is not None
    assert first.execution_graph is not None
    assert first.pass_reports

    node_types = {node.type for node in first.knowledge_graph.nodes}
    assert {
        "objective",
        "role",
        "entity",
        "capability",
        "workflow",
        "business_rule",
        "policy",
        "integration",
        "report",
        "security",
        "quality",
        "constraint",
    } <= node_types
    assert all(
        node.registry_reference.startswith("registry/")
        and node.manifest_origin
        and node.status == "resolved"
        for node in first.knowledge_graph.nodes
    )

    edge_types = {edge.relationship_type for edge in first.knowledge_graph.edges}
    assert {
        "uses",
        "references",
        "owns",
        "consumes",
        "triggers",
        "produces",
        "implements",
    } <= edge_types

    dependency_graph = first.dependency_graph
    assert dependency_graph.directed is True
    assert dependency_graph.acyclic is True
    assert {node.id for node in dependency_graph.nodes} >= {
        "customer",
        "lead",
        "opportunity",
    }

    execution_graph = first.execution_graph
    assert execution_graph.directed is True
    assert execution_graph.acyclic is True
    assert execution_graph.incrementally_updateable is True
    assert [node.id for node in execution_graph.nodes] == [
        "create-business-entities",
        "generate-database",
        "generate-apis",
        "generate-backend",
        "generate-ui",
        "generate-tests",
        "generate-documentation",
        "package-system",
    ]
    assert all(node.status == "pending" for node in execution_graph.nodes)

    report = first.compilation_report
    assert report.compiler_version == COMPILER_VERSION
    assert report.compilation_timestamp == "1970-01-01T00:00:00Z"
    assert report.stages == COMPILATION_STAGES
    assert report.passes == COMPILATION_PASSES
    assert report.expanded_object_count == len(first.knowledge_graph.nodes)
    assert report.resolved_dependency_count == len(first.dependency_graph.edges)


def test_r15_compiler_rejects_invalid_manifest_without_graphs() -> None:
    result = r15_compile_manifest(_load_json(INVALID_TECHNICAL_MANIFEST), SCHEMA, REGISTRY)

    assert result.success_status is False
    assert result.knowledge_graph is None
    assert result.dependency_graph is None
    assert result.execution_graph is None
    codes = {item.code for item in result.diagnostics}
    assert "R14-SCHEMA" in codes
    assert "R14-INTENT-ONLY" in codes


def test_r15_compiler_blocks_graphs_when_registry_definition_is_missing() -> None:
    manifest = _load_json(VALID_MANIFEST)
    manifest["capabilities"][0]["id"] = "missing-capability-definition"  # type: ignore[index]

    result = r15_compile_manifest(manifest, SCHEMA, REGISTRY)

    assert result.success_status is False
    assert result.knowledge_graph is None
    assert result.dependency_graph is None
    assert result.execution_graph is None
    codes = {item.code for item in result.diagnostics}
    assert "R14-REGISTRY-REFERENCE" in codes


def test_r15_compiler_rejects_duplicate_semantic_ids_before_graph_execution() -> None:
    manifest = _load_json(VALID_MANIFEST)
    manifest["businessEntities"][1]["id"] = "customer"  # type: ignore[index]

    result = r15_compile_manifest(manifest, SCHEMA, REGISTRY)

    assert result.success_status is False
    assert result.knowledge_graph is None
    assert result.execution_graph is None
    assert result.dependency_graph is None
    codes = {item.code for item in result.diagnostics}
    assert "R15-DUPLICATE-ID" in codes


def test_r15_compiler_rejects_circular_manifest_dependencies() -> None:
    manifest = _load_json(VALID_MANIFEST)
    manifest["businessEntities"][0]["dependsOn"] = ["lead"]  # type: ignore[index]
    manifest["businessEntities"][1]["dependsOn"] = ["customer"]  # type: ignore[index]

    result = r15_compile_manifest(manifest, SCHEMA, REGISTRY)

    assert result.success_status is False
    assert result.knowledge_graph is None
    assert result.execution_graph is None
    assert result.dependency_graph is None
    codes = {item.code for item in result.diagnostics}
    assert "R15-CIRCULAR-DEPENDENCY" in codes


def test_r15_incremental_compilation_marks_reusable_and_changed_nodes() -> None:
    manifest = _load_json(VALID_MANIFEST)
    first = r15_compile_manifest(manifest, SCHEMA, REGISTRY)
    second = r15_compile_manifest(
        manifest,
        SCHEMA,
        REGISTRY,
        compiler_options={"previous_result": first.model_dump(mode="json")},
    )

    assert second.incremental_impact.previous_result_hash == first.result_hash
    assert second.incremental_impact.changed_node_ids == ()
    assert "customer" in second.incremental_impact.reusable_node_ids

    changed_manifest = _load_json(VALID_MANIFEST)
    changed_manifest["businessEntities"][0]["meaning"] = "A buyer account."  # type: ignore[index]
    third = r15_compile_manifest(
        changed_manifest,
        SCHEMA,
        REGISTRY,
        compiler_options={"previous_result": first.model_dump(mode="json")},
    )

    assert "customer" in third.incremental_impact.changed_node_ids
    assert third.incremental_impact.affected_execution_step_ids


def test_r15_compilation_history_is_append_only_and_hash_bound(tmp_path: Path) -> None:
    result = r15_compile_manifest(_load_json(VALID_MANIFEST), SCHEMA, REGISTRY)
    history_path = tmp_path / "history.jsonl"

    record_hash = r15_persist_compilation_history(
        result,
        history_path,
        actor_id="operator",
    )
    records = r15_read_compilation_history(history_path)

    assert len(records) == 1
    assert records[0]["record_hash"] == record_hash
    assert records[0]["result_hash"] == result.result_hash
    assert records[0]["dependency_graph_hash"] == result.dependency_graph.graph_hash


def test_r15_compile_api_is_exposed_and_returns_compilation_result() -> None:
    client = TestClient(app)

    openapi = client.get("/openapi.json").json()
    assert "/api/v1/r15/compiler-contract" in openapi["paths"]
    assert "/api/v1/r15/compile" in openapi["paths"]

    response = client.post(
        "/api/v1/r15/compile",
        headers=_actor_headers(),
        json={"manifest": _load_json(VALID_MANIFEST)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success_status"] is True
    assert payload["knowledge_graph"]["nodes"]
    assert payload["dependency_graph"]["nodes"]
    assert payload["execution_graph"]["nodes"]
    assert payload["incremental_impact"]["changed_node_ids"]
    assert payload["pass_reports"]
    assert payload["compilation_report"]["compiler_version"] == COMPILER_VERSION
