from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from ai_enterprise.domain.hashing import canonical_json
from ai_enterprise.infrastructure.execution_broker.engine import BrokerEngineResult
from ai_enterprise.infrastructure.execution_broker.policy import BrokerRunRequest

TerminalEvidenceState = Literal["retained", "handoff_started", "handoff_completed"]


class TerminalEvidenceStoreError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StoredTerminalEvidence:
    evidence_ref: uuid.UUID
    workload_id: uuid.UUID
    correlation_id: uuid.UUID
    kind: str
    runtime_instance_id: str
    image_id: str
    exit_code: int
    retained_volumes: dict[str, str]
    output_archive_sha256: str
    workspace_archive_sha256: str
    runtime_log_sha256: str
    manifest_sha256: str
    state: TerminalEvidenceState
    captured_at: datetime


@dataclass(frozen=True, slots=True)
class TerminalEvidenceReconciliation:
    retained_records: int
    started_records: int
    completed_records: int


class TerminalEvidenceStore:
    def __init__(self, root: Path) -> None:
        if root.is_symlink():
            raise ValueError("terminal evidence root cannot be a symbolic link")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.chmod(0o700)
        self._root = root.resolve()
        self._database = self._root / "terminal-evidence.sqlite3"
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS terminal_evidence ("
                "evidence_ref TEXT PRIMARY KEY, "
                "workload_id TEXT NOT NULL, "
                "correlation_id TEXT NOT NULL, "
                "kind TEXT NOT NULL, "
                "runtime_instance_id TEXT NOT NULL, "
                "image_id TEXT NOT NULL, "
                "exit_code INTEGER NOT NULL, "
                "retained_volumes_json TEXT NOT NULL, "
                "output_archive_sha256 TEXT NOT NULL, "
                "workspace_archive_sha256 TEXT NOT NULL, "
                "runtime_log_sha256 TEXT NOT NULL, "
                "manifest_sha256 TEXT NOT NULL, "
                "state TEXT NOT NULL, "
                "captured_at TEXT NOT NULL)"
            )
        self._database.chmod(0o600)
        self.reconciliation = self._reconcile()

    def record(
        self, request: BrokerRunRequest, result: BrokerEngineResult
    ) -> StoredTerminalEvidence:
        retained = _validate_retained_volumes(result.retained_evidence_volumes)
        captured_at = datetime.now(UTC)
        evidence_ref = uuid.uuid4()
        output_archive_sha256 = _sha256_bytes(result.output_archive)
        workspace_archive_sha256 = _sha256_bytes(result.workspace_archive)
        runtime_log_sha256 = _sha256_bytes(result.runtime_log.encode())
        manifest = {
            "schema_version": 1,
            "evidence_ref": str(evidence_ref),
            "workload_id": str(request.workload_id),
            "correlation_id": str(request.correlation_id),
            "kind": request.kind,
            "runtime_instance_id": result.runtime_instance_id,
            "image_id": result.image_id,
            "exit_code": result.exit_code,
            "retained_volumes": retained,
            "output_archive_sha256": output_archive_sha256,
            "workspace_archive_sha256": workspace_archive_sha256,
            "runtime_log_sha256": runtime_log_sha256,
            "captured_at": captured_at.isoformat(),
        }
        manifest_sha256 = _sha256_bytes(canonical_json(manifest).encode())
        stored = StoredTerminalEvidence(
            evidence_ref=evidence_ref,
            workload_id=request.workload_id,
            correlation_id=request.correlation_id,
            kind=request.kind,
            runtime_instance_id=result.runtime_instance_id,
            image_id=result.image_id,
            exit_code=result.exit_code,
            retained_volumes=retained,
            output_archive_sha256=output_archive_sha256,
            workspace_archive_sha256=workspace_archive_sha256,
            runtime_log_sha256=runtime_log_sha256,
            manifest_sha256=manifest_sha256,
            state="retained",
            captured_at=captured_at,
        )
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO terminal_evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(stored.evidence_ref),
                    str(stored.workload_id),
                    str(stored.correlation_id),
                    stored.kind,
                    stored.runtime_instance_id,
                    stored.image_id,
                    stored.exit_code,
                    json.dumps(retained, sort_keys=True, separators=(",", ":")),
                    stored.output_archive_sha256,
                    stored.workspace_archive_sha256,
                    stored.runtime_log_sha256,
                    stored.manifest_sha256,
                    stored.state,
                    stored.captured_at.isoformat(),
                ),
            )
        _fsync_file(self._database)
        _fsync_directory(self._root)
        return stored

    def pending_handoff(self) -> tuple[StoredTerminalEvidence, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM terminal_evidence "
                "WHERE state IN (?, ?) ORDER BY captured_at, evidence_ref",
                ("retained", "handoff_started"),
            ).fetchall()
        return tuple(_row_to_evidence(row) for row in rows)

    def mark_handoff_started(self, evidence_ref: uuid.UUID) -> StoredTerminalEvidence:
        with self._connect() as connection:
            updated = connection.execute(
                "UPDATE terminal_evidence SET state = ? WHERE evidence_ref = ? AND state = ?",
                ("handoff_started", str(evidence_ref), "retained"),
            ).rowcount
        if updated != 1:
            existing = self.get(evidence_ref)
            if existing.state == "handoff_started":
                return existing
            raise KeyError("terminal evidence record is unavailable for handoff")
        _fsync_file(self._database)
        _fsync_directory(self._root)
        return self.get(evidence_ref)

    def mark_handoff_completed(self, evidence_ref: uuid.UUID) -> StoredTerminalEvidence:
        with self._connect() as connection:
            updated = connection.execute(
                "UPDATE terminal_evidence SET state = ? "
                "WHERE evidence_ref = ? AND state IN (?, ?)",
                (
                    "handoff_completed",
                    str(evidence_ref),
                    "retained",
                    "handoff_started",
                ),
            ).rowcount
        if updated != 1:
            raise KeyError("terminal evidence record is unavailable for handoff")
        _fsync_file(self._database)
        _fsync_directory(self._root)
        return self.get(evidence_ref)

    def get(self, evidence_ref: uuid.UUID) -> StoredTerminalEvidence:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM terminal_evidence WHERE evidence_ref = ?",
                (str(evidence_ref),),
            ).fetchone()
        if row is None:
            raise KeyError("terminal evidence record is unavailable")
        return _row_to_evidence(row)

    def _list_by_state(
        self, state: TerminalEvidenceState
    ) -> tuple[StoredTerminalEvidence, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM terminal_evidence "
                "WHERE state = ? ORDER BY captured_at, evidence_ref",
                (state,),
            ).fetchall()
        return tuple(_row_to_evidence(row) for row in rows)

    def _connect(self) -> sqlite3.Connection:
        descriptor = os.open(
            self._database,
            os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            connection = sqlite3.connect(f"/proc/self/fd/{descriptor}")
            connection.execute("PRAGMA synchronous = FULL")
            return connection
        finally:
            os.close(descriptor)

    def _reconcile(self) -> TerminalEvidenceReconciliation:
        with self._connect() as connection:
            integrity = connection.execute("PRAGMA quick_check").fetchone()
            if integrity != ("ok",):
                raise TerminalEvidenceStoreError("terminal evidence database is corrupt")
            rows = connection.execute("SELECT * FROM terminal_evidence").fetchall()
        retained = 0
        started = 0
        completed = 0
        for row in rows:
            evidence = _row_to_evidence(row)
            if evidence.state == "retained":
                retained += 1
            elif evidence.state == "handoff_started":
                started += 1
            else:
                completed += 1
        return TerminalEvidenceReconciliation(
            retained_records=retained,
            started_records=started,
            completed_records=completed,
        )


def _row_to_evidence(row: tuple[Any, ...]) -> StoredTerminalEvidence:
    if len(row) != 14:
        raise TerminalEvidenceStoreError("terminal evidence row is malformed")
    (
        evidence_ref,
        workload_id,
        correlation_id,
        kind,
        runtime_instance_id,
        image_id,
        exit_code,
        retained_volumes_json,
        output_archive_sha256,
        workspace_archive_sha256,
        runtime_log_sha256,
        manifest_sha256,
        state,
        captured_at,
    ) = row
    retained = _validate_retained_volumes(json.loads(str(retained_volumes_json)))
    state_value = str(state)
    if state_value not in {"retained", "handoff_started", "handoff_completed"}:
        raise TerminalEvidenceStoreError("terminal evidence row is malformed")
    hashes = (
        str(output_archive_sha256),
        str(workspace_archive_sha256),
        str(runtime_log_sha256),
        str(manifest_sha256),
    )
    if any(
        len(value) != 64 or any(character not in "0123456789abcdef" for character in value)
        for value in hashes
    ):
        raise TerminalEvidenceStoreError("terminal evidence row is malformed")
    try:
        return StoredTerminalEvidence(
            evidence_ref=uuid.UUID(str(evidence_ref)),
            workload_id=uuid.UUID(str(workload_id)),
            correlation_id=uuid.UUID(str(correlation_id)),
            kind=str(kind),
            runtime_instance_id=str(runtime_instance_id),
            image_id=str(image_id),
            exit_code=int(exit_code),
            retained_volumes=retained,
            output_archive_sha256=str(output_archive_sha256),
            workspace_archive_sha256=str(workspace_archive_sha256),
            runtime_log_sha256=str(runtime_log_sha256),
            manifest_sha256=str(manifest_sha256),
            state=cast(TerminalEvidenceState, state_value),
            captured_at=datetime.fromisoformat(str(captured_at)),
        )
    except ValueError as exc:
        raise TerminalEvidenceStoreError("terminal evidence row is malformed") from exc


def _validate_retained_volumes(value: dict[str, str]) -> dict[str, str]:
    if set(value) != {"workspace", "output"}:
        raise TerminalEvidenceStoreError("terminal evidence volumes are incomplete")
    retained: dict[str, str] = {}
    for purpose, name in value.items():
        if (
            not isinstance(name, str)
            or not name
            or len(name) > 255
            or "/" in name
            or "\x00" in name
        ):
            raise TerminalEvidenceStoreError("terminal evidence volume name is invalid")
        retained[purpose] = name
    return retained


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
