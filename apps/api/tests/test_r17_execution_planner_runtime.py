from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from ai_enterprise.application.r15_manifest_compiler_runtime import r15_compile_manifest
from ai_enterprise.application.r16_knowledge_graph_runtime import r16_load_graph
from ai_enterprise.application.r17_execution_planner_runtime import (
    PLANNER_VERSION,
    PLANNING_STAGES,
    R17ExecutionPlan,
    r17_create_execution_plan,
    r17_persist_execution_plan,
    r17_read_execution_plan_history,
    r17_validate_execution_plan,
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


def test_r17_planner_creates_deterministic_signed_execution_plan() -> None:
    graph = _graph()

    first = r17_create_execution_plan(graph)
    second = r17_create_execution_plan(graph)

    assert first.plan_hash == second.plan_hash
    assert first.plan_signature == second.plan_signature
    assert first.planner_version == PLANNER_VERSION
    assert [stage.stage_id for stage in first.stages] == [
        stage_id for stage_id, _ in PLANNING_STAGES
    ]
    assert first.tasks
    assert first.dependencies
    assert first.validation_gates
    assert first.rollback_points
    assert first.parallel_groups
    assert first.metrics["task_count"] == len(first.tasks)
    assert first.diagnostics == ()
    assert r17_validate_execution_plan(first).valid is True


def test_r17_tasks_are_atomic_owned_and_explainable() -> None:
    plan = r17_create_execution_plan(_graph())

    task = next(item for item in plan.tasks if item.knowledge_node_id == "customer")

    assert task.task_id
    assert task.generator
    assert task.inputs
    assert task.outputs
    assert task.retry_policy["max_attempts"] == 2
    assert task.validation_rule.startswith("validate.")
    assert task.knowledge_node_type == "entity"
    assert f"generator:{task.generator}" in task.required_permissions
    assert task.execution_context["network_policy"] == "deny-by-default"
    assert task.explainability["manifest_origin"]
    assert task.explainability["registry_reference"].startswith("registry/")
    assert task.explainability["knowledge_node_id"] == "customer"


def test_r17_hardening_adds_permissions_approvals_resources_and_decisions() -> None:
    plan = r17_create_execution_plan(
        _graph(),
        planning_options={
            "max_parallel_jobs": 2,
            "distributed_planning_enabled": True,
            "max_partition_task_count": 3,
        },
    )

    assert plan.execution_policy.require_manual_deployment_approval is True
    assert plan.execution_policy.require_security_review is True
    assert plan.generator_permissions
    assert {item.approval_type for item in plan.approval_gates} >= {
        "manual_deployment_release",
    }
    assert all(item.max_parallel_jobs <= 2 for item in plan.resource_schedule)
    assert plan.distributed_planning.enabled is True
    assert plan.distributed_planning.partition_count > 1
    assert {item.category for item in plan.decision_log} >= {
        "generator",
        "planning",
        "policy",
        "approval",
        "scheduling",
    }


def test_r17_incremental_replanning_marks_reusable_and_changed_tasks() -> None:
    graph = _graph()
    first = r17_create_execution_plan(graph)
    second = r17_create_execution_plan(
        graph,
        planning_options={"previous_plan": first.model_dump(mode="json")},
    )

    assert second.incremental_impact.previous_plan_hash == first.plan_hash
    assert second.incremental_impact.added_task_ids == ()
    assert second.incremental_impact.removed_task_ids == ()
    assert second.incremental_impact.changed_task_ids == ()
    assert second.incremental_impact.reusable_task_ids

    changed_graph = json.loads(json.dumps(graph))
    changed_graph["nodes"][1]["description"] = "Changed semantic description."
    third = r17_create_execution_plan(
        changed_graph,
        planning_options={"previous_plan": first.model_dump(mode="json")},
    )

    assert third.incremental_impact.changed_task_ids


def test_r17_validation_rejects_tampered_plan_signature() -> None:
    plan = r17_create_execution_plan(_graph())
    payload = plan.model_dump(mode="json")
    payload["plan_signature"] = "bad"

    report = r17_validate_execution_plan(R17ExecutionPlan.model_validate(payload))

    assert report.valid is False
    assert {item.code for item in report.diagnostics} == {"R17-INVALID-SIGNATURE"}


def test_r17_validation_rejects_tampered_plan_body_even_with_existing_signature() -> None:
    plan = r17_create_execution_plan(_graph())
    payload = plan.model_dump(mode="json")
    payload["tasks"][0]["generator"] = "generator.unauthorized"

    report = r17_validate_execution_plan(R17ExecutionPlan.model_validate(payload))

    assert report.valid is False
    assert {item.code for item in report.diagnostics} >= {
        "R17-GENERATOR-MISMATCH",
        "R17-GENERATOR-MISSING",
        "R17-PLAN-HASH-MISMATCH",
    }


def test_r17_validation_enforces_generator_permissions_and_resource_limits() -> None:
    plan = r17_create_execution_plan(
        _graph(),
        planning_options={"resource_limits": {"cpu": 1}},
    )

    assert r17_validate_execution_plan(plan).valid is False
    assert "R17-RESOURCE-BUDGET-EXCEEDED" in {
        item.code for item in r17_validate_execution_plan(plan).diagnostics
    }

    clean = r17_create_execution_plan(_graph())
    payload = clean.model_dump(mode="json")
    payload["tasks"][0]["knowledge_node_type"] = "forbidden"

    report = r17_validate_execution_plan(R17ExecutionPlan.model_validate(payload))

    assert report.valid is False
    assert "R17-GENERATOR-PERMISSION-DENIED" in {item.code for item in report.diagnostics}


def test_r17_execution_plan_history_is_append_only_and_hash_bound(tmp_path: Path) -> None:
    plan = r17_create_execution_plan(_graph())
    history_path = tmp_path / "planner" / "history.jsonl"

    record_hash = r17_persist_execution_plan(
        plan,
        history_path,
        actor_id="operator",
    )
    records = r17_read_execution_plan_history(history_path)

    assert len(records) == 1
    assert records[0]["record_hash"] == record_hash
    assert records[0]["plan_hash"] == plan.plan_hash
    assert records[0]["plan_signature"] == plan.plan_signature


def test_r17_api_is_exposed_for_planner_contract_create_and_validate() -> None:
    client = TestClient(app)
    graph = _graph()

    openapi = client.get("/openapi.json").json()
    assert "/api/v1/r17/planner-contract" in openapi["paths"]
    assert "/api/v1/r17/execution-plan/create" in openapi["paths"]
    assert "/api/v1/r17/execution-plan/validate" in openapi["paths"]

    response = client.post(
        "/api/v1/r17/execution-plan/create",
        headers=_actor_headers(),
        json={"graph": graph},
    )

    assert response.status_code == 200
    plan = response.json()["plan"]
    assert plan["planner_version"] == PLANNER_VERSION
    assert plan["tasks"]
    assert plan["execution_policy"]["policy_id"] == "r17.default.enterprise"
    assert plan["generator_permissions"]
    assert plan["approval_gates"]

    validation = client.post(
        "/api/v1/r17/execution-plan/validate",
        headers=_actor_headers(),
        json={"plan": plan},
    )
    assert validation.status_code == 200
    assert validation.json()["valid"] is True
