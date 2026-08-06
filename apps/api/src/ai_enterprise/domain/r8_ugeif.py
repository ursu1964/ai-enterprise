from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_enterprise.domain.specification.kernel import specification_hash


class UgeifValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class UgeifGovernanceDomain(StrEnum):
    BUSINESS = "business"
    TECHNICAL = "technical"
    AI = "ai"
    SECURITY = "security"
    DATA = "data"
    COMPLIANCE = "compliance"
    OPERATIONAL = "operational"
    EVOLUTION = "evolution"


class UgeifValidationCategory(StrEnum):
    BUSINESS_CONSISTENCY = "business_consistency"
    ARCHITECTURAL_CONSISTENCY = "architectural_consistency"
    DEPENDENCY_INTEGRITY = "dependency_integrity"
    API_COMPATIBILITY = "api_compatibility"
    DATABASE_CONSISTENCY = "database_consistency"
    SECURITY_POLICIES = "security_policies"
    COMPLIANCE_RULES = "compliance_rules"
    DOCUMENTATION_COMPLETENESS = "documentation_completeness"
    PERFORMANCE_OBJECTIVES = "performance_objectives"
    OPERATIONAL_HEALTH = "operational_health"


class UgeifChangeType(StrEnum):
    BUSINESS = "business"
    TECHNICAL = "technical"
    INFRASTRUCTURE = "infrastructure"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    PERFORMANCE = "performance"
    AI = "ai"


class UgeifLifecycleState(StrEnum):
    PROPOSED = "proposed"
    IMPACT_ANALYZED = "impact_analyzed"
    SIMULATED = "simulated"
    VALIDATED = "validated"
    APPROVED = "approved"
    REJECTED = "rejected"
    GENERATED = "generated"
    DEPLOYED = "deployed"
    OBSERVED = "observed"


class UgeifAssessmentStatus(StrEnum):
    PASSING = "passing"
    NEEDS_ATTENTION = "needs_attention"
    BLOCKED = "blocked"


class UgeifApprovalStatus(StrEnum):
    REQUIRED = "required"
    APPROVED = "approved"
    REJECTED = "rejected"


class UgeifSimulationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class UgeifCertificationStatus(StrEnum):
    CERTIFIED = "certified"
    NOT_CERTIFIED = "not_certified"


class UgeifAssetKind(StrEnum):
    MANIFEST_TEMPLATE = "manifest_template"
    REGISTRY_MODULE = "registry_module"
    GENERATOR_PACK = "generator_pack"
    TEMPLATE_PACK = "template_pack"
    GOVERNANCE_POLICY = "governance_policy"
    WORKFLOW_LIBRARY = "workflow_library"
    COMPLIANCE_MODULE = "compliance_module"


class UgeifLearningSourceStatus(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"


class UgeifSynchronizationStatus(StrEnum):
    SYNCHRONIZED = "synchronized"
    ATTENTION_REQUIRED = "attention_required"


class UgeifGovernanceAssessment(UgeifValue):
    schema_version: Literal["ugeif-governance-assessment-0.1"] = (
        "ugeif-governance-assessment-0.1"
    )
    assessment_id: str = Field(pattern=r"^UGEIF-GOV-[0-9]{4}$")
    project_id: str = Field(min_length=1)
    manifest_version: str = Field(min_length=1, max_length=120)
    domains: tuple[UgeifGovernanceDomain, ...]
    scores: dict[str, float]
    recommendations: tuple[str, ...] = ()
    status: UgeifAssessmentStatus
    human_approval_required: bool
    assessment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_assessment(self) -> UgeifGovernanceAssessment:
        if tuple(sorted(set(self.domains), key=lambda value: value.value)) != self.domains:
            raise ValueError("UGEIF governance domains must be unique and sorted")
        if tuple(sorted(set(self.recommendations))) != self.recommendations:
            raise ValueError("UGEIF recommendations must be unique and sorted")
        if any(score < 0 or score > 100 for score in self.scores.values()):
            raise ValueError("UGEIF governance scores must be between 0 and 100")
        if self.assessment_hash != _governance_assessment_hash(self):
            raise ValueError("UGEIF governance assessment hash does not match canonical content")
        return self


class UgeifValidationReport(UgeifValue):
    schema_version: Literal["ugeif-validation-report-0.1"] = "ugeif-validation-report-0.1"
    validation_id: str = Field(pattern=r"^UGEIF-VAL-[0-9]{4}$")
    project_id: str = Field(min_length=1)
    manifest_version: str = Field(min_length=1, max_length=120)
    categories: tuple[UgeifValidationCategory, ...]
    findings: tuple[str, ...] = ()
    status: UgeifAssessmentStatus
    report_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_report(self) -> UgeifValidationReport:
        if tuple(sorted(set(self.categories), key=lambda value: value.value)) != self.categories:
            raise ValueError("UGEIF validation categories must be unique and sorted")
        if tuple(sorted(set(self.findings))) != self.findings:
            raise ValueError("UGEIF validation findings must be unique and sorted")
        if self.report_hash != _validation_report_hash(self):
            raise ValueError("UGEIF validation report hash does not match canonical content")
        return self


class UgeifChangeProposal(UgeifValue):
    schema_version: Literal["ugeif-change-proposal-0.1"] = "ugeif-change-proposal-0.1"
    proposal_id: str = Field(pattern=r"^UGEIF-CHG-[0-9]{4}$")
    project_id: str = Field(min_length=1)
    change_type: UgeifChangeType
    title: str = Field(min_length=1, max_length=240)
    intent_ref: str = Field(min_length=1, max_length=200)
    current_manifest_version: str = Field(min_length=1, max_length=120)
    proposed_manifest_version: str = Field(min_length=1, max_length=120)
    lifecycle_state: UgeifLifecycleState
    approval_status: UgeifApprovalStatus
    evidence_hashes: tuple[str, ...] = ()
    proposal_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_proposal(self) -> UgeifChangeProposal:
        if tuple(sorted(set(self.evidence_hashes))) != self.evidence_hashes:
            raise ValueError("UGEIF proposal evidence hashes must be unique and sorted")
        if self.proposal_hash != _change_proposal_hash(self):
            raise ValueError("UGEIF change proposal hash does not match canonical content")
        return self


class UgeifImpactAnalysis(UgeifValue):
    schema_version: Literal["ugeif-impact-analysis-0.1"] = "ugeif-impact-analysis-0.1"
    impact_id: str = Field(pattern=r"^UGEIF-IMP-[0-9]{4}$")
    proposal_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    affected_artifacts: tuple[str, ...] = ()
    affected_dependencies: tuple[str, ...] = ()
    affected_workflows: tuple[str, ...] = ()
    affected_permissions: tuple[str, ...] = ()
    affected_documentation: tuple[str, ...] = ()
    impact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_impact(self) -> UgeifImpactAnalysis:
        for values in (
            self.affected_artifacts,
            self.affected_dependencies,
            self.affected_workflows,
            self.affected_permissions,
            self.affected_documentation,
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError("UGEIF impact values must be unique and sorted")
        if self.impact_hash != _impact_analysis_hash(self):
            raise ValueError("UGEIF impact analysis hash does not match canonical content")
        return self


class UgeifSimulationReport(UgeifValue):
    schema_version: Literal["ugeif-simulation-report-0.1"] = "ugeif-simulation-report-0.1"
    simulation_id: str = Field(pattern=r"^UGEIF-SIM-[0-9]{4}$")
    proposal_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    impact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    checks: dict[str, bool]
    status: UgeifSimulationStatus
    blockers: tuple[str, ...] = ()
    simulation_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_simulation(self) -> UgeifSimulationReport:
        if tuple(sorted(set(self.blockers))) != self.blockers:
            raise ValueError("UGEIF simulation blockers must be unique and sorted")
        expected = (
            UgeifSimulationStatus.PASSED
            if all(self.checks.values())
            else UgeifSimulationStatus.FAILED
        )
        if self.status is not expected:
            raise ValueError("UGEIF simulation status must match checks")
        if self.simulation_hash != _simulation_report_hash(self):
            raise ValueError("UGEIF simulation report hash does not match canonical content")
        return self


class UgeifRiskProfile(UgeifValue):
    schema_version: Literal["ugeif-risk-profile-0.1"] = "ugeif-risk-profile-0.1"
    risk_id: str = Field(pattern=r"^UGEIF-RISK-[0-9]{4}$")
    proposal_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    dimensions: dict[str, float]
    approval_level: str = Field(min_length=1, max_length=80)
    risk_score: float = Field(ge=0, le=100)
    risk_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_risk(self) -> UgeifRiskProfile:
        if any(value < 0 or value > 100 for value in self.dimensions.values()):
            raise ValueError("UGEIF risk dimensions must be between 0 and 100")
        if self.risk_hash != _risk_profile_hash(self):
            raise ValueError("UGEIF risk profile hash does not match canonical content")
        return self


class UgeifQualityScorecard(UgeifValue):
    schema_version: Literal["ugeif-quality-scorecard-0.1"] = "ugeif-quality-scorecard-0.1"
    scorecard_id: str = Field(pattern=r"^UGEIF-QUAL-[0-9]{4}$")
    project_id: str = Field(min_length=1)
    deployment_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    scores: dict[str, float]
    status: UgeifAssessmentStatus
    scorecard_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_scorecard(self) -> UgeifQualityScorecard:
        if any(value < 0 or value > 100 for value in self.scores.values()):
            raise ValueError("UGEIF quality scores must be between 0 and 100")
        if self.scorecard_hash != _quality_scorecard_hash(self):
            raise ValueError("UGEIF quality scorecard hash does not match canonical content")
        return self


class UgeifOperationalRecommendation(UgeifValue):
    schema_version: Literal["ugeif-operational-recommendation-0.1"] = (
        "ugeif-operational-recommendation-0.1"
    )
    recommendation_id: str = Field(pattern=r"^UGEIF-REC-[0-9]{4}$")
    project_id: str = Field(min_length=1)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    category: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    recommendation: str = Field(min_length=1, max_length=1000)
    may_auto_apply: bool = False
    requires_manifest_review: bool = True
    recommendation_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_recommendation(self) -> UgeifOperationalRecommendation:
        if self.may_auto_apply:
            raise ValueError("UGEIF recommendations may not auto-apply changes")
        if self.recommendation_hash != _operational_recommendation_hash(self):
            raise ValueError("UGEIF recommendation hash does not match canonical content")
        return self


class UgeifFeedbackLoopRecord(UgeifValue):
    schema_version: Literal["ugeif-feedback-loop-record-0.1"] = (
        "ugeif-feedback-loop-record-0.1"
    )
    feedback_id: str = Field(pattern=r"^UGEIF-FB-[0-9]{4}$")
    project_id: str = Field(min_length=1)
    runtime_source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    metrics: dict[str, float]
    analytics: tuple[str, ...] = ()
    recommendation_refs: tuple[str, ...] = ()
    manifest_review_required: bool = True
    may_auto_modify: bool = False
    feedback_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_feedback(self) -> UgeifFeedbackLoopRecord:
        if any(value < 0 or value > 100 for value in self.metrics.values()):
            raise ValueError("UGEIF feedback metrics must be between 0 and 100")
        if tuple(sorted(set(self.analytics))) != self.analytics:
            raise ValueError("UGEIF feedback analytics must be unique and sorted")
        if tuple(sorted(set(self.recommendation_refs))) != self.recommendation_refs:
            raise ValueError("UGEIF feedback recommendation refs must be unique and sorted")
        if not self.manifest_review_required:
            raise ValueError("UGEIF runtime feedback must require manifest review")
        if self.may_auto_modify:
            raise ValueError("UGEIF runtime feedback may not auto-modify systems")
        if self.feedback_hash != _feedback_loop_record_hash(self):
            raise ValueError("UGEIF feedback loop hash does not match canonical content")
        return self


class UgeifVersionGraphSnapshot(UgeifValue):
    schema_version: Literal["ugeif-version-graph-snapshot-0.1"] = (
        "ugeif-version-graph-snapshot-0.1"
    )
    graph_id: str = Field(pattern=r"^UGEIF-VG-[0-9]{4}$")
    project_id: str = Field(min_length=1)
    nodes: tuple[dict[str, str], ...]
    edges: tuple[dict[str, str], ...] = ()
    graph_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_graph(self) -> UgeifVersionGraphSnapshot:
        if self.graph_hash != _version_graph_hash(self):
            raise ValueError("UGEIF version graph hash does not match canonical content")
        return self


class UgeifTimelineEntry(UgeifValue):
    schema_version: Literal["ugeif-timeline-entry-0.1"] = "ugeif-timeline-entry-0.1"
    timeline_id: str = Field(pattern=r"^UGEIF-TIME-[0-9]{4}$")
    project_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    event_type: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    object_ref: str = Field(min_length=1, max_length=200)
    object_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    entry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_entry(self) -> UgeifTimelineEntry:
        if self.entry_hash != _timeline_entry_hash(self):
            raise ValueError("UGEIF timeline entry hash does not match canonical content")
        return self


class UgeifCertification(UgeifValue):
    schema_version: Literal["ugeif-certification-0.1"] = "ugeif-certification-0.1"
    certification_id: str = Field(pattern=r"^UGEIF-CERT-[0-9]{4}$")
    project_id: str = Field(min_length=1)
    deployment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    checks: dict[str, bool]
    status: UgeifCertificationStatus
    evidence_hashes: tuple[str, ...] = ()
    certification_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_certification(self) -> UgeifCertification:
        if tuple(sorted(set(self.evidence_hashes))) != self.evidence_hashes:
            raise ValueError("UGEIF certification evidence hashes must be unique and sorted")
        expected = (
            UgeifCertificationStatus.CERTIFIED
            if all(self.checks.values())
            else UgeifCertificationStatus.NOT_CERTIFIED
        )
        if self.status is not expected:
            raise ValueError("UGEIF certification status must match checks")
        if self.certification_hash != _certification_hash(self):
            raise ValueError("UGEIF certification hash does not match canonical content")
        return self


class UgeifReusablePattern(UgeifValue):
    schema_version: Literal["ugeif-reusable-pattern-0.1"] = "ugeif-reusable-pattern-0.1"
    pattern_id: str = Field(pattern=r"^UGEIF-PAT-[0-9]{4}$")
    organization_id: str = Field(min_length=1)
    pattern_name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,159}$")
    pattern_type: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    occurrence_refs: tuple[str, ...]
    evidence_hashes: tuple[str, ...]
    generalized_document: dict[str, object]
    human_review_required: bool = True
    pattern_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_pattern(self) -> UgeifReusablePattern:
        if len(set(self.occurrence_refs)) < 2:
            raise ValueError("UGEIF reusable patterns require at least two distinct occurrences")
        if tuple(sorted(set(self.occurrence_refs))) != self.occurrence_refs:
            raise ValueError("UGEIF pattern occurrences must be unique and sorted")
        if tuple(sorted(set(self.evidence_hashes))) != self.evidence_hashes:
            raise ValueError("UGEIF pattern evidence hashes must be unique and sorted")
        if self.pattern_hash != _reusable_pattern_hash(self):
            raise ValueError("UGEIF reusable pattern hash does not match canonical content")
        return self


class UgeifKnowledgeGeneralization(UgeifValue):
    schema_version: Literal["ugeif-knowledge-generalization-0.1"] = (
        "ugeif-knowledge-generalization-0.1"
    )
    knowledge_id: str = Field(pattern=r"^UGEIF-KNOW-[0-9]{4}$")
    organization_id: str = Field(min_length=1)
    source_project_ids: tuple[str, ...]
    category: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    reusable_asset_ref: str = Field(min_length=1, max_length=240)
    source_evidence_hashes: tuple[str, ...]
    redaction_policy: str = Field(min_length=1, max_length=120)
    client_isolation_verified: bool
    generalized_document: dict[str, object]
    knowledge_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_knowledge(self) -> UgeifKnowledgeGeneralization:
        if tuple(sorted(set(self.source_project_ids))) != self.source_project_ids:
            raise ValueError("UGEIF source projects must be unique and sorted")
        if tuple(sorted(set(self.source_evidence_hashes))) != self.source_evidence_hashes:
            raise ValueError("UGEIF source evidence hashes must be unique and sorted")
        if not self.client_isolation_verified:
            raise ValueError("UGEIF knowledge generalization requires client isolation")
        if self.knowledge_hash != _knowledge_generalization_hash(self):
            raise ValueError(
                "UGEIF knowledge generalization hash does not match canonical content"
            )
        return self


class UgeifIndustryFrameworkPack(UgeifValue):
    schema_version: Literal["ugeif-industry-framework-pack-0.1"] = (
        "ugeif-industry-framework-pack-0.1"
    )
    framework_id: str = Field(pattern=r"^UGEIF-IND-[0-9]{4}$")
    industry: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,119}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+$")
    manifest_templates: tuple[str, ...] = ()
    registry_extensions: tuple[str, ...] = ()
    governance_policies: tuple[str, ...] = ()
    compliance_mappings: tuple[str, ...] = ()
    artifact_templates: tuple[str, ...] = ()
    framework_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_framework(self) -> UgeifIndustryFrameworkPack:
        for values in (
            self.manifest_templates,
            self.registry_extensions,
            self.governance_policies,
            self.compliance_mappings,
            self.artifact_templates,
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError("UGEIF framework assets must be unique and sorted")
        if self.framework_hash != _industry_framework_pack_hash(self):
            raise ValueError("UGEIF industry framework hash does not match canonical content")
        return self


class UgeifComplianceFrameworkPack(UgeifValue):
    schema_version: Literal["ugeif-compliance-framework-pack-0.1"] = (
        "ugeif-compliance-framework-pack-0.1"
    )
    compliance_id: str = Field(pattern=r"^UGEIF-COMP-[0-9]{4}$")
    framework: str = Field(pattern=r"^[A-Z][A-Z0-9 _.-]{1,79}$")
    version: str = Field(min_length=1, max_length=80)
    controls: tuple[str, ...]
    audit_evidence_mappings: tuple[str, ...]
    validation_rules: tuple[str, ...]
    documentation_templates: tuple[str, ...] = ()
    compliance_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_compliance(self) -> UgeifComplianceFrameworkPack:
        for values in (
            self.controls,
            self.audit_evidence_mappings,
            self.validation_rules,
            self.documentation_templates,
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError("UGEIF compliance assets must be unique and sorted")
        if not self.controls or not self.validation_rules:
            raise ValueError("UGEIF compliance pack requires controls and validation rules")
        if self.compliance_hash != _compliance_framework_pack_hash(self):
            raise ValueError("UGEIF compliance framework hash does not match canonical content")
        return self


class UgeifMarketplaceAssetCertification(UgeifValue):
    schema_version: Literal["ugeif-marketplace-asset-certification-0.1"] = (
        "ugeif-marketplace-asset-certification-0.1"
    )
    marketplace_certification_id: str = Field(pattern=r"^UGEIF-MKT-[0-9]{4}$")
    asset_kind: UgeifAssetKind
    asset_ref: str = Field(min_length=1, max_length=240)
    asset_version: str = Field(min_length=1, max_length=80)
    asset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    signer_ref: str = Field(min_length=1, max_length=200)
    signature_ref: str = Field(min_length=1, max_length=300)
    signature_algorithm: str = Field(default="ed25519", pattern=r"^[a-z0-9_.-]{3,80}$")
    checks: dict[str, bool]
    status: UgeifCertificationStatus
    certification_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_marketplace_certification(self) -> UgeifMarketplaceAssetCertification:
        expected = (
            UgeifCertificationStatus.CERTIFIED
            if all(self.checks.values())
            else UgeifCertificationStatus.NOT_CERTIFIED
        )
        if self.status is not expected:
            raise ValueError("UGEIF marketplace certification status must match checks")
        if self.certification_hash != _marketplace_asset_certification_hash(self):
            raise ValueError(
                "UGEIF marketplace asset certification hash does not match canonical content"
            )
        return self


class UgeifPredictiveAnalysis(UgeifValue):
    schema_version: Literal["ugeif-predictive-analysis-0.1"] = (
        "ugeif-predictive-analysis-0.1"
    )
    prediction_id: str = Field(pattern=r"^UGEIF-PRED-[0-9]{4}$")
    project_id: str = Field(min_length=1)
    prediction_type: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    signals: dict[str, float]
    risk_score: float = Field(ge=0, le=100)
    planning_recommendation: str = Field(min_length=1, max_length=1000)
    may_auto_modify: bool = False
    prediction_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_prediction(self) -> UgeifPredictiveAnalysis:
        if any(value < 0 or value > 100 for value in self.signals.values()):
            raise ValueError("UGEIF prediction signals must be between 0 and 100")
        if self.may_auto_modify:
            raise ValueError("UGEIF predictions may not auto-modify systems")
        if self.prediction_hash != _predictive_analysis_hash(self):
            raise ValueError("UGEIF predictive analysis hash does not match canonical content")
        return self


class UgeifAiLearningBoundary(UgeifValue):
    schema_version: Literal["ugeif-ai-learning-boundary-0.1"] = (
        "ugeif-ai-learning-boundary-0.1"
    )
    boundary_id: str = Field(pattern=r"^UGEIF-AIL-[0-9]{4}$")
    source_ref: str = Field(min_length=1, max_length=240)
    source_type: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    status: UgeifLearningSourceStatus
    allowed_uses: tuple[str, ...] = ()
    prohibited_uses: tuple[str, ...]
    evidence_hashes: tuple[str, ...] = ()
    boundary_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_boundary(self) -> UgeifAiLearningBoundary:
        if tuple(sorted(set(self.allowed_uses))) != self.allowed_uses:
            raise ValueError("UGEIF allowed learning uses must be unique and sorted")
        if tuple(sorted(set(self.prohibited_uses))) != self.prohibited_uses:
            raise ValueError("UGEIF prohibited learning uses must be unique and sorted")
        if tuple(sorted(set(self.evidence_hashes))) != self.evidence_hashes:
            raise ValueError("UGEIF learning boundary evidence must be unique and sorted")
        if self.status is UgeifLearningSourceStatus.APPROVED and not self.allowed_uses:
            raise ValueError("UGEIF approved learning source requires allowed uses")
        if self.status is UgeifLearningSourceStatus.DENIED and not self.prohibited_uses:
            raise ValueError("UGEIF denied learning source requires prohibited uses")
        if self.boundary_hash != _ai_learning_boundary_hash(self):
            raise ValueError("UGEIF AI learning boundary hash does not match canonical content")
        return self


class UgeifFederatedGovernanceSync(UgeifValue):
    schema_version: Literal["ugeif-federated-governance-sync-0.1"] = (
        "ugeif-federated-governance-sync-0.1"
    )
    sync_id: str = Field(pattern=r"^UGEIF-FED-[0-9]{4}$")
    organization_id: str = Field(min_length=1)
    portfolio_ref: str = Field(min_length=1, max_length=200)
    project_refs: tuple[str, ...]
    shared_asset_refs: tuple[str, ...]
    governance_policy_refs: tuple[str, ...] = ()
    checks: dict[str, bool]
    status: UgeifSynchronizationStatus
    project_independence_preserved: bool = True
    sync_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_sync(self) -> UgeifFederatedGovernanceSync:
        if len(set(self.project_refs)) < 2:
            raise ValueError("UGEIF federated sync requires at least two projects")
        for values in (
            self.project_refs,
            self.shared_asset_refs,
            self.governance_policy_refs,
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError("UGEIF federated sync values must be unique and sorted")
        if not self.shared_asset_refs:
            raise ValueError("UGEIF federated sync requires shared assets")
        if not self.project_independence_preserved:
            raise ValueError("UGEIF federated sync must preserve project independence")
        expected = (
            UgeifSynchronizationStatus.SYNCHRONIZED
            if all(self.checks.values())
            else UgeifSynchronizationStatus.ATTENTION_REQUIRED
        )
        if self.status is not expected:
            raise ValueError("UGEIF federated sync status must match checks")
        if self.sync_hash != _federated_governance_sync_hash(self):
            raise ValueError(
                "UGEIF federated governance sync hash does not match canonical content"
            )
        return self


class UgeifTechnologyEvolutionPlan(UgeifValue):
    schema_version: Literal["ugeif-technology-evolution-plan-0.1"] = (
        "ugeif-technology-evolution-plan-0.1"
    )
    technology_evolution_id: str = Field(pattern=r"^UGEIF-TECH-[0-9]{4}$")
    project_id: str = Field(min_length=1)
    manifest_version: str = Field(min_length=1, max_length=120)
    approved_proposal_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_technology: dict[str, str]
    target_technology: dict[str, str]
    migration_plan_refs: tuple[str, ...]
    simulation_hashes: tuple[str, ...] = ()
    certification_hashes: tuple[str, ...] = ()
    business_intent_ref: str = Field(min_length=1, max_length=200)
    preserves_business_intent: bool = True
    requires_human_approval: bool = True
    plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_technology_evolution(self) -> UgeifTechnologyEvolutionPlan:
        if not self.current_technology or not self.target_technology:
            raise ValueError("UGEIF technology evolution requires current and target technology")
        if self.current_technology == self.target_technology:
            raise ValueError("UGEIF technology evolution requires a technology change")
        for values in (
            self.migration_plan_refs,
            self.simulation_hashes,
            self.certification_hashes,
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError("UGEIF technology evolution refs must be unique and sorted")
        if not self.migration_plan_refs:
            raise ValueError("UGEIF technology evolution requires migration plans")
        if not self.preserves_business_intent:
            raise ValueError("UGEIF technology evolution must preserve business intent")
        if not self.requires_human_approval:
            raise ValueError("UGEIF technology evolution requires human approval")
        if self.plan_hash != _technology_evolution_plan_hash(self):
            raise ValueError(
                "UGEIF technology evolution plan hash does not match canonical content"
            )
        return self


def governance_assessment(
    *,
    index: int,
    project_id: str,
    manifest_version: str,
    scores: dict[str, float],
    recommendations: tuple[str, ...] = (),
) -> UgeifGovernanceAssessment:
    normalized_scores = dict(sorted(scores.items()))
    domains = tuple(
        sorted(
            (UgeifGovernanceDomain(domain) for domain in normalized_scores),
            key=lambda value: value.value,
        )
    )
    lowest = min(normalized_scores.values()) if normalized_scores else 0.0
    status = _assessment_status(lowest)
    normalized_recommendations = tuple(sorted(set(recommendations)))
    provisional = UgeifGovernanceAssessment.model_construct(
        schema_version="ugeif-governance-assessment-0.1",
        assessment_id=f"UGEIF-GOV-{index:04d}",
        project_id=project_id,
        manifest_version=manifest_version,
        domains=domains,
        scores=normalized_scores,
        recommendations=normalized_recommendations,
        status=status,
        human_approval_required=bool(normalized_recommendations)
        or status is not UgeifAssessmentStatus.PASSING,
        assessment_hash="0" * 64,
    )
    return UgeifGovernanceAssessment(
        **provisional.model_dump(exclude={"assessment_hash"}),
        assessment_hash=_governance_assessment_hash(provisional),
    )


def validation_report(
    *,
    index: int,
    project_id: str,
    manifest_version: str,
    findings_by_category: dict[str, tuple[str, ...]],
) -> UgeifValidationReport:
    categories = tuple(
        sorted(
            (UgeifValidationCategory(category) for category in findings_by_category),
            key=lambda value: value.value,
        )
    )
    findings = tuple(
        sorted(
            {
                f"{category}:{finding}"
                for category, findings in findings_by_category.items()
                for finding in findings
            }
        )
    )
    status = (
        UgeifAssessmentStatus.PASSING
        if not findings
        else UgeifAssessmentStatus.NEEDS_ATTENTION
    )
    if any("security" in finding or "compliance" in finding for finding in findings):
        status = UgeifAssessmentStatus.BLOCKED
    provisional = UgeifValidationReport.model_construct(
        schema_version="ugeif-validation-report-0.1",
        validation_id=f"UGEIF-VAL-{index:04d}",
        project_id=project_id,
        manifest_version=manifest_version,
        categories=categories,
        findings=findings,
        status=status,
        report_hash="0" * 64,
    )
    return UgeifValidationReport(
        **provisional.model_dump(exclude={"report_hash"}),
        report_hash=_validation_report_hash(provisional),
    )


def change_proposal(
    *,
    index: int,
    project_id: str,
    change_type: UgeifChangeType,
    title: str,
    intent_ref: str,
    current_manifest_version: str,
    proposed_manifest_version: str,
    evidence_hashes: tuple[str, ...] = (),
) -> UgeifChangeProposal:
    normalized_evidence = tuple(sorted(set(evidence_hashes)))
    provisional = UgeifChangeProposal.model_construct(
        schema_version="ugeif-change-proposal-0.1",
        proposal_id=f"UGEIF-CHG-{index:04d}",
        project_id=project_id,
        change_type=change_type,
        title=title,
        intent_ref=intent_ref,
        current_manifest_version=current_manifest_version,
        proposed_manifest_version=proposed_manifest_version,
        lifecycle_state=UgeifLifecycleState.PROPOSED,
        approval_status=UgeifApprovalStatus.REQUIRED,
        evidence_hashes=normalized_evidence,
        proposal_hash="0" * 64,
    )
    return UgeifChangeProposal(
        **provisional.model_dump(exclude={"proposal_hash"}),
        proposal_hash=_change_proposal_hash(provisional),
    )


def decide_change_proposal(
    proposal: UgeifChangeProposal,
    *,
    approved: bool,
) -> UgeifChangeProposal:
    lifecycle_state = UgeifLifecycleState.APPROVED if approved else UgeifLifecycleState.REJECTED
    approval_status = UgeifApprovalStatus.APPROVED if approved else UgeifApprovalStatus.REJECTED
    provisional = UgeifChangeProposal.model_construct(
        schema_version=proposal.schema_version,
        proposal_id=proposal.proposal_id,
        project_id=proposal.project_id,
        change_type=proposal.change_type,
        title=proposal.title,
        intent_ref=proposal.intent_ref,
        current_manifest_version=proposal.current_manifest_version,
        proposed_manifest_version=proposal.proposed_manifest_version,
        lifecycle_state=lifecycle_state,
        approval_status=approval_status,
        evidence_hashes=proposal.evidence_hashes,
        proposal_hash="0" * 64,
    )
    return UgeifChangeProposal(
        **provisional.model_dump(exclude={"proposal_hash"}),
        proposal_hash=_change_proposal_hash(provisional),
    )


def impact_analysis(
    *,
    index: int,
    proposal_hash: str,
    affected_artifacts: tuple[str, ...] = (),
    affected_dependencies: tuple[str, ...] = (),
    affected_workflows: tuple[str, ...] = (),
    affected_permissions: tuple[str, ...] = (),
    affected_documentation: tuple[str, ...] = (),
) -> UgeifImpactAnalysis:
    provisional = UgeifImpactAnalysis.model_construct(
        schema_version="ugeif-impact-analysis-0.1",
        impact_id=f"UGEIF-IMP-{index:04d}",
        proposal_hash=proposal_hash,
        affected_artifacts=tuple(sorted(set(affected_artifacts))),
        affected_dependencies=tuple(sorted(set(affected_dependencies))),
        affected_workflows=tuple(sorted(set(affected_workflows))),
        affected_permissions=tuple(sorted(set(affected_permissions))),
        affected_documentation=tuple(sorted(set(affected_documentation))),
        impact_hash="0" * 64,
    )
    return UgeifImpactAnalysis(
        **provisional.model_dump(exclude={"impact_hash"}),
        impact_hash=_impact_analysis_hash(provisional),
    )


def simulation_report(
    *,
    index: int,
    proposal_hash: str,
    impact_hash: str,
    checks: dict[str, bool],
) -> UgeifSimulationReport:
    normalized_checks = dict(sorted(checks.items()))
    blockers = tuple(sorted(key for key, passed in normalized_checks.items() if not passed))
    provisional = UgeifSimulationReport.model_construct(
        schema_version="ugeif-simulation-report-0.1",
        simulation_id=f"UGEIF-SIM-{index:04d}",
        proposal_hash=proposal_hash,
        impact_hash=impact_hash,
        checks=normalized_checks,
        status=UgeifSimulationStatus.PASSED if not blockers else UgeifSimulationStatus.FAILED,
        blockers=blockers,
        simulation_hash="0" * 64,
    )
    return UgeifSimulationReport(
        **provisional.model_dump(exclude={"simulation_hash"}),
        simulation_hash=_simulation_report_hash(provisional),
    )


def risk_profile(
    *, index: int, proposal_hash: str, dimensions: dict[str, float]
) -> UgeifRiskProfile:
    normalized = dict(sorted(dimensions.items()))
    score = round(sum(normalized.values()) / len(normalized), 2) if normalized else 0.0
    approval_level = "board" if score >= 75 else "security" if score >= 50 else "owner"
    provisional = UgeifRiskProfile.model_construct(
        schema_version="ugeif-risk-profile-0.1",
        risk_id=f"UGEIF-RISK-{index:04d}",
        proposal_hash=proposal_hash,
        dimensions=normalized,
        approval_level=approval_level,
        risk_score=score,
        risk_hash="0" * 64,
    )
    return UgeifRiskProfile(
        **provisional.model_dump(exclude={"risk_hash"}),
        risk_hash=_risk_profile_hash(provisional),
    )


def quality_scorecard(
    *,
    index: int,
    project_id: str,
    scores: dict[str, float],
    deployment_hash: str | None = None,
) -> UgeifQualityScorecard:
    normalized = dict(sorted(scores.items()))
    lowest = min(normalized.values()) if normalized else 0.0
    provisional = UgeifQualityScorecard.model_construct(
        schema_version="ugeif-quality-scorecard-0.1",
        scorecard_id=f"UGEIF-QUAL-{index:04d}",
        project_id=project_id,
        deployment_hash=deployment_hash,
        scores=normalized,
        status=_assessment_status(lowest),
        scorecard_hash="0" * 64,
    )
    return UgeifQualityScorecard(
        **provisional.model_dump(exclude={"scorecard_hash"}),
        scorecard_hash=_quality_scorecard_hash(provisional),
    )


def operational_recommendation(
    *,
    index: int,
    project_id: str,
    source_hash: str,
    category: str,
    recommendation: str,
) -> UgeifOperationalRecommendation:
    provisional = UgeifOperationalRecommendation.model_construct(
        schema_version="ugeif-operational-recommendation-0.1",
        recommendation_id=f"UGEIF-REC-{index:04d}",
        project_id=project_id,
        source_hash=source_hash,
        category=category,
        recommendation=recommendation,
        may_auto_apply=False,
        requires_manifest_review=True,
        recommendation_hash="0" * 64,
    )
    return UgeifOperationalRecommendation(
        **provisional.model_dump(exclude={"recommendation_hash"}),
        recommendation_hash=_operational_recommendation_hash(provisional),
    )


def feedback_loop_record(
    *,
    index: int,
    project_id: str,
    runtime_source_hash: str,
    metrics: dict[str, float],
    analytics: tuple[str, ...] = (),
    recommendation_refs: tuple[str, ...] = (),
) -> UgeifFeedbackLoopRecord:
    provisional = UgeifFeedbackLoopRecord.model_construct(
        schema_version="ugeif-feedback-loop-record-0.1",
        feedback_id=f"UGEIF-FB-{index:04d}",
        project_id=project_id,
        runtime_source_hash=runtime_source_hash,
        metrics=dict(sorted(metrics.items())),
        analytics=tuple(sorted(set(analytics))),
        recommendation_refs=tuple(sorted(set(recommendation_refs))),
        manifest_review_required=True,
        may_auto_modify=False,
        feedback_hash="0" * 64,
    )
    return UgeifFeedbackLoopRecord(
        **provisional.model_dump(exclude={"feedback_hash"}),
        feedback_hash=_feedback_loop_record_hash(provisional),
    )


def version_graph_snapshot(
    *,
    index: int,
    project_id: str,
    nodes: tuple[dict[str, str], ...],
    edges: tuple[dict[str, str], ...] = (),
) -> UgeifVersionGraphSnapshot:
    provisional = UgeifVersionGraphSnapshot.model_construct(
        schema_version="ugeif-version-graph-snapshot-0.1",
        graph_id=f"UGEIF-VG-{index:04d}",
        project_id=project_id,
        nodes=tuple(sorted(nodes, key=lambda item: (item.get("type", ""), item.get("id", "")))),
        edges=tuple(sorted(edges, key=lambda item: (item.get("from", ""), item.get("to", "")))),
        graph_hash="0" * 64,
    )
    return UgeifVersionGraphSnapshot(
        **provisional.model_dump(exclude={"graph_hash"}),
        graph_hash=_version_graph_hash(provisional),
    )


def timeline_entry(
    *,
    index: int,
    project_id: str,
    sequence: int,
    event_type: str,
    object_ref: str,
    object_hash: str,
) -> UgeifTimelineEntry:
    provisional = UgeifTimelineEntry.model_construct(
        schema_version="ugeif-timeline-entry-0.1",
        timeline_id=f"UGEIF-TIME-{index:04d}",
        project_id=project_id,
        sequence=sequence,
        event_type=event_type,
        object_ref=object_ref,
        object_hash=object_hash,
        entry_hash="0" * 64,
    )
    return UgeifTimelineEntry(
        **provisional.model_dump(exclude={"entry_hash"}),
        entry_hash=_timeline_entry_hash(provisional),
    )


def certification(
    *,
    index: int,
    project_id: str,
    deployment_hash: str,
    checks: dict[str, bool],
    evidence_hashes: tuple[str, ...] = (),
) -> UgeifCertification:
    normalized_checks = dict(sorted(checks.items()))
    provisional = UgeifCertification.model_construct(
        schema_version="ugeif-certification-0.1",
        certification_id=f"UGEIF-CERT-{index:04d}",
        project_id=project_id,
        deployment_hash=deployment_hash,
        checks=normalized_checks,
        status=UgeifCertificationStatus.CERTIFIED
        if all(normalized_checks.values())
        else UgeifCertificationStatus.NOT_CERTIFIED,
        evidence_hashes=tuple(sorted(set(evidence_hashes))),
        certification_hash="0" * 64,
    )
    return UgeifCertification(
        **provisional.model_dump(exclude={"certification_hash"}),
        certification_hash=_certification_hash(provisional),
    )


def reusable_pattern(
    *,
    index: int,
    organization_id: str,
    pattern_name: str,
    pattern_type: str,
    occurrence_refs: tuple[str, ...],
    evidence_hashes: tuple[str, ...],
    generalized_document: dict[str, object],
) -> UgeifReusablePattern:
    provisional = UgeifReusablePattern.model_construct(
        schema_version="ugeif-reusable-pattern-0.1",
        pattern_id=f"UGEIF-PAT-{index:04d}",
        organization_id=organization_id,
        pattern_name=pattern_name,
        pattern_type=pattern_type,
        occurrence_refs=tuple(sorted(set(occurrence_refs))),
        evidence_hashes=tuple(sorted(set(evidence_hashes))),
        generalized_document=dict(sorted(generalized_document.items())),
        human_review_required=True,
        pattern_hash="0" * 64,
    )
    return UgeifReusablePattern(
        **provisional.model_dump(exclude={"pattern_hash"}),
        pattern_hash=_reusable_pattern_hash(provisional),
    )


def knowledge_generalization(
    *,
    index: int,
    organization_id: str,
    source_project_ids: tuple[str, ...],
    category: str,
    reusable_asset_ref: str,
    source_evidence_hashes: tuple[str, ...],
    generalized_document: dict[str, object],
    redaction_policy: str = "client-data-isolation-v1",
    client_isolation_verified: bool = True,
) -> UgeifKnowledgeGeneralization:
    provisional = UgeifKnowledgeGeneralization.model_construct(
        schema_version="ugeif-knowledge-generalization-0.1",
        knowledge_id=f"UGEIF-KNOW-{index:04d}",
        organization_id=organization_id,
        source_project_ids=tuple(sorted(set(source_project_ids))),
        category=category,
        reusable_asset_ref=reusable_asset_ref,
        source_evidence_hashes=tuple(sorted(set(source_evidence_hashes))),
        redaction_policy=redaction_policy,
        client_isolation_verified=client_isolation_verified,
        generalized_document=dict(sorted(generalized_document.items())),
        knowledge_hash="0" * 64,
    )
    return UgeifKnowledgeGeneralization(
        **provisional.model_dump(exclude={"knowledge_hash"}),
        knowledge_hash=_knowledge_generalization_hash(provisional),
    )


def industry_framework_pack(
    *,
    index: int,
    industry: str,
    version: str,
    manifest_templates: tuple[str, ...] = (),
    registry_extensions: tuple[str, ...] = (),
    governance_policies: tuple[str, ...] = (),
    compliance_mappings: tuple[str, ...] = (),
    artifact_templates: tuple[str, ...] = (),
) -> UgeifIndustryFrameworkPack:
    provisional = UgeifIndustryFrameworkPack.model_construct(
        schema_version="ugeif-industry-framework-pack-0.1",
        framework_id=f"UGEIF-IND-{index:04d}",
        industry=industry,
        version=version,
        manifest_templates=tuple(sorted(set(manifest_templates))),
        registry_extensions=tuple(sorted(set(registry_extensions))),
        governance_policies=tuple(sorted(set(governance_policies))),
        compliance_mappings=tuple(sorted(set(compliance_mappings))),
        artifact_templates=tuple(sorted(set(artifact_templates))),
        framework_hash="0" * 64,
    )
    return UgeifIndustryFrameworkPack(
        **provisional.model_dump(exclude={"framework_hash"}),
        framework_hash=_industry_framework_pack_hash(provisional),
    )


def compliance_framework_pack(
    *,
    index: int,
    framework: str,
    version: str,
    controls: tuple[str, ...],
    audit_evidence_mappings: tuple[str, ...],
    validation_rules: tuple[str, ...],
    documentation_templates: tuple[str, ...] = (),
) -> UgeifComplianceFrameworkPack:
    provisional = UgeifComplianceFrameworkPack.model_construct(
        schema_version="ugeif-compliance-framework-pack-0.1",
        compliance_id=f"UGEIF-COMP-{index:04d}",
        framework=framework,
        version=version,
        controls=tuple(sorted(set(controls))),
        audit_evidence_mappings=tuple(sorted(set(audit_evidence_mappings))),
        validation_rules=tuple(sorted(set(validation_rules))),
        documentation_templates=tuple(sorted(set(documentation_templates))),
        compliance_hash="0" * 64,
    )
    return UgeifComplianceFrameworkPack(
        **provisional.model_dump(exclude={"compliance_hash"}),
        compliance_hash=_compliance_framework_pack_hash(provisional),
    )


def marketplace_asset_certification(
    *,
    index: int,
    asset_kind: UgeifAssetKind,
    asset_ref: str,
    asset_version: str,
    asset_hash: str,
    signer_ref: str,
    signature_ref: str,
    signature_algorithm: str = "ed25519",
    checks: dict[str, bool],
) -> UgeifMarketplaceAssetCertification:
    normalized_checks = dict(sorted(checks.items()))
    provisional = UgeifMarketplaceAssetCertification.model_construct(
        schema_version="ugeif-marketplace-asset-certification-0.1",
        marketplace_certification_id=f"UGEIF-MKT-{index:04d}",
        asset_kind=asset_kind,
        asset_ref=asset_ref,
        asset_version=asset_version,
        asset_hash=asset_hash,
        signer_ref=signer_ref,
        signature_ref=signature_ref,
        signature_algorithm=signature_algorithm,
        checks=normalized_checks,
        status=UgeifCertificationStatus.CERTIFIED
        if all(normalized_checks.values())
        else UgeifCertificationStatus.NOT_CERTIFIED,
        certification_hash="0" * 64,
    )
    return UgeifMarketplaceAssetCertification(
        **provisional.model_dump(exclude={"certification_hash"}),
        certification_hash=_marketplace_asset_certification_hash(provisional),
    )


def predictive_analysis(
    *,
    index: int,
    project_id: str,
    prediction_type: str,
    signals: dict[str, float],
    planning_recommendation: str,
) -> UgeifPredictiveAnalysis:
    normalized = dict(sorted(signals.items()))
    score = round(sum(normalized.values()) / len(normalized), 2) if normalized else 0.0
    provisional = UgeifPredictiveAnalysis.model_construct(
        schema_version="ugeif-predictive-analysis-0.1",
        prediction_id=f"UGEIF-PRED-{index:04d}",
        project_id=project_id,
        prediction_type=prediction_type,
        signals=normalized,
        risk_score=score,
        planning_recommendation=planning_recommendation,
        may_auto_modify=False,
        prediction_hash="0" * 64,
    )
    return UgeifPredictiveAnalysis(
        **provisional.model_dump(exclude={"prediction_hash"}),
        prediction_hash=_predictive_analysis_hash(provisional),
    )


def ai_learning_boundary(
    *,
    index: int,
    source_ref: str,
    source_type: str,
    status: UgeifLearningSourceStatus,
    allowed_uses: tuple[str, ...] = (),
    prohibited_uses: tuple[str, ...] = (),
    evidence_hashes: tuple[str, ...] = (),
) -> UgeifAiLearningBoundary:
    default_prohibited = (
        "unapproved_modifications",
        "runtime_speculation",
        "temporary_execution_state",
    )
    normalized_prohibited = tuple(sorted(set(prohibited_uses or default_prohibited)))
    provisional = UgeifAiLearningBoundary.model_construct(
        schema_version="ugeif-ai-learning-boundary-0.1",
        boundary_id=f"UGEIF-AIL-{index:04d}",
        source_ref=source_ref,
        source_type=source_type,
        status=status,
        allowed_uses=tuple(sorted(set(allowed_uses))),
        prohibited_uses=normalized_prohibited,
        evidence_hashes=tuple(sorted(set(evidence_hashes))),
        boundary_hash="0" * 64,
    )
    return UgeifAiLearningBoundary(
        **provisional.model_dump(exclude={"boundary_hash"}),
        boundary_hash=_ai_learning_boundary_hash(provisional),
    )


def federated_governance_sync(
    *,
    index: int,
    organization_id: str,
    portfolio_ref: str,
    project_refs: tuple[str, ...],
    shared_asset_refs: tuple[str, ...],
    checks: dict[str, bool],
    governance_policy_refs: tuple[str, ...] = (),
) -> UgeifFederatedGovernanceSync:
    normalized_checks = dict(sorted(checks.items()))
    provisional = UgeifFederatedGovernanceSync.model_construct(
        schema_version="ugeif-federated-governance-sync-0.1",
        sync_id=f"UGEIF-FED-{index:04d}",
        organization_id=organization_id,
        portfolio_ref=portfolio_ref,
        project_refs=tuple(sorted(set(project_refs))),
        shared_asset_refs=tuple(sorted(set(shared_asset_refs))),
        governance_policy_refs=tuple(sorted(set(governance_policy_refs))),
        checks=normalized_checks,
        status=UgeifSynchronizationStatus.SYNCHRONIZED
        if all(normalized_checks.values())
        else UgeifSynchronizationStatus.ATTENTION_REQUIRED,
        project_independence_preserved=True,
        sync_hash="0" * 64,
    )
    return UgeifFederatedGovernanceSync(
        **provisional.model_dump(exclude={"sync_hash"}),
        sync_hash=_federated_governance_sync_hash(provisional),
    )


def technology_evolution_plan(
    *,
    index: int,
    project_id: str,
    manifest_version: str,
    approved_proposal_hash: str,
    current_technology: dict[str, str],
    target_technology: dict[str, str],
    migration_plan_refs: tuple[str, ...],
    business_intent_ref: str,
    simulation_hashes: tuple[str, ...] = (),
    certification_hashes: tuple[str, ...] = (),
) -> UgeifTechnologyEvolutionPlan:
    provisional = UgeifTechnologyEvolutionPlan.model_construct(
        schema_version="ugeif-technology-evolution-plan-0.1",
        technology_evolution_id=f"UGEIF-TECH-{index:04d}",
        project_id=project_id,
        manifest_version=manifest_version,
        approved_proposal_hash=approved_proposal_hash,
        current_technology=dict(sorted(current_technology.items())),
        target_technology=dict(sorted(target_technology.items())),
        migration_plan_refs=tuple(sorted(set(migration_plan_refs))),
        simulation_hashes=tuple(sorted(set(simulation_hashes))),
        certification_hashes=tuple(sorted(set(certification_hashes))),
        business_intent_ref=business_intent_ref,
        preserves_business_intent=True,
        requires_human_approval=True,
        plan_hash="0" * 64,
    )
    return UgeifTechnologyEvolutionPlan(
        **provisional.model_dump(exclude={"plan_hash"}),
        plan_hash=_technology_evolution_plan_hash(provisional),
    )


def _assessment_status(score: float) -> UgeifAssessmentStatus:
    if score >= 80:
        return UgeifAssessmentStatus.PASSING
    if score >= 60:
        return UgeifAssessmentStatus.NEEDS_ATTENTION
    return UgeifAssessmentStatus.BLOCKED


def _governance_assessment_hash(value: UgeifGovernanceAssessment) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"assessment_hash"}))


def _validation_report_hash(value: UgeifValidationReport) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"report_hash"}))


def _change_proposal_hash(value: UgeifChangeProposal) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"proposal_hash"}))


def _impact_analysis_hash(value: UgeifImpactAnalysis) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"impact_hash"}))


def _simulation_report_hash(value: UgeifSimulationReport) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"simulation_hash"}))


def _risk_profile_hash(value: UgeifRiskProfile) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"risk_hash"}))


def _quality_scorecard_hash(value: UgeifQualityScorecard) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"scorecard_hash"}))


def _operational_recommendation_hash(value: UgeifOperationalRecommendation) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"recommendation_hash"}))


def _feedback_loop_record_hash(value: UgeifFeedbackLoopRecord) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"feedback_hash"}))


def _version_graph_hash(value: UgeifVersionGraphSnapshot) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"graph_hash"}))


def _timeline_entry_hash(value: UgeifTimelineEntry) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"entry_hash"}))


def _certification_hash(value: UgeifCertification) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"certification_hash"}))


def _reusable_pattern_hash(value: UgeifReusablePattern) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"pattern_hash"}))


def _knowledge_generalization_hash(value: UgeifKnowledgeGeneralization) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"knowledge_hash"}))


def _industry_framework_pack_hash(value: UgeifIndustryFrameworkPack) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"framework_hash"}))


def _compliance_framework_pack_hash(value: UgeifComplianceFrameworkPack) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"compliance_hash"}))


def _marketplace_asset_certification_hash(
    value: UgeifMarketplaceAssetCertification,
) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"certification_hash"}))


def _predictive_analysis_hash(value: UgeifPredictiveAnalysis) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"prediction_hash"}))


def _ai_learning_boundary_hash(value: UgeifAiLearningBoundary) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"boundary_hash"}))


def _federated_governance_sync_hash(value: UgeifFederatedGovernanceSync) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"sync_hash"}))


def _technology_evolution_plan_hash(value: UgeifTechnologyEvolutionPlan) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"plan_hash"}))
