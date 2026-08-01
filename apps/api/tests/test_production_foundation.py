import uuid

import pytest
from pydantic import ValidationError

from ai_enterprise.domain.foundation import CommandEnvelope, EventEnvelope, SignatureProvider
from ai_enterprise.infrastructure.database import foundation_models  # noqa: F401
from ai_enterprise.infrastructure.database.models import Base


def test_command_and_event_envelopes_are_strict_and_correlated() -> None:
    correlation = uuid.uuid4()
    command = CommandEnvelope(
        command_type="workflow.start",
        actor_id="alice",
        correlation_id=correlation,
        payload={"project_id": str(uuid.uuid4())},
    )
    event = EventEnvelope(
        event_type="workflow.started",
        aggregate_type="workflow",
        aggregate_id=uuid.uuid4(),
        correlation_id=correlation,
        causation_id=command.command_id,
        payload={},
    )
    assert event.correlation_id == command.correlation_id
    assert event.causation_id == command.command_id
    with pytest.raises(ValidationError):
        CommandEnvelope.model_validate(command.model_dump() | {"unknown": True})


def test_foundation_tables_are_registered_in_shared_metadata() -> None:
    assert {
        "actor_identities",
        "authority_grants",
        "transactional_outbox",
        "audit_chain_records",
        "artifact_versions",
        "external_effect_ledger",
    }.issubset(Base.metadata.tables)


def test_signature_provider_is_a_port() -> None:
    class Signer:
        key_id = "test-key"

        def sign(self, digest: bytes) -> str:
            return digest.hex()

        def verify(self, digest: bytes, signature: str) -> bool:
            return self.sign(digest) == signature

    signer: SignatureProvider = Signer()
    assert signer.verify(b"record", signer.sign(b"record"))
