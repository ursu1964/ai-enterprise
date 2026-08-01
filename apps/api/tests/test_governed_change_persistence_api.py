from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from ai_enterprise.api.change_management_authority import governed_change_actor
from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.routes.change_management import router
from ai_enterprise.application.change_management.dto import CreateChangeProposal
from ai_enterprise.domain.change_management.entities import (
    ChangeOperation,
    ChangeSet,
    EntityReference,
    ImpactAssessment,
    ImpactFinding,
)
from ai_enterprise.domain.change_management.enums import (
    ChangeRisk,
    ImpactKnowledge,
)
from ai_enterprise.infrastructure.change_management.models import (
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
from ai_enterprise.infrastructure.change_management.repository import (
    SqlAlchemyGovernedChangeRepository,
)
from ai_enterprise.main import app


def test_bounded_models_define_expected_tables() -> None:
    assert {
        ChangeProposalModel.__tablename__,
        ChangeEvidenceModel.__tablename__,
        ChangeSetModel.__tablename__,
        ChangeTransformationPlanModel.__tablename__,
        ChangeImpactAssessmentModel.__tablename__,
        ChangeValidationPlanModel.__tablename__,
        ChangeRolloutPlanModel.__tablename__,
        ChangeRollbackPlanModel.__tablename__,
        ChangeDecisionModel.__tablename__,
        ChangeObservationModel.__tablename__,
        ChangeOutcomeModel.__tablename__,
    } == {
        "change_proposals",
        "change_evidence",
        "change_sets",
        "change_transformation_plans",
        "change_impact_assessments",
        "change_validation_plans",
        "change_rollout_plans",
        "change_rollback_plans",
        "change_decisions",
        "change_observations",
        "change_outcomes",
    }
    assert ChangeDecisionModel.__table__.c.content_hash.unique is True
    assert ChangeTransformationPlanModel.__table__.c.content_hash.unique is True
    assert ChangeRolloutPlanModel.__table__.c.content_hash.unique is True
    assert ChangeRollbackPlanModel.__table__.c.content_hash.unique is True
    assert ChangeObservationModel.__table__.c.content_hash.unique is True
    assert ChangeOutcomeModel.__table__.c.content_hash.unique is True
    assert "updated_at" not in ChangeDecisionModel.__table__.c


def test_repository_round_trips_change_set_model() -> None:
    target = EntityReference("policy", uuid4(), "3")
    domain = ChangeSet(
        id=uuid4(),
        proposal_id=uuid4(),
        version=2,
        operations=(ChangeOperation("replace", target, "a" * 64, "b" * 64, "Candidate"),),
        created_by="alice",
        created_at=datetime.now(UTC),
        content_hash="c" * 64,
    )
    model = ChangeSetModel(
        id=domain.id,
        proposal_id=domain.proposal_id,
        version=domain.version,
        operations=[
            {
                "operation_type": "replace",
                "target": {
                    "entity_type": "policy",
                    "entity_id": str(target.entity_id),
                    "entity_version": "3",
                },
                "before_hash": "a" * 64,
                "candidate_hash": "b" * 64,
                "description": "Candidate",
            }
        ],
        created_by="alice",
        created_at=domain.created_at,
        content_hash=domain.content_hash,
    )
    assert SqlAlchemyGovernedChangeRepository._change_set(model) == domain


def test_repository_preserves_unknown_impact() -> None:
    now = datetime.now(UTC)
    model = ChangeImpactAssessmentModel(
        id=uuid4(),
        proposal_id=uuid4(),
        change_set_id=uuid4(),
        version=1,
        assessed_by="assessor",
        direct_impacts=[],
        indirect_impacts=[],
        findings=[
            {
                "code": "DEPENDENCY_IMPACT_UNKNOWN",
                "dimension": "dependencies",
                "knowledge": "unknown",
                "severity": "critical",
                "message": "Unknown",
                "affected_entities": [],
            }
        ],
        required_approval_roles=["change_approver"],
        required_tests=["impact"],
        estimated_blast_radius="critical",
        rollback_complexity="high",
        confidence=0.1,
        created_at=now,
        content_hash="d" * 64,
    )
    value: ImpactAssessment = SqlAlchemyGovernedChangeRepository._assessment(model)
    assert value.has_unknown_impact is True
    assert value.findings == (
        ImpactFinding(
            "DEPENDENCY_IMPACT_UNKNOWN",
            "dependencies",
            ImpactKnowledge.UNKNOWN,
            ChangeRisk.CRITICAL,
            "Unknown",
        ),
    )


def test_actor_header_adapter_enforces_capability_and_human_decision() -> None:
    value = governed_change_actor(Actor("alice", "human", "change_approver"), "change.decide")
    assert value.subject == "alice"
    with pytest.raises(HTTPException) as wrong_role:
        governed_change_actor(Actor("alice", "human", "change_proposer"), "change.decide")
    assert wrong_role.value.status_code == 403
    with pytest.raises(HTTPException, match="human"):
        governed_change_actor(Actor("agent", "agent", "change_approver"), "change.decide")
    assert (
        governed_change_actor(Actor("observer", "human", "change_observer"), "change.observe")
        .subject
        == "observer"
    )
    assert (
        governed_change_actor(Actor("planner", "agent", "change_planner"), "change.plan").subject
        == "planner"
    )
    assert (
        governed_change_actor(Actor("planner", "human", "change_planner"), "change.read").subject
        == "planner"
    )
    with pytest.raises(HTTPException, match="human"):
        governed_change_actor(Actor("agent", "agent", "change_approver"), "change.outcome")


def test_api_surface_has_planning_but_no_activation_or_rollout_execution_route() -> None:
    paths = {route.path for route in router.routes if isinstance(route, APIRoute)}
    assert "/change-proposals" in paths
    assert "/change-proposals/{proposal_id}/submit" in paths
    assert "/change-proposals/{proposal_id}/transformation-plans" in paths
    assert "/change-proposals/{proposal_id}/impact-assessments" in paths
    assert "/change-proposals/{proposal_id}/validation-plans" in paths
    assert "/change-proposals/{proposal_id}/rollout-plans" in paths
    assert "/change-proposals/{proposal_id}/rollback-plans" in paths
    assert "/change-proposals/{proposal_id}/decisions" in paths
    assert "/change-proposals/{proposal_id}/observations" in paths
    assert "/change-proposals/{proposal_id}/outcomes" in paths
    assert "/change-proposals/{proposal_id}/timeline" in paths
    assert all("activat" not in path for path in paths)
    assert all("rollout" not in path or "rollout-plans" in path for path in paths)
    registered = set(app.openapi()["paths"])
    assert "/api/v1/change-proposals" in registered
    assert all(
        not (
            path.startswith("/api/v1/change-proposals")
            and (
                "activat" in path
                or ("rollout" in path and "rollout-plans" not in path)
            )
        )
        for path in registered
    )


def test_request_contract_does_not_accept_actor_or_activation_fields() -> None:
    assert "proposed_by" not in CreateChangeProposal.model_fields
    assert "status" not in CreateChangeProposal.model_fields
    assert "activate" not in CreateChangeProposal.model_fields
    assert "rollout" not in CreateChangeProposal.model_fields


def test_models_are_not_added_to_central_models_source() -> None:
    assert ChangeProposalModel.__module__.endswith("change_management.models")
