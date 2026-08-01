import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ai_enterprise.api.architecture_schemas import FindingRequest
from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.routes.architecture_governance import (
    architecture_provider_readiness,
    conflict,
)
from ai_enterprise.application.architecture_service import (
    ArchitectureAuthorizationError,
    ArchitectureGovernanceError,
    _require,
)
from ai_enterprise.domain.architecture.enums import (
    ArchitectureArtifactStatus,
    ArchitectureReviewDecision,
    ArchitectureReviewStatus,
    ArchitectureRunStatus,
)
from ai_enterprise.domain.architecture.state_machine import (
    ARTIFACT_TRANSITIONS,
    REVIEW_TRANSITIONS,
    RUN_TRANSITIONS,
    InvalidArchitectureTransition,
    require_transition,
)
from ai_enterprise.infrastructure.database.models import Base


def test_architecture_state_machines_reject_illegal_shortcuts() -> None:
    require_transition(ArchitectureRunStatus.READY, ArchitectureRunStatus.RUNNING, RUN_TRANSITIONS)
    require_transition(
        ArchitectureArtifactStatus.DRAFT,
        ArchitectureArtifactStatus.UNDER_REVIEW,
        ARTIFACT_TRANSITIONS,
    )
    require_transition(
        ArchitectureReviewStatus.OPEN,
        ArchitectureReviewStatus.COMPLETED,
        REVIEW_TRANSITIONS,
    )
    with pytest.raises(InvalidArchitectureTransition):
        require_transition(
            ArchitectureArtifactStatus.DRAFT,
            ArchitectureArtifactStatus.APPROVED,
            ARTIFACT_TRANSITIONS,
        )


def test_review_decision_is_recommendation_not_final_approval() -> None:
    assert ArchitectureReviewDecision.RECOMMEND_APPROVAL == "recommend_approval"
    with pytest.raises(ValueError):
        ArchitectureReviewDecision("approve")


def test_blocking_finding_requires_bounded_structured_identity() -> None:
    finding = FindingRequest(
        finding_key="SEC-001",
        severity="high",
        category="security",
        description="Authentication boundary is incomplete.",
        required_change="Define the authentication boundary.",
        blocking=True,
    )
    assert finding.blocking
    with pytest.raises(ValidationError):
        FindingRequest(
            finding_key="bad key",
            severity="high",
            category="security",
            description="Invalid stable key.",
        )


def test_capability_and_human_authority_fail_closed() -> None:
    actor = Actor(
        subject="agent-1",
        actor_type="agent",
        role="architecture_approver",
        capabilities=frozenset({"architecture.approve"}),
        trusted=True,
    )
    with pytest.raises(ArchitectureGovernanceError, match="human"):
        _require(actor, "architecture_approver", "architecture.approve")
    with pytest.raises(ArchitectureGovernanceError, match="Missing capability"):
        _require(
            Actor("human-1", "human", "architecture_approver", frozenset({"other"})),
            "architecture_approver",
            "architecture.approve",
        )


def test_architecture_tables_are_bounded_and_registered() -> None:
    expected = {
        "architecture_runs",
        "architecture_artifacts",
        "architecture_reviews",
        "architecture_review_findings",
        "architecture_revision_requests",
        "architecture_approvals",
    }
    assert expected.issubset(Base.metadata.tables)
    approval = Base.metadata.tables["architecture_approvals"]
    assert approval.c.approved_checksum.type.length == 64
    assert approval.c.approving_review_id.unique


def test_approval_identity_cannot_alias_review_identity() -> None:
    reviewer = uuid.uuid4()
    approver = uuid.uuid4()
    assert reviewer != approver


def test_api_error_mapping_distinguishes_authority_and_conflict() -> None:
    assert conflict(ArchitectureAuthorizationError("denied")).status_code == 403
    assert conflict(ArchitectureGovernanceError("stale checksum")).status_code == 409


@pytest.mark.asyncio
async def test_scripted_provider_readiness_is_configuration_only() -> None:
    settings = SimpleNamespace(
        architecture_provider="scripted",
        architecture_model_name="fake-architecture-v1",
        ollama_base_url="http://localhost:11434",
        architecture_temperature=0.0,
        architecture_timeout_seconds=30,
        architecture_max_tokens=1024,
    )
    with patch(
        "ai_enterprise.api.routes.architecture_governance.get_settings",
        return_value=settings,
    ):
        result = await architecture_provider_readiness()
    assert result == {
        "status": "ready",
        "provider": "scripted",
        "model": "deterministic-fake",
    }


def test_legacy_work_package_flow_cannot_bypass_architecture_approval() -> None:
    source = (
        Path(__file__).parents[1] / "src/ai_enterprise/application/project_workflow.py"
    ).read_text(encoding="utf-8")
    method = source[source.index("async def queue_work_package_planning") :]
    assert "ProjectStatus.ARCHITECTURE_APPROVED" in method[:2000]
    assert "_get_latest_approved_artifact" in method[:2000]
