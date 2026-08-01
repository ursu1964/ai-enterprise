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


def test_execution_idempotency_key_uses_public_contract() -> None:
    request = RequestExecutionRequest(
        idempotency_key="execution:request-1"
    )

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
