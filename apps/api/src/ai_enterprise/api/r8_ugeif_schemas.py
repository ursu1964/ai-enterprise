from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class R8GovernanceAssessmentRequest(BaseModel):
    manifest_version: str = Field(min_length=1, max_length=120)
    scores: dict[str, float]
    recommendations: list[str] = Field(default_factory=list)


class R8ValidationReportRequest(BaseModel):
    manifest_version: str = Field(min_length=1, max_length=120)
    findings_by_category: dict[str, list[str]]


class R8ChangeProposalRequest(BaseModel):
    change_type: str = Field(
        pattern=r"^(business|technical|infrastructure|security|compliance|performance|ai)$"
    )
    title: str = Field(min_length=1, max_length=240)
    intent_ref: str = Field(min_length=1, max_length=200)
    current_manifest_version: str = Field(min_length=1, max_length=120)
    proposed_manifest_version: str = Field(min_length=1, max_length=120)
    evidence_hashes: list[str] = Field(default_factory=list)


class R8ImpactAnalysisRequest(BaseModel):
    affected_artifacts: list[str] = Field(default_factory=list)
    affected_dependencies: list[str] = Field(default_factory=list)
    affected_workflows: list[str] = Field(default_factory=list)
    affected_permissions: list[str] = Field(default_factory=list)
    affected_documentation: list[str] = Field(default_factory=list)


class R8SimulationReportRequest(BaseModel):
    impact_analysis_id: uuid.UUID
    checks: dict[str, bool]


class R8RiskProfileRequest(BaseModel):
    dimensions: dict[str, float]


class R8QualityScorecardRequest(BaseModel):
    deployment_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    scores: dict[str, float]


class R8OperationalRecommendationRequest(BaseModel):
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    category: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    recommendation: str = Field(min_length=1, max_length=1000)


class R8FeedbackLoopRecordRequest(BaseModel):
    runtime_source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    metrics: dict[str, float]
    analytics: list[str] = Field(default_factory=list)
    recommendation_refs: list[str] = Field(default_factory=list)


class R8VersionGraphRequest(BaseModel):
    nodes: list[dict[str, str]]
    edges: list[dict[str, str]] = Field(default_factory=list)


class R8TimelineEntryRequest(BaseModel):
    event_type: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    object_ref: str = Field(min_length=1, max_length=200)
    object_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class R8CertificationRequest(BaseModel):
    deployment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    checks: dict[str, bool]
    evidence_hashes: list[str] = Field(default_factory=list)


class R8ReusablePatternRequest(BaseModel):
    organization_id: str = Field(min_length=1)
    pattern_name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,159}$")
    pattern_type: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    occurrence_refs: list[str]
    evidence_hashes: list[str]
    generalized_document: dict[str, Any]


class R8KnowledgeGeneralizationRequest(BaseModel):
    organization_id: str = Field(min_length=1)
    source_project_ids: list[str]
    category: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    reusable_asset_ref: str = Field(min_length=1, max_length=240)
    source_evidence_hashes: list[str]
    generalized_document: dict[str, Any]
    redaction_policy: str = Field(default="client-data-isolation-v1", max_length=120)
    client_isolation_verified: bool = True


class R8IndustryFrameworkPackRequest(BaseModel):
    industry: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,119}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+$")
    manifest_templates: list[str] = Field(default_factory=list)
    registry_extensions: list[str] = Field(default_factory=list)
    governance_policies: list[str] = Field(default_factory=list)
    compliance_mappings: list[str] = Field(default_factory=list)
    artifact_templates: list[str] = Field(default_factory=list)


class R8ComplianceFrameworkPackRequest(BaseModel):
    framework: str = Field(pattern=r"^[A-Z][A-Z0-9 _.-]{1,79}$")
    version: str = Field(min_length=1, max_length=80)
    controls: list[str]
    audit_evidence_mappings: list[str]
    validation_rules: list[str]
    documentation_templates: list[str] = Field(default_factory=list)


class R8MarketplaceAssetCertificationRequest(BaseModel):
    asset_kind: str = Field(
        pattern=(
            r"^(manifest_template|registry_module|generator_pack|template_pack|"
            r"governance_policy|workflow_library|compliance_module)$"
        )
    )
    asset_ref: str = Field(min_length=1, max_length=240)
    asset_version: str = Field(min_length=1, max_length=80)
    asset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    signer_ref: str = Field(min_length=1, max_length=200)
    signature_ref: str = Field(min_length=1, max_length=300)
    signature_algorithm: str = Field(default="ed25519", pattern=r"^[a-z0-9_.-]{3,80}$")
    checks: dict[str, bool]


class R8PredictiveAnalysisRequest(BaseModel):
    prediction_type: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    signals: dict[str, float]
    planning_recommendation: str = Field(min_length=1, max_length=1000)


class R8AiLearningBoundaryRequest(BaseModel):
    source_ref: str = Field(min_length=1, max_length=240)
    source_type: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    status: str = Field(pattern=r"^(approved|denied)$")
    allowed_uses: list[str] = Field(default_factory=list)
    prohibited_uses: list[str] = Field(default_factory=list)
    evidence_hashes: list[str] = Field(default_factory=list)


class R8FederatedGovernanceSyncRequest(BaseModel):
    organization_id: str = Field(min_length=1)
    portfolio_ref: str = Field(min_length=1, max_length=200)
    project_refs: list[str]
    shared_asset_refs: list[str]
    governance_policy_refs: list[str] = Field(default_factory=list)
    checks: dict[str, bool]


class R8TechnologyEvolutionPlanRequest(BaseModel):
    manifest_version: str = Field(min_length=1, max_length=120)
    approved_proposal_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_technology: dict[str, str]
    target_technology: dict[str, str]
    migration_plan_refs: list[str]
    business_intent_ref: str = Field(min_length=1, max_length=200)
    simulation_hashes: list[str] = Field(default_factory=list)
    certification_hashes: list[str] = Field(default_factory=list)


class R8HumanDecisionRequest(BaseModel):
    decision: str = Field(pattern=r"^(approve|reject)$")
    rationale: str = Field(min_length=1, max_length=2000)


class R8RecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    record_type: str
    record_id: str
    status: str
    lifecycle_state: str | None
    approval_status: str | None
    record_document: dict[str, Any]
    record_hash: str


class R8GovernanceDashboardResponse(BaseModel):
    project_id: uuid.UUID
    latest_governance_status: str | None
    latest_validation_status: str | None
    latest_quality_status: str | None
    latest_certification_status: str | None
    open_recommendation_count: int
    feedback_loop_count: int
    pending_approval_count: int
    timeline_entry_count: int
    reusable_pattern_count: int
    knowledge_generalization_count: int
    industry_framework_pack_count: int
    compliance_framework_pack_count: int
    certified_marketplace_asset_count: int
    predictive_analysis_count: int
    maximum_predictive_risk_score: float | None
    approved_ai_learning_source_count: int
    denied_ai_learning_source_count: int
    federated_governance_sync_count: int
    federated_sync_attention_required_count: int
    technology_evolution_plan_count: int
