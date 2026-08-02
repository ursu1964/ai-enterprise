import io
import json
import tarfile
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.routes.audit import export as export_audit
from ai_enterprise.application.audit.writer import AuditWriter
from ai_enterprise.domain.audit.exceptions import InvalidAuditCursorError
from ai_enterprise.domain.audit.policies import AuditCursor, sanitize_payload
from ai_enterprise.infrastructure.audit.audit_exporter import AuditExporter
from ai_enterprise.infrastructure.audit.event_hasher import (
    canonical_chain_record_hash,
    canonical_event_hash,
    verify_chain_records,
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


def test_chain_record_hash_detects_payload_and_link_tampering() -> None:
    first = {
        "stream_id": "project:1",
        "sequence": 1,
        "previous_hash": None,
        "payload": {"status": "created"},
    }
    first["record_hash"] = canonical_chain_record_hash(**first)
    second = {
        "stream_id": "project:1",
        "sequence": 2,
        "previous_hash": first["record_hash"],
        "payload": {"status": "approved"},
    }
    second["record_hash"] = canonical_chain_record_hash(**second)
    assert verify_chain_records([first, second]) == []

    second["payload"]["status"] = "rejected"
    assert verify_chain_records([first, second])[0]["reason"] == "record_hash_mismatch"

    second["payload"]["status"] = "approved"
    second["previous_hash"] = "0" * 64
    assert verify_chain_records([first, second])[0]["reason"] == "previous_hash_mismatch"


@pytest.mark.asyncio
async def test_audit_writer_appends_read_event_and_chain_record() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.records = []
            self.added = []

        async def scalar(self, _statement: object) -> object | None:
            return self.records[-1] if self.records else None

        def add_all(self, values: list[object]) -> None:
            self.added.extend(values)
            self.records.append(values[1])

        async def flush(self) -> None:
            return None

    project_id = uuid4()
    session = FakeSession()
    first = await AuditWriter(session).append_project_event(
        project_id=project_id,
        event_type="project.created",
        actor_type="human",
        actor_id="alice",
        payload={"name": "Platform hardening"},
    )
    second = await AuditWriter(session).append_project_event(
        project_id=project_id,
        event_type="project.approved",
        actor_type="system",
        actor_id="approval-policy",
        payload={"mode": "manual"},
    )

    assert first.event.payload["audit_chain"]["sequence"] == 1
    assert second.event.payload["audit_chain"]["sequence"] == 2
    assert second.chain_record.previous_hash == first.chain_record.record_hash
    assert verify_chain_records([
        {
            "stream_id": item.stream_id,
            "sequence": item.sequence,
            "previous_hash": item.previous_hash,
            "record_hash": item.record_hash,
            "payload": item.payload,
        }
        for item in session.records
    ]) == []


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
