from uuid import uuid4

import pytest

from ai_enterprise.application.integration.service import ControlledIntegrationService
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
