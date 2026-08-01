from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ai_enterprise.application.performance import PerformanceEvaluationService
from ai_enterprise.domain.performance.certification import (
    CapabilityAssessment,
    CapabilityLevel,
    CertificationBoardDecision,
    CertificationGovernanceError,
    CertificationPolicy,
    issue_certificate,
    recommend_certification,
)
from ai_enterprise.domain.performance.evidence import (
    CompleteEvidenceWindow,
    EvidenceInvariantError,
    WorkflowEvidence,
    validate_evidence,
)
from ai_enterprise.domain.performance.learning import (
    LearningProposal,
    PromptChangeApproval,
    PromptVersion,
    create_prompt_successor,
)
from ai_enterprise.domain.performance.metrics import MetricKey, MetricsEngine, assess_assignment

NOW = datetime(2026, 8, 1, tzinfo=UTC)


def _evidence(
    *, agent_id=None, assignment_id=None, accepted=True, revisions=0, rollback=False
) -> WorkflowEvidence:
    return WorkflowEvidence.create(
        id=uuid4(),
        workflow_id=uuid4(),
        workflow_type="implementation",
        agent_id=agent_id or uuid4(),
        crew_id=uuid4(),
        assignment_id=assignment_id or uuid4(),
        task_id=uuid4(),
        duration_seconds=120,
        cpu_seconds=30,
        memory_peak_bytes=1024,
        tests_passed=10,
        tests_failed=0,
        review_findings=2,
        correct_review_findings=2,
        false_negative_findings=0,
        accepted=accepted,
        integration_success=accepted,
        rollback=rollback,
        retry_count=0,
        revision_count=revisions,
        scope_violations=0,
        architecture_violations=0,
        requirements_total=4,
        requirements_verified=4,
        prompt_version_id=uuid4(),
        audit_record_id=uuid4(),
        occurred_at=NOW,
    )


def _assess(agent, capability, records, policy_version):
    return PerformanceEvaluationService().assess_agent(
        agent_id=agent,
        capability=capability,
        evidence=records,
        expected_workflow_ids=frozenset(record.workflow_id for record in records),
        policy_version=policy_version,
    )


def test_evidence_is_immutable_hash_bound_and_rejects_tampering() -> None:
    evidence = _evidence()
    validate_evidence(evidence)
    with pytest.raises(FrozenInstanceError):
        evidence.accepted = False  # type: ignore[misc]
    with pytest.raises(EvidenceInvariantError, match="hash mismatch"):
        validate_evidence(replace(evidence, accepted=False))


def test_standard_metrics_are_deterministic_and_traceable_for_agents_and_crews() -> None:
    agent = uuid4()
    records = (_evidence(agent_id=agent), _evidence(agent_id=agent, accepted=False, revisions=2))
    first = MetricsEngine().derive(subject_type="agent", subject_id=agent, evidence=records)
    second = MetricsEngine().derive(
        subject_type="agent", subject_id=agent, evidence=tuple(reversed(records))
    )
    assert first == second
    acceptance = next(metric for metric in first if metric.key is MetricKey.ACCEPTANCE_RATE)
    assert str(acceptance.value) == "0.5000"
    assert set(acceptance.evidence_ids) == {record.id for record in records}
    assert _assess(agent, "implement", records, "cert-v1").evidence_count == 2


def test_assignment_quality_uses_observable_outcomes_only() -> None:
    assignment = uuid4()
    records = tuple(_evidence(assignment_id=assignment) for _ in range(3))
    quality = assess_assignment(assignment, records)
    assert quality.band == "excellent"
    assert len(quality.evidence_ids) == 3


def test_certification_is_a_recommendation_and_cannot_change_authority() -> None:
    agent = uuid4()
    records = tuple(_evidence(agent_id=agent) for _ in range(3))
    assessment = _assess(agent, "review", records, "cert-v1")
    policy = CertificationPolicy(
        "cert-v1",
        "review",
        CapabilityLevel.SENIOR,
        3,
        ((MetricKey.ACCEPTANCE_RATE, "0.95"), (MetricKey.REVIEW_PRECISION, "0.95")),
        ((MetricKey.ROLLBACK_RATE, "0.01"),),
        365,
    )
    recommendation = recommend_certification(
        recommendation_id=uuid4(), assessment=assessment, policy=policy, now=NOW
    )
    assert recommendation.eligible and recommendation.recommendation_only
    with pytest.raises(CertificationGovernanceError, match="human approval"):
        issue_certificate(
            certificate_id=uuid4(),
            recommendation=recommendation,
            decision=CertificationBoardDecision(uuid4(), uuid4(), "approve", uuid4(), NOW, None),
            expires_at=NOW + timedelta(days=365),
        )


def test_human_board_issues_expiring_certificate_and_recertification_supersedes() -> None:
    agent = uuid4()
    records = tuple(_evidence(agent_id=agent) for _ in range(2))
    assessment = _assess(agent, "review", records, "cert-v1")
    recommendation = recommend_certification(
        recommendation_id=uuid4(),
        assessment=assessment,
        policy=CertificationPolicy(
            "cert-v1",
            "review",
            CapabilityLevel.CERTIFIED,
            2,
            ((MetricKey.ACCEPTANCE_RATE, "1"),),
            (),
            30,
        ),
        now=NOW,
    )
    decision = CertificationBoardDecision(uuid4(), recommendation.id, "approve", uuid4(), NOW, None)
    certificate = issue_certificate(
        certificate_id=uuid4(),
        recommendation=recommendation,
        decision=decision,
        expires_at=NOW + timedelta(days=30),
    )
    assert certificate.is_active_at(NOW + timedelta(days=29))
    assert not certificate.is_active_at(NOW + timedelta(days=30))


def test_learning_proposal_neither_mutates_nor_activates_prompt() -> None:
    prompt = PromptVersion(
        uuid4(),
        "review.system",
        "1.0.0",
        "a" * 64,
        ("local-model",),
        "review-output-v1",
        None,
        uuid4(),
        NOW,
    )
    proposal = LearningProposal(
        uuid4(),
        "Check dependency boundaries",
        "Repeated misses",
        "Add deterministic dependency verification",
        (uuid4(),),
        prompt.id,
        "proposed",
        NOW,
        "candidate prompt text",
    )
    assert proposal.status == "proposed"
    approved = replace(proposal, status="approved")
    approval = PromptChangeApproval(uuid4(), approved.id, uuid4(), NOW)
    successor = create_prompt_successor(
        version_id=uuid4(),
        predecessor=prompt,
        proposal=approved,
        semantic_version="1.1.0",
        content_hash="b" * 64,
        approval=approval,
    )
    assert successor.predecessor_id == prompt.id
    assert prompt.semantic_version == "1.0.0"


def test_learning_without_evidence_and_ineligible_certification_fail_closed() -> None:
    with pytest.raises(ValueError, match="evidence"):
        LearningProposal(
            uuid4(), "Title", "Observation", "Recommendation", (), uuid4(), "proposed", NOW
        )
    assessment = _assess(uuid4(), "architecture", (), "v1")
    recommendation = recommend_certification(
        recommendation_id=uuid4(),
        assessment=assessment,
        policy=CertificationPolicy(
            "v1",
            "architecture",
            CapabilityLevel.SENIOR,
            200,
            ((MetricKey.ACCEPTANCE_RATE, "0.98"),),
            (),
            365,
        ),
        now=NOW,
    )
    assert not recommendation.eligible


def test_replay_wrong_subject_reidentification_and_negative_suppression_fail_closed() -> None:
    agent = uuid4()
    record = _evidence(agent_id=agent, accepted=False)
    with pytest.raises(EvidenceInvariantError, match="duplicate"):
        MetricsEngine().derive(subject_type="agent", subject_id=agent, evidence=(record, record))
    with pytest.raises(EvidenceInvariantError, match="subject"):
        MetricsEngine().derive(subject_type="agent", subject_id=uuid4(), evidence=(record,))
    with pytest.raises(EvidenceInvariantError, match="hash mismatch"):
        validate_evidence(replace(record, id=uuid4()))
    with pytest.raises(EvidenceInvariantError, match="incomplete"):
        CompleteEvidenceWindow.build((), expected_workflow_ids=frozenset({record.workflow_id}))


def test_forged_assessment_manifest_cannot_produce_eligible_recommendation() -> None:
    agent = uuid4()
    record = _evidence(agent_id=agent)
    legitimate = _assess(agent, "review", (record,), "cert-v1")
    forged = CapabilityAssessment(
        legitimate.agent_id,
        legitimate.capability,
        1000,
        legitimate.metrics,
        legitimate.evidence_ids,
        legitimate.policy_version,
        legitimate.evidence_window_hash,
    )
    recommendation = recommend_certification(
        recommendation_id=uuid4(),
        assessment=forged,
        policy=CertificationPolicy("cert-v1", "review", CapabilityLevel.SENIOR, 100, (), (), 30),
        now=NOW,
    )
    assert not recommendation.eligible
    assert "CERT-EVIDENCE-MANIFEST-INVALID" in recommendation.findings


def test_board_chronology_and_recommendation_only_flag_cannot_be_bypassed() -> None:
    agent = uuid4()
    assessment = _assess(agent, "review", (_evidence(agent_id=agent),), "cert-v1")
    recommendation = recommend_certification(
        recommendation_id=uuid4(),
        assessment=assessment,
        policy=CertificationPolicy("cert-v1", "review", CapabilityLevel.CERTIFIED, 1, (), (), 30),
        now=NOW,
    )
    early = CertificationBoardDecision(
        uuid4(), recommendation.id, "approve", uuid4(), NOW - timedelta(seconds=1), None
    )
    with pytest.raises(CertificationGovernanceError, match="predate"):
        issue_certificate(
            certificate_id=uuid4(),
            recommendation=recommendation,
            decision=early,
            expires_at=NOW + timedelta(days=30),
        )
    with pytest.raises(CertificationGovernanceError):
        issue_certificate(
            certificate_id=uuid4(),
            recommendation=replace(recommendation, recommendation_only=False),
            decision=replace(early, decided_at=NOW),
            expires_at=NOW + timedelta(days=30),
        )


def test_prompt_release_requires_matching_approved_proposal() -> None:
    prompt = PromptVersion(
        uuid4(), "review.system", "1.0.0", "a" * 64, ("local",), "v1", None, uuid4(), NOW
    )
    proposal = LearningProposal(
        uuid4(),
        "Improve review",
        "missed issue",
        "add check",
        (uuid4(),),
        prompt.id,
        "proposed",
        NOW,
    )
    with pytest.raises(ValueError, match="approved"):
        create_prompt_successor(
            version_id=uuid4(),
            predecessor=prompt,
            proposal=proposal,
            semantic_version="1.1.0",
            content_hash="b" * 64,
            approval=PromptChangeApproval(uuid4(), proposal.id, uuid4(), NOW),
        )
