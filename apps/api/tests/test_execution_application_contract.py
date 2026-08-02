from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ai_enterprise.api.schemas import RequestExecutionRequest
from ai_enterprise.application.execution_workflow import (
    ExecutionApplicationService,
)
from ai_enterprise.config import Settings
from ai_enterprise.domain.enums import WorkPackageStatus
from ai_enterprise.domain.execution.exceptions import ApprovalInvalidError
from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.infrastructure.audit.event_hasher import verify_chain_records
from ai_enterprise.infrastructure.database.foundation_models import AuditChainRecordModel
from ai_enterprise.infrastructure.database.models import AuditEventModel, ExecutionEventModel


class WriteSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.records: list[AuditChainRecordModel] = []

    async def scalar(self, statement: object) -> AuditChainRecordModel | None:
        return self.records[-1] if self.records else None

    def add(self, row: object) -> None:
        self.added.append(row)

    def add_all(self, rows: list[object]) -> None:
        self.added.extend(rows)
        self.records.extend(row for row in rows if isinstance(row, AuditChainRecordModel))

    async def flush(self) -> None:
        return None


def test_execution_idempotency_key_uses_public_contract() -> None:
    request = RequestExecutionRequest(idempotency_key="execution:request-1")

    assert request.idempotency_key == "execution:request-1"


@pytest.mark.parametrize(
    "value",
    ["too-short", "contains whitespace 123", "invalid/key/123456"],
)
def test_execution_idempotency_key_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValidationError):
        RequestExecutionRequest(idempotency_key=value)


@pytest.mark.asyncio
async def test_worker_rejects_mutated_work_package_contract() -> None:
    settings = Settings()
    service = ExecutionApplicationService(
        session=AsyncMock(),
        settings=settings,
    )
    approval_id = uuid4()
    service._get_approval = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(id=approval_id)
    )
    manifest = {"name": "test"}
    contract = {
        "command_policy": {"test_commands": [["pytest", "-q"]]},
        "file_scope": {
            "allowed_files": ["src/example.py"],
            "allowed_directories": [],
            "forbidden_files": [".env"],
            "forbidden_directories": [".git"],
        },
        "network": {"policy": "none"},
    }
    work_package = SimpleNamespace(
        id=uuid4(),
        status=WorkPackageStatus.APPROVED,
        contract=contract | {"mutated": True},
        contract_hash=hash_json(contract),
    )

    with pytest.raises(ApprovalInvalidError, match="not immutable"):
        await service._validate_execution_invariants(
            run=SimpleNamespace(
                approval_id=approval_id,
                container_image=settings.execution_image,
            ),
            project=SimpleNamespace(
                manifest=manifest,
                manifest_hash=hash_json(manifest),
            ),
            work_package=work_package,
        )


@pytest.mark.asyncio
async def test_worker_rejects_unpermitted_execution_image() -> None:
    settings = Settings()
    service = ExecutionApplicationService(
        session=AsyncMock(),
        settings=settings,
    )
    approval_id = uuid4()
    service._get_approval = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(id=approval_id)
    )
    manifest = {"name": "test"}
    contract = {
        "command_policy": {"test_commands": [["pytest", "-q"]]},
        "file_scope": {
            "allowed_files": ["src/example.py"],
            "allowed_directories": [],
            "forbidden_files": [".env"],
            "forbidden_directories": [".git"],
        },
        "network": {"policy": "none"},
    }

    with pytest.raises(ApprovalInvalidError, match="not permitted"):
        await service._validate_execution_invariants(
            run=SimpleNamespace(
                approval_id=approval_id,
                container_image="unapproved-agent:latest",
            ),
            project=SimpleNamespace(
                manifest=manifest,
                manifest_hash=hash_json(manifest),
            ),
            work_package=SimpleNamespace(
                id=uuid4(),
                status=WorkPackageStatus.APPROVED,
                contract=contract,
                contract_hash=hash_json(contract),
            ),
        )


@pytest.mark.asyncio
async def test_terminal_execution_events_write_tamper_evident_audit_chain() -> None:
    session = WriteSession()
    service = ExecutionApplicationService(
        session=session,  # type: ignore[arg-type]
        settings=Settings(),
    )
    project_id = uuid4()
    run_id = uuid4()
    work_package_id = uuid4()

    await service._add_terminal_events(
        run=SimpleNamespace(
            id=run_id,
            status="failed",
            failure_code="tests_failed",
        ),
        project=SimpleNamespace(id=project_id),
        work_package=SimpleNamespace(id=work_package_id),
        event_type="execution.failed",
        test_summary={"total": 1, "passed": 0, "failed": 1, "success": False},
    )

    audit_event = next(row for row in session.added if isinstance(row, AuditEventModel))
    chain_record = next(row for row in session.added if isinstance(row, AuditChainRecordModel))
    execution_event = next(row for row in session.added if isinstance(row, ExecutionEventModel))

    assert audit_event.event_type == "execution.failed"
    assert audit_event.payload["audit_chain"]["record_hash"] == chain_record.record_hash
    assert chain_record.stream_id == f"project:{project_id}"
    assert chain_record.payload["payload"]["execution_id"] == str(run_id)
    assert execution_event.event_type == "execution.finished"
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
