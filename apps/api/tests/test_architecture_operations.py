import pytest

from ai_enterprise.application.architecture_operations.contracts import (
    ArchitectureIntegrityRecord,
    ArchitectureRunSnapshot,
    RecoveryAction,
)
from ai_enterprise.application.architecture_operations.integrity import ArchitectureIntegrityScanner
from ai_enterprise.application.architecture_operations.observability import (
    ArchitectureMetric,
    ArchitectureWorkerHealth,
    record_metric,
    safe_event,
)
from ai_enterprise.application.architecture_operations.recovery import (
    ArchitectureRecoveryError,
    ArchitectureRecoveryPolicy,
    ArchitectureRecoveryService,
)
from ai_enterprise.application.architecture_operations.retention import (
    REQUIRED_BACKUP_COLLECTIONS,
    REQUIRED_RESTORE_CHECKS,
    ArchitectureRetentionPolicy,
    verify_backup_contract,
)


def snapshot(**changes: object) -> ArchitectureRunSnapshot:
    values: dict[str, object] = {
        "run_id": "run-1",
        "project_id": "project-1",
        "status": "running",
        "latest_attempt_status": "succeeded",
        "artifact_present": False,
    }
    values.update(changes)
    return ArchitectureRunSnapshot(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("value", "action", "eligible"),
    [
        (snapshot(), RecoveryAction.RECONSTRUCT_ARTIFACT, True),
        (snapshot(artifact_present=True), RecoveryAction.COMPLETE_RUN, True),
        (snapshot(latest_attempt_status="timed_out"), RecoveryAction.RETRY, True),
        (
            snapshot(status="completed", artifact_present=True),
            RecoveryAction.NO_ACTION,
            True,
        ),
        (
            snapshot(status="completed", artifact_present=False),
            RecoveryAction.INTEGRITY_INCIDENT,
            False,
        ),
        (
            snapshot(artifact_checksum_valid=False),
            RecoveryAction.INVESTIGATE,
            False,
        ),
    ],
)
def test_recovery_decision_table(
    value: ArchitectureRunSnapshot, action: RecoveryAction, eligible: bool
) -> None:
    result = ArchitectureRecoveryPolicy().inspect(value)
    assert result.recovery_action is action
    assert result.recovery_eligible is eligible


async def test_recovery_uses_exactly_one_service_callback() -> None:
    calls: list[tuple[str, str]] = []

    async def callback(name: str, run_id: str) -> None:
        calls.append((name, run_id))

    service = ArchitectureRecoveryService(
        reconstruct=lambda run_id: callback("reconstruct", run_id),
        complete=lambda run_id: callback("complete", run_id),
        retry=lambda run_id: callback("retry", run_id),
    )
    await service.recover(snapshot())
    assert calls == [("reconstruct", "run-1")]
    with pytest.raises(ArchitectureRecoveryError):
        await service.recover(snapshot(artifact_checksum_valid=False))


def test_integrity_scan_reports_all_corruption_and_cardinality_failures() -> None:
    row = ArchitectureIntegrityRecord(
        run_id="run-1",
        run_status="completed",
        attempt_statuses=("succeeded", "succeeded"),
        artifact_ids=("a1", "a2"),
        artifact_checksum_valid=False,
        review_checksum_valid=False,
        approval_checksum_valid=False,
        approval_evidence_checksum_valid=False,
        audit_chain_valid=False,
        revision_lineage_valid=False,
    )
    codes = {finding.code for finding in ArchitectureIntegrityScanner().scan((row,))}
    assert codes == {
        "MULTIPLE_AUTHORITATIVE_ARTIFACTS",
        "MULTIPLE_SUCCESSFUL_ATTEMPTS",
        "ARTIFACT_CHECKSUM_MISMATCH",
        "REVIEW_CHECKSUM_MISMATCH",
        "APPROVAL_CHECKSUM_MISMATCH",
        "APPROVAL_EVIDENCE_MISMATCH",
        "AUDIT_CHAIN_INVALID",
        "REVISION_LINEAGE_INVALID",
    }


def test_retention_and_restore_contracts_fail_closed() -> None:
    policy = ArchitectureRetentionPolicy()
    assert not policy.may_delete("artifact", evidence_retained=True, audited=True)
    assert policy.may_delete("raw_failure", evidence_retained=True, audited=True)
    assert not policy.may_delete("raw_failure", evidence_retained=False, audited=True)
    verify_backup_contract(
        set(REQUIRED_BACKUP_COLLECTIONS), {check: True for check in REQUIRED_RESTORE_CHECKS}
    )
    with pytest.raises(ValueError):
        verify_backup_contract(set(), {})


def test_observability_rejects_content_and_high_cardinality_labels() -> None:
    record_metric(ArchitectureMetric.RUNS_COMPLETED, {"status": "completed"})
    with pytest.raises(ValueError):
        record_metric(ArchitectureMetric.RUNS_COMPLETED, {"run_id": "run-1"})
    assert safe_event("architecture.completed", {"status": "completed"})["event"]
    with pytest.raises(ValueError):
        safe_event("architecture.completed", {"raw_output": "secret"})


def test_worker_health_separates_liveness_and_readiness() -> None:
    degraded = ArchitectureWorkerHealth(True, True, False, True, 3)
    assert degraded.live
    assert not degraded.ready
    assert degraded.payload()["active_leases"] == 3
