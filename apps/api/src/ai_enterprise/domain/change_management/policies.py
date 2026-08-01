from .entities import (
    ChangeDecision,
    ChangeOperation,
    ChangeProposal,
    EntityReference,
    ImpactAssessment,
    ValidationPlan,
)
from .enums import ChangeCategory, ChangeDecisionType, ChangeRisk, ChangeStatus
from .exceptions import (
    ChangeEvidenceRequired,
    ChangeRiskUnderstated,
    ChangeSelfApprovalForbidden,
    IndependentAssessmentRequired,
    InvalidChangeTransition,
    SelfModificationForbidden,
    UnknownImpactBlocksDecision,
)


class ChangeRiskPolicy:
    _RANK = {
        ChangeRisk.LOW: 0,
        ChangeRisk.MEDIUM: 1,
        ChangeRisk.HIGH: 2,
        ChangeRisk.CRITICAL: 3,
    }
    _CATEGORY_FLOOR = {
        ChangeCategory.POLICY: ChangeRisk.MEDIUM,
        ChangeCategory.WORKFLOW: ChangeRisk.MEDIUM,
        ChangeCategory.AGENT_DEFINITION: ChangeRisk.MEDIUM,
        ChangeCategory.SCHEMA: ChangeRisk.MEDIUM,
        ChangeCategory.SECURITY_CONTROL: ChangeRisk.HIGH,
    }

    def require_not_understated(
        self,
        *,
        category: ChangeCategory,
        declared_risk: ChangeRisk,
        affected_entities: tuple[EntityReference, ...],
    ) -> None:
        floor = self._CATEGORY_FLOOR.get(category, ChangeRisk.LOW)
        if any(item.entity_type == "constitutional_policy" for item in affected_entities):
            floor = ChangeRisk.CRITICAL
        if self._RANK[declared_risk] < self._RANK[floor]:
            raise ChangeRiskUnderstated(f"{category} changes require risk of at least {floor}")


class SelfModificationPolicy:
    def require_not_self_modifying(
        self,
        *,
        operations: tuple[ChangeOperation, ...],
        actor_type: str | None,
        controlled_entity_ids: set[str],
    ) -> None:
        if actor_type != "agent":
            return
        targeted = {str(item.target.entity_id) for item in operations}
        if targeted & controlled_entity_ids:
            raise SelfModificationForbidden(
                "An agent cannot modify its own definition, authority, or evaluation"
            )


class ChangeStatePolicy:
    _TRANSITIONS = {
        ChangeStatus.DRAFT: {ChangeStatus.SUBMITTED},
        ChangeStatus.SUBMITTED: {ChangeStatus.UNDER_ANALYSIS},
        ChangeStatus.UNDER_ANALYSIS: {ChangeStatus.VALIDATION_REQUIRED},
        ChangeStatus.VALIDATION_REQUIRED: {ChangeStatus.READY_FOR_DECISION},
        ChangeStatus.READY_FOR_DECISION: {
            ChangeStatus.APPROVED,
            ChangeStatus.REJECTED,
            ChangeStatus.DEFERRED,
        },
    }

    def require_transition(self, current: ChangeStatus, target: ChangeStatus) -> None:
        if target not in self._TRANSITIONS.get(current, set()):
            raise InvalidChangeTransition(f"Cannot transition from {current} to {target}")


class ChangeSubmissionPolicy:
    def require_complete(self, proposal: ChangeProposal, change_set_count: int) -> None:
        if not proposal.evidence:
            raise ChangeEvidenceRequired("A material change requires supporting evidence")
        if not proposal.affected_entities:
            raise ChangeEvidenceRequired("A material change requires affected entities")
        if change_set_count < 1:
            raise ChangeEvidenceRequired("A material change requires an immutable change set")


class ChangeSeparationPolicy:
    def require_independent_assessor(self, proposal: ChangeProposal, assessor_id: str) -> None:
        if assessor_id == proposal.proposed_by:
            raise IndependentAssessmentRequired(
                "The proposer cannot independently assess the change"
            )

    def require_independent_decider(self, proposal: ChangeProposal, decider_id: str) -> None:
        if decider_id == proposal.proposed_by:
            raise ChangeSelfApprovalForbidden("A change proposal cannot approve itself")


class ChangeDecisionPolicy:
    def require_decidable(
        self,
        *,
        proposal: ChangeProposal,
        assessment: ImpactAssessment,
        validation_plan: ValidationPlan,
        decision: ChangeDecisionType,
        passed_requirement_codes: set[str],
        actor_roles: set[str],
    ) -> None:
        if proposal.status is not ChangeStatus.READY_FOR_DECISION:
            raise InvalidChangeTransition("Change is not ready for decision")
        if decision is ChangeDecisionType.APPROVED and assessment.has_unknown_impact:
            raise UnknownImpactBlocksDecision("Unknown impact must be resolved before approval")
        if decision is ChangeDecisionType.APPROVED:
            blocking = {item.code for item in validation_plan.requirements if item.blocking}
            if not blocking.issubset(passed_requirement_codes):
                raise InvalidChangeTransition("Blocking validation has not passed")
            required_roles = set(assessment.required_approval_roles)
            if not required_roles.issubset(actor_roles):
                raise InvalidChangeTransition("Required approval roles are missing")


def resulting_status(decision: ChangeDecision) -> ChangeStatus:
    return {
        ChangeDecisionType.APPROVED: ChangeStatus.APPROVED,
        ChangeDecisionType.REJECTED: ChangeStatus.REJECTED,
        ChangeDecisionType.DEFERRED: ChangeStatus.DEFERRED,
    }[decision.decision]
