import io
import json
import tarfile
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.routes.audit import export as export_audit
from ai_enterprise.domain.audit.exceptions import InvalidAuditCursorError
from ai_enterprise.domain.audit.policies import AuditCursor, sanitize_payload
from ai_enterprise.infrastructure.audit.audit_exporter import AuditExporter
from ai_enterprise.infrastructure.audit.event_hasher import (
    canonical_event_hash,
    verify_hash_chain,
)


def test_cursor_round_trip_and_invalid_value() -> None:
    cursor = AuditCursor(datetime(2026, 7, 31, tzinfo=UTC), 7, uuid4())
    assert AuditCursor.decode(cursor.encode()) == cursor
    with pytest.raises(InvalidAuditCursorError):
        AuditCursor.decode("not-a-cursor")


def test_payload_redaction_is_recursive() -> None:
    payload = {
        "safe": "visible",
        "password": "hidden",
        "nested": [{"access_token": "hidden", "count": 2}],
    }
    assert sanitize_payload(payload) == {
        "safe": "visible",
        "password": "[REDACTED]",
        "nested": [{"access_token": "[REDACTED]", "count": 2}],
    }


def test_hash_chain_detects_tampering() -> None:
    first = {"id": "1", "payload": {"status": "created"}}
    first["event_hash"] = canonical_event_hash(first)
    second = {"id": "2", "payload": {"status": "approved"}}
    second["event_hash"] = canonical_event_hash(second, first["event_hash"])
    assert verify_hash_chain([first, second]) == []
    second["payload"]["status"] = "rejected"
    assert verify_hash_chain([first, second])[0]["reason"] == "event_hash_mismatch"


def test_export_contains_checksums_and_root_hash() -> None:
    files = {"summary.json": {"event_count": 3}}
    payload, root_hash = AuditExporter().build(files)
    repeated_payload, repeated_hash = AuditExporter().build(files)
    assert repeated_payload == payload
    assert repeated_hash == root_hash
    assert len(root_hash) == 64
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        names = archive.getnames()
        assert names == ["SHA256SUMS.json", "summary.json"]
        checksums_file = archive.extractfile("SHA256SUMS.json")
        assert checksums_file is not None
        checksums = json.load(checksums_file)
        assert len(checksums["summary.json"]) == 64


@pytest.mark.asyncio
async def test_audit_export_requires_project_scoped_capability() -> None:
    project_id = uuid4()
    denied = Actor(
        "auditor",
        "human",
        "auditor",
        frozenset({"audit.export"}),
        scopes=frozenset({f"project:{uuid4()}"}),
    )

    with pytest.raises(HTTPException) as exc:
        await export_audit(project_id, object(), denied)  # type: ignore[arg-type]

    assert exc.value.status_code == 403
