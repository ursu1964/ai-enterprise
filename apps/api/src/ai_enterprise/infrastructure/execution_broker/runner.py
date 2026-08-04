from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from ai_enterprise.infrastructure.execution_broker.engine import (
    BrokerEngineError,
    BrokerEngineResult,
)
from ai_enterprise.infrastructure.execution_broker.evidence import (
    StoredTerminalEvidence,
    TerminalEvidenceStoreError,
)
from ai_enterprise.infrastructure.execution_broker.policy import BrokerRunRequest
from ai_enterprise.infrastructure.execution_broker.store import SnapshotHandle


class BrokerRunPersistenceError(RuntimeError):
    pass


class BrokerSnapshotResolver(Protocol):
    def resolve(self, snapshot_ref: uuid.UUID, *, owner_worker_id: str) -> SnapshotHandle: ...


class BrokerEngine(Protocol):
    def run(
        self,
        request: BrokerRunRequest,
        *,
        snapshot: SnapshotHandle,
        runtime_input: dict[str, Any],
    ) -> BrokerEngineResult: ...


class BrokerTerminalEvidenceRecorder(Protocol):
    def record(
        self, request: BrokerRunRequest, result: BrokerEngineResult
    ) -> StoredTerminalEvidence: ...


@dataclass(frozen=True, slots=True)
class DurableBrokerRunReceipt:
    result: BrokerEngineResult
    evidence: StoredTerminalEvidence


class DurableBrokerRunner:
    def __init__(
        self,
        *,
        snapshot_store: BrokerSnapshotResolver,
        engine: BrokerEngine,
        evidence_store: BrokerTerminalEvidenceRecorder,
    ) -> None:
        self._snapshot_store = snapshot_store
        self._engine = engine
        self._evidence_store = evidence_store

    def run(
        self,
        request: BrokerRunRequest,
        *,
        owner_worker_id: str,
        runtime_input: dict[str, Any],
    ) -> DurableBrokerRunReceipt:
        snapshot = self._snapshot_store.resolve(
            request.snapshot_ref, owner_worker_id=owner_worker_id
        )
        try:
            result = self._engine.run(request, snapshot=snapshot, runtime_input=runtime_input)
        except BrokerEngineError:
            raise
        try:
            evidence = self._evidence_store.record(request, result)
        except (TerminalEvidenceStoreError, OSError, sqlite3.Error, ValueError) as exc:
            raise BrokerRunPersistenceError(
                "terminal broker run could not be acknowledged because evidence was not durable"
            ) from exc
        return DurableBrokerRunReceipt(result=result, evidence=evidence)
