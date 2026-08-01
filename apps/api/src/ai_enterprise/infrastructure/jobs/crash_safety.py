from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class LeaseLostError(RuntimeError):
    pass


class FailureClass(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    TEMPORARY_PROVIDER = "temporary_provider"
    VALIDATION = "validation"
    AUTHORIZATION = "authorization"
    CONFIGURATION = "configuration"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class JobExecutionContext:
    job_id: uuid.UUID
    attempt_id: uuid.UUID
    worker_id: str
    lease_token: uuid.UUID
    lease_version: int
    started_at: datetime
    deadline_at: datetime


@dataclass(frozen=True, slots=True)
class FailureDecision:
    failure_class: FailureClass
    retryable: bool
    code: str


class RetryPolicy:
    def __init__(self, *, base_seconds: int, maximum_seconds: int) -> None:
        self.base_seconds = base_seconds
        self.maximum_seconds = maximum_seconds

    def classify(self, exc: Exception) -> FailureDecision:
        name = type(exc).__name__.lower()
        message = str(exc).lower()
        if isinstance(exc, TimeoutError) or "timeout" in name:
            return FailureDecision(FailureClass.TEMPORARY_PROVIDER, True, "execution_timeout")
        if any(value in name + message for value in ("connection", "docker", "database")):
            return FailureDecision(FailureClass.INFRASTRUCTURE, True, "infrastructure_error")
        if any(value in name + message for value in ("validation", "schema", "artifact")):
            return FailureDecision(FailureClass.VALIDATION, True, "validation_error")
        if any(value in name + message for value in ("permission", "authorization", "deleted")):
            return FailureDecision(FailureClass.AUTHORIZATION, False, "authorization_error")
        if any(value in name + message for value in ("configuration", "missing model", "provider")):
            return FailureDecision(FailureClass.CONFIGURATION, False, "configuration_error")
        return FailureDecision(FailureClass.UNKNOWN, False, "unexpected_error")

    def delay(self, retry_count: int) -> timedelta:
        seconds = min(self.maximum_seconds, self.base_seconds * (2 ** max(0, retry_count - 1)))
        return timedelta(seconds=seconds)
