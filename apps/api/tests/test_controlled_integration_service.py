from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ai_enterprise.application.integration.service import ControlledIntegrationService
from ai_enterprise.domain.execution.enums import ExecutionStatus
from ai_enterprise.domain.integration.enums import IntegrationApprovalDecision, PatchStatus
from ai_enterprise.infrastructure.audit.event_hasher import verify_chain_records
from ai_enterprise.infrastructure.database.foundation_models import AuditChainRecordModel
from ai_enterprise.infrastructure.database.models import (
    AuditEventModel,
    ExecutionRunModel,
    IntegrationApprovalModel,
    IntegrationAttemptModel,
    IntegrationEligibilityModel,
    JobModel,
)


class WriteSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.records: list[AuditChainRecordModel] = []

    async def scalar(self, statement: object) -> AuditChainRecordModel | None:
        return self.records[-1] if self.records else None

    def add_all(self, rows: list[object]) -> None:
        self.added.extend(rows)
        self.records.extend(row for row in rows if isinstance(row, AuditChainRecordModel))

    async def flush(self) -> None:
        return None


class AttemptSession:
    def __init__(
        self,
        *,
        approval: IntegrationApprovalModel,
        execution: ExecutionRunModel,
        eligibility: IntegrationEligibilityModel,
        previous_attempt_number: int | None,
    ) -> None:
        self.approval = approval
        self.execution = execution
        self.eligibility = eligibility
        self.previous_attempt_number = previous_attempt_number
        self.scalar_calls = 0
        self.added: list[object] = []
        self.commit_count = 0
        self.refreshed: list[object] = []

    async def scalar(self, statement: object) -> object | None:
        self.scalar_calls += 1
        if self.scalar_calls == 1:
            return self.approval
        if self.scalar_calls == 2:
            return self.previous_attempt_number
        return None

    async def get(self, model: type, identity: object) -> object | None:
        if model is ExecutionRunModel and identity == self.execution.id:
            return self.execution
        if model is IntegrationEligibilityModel and identity == self.eligibility.id:
            return self.eligibility
        return None

    def add(self, row: object) -> None:
        self.added.append(row)

    def add_all(self, rows: list[object]) -> None:
        self.added.extend(rows)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commit_count += 1

    async def refresh(self, row: object) -> None:
        self.refreshed.append(row)


@pytest.mark.asyncio
async def test_integration_audit_events_write_tamper_evident_chain() -> None:
    session = WriteSession()
    service = ControlledIntegrationService(session)  # type: ignore[arg-type]
    project_id = uuid4()
    attempt_id = uuid4()

    await service._append_audit_event(
        project_id=project_id,
        event_type="integration.attempt_created",
        actor_type="system",
        actor_id="control-plane",
        payload={
            "attempt_id": str(attempt_id),
            "approval_id": str(uuid4()),
            "correlation_id": str(uuid4()),
        },
    )

    audit_event = next(row for row in session.added if isinstance(row, AuditEventModel))
    chain_record = next(row for row in session.added if isinstance(row, AuditChainRecordModel))

    assert audit_event.event_type == "integration.attempt_created"
    assert audit_event.payload["audit_chain"]["record_hash"] == chain_record.record_hash
    assert chain_record.stream_id == f"project:{project_id}"
    assert chain_record.payload["payload"]["attempt_id"] == str(attempt_id)
    assert (
        verify_chain_records(
            [
                {
                    "stream_id": chain_record.stream_id,
                    "sequence": chain_record.sequence,
                    "previous_hash": chain_record.previous_hash,
                    "record_hash": chain_record.record_hash,
                    "payload": chain_record.payload,
                }
            ]
        )
        == []
    )


@pytest.mark.asyncio
async def test_integration_attempt_number_increments_for_recreated_attempt() -> None:
    project_id = uuid4()
    execution = ExecutionRunModel(
        id=uuid4(),
        project_id=project_id,
        work_package_id=uuid4(),
        approval_id=uuid4(),
        status=ExecutionStatus.SUCCEEDED,
        base_commit="b" * 40,
        base_tree_sha="c" * 40,
        patch_status=PatchStatus.INTEGRATION_APPROVED,
        container_image="python:3.12",
        container_image_digest=None,
        implementation_exit_code=0,
        failure_code=None,
        failure_message=None,
        started_at=None,
        finished_at=None,
        timeout_seconds=300,
        cpu_limit=1.0,
        memory_limit_bytes=536870912,
        pids_limit=128,
        network_disabled=True,
        runtime_policy={},
        changed_files=[],
        changed_file_count=0,
        insertions=0,
        deletions=0,
        patch_artifact_id=uuid4(),
        log_artifact_id=None,
        patch_sha256="a" * 64,
        idempotency_key="integration-retry",
    )
    eligibility = IntegrationEligibilityModel(
        id=uuid4(),
        execution_run_id=execution.id,
        eligible=True,
        evaluated_at=datetime.now(UTC),
        policy_version="integration-eligibility-v1",
        patch_sha256=execution.patch_sha256,
        base_commit_sha=execution.base_commit,
        base_tree_sha=execution.base_tree_sha or "",
        accepted_review_id=uuid4(),
        failure_reasons=[],
        evidence={},
    )
    approval = IntegrationApprovalModel(
        id=uuid4(),
        execution_run_id=execution.id,
        eligibility_id=eligibility.id,
        approver_subject="approver",
        approver_role="integration_approver",
        project_id=project_id,
        repository_url="git@github.com:example/project.git",
        target_branch="main",
        approved_patch_sha256=execution.patch_sha256 or "",
        approved_base_commit_sha=execution.base_commit,
        approved_base_tree_sha=execution.base_tree_sha or "",
        approved_test_commands=[],
        approved_test_commands_sha256="d" * 64,
        decision=IntegrationApprovalDecision.APPROVED,
        reason="Retry after infrastructure failure.",
        policy_version="integration-authorization-v1",
        approved_at=None,
    )
    session = AttemptSession(
        approval=approval,
        execution=execution,
        eligibility=eligibility,
        previous_attempt_number=1,
    )

    attempt = await ControlledIntegrationService(session).create_attempt(approval.id)  # type: ignore[arg-type]

    assert attempt.attempt_number == 2
    assert approval.decision == IntegrationApprovalDecision.CONSUMED
    assert execution.patch_status == PatchStatus.INTEGRATING
    assert any(isinstance(row, IntegrationAttemptModel) for row in session.added)
    assert any(isinstance(row, JobModel) for row in session.added)
    assert any(
        isinstance(row, AuditEventModel)
        and row.payload["attempt_id"] == str(attempt.id)
        for row in session.added
    )
    assert session.commit_count == 1
    assert session.refreshed == [attempt]
