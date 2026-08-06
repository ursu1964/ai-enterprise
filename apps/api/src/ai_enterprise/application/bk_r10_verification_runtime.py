from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict

from ai_enterprise.domain.specification.kernel import specification_hash

BK_R10_VERSION = "verification-validation-engine-1.0"
DETERMINISTIC_VERIFICATION_TIMESTAMP = "1970-01-01T00:00:00Z"

CAMPAIGN_STATES: tuple[str, ...] = (
    "DRAFT",
    "PLANNING",
    "PLAN_READY",
    "APPROVED",
    "ENVIRONMENT_PREPARING",
    "READY",
    "EXECUTING",
    "SUSPENDED",
    "BLOCKED",
    "ANALYZING",
    "VERIFIED",
    "VALIDATING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "SUPERSEDED",
    "ARCHIVED",
)

VERIFICATION_METHODS: tuple[str, ...] = (
    "TEST",
    "INSPECTION",
    "ANALYSIS",
    "DEMONSTRATION",
    "AUDIT",
    "REVIEW",
    "OBSERVATION",
    "SIMULATION",
    "FORMAL_VERIFICATION",
    "STATIC_ANALYSIS",
    "CONTRACT_VALIDATION",
    "POLICY_EVALUATION",
    "THREAT_VALIDATION",
    "PERFORMANCE_MEASUREMENT",
    "RESILIENCE_EXERCISE",
    "MIGRATION_REHEARSAL",
    "USABILITY_ASSESSMENT",
    "ACCESSIBILITY_ASSESSMENT",
    "STAKEHOLDER_ACCEPTANCE",
)

TEST_TYPES: tuple[str, ...] = (
    "UNIT",
    "DOMAIN_INVARIANT",
    "PROPERTY_BASED",
    "SCHEMA",
    "MIGRATION",
    "DATA_INTEGRITY",
    "API_CONTRACT",
    "EVENT_CONTRACT",
    "COMPONENT",
    "INTEGRATION",
    "SYSTEM",
    "END_TO_END",
    "REGRESSION",
    "AUTHENTICATION",
    "AUTHORIZATION",
    "SECURITY",
    "PRIVACY",
    "POLICY",
    "COMPLIANCE",
    "PERFORMANCE",
    "LOAD",
    "STRESS",
    "SOAK",
    "SCALABILITY",
    "RESILIENCE",
    "FAILOVER",
    "RECOVERY",
    "BACKUP_RESTORE",
    "COMPATIBILITY",
    "ACCESSIBILITY",
    "USABILITY",
    "OBSERVABILITY",
    "DEPLOYMENT",
    "ROLLBACK",
    "CHAOS",
    "AI_BEHAVIOR",
    "AI_SAFETY",
    "PROMPT_INJECTION",
    "MODEL_EVALUATION",
)

FINAL_OBLIGATION_STATES: tuple[str, ...] = (
    "PASSED",
    "FAILED",
    "BLOCKED",
    "WAIVED",
    "INCONCLUSIVE",
)

EXTERNAL_BACKENDS: tuple[str, ...] = (
    "ci_runner",
    "scanner",
    "evidence_store",
    "policy_engine",
    "lab_environment",
)


class BKR10Diagnostic(BaseModel):
    model_config = ConfigDict(frozen=True)

    severity: str
    category: str
    code: str
    message: str
    path: str


class BKR10ActorReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    actor_type: str
    actor_id: str
    role: str


class BKR10VerificationHandoff(BaseModel):
    model_config = ConfigDict(frozen=True)

    verification_handoff_id: str
    implementation_result_id: str
    implementation_slice_id: str
    repository_revision: str
    requirement_baseline_id: str
    architecture_baseline_id: str
    planning_baseline_id: str
    policy_refs: tuple[str, ...]
    produced_by: BKR10ActorReference
    artifact_refs: tuple[str, ...]
    handoff_hash: str


class BKR10VerificationObligation(BaseModel):
    model_config = ConfigDict(frozen=True)

    verification_obligation_id: str
    requirement_id: str | None
    acceptance_criterion_id: str | None
    architecture_element_id: str | None
    policy_reference: str | None
    obligation_type: str
    method: str
    criticality: str
    mandatory: bool
    responsible_authority: BKR10ActorReference
    required_environment_profile: str | None
    required_evidence_types: tuple[str, ...]
    pass_conditions: tuple[str, ...]
    fail_conditions: tuple[str, ...]
    status: str


class BKR10VerificationProcedure(BaseModel):
    model_config = ConfigDict(frozen=True)

    verification_procedure_id: str
    verification_obligation_ids: tuple[str, ...]
    title: str
    procedure_type: str
    ordered_steps: tuple[str, ...]
    expected_results: tuple[str, ...]
    required_tools: tuple[str, ...]
    required_environment_profile: str
    version: str
    content_hash: str
    approval_reference: str | None


class BKR10VerificationEnvironment(BaseModel):
    model_config = ConfigDict(frozen=True)

    verification_environment_id: str
    environment_type: str
    environment_profile: str
    runtime_versions: dict[str, str]
    infrastructure_reference: str
    repository_revision: str
    configuration_hashes: tuple[str, ...]
    dependency_lock_hashes: tuple[str, ...]
    network_policy: str
    secret_scope: tuple[str, ...]
    integrity_status: str
    verified_at: str | None
    evidence_reference: str | None
    environment_hash: str


class BKR10VerificationExecution(BaseModel):
    model_config = ConfigDict(frozen=True)

    verification_execution_id: str
    verification_campaign_id: str
    procedure_id: str
    environment_id: str
    execution_attempt: int
    executor: BKR10ActorReference
    tool_versions: dict[str, str]
    input_hashes: tuple[str, ...]
    started_at: str
    completed_at: str | None
    status: str
    raw_result_reference: str | None
    result_id: str | None
    correlation_id: str
    execution_hash: str


class BKR10ObligationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    verification_obligation_id: str
    status: str
    evidence_references: tuple[str, ...]
    notes: str | None = None


class BKR10VerificationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    verification_result_id: str
    verification_execution_id: str
    obligation_results: tuple[BKR10ObligationResult, ...]
    observed_outputs: dict[str, Any]
    defects_detected: tuple[str, ...]
    warnings: tuple[str, ...]
    raw_evidence_references: tuple[str, ...]
    normalized_evidence_references: tuple[str, ...]
    verdict: str
    confidence: float | None
    classified_by: BKR10ActorReference
    reviewed_by: BKR10ActorReference | None
    content_hash: str
    created_at: str


class BKR10VerificationFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    finding_id: str
    verification_campaign_id: str
    finding_type: str
    severity: str
    description: str
    affected_requirements: tuple[str, ...]
    affected_implementation_references: tuple[str, ...]
    owner: BKR10ActorReference
    status: str
    evidence_references: tuple[str, ...]
    finding_hash: str


class BKR10VerificationWaiver(BaseModel):
    model_config = ConfigDict(frozen=True)

    waiver_id: str
    verification_campaign_id: str
    obligation_id: str
    authority: BKR10ActorReference
    justification: str
    risk_acceptance: str
    scope: str
    expires_at: str
    compensating_controls: tuple[str, ...]
    status: str
    waiver_hash: str


class BKR10CoverageAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    coverage_assessment_id: str
    verification_campaign_id: str
    total_mandatory_obligations: int
    passed_mandatory_obligations: int
    failed_mandatory_obligations: int
    blocked_mandatory_obligations: int
    waived_mandatory_obligations: int
    incomplete_mandatory_obligations: int
    critical_gaps: tuple[dict[str, Any], ...]
    coverage_hash: str


class BKR10CampaignVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    verdict_id: str
    verification_campaign_id: str
    verification_status: str
    validation_status: str
    policy_status: str
    security_status: str
    coverage_status: str
    final_verdict: str
    blocking_findings: tuple[str, ...]
    diagnostics: tuple[BKR10Diagnostic, ...]
    verdict_hash: str


class BKR10SatisfactionRecommendation(BaseModel):
    model_config = ConfigDict(frozen=True)

    satisfaction_recommendation_id: str
    verification_campaign_id: str
    requirement_id: str
    verification_status: str
    validation_status: str
    blocking_findings: tuple[str, ...]
    waiver_references: tuple[str, ...]
    evidence_references: tuple[str, ...]
    recommendation: str
    generated_by: BKR10ActorReference
    approved_by: BKR10ActorReference | None
    created_at: str
    recommendation_hash: str


class BKR10DomainEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    event_type: str
    event_version: int
    occurred_at: str
    organization_id: str
    project_id: str
    campaign_id: str
    actor: BKR10ActorReference
    payload: dict[str, Any]
    correlation_id: str
    event_hash: str


class BKR10ExternalBackendConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    backend_type: str
    provider: str
    enabled: bool = False
    endpoint_reference: str | None = None
    credential_reference: str | None = None
    repository_reference: str | None = None
    evidence_reference: str | None = None
    policy_reference: str | None = None
    timeout_seconds: int = 300
    mock_mode: bool = False


class BKR10BackendReadiness(BaseModel):
    model_config = ConfigDict(frozen=True)

    backend_type: str
    provider: str
    configured: bool
    production_ready: bool
    diagnostics: tuple[BKR10Diagnostic, ...]
    readiness_hash: str


class BKR10ExternalReadinessReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    environment: str
    production_ready: bool
    backends: tuple[BKR10BackendReadiness, ...]
    diagnostics: tuple[BKR10Diagnostic, ...]
    readiness_hash: str


class BKR10ExternalExecutionRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    procedure_id: str
    obligation_ids: tuple[str, ...]
    repository_revision: str
    environment_id: str
    tool: str
    inputs: dict[str, Any]


class BKR10ExternalExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    backend_type: str
    status: str
    obligation_results: tuple[BKR10ObligationResult, ...]
    raw_evidence_references: tuple[str, ...]
    normalized_evidence_references: tuple[str, ...]
    metrics: dict[str, int]
    diagnostics: tuple[BKR10Diagnostic, ...]
    result_hash: str


class BKR10ConformanceCriterion(BaseModel):
    model_config = ConfigDict(frozen=True)

    criterion_id: str
    description: str
    status: str
    evidence_paths: tuple[str, ...]
    diagnostics: tuple[BKR10Diagnostic, ...]


class BKR10ConformanceReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    report_id: str
    version: str
    status: str
    criteria: tuple[BKR10ConformanceCriterion, ...]
    summary: dict[str, int]
    report_hash: str


class BKR10ExternalAdapterError(RuntimeError):
    pass


class BKR10ExternalVerificationAdapter(Protocol):
    def execute(
        self,
        request: BKR10ExternalExecutionRequest,
        config: BKR10ExternalBackendConfig,
    ) -> BKR10ExternalExecutionResult: ...


class BKR10MockVerificationAdapter:
    def execute(
        self,
        request: BKR10ExternalExecutionRequest,
        config: BKR10ExternalBackendConfig,
    ) -> BKR10ExternalExecutionResult:
        status = str(request.inputs.get("status", "PASSED"))
        obligation_results = tuple(
            BKR10ObligationResult(
                verification_obligation_id=obligation_id,
                status=status,
                evidence_references=(
                    f"mock-evidence://{config.backend_type}/{request.procedure_id}/{obligation_id}",
                ),
                notes=request.inputs.get("notes"),
            )
            for obligation_id in request.obligation_ids
        )
        payload = {
            "provider": config.provider,
            "backend_type": config.backend_type,
            "request": request.model_dump(mode="json"),
            "status": status,
        }
        result_hash = specification_hash(payload)
        return BKR10ExternalExecutionResult(
            provider=config.provider,
            backend_type=config.backend_type,
            status=status,
            obligation_results=obligation_results,
            raw_evidence_references=(f"mock-evidence://raw/{result_hash[:16]}",),
            normalized_evidence_references=(f"mock-evidence://normalized/{result_hash[:16]}",),
            metrics={"external_calls": 0 if config.mock_mode else 1},
            diagnostics=(),
            result_hash=result_hash,
        )


class BKR10HTTPVerificationAdapter:
    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        self.transport = transport

    def execute(
        self,
        request: BKR10ExternalExecutionRequest,
        config: BKR10ExternalBackendConfig,
    ) -> BKR10ExternalExecutionResult:
        if not config.endpoint_reference:
            raise BKR10ExternalAdapterError("BK/R10 HTTP adapter requires endpoint_reference")
        headers = {
            "content-type": "application/json",
            "x-bk-r10-provider": config.provider,
            "x-bk-r10-backend-type": config.backend_type,
        }
        if config.credential_reference:
            headers["authorization"] = f"Reference {config.credential_reference}"
        payload = {
            "procedure_id": request.procedure_id,
            "obligation_ids": list(request.obligation_ids),
            "repository_revision": request.repository_revision,
            "environment_id": request.environment_id,
            "tool": request.tool,
            "inputs": request.inputs,
        }
        try:
            with httpx.Client(
                timeout=float(config.timeout_seconds),
                transport=self.transport,
            ) as client:
                response = client.post(config.endpoint_reference, headers=headers, json=payload)
                response.raise_for_status()
                response_payload = response.json()
        except httpx.HTTPError as exc:
            raise BKR10ExternalAdapterError(f"BK/R10 HTTP adapter request failed: {exc}") from exc
        try:
            return _external_result_from_payload(request, config, response_payload)
        except Exception as exc:
            raise BKR10ExternalAdapterError(
                "BK/R10 HTTP adapter returned an invalid verification result"
            ) from exc


class BKR10VerificationCampaign(BaseModel):
    model_config = ConfigDict(frozen=True)

    verification_campaign_id: str
    organization_id: str
    project_id: str
    implementation_slice_id: str
    implementation_result_id: str
    verification_handoff: BKR10VerificationHandoff
    status: str
    criticality: str
    risk_classification: str
    owner: BKR10ActorReference
    obligations: tuple[BKR10VerificationObligation, ...]
    procedures: tuple[BKR10VerificationProcedure, ...]
    environments: tuple[BKR10VerificationEnvironment, ...]
    executions: tuple[BKR10VerificationExecution, ...]
    results: tuple[BKR10VerificationResult, ...]
    findings: tuple[BKR10VerificationFinding, ...]
    waivers: tuple[BKR10VerificationWaiver, ...]
    coverage: BKR10CoverageAssessment | None
    verdict: BKR10CampaignVerdict | None
    satisfaction_recommendations: tuple[BKR10SatisfactionRecommendation, ...]
    events: tuple[BKR10DomainEvent, ...]
    started_at: str | None
    completed_at: str | None
    content_hash: str


def bk_r10_create_handoff(
    *,
    implementation_result_id: str,
    implementation_slice_id: str,
    repository_revision: str,
    requirement_baseline_id: str,
    architecture_baseline_id: str,
    planning_baseline_id: str,
    produced_by: dict[str, str],
    policy_refs: tuple[str, ...] = (),
    artifact_refs: tuple[str, ...] = (),
) -> BKR10VerificationHandoff:
    actor = BKR10ActorReference.model_validate(produced_by)
    payload = {
        "implementation_result_id": implementation_result_id,
        "implementation_slice_id": implementation_slice_id,
        "repository_revision": repository_revision,
        "requirement_baseline_id": requirement_baseline_id,
        "architecture_baseline_id": architecture_baseline_id,
        "planning_baseline_id": planning_baseline_id,
        "policy_refs": policy_refs,
        "artifact_refs": artifact_refs,
    }
    handoff_hash = specification_hash(payload)
    return BKR10VerificationHandoff(
        verification_handoff_id=f"bk-r10-handoff-{handoff_hash[:16]}",
        implementation_result_id=implementation_result_id,
        implementation_slice_id=implementation_slice_id,
        repository_revision=repository_revision,
        requirement_baseline_id=requirement_baseline_id,
        architecture_baseline_id=architecture_baseline_id,
        planning_baseline_id=planning_baseline_id,
        policy_refs=policy_refs,
        produced_by=actor,
        artifact_refs=artifact_refs,
        handoff_hash=handoff_hash,
    )


def bk_r10_external_readiness(
    configs: tuple[dict[str, Any] | BKR10ExternalBackendConfig, ...],
    *,
    environment: str = "development",
    required_backends: tuple[str, ...] | None = EXTERNAL_BACKENDS,
) -> BKR10ExternalReadinessReport:
    normalized = tuple(
        config
        if isinstance(config, BKR10ExternalBackendConfig)
        else BKR10ExternalBackendConfig.model_validate(config)
        for config in configs
    )
    by_type = {item.backend_type: item for item in normalized}
    reports: list[BKR10BackendReadiness] = []
    diagnostics: list[BKR10Diagnostic] = []
    production = environment.lower() in {"production", "staging"}
    required = required_backends or EXTERNAL_BACKENDS
    for backend_type in required:
        config = by_type.get(backend_type)
        if config is None:
            backend_diagnostics = (
                _diag(
                    "error" if production else "warning",
                    "readiness",
                    "BK_R10_BACKEND_MISSING",
                    f"{backend_type} backend is not configured",
                    f"$.backends.{backend_type}",
                ),
            )
            reports.append(
                BKR10BackendReadiness(
                    backend_type=backend_type,
                    provider="unconfigured",
                    configured=False,
                    production_ready=False,
                    diagnostics=backend_diagnostics,
                    readiness_hash=specification_hash(
                        {"backend_type": backend_type, "missing": True}
                    ),
                )
            )
            diagnostics.extend(backend_diagnostics)
            continue
        backend_diagnostics = _backend_diagnostics(config, production=production)
        configured = not any(item.severity == "error" for item in backend_diagnostics)
        production_ready = configured and config.enabled and not config.mock_mode
        if config.mock_mode and production:
            production_ready = False
        reports.append(
            BKR10BackendReadiness(
                backend_type=backend_type,
                provider=config.provider,
                configured=configured,
                production_ready=production_ready,
                diagnostics=backend_diagnostics,
                readiness_hash=specification_hash(
                    {
                        "backend_type": backend_type,
                        "provider": config.provider,
                        "configured": configured,
                        "production_ready": production_ready,
                    }
                ),
            )
        )
        diagnostics.extend(backend_diagnostics)
    production_ready = (
        all(item.production_ready for item in reports)
        if production
        else all(item.configured for item in reports)
    )
    payload = {
        "environment": environment,
        "production_ready": production_ready,
        "backends": [item.model_dump(mode="json") for item in reports],
    }
    return BKR10ExternalReadinessReport(
        environment=environment,
        production_ready=production_ready,
        backends=tuple(reports),
        diagnostics=tuple(diagnostics),
        readiness_hash=specification_hash(payload),
    )


def bk_r10_execute_external_verification(
    request: dict[str, Any] | BKR10ExternalExecutionRequest,
    config: dict[str, Any] | BKR10ExternalBackendConfig,
    *,
    adapter: BKR10ExternalVerificationAdapter | None = None,
    environment: str = "development",
) -> BKR10ExternalExecutionResult:
    validated_request = (
        request
        if isinstance(request, BKR10ExternalExecutionRequest)
        else BKR10ExternalExecutionRequest.model_validate(request)
    )
    validated_config = (
        config
        if isinstance(config, BKR10ExternalBackendConfig)
        else BKR10ExternalBackendConfig.model_validate(config)
    )
    readiness = bk_r10_external_readiness(
        (validated_config,),
        environment=environment,
        required_backends=(validated_config.backend_type,),
    )
    if readiness.diagnostics and any(item.severity == "error" for item in readiness.diagnostics):
        raise BKR10ExternalAdapterError(
            "; ".join(f"{item.code}: {item.message}" for item in readiness.diagnostics)
        )
    if environment.lower() in {"production", "staging"} and not readiness.production_ready:
        raise BKR10ExternalAdapterError("BK/R10 external backend is not production ready")
    selected = adapter or BKR10MockVerificationAdapter()
    return selected.execute(validated_request, validated_config)


def bk_r10_http_verification_adapter(
    *,
    transport: httpx.BaseTransport | None = None,
) -> BKR10HTTPVerificationAdapter:
    return BKR10HTTPVerificationAdapter(transport=transport)


def bk_r10_conformance_report(repo_root: Path) -> BKR10ConformanceReport:
    criteria = tuple(_conformance_criteria(repo_root))
    summary = {
        "total": len(criteria),
        "passed": sum(1 for item in criteria if item.status == "PASS"),
        "failed": sum(1 for item in criteria if item.status == "FAIL"),
    }
    status = "PASS" if summary["failed"] == 0 else "FAIL"
    payload = {
        "version": BK_R10_VERSION,
        "status": status,
        "criteria": [item.model_dump(mode="json") for item in criteria],
    }
    report_hash = specification_hash(payload)
    return BKR10ConformanceReport(
        report_id=f"bk-r10-conformance-{report_hash[:16]}",
        version=BK_R10_VERSION,
        status=status,
        criteria=criteria,
        summary=summary,
        report_hash=report_hash,
    )


def bk_r10_create_campaign(
    *,
    organization_id: str,
    project_id: str,
    handoff: dict[str, Any] | BKR10VerificationHandoff,
    owner: dict[str, str],
    obligations: tuple[dict[str, Any], ...],
    procedures: tuple[dict[str, Any], ...] = (),
    criticality: str = "MEDIUM",
    risk_classification: str = "standard",
) -> BKR10VerificationCampaign:
    validated_handoff = (
        handoff
        if isinstance(handoff, BKR10VerificationHandoff)
        else BKR10VerificationHandoff.model_validate(handoff)
    )
    validated_owner = BKR10ActorReference.model_validate(owner)
    campaign_seed = {
        "organization_id": organization_id,
        "project_id": project_id,
        "handoff_hash": validated_handoff.handoff_hash,
    }
    campaign_id = f"bk-r10-campaign-{specification_hash(campaign_seed)[:16]}"
    campaign = BKR10VerificationCampaign(
        verification_campaign_id=campaign_id,
        organization_id=organization_id,
        project_id=project_id,
        implementation_slice_id=validated_handoff.implementation_slice_id,
        implementation_result_id=validated_handoff.implementation_result_id,
        verification_handoff=validated_handoff,
        status="DRAFT",
        criticality=criticality,
        risk_classification=risk_classification,
        owner=validated_owner,
        obligations=tuple(_obligation(item) for item in obligations),
        procedures=tuple(_procedure(item) for item in procedures),
        environments=(),
        executions=(),
        results=(),
        findings=(),
        waivers=(),
        coverage=None,
        verdict=None,
        satisfaction_recommendations=(),
        events=(),
        started_at=None,
        completed_at=None,
        content_hash="",
    )
    campaign = _rehash_campaign(campaign)
    return _append_event(campaign, "VerificationCampaignCreated", validated_owner, {})


def bk_r10_qualify_environment(
    campaign: dict[str, Any] | BKR10VerificationCampaign,
    environment: dict[str, Any],
    *,
    actor: dict[str, str],
) -> BKR10VerificationCampaign:
    current = _campaign(campaign)
    qualified = _environment(environment, current.verification_handoff.repository_revision)
    event_type = (
        "VerificationEnvironmentQualified"
        if qualified.integrity_status == "VERIFIED"
        else "VerificationEnvironmentRejected"
    )
    next_campaign = current.model_copy(update={"environments": current.environments + (qualified,)})
    return _append_event(
        _rehash_campaign(next_campaign), event_type, _actor(actor), qualified.model_dump()
    )


def bk_r10_start_campaign(
    campaign: dict[str, Any] | BKR10VerificationCampaign,
    *,
    actor: dict[str, str],
) -> BKR10VerificationCampaign:
    current = _campaign(campaign)
    diagnostics = _entry_diagnostics(current)
    if diagnostics:
        finding = _finding(
            current,
            finding_type="COVERAGE_GAP",
            severity="HIGH",
            description="Campaign entry criteria are not met",
            affected_requirements=tuple(
                obligation.requirement_id
                for obligation in current.obligations
                if obligation.requirement_id
            ),
            evidence_references=(),
            owner=_actor(actor),
        )
        next_campaign = current.model_copy(
            update={"status": "BLOCKED", "findings": current.findings + (finding,)}
        )
        return _append_event(
            _rehash_campaign(next_campaign), "VerificationObligationBlocked", _actor(actor), {}
        )
    next_campaign = current.model_copy(
        update={"status": "EXECUTING", "started_at": DETERMINISTIC_VERIFICATION_TIMESTAMP}
    )
    return _append_event(
        _rehash_campaign(next_campaign),
        "VerificationCampaignStarted",
        _actor(actor),
        {},
    )


def bk_r10_record_result(
    campaign: dict[str, Any] | BKR10VerificationCampaign,
    *,
    procedure_id: str,
    environment_id: str,
    executor: dict[str, str],
    obligation_results: tuple[dict[str, Any], ...],
    raw_evidence_references: tuple[str, ...],
    normalized_evidence_references: tuple[str, ...] = (),
    observed_outputs: dict[str, Any] | None = None,
    defects_detected: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
) -> BKR10VerificationCampaign:
    current = _campaign(campaign)
    diagnostics = _result_diagnostics(
        current,
        procedure_id,
        environment_id,
        obligation_results,
        raw_evidence_references,
    )
    attempt = 1 + sum(1 for item in current.executions if item.procedure_id == procedure_id)
    executor_ref = _actor(executor)
    execution_seed = {
        "campaign": current.verification_campaign_id,
        "procedure": procedure_id,
        "attempt": attempt,
        "environment": environment_id,
    }
    execution_hash = specification_hash(execution_seed)
    result_status = "ERROR" if diagnostics else _aggregate_obligation_status(obligation_results)
    execution = BKR10VerificationExecution(
        verification_execution_id=f"bk-r10-exec-{execution_hash[:16]}",
        verification_campaign_id=current.verification_campaign_id,
        procedure_id=procedure_id,
        environment_id=environment_id,
        execution_attempt=attempt,
        executor=executor_ref,
        tool_versions={"bk-r10": BK_R10_VERSION},
        input_hashes=(current.verification_handoff.handoff_hash,),
        started_at=DETERMINISTIC_VERIFICATION_TIMESTAMP,
        completed_at=DETERMINISTIC_VERIFICATION_TIMESTAMP,
        status=result_status,
        raw_result_reference=raw_evidence_references[0] if raw_evidence_references else None,
        result_id=None,
        correlation_id=f"bk-r10-corr-{execution_hash[:12]}",
        execution_hash=execution_hash,
    )
    result_seed = {
        "execution_id": execution.verification_execution_id,
        "obligation_results": obligation_results,
        "raw_evidence": raw_evidence_references,
        "diagnostics": [item.model_dump(mode="json") for item in diagnostics],
    }
    result_hash = specification_hash(result_seed)
    result = BKR10VerificationResult(
        verification_result_id=f"bk-r10-result-{result_hash[:16]}",
        verification_execution_id=execution.verification_execution_id,
        obligation_results=tuple(
            BKR10ObligationResult.model_validate(item) for item in obligation_results
        ),
        observed_outputs=observed_outputs or {},
        defects_detected=defects_detected,
        warnings=warnings,
        raw_evidence_references=raw_evidence_references,
        normalized_evidence_references=normalized_evidence_references or raw_evidence_references,
        verdict="ERROR" if diagnostics else result_status,
        confidence=None if diagnostics else 1.0,
        classified_by=executor_ref,
        reviewed_by=None,
        content_hash=result_hash,
        created_at=DETERMINISTIC_VERIFICATION_TIMESTAMP,
    )
    execution = execution.model_copy(update={"result_id": result.verification_result_id})
    obligations = _apply_obligation_results(current.obligations, result.obligation_results)
    findings = current.findings + _findings_from_result(current, result, diagnostics, executor_ref)
    next_campaign = current.model_copy(
        update={
            "status": "ANALYZING",
            "obligations": obligations,
            "executions": current.executions + (execution,),
            "results": current.results + (result,),
            "findings": findings,
        }
    )
    next_campaign = _detect_flaky_results(_rehash_campaign(next_campaign), executor_ref)
    return _append_event(
        next_campaign,
        "VerificationResultRecorded",
        executor_ref,
        {"result_id": result.verification_result_id, "verdict": result.verdict},
    )


def bk_r10_submit_waiver(
    campaign: dict[str, Any] | BKR10VerificationCampaign,
    *,
    obligation_id: str,
    authority: dict[str, str],
    justification: str,
    risk_acceptance: str,
    scope: str,
    expires_at: str,
    compensating_controls: tuple[str, ...],
) -> BKR10VerificationCampaign:
    current = _campaign(campaign)
    authority_ref = _actor(authority)
    if not all((justification, risk_acceptance, scope, expires_at, compensating_controls)):
        finding = _finding(
            current,
            finding_type="EVIDENCE_GAP",
            severity="HIGH",
            description="Waiver is missing mandatory governance fields",
            affected_requirements=(),
            evidence_references=(),
            owner=authority_ref,
        )
        return _append_event(
            _rehash_campaign(
                current.model_copy(update={"findings": current.findings + (finding,)})
            ),
            "VerificationWaiverRejected",
            authority_ref,
            {"obligation_id": obligation_id},
        )
    seed = {
        "campaign": current.verification_campaign_id,
        "obligation_id": obligation_id,
        "authority": authority_ref.model_dump(),
        "expires_at": expires_at,
    }
    waiver_hash = specification_hash(seed)
    waiver = BKR10VerificationWaiver(
        waiver_id=f"bk-r10-waiver-{waiver_hash[:16]}",
        verification_campaign_id=current.verification_campaign_id,
        obligation_id=obligation_id,
        authority=authority_ref,
        justification=justification,
        risk_acceptance=risk_acceptance,
        scope=scope,
        expires_at=expires_at,
        compensating_controls=compensating_controls,
        status="APPROVED",
        waiver_hash=waiver_hash,
    )
    obligations = tuple(
        item.model_copy(update={"status": "WAIVED"})
        if item.verification_obligation_id == obligation_id
        else item
        for item in current.obligations
    )
    next_campaign = current.model_copy(
        update={"waivers": current.waivers + (waiver,), "obligations": obligations}
    )
    return _append_event(
        _rehash_campaign(next_campaign),
        "VerificationWaiverApproved",
        authority_ref,
        {"waiver_id": waiver.waiver_id},
    )


def bk_r10_perform_coverage_assessment(
    campaign: dict[str, Any] | BKR10VerificationCampaign,
    *,
    actor: dict[str, str],
) -> BKR10VerificationCampaign:
    current = _campaign(campaign)
    coverage = _coverage(current)
    next_campaign = current.model_copy(update={"coverage": coverage})
    return _append_event(
        _rehash_campaign(next_campaign),
        "CoverageAssessmentCompleted",
        _actor(actor),
        coverage.model_dump(),
    )


def bk_r10_generate_verdict(
    campaign: dict[str, Any] | BKR10VerificationCampaign,
    *,
    actor: dict[str, str],
    validation_status: str = "NOT_REQUIRED",
) -> BKR10VerificationCampaign:
    current = _campaign(campaign)
    coverage = current.coverage or _coverage(current)
    diagnostics = _verdict_diagnostics(current, coverage)
    blocking_findings = tuple(
        finding.finding_id
        for finding in current.findings
        if finding.status == "OPEN" and finding.severity in {"HIGH", "CRITICAL"}
    )
    verification_status = "PASSED" if not diagnostics else "FAILED"
    final_verdict = "PASS" if verification_status == "PASSED" else "FAIL"
    payload = {
        "campaign": current.verification_campaign_id,
        "verification_status": verification_status,
        "validation_status": validation_status,
        "blocking_findings": blocking_findings,
        "diagnostics": [item.model_dump(mode="json") for item in diagnostics],
    }
    verdict_hash = specification_hash(payload)
    verdict = BKR10CampaignVerdict(
        verdict_id=f"bk-r10-verdict-{verdict_hash[:16]}",
        verification_campaign_id=current.verification_campaign_id,
        verification_status=verification_status,
        validation_status=validation_status,
        policy_status="PASSED" if verification_status == "PASSED" else "FAILED",
        security_status="PASSED"
        if not any(f.finding_type == "POLICY_VIOLATION" for f in current.findings)
        else "FAILED",
        coverage_status="PASSED" if coverage.incomplete_mandatory_obligations == 0 else "FAILED",
        final_verdict=final_verdict,
        blocking_findings=blocking_findings,
        diagnostics=diagnostics,
        verdict_hash=verdict_hash,
    )
    next_status = "COMPLETED" if final_verdict == "PASS" else "FAILED"
    next_campaign = current.model_copy(
        update={
            "coverage": coverage,
            "verdict": verdict,
            "status": next_status,
            "completed_at": DETERMINISTIC_VERIFICATION_TIMESTAMP,
        }
    )
    return _append_event(
        _rehash_campaign(next_campaign),
        "CampaignVerdictGenerated",
        _actor(actor),
        verdict.model_dump(),
    )


def bk_r10_generate_satisfaction_recommendations(
    campaign: dict[str, Any] | BKR10VerificationCampaign,
    *,
    actor: dict[str, str],
    validation_status: str = "NOT_REQUIRED",
) -> BKR10VerificationCampaign:
    current = _campaign(campaign)
    actor_ref = _actor(actor)
    by_requirement: dict[str, list[BKR10VerificationObligation]] = {}
    for obligation in current.obligations:
        if obligation.requirement_id:
            by_requirement.setdefault(obligation.requirement_id, []).append(obligation)
    recommendations: list[BKR10SatisfactionRecommendation] = []
    for requirement_id, obligations in sorted(by_requirement.items()):
        statuses = {item.status for item in obligations}
        blocking = tuple(
            finding.finding_id
            for finding in current.findings
            if requirement_id in finding.affected_requirements and finding.status == "OPEN"
        )
        waivers = tuple(
            waiver.waiver_id
            for waiver in current.waivers
            if waiver.obligation_id in {item.verification_obligation_id for item in obligations}
        )
        evidence = tuple(
            ref
            for result in current.results
            for obligation_result in result.obligation_results
            if obligation_result.verification_obligation_id
            in {item.verification_obligation_id for item in obligations}
            for ref in obligation_result.evidence_references
        )
        verification_status = _requirement_verification_status(statuses)
        recommendation = (
            "SATISFY"
            if verification_status == "PASSED" and not blocking
            else "SATISFY_WITH_CONDITIONS"
            if verification_status == "WAIVED" and not blocking
            else "DO_NOT_SATISFY"
        )
        seed = {
            "campaign": current.verification_campaign_id,
            "requirement_id": requirement_id,
            "verification_status": verification_status,
            "recommendation": recommendation,
        }
        recommendation_hash = specification_hash(seed)
        recommendations.append(
            BKR10SatisfactionRecommendation(
                satisfaction_recommendation_id=f"bk-r10-sr-{recommendation_hash[:16]}",
                verification_campaign_id=current.verification_campaign_id,
                requirement_id=requirement_id,
                verification_status=verification_status,
                validation_status=validation_status,
                blocking_findings=blocking,
                waiver_references=waivers,
                evidence_references=evidence,
                recommendation=recommendation,
                generated_by=actor_ref,
                approved_by=None,
                created_at=DETERMINISTIC_VERIFICATION_TIMESTAMP,
                recommendation_hash=recommendation_hash,
            )
        )
    next_campaign = current.model_copy(
        update={"satisfaction_recommendations": tuple(recommendations)}
    )
    return _append_event(
        _rehash_campaign(next_campaign),
        "SatisfactionRecommendationGenerated",
        actor_ref,
        {"count": len(recommendations)},
    )


def bk_r10_write_campaign(campaign: dict[str, Any] | BKR10VerificationCampaign, path: Path) -> str:
    current = _campaign(campaign)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(current.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return current.content_hash


def bk_r10_read_campaign(path: Path) -> BKR10VerificationCampaign | None:
    if not path.exists():
        return None
    return BKR10VerificationCampaign.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _campaign(campaign: dict[str, Any] | BKR10VerificationCampaign) -> BKR10VerificationCampaign:
    return (
        campaign
        if isinstance(campaign, BKR10VerificationCampaign)
        else BKR10VerificationCampaign.model_validate(campaign)
    )


def _actor(actor: dict[str, str]) -> BKR10ActorReference:
    return BKR10ActorReference.model_validate(actor)


def _conformance_criteria(repo_root: Path) -> list[BKR10ConformanceCriterion]:
    checks: tuple[tuple[str, str, tuple[str, ...]], ...] = (
        (
            "BK-R10-AC-001",
            "An R9-style verification handoff can create a governed verification campaign.",
            (
                "apps/api/src/ai_enterprise/application/bk_r10_verification_runtime.py",
                "apps/api/tests/test_bk_r10_verification_runtime.py",
            ),
        ),
        (
            "BK-R10-AC-002",
            "Campaigns bind to exact constitutional and repository baselines.",
            (
                "schemas/verification/handoff.schema.json",
                "apps/api/tests/test_bk_r10_verification_contracts.py",
            ),
        ),
        (
            "BK-R10-AC-003",
            "Mandatory obligations have explicit final governed states.",
            (
                "schemas/verification/obligation.schema.json",
                "registry/verification-policies/bk-r10-default.json",
            ),
        ),
        (
            "BK-R10-AC-004",
            "No-evidence-no-pass is enforced.",
            (
                "apps/api/src/ai_enterprise/application/bk_r10_verification_runtime.py",
                "apps/api/tests/test_bk_r10_verification_runtime.py",
            ),
        ),
        (
            "BK-R10-AC-005",
            "Skipped, blocked, waived, failed, and inconclusive results remain distinct.",
            (
                "schemas/verification/result.schema.json",
                "apps/api/tests/test_bk_r10_verification_runtime.py",
            ),
        ),
        (
            "BK-R10-AC-006",
            "Failed results remain visible after retries; flaky retries block positive verdicts.",
            (
                "apps/api/src/ai_enterprise/application/bk_r10_verification_runtime.py",
                "apps/api/tests/test_bk_r10_verification_runtime.py",
            ),
        ),
        (
            "BK-R10-AC-007",
            "Verification environments are qualified before execution.",
            (
                "schemas/verification/environment.schema.json",
                "apps/api/tests/test_bk_r10_verification_runtime.py",
            ),
        ),
        (
            "BK-R10-AC-008",
            "Coverage assessment identifies exact mandatory obligation gaps.",
            (
                "apps/api/src/ai_enterprise/application/bk_r10_verification_runtime.py",
                "apps/api/tests/test_bk_r10_verification_runtime.py",
            ),
        ),
        (
            "BK-R10-AC-009",
            "Waivers are governed, scoped, expiring, and auditable.",
            (
                "schemas/verification/waiver.schema.json",
                "apps/api/tests/test_bk_r10_verification_runtime.py",
            ),
        ),
        (
            "BK-R10-AC-010",
            "Campaign verdicts separate verification and validation status.",
            (
                "apps/api/src/ai_enterprise/application/bk_r10_verification_runtime.py",
                "apps/api/tests/test_bk_r10_verification_runtime.py",
            ),
        ),
        (
            "BK-R10-AC-011",
            "R5 receives satisfaction recommendations instead of direct requirement mutation.",
            (
                "apps/api/src/ai_enterprise/application/bk_r10_verification_runtime.py",
                "apps/api/tests/test_bk_r10_verification_runtime.py",
            ),
        ),
        (
            "BK-R10-AC-012",
            "R11-style evidence and audit references are preserved.",
            (
                "apps/api/src/ai_enterprise/application/bk_r10_persistence_service.py",
                "apps/api/tests/test_bk_r10_verification_persistence.py",
            ),
        ),
        (
            "BK-R10-AC-013",
            "API commands and queries are exposed.",
            (
                "apps/api/src/ai_enterprise/api/routes/bk_r10_verification.py",
                "apps/api/tests/test_bk_r10_verification_runtime.py",
            ),
        ),
        (
            "BK-R10-AC-014",
            "Relational persistence and migration are append-only and drift-checked.",
            (
                "apps/api/src/ai_enterprise/infrastructure/bk_r10/models.py",
                "migrations/versions/f8a6c2d4e9b1_add_bk_r10_verification_records.py",
            ),
        ),
        (
            "BK-R10-AC-015",
            "External verification backends have fail-closed readiness contracts.",
            (
                "schemas/verification/external-backend.schema.json",
                "registry/verification-backends/bk-r10-default.json",
            ),
        ),
        (
            "BK-R10-AC-016",
            "Mock and HTTP adapters support CI-safe and production integration paths.",
            (
                "apps/api/src/ai_enterprise/application/bk_r10_verification_runtime.py",
                "apps/api/tests/test_bk_r10_verification_runtime.py",
            ),
        ),
    )
    return [
        _conformance_criterion(repo_root, criterion_id, description, paths)
        for criterion_id, description, paths in checks
    ]


def _conformance_criterion(
    repo_root: Path,
    criterion_id: str,
    description: str,
    evidence_paths: tuple[str, ...],
) -> BKR10ConformanceCriterion:
    missing = tuple(path for path in evidence_paths if not (repo_root / path).exists())
    diagnostics = tuple(
        _diag(
            "error",
            "conformance",
            "BK_R10_CONFORMANCE_EVIDENCE_MISSING",
            f"Required evidence path is missing: {path}",
            f"$.criteria.{criterion_id}.evidence_paths",
        )
        for path in missing
    )
    return BKR10ConformanceCriterion(
        criterion_id=criterion_id,
        description=description,
        status="FAIL" if missing else "PASS",
        evidence_paths=evidence_paths,
        diagnostics=diagnostics,
    )


def _obligation(raw: dict[str, Any]) -> BKR10VerificationObligation:
    method = raw.get("method", "TEST")
    if method not in VERIFICATION_METHODS:
        method = "TEST"
    seed = {
        "requirement_id": raw.get("requirement_id"),
        "acceptance_criterion_id": raw.get("acceptance_criterion_id"),
        "method": method,
        "obligation_type": raw.get("obligation_type", "REQUIREMENT"),
    }
    obligation_id = raw.get("verification_obligation_id") or (
        f"bk-r10-obl-{specification_hash(seed)[:16]}"
    )
    return BKR10VerificationObligation(
        verification_obligation_id=obligation_id,
        requirement_id=raw.get("requirement_id"),
        acceptance_criterion_id=raw.get("acceptance_criterion_id"),
        architecture_element_id=raw.get("architecture_element_id"),
        policy_reference=raw.get("policy_reference"),
        obligation_type=raw.get("obligation_type", "REQUIREMENT"),
        method=method,
        criticality=raw.get("criticality", "MEDIUM"),
        mandatory=raw.get("mandatory", True),
        responsible_authority=_actor(
            raw.get(
                "responsible_authority",
                {"actor_type": "human", "actor_id": "verification-authority", "role": "verifier"},
            )
        ),
        required_environment_profile=raw.get("required_environment_profile"),
        required_evidence_types=tuple(raw.get("required_evidence_types", ("test-report",))),
        pass_conditions=tuple(raw.get("pass_conditions", ("all assertions pass",))),
        fail_conditions=tuple(raw.get("fail_conditions", ("any mandatory assertion fails",))),
        status=raw.get("status", "PLANNED"),
    )


def _procedure(raw: dict[str, Any]) -> BKR10VerificationProcedure:
    seed = {
        "title": raw.get("title", "Verification Procedure"),
        "obligations": raw.get("verification_obligation_ids", ()),
        "steps": raw.get("ordered_steps", ()),
    }
    content_hash = specification_hash(seed)
    return BKR10VerificationProcedure(
        verification_procedure_id=raw.get("verification_procedure_id")
        or f"bk-r10-proc-{content_hash[:16]}",
        verification_obligation_ids=tuple(raw.get("verification_obligation_ids", ())),
        title=raw.get("title", "Verification Procedure"),
        procedure_type=raw.get("procedure_type", "AUTOMATED"),
        ordered_steps=tuple(raw.get("ordered_steps", ())),
        expected_results=tuple(raw.get("expected_results", ())),
        required_tools=tuple(raw.get("required_tools", ())),
        required_environment_profile=raw.get("required_environment_profile", "default"),
        version=raw.get("version", "1.0.0"),
        content_hash=content_hash,
        approval_reference=raw.get("approval_reference"),
    )


def _environment(raw: dict[str, Any], expected_revision: str) -> BKR10VerificationEnvironment:
    required = (
        raw.get("repository_revision") == expected_revision
        and bool(raw.get("runtime_versions"))
        and bool(raw.get("configuration_hashes"))
        and bool(raw.get("dependency_lock_hashes"))
        and bool(raw.get("evidence_reference"))
    )
    seed = {
        "profile": raw.get("environment_profile", "default"),
        "repository_revision": raw.get("repository_revision"),
        "configuration_hashes": raw.get("configuration_hashes", ()),
        "dependency_lock_hashes": raw.get("dependency_lock_hashes", ()),
    }
    environment_hash = specification_hash(seed)
    return BKR10VerificationEnvironment(
        verification_environment_id=raw.get("verification_environment_id")
        or f"bk-r10-env-{environment_hash[:16]}",
        environment_type=raw.get("environment_type", "CI"),
        environment_profile=raw.get("environment_profile", "default"),
        runtime_versions=dict(raw.get("runtime_versions", {})),
        infrastructure_reference=raw.get("infrastructure_reference", "local"),
        repository_revision=raw.get("repository_revision", ""),
        configuration_hashes=tuple(raw.get("configuration_hashes", ())),
        dependency_lock_hashes=tuple(raw.get("dependency_lock_hashes", ())),
        network_policy=raw.get("network_policy", "isolated"),
        secret_scope=tuple(raw.get("secret_scope", ())),
        integrity_status="VERIFIED" if required else "INVALID",
        verified_at=DETERMINISTIC_VERIFICATION_TIMESTAMP if required else None,
        evidence_reference=raw.get("evidence_reference"),
        environment_hash=environment_hash,
    )


def _entry_diagnostics(campaign: BKR10VerificationCampaign) -> tuple[BKR10Diagnostic, ...]:
    diagnostics: list[BKR10Diagnostic] = []
    if not campaign.obligations:
        diagnostics.append(
            _diag("error", "planning", "BK_R10_OBLIGATIONS_REQUIRED", "No obligations are defined")
        )
    if not any(env.integrity_status == "VERIFIED" for env in campaign.environments):
        diagnostics.append(
            _diag("error", "environment", "BK_R10_ENVIRONMENT_NOT_READY", "No verified environment")
        )
    if campaign.verification_handoff.repository_revision in {"", "unknown"}:
        diagnostics.append(
            _diag(
                "error",
                "handoff",
                "BK_R10_REPOSITORY_REVISION_REQUIRED",
                "Repository revision is required",
            )
        )
    return tuple(diagnostics)


def _backend_diagnostics(
    config: BKR10ExternalBackendConfig,
    *,
    production: bool,
) -> tuple[BKR10Diagnostic, ...]:
    diagnostics: list[BKR10Diagnostic] = []
    if config.backend_type not in EXTERNAL_BACKENDS:
        diagnostics.append(
            _diag(
                "error",
                "readiness",
                "BK_R10_BACKEND_TYPE_INVALID",
                "External backend type is not supported",
                "$.backend_type",
            )
        )
    if not config.enabled:
        diagnostics.append(
            _diag(
                "error" if production else "warning",
                "readiness",
                "BK_R10_BACKEND_DISABLED",
                "External backend is disabled",
                "$.enabled",
            )
        )
    if not config.provider:
        diagnostics.append(
            _diag(
                "error",
                "readiness",
                "BK_R10_PROVIDER_REQUIRED",
                "External backend provider is required",
                "$.provider",
            )
        )
    if config.provider != "mock" and not config.endpoint_reference:
        diagnostics.append(
            _diag(
                "error",
                "readiness",
                "BK_R10_ENDPOINT_REQUIRED",
                "External backend endpoint reference is required",
                "$.endpoint_reference",
            )
        )
    if production and config.mock_mode:
        diagnostics.append(
            _diag(
                "error",
                "readiness",
                "BK_R10_MOCK_BACKEND_FORBIDDEN_IN_PRODUCTION",
                "Mock verification backends are forbidden in production",
                "$.mock_mode",
            )
        )
    if production and config.provider != "mock" and not config.credential_reference:
        diagnostics.append(
            _diag(
                "error",
                "readiness",
                "BK_R10_CREDENTIAL_REFERENCE_REQUIRED",
                "Production external backend requires a credential reference",
                "$.credential_reference",
            )
        )
    if config.backend_type == "evidence_store" and not config.evidence_reference:
        diagnostics.append(
            _diag(
                "error" if production else "warning",
                "readiness",
                "BK_R10_EVIDENCE_REFERENCE_REQUIRED",
                "Evidence store backend should provide an evidence reference",
                "$.evidence_reference",
            )
        )
    if config.backend_type == "policy_engine" and not config.policy_reference:
        diagnostics.append(
            _diag(
                "error" if production else "warning",
                "readiness",
                "BK_R10_POLICY_REFERENCE_REQUIRED",
                "Policy engine backend should provide a policy reference",
                "$.policy_reference",
            )
        )
    return tuple(diagnostics)


def _external_result_from_payload(
    request: BKR10ExternalExecutionRequest,
    config: BKR10ExternalBackendConfig,
    payload: dict[str, Any],
) -> BKR10ExternalExecutionResult:
    if "status" not in payload and "obligation_results" not in payload:
        raise ValueError("provider payload must include status or obligation_results")
    diagnostics = tuple(
        BKR10Diagnostic.model_validate(item) for item in payload.get("diagnostics", ())
    )
    obligation_payloads = payload.get("obligation_results")
    if obligation_payloads is None:
        status = str(payload.get("status", "INCONCLUSIVE"))
        obligation_payloads = [
            {
                "verification_obligation_id": obligation_id,
                "status": status,
                "evidence_references": tuple(payload.get("evidence_references", ())),
                "notes": payload.get("notes"),
            }
            for obligation_id in request.obligation_ids
        ]
    obligation_results = tuple(
        BKR10ObligationResult.model_validate(item) for item in obligation_payloads
    )
    raw_evidence = tuple(payload.get("raw_evidence_references", ()))
    normalized_evidence = tuple(payload.get("normalized_evidence_references", raw_evidence))
    if not raw_evidence and not any(item.evidence_references for item in obligation_results):
        raise ValueError("provider payload must include evidence references")
    status = str(
        payload.get(
            "status",
            _aggregate_obligation_status(
                tuple(item.model_dump(mode="json") for item in obligation_results)
            ),
        )
    )
    result_seed = {
        "provider": config.provider,
        "backend_type": config.backend_type,
        "request": request.model_dump(mode="json"),
        "payload": payload,
    }
    result_hash = str(payload.get("result_hash") or specification_hash(result_seed))
    return BKR10ExternalExecutionResult(
        provider=config.provider,
        backend_type=config.backend_type,
        status=status,
        obligation_results=obligation_results,
        raw_evidence_references=raw_evidence,
        normalized_evidence_references=normalized_evidence,
        metrics={key: int(value) for key, value in dict(payload.get("metrics", {})).items()},
        diagnostics=diagnostics,
        result_hash=result_hash,
    )


def _result_diagnostics(
    campaign: BKR10VerificationCampaign,
    procedure_id: str,
    environment_id: str,
    obligation_results: tuple[dict[str, Any], ...],
    raw_evidence_references: tuple[str, ...],
) -> tuple[BKR10Diagnostic, ...]:
    diagnostics: list[BKR10Diagnostic] = []
    if procedure_id and not any(
        item.verification_procedure_id == procedure_id for item in campaign.procedures
    ):
        diagnostics.append(
            _diag("error", "procedure", "BK_R10_PROCEDURE_NOT_FOUND", "Procedure not found")
        )
    if not any(
        item.verification_environment_id == environment_id and item.integrity_status == "VERIFIED"
        for item in campaign.environments
    ):
        diagnostics.append(
            _diag(
                "error",
                "environment",
                "BK_R10_ENVIRONMENT_NOT_READY",
                "Environment is not verified",
            )
        )
    obligations = {item.verification_obligation_id: item for item in campaign.obligations}
    for index, result in enumerate(obligation_results):
        obligation = obligations.get(str(result.get("verification_obligation_id")))
        status = str(result.get("status", ""))
        evidence = tuple(result.get("evidence_references", ()))
        if obligation is None:
            diagnostics.append(
                _diag(
                    "error",
                    "obligation",
                    "BK_R10_OBLIGATION_NOT_FOUND",
                    "Obligation result references an unknown obligation",
                    f"$.obligation_results[{index}]",
                )
            )
            continue
        if (
            status == "PASSED"
            and obligation.mandatory
            and not evidence
            and not raw_evidence_references
        ):
            diagnostics.append(
                _diag(
                    "error",
                    "evidence",
                    "BK_R10_EVIDENCE_REQUIRED",
                    "Mandatory passed obligation requires evidence",
                    f"$.obligation_results[{index}].evidence_references",
                )
            )
        if status in {"SKIPPED", ""}:
            diagnostics.append(
                _diag(
                    "error",
                    "classification",
                    "BK_R10_NO_SILENT_OMISSION",
                    "Skipped or empty outcomes must be BLOCKED, WAIVED, FAILED, or INCONCLUSIVE",
                    f"$.obligation_results[{index}].status",
                )
            )
    return tuple(diagnostics)


def _aggregate_obligation_status(obligation_results: tuple[dict[str, Any], ...]) -> str:
    statuses = {str(item.get("status")) for item in obligation_results}
    if "FAILED" in statuses:
        return "FAILED"
    if "BLOCKED" in statuses:
        return "BLOCKED"
    if "INCONCLUSIVE" in statuses:
        return "INCONCLUSIVE"
    if statuses and statuses <= {"PASSED", "WAIVED"}:
        return "PASSED"
    return "ERROR"


def _apply_obligation_results(
    obligations: tuple[BKR10VerificationObligation, ...],
    results: tuple[BKR10ObligationResult, ...],
) -> tuple[BKR10VerificationObligation, ...]:
    result_by_id = {item.verification_obligation_id: item for item in results}
    updated: list[BKR10VerificationObligation] = []
    for obligation in obligations:
        result = result_by_id.get(obligation.verification_obligation_id)
        if result is None:
            updated.append(obligation)
        elif result.status in FINAL_OBLIGATION_STATES:
            updated.append(obligation.model_copy(update={"status": result.status}))
        else:
            updated.append(obligation.model_copy(update={"status": "INCONCLUSIVE"}))
    return tuple(updated)


def _findings_from_result(
    campaign: BKR10VerificationCampaign,
    result: BKR10VerificationResult,
    diagnostics: tuple[BKR10Diagnostic, ...],
    owner: BKR10ActorReference,
) -> tuple[BKR10VerificationFinding, ...]:
    findings: list[BKR10VerificationFinding] = []
    obligations = {item.verification_obligation_id: item for item in campaign.obligations}
    for diagnostic in diagnostics:
        findings.append(
            _finding(
                campaign,
                finding_type="EVIDENCE_GAP"
                if diagnostic.category == "evidence"
                else "NONCONFORMANCE",
                severity="HIGH",
                description=diagnostic.message,
                affected_requirements=(),
                affected_implementation_references=(campaign.implementation_result_id,),
                evidence_references=result.raw_evidence_references,
                owner=owner,
            )
        )
    for obligation_result in result.obligation_results:
        if obligation_result.status in {"FAILED", "BLOCKED", "INCONCLUSIVE"}:
            obligation = obligations.get(obligation_result.verification_obligation_id)
            findings.append(
                _finding(
                    campaign,
                    finding_type="FAILURE"
                    if obligation_result.status == "FAILED"
                    else "COVERAGE_GAP",
                    severity="CRITICAL"
                    if obligation and obligation.criticality == "CRITICAL"
                    else "HIGH",
                    description=obligation_result.notes or f"Obligation {obligation_result.status}",
                    affected_requirements=(obligation.requirement_id,)
                    if obligation and obligation.requirement_id
                    else (),
                    affected_implementation_references=(campaign.implementation_result_id,),
                    evidence_references=obligation_result.evidence_references,
                    owner=owner,
                )
            )
    return tuple(findings)


def _detect_flaky_results(
    campaign: BKR10VerificationCampaign,
    owner: BKR10ActorReference,
) -> BKR10VerificationCampaign:
    by_procedure: dict[str, set[str]] = {}
    for execution in campaign.executions:
        if execution.status in {"PASSED", "FAILED"}:
            by_procedure.setdefault(execution.procedure_id, set()).add(execution.status)
    flaky_findings = tuple(
        _finding(
            campaign,
            finding_type="FLAKY_RESULT",
            severity="HIGH",
            description=f"Procedure {procedure_id} has both passing and failing attempts",
            affected_requirements=(),
            affected_implementation_references=(campaign.implementation_result_id,),
            evidence_references=(),
            owner=owner,
        )
        for procedure_id, statuses in sorted(by_procedure.items())
        if {"PASSED", "FAILED"} <= statuses
    )
    if not flaky_findings:
        return campaign
    return _append_event(
        _rehash_campaign(
            campaign.model_copy(update={"findings": campaign.findings + flaky_findings})
        ),
        "FlakyResultDetected",
        owner,
        {"count": len(flaky_findings)},
    )


def _coverage(campaign: BKR10VerificationCampaign) -> BKR10CoverageAssessment:
    mandatory = tuple(item for item in campaign.obligations if item.mandatory)
    passed = tuple(item for item in mandatory if item.status == "PASSED")
    failed = tuple(item for item in mandatory if item.status == "FAILED")
    blocked = tuple(item for item in mandatory if item.status == "BLOCKED")
    waived = tuple(item for item in mandatory if item.status == "WAIVED")
    incomplete = tuple(item for item in mandatory if item.status not in FINAL_OBLIGATION_STATES)
    gaps = tuple(
        {
            "obligation_id": item.verification_obligation_id,
            "requirement_id": item.requirement_id,
            "status": item.status,
            "missing": ["final_state" if item in incomplete else "passing_result"],
        }
        for item in failed + blocked + incomplete
    )
    seed = {"campaign": campaign.verification_campaign_id, "gaps": gaps}
    coverage_hash = specification_hash(seed)
    return BKR10CoverageAssessment(
        coverage_assessment_id=f"bk-r10-coverage-{coverage_hash[:16]}",
        verification_campaign_id=campaign.verification_campaign_id,
        total_mandatory_obligations=len(mandatory),
        passed_mandatory_obligations=len(passed),
        failed_mandatory_obligations=len(failed),
        blocked_mandatory_obligations=len(blocked),
        waived_mandatory_obligations=len(waived),
        incomplete_mandatory_obligations=len(incomplete),
        critical_gaps=gaps,
        coverage_hash=coverage_hash,
    )


def _verdict_diagnostics(
    campaign: BKR10VerificationCampaign,
    coverage: BKR10CoverageAssessment,
) -> tuple[BKR10Diagnostic, ...]:
    diagnostics: list[BKR10Diagnostic] = []
    if coverage.failed_mandatory_obligations:
        diagnostics.append(
            _diag(
                "error",
                "verification",
                "BK_R10_MANDATORY_OBLIGATION_FAILED",
                "Mandatory obligations failed",
            )
        )
    if coverage.blocked_mandatory_obligations:
        diagnostics.append(
            _diag(
                "error",
                "verification",
                "BK_R10_MANDATORY_OBLIGATION_BLOCKED",
                "Mandatory obligations are blocked",
            )
        )
    if coverage.incomplete_mandatory_obligations:
        diagnostics.append(
            _diag(
                "error",
                "coverage",
                "BK_R10_COVERAGE_INSUFFICIENT",
                "Mandatory obligations are incomplete",
            )
        )
    if any(
        item.finding_type == "FLAKY_RESULT" and item.status == "OPEN" for item in campaign.findings
    ):
        diagnostics.append(
            _diag(
                "error",
                "reliability",
                "BK_R10_FLAKY_RESULT_DETECTED",
                "Flaky results block positive verdict",
            )
        )
    return tuple(diagnostics)


def _requirement_verification_status(statuses: set[str]) -> str:
    if not statuses:
        return "INCOMPLETE"
    if statuses <= {"PASSED"}:
        return "PASSED"
    if statuses <= {"PASSED", "WAIVED"}:
        return "WAIVED"
    if "FAILED" in statuses:
        return "FAILED"
    return "INCOMPLETE"


def _finding(
    campaign: BKR10VerificationCampaign,
    *,
    finding_type: str,
    severity: str,
    description: str,
    affected_requirements: tuple[str | None, ...],
    affected_implementation_references: tuple[str, ...] = (),
    evidence_references: tuple[str, ...],
    owner: BKR10ActorReference,
) -> BKR10VerificationFinding:
    affected = tuple(str(item) for item in affected_requirements if item)
    seed = {
        "campaign": campaign.verification_campaign_id,
        "finding_type": finding_type,
        "description": description,
        "affected": affected,
        "sequence": len(campaign.findings),
    }
    finding_hash = specification_hash(seed)
    return BKR10VerificationFinding(
        finding_id=f"bk-r10-finding-{finding_hash[:16]}",
        verification_campaign_id=campaign.verification_campaign_id,
        finding_type=finding_type,
        severity=severity,
        description=description,
        affected_requirements=affected,
        affected_implementation_references=affected_implementation_references,
        owner=owner,
        status="OPEN",
        evidence_references=evidence_references,
        finding_hash=finding_hash,
    )


def _append_event(
    campaign: BKR10VerificationCampaign,
    event_type: str,
    actor: BKR10ActorReference,
    payload: dict[str, Any],
) -> BKR10VerificationCampaign:
    seed = {
        "event_type": event_type,
        "campaign": campaign.verification_campaign_id,
        "payload": payload,
        "sequence": len(campaign.events) + 1,
    }
    event_hash = specification_hash(seed)
    event = BKR10DomainEvent(
        event_id=f"bk-r10-event-{event_hash[:16]}",
        event_type=event_type,
        event_version=1,
        occurred_at=DETERMINISTIC_VERIFICATION_TIMESTAMP,
        organization_id=campaign.organization_id,
        project_id=campaign.project_id,
        campaign_id=campaign.verification_campaign_id,
        actor=actor,
        payload=payload,
        correlation_id=f"bk-r10-corr-{event_hash[:12]}",
        event_hash=event_hash,
    )
    return _rehash_campaign(campaign.model_copy(update={"events": campaign.events + (event,)}))


def _rehash_campaign(campaign: BKR10VerificationCampaign) -> BKR10VerificationCampaign:
    return campaign.model_copy(
        update={
            "content_hash": specification_hash(
                campaign.model_dump(mode="json", exclude={"content_hash"})
            )
        }
    )


def _diag(
    severity: str,
    category: str,
    code: str,
    message: str,
    path: str = "$",
) -> BKR10Diagnostic:
    return BKR10Diagnostic(
        severity=severity,
        category=category,
        code=code,
        message=message,
        path=path,
    )
