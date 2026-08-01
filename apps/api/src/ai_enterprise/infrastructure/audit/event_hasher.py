import hashlib
import json
from typing import Any


def canonical_event_hash(event: dict[str, Any], previous_hash: str | None = None) -> str:
    envelope = {"previous_hash": previous_hash, "event": event}
    encoded = json.dumps(
        envelope, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


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
