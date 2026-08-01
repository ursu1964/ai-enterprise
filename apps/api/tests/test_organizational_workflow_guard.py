from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from uuid import UUID, uuid4

import pytest

from ai_enterprise.application.organization import (
    AgentRuntimeIdentity,
    AuthorizationDenied,
    InMemoryParticipationLedger,
    OrganizationalWorkflowGuard,
    RunningWorkDisposition,
    SuspensionPlan,
    WorkflowAction,
    WorkflowBinding,
)
from ai_enterprise.application.organization.workflow_guard import AuthorityResult


class StubAuthority:
    def __init__(self, *, allowed: bool = True) -> None:
        self.allowed = allowed

    def evaluate(
        self,
        *,
        identity: AgentRuntimeIdentity,
        capability: str,
        scope_type: str,
        scope_id: UUID,
        now: datetime,
    ) -> AuthorityResult:
        del identity, capability, scope_type, scope_id, now
        return AuthorityResult(
            allowed=self.allowed,
            code="AUTH-ALLOWED" if self.allowed else "AUTH-DENIED-BY-DEFAULT",
            reasons=() if self.allowed else ("No active assignment grants capability",),
            policy_versions=("authority-v1",),
        )


def identity() -> AgentRuntimeIdentity:
    return AgentRuntimeIdentity(
        agent_profile_id=uuid4(),
        agent_profile_version_id=uuid4(),
        assignment_id=uuid4(),
        role_version_id=uuid4(),
        configuration_hash="a" * 64,
    )


def binding(action: WorkflowAction, scope_id: UUID | None = None) -> WorkflowBinding:
    return WorkflowBinding(
        workflow_type="test-workflow",
        action=action,
        scope_type="work_package",
        scope_id=scope_id or uuid4(),
        artifact_hash="b" * 64,
        correlation_id=uuid4(),
        high_risk=action in {WorkflowAction.EXECUTE, WorkflowAction.INTEGRATE},
    )


def test_authorization_is_bound_to_exact_runtime_identity() -> None:
    actor = identity()
    guard = OrganizationalWorkflowGuard(StubAuthority(), InMemoryParticipationLedger())
    grant = guard.authorize_agent(identity=actor, binding=binding(WorkflowAction.EXECUTE))

    grant.verify_runtime_identity(actor)
    with pytest.raises(AuthorizationDenied) as error:
        grant.verify_runtime_identity(
            replace(actor, agent_profile_version_id=uuid4())
        )
    assert error.value.code == "ORG-RUNTIME-IDENTITY-SUBSTITUTION"


def test_authorization_fails_closed() -> None:
    guard = OrganizationalWorkflowGuard(
        StubAuthority(allowed=False), InMemoryParticipationLedger()
    )
    with pytest.raises(AuthorizationDenied) as error:
        guard.authorize_agent(
            identity=identity(), binding=binding(WorkflowAction.ARCHITECTURE_AUTHOR)
        )
    assert error.value.code == "AUTH-DENIED-BY-DEFAULT"


@pytest.mark.parametrize(
    "action",
    [
        WorkflowAction.APPROVE_REQUIREMENTS,
        WorkflowAction.APPROVE_ARCHITECTURE,
        WorkflowAction.APPROVE_DECOMPOSITION,
        WorkflowAction.APPROVE_INTEGRATION,
    ],
)
def test_agent_can_never_acquire_human_only_authority(action: WorkflowAction) -> None:
    guard = OrganizationalWorkflowGuard(StubAuthority(), InMemoryParticipationLedger())
    with pytest.raises(AuthorizationDenied) as error:
        guard.authorize_agent(identity=identity(), binding=binding(action))
    assert error.value.code == "ORG-HUMAN-AUTHORITY-REQUIRED"


def test_implementation_actor_cannot_review_own_patch_even_with_capability() -> None:
    actor = identity()
    scope_id = uuid4()
    ledger = InMemoryParticipationLedger()
    guard = OrganizationalWorkflowGuard(StubAuthority(), ledger)
    implementation = guard.authorize_agent(
        identity=actor, binding=binding(WorkflowAction.EXECUTE, scope_id)
    )
    guard.record_completion(implementation, actor)

    with pytest.raises(AuthorizationDenied) as error:
        guard.authorize_agent(
            identity=actor, binding=binding(WorkflowAction.PATCH_REVIEW, scope_id)
        )
    assert error.value.code == "ORG-SEPARATION-OF-DUTIES-CONFLICT"


def test_distinct_profile_can_review_patch() -> None:
    implementer = identity()
    reviewer = identity()
    scope_id = uuid4()
    guard = OrganizationalWorkflowGuard(StubAuthority(), InMemoryParticipationLedger())
    grant = guard.authorize_agent(
        identity=implementer, binding=binding(WorkflowAction.EXECUTE, scope_id)
    )
    guard.record_completion(grant, implementer)

    review_grant = guard.authorize_agent(
        identity=reviewer, binding=binding(WorkflowAction.PATCH_REVIEW, scope_id)
    )
    assert review_grant.identity == reviewer


def test_hidden_participation_cannot_bypass_separation_of_duties() -> None:
    actor = identity()
    scope_id = uuid4()
    ledger = InMemoryParticipationLedger()
    first_guard = OrganizationalWorkflowGuard(StubAuthority(), ledger)
    grant = first_guard.authorize_agent(
        identity=actor, binding=binding(WorkflowAction.ARCHITECTURE_AUTHOR, scope_id)
    )
    first_guard.record_completion(grant, actor)

    # A fresh service instance still observes the durable-ledger boundary.
    restarted_guard = OrganizationalWorkflowGuard(StubAuthority(), ledger)
    with pytest.raises(AuthorizationDenied):
        restarted_guard.authorize_agent(
            identity=actor, binding=binding(WorkflowAction.ARCHITECTURE_REVIEW, scope_id)
        )


def test_configuration_hash_is_strictly_validated() -> None:
    with pytest.raises(ValueError):
        AgentRuntimeIdentity(
            agent_profile_id=uuid4(),
            agent_profile_version_id=uuid4(),
            assignment_id=uuid4(),
            role_version_id=uuid4(),
            configuration_hash="not-a-digest",
        )


def test_suspension_propagation_is_risk_sensitive_and_auditable() -> None:
    profile_id = uuid4()
    high = SuspensionPlan.create(profile_id=profile_id, reason="credential leak", high_risk=True)
    low = SuspensionPlan.create(profile_id=profile_id, reason="maintenance", high_risk=False)

    assert high.running_work is RunningWorkDisposition.CANCEL
    assert low.running_work is RunningWorkDisposition.CONTROLLED_TERMINATION
    assert high.revoke_unused_authorizations
    assert high.recompose_queued_crews
    assert low.artifact_approval_blocked
    assert high.policy_version == "agent-suspension-v1"


def test_completion_refuses_scheduler_substitution_and_records_nothing() -> None:
    actor = identity()
    ledger = InMemoryParticipationLedger()
    guard = OrganizationalWorkflowGuard(StubAuthority(), ledger)
    bound = binding(WorkflowAction.DECOMPOSE)
    grant = guard.authorize_agent(identity=actor, binding=bound)

    with pytest.raises(AuthorizationDenied):
        guard.record_completion(grant, replace(actor, assignment_id=uuid4()))
    assert ledger.for_scope(scope_type=bound.scope_type, scope_id=bound.scope_id) == ()
