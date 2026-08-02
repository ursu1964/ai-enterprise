from uuid import uuid4

import pytest

from ai_enterprise.application.review.service import ReviewCandidatePatchService
from ai_enterprise.config import Settings
from ai_enterprise.infrastructure.audit.event_hasher import verify_chain_records
from ai_enterprise.infrastructure.database.foundation_models import AuditChainRecordModel
from ai_enterprise.infrastructure.database.models import AuditEventModel


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


@pytest.mark.asyncio
async def test_review_audit_events_write_tamper_evident_chain() -> None:
    session = WriteSession()
    service = ReviewCandidatePatchService(
        session=session,  # type: ignore[arg-type]
        settings=Settings(),
    )
    project_id = uuid4()
    review_id = uuid4()

    await service._append_audit_event(
        project_id=project_id,
        event_type="patch_review.requested",
        actor_type="human",
        actor_id="operator",
        payload={
            "review_id": str(review_id),
            "execution_run_id": str(uuid4()),
            "work_package_id": str(uuid4()),
            "patch_artifact_id": str(uuid4()),
            "job_id": str(uuid4()),
        },
    )

    audit_event = next(row for row in session.added if isinstance(row, AuditEventModel))
    chain_record = next(row for row in session.added if isinstance(row, AuditChainRecordModel))

    assert audit_event.event_type == "patch_review.requested"
    assert audit_event.payload["audit_chain"]["record_hash"] == chain_record.record_hash
    assert chain_record.stream_id == f"project:{project_id}"
    assert chain_record.payload["payload"]["review_id"] == str(review_id)
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
