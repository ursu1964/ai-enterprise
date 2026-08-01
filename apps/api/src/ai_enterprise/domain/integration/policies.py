from collections.abc import Iterable

from ai_enterprise.domain.integration.entities import (
    EligibilityDecision,
    EligibilityFailure,
)


class PatchEligibilityPolicy:
    POLICY_VERSION = "integration-eligibility-v1"

    def evaluate(
        self,
        *,
        execution_succeeded: bool,
        patch_hash_present: bool,
        accepted_review: bool,
        review_independent: bool,
        work_package_matches: bool,
        base_commit_matches: bool,
        base_tree_present: bool,
        scope_validation_passed: bool,
        required_tests_passed: bool,
        unresolved_findings: bool,
    ) -> EligibilityDecision:
        checks = (
            (execution_succeeded, "EXECUTION_NOT_SUCCESSFUL"),
            (patch_hash_present, "PATCH_HASH_MISSING"),
            (accepted_review, "ACCEPTED_REVIEW_MISSING"),
            (review_independent, "REVIEW_NOT_INDEPENDENT"),
            (work_package_matches, "WORK_PACKAGE_MISMATCH"),
            (base_commit_matches, "BASE_COMMIT_MISMATCH"),
            (base_tree_present, "BASE_TREE_MISSING"),
            (scope_validation_passed, "SCOPE_VALIDATION_FAILED"),
            (required_tests_passed, "REQUIRED_TESTS_FAILED"),
            (not unresolved_findings, "OPEN_REVIEW_FINDINGS"),
        )
        failures = tuple(
            EligibilityFailure(code=code, message=code.replace("_", " ").title())
            for passed, code in checks
            if not passed
        )
        return EligibilityDecision(
            eligible=not failures,
            failures=failures,
            policy_version=self.POLICY_VERSION,
        )


class IntegrationAuthorizationPolicy:
    POLICY_VERSION = "integration-approval-v1"

    def require_human(self, *, actor_type: str) -> None:
        from ai_enterprise.domain.integration.exceptions import (
            HumanApprovalRequiredError,
        )

        if actor_type != "human":
            raise HumanApprovalRequiredError("Only an authenticated human may approve integration")

    def require_allowed_branch(
        self, *, target_branch: str, allowed_branches: Iterable[str]
    ) -> None:
        from ai_enterprise.domain.integration.exceptions import (
            TargetBranchNotAllowedError,
        )

        if target_branch not in set(allowed_branches):
            raise TargetBranchNotAllowedError(f"Target branch {target_branch!r} is not allowed")
