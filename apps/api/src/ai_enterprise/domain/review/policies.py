from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai_enterprise.domain.review.enums import (
    FindingSeverity,
    ReviewDecision,
)


@dataclass(frozen=True, slots=True)
class ReviewFinding:
    rule_id: str
    category: str
    severity: FindingSeverity
    title: str
    description: str
    blocking: bool
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    evidence: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ReviewPolicy:
    reject_on_critical: bool = True
    reject_on_high_security: bool = True
    request_changes_on_high: bool = True
    request_changes_on_medium_count: int = 3
    require_all_approved_tests: bool = True
    require_patch_reproducibility: bool = True


class ReviewDecisionPolicy:
    def decide(
        self,
        *,
        findings: tuple[ReviewFinding, ...],
        approved_tests_passed: bool,
        patch_reproducible: bool,
        policy: ReviewPolicy,
    ) -> ReviewDecision:
        if policy.require_all_approved_tests and not approved_tests_passed:
            return ReviewDecision.REJECT

        if policy.require_patch_reproducibility and not patch_reproducible:
            return ReviewDecision.REJECT

        if any(finding.blocking for finding in findings):
            return ReviewDecision.REJECT

        if policy.reject_on_critical and any(
            finding.severity == FindingSeverity.CRITICAL
            for finding in findings
        ):
            return ReviewDecision.REJECT

        if policy.reject_on_high_security and any(
            finding.category == "security"
            and finding.severity == FindingSeverity.HIGH
            for finding in findings
        ):
            return ReviewDecision.REJECT

        if policy.request_changes_on_high and any(
            finding.severity == FindingSeverity.HIGH
            for finding in findings
        ):
            return ReviewDecision.CHANGES_REQUESTED

        medium_count = sum(
            finding.severity == FindingSeverity.MEDIUM
            for finding in findings
        )

        if medium_count >= policy.request_changes_on_medium_count:
            return ReviewDecision.CHANGES_REQUESTED

        return ReviewDecision.ACCEPT


@dataclass(frozen=True, slots=True)
class ReviewReport:
    schema_version: int = 1
    review_id: str = ""
    execution_run_id: str = ""
    work_package_id: str = ""
    base_commit: str = ""
    patch_sha256: str = ""
    resulting_tree_hash: str = ""
    changed_files: list[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0
    required_checks_passed: bool = False
    decision: str = ""
    summary: str = ""
    findings: list[dict[str, Any]] = field(default_factory=list)
