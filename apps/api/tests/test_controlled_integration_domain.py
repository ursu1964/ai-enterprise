from uuid import uuid4

import pytest
from fastapi import HTTPException

from ai_enterprise.api.dependencies import Actor, get_actor
from ai_enterprise.api.routes.integration import (
    _require_integration_attempt_create,
    get_integration_attempt,
)
from ai_enterprise.domain.execution.lineage import RevisionLineagePolicy
from ai_enterprise.domain.integration.exceptions import (
    HumanApprovalRequiredError,
    TargetBranchNotAllowedError,
)
from ai_enterprise.domain.integration.policies import (
    IntegrationAuthorizationPolicy,
    PatchEligibilityPolicy,
)
from ai_enterprise.infrastructure.database.models import IntegrationAttemptModel


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


def test_integration_attempt_creation_requires_scoped_capability() -> None:
    with pytest.raises(HTTPException, match="Integration operator authority"):
        _require_integration_attempt_create(
            Actor(
                "operator",
                "service",
                "integration_operator",
                frozenset({"integration.attempt.create"}),
                scopes=frozenset({"global"}),
            )
        )
    with pytest.raises(HTTPException, match="Integration operator authority"):
        _require_integration_attempt_create(Actor("operator", "human", "integration_operator"))
    with pytest.raises(HTTPException, match="Integration operator authority"):
        _require_integration_attempt_create(
            Actor(
                "operator",
                "human",
                "integration_operator",
                frozenset({"integration.attempt.create"}),
                scopes=frozenset({"project:wrong"}),
            )
        )
    _require_integration_attempt_create(
        Actor(
            "operator",
            "human",
            "integration_operator",
            frozenset({"integration.attempt.create"}),
            scopes=frozenset({"global"}),
        )
    )


class IntegrationReadSession:
    def __init__(self, row: IntegrationAttemptModel | None) -> None:
        self.row = row

    async def get(self, model: type, identity: object) -> object | None:
        return self.row


def integration_attempt(project_id) -> IntegrationAttemptModel:
    return IntegrationAttemptModel(
        id=uuid4(),
        execution_run_id=uuid4(),
        integration_approval_id=uuid4(),
        attempt_number=1,
        status="queued",
        project_id=project_id,
        target_branch="main",
        expected_patch_sha256="a" * 64,
        expected_base_commit_sha="b" * 40,
        expected_base_tree_sha="c" * 40,
        actual_base_commit_sha=None,
        actual_base_tree_sha=None,
        resulting_tree_sha=None,
        failure_code=None,
        failure_message=None,
        worker_id=None,
        correlation_id=uuid4(),
        started_at=None,
        completed_at=None,
    )


@pytest.mark.asyncio
async def test_integration_attempt_read_requires_project_scope() -> None:
    project_id = uuid4()
    row = integration_attempt(project_id)
    denied = Actor(
        "reader",
        "human",
        "operator",
        frozenset({"integration.read"}),
        scopes=frozenset({f"project:{uuid4()}"}),
    )
    allowed = Actor(
        "reader",
        "human",
        "operator",
        frozenset({"integration.read"}),
        scopes=frozenset({f"project:{project_id}"}),
    )

    with pytest.raises(HTTPException) as exc:
        await get_integration_attempt(row.id, IntegrationReadSession(row), denied)  # type: ignore[arg-type]

    assert exc.value.status_code == 403
    assert (
        await get_integration_attempt(row.id, IntegrationReadSession(row), allowed)  # type: ignore[arg-type]
    ).id == row.id


@pytest.mark.asyncio
async def test_integration_attempt_read_requires_human_actor() -> None:
    project_id = uuid4()
    row = integration_attempt(project_id)
    denied = Actor(
        "integration-service",
        "service",
        "operator",
        frozenset({"integration.read"}),
        scopes=frozenset({f"project:{project_id}"}),
    )

    with pytest.raises(HTTPException) as exc:
        await get_integration_attempt(row.id, IntegrationReadSession(row), denied)  # type: ignore[arg-type]

    assert exc.value.status_code == 403
    assert exc.value.detail == "Human integration authority is required"
