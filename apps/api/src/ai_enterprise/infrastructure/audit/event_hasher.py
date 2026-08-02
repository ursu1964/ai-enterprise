import hashlib
import json
from typing import Any

from ai_enterprise.domain.hashing import hash_json


def canonical_event_hash(event: dict[str, Any], previous_hash: str | None = None) -> str:
    envelope = {"previous_hash": previous_hash, "event": event}
    encoded = json.dumps(
        envelope, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def canonical_chain_record_hash(
    *, stream_id: str, sequence: int, previous_hash: str | None, payload: dict[str, Any]
) -> str:
    return hash_json(
        {
            "stream_id": stream_id,
            "sequence": sequence,
            "previous_hash": previous_hash,
            "payload": payload,
        }
    )


def verify_chain_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    previous_hash: str | None = None
    for expected_sequence, record in enumerate(records, start=1):
        sequence = int(record.get("sequence", expected_sequence))
        stored = record.get("record_hash")
        stream_id = str(record.get("stream_id", ""))
        previous = record.get("previous_hash")
        payload = record.get("payload")
        if not stored:
            failures.append({"sequence": sequence, "reason": "record_hash_missing"})
            continue
        if previous != previous_hash:
            failures.append(
                {
                    "sequence": sequence,
                    "expected_previous_hash": previous_hash,
                    "actual_previous_hash": previous,
                    "reason": "previous_hash_mismatch",
                }
            )
        if not isinstance(payload, dict):
            failures.append({"sequence": sequence, "reason": "payload_invalid"})
            previous_hash = stored
            continue
        actual = canonical_chain_record_hash(
            stream_id=stream_id,
            sequence=sequence,
            previous_hash=previous,
            payload=payload,
        )
        if actual != stored:
            failures.append(
                {
                    "sequence": sequence,
                    "expected_hash": stored,
                    "actual_hash": actual,
                    "reason": "record_hash_mismatch",
                }
            )
        previous_hash = stored
    return failures


def verify_hash_chain(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    previous_hash: str | None = None
    for sequence, event in enumerate(events, start=1):
        stored = event.get("event_hash")
        if not stored:
            failures.append({"sequence": sequence, "reason": "hash_missing"})
            continue
        material = {key: value for key, value in event.items() if key != "event_hash"}
        actual = canonical_event_hash(material, previous_hash)
        if actual != stored:
            failures.append(
                {"sequence": sequence, "expected_hash": stored, "actual_hash": actual,
                 "reason": "event_hash_mismatch"}
            )
        previous_hash = stored
    return failures
