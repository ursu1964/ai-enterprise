from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from ai_enterprise.domain.audit.exceptions import InvalidAuditCursorError

_REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = {
    "access_token", "refresh_token", "authorization", "cookie", "password",
    "secret", "private_key", "environment", "env", "stdout", "stderr",
    "source_code",
}


@dataclass(frozen=True, slots=True)
class AuditCursor:
    occurred_at: datetime
    sequence: int
    event_id: UUID

    def encode(self) -> str:
        raw = json.dumps(
            [self.occurred_at.isoformat(), self.sequence, str(self.event_id)],
            separators=(",", ":"),
        ).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @classmethod
    def decode(cls, value: str) -> AuditCursor:
        try:
            padded = value + "=" * (-len(value) % 4)
            timestamp, sequence, event_id = json.loads(
                base64.urlsafe_b64decode(padded).decode()
            )
            return cls(datetime.fromisoformat(timestamp), int(sequence), UUID(event_id))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise InvalidAuditCursorError("Invalid audit cursor") from exc


def sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _REDACTED
            if str(key).lower() in _SENSITIVE_KEYS
            else sanitize_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    return value
