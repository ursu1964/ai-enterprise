from dataclasses import FrozenInstanceError
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from ai_enterprise.application.change_management.dto import (
    ChangeOperationInput,
    CreateChangeProposal,
    CreateChangeSet,
    CreateValidationPlan,
    EntityReferenceInput,
    EvidenceReferenceInput,
    GovernanceActor,
    ImpactFindingInput,
    RecordChangeDecision,
    RecordImpactAssessment,
    ValidationRequirementInput,
    ValidationResultInput,
)
from ai_enterprise.application.change_management.service import GovernedChangeService
from ai_enterprise.domain.change_management.entities import (
    ChangeAuditRecord,
    ChangeDecision,
    ChangeProposal,
    ChangeSet,
    ImpactAssessment,
    ValidationPlan,
)
from ai_enterprise.domain.change_management.enums import (
    ChangeCategory,
    ChangeDecisionType,
    ChangeRisk,
    ChangeStatus,
    ImpactKnowledge,
)
from ai_enterprise.domain.change_management.exceptions import (
    ActivationNotSupported,
    ChangeEvidenceRequired,
    ChangeRecordImmutable,
    ChangeRiskUnderstated,
    ChangeSelfApprovalForbidden,
    IndependentAssessmentRequired,
    InvalidChangeTransition,
    SelfModificationForbidden,
    UnknownImpactBlocksDecision,
)
from ai_enterprise.domain.change_management.hashing import canonical_hash

HASH_A = "a" * 64
HASH_B = "b" * 64


class MemoryRepository:
    def __init__(self) -> None:
        self.proposals: dict[UUID, ChangeProposal] = {}
        self.change_sets: dict[UUID, ChangeSet] = {}
        self.assessments: dict[UUID, ImpactAssessment] = {}
        self.plans: dict[UUID, ValidationPlan] = {}
        self.decisions: list[ChangeDecision] = []
        self.commits = 0

    async def add_proposal(self, proposal: ChangeProposal) -> None:
        self.proposals[proposal.id] = proposal

    async def get_proposal(self, proposal_id: UUID) -> ChangeProposal | None:
        return self.proposals.get(proposal_id)

    async def replace_proposal(self, proposal: ChangeProposal) -> None:
        self.proposals[proposal.id] = proposal

    async def add_change_set(self, value: ChangeSet) -> None:
        self.change_sets[value.id] = value

    async def list_change_sets(self, proposal_id: UUID) -> tuple[ChangeSet, ...]:
        return tuple(item for item in self.change_sets.values() if item.proposal_id == proposal_id)

    async def get_change_set(self, value_id: UUID) -> ChangeSet | None:
        return self.change_sets.get(value_id)

    async def add_impact_assessment(self, value: ImpactAssessment) -> None:
        self.assessments[value.id] = value

    async def list_impact_assessments(self, proposal_id: UUID) -> tuple[ImpactAssessment, ...]:
        return tuple(item for item in self.assessments.values() if item.proposal_id == proposal_id)

    async def get_impact_assessment(self, value_id: UUID) -> ImpactAssessment | None:
        return self.assessments.get(value_id)

    async def add_validation_plan(self, value: ValidationPlan) -> None:
        self.plans[value.id] = value

    async def list_validation_plans(self, proposal_id: UUID) -> tuple[ValidationPlan, ...]:
        return tuple(item for item in self.plans.values() if item.proposal_id == proposal_id)

    async def get_validation_plan(self, value_id: UUID) -> ValidationPlan | None:
        return self.plans.get(value_id)

    async def append_decision(self, value: ChangeDecision) -> None:
        self.decisions.append(value)

    async def list_decisions(self, proposal_id: UUID) -> tuple[ChangeDecision, ...]:
        return tuple(item for item in self.decisions if item.proposal_id == proposal_id)

    async def commit(self) -> None:
        self.commits += 1


class MemoryAudit:
    def __init__(self) -> None:
        self.records: list[ChangeAuditRecord] = []

    async def append(self, record: ChangeAuditRecord) -> None:
        self.records.append(record)


@pytest.fixture
def kernel() -> tuple[GovernedChangeService, MemoryRepository, MemoryAudit]:
    repository = MemoryRepository()
    audit = MemoryAudit()
    return GovernedChangeService(repository, audit), repository, audit


def actor(subject: str, *roles: str) -> GovernanceActor:
    return GovernanceActor(subject=subject, roles=frozenset(roles))


def proposal_request(*, evidence: bool = True) -> CreateChangeProposal:
    return CreateChangeProposal(
        organization_id=uuid4(),
        title="Version integration policy",
        description="Introduce a candidate policy version without activating it.",
        category=ChangeCategory.POLICY,
        sponsor_id="sponsor-1",
        problem_statement="Policy behavior is not explicitly versioned.",
        desired_outcome="A reviewed and testable candidate policy exists.",
        risk=ChangeRisk.HIGH,
        affected_entities=(
            EntityReferenceInput(entity_type="policy", entity_id=uuid4(), entity_version="1"),
        ),
        evidence=(
            (
                EvidenceReferenceInput(
                    artifact_id=uuid4(), content_hash=HASH_A, evidence_type="incident"
                ),
            )
            if evidence
            else ()
        ),
    )


def set_request() -> CreateChangeSet:
    return CreateChangeSet(
        operations=(
            ChangeOperationInput(
                operation_type="replace_candidate",
                target=EntityReferenceInput(
                    entity_type="policy", entity_id=uuid4(), entity_version="1"
                ),
                before_hash=HASH_A,
                candidate_hash=HASH_B,
                description="Create a new immutable policy candidate.",
            ),
        )
    )


def impact_request(change_set_id: UUID, *, complete: bool = True) -> RecordImpactAssessment:
    return RecordImpactAssessment(
        change_set_id=change_set_id,
        direct_impacts=(),
        indirect_impacts=(),
        findings=(
            ImpactFindingInput(
                code="AUTHORITY_REVIEW",
                dimension="authority",
                knowledge=ImpactKnowledge.KNOWN,
                severity=ChangeRisk.HIGH,
                message="Approval separation must remain enforced.",
            ),
        ),
        required_approval_roles=("change_approver",),
        required_tests=("policy-separation",),
        estimated_blast_radius=ChangeRisk.HIGH,
        rollback_complexity=ChangeRisk.MEDIUM,
        confidence=0.8,
        dependency_analysis_complete=complete,
    )


async def ready_change(
    kernel: tuple[GovernedChangeService, MemoryRepository, MemoryAudit], *, complete: bool = True
):
    service, repository, _ = kernel
    proposal = await service.create_proposal(proposal_request(), actor("proposer"))
    change_set = await service.add_change_set(proposal.id, set_request(), actor("proposer"))
    await service.submit(proposal.id, actor("proposer"))
    assessment = await service.assess_impact(
        proposal.id, impact_request(change_set.id, complete=complete), actor("assessor")
    )
    plan = await service.create_validation_plan(
        proposal.id,
        CreateValidationPlan(
            impact_assessment_id=assessment.id,
            requirements=(
                ValidationRequirementInput(
                    code="policy-separation",
                    description="Verify implementation and approval remain separate.",
                ),
            ),
        ),
        actor("validator"),
    )
    return service, repository, proposal, change_set, assessment, plan


@pytest.mark.asyncio
async def test_proposal_is_immutable_and_hashed(kernel) -> None:
    service, _, audit = kernel
    proposal = await service.create_proposal(proposal_request(), actor("proposer"))
    assert len(proposal.content_hash) == 64
    assert audit.records[0].payload_hash == canonical_hash(audit.records[0].payload)
    with pytest.raises(FrozenInstanceError):
        proposal.title = "mutated"  # type: ignore[misc]


@pytest.mark.asyncio
async def test_submission_requires_evidence_and_change_set(kernel) -> None:
    service, _, _ = kernel
    proposal = await service.create_proposal(proposal_request(evidence=False), actor("proposer"))
    with pytest.raises(ChangeEvidenceRequired):
        await service.submit(proposal.id, actor("proposer"))


@pytest.mark.asyncio
async def test_change_set_cannot_change_after_submission(kernel) -> None:
    service, _, _ = kernel
    proposal = await service.create_proposal(proposal_request(), actor("proposer"))
    await service.add_change_set(proposal.id, set_request(), actor("proposer"))
    await service.submit(proposal.id, actor("proposer"))
    with pytest.raises(ChangeRecordImmutable):
        await service.add_change_set(proposal.id, set_request(), actor("proposer"))


@pytest.mark.asyncio
async def test_proposer_cannot_assess_own_change(kernel) -> None:
    service, _, _ = kernel
    proposal = await service.create_proposal(proposal_request(), actor("proposer"))
    change_set = await service.add_change_set(proposal.id, set_request(), actor("proposer"))
    await service.submit(proposal.id, actor("proposer"))
    with pytest.raises(IndependentAssessmentRequired):
        await service.assess_impact(proposal.id, impact_request(change_set.id), actor("proposer"))


@pytest.mark.asyncio
async def test_incomplete_dependency_analysis_creates_blocking_unknown(kernel) -> None:
    _, _, _, _, assessment, _ = await ready_change(kernel, complete=False)
    assert assessment.has_unknown_impact
    finding = next(item for item in assessment.findings if item.code == "DEPENDENCY_IMPACT_UNKNOWN")
    assert finding.severity is ChangeRisk.CRITICAL


@pytest.mark.asyncio
async def test_unknown_impact_fails_closed_on_approval(kernel) -> None:
    service, _, proposal, change_set, assessment, plan = await ready_change(kernel, complete=False)
    with pytest.raises(UnknownImpactBlocksDecision):
        await service.decide(
            proposal.id,
            decision_request(change_set.id, assessment.id, plan.id),
            actor("approver", "change_approver"),
        )


def decision_request(
    change_set_id: UUID,
    assessment_id: UUID,
    plan_id: UUID,
    decision: ChangeDecisionType = ChangeDecisionType.APPROVED,
) -> RecordChangeDecision:
    return RecordChangeDecision(
        change_set_id=change_set_id,
        impact_assessment_id=assessment_id,
        validation_plan_id=plan_id,
        decision=decision,
        reason="Independent evidence supports this decision.",
        validation_results=(
            ValidationResultInput(
                requirement_code="policy-separation",
                passed=True,
                evidence=(
                    EvidenceReferenceInput(
                        artifact_id=uuid4(), content_hash=HASH_B, evidence_type="test"
                    ),
                ),
            ),
        ),
    )


@pytest.mark.asyncio
async def test_proposer_cannot_approve_own_change(kernel) -> None:
    service, _, proposal, change_set, assessment, plan = await ready_change(kernel)
    with pytest.raises(ChangeSelfApprovalForbidden):
        await service.decide(
            proposal.id,
            decision_request(change_set.id, assessment.id, plan.id),
            actor("proposer", "change_approver"),
        )


@pytest.mark.asyncio
async def test_required_role_and_blocking_validation_are_enforced(kernel) -> None:
    service, _, proposal, change_set, assessment, plan = await ready_change(kernel)
    request = decision_request(change_set.id, assessment.id, plan.id)
    with pytest.raises(InvalidChangeTransition, match="roles"):
        await service.decide(proposal.id, request, actor("approver"))


@pytest.mark.asyncio
async def test_approved_decision_is_appended_and_terminal(kernel) -> None:
    service, repository, proposal, change_set, assessment, plan = await ready_change(kernel)
    decision = await service.decide(
        proposal.id,
        decision_request(change_set.id, assessment.id, plan.id),
        actor("approver", "change_approver"),
    )
    assert repository.decisions == [decision]
    assert repository.proposals[proposal.id].status is ChangeStatus.APPROVED
    with pytest.raises(InvalidChangeTransition):
        await service.decide(
            proposal.id,
            decision_request(change_set.id, assessment.id, plan.id),
            actor("other", "change_approver"),
        )


@pytest.mark.asyncio
async def test_rejection_is_allowed_without_claiming_activation(kernel) -> None:
    service, repository, proposal, change_set, assessment, plan = await ready_change(
        kernel, complete=False
    )
    decision = await service.decide(
        proposal.id,
        decision_request(change_set.id, assessment.id, plan.id, ChangeDecisionType.REJECTED),
        actor("approver", "change_approver"),
    )
    assert decision.decision is ChangeDecisionType.REJECTED
    assert repository.proposals[proposal.id].status is ChangeStatus.REJECTED


@pytest.mark.asyncio
async def test_activation_and_rollout_are_explicitly_unsupported(kernel) -> None:
    service, _, _ = kernel
    with pytest.raises(ActivationNotSupported, match="self-modification"):
        await service.activate(uuid4(), actor("approver", "change_approver"))


def test_passing_validation_result_requires_evidence() -> None:
    with pytest.raises(ValidationError, match="requires evidence"):
        RecordChangeDecision(
            change_set_id=uuid4(),
            impact_assessment_id=uuid4(),
            validation_plan_id=uuid4(),
            decision=ChangeDecisionType.APPROVED,
            reason="Approve candidate.",
            validation_results=(ValidationResultInput(requirement_code="test", passed=True),),
        )


def test_canonical_hash_is_order_independent() -> None:
    assert canonical_hash({"a": 1, "b": 2}) == canonical_hash({"b": 2, "a": 1})


@pytest.mark.asyncio
async def test_security_control_change_cannot_understate_risk(kernel) -> None:
    service, _, _ = kernel
    request = proposal_request().model_copy(
        update={
            "category": ChangeCategory.SECURITY_CONTROL,
            "risk": ChangeRisk.LOW,
        }
    )
    with pytest.raises(ChangeRiskUnderstated):
        await service.create_proposal(request, actor("proposer"))


@pytest.mark.asyncio
async def test_agent_cannot_target_its_own_controlled_entity(kernel) -> None:
    service, _, _ = kernel
    proposal = await service.create_proposal(proposal_request(), actor("agent-1"))
    target_id = uuid4()
    request = CreateChangeSet(
        operations=(
            ChangeOperationInput(
                operation_type="replace_candidate",
                target=EntityReferenceInput(entity_type="agent_definition", entity_id=target_id),
                before_hash=HASH_A,
                candidate_hash=HASH_B,
                description="Attempt to change this agent's own definition.",
            ),
        )
    )
    self_actor = GovernanceActor(
        subject="agent-1",
        metadata={
            "actor_type": "agent",
            "controlled_entity_ids": [str(target_id)],
        },
    )
    with pytest.raises(SelfModificationForbidden):
        await service.add_change_set(proposal.id, request, self_actor)
