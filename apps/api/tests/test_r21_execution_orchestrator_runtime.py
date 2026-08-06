from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_enterprise.application.r21_execution_orchestrator_runtime import (
    EXECUTION_ORCHESTRATOR_VERSION,
    WORKER_TYPES,
    r21_analyze_manifest_change,
    r21_apply_approval,
    r21_cancel_execution,
    r21_cancel_work_package,
    r21_compile_project,
    r21_create_execution_plan,
    r21_pause_execution,
    r21_read_compilation,
    r21_read_execution,
    r21_read_execution_plan,
    r21_recover_execution,
    r21_remediate_work_package,
    r21_resume_execution,
    r21_retry_work_package,
    r21_start_execution,
    r21_write_compilation,
    r21_write_execution,
    r21_write_execution_plan,
)
from ai_enterprise.application.r21_persistence_service import R21PersistenceService
from ai_enterprise.infrastructure.r21.models import (
    R21ExecutionCheckpointModel,
    R21ExecutionEventRecordModel,
    R21ExecutionModel,
    R21ExecutionPlanModel,
    R21ProjectCompilationModel,
    R21WorkPackageRecordModel,
)
from ai_enterprise.main import app
from ai_enterprise.observability import metrics_snapshot

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "schemas" / "Manifest.schema.json"
REGISTRY = ROOT / "registry"
VALID_MANIFEST = ROOT / "manifest" / "crm.r14.json"


def _load_manifest() -> dict[str, object]:
    return json.loads(VALID_MANIFEST.read_text(encoding="utf-8"))


def _actor_headers() -> dict[str, str]:
    return {
        "X-Actor-ID": "local-dashboard-admin",
        "X-Actor-Type": "human",
        "X-Actor-Role": "platform-admin",
    }


def _compiled_plan() -> tuple[dict[str, object], object, object]:
    manifest = _load_manifest()
    compilation = r21_compile_project(manifest, SCHEMA, REGISTRY)
    plan = r21_create_execution_plan(manifest, compilation)
    return manifest, compilation, plan


def _approved_execution() -> tuple[dict[str, object], object, object, object]:
    manifest, _, plan = _compiled_plan()
    execution = r21_start_execution(plan)
    execution = r21_apply_approval(
        execution,
        gate_id="gate-release",
        decision="approve",
        actor_role="project_owner",
        actor_id="owner",
    )
    execution = r21_apply_approval(
        execution,
        gate_id="gate-release",
        decision="approve",
        actor_role="release_authority",
        actor_id="release",
    )
    execution = r21_resume_execution(plan, execution)
    return manifest, plan, execution, execution.delivery_package


def test_r21_compiles_manifest_and_creates_traceable_execution_plan() -> None:
    manifest, compilation, plan = _compiled_plan()

    assert compilation.status == "COMPILED"
    assert compilation.schema_valid is True
    assert plan.orchestrator_version == EXECUTION_ORCHESTRATOR_VERSION
    assert len(plan.work_packages) == 8
    assert {item.worker_type for item in plan.work_packages} <= set(WORKER_TYPES)
    assert plan.parallel_groups
    assert any(len(group) > 1 for group in plan.parallel_groups)
    assert all(item.manifest_trace.source_objects for item in plan.work_packages)
    assert all(item.idempotency_key for item in plan.work_packages)
    assert plan.project_id == manifest["metadata"]["id"]


def test_r21_successful_execution_pauses_for_human_gate_then_completes_delivery() -> None:
    _, _, plan = _compiled_plan()

    execution = r21_start_execution(plan)

    assert execution.project_state == "AWAITING_AUTHORIZATION"
    assert execution.delivery_package is None
    assert any(item.event_type == "approval.requested" for item in execution.events)
    assert any(item.state == "WAITING_FOR_APPROVAL" for item in execution.work_package_states)
    assert len(execution.artifacts) == 10

    owner_approved = r21_apply_approval(
        execution,
        gate_id="gate-release",
        decision="approve",
        actor_role="project_owner",
        actor_id="owner",
    )
    assert owner_approved.project_state == "AWAITING_AUTHORIZATION"
    assert owner_approved.approval_gates[0].status == "pending"

    release_approved = r21_apply_approval(
        owner_approved,
        gate_id="gate-release",
        decision="approve",
        actor_role="release_authority",
        actor_id="release",
    )
    completed = r21_resume_execution(plan, release_approved)

    assert completed.project_state == "COMPLETED"
    assert completed.delivery_package is not None
    assert completed.delivery_package.delivery_status == "evidence_backed"
    assert all(item.passed for item in completed.validations)
    assert completed.approval_gates[0].decisions[0].bound_artifact_hashes
    assert completed.checkpoints[-1].completed_work_packages


def test_r21_invalid_manifest_is_rejected_before_plan_execution() -> None:
    manifest = _load_manifest()
    manifest.pop("objectives")

    compilation = r21_compile_project(manifest, SCHEMA, REGISTRY)
    plan = r21_create_execution_plan(manifest, compilation)
    execution = r21_start_execution(plan)

    assert compilation.status == "REJECTED"
    assert plan.diagnostics
    assert execution.project_state == "BLOCKED"
    assert "R21-MANIFEST-NOT-COMPILED" in {item.code for item in execution.diagnostics}


def test_r21_worker_validation_failure_creates_retry_record_and_blocks_promotion() -> None:
    _, _, plan = _compiled_plan()

    execution = r21_start_execution(
        plan,
        options={"validation_fail_work_package_ids": ["wp-api-contract-001"]},
    )

    failed_state = next(
        item
        for item in execution.work_package_states
        if item.work_package_id == "wp-api-contract-001"
    )
    assert execution.project_state == "BLOCKED"
    assert failed_state.state == "RETRY_SCHEDULED"
    assert execution.retries
    assert any(item.passed is False for item in execution.validations)
    assert not any(
        artifact.work_package_id == "wp-api-contract-001" for artifact in execution.artifacts
    )


def test_r21_human_rejection_blocks_downstream_delivery() -> None:
    _, _, plan = _compiled_plan()
    execution = r21_start_execution(plan)

    rejected = r21_apply_approval(
        execution,
        gate_id="gate-release",
        decision="reject",
        actor_role="project_owner",
        actor_id="owner",
    )
    resumed = r21_resume_execution(plan, rejected)

    assert rejected.project_state == "REJECTED_OUTPUT"
    assert rejected.approval_gates[0].status == "rejected"
    assert resumed.project_state == "REJECTED_OUTPUT"
    assert resumed.delivery_package is None


def test_r21_checkpoint_persistence_and_recovery_are_idempotent(tmp_path: Path) -> None:
    _, _, execution, _ = _approved_execution()
    path = tmp_path / "r21" / "execution.json"

    written = r21_write_execution(execution, path)
    loaded = r21_read_execution(path)
    recovery = r21_recover_execution(execution.checkpoints[-1])

    assert written == execution.execution_hash
    assert loaded is not None
    assert loaded.execution_hash == execution.execution_hash
    assert recovery["project_state"] == "COMPLETED"
    assert recovery["completed_work_packages"] == list(
        execution.checkpoints[-1].completed_work_packages
    )


def test_r21_compilation_and_plan_persistence_roundtrip(tmp_path: Path) -> None:
    manifest, compilation, plan = _compiled_plan()
    compilation_path = tmp_path / "r21" / "compilation.json"
    plan_path = tmp_path / "r21" / "plan.json"

    compilation_hash = r21_write_compilation(compilation, compilation_path)
    plan_hash = r21_write_execution_plan(plan, plan_path)
    loaded_compilation = r21_read_compilation(compilation_path)
    loaded_plan = r21_read_execution_plan(plan_path)

    assert compilation_hash == compilation.compilation_hash
    assert plan_hash == plan.plan_hash
    assert loaded_compilation is not None
    assert loaded_compilation.project_id == manifest["metadata"]["id"]
    assert loaded_plan is not None
    assert loaded_plan.execution_plan_id == plan.execution_plan_id


def test_r21_runtime_owned_mutations_emit_events_transitions_checkpoints_and_hashes() -> None:
    _, _, plan = _compiled_plan()
    failed = r21_start_execution(
        plan,
        options={"validation_fail_work_package_ids": ["wp-api-contract-001"]},
    )

    retried = r21_retry_work_package(
        failed,
        work_package_id="wp-api-contract-001",
        actor_id="operator",
    )
    cancelled_package = r21_cancel_work_package(
        retried,
        work_package_id="wp-api-contract-001",
        actor_id="operator",
    )
    remediated = r21_remediate_work_package(
        cancelled_package,
        work_package_id="wp-api-contract-001",
        actor_id="operator",
    )
    cancelled_execution = r21_cancel_execution(
        remediated,
        reason="operator-cancel",
        actor_id="operator",
    )

    assert retried.execution_hash != failed.execution_hash
    assert retried.events[-1].event_type == "work_package.retry_scheduled"
    assert retried.transitions[-1].to_state == "PENDING"
    assert retried.checkpoints[-1].project_state == "EXECUTING"
    assert cancelled_package.events[-1].event_type == "work_package.cancelled"
    assert cancelled_package.transitions[-1].to_state == "CANCELLED"
    assert remediated.events[-1].event_type == "work_package.remediation_requested"
    assert remediated.transitions[-1].to_state == "PENDING"
    assert cancelled_execution.project_state == "FAILED"
    assert cancelled_execution.events[-1].event_type == "execution.cancelled"
    assert cancelled_execution.checkpoints[-1].project_state == "FAILED"


def test_r21_manifest_change_impact_invalidates_affected_artifacts_and_approvals() -> None:
    manifest, plan, execution, _ = _approved_execution()
    changed = json.loads(json.dumps(manifest))
    changed["capabilities"][0]["description"] = "Changed capability scope."

    analysis = r21_analyze_manifest_change(manifest, changed, plan, execution)

    assert analysis.impact_class == "LOCAL"
    assert analysis.plan_regeneration_required is True
    assert analysis.affected_work_package_ids
    assert analysis.invalidated_artifact_ids
    assert analysis.invalidated_gate_ids


def test_r21_policy_violation_blocks_execution_and_records_security_event() -> None:
    _, _, plan = _compiled_plan()

    execution = r21_start_execution(plan, options={"prohibited_tool_attempts": ["artifact.write"]})

    assert execution.project_state == "BLOCKED"
    assert "R21-POLICY-VIOLATION" in {item.code for item in execution.diagnostics}
    assert any(item.event_type == "policy.violation.detected" for item in execution.events)


def test_r21_pause_preserves_checkpoint_without_completing_delivery() -> None:
    _, _, plan = _compiled_plan()
    execution = r21_start_execution(plan)

    paused = r21_pause_execution(execution, "operator-pause")

    assert paused.project_state == "PAUSED"
    assert paused.delivery_package is None
    assert paused.checkpoints[-1].project_state == "PAUSED"


def test_r21_api_exposes_compile_plan_execute_approval_resume_and_recovery() -> None:
    client = TestClient(app)
    manifest = _load_manifest()

    openapi = client.get("/openapi.json").json()
    assert "/api/v1/r21/orchestrator-contract" in openapi["paths"]
    assert "/api/v1/r21/projects/{project_id}/compile" in openapi["paths"]
    assert "/api/v1/r21/projects/{project_id}/execution-plans" in openapi["paths"]
    assert "/api/v1/r21/projects/{project_id}/executions" in openapi["paths"]
    assert "/api/v1/r21/approval-gates/{gate_id}/decisions" in openapi["paths"]
    assert "/api/v1/r21/executions/recover" in openapi["paths"]

    compile_response = client.post(
        "/api/v1/r21/projects/crm-v1/compile",
        headers=_actor_headers(),
        json={"manifest": manifest, "persist": True},
    )
    assert compile_response.status_code == 200
    compilation = compile_response.json()["compilation"]

    plan_response = client.post(
        "/api/v1/r21/projects/crm-v1/execution-plans",
        headers=_actor_headers(),
        json={"manifest": manifest, "compilation": compilation, "persist": True},
    )
    assert plan_response.status_code == 200
    plan = plan_response.json()["plan"]
    persisted_plan_response = client.get(
        f"/api/v1/r21/projects/crm-v1/execution-plans/{plan['execution_plan_id']}",
        headers=_actor_headers(),
    )
    assert persisted_plan_response.status_code == 200
    assert persisted_plan_response.json()["plan"]["plan_hash"] == plan["plan_hash"]

    execution_response = client.post(
        "/api/v1/r21/projects/crm-v1/executions",
        headers=_actor_headers(),
        json={"plan": plan, "persist": True},
    )
    assert execution_response.status_code == 200
    execution = execution_response.json()["execution"]
    assert execution["project_state"] == "AWAITING_AUTHORIZATION"

    for role in ("project_owner", "release_authority"):
        approval_response = client.post(
            "/api/v1/r21/approval-gates/gate-release/decisions",
            headers=_actor_headers(),
            json={
                "execution": execution,
                "decision": "approve",
                "actor_role": role,
                "actor_id": role,
                "persist": False,
            },
        )
        assert approval_response.status_code == 200
        execution = approval_response.json()["execution"]

    resume_response = client.post(
        f"/api/v1/r21/projects/crm-v1/executions/{execution['execution_id']}/resume",
        headers=_actor_headers(),
        json={"execution": execution, "persist": False},
    )
    assert resume_response.status_code == 200
    completed = resume_response.json()["execution"]
    assert completed["project_state"] == "COMPLETED"

    recovery_response = client.post(
        "/api/v1/r21/executions/recover",
        headers=_actor_headers(),
        json={"checkpoint": completed["checkpoints"][-1]},
    )
    assert recovery_response.status_code == 200
    assert recovery_response.json()["recovery"]["project_state"] == "COMPLETED"


class R21PersistenceSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.audit_records: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)

    def add_all(self, values: list[object]) -> None:
        self.added.extend(values)
        if len(values) == 2 and values[1].__class__.__name__ == "AuditChainRecordModel":
            self.audit_records.append(values[1])

    async def scalar(self, _statement: object) -> object | None:
        return self.audit_records[-1] if self.audit_records else None

    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_r21_persistence_service_records_db_rows_audit_and_metrics() -> None:
    manifest, compilation, plan = _compiled_plan()
    execution = r21_start_execution(plan)
    session = R21PersistenceSession()
    before = metrics_snapshot()

    service = R21PersistenceService(session)  # type: ignore[arg-type]
    await service.record_compilation(compilation, actor_type="human", actor_id="operator")
    await service.record_plan(plan, actor_type="human", actor_id="operator")
    await service.record_execution(
        execution,
        actor_type="human",
        actor_id="operator",
        action="started",
    )

    assert any(isinstance(item, R21ProjectCompilationModel) for item in session.added)
    assert any(isinstance(item, R21ExecutionPlanModel) for item in session.added)
    assert any(isinstance(item, R21ExecutionModel) for item in session.added)
    assert any(isinstance(item, R21ExecutionCheckpointModel) for item in session.added)
    assert any(isinstance(item, R21WorkPackageRecordModel) for item in session.added)
    assert any(isinstance(item, R21ExecutionEventRecordModel) for item in session.added)
    event_types = {
        item.event_type for item in session.added if item.__class__.__name__ == "AuditEventModel"
    }
    assert {
        "r21.project.compiled",
        "r21.execution_plan.created",
        "r21.execution.started",
    } <= event_types
    after = metrics_snapshot()
    assert (
        after["r21_project_compilations_total"]
        >= before.get("r21_project_compilations_total", 0) + 1
    )
    assert (
        after["r21_execution_plans_created_total"]
        >= before.get("r21_execution_plans_created_total", 0) + 1
    )
    assert after["executions_started_total"] >= before.get("executions_started_total", 0) + 1
    assert manifest["metadata"]["id"] == compilation.project_id
