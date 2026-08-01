from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class EligibilityFailure:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    eligible: bool
    failures: tuple[EligibilityFailure, ...]
    policy_version: str


@dataclass(frozen=True, slots=True)
class ApprovalBinding:
    execution_run_id: UUID
    patch_sha256: str
    repository_url: str
    target_branch: str
    base_commit_sha: str
    base_tree_sha: str
    test_commands_sha256: str
    policy_version: str
    approved_at: datetime
