from __future__ import annotations

import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from ai_enterprise.application.r15_manifest_compiler_runtime import r15_compile_manifest
from ai_enterprise.application.r16_knowledge_graph_runtime import r16_load_graph
from ai_enterprise.application.r17_execution_planner_runtime import r17_create_execution_plan
from ai_enterprise.application.r18_generator_orchestration_runtime import (
    BUILTIN_GENERATOR_REGISTRY,
    ORCHESTRATOR_VERSION,
    R18MockOpenAICompatibleAdapter,
    r18_check_provider_readiness,
    r18_orchestrate_execution,
    r18_persist_execution_result,
    r18_read_execution_history,
    r18_validate_generator_registry,
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


def _plan_and_graph() -> tuple[dict[str, object], dict[str, object]]:
    graph = _graph()
    plan = r17_create_execution_plan(graph)
    approvals = {gate.approval_id: True for gate in plan.approval_gates}
    plan_payload = plan.model_dump(mode="json")
    plan_payload["_test_approvals"] = approvals
    return plan_payload, graph


def test_r18_registry_validates_builtin_generators() -> None:
    report = r18_validate_generator_registry()

    assert report.valid is True
    assert report.registry_hash
    assert report.diagnostics == ()


def test_r18_orchestrates_r17_plan_deterministically_with_traceable_artifacts() -> None:
    plan, graph = _plan_and_graph()
    approvals = plan.pop("_test_approvals")

    first = r18_orchestrate_execution(
        plan,
        graph,
        orchestration_options={"approvals": approvals},
    )
    second = r18_orchestrate_execution(
        plan,
        graph,
        orchestration_options={"approvals": approvals},
    )

    assert first.status == "completed"
    assert first.result_hash == second.result_hash
    assert first.execution_signature == second.execution_signature
    assert first.orchestrator_version == ORCHESTRATOR_VERSION
    assert first.task_records
    assert first.artifact_repository.artifact_count == first.metrics["artifact_count"]
    assert first.artifact_repository.immutable_stage_ids
    artifact = first.task_records[0].artifacts[0]
    assert artifact.execution_task_id == first.task_records[0].task_id
    assert artifact.registry_reference
    assert artifact.manifest_origin
    assert artifact.immutable is True


def test_r18_blocks_without_required_human_approvals() -> None:
    plan, graph = _plan_and_graph()
    plan.pop("_test_approvals")

    result = r18_orchestrate_execution(plan, graph)

    assert result.status == "blocked"
    assert result.task_records == ()
    assert "R18-APPROVAL-MISSING" in {item.code for item in result.diagnostics}


def test_r18_selectively_retries_transient_task_failures() -> None:
    plan, graph = _plan_and_graph()
    approvals = plan.pop("_test_approvals")
    target_task_id = plan["tasks"][0]["task_id"]

    result = r18_orchestrate_execution(
        plan,
        graph,
        orchestration_options={
            "approvals": approvals,
            "transient_fail_task_ids": [target_task_id],
        },
    )

    retried = next(item for item in result.task_records if item.task_id == target_task_id)
    assert result.status == "completed"
    assert retried.retry_count == 1
    assert "retry_eligible" in {item.status for item in retried.lifecycle}
    assert result.metrics["retry_count"] == 1


def test_r18_registry_validation_rejects_missing_required_task_support() -> None:
    incomplete_registry = [
        item.model_dump(mode="json")
        for item in BUILTIN_GENERATOR_REGISTRY
        if item.generator_id != "generator.deployment"
    ]

    report = r18_validate_generator_registry(incomplete_registry)

    assert report.valid is False
    assert "R18-GENERATOR-TASK-MISSING" in {item.code for item in report.diagnostics}


def test_r18_execution_requires_exact_generator_owner_from_plan() -> None:
    plan, graph = _plan_and_graph()
    approvals = plan.pop("_test_approvals")
    replacement_registry = [
        item.model_dump(mode="json")
        for item in BUILTIN_GENERATOR_REGISTRY
        if item.generator_id != "generator.database"
    ]
    replacement = next(
        item.model_dump(mode="json")
        for item in BUILTIN_GENERATOR_REGISTRY
        if item.generator_id == "generator.database"
    )
    replacement["generator_id"] = "custom.database"
    replacement_registry.append(replacement)

    result = r18_orchestrate_execution(
        plan,
        graph,
        generator_registry=replacement_registry,
        orchestration_options={"approvals": approvals},
    )

    assert result.status == "blocked"
    assert "R18-ASSIGNED-GENERATOR-UNAVAILABLE" in {item.code for item in result.diagnostics}


def test_r18_external_provider_registry_fails_closed_without_configuration() -> None:
    plan, graph = _plan_and_graph()
    approvals = plan.pop("_test_approvals")
    registry = [item.model_dump(mode="json") for item in BUILTIN_GENERATOR_REGISTRY]
    database = next(item for item in registry if item["generator_id"] == "generator.database")
    database["model_provider"] = "openai"
    database["model_version"] = "gpt-production"

    readiness = r18_check_provider_readiness(registry)
    result = r18_orchestrate_execution(
        plan,
        graph,
        generator_registry=registry,
        orchestration_options={"approvals": approvals},
    )

    assert any(item.provider == "openai" and item.configured is False for item in readiness)
    assert result.status == "blocked"
    assert "R18-EXTERNAL-PROVIDER-NOT-READY" in {item.code for item in result.diagnostics}


def test_r18_external_provider_registry_uses_injected_mock_adapter() -> None:
    plan, graph = _plan_and_graph()
    approvals = plan.pop("_test_approvals")
    registry = [item.model_dump(mode="json") for item in BUILTIN_GENERATOR_REGISTRY]
    database = next(item for item in registry if item["generator_id"] == "generator.database")
    database["model_provider"] = "openai"
    database["model_version"] = "gpt-production"

    result = r18_orchestrate_execution(
        plan,
        graph,
        generator_registry=registry,
        orchestration_options={
            "approvals": approvals,
            "provider_configs": {
                "openai": {
                    "credential_reference": "env:OPENAI_API_KEY",
                    "model_reference": "gpt-production",
                }
            },
            "provider_adapters": {"openai": R18MockOpenAICompatibleAdapter()},
        },
    )

    assert result.status == "completed"
    assert any(
        item.provider == "openai" and item.supports_live_execution
        for item in result.provider_readiness
    )
    assert result.metrics["provider_call_count"] == sum(
        1 for item in plan["tasks"] if item["generator"] == "generator.database"
    )


def test_r18_openai_http_adapter_translates_provider_response() -> None:
    plan, graph = _plan_and_graph()
    approvals = plan.pop("_test_approvals")
    registry = [item.model_dump(mode="json") for item in BUILTIN_GENERATOR_REGISTRY]
    database = next(item for item in registry if item["generator_id"] == "generator.database")
    database["model_provider"] = "openai"
    database["model_version"] = "gpt-production"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://api.openai.test/v1/responses")
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "output_text": json.dumps(
                    {
                        "artifacts": [
                            {
                                "artifact_type": "schema",
                                "content": {"generated_text": "provider schema"},
                            },
                            {
                                "artifact_type": "repository-contract",
                                "content": {"generated_text": "provider repository"},
                            },
                        ]
                    }
                )
            },
        )

    result = r18_orchestrate_execution(
        plan,
        graph,
        generator_registry=registry,
        orchestration_options={
            "approvals": approvals,
            "enable_live_provider_calls": True,
            "http_transport": httpx.MockTransport(handler),
            "provider_configs": {
                "openai": {
                    "api_key": "test-key",
                    "model_reference": "gpt-production",
                    "endpoint_reference": "https://api.openai.test/v1/responses",
                }
            },
        },
    )

    provider_record = next(
        item for item in result.task_records if item.generator_id == "generator.database"
    )
    assert result.status == "completed"
    assert provider_record.metrics.provider_calls == 1
    assert provider_record.artifacts[0].generated_content["generated_text"] == "provider schema"


def test_r18_provider_output_must_include_every_required_artifact() -> None:
    plan, graph = _plan_and_graph()
    approvals = plan.pop("_test_approvals")
    registry = [item.model_dump(mode="json") for item in BUILTIN_GENERATOR_REGISTRY]
    database = next(item for item in registry if item["generator_id"] == "generator.database")
    database["model_provider"] = "openai"
    database["model_version"] = "gpt-production"
    first_database_task = next(
        item for item in plan["tasks"] if item["generator"] == "generator.database"
    )

    result = r18_orchestrate_execution(
        plan,
        graph,
        generator_registry=registry,
        orchestration_options={
            "approvals": approvals,
            "provider_configs": {
                "openai": {
                    "credential_reference": "env:OPENAI_API_KEY",
                    "model_reference": "gpt-production",
                }
            },
            "provider_adapters": {
                "openai": R18MockOpenAICompatibleAdapter(
                    outputs={
                        first_database_task["task_id"]: [
                            {
                                "artifact_type": "schema",
                                "content": {"generated_text": "schema only"},
                            }
                        ]
                    }
                )
            },
        },
    )

    failed = next(
        item for item in result.task_records if item.task_id == first_database_task["task_id"]
    )
    assert result.status == "blocked"
    assert failed.status == "failed"
    assert "R18-ARTIFACT-OUTPUT-MISSING" in {
        item["code"] for item in failed.validation_report.diagnostics
    }


def test_r18_provider_output_rejects_duplicate_and_unrequested_artifacts() -> None:
    plan, graph = _plan_and_graph()
    approvals = plan.pop("_test_approvals")
    registry = [item.model_dump(mode="json") for item in BUILTIN_GENERATOR_REGISTRY]
    database = next(item for item in registry if item["generator_id"] == "generator.database")
    database["model_provider"] = "openai"
    database["model_version"] = "gpt-production"
    first_database_task = next(
        item for item in plan["tasks"] if item["generator"] == "generator.database"
    )

    result = r18_orchestrate_execution(
        plan,
        graph,
        generator_registry=registry,
        orchestration_options={
            "approvals": approvals,
            "provider_configs": {
                "openai": {
                    "credential_reference": "env:OPENAI_API_KEY",
                    "model_reference": "gpt-production",
                }
            },
            "provider_adapters": {
                "openai": R18MockOpenAICompatibleAdapter(
                    outputs={
                        first_database_task["task_id"]: [
                            {
                                "artifact_type": "schema",
                                "content": {"generated_text": "schema one"},
                            },
                            {
                                "artifact_type": "schema",
                                "content": {"generated_text": "schema two"},
                            },
                            {
                                "artifact_type": "unexpected",
                                "content": {"generated_text": "extra"},
                            },
                        ]
                    }
                )
            },
        },
    )

    failed = next(
        item for item in result.task_records if item.task_id == first_database_task["task_id"]
    )
    codes = {item["code"] for item in failed.validation_report.diagnostics}
    assert result.status == "blocked"
    assert "R18-ARTIFACT-OUTPUT-DUPLICATE" in codes
    assert "R18-ARTIFACT-UNREQUESTED-OUTPUT" in codes


def test_r18_materializes_physical_artifacts_when_enabled(tmp_path: Path) -> None:
    plan, graph = _plan_and_graph()
    approvals = plan.pop("_test_approvals")

    result = r18_orchestrate_execution(
        plan,
        graph,
        orchestration_options={
            "approvals": approvals,
            "materialize_artifacts": True,
            "artifact_root": str(tmp_path),
        },
    )

    assert result.status == "completed"
    assert result.artifact_repository.materialized_artifacts
    materialized = result.artifact_repository.materialized_artifacts[0]
    materialized_path = Path(materialized.physical_path)
    assert materialized_path.exists()
    payload = json.loads(materialized_path.read_text(encoding="utf-8"))
    assert payload["artifact"]["artifact_id"] == materialized.artifact_id
    assert payload["generated_content"]["traceability"]["manifest_origin"]


def test_r18_execution_history_is_append_only_and_hash_bound(tmp_path: Path) -> None:
    plan, graph = _plan_and_graph()
    approvals = plan.pop("_test_approvals")
    result = r18_orchestrate_execution(
        plan,
        graph,
        orchestration_options={"approvals": approvals},
    )
    history_path = tmp_path / "runtime" / "r18-history.jsonl"

    record_hash = r18_persist_execution_result(
        result,
        history_path,
        actor_id="operator",
    )
    records = r18_read_execution_history(history_path)

    assert len(records) == 1
    assert records[0]["record_hash"] == record_hash
    assert records[0]["result_hash"] == result.result_hash
    assert records[0]["execution_signature"] == result.execution_signature


def test_r18_api_is_exposed_for_contract_registry_execute_and_history() -> None:
    client = TestClient(app)
    plan, graph = _plan_and_graph()
    approvals = plan.pop("_test_approvals")

    openapi = client.get("/openapi.json").json()
    assert "/api/v1/r18/orchestrator-contract" in openapi["paths"]
    assert "/api/v1/r18/generator-registry/validate" in openapi["paths"]
    assert "/api/v1/r18/provider-readiness" in openapi["paths"]
    assert "/api/v1/r18/execute-plan" in openapi["paths"]
    assert "/api/v1/r18/execution-history" in openapi["paths"]

    contract = client.get(
        "/api/v1/r18/orchestrator-contract",
        headers=_actor_headers(),
    )
    assert contract.status_code == 200
    assert contract.json()["orchestrator_version"] == ORCHESTRATOR_VERSION

    registry = client.post(
        "/api/v1/r18/generator-registry/validate",
        headers=_actor_headers(),
        json={},
    )
    assert registry.status_code == 200
    assert registry.json()["valid"] is True

    readiness = client.post(
        "/api/v1/r18/provider-readiness",
        headers=_actor_headers(),
        json={},
    )
    assert readiness.status_code == 200
    assert readiness.json()["providers"]

    execution = client.post(
        "/api/v1/r18/execute-plan",
        headers=_actor_headers(),
        json={
            "plan": plan,
            "graph": graph,
            "orchestration_options": {"approvals": approvals},
        },
    )
    assert execution.status_code == 200
    assert execution.json()["result"]["status"] == "completed"
