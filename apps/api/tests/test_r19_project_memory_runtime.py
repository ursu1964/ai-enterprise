from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from ai_enterprise.application.r15_manifest_compiler_runtime import r15_compile_manifest
from ai_enterprise.application.r16_knowledge_graph_runtime import r16_load_graph
from ai_enterprise.application.r17_execution_planner_runtime import r17_create_execution_plan
from ai_enterprise.application.r18_generator_orchestration_runtime import r18_orchestrate_execution
from ai_enterprise.application.r19_project_memory_runtime import (
    MEMORY_DOMAINS,
    MEMORY_ENGINE_VERSION,
    r19_authorize_memory_action,
    r19_context,
    r19_empty_store,
    r19_export_memory,
    r19_history,
    r19_ingest_r17_execution_plan,
    r19_ingest_r18_execution_result,
    r19_memory_readiness,
    r19_production_validate_store,
    r19_query_memory,
    r19_read_store,
    r19_relate_memory,
    r19_semantic_index_report,
    r19_store_memory,
    r19_update_memory,
    r19_validate_store,
    r19_write_store,
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


def _graph() -> dict[str, object]:
    compiled = r15_compile_manifest(_load_json(VALID_MANIFEST), SCHEMA, REGISTRY)
    assert compiled.success_status is True
    assert compiled.knowledge_graph is not None
    graph = r16_load_graph(
        compiled.knowledge_graph.model_dump(mode="json"),
        compilation_report=compiled.compilation_report.model_dump(mode="json"),
        registry_root=REGISTRY,
    )
    return graph.model_dump(mode="json")


def _plan_and_result() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    graph = _graph()
    plan = r17_create_execution_plan(graph)
    result = r18_orchestrate_execution(
        plan,
        graph,
        orchestration_options={
            "approvals": {gate.approval_id: True for gate in plan.approval_gates}
        },
    )
    assert result.status == "completed"
    return graph, plan.model_dump(mode="json"), result.model_dump(mode="json")


def test_r19_empty_store_has_canonical_domains_and_hash() -> None:
    store = r19_empty_store()

    assert store.engine_version == MEMORY_ENGINE_VERSION
    assert set(MEMORY_DOMAINS) >= {"project", "architecture", "execution", "artifacts"}
    assert store.records == ()
    assert store.store_hash
    assert r19_validate_store(store).valid is True


def test_r19_store_query_and_security_visibility_are_deterministic() -> None:
    store = r19_store_memory(
        None,
        project_id="crm",
        domain="architecture",
        category="adr",
        author="architect",
        source="human-review",
        summary="Use event sourcing for auditability.",
        content={"decision": "event sourcing", "reason": "auditability"},
        tags=["audit", "architecture"],
    )
    store = r19_store_memory(
        store,
        project_id="crm",
        domain="business",
        category="retention-policy",
        author="legal",
        source="business-review",
        summary="Customer records are retained for ten years.",
        content={"policy": "retention", "years": 10},
        tags=["retention"],
        retention_class="confidential",
        visibility="confidential",
    )

    public_result = r19_query_memory(store, {"project_id": "crm", "text": "audit"})
    confidential_result = r19_query_memory(
        store,
        {"project_id": "crm", "text": "retained", "include_confidential": True},
    )

    assert len(public_result.records) == 1
    assert public_result.records[0].summary == "Use event sourcing for auditability."
    assert len(confidential_result.records) == 1
    assert confidential_result.records[0].retention_class == "confidential"
    assert (
        public_result.query_hash
        == r19_query_memory(store, {"project_id": "crm", "text": "audit"}).query_hash
    )


def test_r19_update_creates_immutable_version_history() -> None:
    store = r19_store_memory(
        None,
        project_id="crm",
        domain="business",
        category="business-decision",
        author="owner",
        source="manifest-change",
        summary="Retention is five years.",
        content={"years": 5},
        tags=["retention"],
    )
    first = store.records[0]

    updated = r19_update_memory(
        store,
        memory_id=first.memory_id,
        author="owner",
        summary="Retention is ten years.",
        content={"years": 10, "reason": "regulatory change"},
    )
    history = r19_history(updated, first.memory_id)

    assert len(history) == 2
    assert history[0].summary == "Retention is five years."
    assert history[1].summary == "Retention is ten years."
    assert history[1].supersedes == first.memory_id
    assert len(updated.relationships) == 1
    assert r19_validate_store(updated).valid is True


def test_r19_relate_memory_and_context_assembly_select_relevant_memory() -> None:
    graph, plan, _ = _plan_and_result()
    task = next(item for item in plan["tasks"] if item["knowledge_node_id"] == "customer")
    store = r19_store_memory(
        None,
        project_id="crm",
        domain="architecture",
        category="adr",
        author="architect",
        source="architecture-review",
        summary="Customer API exists to support account service workflows.",
        related_objects=[
            {
                "object_type": "knowledge_node",
                "object_id": "customer",
                "relation": "explains",
            }
        ],
        content={"decision": "create customer api"},
        tags=["customer", "api"],
    )
    record = store.records[0]
    store = r19_relate_memory(
        store,
        source_memory_id=record.memory_id,
        target_type="execution_task",
        target_id=task["task_id"],
        relationship_type="informs",
        evidence={"reason": "task creates customer artifacts"},
    )

    context = r19_context(
        store,
        {
            "execution_task": task,
            "knowledge_graph": graph,
            "project_id": "crm",
            "max_records": 5,
        },
    )

    assert context.task_id == task["task_id"]
    assert context.selected_memory_ids == (record.memory_id,)
    assert context.knowledge_references
    assert context.context_hash


def test_r19_ingests_r17_plan_and_r18_result_as_memory() -> None:
    graph, plan, result = _plan_and_result()
    store = r19_ingest_r17_execution_plan(
        None,
        plan,
        project_id="crm",
        author="planner",
    )
    store = r19_ingest_r18_execution_result(
        store,
        result,
        project_id="crm",
        author="orchestrator",
    )

    execution_records = r19_query_memory(store, {"project_id": "crm", "domains": ["execution"]})
    artifact_records = r19_query_memory(store, {"project_id": "crm", "domains": ["artifacts"]})

    assert len(execution_records.records) >= 2
    assert artifact_records.records
    assert any(item.category == "ai-decision" for item in store.records)
    assert r19_context(
        store,
        {
            "execution_task": plan["tasks"][0],
            "knowledge_graph": graph,
            "project_id": "crm",
        },
    ).selected_memory_ids


def test_r19_store_export_and_filesystem_roundtrip(tmp_path: Path) -> None:
    store = r19_store_memory(
        None,
        project_id="crm",
        domain="operations",
        category="release",
        author="release-manager",
        source="deployment",
        summary="Release 1.0 affected billing.",
        content={"release": "1.0", "affected": ["billing"]},
        tags=["release", "billing"],
    )
    path = tmp_path / "r19" / "memory.json"

    written_hash = r19_write_store(store, path)
    loaded = r19_read_store(path)
    exported = r19_export_memory(loaded)

    assert written_hash == store.store_hash
    assert loaded.store_hash == store.store_hash
    assert exported.store_hash == store.store_hash
    assert exported.export_hash


def test_r19_memory_backend_readiness_fails_closed_for_unconfigured_vector_backend() -> None:
    readiness = r19_memory_readiness(
        {
            "memory_backend": "vector",
            "semantic_index_backend": "pgvector",
            "encryption_required": True,
        }
    )

    assert readiness.ready is False
    codes = {item["code"] for item in readiness.diagnostics}
    assert "R19-BACKEND-ENDPOINT-MISSING" in codes
    assert "R19-BACKEND-CREDENTIALS-MISSING" in codes
    assert "R19-DEPLOYMENT-EVIDENCE-MISSING" in codes
    assert "R19-CONNECTIVITY-EVIDENCE-MISSING" in codes
    assert "R19-KMS-KEY-MISSING" in codes
    assert "R19-SEMANTIC-INDEX-REFERENCE-MISSING" in codes


def test_r19_memory_backend_readiness_accepts_configured_external_backend() -> None:
    readiness = r19_memory_readiness(
        {
            "memory_backend": "vector",
            "semantic_index_backend": "pgvector",
            "endpoint_reference": "memory-vector.internal",
            "index_reference": "project-memory-index",
            "credentials_reference": "vault:r19-memory",
            "deployment_evidence_ref": "deployments/r19/vector-cluster",
            "connectivity_evidence_ref": "evidence/r19/connectivity.json",
            "encryption_required": True,
            "kms_key_ref": "kms:r19-memory",
            "rbac_policy_ref": "policy:r19-memory-rbac",
        }
    )

    assert readiness.ready is True
    assert not any(item["severity"] == "fatal" for item in readiness.diagnostics)


def test_r19_authorization_denies_confidential_access_without_privileged_role() -> None:
    denied = r19_authorize_memory_action(
        action="read",
        actor_type="human",
        actor_role="memory-reader",
        include_confidential=True,
    )
    allowed = r19_authorize_memory_action(
        action="read",
        actor_type="human",
        actor_role="compliance-officer",
        include_confidential=True,
    )

    assert denied.allowed is False
    assert denied.code == "R19-AUTHORIZATION-DENIED"
    assert allowed.allowed is True
    assert allowed.code == "R19-AUTHORIZED"


def test_r19_semantic_index_report_is_deterministic_and_backend_bound() -> None:
    store = r19_store_memory(
        None,
        project_id="crm",
        domain="knowledge",
        category="lesson",
        author="operator",
        source="postmortem",
        summary="Billing retry behavior should preserve idempotency.",
        content={"lesson": "preserve idempotency"},
        tags=["billing", "idempotency"],
    )

    first = r19_semantic_index_report(
        store,
        {"semantic_index_backend": "deterministic"},
    )
    second = r19_semantic_index_report(
        store,
        {"semantic_index_backend": "deterministic"},
    )

    assert first.report_hash == second.report_hash
    assert first.entries[0].backend == "deterministic"
    assert first.entries[0].embedding_ref.startswith("deterministic:")


def test_r19_production_validation_combines_store_and_backend_checks() -> None:
    store = r19_store_memory(
        None,
        project_id="crm",
        domain="operations",
        category="incident",
        author="sre",
        source="monitoring",
        summary="Failed execution was recovered.",
        content={"incident": "execution failure"},
        tags=["incident"],
    )

    report = r19_production_validate_store(
        store,
        {"memory_backend": "custom", "semantic_index_backend": "custom"},
    )

    assert report.valid is False
    assert "R19-BACKEND-ENDPOINT-MISSING" in {item["code"] for item in report.diagnostics}


def test_r19_api_exposes_contract_store_query_context_export_validate() -> None:
    client = TestClient(app)

    openapi = client.get("/openapi.json").json()
    assert "/api/v1/r19/memory-contract" in openapi["paths"]
    assert "/api/v1/r19/memory/store" in openapi["paths"]
    assert "/api/v1/r19/memory/query" in openapi["paths"]
    assert "/api/v1/r19/memory/context" in openapi["paths"]
    assert "/api/v1/r19/memory/export" in openapi["paths"]
    assert "/api/v1/r19/memory/validate" in openapi["paths"]
    assert "/api/v1/r19/memory/readiness" in openapi["paths"]
    assert "/api/v1/r19/memory/semantic-index" in openapi["paths"]
    assert "/api/v1/r19/memory/production-validate" in openapi["paths"]
    assert "/api/v1/r19/memory/authorization/{action}" in openapi["paths"]

    contract = client.get("/api/v1/r19/memory-contract", headers=_actor_headers())
    assert contract.status_code == 200
    assert contract.json()["engine_version"] == MEMORY_ENGINE_VERSION

    stored = client.post(
        "/api/v1/r19/memory/store",
        headers=_actor_headers(),
        json={
            "project_id": "api-test",
            "domain": "architecture",
            "category": "adr",
            "source": "test",
            "summary": "API memory record for query.",
            "content": {"decision": "test"},
            "tags": ["api"],
        },
    )
    assert stored.status_code == 200
    memory_id = stored.json()["store"]["records"][0]["memory_id"]

    query = client.post(
        "/api/v1/r19/memory/query",
        headers=_actor_headers(),
        json={"query": {"project_id": "api-test", "text": "query"}},
    )
    assert query.status_code == 200
    assert query.json()["result"]["records"][0]["memory_id"] == memory_id

    validation = client.get("/api/v1/r19/memory/validate", headers=_actor_headers())
    assert validation.status_code == 200
    assert validation.json()["valid"] is True

    readiness = client.post(
        "/api/v1/r19/memory/readiness",
        headers=_actor_headers(),
        json={"backend_config": {"memory_backend": "filesystem"}},
    )
    assert readiness.status_code == 200
    assert readiness.json()["readiness"]["ready"] is True


def test_r19_api_denies_confidential_query_to_non_confidential_role() -> None:
    client = TestClient(app)
    headers = {
        "X-Actor-ID": "reader",
        "X-Actor-Type": "human",
        "X-Actor-Role": "memory-reader",
    }

    response = client.post(
        "/api/v1/r19/memory/query",
        headers=headers,
        json={"query": {"include_confidential": True}},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "R19-AUTHORIZATION-DENIED"
