from enum import StrEnum


class ExecutionStatus(StrEnum):
    PENDING = "pending"
    PREPARING = "preparing"
    RUNNING = "running"
    VALIDATING = "validating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class TestStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    SKIPPED = "skipped"
