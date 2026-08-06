from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from ai_enterprise.application.r15_manifest_compiler_runtime import r15_compile_manifest
from ai_enterprise.application.r16_knowledge_graph_runtime import r16_load_graph
from ai_enterprise.application.r17_execution_planner_runtime import r17_create_execution_plan
from ai_enterprise.application.r18_generator_orchestration_runtime import r18_orchestrate_execution
from ai_enterprise.application.r19_project_memory_runtime import (
    r19_ingest_r17_execution_plan,
    r19_ingest_r18_execution_result,
)
from ai_enterprise.application.r20_runtime_kernel_runtime import (
    RUNTIME_KERNEL_VERSION,
    SERVICE_INTERFACES,
    r20_boot_kernel,
    r20_read_kernel,
    r20_recover_kernel,
    r20_transition_lifecycle,
    r20_validate_kernel,
    r20_write_kernel,
)
from ai_enterprise.domain.specification.kernel import specification_hash
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


def _runtime_inputs() -> tuple[
    str, dict[str, object], dict[str, object], dict[str, object], dict[str, object]
]:
    manifest = _load_json(VALID_MANIFEST)
    compiled = r15_compile_manifest(manifest, SCHEMA, REGISTRY)
    assert compiled.success_status is True
    assert compiled.knowledge_graph is not None
    manifest_hash = specification_hash(manifest)
    graph = r16_load_graph(
        compiled.knowledge_graph.model_dump(mode="json"),
        compilation_report=compiled.compilation_report.model_dump(mode="json"),
        registry_root=REGISTRY,
    )
    plan = r17_create_execution_plan(graph.model_dump(mode="json"))
    result = r18_orchestrate_execution(
        plan,
        graph.model_dump(mode="json"),
        orchestration_options={
            "approvals": {gate.approval_id: True for gate in plan.approval_gates}
        },
    )
    assert result.status == "completed"
    memory = r19_ingest_r17_execution_plan(
        None,
        plan,
        project_id="crm",
        author="planner",
    )
    memory = r19_ingest_r18_execution_result(
        memory,
        result,
        project_id="crm",
        author="orchestrator",
    )
    return (
        manifest_hash,
        graph.model_dump(mode="json"),
        plan.model_dump(mode="json"),
        result.model_dump(mode="json"),
        memory.model_dump(mode="json"),
    )


def test_r20_boots_valid_runtime_kernel_with_services_events_and_policy() -> None:
    manifest_hash, graph, plan, result, memory = _runtime_inputs()

    snapshot = r20_boot_kernel(
        project_id="crm",
        manifest_hash=manifest_hash,
        graph=graph,
        plan=plan,
        execution_result=result,
        memory_store=memory,
    )
    report = r20_validate_kernel(snapshot)

    assert snapshot.kernel_version == RUNTIME_KERNEL_VERSION
    assert snapshot.lifecycle.phase == "boot"
    assert {item.interface for item in snapshot.service_registry} == set(SERVICE_INTERFACES)
    assert len(snapshot.event_history) >= 5
    assert all(item.allowed for item in snapshot.policy_decisions)
    assert snapshot.schedule
    assert snapshot.task_states
    assert report.valid is True


def test_r20_lifecycle_transitions_are_forward_only_and_append_events() -> None:
    manifest_hash, graph, plan, result, memory = _runtime_inputs()
    booted = r20_boot_kernel(
        project_id="crm",
        manifest_hash=manifest_hash,
        graph=graph,
        plan=plan,
        execution_result=result,
        memory_store=memory,
    )

    initialized = r20_transition_lifecycle(booted, "initialize")
    denied = r20_transition_lifecycle(initialized, "boot")

    assert initialized.lifecycle.phase == "initialize"
    assert initialized.lifecycle.transition_allowed is True
    assert initialized.state.state_version == booted.state.state_version + 1
    assert len(initialized.event_history) == len(booted.event_history) + 1
    assert denied.lifecycle.transition_allowed is False
    assert "R20-LIFECYCLE-TRANSITION-DENIED" in {item.code for item in denied.diagnostics}
    assert r20_validate_kernel(denied).valid is False


def test_r20_scheduler_preserves_plan_tasks_and_dependency_order() -> None:
    manifest_hash, graph, plan, result, memory = _runtime_inputs()
    snapshot = r20_boot_kernel(
        project_id="crm",
        manifest_hash=manifest_hash,
        graph=graph,
        plan=plan,
        execution_result=result,
        memory_store=memory,
    )
    planned_task_ids = {item["task_id"] for item in plan["tasks"]}
    scheduled_task_ids = {item.task_id for item in snapshot.schedule}
    order_by_task = {item.task_id: item.order for item in snapshot.schedule}

    assert scheduled_task_ids == planned_task_ids
    for item in snapshot.schedule:
        assert set(item.dependency_ids) <= planned_task_ids
        assert all(order_by_task[dependency] < item.order for dependency in item.dependency_ids)


def test_r20_recovery_moves_failed_tasks_to_retry_until_retry_limit() -> None:
    manifest_hash, graph, plan, _, memory = _runtime_inputs()
    result = r18_orchestrate_execution(
        plan,
        graph,
        orchestration_options={
            "approvals": {gate["approval_id"]: True for gate in plan["approval_gates"]},
            "fail_task_ids": [plan["tasks"][0]["task_id"]],
        },
    )
    snapshot = r20_boot_kernel(
        project_id="crm",
        manifest_hash=manifest_hash,
        graph=graph,
        plan=plan,
        execution_result=result,
        memory_store=memory,
    )

    recovered = r20_recover_kernel(snapshot)

    assert any(item.state == "failed" for item in snapshot.task_states)
    assert any(item.state == "retry" for item in recovered.task_states)
    assert recovered.state.state_version == snapshot.state.state_version + 1
    assert recovered.event_history[-1].event_type == "runtime.recovery"


def test_r20_filesystem_persistence_roundtrip(tmp_path: Path) -> None:
    manifest_hash, graph, plan, result, memory = _runtime_inputs()
    snapshot = r20_boot_kernel(
        project_id="crm",
        manifest_hash=manifest_hash,
        graph=graph,
        plan=plan,
        execution_result=result,
        memory_store=memory,
    )
    path = tmp_path / "runtime" / "kernel.json"

    written_hash = r20_write_kernel(snapshot, path)
    loaded = r20_read_kernel(path)

    assert written_hash == snapshot.kernel_hash
    assert loaded is not None
    assert loaded.kernel_hash == snapshot.kernel_hash


def test_r20_api_exposes_runtime_kernel_contract_boot_validate_and_events() -> None:
    client = TestClient(app)
    manifest_hash, graph, plan, result, memory = _runtime_inputs()

    openapi = client.get("/openapi.json").json()
    assert "/api/v1/r20/runtime-kernel-contract" in openapi["paths"]
    assert "/api/v1/r20/runtime-kernel/boot" in openapi["paths"]
    assert "/api/v1/r20/runtime-kernel/validate" in openapi["paths"]

    boot = client.post(
        "/api/v1/r20/runtime-kernel/boot",
        headers=_actor_headers(),
        json={
            "project_id": "crm",
            "manifest_hash": manifest_hash,
            "graph": graph,
            "plan": plan,
            "execution_result": result,
            "memory_store": memory,
            "persist": False,
        },
    )
    assert boot.status_code == 200
    snapshot = boot.json()["snapshot"]
    validation = client.post(
        "/api/v1/r20/runtime-kernel/validate",
        headers=_actor_headers(),
        json={"snapshot": snapshot},
    )

    assert validation.status_code == 200
    assert validation.json()["valid"] is True
