import uuid
from dataclasses import asdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.domain.change_management.entities import (
    ChangeAuditRecord,
    ChangeDecision,
    ChangeObservation,
    ChangeOperation,
    ChangeOutcome,
    ChangeProposal,
    ChangeSet,
    EntityReference,
    EvidenceReference,
    ImpactAssessment,
    ImpactFinding,
    RollbackPlan,
    RolloutPlan,
    TransformationPlan,
    ValidationPlan,
    ValidationRequirement,
    ValidationResult,
)
from ai_enterprise.domain.change_management.enums import (
    ChangeCategory,
    ChangeDecisionType,
    ChangeOutcomeDisposition,
    ChangeRisk,
    ChangeStatus,
    ImpactKnowledge,
)
from ai_enterprise.infrastructure.database.models import AuditEventModel

from .models import (
    ChangeDecisionModel,
    ChangeEvidenceModel,
    ChangeImpactAssessmentModel,
    ChangeObservationModel,
    ChangeOutcomeModel,
    ChangeProposalModel,
    ChangeRollbackPlanModel,
    ChangeRolloutPlanModel,
    ChangeSetModel,
    ChangeTransformationPlanModel,
    ChangeValidationPlanModel,
)


def _reference_payload(value: EntityReference) -> dict[str, Any]:
    return {
        "entity_type": value.entity_type,
        "entity_id": str(value.entity_id),
        "entity_version": value.entity_version,
    }


def _reference(value: dict[str, Any]) -> EntityReference:
    return EntityReference(
        entity_type=str(value["entity_type"]),
        entity_id=uuid.UUID(str(value["entity_id"])),
        entity_version=value.get("entity_version"),
    )


def _evidence_payload(value: EvidenceReference) -> dict[str, str]:
    return {
        "artifact_id": str(value.artifact_id),
        "content_hash": value.content_hash,
        "evidence_type": value.evidence_type,
    }


class SqlAlchemyGovernedChangeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_proposal(self, value: ChangeProposal) -> None:
        self._session.add(
            ChangeProposalModel(
                id=value.id,
                organization_id=value.organization_id,
                title=value.title,
                description=value.description,
                category=value.category,
                proposed_by=value.proposed_by,
                sponsor_id=value.sponsor_id,
                problem_statement=value.problem_statement,
                desired_outcome=value.desired_outcome,
                risk=value.risk,
                status=value.status,
                affected_entities=[_reference_payload(item) for item in value.affected_entities],
                content_hash=value.content_hash,
                created_at=value.created_at,
            )
        )
        for evidence in value.evidence:
            self._add_evidence(value.id, "proposal", value.id, evidence)

    async def get_proposal(self, proposal_id: uuid.UUID) -> ChangeProposal | None:
        model = await self._session.get(ChangeProposalModel, proposal_id)
        if model is None:
            return None
        evidence = await self._evidence("proposal", proposal_id)
        return ChangeProposal(
            id=model.id,
            organization_id=model.organization_id,
            title=model.title,
            description=model.description,
            category=ChangeCategory(model.category),
            proposed_by=model.proposed_by,
            sponsor_id=model.sponsor_id,
            problem_statement=model.problem_statement,
            desired_outcome=model.desired_outcome,
            risk=ChangeRisk(model.risk),
            status=ChangeStatus(model.status),
            affected_entities=tuple(_reference(item) for item in model.affected_entities),
            evidence=evidence,
            created_at=model.created_at,
            content_hash=model.content_hash,
        )

    async def replace_proposal(self, value: ChangeProposal) -> None:
        model = await self._session.get(ChangeProposalModel, value.id)
        if model is None:
            raise LookupError("Change proposal not found")
        model.status = value.status

    async def add_change_set(self, value: ChangeSet) -> None:
        self._session.add(
            ChangeSetModel(
                id=value.id,
                proposal_id=value.proposal_id,
                version=value.version,
                operations=[
                    {
                        "operation_type": item.operation_type,
                        "target": _reference_payload(item.target),
                        "before_hash": item.before_hash,
                        "candidate_hash": item.candidate_hash,
                        "description": item.description,
                    }
                    for item in value.operations
                ],
                created_by=value.created_by,
                created_at=value.created_at,
                content_hash=value.content_hash,
            )
        )

    async def list_change_sets(self, proposal_id: uuid.UUID) -> tuple[ChangeSet, ...]:
        values = await self._models(ChangeSetModel, proposal_id)
        return tuple(self._change_set(item) for item in values)

    async def get_change_set(self, value_id: uuid.UUID) -> ChangeSet | None:
        value = await self._session.get(ChangeSetModel, value_id)
        return self._change_set(value) if value else None

    async def add_transformation_plan(self, value: TransformationPlan) -> None:
        self._session.add(
            ChangeTransformationPlanModel(
                id=value.id,
                proposal_id=value.proposal_id,
                change_set_id=value.change_set_id,
                version=value.version,
                strategy=value.strategy,
                steps=list(value.steps),
                prerequisites=list(value.prerequisites),
                created_by=value.created_by,
                created_at=value.created_at,
                content_hash=value.content_hash,
            )
        )
        for evidence in value.evidence:
            self._add_evidence(value.proposal_id, "transformation_plan", value.id, evidence)

    async def get_transformation_plan(
        self, value_id: uuid.UUID
    ) -> TransformationPlan | None:
        value = await self._session.get(ChangeTransformationPlanModel, value_id)
        return await self._transformation_plan(value) if value else None

    async def list_transformation_plans(
        self, proposal_id: uuid.UUID
    ) -> tuple[TransformationPlan, ...]:
        models = await self._models(ChangeTransformationPlanModel, proposal_id)
        return tuple([await self._transformation_plan(item) for item in models])

    async def add_impact_assessment(self, value: ImpactAssessment) -> None:
        self._session.add(
            ChangeImpactAssessmentModel(
                id=value.id,
                proposal_id=value.proposal_id,
                change_set_id=value.change_set_id,
                version=value.version,
                assessed_by=value.assessed_by,
                direct_impacts=[_reference_payload(item) for item in value.direct_impacts],
                indirect_impacts=[_reference_payload(item) for item in value.indirect_impacts],
                findings=[
                    {
                        "code": item.code,
                        "dimension": item.dimension,
                        "knowledge": item.knowledge,
                        "severity": item.severity,
                        "message": item.message,
                        "affected_entities": [
                            _reference_payload(ref) for ref in item.affected_entities
                        ],
                    }
                    for item in value.findings
                ],
                required_approval_roles=list(value.required_approval_roles),
                required_tests=list(value.required_tests),
                estimated_blast_radius=value.estimated_blast_radius,
                rollback_complexity=value.rollback_complexity,
                confidence=value.confidence,
                created_at=value.created_at,
                content_hash=value.content_hash,
            )
        )

    async def list_impact_assessments(self, proposal_id: uuid.UUID) -> tuple[ImpactAssessment, ...]:
        return tuple(
            self._assessment(item)
            for item in await self._models(ChangeImpactAssessmentModel, proposal_id)
        )

    async def get_impact_assessment(self, value_id: uuid.UUID) -> ImpactAssessment | None:
        value = await self._session.get(ChangeImpactAssessmentModel, value_id)
        return self._assessment(value) if value else None

    async def add_validation_plan(self, value: ValidationPlan) -> None:
        self._session.add(
            ChangeValidationPlanModel(
                id=value.id,
                proposal_id=value.proposal_id,
                impact_assessment_id=value.impact_assessment_id,
                version=value.version,
                requirements=[asdict(item) for item in value.requirements],
                rollback_evidence_required=value.rollback_evidence_required,
                created_by=value.created_by,
                created_at=value.created_at,
                content_hash=value.content_hash,
            )
        )

    async def list_validation_plans(self, proposal_id: uuid.UUID) -> tuple[ValidationPlan, ...]:
        return tuple(
            self._plan(item) for item in await self._models(ChangeValidationPlanModel, proposal_id)
        )

    async def get_validation_plan(self, value_id: uuid.UUID) -> ValidationPlan | None:
        value = await self._session.get(ChangeValidationPlanModel, value_id)
        return self._plan(value) if value else None

    async def add_rollout_plan(self, value: RolloutPlan) -> None:
        self._session.add(
            ChangeRolloutPlanModel(
                id=value.id,
                proposal_id=value.proposal_id,
                transformation_plan_id=value.transformation_plan_id,
                validation_plan_id=value.validation_plan_id,
                version=value.version,
                stages=list(value.stages),
                eligible_scope=value.eligible_scope,
                excluded_scope=value.excluded_scope,
                success_criteria=list(value.success_criteria),
                rollback_criteria=list(value.rollback_criteria),
                created_by=value.created_by,
                created_at=value.created_at,
                content_hash=value.content_hash,
            )
        )

    async def list_rollout_plans(self, proposal_id: uuid.UUID) -> tuple[RolloutPlan, ...]:
        return tuple(
            self._rollout_plan(item)
            for item in await self._models(ChangeRolloutPlanModel, proposal_id)
        )

    async def add_rollback_plan(self, value: RollbackPlan) -> None:
        self._session.add(
            ChangeRollbackPlanModel(
                id=value.id,
                proposal_id=value.proposal_id,
                transformation_plan_id=value.transformation_plan_id,
                validation_plan_id=value.validation_plan_id,
                version=value.version,
                rollback_steps=list(value.rollback_steps),
                trigger_criteria=list(value.trigger_criteria),
                recovery_time_objective_seconds=value.recovery_time_objective_seconds,
                created_by=value.created_by,
                created_at=value.created_at,
                content_hash=value.content_hash,
            )
        )
        for evidence in value.evidence:
            self._add_evidence(value.proposal_id, "rollback_plan", value.id, evidence)

    async def list_rollback_plans(self, proposal_id: uuid.UUID) -> tuple[RollbackPlan, ...]:
        models = await self._models(ChangeRollbackPlanModel, proposal_id)
        return tuple([await self._rollback_plan(item) for item in models])

    async def append_decision(self, value: ChangeDecision) -> None:
        results: list[dict[str, Any]] = []
        for result in value.validation_results:
            results.append(
                {
                    "requirement_code": result.requirement_code,
                    "passed": result.passed,
                    "evidence": [_evidence_payload(item) for item in result.evidence],
                }
            )
            for evidence in result.evidence:
                self._add_evidence(value.proposal_id, "decision", value.id, evidence)
        self._session.add(
            ChangeDecisionModel(
                id=value.id,
                proposal_id=value.proposal_id,
                change_set_id=value.change_set_id,
                impact_assessment_id=value.impact_assessment_id,
                validation_plan_id=value.validation_plan_id,
                decision=value.decision,
                decided_by=value.decided_by,
                actor_roles=list(value.actor_roles),
                reason=value.reason,
                validation_results=results,
                decided_at=value.decided_at,
                content_hash=value.content_hash,
            )
        )

    async def list_decisions(self, proposal_id: uuid.UUID) -> tuple[ChangeDecision, ...]:
        models = await self._models(ChangeDecisionModel, proposal_id)
        return tuple(self._decision(item) for item in models)

    async def append_observation(self, value: ChangeObservation) -> None:
        self._session.add(
            ChangeObservationModel(
                id=value.id,
                proposal_id=value.proposal_id,
                decision_id=value.decision_id,
                version=value.version,
                observed_by=value.observed_by,
                observation_window_start=value.observation_window_start,
                observation_window_end=value.observation_window_end,
                metrics=value.metrics,
                findings=list(value.findings),
                created_at=value.created_at,
                content_hash=value.content_hash,
            )
        )
        for evidence in value.evidence:
            self._add_evidence(value.proposal_id, "observation", value.id, evidence)

    async def get_observation(self, value_id: uuid.UUID) -> ChangeObservation | None:
        value = await self._session.get(ChangeObservationModel, value_id)
        return await self._observation(value) if value else None

    async def list_observations(self, proposal_id: uuid.UUID) -> tuple[ChangeObservation, ...]:
        models = await self._models(ChangeObservationModel, proposal_id)
        return tuple([await self._observation(item) for item in models])

    async def append_outcome(self, value: ChangeOutcome) -> None:
        self._session.add(
            ChangeOutcomeModel(
                id=value.id,
                proposal_id=value.proposal_id,
                observation_id=value.observation_id,
                disposition=value.disposition,
                decided_by=value.decided_by,
                reason=value.reason,
                decided_at=value.decided_at,
                content_hash=value.content_hash,
            )
        )
        for evidence in value.evidence:
            self._add_evidence(value.proposal_id, "outcome", value.id, evidence)

    async def list_outcomes(self, proposal_id: uuid.UUID) -> tuple[ChangeOutcome, ...]:
        models = await self._models(ChangeOutcomeModel, proposal_id)
        return tuple([await self._outcome(item) for item in models])

    async def timeline(self, proposal_id: uuid.UUID) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        proposal = await self.get_proposal(proposal_id)
        if proposal is None:
            return records
        records.append(
            {
                "type": "proposal",
                "id": str(proposal.id),
                "at": proposal.created_at,
                "status": proposal.status,
                "content_hash": proposal.content_hash,
            }
        )
        for change_set in await self.list_change_sets(proposal_id):
            records.append(
                {
                    "type": "change_set",
                    "id": str(change_set.id),
                    "at": change_set.created_at,
                    "version": change_set.version,
                    "content_hash": change_set.content_hash,
                }
            )
        for plan in await self.list_transformation_plans(proposal_id):
            records.append(
                {
                    "type": "transformation_plan",
                    "id": str(plan.id),
                    "at": plan.created_at,
                    "version": plan.version,
                    "content_hash": plan.content_hash,
                }
            )
        for assessment in await self.list_impact_assessments(proposal_id):
            records.append(
                {
                    "type": "impact_assessment",
                    "id": str(assessment.id),
                    "at": assessment.created_at,
                    "version": assessment.version,
                    "unknown_impact": assessment.has_unknown_impact,
                    "content_hash": assessment.content_hash,
                }
            )
        for validation_plan in await self.list_validation_plans(proposal_id):
            records.append(
                {
                    "type": "validation_plan",
                    "id": str(validation_plan.id),
                    "at": validation_plan.created_at,
                    "version": validation_plan.version,
                    "content_hash": validation_plan.content_hash,
                }
            )
        for rollout_plan in await self.list_rollout_plans(proposal_id):
            records.append(
                {
                    "type": "rollout_plan",
                    "id": str(rollout_plan.id),
                    "at": rollout_plan.created_at,
                    "version": rollout_plan.version,
                    "content_hash": rollout_plan.content_hash,
                }
            )
        for rollback_plan in await self.list_rollback_plans(proposal_id):
            records.append(
                {
                    "type": "rollback_plan",
                    "id": str(rollback_plan.id),
                    "at": rollback_plan.created_at,
                    "version": rollback_plan.version,
                    "content_hash": rollback_plan.content_hash,
                }
            )
        for decision in await self.list_decisions(proposal_id):
            records.append(
                {
                    "type": "decision",
                    "id": str(decision.id),
                    "at": decision.decided_at,
                    "decision": decision.decision,
                    "content_hash": decision.content_hash,
                }
            )
        for observation in await self.list_observations(proposal_id):
            records.append(
                {
                    "type": "observation",
                    "id": str(observation.id),
                    "at": observation.created_at,
                    "version": observation.version,
                    "content_hash": observation.content_hash,
                }
            )
        for outcome in await self.list_outcomes(proposal_id):
            records.append(
                {
                    "type": "outcome",
                    "id": str(outcome.id),
                    "at": outcome.decided_at,
                    "disposition": outcome.disposition,
                    "content_hash": outcome.content_hash,
                }
            )
        return sorted(records, key=lambda item: (item["at"], item["type"], item["id"]))

    async def commit(self) -> None:
        await self._session.commit()

    async def _models(self, model_type: type[Any], proposal_id: uuid.UUID) -> list[Any]:
        result = await self._session.execute(
            select(model_type).where(model_type.proposal_id == proposal_id).order_by(model_type.id)
        )
        return list(result.scalars().all())

    def _add_evidence(
        self, proposal_id: uuid.UUID, owner_type: str, owner_id: uuid.UUID, value: EvidenceReference
    ) -> None:
        self._session.add(
            ChangeEvidenceModel(
                proposal_id=proposal_id,
                owner_type=owner_type,
                owner_id=owner_id,
                artifact_id=value.artifact_id,
                artifact_content_hash=value.content_hash,
                evidence_type=value.evidence_type,
            )
        )

    async def _evidence(
        self, owner_type: str, owner_id: uuid.UUID
    ) -> tuple[EvidenceReference, ...]:
        result = await self._session.execute(
            select(ChangeEvidenceModel).where(
                ChangeEvidenceModel.owner_type == owner_type,
                ChangeEvidenceModel.owner_id == owner_id,
            )
        )
        return tuple(
            EvidenceReference(
                artifact_id=item.artifact_id,
                content_hash=item.artifact_content_hash,
                evidence_type=item.evidence_type,
            )
            for item in result.scalars().all()
        )

    @staticmethod
    def _change_set(value: ChangeSetModel) -> ChangeSet:
        return ChangeSet(
            id=value.id,
            proposal_id=value.proposal_id,
            version=value.version,
            operations=tuple(
                ChangeOperation(
                    operation_type=item["operation_type"],
                    target=_reference(item["target"]),
                    before_hash=item.get("before_hash"),
                    candidate_hash=item["candidate_hash"],
                    description=item["description"],
                )
                for item in value.operations
            ),
            created_by=value.created_by,
            created_at=value.created_at,
            content_hash=value.content_hash,
        )

    async def _transformation_plan(
        self, value: ChangeTransformationPlanModel
    ) -> TransformationPlan:
        return TransformationPlan(
            id=value.id,
            proposal_id=value.proposal_id,
            change_set_id=value.change_set_id,
            version=value.version,
            strategy=value.strategy,
            steps=tuple(value.steps),
            prerequisites=tuple(value.prerequisites),
            evidence=await self._evidence("transformation_plan", value.id),
            created_by=value.created_by,
            created_at=value.created_at,
            content_hash=value.content_hash,
        )

    @staticmethod
    def _assessment(value: ChangeImpactAssessmentModel) -> ImpactAssessment:
        return ImpactAssessment(
            id=value.id,
            proposal_id=value.proposal_id,
            change_set_id=value.change_set_id,
            version=value.version,
            assessed_by=value.assessed_by,
            direct_impacts=tuple(_reference(item) for item in value.direct_impacts),
            indirect_impacts=tuple(_reference(item) for item in value.indirect_impacts),
            findings=tuple(
                ImpactFinding(
                    code=item["code"],
                    dimension=item["dimension"],
                    knowledge=ImpactKnowledge(item["knowledge"]),
                    severity=ChangeRisk(item["severity"]),
                    message=item["message"],
                    affected_entities=tuple(
                        _reference(ref) for ref in item.get("affected_entities", [])
                    ),
                )
                for item in value.findings
            ),
            required_approval_roles=tuple(value.required_approval_roles),
            required_tests=tuple(value.required_tests),
            estimated_blast_radius=ChangeRisk(value.estimated_blast_radius),
            rollback_complexity=ChangeRisk(value.rollback_complexity),
            confidence=value.confidence,
            created_at=value.created_at,
            content_hash=value.content_hash,
        )

    @staticmethod
    def _plan(value: ChangeValidationPlanModel) -> ValidationPlan:
        return ValidationPlan(
            id=value.id,
            proposal_id=value.proposal_id,
            impact_assessment_id=value.impact_assessment_id,
            version=value.version,
            requirements=tuple(ValidationRequirement(**item) for item in value.requirements),
            rollback_evidence_required=value.rollback_evidence_required,
            created_by=value.created_by,
            created_at=value.created_at,
            content_hash=value.content_hash,
        )

    @staticmethod
    def _rollout_plan(value: ChangeRolloutPlanModel) -> RolloutPlan:
        return RolloutPlan(
            id=value.id,
            proposal_id=value.proposal_id,
            transformation_plan_id=value.transformation_plan_id,
            validation_plan_id=value.validation_plan_id,
            version=value.version,
            stages=tuple(value.stages),
            eligible_scope=value.eligible_scope,
            excluded_scope=value.excluded_scope,
            success_criteria=tuple(value.success_criteria),
            rollback_criteria=tuple(value.rollback_criteria),
            created_by=value.created_by,
            created_at=value.created_at,
            content_hash=value.content_hash,
        )

    async def _rollback_plan(self, value: ChangeRollbackPlanModel) -> RollbackPlan:
        return RollbackPlan(
            id=value.id,
            proposal_id=value.proposal_id,
            transformation_plan_id=value.transformation_plan_id,
            validation_plan_id=value.validation_plan_id,
            version=value.version,
            rollback_steps=tuple(value.rollback_steps),
            trigger_criteria=tuple(value.trigger_criteria),
            recovery_time_objective_seconds=value.recovery_time_objective_seconds,
            evidence=await self._evidence("rollback_plan", value.id),
            created_by=value.created_by,
            created_at=value.created_at,
            content_hash=value.content_hash,
        )

    @staticmethod
    def _decision(value: ChangeDecisionModel) -> ChangeDecision:
        return ChangeDecision(
            id=value.id,
            proposal_id=value.proposal_id,
            change_set_id=value.change_set_id,
            impact_assessment_id=value.impact_assessment_id,
            validation_plan_id=value.validation_plan_id,
            decision=ChangeDecisionType(value.decision),
            decided_by=value.decided_by,
            actor_roles=tuple(value.actor_roles),
            reason=value.reason,
            validation_results=tuple(
                ValidationResult(
                    requirement_code=item["requirement_code"],
                    passed=item["passed"],
                    evidence=tuple(
                        EvidenceReference(
                            artifact_id=uuid.UUID(str(ref["artifact_id"])),
                            content_hash=ref["content_hash"],
                            evidence_type=ref["evidence_type"],
                        )
                        for ref in item.get("evidence", [])
                    ),
                )
                for item in value.validation_results
            ),
            decided_at=value.decided_at,
            content_hash=value.content_hash,
        )

    async def _observation(self, value: ChangeObservationModel) -> ChangeObservation:
        return ChangeObservation(
            id=value.id,
            proposal_id=value.proposal_id,
            decision_id=value.decision_id,
            version=value.version,
            observed_by=value.observed_by,
            observation_window_start=value.observation_window_start,
            observation_window_end=value.observation_window_end,
            metrics=value.metrics,
            findings=tuple(value.findings),
            evidence=await self._evidence("observation", value.id),
            created_at=value.created_at,
            content_hash=value.content_hash,
        )

    async def _outcome(self, value: ChangeOutcomeModel) -> ChangeOutcome:
        return ChangeOutcome(
            id=value.id,
            proposal_id=value.proposal_id,
            observation_id=value.observation_id,
            disposition=ChangeOutcomeDisposition(value.disposition),
            decided_by=value.decided_by,
            reason=value.reason,
            evidence=await self._evidence("outcome", value.id),
            decided_at=value.decided_at,
            content_hash=value.content_hash,
        )


class SqlAlchemyChangeAuditSink:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, record: ChangeAuditRecord) -> None:
        self._session.add(
            AuditEventModel(
                id=uuid.uuid4(),
                project_id=None,
                event_type=record.event_type,
                actor_type="governance_actor",
                actor_id=record.actor_id,
                payload={
                    "aggregate_id": str(record.aggregate_id),
                    "occurred_at": record.occurred_at.isoformat(),
                    "payload_hash": record.payload_hash,
                    **record.payload,
                },
            )
        )
