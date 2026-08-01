from typing import Literal

from pydantic import Field, model_validator

from .api import _schema
from .kernel import Compatibility, StrictSpecification
from .service import DataField


class EventSpecification(StrictSpecification):
    name: str = Field(pattern=r"^[A-Z][A-Za-z0-9]+$")
    version: str = Field(pattern=r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
    producer: str
    consumers: tuple[str, ...]
    payload: tuple[DataField, ...]
    retention_days: int = Field(gt=0)
    ordering_key: str
    idempotency_key: str
    replay_policy: Literal["forbidden", "audited", "unrestricted"]

    @model_validator(mode="after")
    def validate_contract(self) -> "EventSpecification":
        names = [field.name for field in self.payload]
        if names != sorted(set(names)):
            raise ValueError("event fields must be sorted and unique")
        if self.ordering_key not in names or self.idempotency_key not in names:
            raise ValueError("ordering and idempotency keys must reference payload fields")
        if tuple(sorted(set(self.consumers))) != self.consumers:
            raise ValueError("event consumers must be unique and sorted")
        return self


def generate_event_schema(event: EventSpecification, *, spec_hash: str) -> dict[str, object]:
    payload = _schema(event.payload)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"urn:ai-enterprise:event:{event.name}:{event.version}",
        "title": event.name,
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "event_id": {"type": "string", "format": "uuid"},
            "event_type": {"const": event.name},
            "schema_version": {"const": event.version},
            "occurred_at": {"type": "string", "format": "date-time"},
            "correlation_id": {"type": "string", "format": "uuid"},
            "causation_id": {"type": ["string", "null"], "format": "uuid"},
            "organization_id": {"type": "string", "format": "uuid"},
            "payload": payload,
        },
        "required": [
            "event_id",
            "event_type",
            "schema_version",
            "occurred_at",
            "correlation_id",
            "organization_id",
            "payload",
        ],
        "x-producer": event.producer,
        "x-consumers": list(event.consumers),
        "x-retention-days": event.retention_days,
        "x-ordering-key": event.ordering_key,
        "x-idempotency-key": event.idempotency_key,
        "x-replay-policy": event.replay_policy,
        "x-spec-hash": spec_hash,
    }


def classify_event_change(old: EventSpecification, new: EventSpecification) -> Compatibility:
    old_fields, new_fields = (
        {field.name: field for field in old.payload},
        {field.name: field for field in new.payload},
    )
    if (
        old.name != new.name
        or old.producer != new.producer
        or old.ordering_key != new.ordering_key
        or old.idempotency_key != new.idempotency_key
        or old.replay_policy != new.replay_policy
        or old.retention_days != new.retention_days
        or not set(old.consumers).issubset(new.consumers)
        or not set(old_fields).issubset(new_fields)
    ):
        return Compatibility.BREAKING
    if any(
        new_fields[name].type != field.type
        or new_fields[name].required != field.required
        or new_fields[name].nullable != field.nullable
        for name, field in old_fields.items()
    ):
        return Compatibility.BREAKING
    if any(field.required for name, field in new_fields.items() if name not in old_fields):
        return Compatibility.BREAKING
    return Compatibility.CONDITIONALLY_COMPATIBLE if old != new else Compatibility.COMPATIBLE
