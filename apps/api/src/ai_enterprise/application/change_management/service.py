import uuid
from dataclasses import replace
from datetime import UTC, datetime

from ai_enterprise.application.change_management.dto import (
    CreateChangeProposal,
    CreateChangeSet,
    CreateValidationPlan,
    GovernanceActor,
    RecordChangeDecision,
    RecordImpactAssessment,
)
from ai_enterprise.application.change_management.ports import (
    ChangeAuditSink,
    GovernedChangeRepository,
)
from ai_enterprise.domain.change_management.entities import (
    ChangeAuditRecord,
    ChangeDecision,
    ChangeOperation,
    ChangeProposal,
    ChangeSet,
    EntityReference,
    EvidenceReference,
    ImpactAssessment,
    ImpactFinding,
    ValidationPlan,
    ValidationRequirement,
    ValidationResult,
)
from ai_enterprise.domain.change_management.enums import (
    ChangeRisk,
    ChangeStatus,
    ImpactKnowledge,
)
from ai_enterprise.domain.change_management.exceptions import (
    ActivationNotSupported,
    ChangeRecordImmutable,
    InvalidChangeTransition,
)
from ai_enterprise.domain.change_management.hashing import canonical_hash
from ai_enterprise.domain.change_management.policies import (
    ChangeDecisionPolicy,
    ChangeRiskPolicy,
    ChangeSeparationPolicy,
    ChangeStatePolicy,
    ChangeSubmissionPolicy,
    SelfModificationPolicy,
    resulting_status,
)


class GovernedChangeNotFound(Exception):
    pass


class GovernedChangeService:
    """Decision-only kernel. It cannot activate, deploy, or roll out changes."""

    def __init__(self, repository: GovernedChangeRepository, audit: ChangeAuditSink) -> None:
        self._repository = repository
        self._audit = audit
        self._states = ChangeStatePolicy()
        self._separation = ChangeSeparationPolicy()

    async def create_proposal(
        self, request: CreateChangeProposal, actor: GovernanceActor
    ) -> ChangeProposal:
        now = datetime.now(UTC)
        material = {
            **request.model_dump(mode="json"),
            "proposed_by": actor.subject,
            "created_at": now,
        }
        affected_entities = tuple(
            EntityReference(**item.model_dump()) for item in request.affected_entities
        )
        ChangeRiskPolicy().require_not_understated(
            category=request.category,
            declared_risk=request.risk,
            affected_entities=affected_entities,
        )
        proposal = ChangeProposal(
            id=uuid.uuid4(),
            organization_id=request.organization_id,
            title=request.title,
            description=request.description,
            category=request.category,
            proposed_by=actor.subject,
            sponsor_id=request.sponsor_id,
            problem_statement=request.problem_statement,
            desired_outcome=request.desired_outcome,
            risk=request.risk,
            status=ChangeStatus.DRAFT,
            affected_entities=affected_entities,
            evidence=tuple(EvidenceReference(**item.model_dump()) for item in request.evidence),
            created_at=now,
            content_hash=canonical_hash(material),
        )
        await self._repository.add_proposal(proposal)
        await self._record(
            "change.proposal_created",
            proposal.id,
            actor.subject,
            {"content_hash": proposal.content_hash},
        )
        await self._repository.commit()
        return proposal

    async def add_change_set(
        self, proposal_id: uuid.UUID, request: CreateChangeSet, actor: GovernanceActor
    ) -> ChangeSet:
        proposal = await self._proposal(proposal_id)
        if proposal.status is not ChangeStatus.DRAFT:
            raise ChangeRecordImmutable("Change sets can only be added while draft")
        existing = await self._repository.list_change_sets(proposal_id)
        operations = tuple(
            ChangeOperation(
                operation_type=item.operation_type,
                target=EntityReference(**item.target.model_dump()),
                before_hash=item.before_hash,
                candidate_hash=item.candidate_hash,
                description=item.description,
            )
            for item in request.operations
        )
        SelfModificationPolicy().require_not_self_modifying(
            operations=operations,
            actor_type=str(actor.metadata.get("actor_type", "")),
            controlled_entity_ids={
                str(value) for value in actor.metadata.get("controlled_entity_ids", [])
            },
        )
        now = datetime.now(UTC)
        material = {
            "proposal_id": proposal_id,
            "version": len(existing) + 1,
            "operations": operations,
            "created_by": actor.subject,
            "created_at": now,
        }
        value = ChangeSet(
            id=uuid.uuid4(),
            proposal_id=proposal_id,
            version=len(existing) + 1,
            operations=operations,
            created_by=actor.subject,
            created_at=now,
            content_hash=canonical_hash(material),
        )
        await self._repository.add_change_set(value)
        await self._record(
            "change.set_created",
            proposal_id,
            actor.subject,
            {"change_set_id": str(value.id), "content_hash": value.content_hash},
        )
        await self._repository.commit()
        return value

    async def submit(self, proposal_id: uuid.UUID, actor: GovernanceActor) -> ChangeProposal:
        proposal = await self._proposal(proposal_id)
        sets = await self._repository.list_change_sets(proposal_id)
        ChangeSubmissionPolicy().require_complete(proposal, len(sets))
        updated = await self._transition(proposal, ChangeStatus.SUBMITTED, actor.subject)
        return updated

    async def assess_impact(
        self, proposal_id: uuid.UUID, request: RecordImpactAssessment, actor: GovernanceActor
    ) -> ImpactAssessment:
        proposal = await self._proposal(proposal_id)
        if proposal.status is not ChangeStatus.SUBMITTED:
            raise InvalidChangeTransition("Only submitted changes may be assessed")
        self._separation.require_independent_assessor(proposal, actor.subject)
        change_set = await self._repository.get_change_set(request.change_set_id)
        if change_set is None or change_set.proposal_id != proposal.id:
            raise GovernedChangeNotFound("Change set not found for proposal")
        findings = [
            ImpactFinding(
                code=item.code,
                dimension=item.dimension,
                knowledge=item.knowledge,
                severity=item.severity,
                message=item.message,
                affected_entities=tuple(
                    EntityReference(**ref.model_dump()) for ref in item.affected_entities
                ),
            )
            for item in request.findings
        ]
        if not request.dependency_analysis_complete:
            findings.append(
                ImpactFinding(
                    code="DEPENDENCY_IMPACT_UNKNOWN",
                    dimension="dependencies",
                    knowledge=ImpactKnowledge.UNKNOWN,
                    severity=ChangeRisk.CRITICAL,
                    message="Dependency analysis is incomplete; approval must fail closed.",
                )
            )
        existing = await self._repository.list_impact_assessments(proposal.id)
        now = datetime.now(UTC)
        direct = tuple(EntityReference(**item.model_dump()) for item in request.direct_impacts)
        indirect = tuple(EntityReference(**item.model_dump()) for item in request.indirect_impacts)
        material = {
            **request.model_dump(mode="json"),
            "findings": findings,
            "assessed_by": actor.subject,
            "version": len(existing) + 1,
            "created_at": now,
        }
        assessment = ImpactAssessment(
            id=uuid.uuid4(),
            proposal_id=proposal.id,
            change_set_id=change_set.id,
            version=len(existing) + 1,
            assessed_by=actor.subject,
            direct_impacts=direct,
            indirect_impacts=indirect,
            findings=tuple(findings),
            required_approval_roles=request.required_approval_roles,
            required_tests=request.required_tests,
            estimated_blast_radius=request.estimated_blast_radius,
            rollback_complexity=request.rollback_complexity,
            confidence=request.confidence,
            created_at=now,
            content_hash=canonical_hash(material),
        )
        await self._repository.add_impact_assessment(assessment)
        proposal = await self._transition(
            proposal, ChangeStatus.UNDER_ANALYSIS, actor.subject, commit=False
        )
        await self._transition(
            proposal, ChangeStatus.VALIDATION_REQUIRED, actor.subject, commit=False
        )
        await self._record(
            "change.impact_assessed",
            proposal.id,
            actor.subject,
            {
                "assessment_id": str(assessment.id),
                "content_hash": assessment.content_hash,
                "unknown_impact": assessment.has_unknown_impact,
            },
        )
        await self._repository.commit()
        return assessment

    async def create_validation_plan(
        self, proposal_id: uuid.UUID, request: CreateValidationPlan, actor: GovernanceActor
    ) -> ValidationPlan:
        proposal = await self._proposal(proposal_id)
        if proposal.status is not ChangeStatus.VALIDATION_REQUIRED:
            raise InvalidChangeTransition("Change does not require a validation plan")
        assessment = await self._repository.get_impact_assessment(request.impact_assessment_id)
        if assessment is None or assessment.proposal_id != proposal.id:
            raise GovernedChangeNotFound("Impact assessment not found for proposal")
        existing = await self._repository.list_validation_plans(proposal.id)
        requirements = tuple(
            ValidationRequirement(**item.model_dump()) for item in request.requirements
        )
        now = datetime.now(UTC)
        material = {
            **request.model_dump(mode="json"),
            "version": len(existing) + 1,
            "created_by": actor.subject,
            "created_at": now,
        }
        plan = ValidationPlan(
            id=uuid.uuid4(),
            proposal_id=proposal.id,
            impact_assessment_id=assessment.id,
            version=len(existing) + 1,
            requirements=requirements,
            rollback_evidence_required=request.rollback_evidence_required,
            created_by=actor.subject,
            created_at=now,
            content_hash=canonical_hash(material),
        )
        await self._repository.add_validation_plan(plan)
        await self._transition(
            proposal, ChangeStatus.READY_FOR_DECISION, actor.subject, commit=False
        )
        await self._record(
            "change.validation_plan_created",
            proposal.id,
            actor.subject,
            {"validation_plan_id": str(plan.id), "content_hash": plan.content_hash},
        )
        await self._repository.commit()
        return plan

    async def decide(
        self, proposal_id: uuid.UUID, request: RecordChangeDecision, actor: GovernanceActor
    ) -> ChangeDecision:
        proposal = await self._proposal(proposal_id)
        self._separation.require_independent_decider(proposal, actor.subject)
        change_set = await self._repository.get_change_set(request.change_set_id)
        assessment = await self._repository.get_impact_assessment(request.impact_assessment_id)
        plan = await self._repository.get_validation_plan(request.validation_plan_id)
        if any(item is None for item in (change_set, assessment, plan)):
            raise GovernedChangeNotFound("Decision binding is incomplete")
        assert change_set is not None and assessment is not None and plan is not None
        if {change_set.proposal_id, assessment.proposal_id, plan.proposal_id} != {proposal.id}:
            raise GovernedChangeNotFound("Decision records belong to another proposal")
        results = tuple(
            ValidationResult(
                requirement_code=item.requirement_code,
                passed=item.passed,
                evidence=tuple(EvidenceReference(**ref.model_dump()) for ref in item.evidence),
            )
            for item in request.validation_results
        )
        ChangeDecisionPolicy().require_decidable(
            proposal=proposal,
            assessment=assessment,
            validation_plan=plan,
            decision=request.decision,
            passed_requirement_codes={item.requirement_code for item in results if item.passed},
            actor_roles=set(actor.roles),
        )
        now = datetime.now(UTC)
        material = {
            **request.model_dump(mode="json"),
            "decided_by": actor.subject,
            "actor_roles": sorted(actor.roles),
            "decided_at": now,
        }
        decision = ChangeDecision(
            id=uuid.uuid4(),
            proposal_id=proposal.id,
            change_set_id=change_set.id,
            impact_assessment_id=assessment.id,
            validation_plan_id=plan.id,
            decision=request.decision,
            decided_by=actor.subject,
            actor_roles=tuple(sorted(actor.roles)),
            reason=request.reason,
            validation_results=results,
            decided_at=now,
            content_hash=canonical_hash(material),
        )
        await self._repository.append_decision(decision)
        await self._transition(proposal, resulting_status(decision), actor.subject, commit=False)
        await self._record(
            "change.decision_recorded",
            proposal.id,
            actor.subject,
            {
                "decision_id": str(decision.id),
                "decision": decision.decision,
                "content_hash": decision.content_hash,
            },
        )
        await self._repository.commit()
        return decision

    async def activate(self, proposal_id: uuid.UUID, actor: GovernanceActor) -> None:
        raise ActivationNotSupported(
            "P10-M1 records decisions only; activation, rollout, and "
            "self-modification are prohibited"
        )

    async def _proposal(self, proposal_id: uuid.UUID) -> ChangeProposal:
        value = await self._repository.get_proposal(proposal_id)
        if value is None:
            raise GovernedChangeNotFound("Change proposal not found")
        return value

    async def _transition(
        self, proposal: ChangeProposal, target: ChangeStatus, actor_id: str, *, commit: bool = True
    ) -> ChangeProposal:
        self._states.require_transition(proposal.status, target)
        updated = replace(proposal, status=target)
        await self._repository.replace_proposal(updated)
        await self._record(
            "change.status_changed",
            proposal.id,
            actor_id,
            {
                "previous_status": proposal.status,
                "status": target,
                "proposal_content_hash": proposal.content_hash,
            },
        )
        if commit:
            await self._repository.commit()
        return updated

    async def _record(
        self, event_type: str, aggregate_id: uuid.UUID, actor_id: str, payload: dict[str, object]
    ) -> None:
        now = datetime.now(UTC)
        await self._audit.append(
            ChangeAuditRecord(
                event_type=event_type,
                aggregate_id=aggregate_id,
                actor_id=actor_id,
                occurred_at=now,
                payload=payload,
                payload_hash=canonical_hash(payload),
            )
        )
