from uuid import uuid4

import pytest

from ai_enterprise.api.dependencies import get_actor
from ai_enterprise.domain.execution.lineage import RevisionLineagePolicy
from ai_enterprise.domain.integration.exceptions import (
    HumanApprovalRequiredError,
    TargetBranchNotAllowedError,
)
from ai_enterprise.domain.integration.policies import (
    IntegrationAuthorizationPolicy,
    PatchEligibilityPolicy,
)


def test_eligible_patch_requires_every_protected_fact() -> None:
    decision = PatchEligibilityPolicy().evaluate(
        execution_succeeded=True,
        patch_hash_present=True,
        accepted_review=True,
        review_independent=True,
        work_package_matches=True,
        base_commit_matches=True,
        base_tree_present=True,
        scope_validation_passed=True,
        required_tests_passed=True,
        unresolved_findings=False,
    )
    assert decision.eligible is True
    assert decision.failures == ()


def test_open_findings_and_failed_tests_prevent_eligibility() -> None:
    decision = PatchEligibilityPolicy().evaluate(
        execution_succeeded=True,
        patch_hash_present=True,
        accepted_review=True,
        review_independent=True,
        work_package_matches=True,
        base_commit_matches=True,
        base_tree_present=True,
        scope_validation_passed=True,
        required_tests_passed=False,
        unresolved_findings=True,
    )
    assert decision.eligible is False
    assert {failure.code for failure in decision.failures} == {
        "OPEN_REVIEW_FINDINGS",
        "REQUIRED_TESTS_FAILED",
    }


def test_revision_lineage_increments_and_preserves_root() -> None:
    parent_id = uuid4()
    root_id = uuid4()
    review_id = uuid4()
    lineage = RevisionLineagePolicy().derive(
        parent_id=parent_id,
        parent_root_id=root_id,
        parent_depth=2,
        source_review_id=review_id,
    )
    assert lineage.parent_attempt_id == parent_id
    assert lineage.root_attempt_id == root_id
    assert lineage.source_review_id == review_id
    assert lineage.lineage_depth == 3


def test_agent_cannot_approve_integration() -> None:
    with pytest.raises(HumanApprovalRequiredError):
        IntegrationAuthorizationPolicy().require_human(actor_type="agent")


def test_arbitrary_target_branch_is_rejected() -> None:
    with pytest.raises(TargetBranchNotAllowedError):
        IntegrationAuthorizationPolicy().require_allowed_branch(
            target_branch="attacker/branch", allowed_branches=("main",)
        )


@pytest.mark.asyncio
async def test_actor_dependency_uses_headers_not_body_identity() -> None:
    actor = await get_actor(actor_id="alice", actor_type="human", actor_role="integration_approver")
    assert actor.subject == "alice"
    assert actor.role == "integration_approver"
