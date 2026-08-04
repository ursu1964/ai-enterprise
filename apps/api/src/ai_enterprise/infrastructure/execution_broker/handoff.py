from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from ai_enterprise.infrastructure.execution_broker.evidence import StoredTerminalEvidence


class BrokerEvidenceHandoffError(RuntimeError):
    pass


class BrokerVolumeGateway(Protocol):
    def exists(self, volume_name: str) -> bool: ...

    def remove(self, volume_name: str) -> None: ...


class BrokerEvidenceStore(Protocol):
    def pending_handoff(self) -> tuple[StoredTerminalEvidence, ...]: ...

    def mark_handoff_started(self, evidence_ref: uuid.UUID) -> StoredTerminalEvidence: ...

    def mark_handoff_completed(self, evidence_ref: uuid.UUID) -> StoredTerminalEvidence: ...


@dataclass(frozen=True, slots=True)
class BrokerEvidenceHandoffResult:
    evidence_ref: uuid.UUID
    removed_volumes: tuple[str, ...]


class TerminalEvidenceHandoffReplayer:
    def __init__(
        self, *, evidence_store: BrokerEvidenceStore, volume_gateway: BrokerVolumeGateway
    ) -> None:
        self._evidence_store = evidence_store
        self._volume_gateway = volume_gateway

    def replay_pending(self) -> tuple[BrokerEvidenceHandoffResult, ...]:
        completed: list[BrokerEvidenceHandoffResult] = []
        for evidence in self._evidence_store.pending_handoff():
            completed.append(self._handoff(evidence))
        return tuple(completed)

    def _handoff(self, evidence: StoredTerminalEvidence) -> BrokerEvidenceHandoffResult:
        if evidence.state == "retained":
            missing = [
                volume_name
                for volume_name in evidence.retained_volumes.values()
                if not self._volume_gateway.exists(volume_name)
            ]
            if missing:
                raise BrokerEvidenceHandoffError(
                    "retained terminal evidence volume is unavailable"
                )
            evidence = self._evidence_store.mark_handoff_started(evidence.evidence_ref)
        volume_names = tuple(
            evidence.retained_volumes[purpose] for purpose in ("workspace", "output")
        )
        removed: list[str] = []
        for volume_name in volume_names:
            if self._volume_gateway.exists(volume_name):
                self._volume_gateway.remove(volume_name)
                removed.append(volume_name)
        self._evidence_store.mark_handoff_completed(evidence.evidence_ref)
        return BrokerEvidenceHandoffResult(
            evidence_ref=evidence.evidence_ref,
            removed_volumes=tuple(removed),
        )


class DockerVolumeGateway:
    def __init__(self, client: object) -> None:
        self._client = client

    def exists(self, volume_name: str) -> bool:
        try:
            self._client.volumes.get(volume_name)  # type: ignore[attr-defined]
        except Exception:
            return False
        return True

    def remove(self, volume_name: str) -> None:
        volume = self._client.volumes.get(volume_name)  # type: ignore[attr-defined]
        volume.remove(force=True)
