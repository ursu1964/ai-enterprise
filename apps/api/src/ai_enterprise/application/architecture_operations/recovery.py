from collections.abc import Awaitable, Callable

from .contracts import ArchitectureInspection, ArchitectureRunSnapshot, RecoveryAction


class ArchitectureRecoveryError(RuntimeError):
    pass


class ArchitectureRecoveryPolicy:
    def inspect(self, value: ArchitectureRunSnapshot) -> ArchitectureInspection:
        if not value.artifact_checksum_valid or value.successful_attempt_count > 1:
            return ArchitectureInspection(
                value, RecoveryAction.INVESTIGATE, False, "Ambiguous or corrupted evidence"
            )
        key = (value.status, value.latest_attempt_status, value.artifact_present)
        action = {
            ("running", "succeeded", False): RecoveryAction.RECONSTRUCT_ARTIFACT,
            ("running", "succeeded", True): RecoveryAction.COMPLETE_RUN,
            ("running", "failed", False): RecoveryAction.RETRY,
            ("running", "timed_out", False): RecoveryAction.RETRY,
            ("running", "validation_failed", False): RecoveryAction.RETRY,
            ("completed", "succeeded", True): RecoveryAction.NO_ACTION,
            ("completed", "succeeded", False): RecoveryAction.INTEGRITY_INCIDENT,
            ("failed", "succeeded", False): RecoveryAction.INVESTIGATE,
            ("failed", "failed", True): RecoveryAction.INTEGRITY_INCIDENT,
            ("cancelled", None, False): RecoveryAction.NO_ACTION,
            ("cancelled", "failed", False): RecoveryAction.NO_ACTION,
        }.get(key, RecoveryAction.INVESTIGATE)
        eligible = action in {
            RecoveryAction.RECONSTRUCT_ARTIFACT,
            RecoveryAction.COMPLETE_RUN,
            RecoveryAction.RETRY,
            RecoveryAction.NO_ACTION,
        }
        return ArchitectureInspection(value, action, eligible, f"Decision table selected {action}")


class ArchitectureRecoveryService:
    """Executes only deterministic service callbacks; it never performs direct SQL."""

    def __init__(
        self,
        *,
        reconstruct: Callable[[str], Awaitable[None]],
        complete: Callable[[str], Awaitable[None]],
        retry: Callable[[str], Awaitable[None]],
    ) -> None:
        self._reconstruct = reconstruct
        self._complete = complete
        self._retry = retry
        self._policy = ArchitectureRecoveryPolicy()

    async def recover(self, snapshot: ArchitectureRunSnapshot) -> ArchitectureInspection:
        inspection = self._policy.inspect(snapshot)
        if not inspection.recovery_eligible:
            raise ArchitectureRecoveryError(inspection.reason)
        callbacks = {
            RecoveryAction.RECONSTRUCT_ARTIFACT: self._reconstruct,
            RecoveryAction.COMPLETE_RUN: self._complete,
            RecoveryAction.RETRY: self._retry,
        }
        callback = callbacks.get(inspection.recovery_action)
        if callback is not None:
            await callback(snapshot.run_id)
        return inspection
