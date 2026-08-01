import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class CommandEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: str = "1.0"
    command_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    command_type: str
    actor_id: str
    correlation_id: uuid.UUID
    causation_id: uuid.UUID | None = None
    payload: dict[str, Any]
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EventEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: str = "1.0"
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: str
    aggregate_type: str
    aggregate_id: uuid.UUID
    correlation_id: uuid.UUID
    causation_id: uuid.UUID
    payload: dict[str, Any]
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SignatureProvider(Protocol):
    @property
    def key_id(self) -> str: ...
    def sign(self, digest: bytes) -> str: ...
    def verify(self, digest: bytes, signature: str) -> bool: ...
