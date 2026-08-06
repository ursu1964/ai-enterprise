import pytest
from pydantic import ValidationError

from ai_enterprise.domain.r8_ugeif import (
    UgeifAssessmentStatus,
    UgeifAssetKind,
    UgeifCertificationStatus,
    UgeifChangeType,
    UgeifLearningSourceStatus,
    UgeifLifecycleState,
    UgeifSimulationStatus,
    ai_learning_boundary,
    certification,
    change_proposal,
    compliance_framework_pack,
    decide_change_proposal,
    federated_governance_sync,
    feedback_loop_record,
    governance_assessment,
    impact_analysis,
    industry_framework_pack,
    knowledge_generalization,
    marketplace_asset_certification,
    operational_recommendation,
    predictive_analysis,
    quality_scorecard,
    reusable_pattern,
    risk_profile,
    simulation_report,
    technology_evolution_plan,
    timeline_entry,
    validation_report,
    version_graph_snapshot,
)


def test_r8_governance_validation_quality_and_certification_are_deterministic() -> None:
    assessment = governance_assessment(
        index=1,
        project_id="project-1",
        manifest_version="manifest-1",
        scores={"security": 72.0, "business": 91.0},
        recommendations=("raise security score", "raise security score"),
    )
    validation = validation_report(
        index=1,
        project_id="project-1",
        manifest_version="manifest-1",
        findings_by_category={"security_policies": ("missing control",)},
    )
    quality = quality_scorecard(
        index=1,
        project_id="project-1",
        scores={"test_coverage": 82.0, "observability_completeness": 78.0},
    )
    cert = certification(
        index=1,
        project_id="project-1",
        deployment_hash="a" * 64,
        checks={"traceability": True, "reproducibility": True},
        evidence_hashes=("b" * 64, "b" * 64),
    )

    assert assessment.status is UgeifAssessmentStatus.NEEDS_ATTENTION
    assert assessment.domains[0].value == "business"
    assert assessment.recommendations == ("raise security score",)
    assert validation.status is UgeifAssessmentStatus.BLOCKED
    assert quality.status is UgeifAssessmentStatus.NEEDS_ATTENTION
    assert cert.status is UgeifCertificationStatus.CERTIFIED
    assert cert.evidence_hashes == ("b" * 64,)


def test_r8_change_lifecycle_impact_simulation_risk_feedback_and_lineage_are_hashed() -> None:
    proposal = change_proposal(
        index=1,
        project_id="project-1",
        change_type=UgeifChangeType.BUSINESS,
        title="Add customer loyalty",
        intent_ref="manifest.intent.loyalty",
        current_manifest_version="manifest-1",
        proposed_manifest_version="manifest-2",
        evidence_hashes=("c" * 64,),
    )
    approved = decide_change_proposal(proposal, approved=True)
    impact = impact_analysis(
        index=1,
        proposal_hash=proposal.proposal_hash,
        affected_artifacts=("api.orders", "db.orders", "api.orders"),
        affected_workflows=("orders.checkout",),
    )
    simulation = simulation_report(
        index=1,
        proposal_hash=proposal.proposal_hash,
        impact_hash=impact.impact_hash,
        checks={"generated_artifacts": True, "rollback_capability": False},
    )
    risk = risk_profile(
        index=1,
        proposal_hash=proposal.proposal_hash,
        dimensions={"business_impact": 60.0, "deployment_risk": 80.0},
    )
    recommendation = operational_recommendation(
        index=1,
        project_id="project-1",
        source_hash=simulation.simulation_hash,
        category="runtime.optimization",
        recommendation="Prepare rollback before deploying loyalty changes.",
    )
    feedback = feedback_loop_record(
        index=1,
        project_id="project-1",
        runtime_source_hash=simulation.simulation_hash,
        metrics={"deployment_health": 68.0, "runtime_errors": 12.0},
        analytics=("rollback readiness is weak", "rollback readiness is weak"),
        recommendation_refs=(recommendation.recommendation_id,),
    )
    technology_plan = technology_evolution_plan(
        index=1,
        project_id="project-1",
        manifest_version="manifest-2",
        approved_proposal_hash=approved.proposal_hash,
        current_technology={
            "cloud_provider": "aws",
            "database_engine": "postgres",
            "ui_framework": "react",
        },
        target_technology={
            "cloud_provider": "azure",
            "database_engine": "postgres",
            "ui_framework": "vue",
        },
        migration_plan_refs=("migration-cloud-cutover", "migration-ui-rewrite"),
        business_intent_ref="manifest.intent.loyalty",
        simulation_hashes=(simulation.simulation_hash,),
        certification_hashes=("d" * 64,),
    )
    graph = version_graph_snapshot(
        index=1,
        project_id="project-1",
        nodes=({"type": "manifest", "id": "manifest-1"}, {"type": "deployment", "id": "dep-1"}),
        edges=({"from": "manifest-1", "to": "dep-1", "type": "generated"},),
    )
    entry = timeline_entry(
        index=1,
        project_id="project-1",
        sequence=1,
        event_type="manifest.generated",
        object_ref="manifest-1",
        object_hash=proposal.proposal_hash,
    )

    assert proposal.lifecycle_state is UgeifLifecycleState.PROPOSED
    assert approved.lifecycle_state is UgeifLifecycleState.APPROVED
    assert approved.proposal_hash != proposal.proposal_hash
    assert impact.affected_artifacts == ("api.orders", "db.orders")
    assert simulation.status is UgeifSimulationStatus.FAILED
    assert simulation.blockers == ("rollback_capability",)
    assert risk.approval_level == "security"
    assert recommendation.requires_manifest_review is True
    assert feedback.manifest_review_required is True
    assert feedback.may_auto_modify is False
    assert feedback.analytics == ("rollback readiness is weak",)
    assert technology_plan.preserves_business_intent is True
    assert technology_plan.requires_human_approval is True
    assert technology_plan.target_technology["cloud_provider"] == "azure"
    assert technology_plan.migration_plan_refs == (
        "migration-cloud-cutover",
        "migration-ui-rewrite",
    )
    assert graph.graph_hash
    assert entry.entry_hash


def test_r8_rejects_tampered_hashes_and_autonomous_apply() -> None:
    proposal = change_proposal(
        index=1,
        project_id="project-1",
        change_type=UgeifChangeType.AI,
        title="Improve summarizer",
        intent_ref="manifest.ai.summary",
        current_manifest_version="manifest-1",
        proposed_manifest_version="manifest-2",
    )

    with pytest.raises(ValidationError, match="proposal hash"):
        type(proposal).model_validate(
            {**proposal.model_dump(mode="json"), "proposal_hash": "0" * 64}
        )

    recommendation = operational_recommendation(
        index=1,
        project_id="project-1",
        source_hash=proposal.proposal_hash,
        category="ai.governance",
        recommendation="Review summarizer confidence threshold.",
    )
    with pytest.raises(ValidationError, match="auto-apply"):
        type(recommendation).model_validate(
            {**recommendation.model_dump(mode="json"), "may_auto_apply": True}
        )

    feedback = feedback_loop_record(
        index=1,
        project_id="project-1",
        runtime_source_hash=proposal.proposal_hash,
        metrics={"observed_health": 81.0},
    )
    with pytest.raises(ValidationError, match="manifest review"):
        type(feedback).model_validate(
            {**feedback.model_dump(mode="json"), "manifest_review_required": False}
        )
    with pytest.raises(ValidationError, match="auto-modify"):
        type(feedback).model_validate(
            {**feedback.model_dump(mode="json"), "may_auto_modify": True}
        )

    with pytest.raises(ValidationError, match="technology change"):
        technology_evolution_plan(
            index=1,
            project_id="project-1",
            manifest_version="manifest-2",
            approved_proposal_hash=proposal.proposal_hash,
            current_technology={"database_engine": "postgres"},
            target_technology={"database_engine": "postgres"},
            migration_plan_refs=("migration-db",),
            business_intent_ref="manifest.intent.summary",
        )

    with pytest.raises(ValidationError, match="migration plans"):
        technology_evolution_plan(
            index=1,
            project_id="project-1",
            manifest_version="manifest-2",
            approved_proposal_hash=proposal.proposal_hash,
            current_technology={"database_engine": "postgres"},
            target_technology={"database_engine": "mysql"},
            migration_plan_refs=(),
            business_intent_ref="manifest.intent.summary",
        )


def test_r8_deeper_pattern_compliance_marketplace_prediction_and_learning_records() -> None:
    pattern = reusable_pattern(
        index=1,
        organization_id="org-1",
        pattern_name="commerce.order-payment",
        pattern_type="workflow.pattern",
        occurrence_refs=("project-a:orders", "project-b:orders", "project-a:orders"),
        evidence_hashes=("d" * 64, "e" * 64),
        generalized_document={"workflow": "order-payment"},
    )
    knowledge = knowledge_generalization(
        index=1,
        organization_id="org-1",
        source_project_ids=("project-b", "project-a", "project-a"),
        category="workflow.pattern",
        reusable_asset_ref=pattern.pattern_id,
        source_evidence_hashes=pattern.evidence_hashes,
        generalized_document={"asset": "commerce pattern"},
    )
    industry = industry_framework_pack(
        index=1,
        industry="finance",
        version="1.0",
        manifest_templates=("loan-origination",),
        registry_extensions=("kyc-registry",),
        governance_policies=("dual-control",),
        compliance_mappings=("SOC2",),
        artifact_templates=("audit-report",),
    )
    compliance = compliance_framework_pack(
        index=1,
        framework="SOC 2",
        version="2026",
        controls=("CC6.1", "CC6.1"),
        audit_evidence_mappings=("access-review",),
        validation_rules=("mfa-required",),
    )
    marketplace = marketplace_asset_certification(
        index=1,
        asset_kind=UgeifAssetKind.GENERATOR_PACK,
        asset_ref="uagf.spring-terraform",
        asset_version="1.0",
        asset_hash="1" * 64,
        signer_ref="enterprise-certifier",
        signature_ref="sigstore://uagf.spring-terraform@1.0",
        checks={"signed": True, "traceable": True, "reproducible": True},
    )
    prediction = predictive_analysis(
        index=1,
        project_id="project-1",
        prediction_type="upgrade.risk",
        signals={"dependency_conflicts": 70.0, "capacity_exhaustion": 40.0},
        planning_recommendation="Schedule capacity and dependency remediation.",
    )
    boundary = ai_learning_boundary(
        index=1,
        source_ref="approved-manifest-template:commerce",
        source_type="approved_manifest",
        status=UgeifLearningSourceStatus.APPROVED,
        allowed_uses=("pattern_extraction", "recommendation_generation"),
        evidence_hashes=("f" * 64,),
    )
    sync = federated_governance_sync(
        index=1,
        organization_id="org-1",
        portfolio_ref="commerce-portfolio",
        project_refs=("project-b", "project-a", "project-a"),
        shared_asset_refs=("asset.registry.customer", "asset.registry.order"),
        governance_policy_refs=("policy.dual-control",),
        checks={"asset_versions_aligned": True, "project_boundaries_intact": True},
    )

    assert pattern.occurrence_refs == ("project-a:orders", "project-b:orders")
    assert knowledge.source_project_ids == ("project-a", "project-b")
    assert knowledge.client_isolation_verified is True
    assert industry.framework_hash
    assert compliance.controls == ("CC6.1",)
    assert marketplace.status is UgeifCertificationStatus.CERTIFIED
    assert marketplace.asset_hash == "1" * 64
    assert marketplace.signature_ref == "sigstore://uagf.spring-terraform@1.0"
    assert marketplace.signature_algorithm == "ed25519"
    assert prediction.risk_score == 55.0
    assert prediction.may_auto_modify is False
    assert boundary.status is UgeifLearningSourceStatus.APPROVED
    assert "runtime_speculation" in boundary.prohibited_uses
    assert sync.status.value == "synchronized"
    assert sync.project_refs == ("project-a", "project-b")
    assert sync.project_independence_preserved is True


def test_r8_rejects_unsafe_generalization_prediction_and_learning_boundary() -> None:
    with pytest.raises(ValidationError, match="client isolation"):
        knowledge_generalization(
            index=1,
            organization_id="org-1",
            source_project_ids=("project-a",),
            category="workflow.pattern",
            reusable_asset_ref="pattern-1",
            source_evidence_hashes=("a" * 64,),
            generalized_document={"asset": "unsafe"},
            client_isolation_verified=False,
        )

    prediction = predictive_analysis(
        index=1,
        project_id="project-1",
        prediction_type="capacity.exhaustion",
        signals={"queue_depth": 85.0},
        planning_recommendation="Plan capacity expansion.",
    )
    with pytest.raises(ValidationError, match="auto-modify"):
        type(prediction).model_validate(
            {**prediction.model_dump(mode="json"), "may_auto_modify": True}
        )

    with pytest.raises(ValidationError, match="allowed uses"):
        ai_learning_boundary(
            index=1,
            source_ref="approved-template",
            source_type="approved_template",
            status=UgeifLearningSourceStatus.APPROVED,
        )

    with pytest.raises(ValidationError):
        marketplace_asset_certification(
            index=1,
            asset_kind=UgeifAssetKind.GENERATOR_PACK,
            asset_ref="uagf.spring-terraform",
            asset_version="1.0",
            asset_hash="not-a-sha256",
            signer_ref="enterprise-certifier",
            signature_ref="sigstore://uagf.spring-terraform@1.0",
            checks={"signed": True, "traceable": True},
        )

    with pytest.raises(ValidationError, match="at least two projects"):
        federated_governance_sync(
            index=1,
            organization_id="org-1",
            portfolio_ref="single-project",
            project_refs=("project-a",),
            shared_asset_refs=("asset.registry.customer",),
            checks={"asset_versions_aligned": True},
        )
