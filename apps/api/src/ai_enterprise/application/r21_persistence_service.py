from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.audit.writer import AuditWriter
from ai_enterprise.application.r21_execution_orchestrator_runtime import (
    R21Execution,
    R21ExecutionPlan,
    R21ProjectCompilation,
)
from ai_enterprise.infrastructure.r21.models import (
    R21ApprovalDecisionRecordModel,
    R21ApprovalGateRecordModel,
    R21EvidenceRecordModel,
    R21ExecutionCheckpointModel,
    R21ExecutionEventRecordModel,
    R21ExecutionModel,
    R21ExecutionPlanModel,
    R21IdempotencyRecordModel,
    R21ProjectCompilationModel,
    R21WorkPackageRecordModel,
)
from ai_enterprise.observability import increment_metric


class R21PersistenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_compilation(
        self,
        compilation: R21ProjectCompilation,
        *,
        actor_type: str,
        actor_id: str,
    ) -> None:
        self.session.add(
            R21ProjectCompilationModel(
                project_key=compilation.project_id,
                compilation_id=compilation.compilation_id,
                manifest_hash=compilation.manifest_hash,
                manifest_version=compilation.manifest_version,
                status=compilation.status,
                compilation_hash=compilation.compilation_hash,
                document=compilation.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
        increment_metric("r21_project_compilations_total")
        await self._audit(
            "r21.project.compiled",
            compilation.project_id,
            actor_type,
            actor_id,
            {
                "compilation_id": compilation.compilation_id,
                "status": compilation.status,
                "compilation_hash": compilation.compilation_hash,
            },
        )

    async def record_plan(
        self,
        plan: R21ExecutionPlan,
        *,
        actor_type: str,
        actor_id: str,
    ) -> None:
        self.session.add(
            R21ExecutionPlanModel(
                project_key=plan.project_id,
                execution_plan_id=plan.execution_plan_id,
                manifest_hash=plan.manifest_hash,
                manifest_version=plan.manifest_version,
                plan_hash=plan.plan_hash,
                document=plan.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
        increment_metric("r21_execution_plans_created_total")
        await self._audit(
            "r21.execution_plan.created",
            plan.project_id,
            actor_type,
            actor_id,
            {"execution_plan_id": plan.execution_plan_id, "plan_hash": plan.plan_hash},
        )

    async def record_execution(
        self,
        execution: R21Execution,
        *,
        actor_type: str,
        actor_id: str,
        action: str,
    ) -> None:
        self.session.add(
            R21ExecutionModel(
                project_key=execution.project_id,
                execution_id=execution.execution_id,
                execution_plan_id=execution.execution_plan_id,
                project_state=execution.project_state,
                execution_hash=execution.execution_hash,
                document=execution.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
        self.session.add_all(_execution_projection_rows(execution, actor_id))
        _increment_execution_metrics(execution, action)
        await self._audit(
            f"r21.execution.{action}",
            execution.project_id,
            actor_type,
            actor_id,
            {
                "execution_id": execution.execution_id,
                "execution_plan_id": execution.execution_plan_id,
                "project_state": execution.project_state,
                "execution_hash": execution.execution_hash,
                "event_count": len(execution.events),
                "checkpoint_count": len(execution.checkpoints),
            },
        )

    async def record_recovery(
        self,
        *,
        project_key: str,
        execution_id: str,
        actor_type: str,
        actor_id: str,
        payload: dict[str, Any],
    ) -> None:
        increment_metric("r21_execution_recovery_total")
        await self._audit(
            "r21.execution.recovery_requested",
            project_key,
            actor_type,
            actor_id,
            {"execution_id": execution_id, "recovery": payload},
        )

    async def flush(self) -> None:
        await self.session.flush()

    async def _audit(
        self,
        event_type: str,
        project_key: str,
        actor_type: str,
        actor_id: str,
        payload: dict[str, Any],
    ) -> None:
        await AuditWriter(self.session).append_event(
            stream_id=f"r21:{project_key}",
            project_id=None,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            payload={"project_key": project_key, **payload},
        )


def _execution_projection_rows(execution: R21Execution, actor_id: str) -> list[object]:
    rows: list[object] = []
    for checkpoint in execution.checkpoints:
        rows.append(
            R21ExecutionCheckpointModel(
                project_key=execution.project_id,
                execution_id=execution.execution_id,
                checkpoint_id=checkpoint.checkpoint_id,
                project_state=checkpoint.project_state,
                checkpoint_hash=checkpoint.checkpoint_hash,
                document=checkpoint.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
    for work_package in execution.work_package_states:
        rows.append(
            R21WorkPackageRecordModel(
                project_key=execution.project_id,
                execution_id=execution.execution_id,
                work_package_id=work_package.work_package_id,
                state=work_package.state,
                state_hash=work_package.state_hash,
                document=work_package.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
    for gate in execution.approval_gates:
        rows.append(
            R21ApprovalGateRecordModel(
                project_key=execution.project_id,
                execution_id=execution.execution_id,
                gate_id=gate.gate_id,
                status=gate.status,
                gate_hash=gate.gate_hash,
                document=gate.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
        for decision in gate.decisions:
            rows.append(
                R21ApprovalDecisionRecordModel(
                    project_key=execution.project_id,
                    execution_id=execution.execution_id,
                    gate_id=gate.gate_id,
                    decision_id=decision.decision_id,
                    actor_role=decision.actor_role,
                    decision_hash=decision.decision_hash,
                    document=decision.model_dump(mode="json"),
                    created_by=actor_id,
                )
            )
    for event in execution.events:
        rows.append(
            R21ExecutionEventRecordModel(
                project_key=execution.project_id,
                execution_id=execution.execution_id,
                event_id=event.event_id,
                event_type=event.event_type,
                checksum=event.checksum,
                document=event.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
    for evidence in execution.evidence:
        rows.append(
            R21EvidenceRecordModel(
                project_key=execution.project_id,
                execution_id=execution.execution_id,
                evidence_id=evidence.evidence_id,
                entity_type=evidence.entity_type,
                entity_id=evidence.entity_id,
                evidence_type=evidence.evidence_type,
                evidence_hash=evidence.evidence_hash,
                document=evidence.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
    for request in execution.worker_requests:
        rows.append(
            R21IdempotencyRecordModel(
                project_key=execution.project_id,
                execution_id=execution.execution_id,
                scope="worker_request",
                idempotency_key=f"{execution.execution_id}:{request.work_package_id}:{request.request_id}",
                status="completed",
                document=request.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
    return rows


def _increment_execution_metrics(execution: R21Execution, action: str) -> None:
    increment_metric(f"r21_executions_{action}_total")
    if action == "started":
        increment_metric("executions_started_total")
    if execution.project_state == "COMPLETED":
        increment_metric("executions_completed_total")
    if execution.project_state == "FAILED":
        increment_metric("executions_failed_total")
    if execution.project_state == "PAUSED":
        increment_metric("executions_paused_total")
    if any(item.event_type == "policy.violation.detected" for item in execution.events):
        increment_metric("policy_violation_total")
    increment_metric("checkpoint_creation_total", len(execution.checkpoints))
    increment_metric("work_package_retry_total", len(execution.retries))
