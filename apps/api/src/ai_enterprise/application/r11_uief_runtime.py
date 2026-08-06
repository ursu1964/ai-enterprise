from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from ai_enterprise.domain.specification.kernel import specification_hash


class UiefRuntimeError(ValueError):
    pass


class UiefCompatibilityFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    integration_ref: str
    compatible: bool
    findings: tuple[str, ...]
    required_refs: tuple[str, ...]


class UiefCompatibilityReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    compatible: bool
    integration_count: int
    findings: tuple[UiefCompatibilityFinding, ...]
    report_hash: str


class UiefGeneratedArtifactPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    integration_ref: str
    artifacts: tuple[str, ...]
    synchronized_with_manifest: bool


class UiefGenerationPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    integration_count: int
    artifact_plans: tuple[UiefGeneratedArtifactPlan, ...]
    plan_hash: str


class UiefIntegrationTestPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    integration_ref: str
    tests: tuple[str, ...]
    certification_ready: bool


class UiefTestPlanReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    integration_count: int
    test_plans: tuple[UiefIntegrationTestPlan, ...]
    certification_ready: bool
    report_hash: str


class UiefReconciliationDifference(BaseModel):
    model_config = ConfigDict(frozen=True)

    integration_ref: str
    category: str
    detail: str


class UiefReconciliationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    difference_count: int
    differences: tuple[UiefReconciliationDifference, ...]
    report_hash: str


class UiefObservabilitySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    integration_count: int
    healthy_count: int
    degraded_count: int
    unavailable_count: int
    disabled_count: int
    unknown_count: int
    metrics: dict[str, float]
    snapshot_hash: str


class UiefTopologyNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    node_id: str
    node_type: str
    label: str
    metadata: dict[str, str]


class UiefTopologyEdge(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    target: str
    relationship: str
    integration_ref: str


class UiefTopologyMap(BaseModel):
    model_config = ConfigDict(frozen=True)

    node_count: int
    edge_count: int
    nodes: tuple[UiefTopologyNode, ...]
    edges: tuple[UiefTopologyEdge, ...]
    topology_hash: str


class UiefIntegrationDocumentation(BaseModel):
    model_config = ConfigDict(frozen=True)

    integration_ref: str
    title: str
    sections: dict[str, str]
    source_record_hashes: tuple[str, ...]
    documentation_hash: str


class UiefDocumentationBundle(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_count: int
    documents: tuple[UiefIntegrationDocumentation, ...]
    bundle_hash: str


class UiefSandboxEnvironmentPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    integration_ref: str
    virtualized_behaviors: tuple[str, ...]
    sandbox_assets: tuple[str, ...]
    limited_operations: tuple[str, ...]
    controlled_rate_limits: dict[str, float]
    production_separated: bool


class UiefSandboxPlanReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    integration_count: int
    sandbox_plans: tuple[UiefSandboxEnvironmentPlan, ...]
    ready_for_isolated_testing: bool
    report_hash: str


class UiefSecurityReadinessFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    integration_ref: str
    severity: str
    category: str
    detail: str


class UiefSecurityReadinessReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    integration_count: int
    finding_count: int
    activation_allowed: bool
    findings: tuple[UiefSecurityReadinessFinding, ...]
    report_hash: str


class UiefImpactAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    integration_ref: str
    changed_ref: str
    affected_connectors: tuple[str, ...]
    dependent_services: tuple[str, ...]
    event_consumers: tuple[str, ...]
    api_clients: tuple[str, ...]
    mappings: tuple[str, ...]
    tests: tuple[str, ...]
    documentation_refs: tuple[str, ...]
    partner_agreements: tuple[str, ...]
    runtime_deployments: tuple[str, ...]
    risk_level: str


class UiefImpactAnalysisReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    changed_ref: str | None
    impact_count: int
    impacts: tuple[UiefImpactAssessment, ...]
    report_hash: str


class UiefMigrationStagePlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    stage: str
    objective: str
    required_evidence: tuple[str, ...]


class UiefMigrationPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    integration_ref: str
    strategy: str
    source_ref: str
    target_ref: str
    stages: tuple[UiefMigrationStagePlan, ...]
    rollback_required: bool
    parallel_run_required: bool


class UiefMigrationPlanReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    migration_count: int
    migration_plans: tuple[UiefMigrationPlan, ...]
    report_hash: str


class UiefEcosystemReadinessFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: str
    severity: str
    subject_ref: str
    detail: str


class UiefEcosystemReadinessReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    connector_registry_ready: bool
    gateway_ready: bool
    marketplace_ready: bool
    partner_ready: bool
    data_governance_ready: bool
    production_ready: bool
    finding_count: int
    findings: tuple[UiefEcosystemReadinessFinding, ...]
    report_hash: str


class UiefDeveloperSurfaceCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    capability: str
    method: str
    path: str
    kernel_managed: bool
    human_approval_required: bool


class UiefDeveloperSurfaceReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    public_api_count: int
    cli_capabilities: tuple[str, ...]
    commands: tuple[UiefDeveloperSurfaceCommand, ...]
    sdk_surfaces: tuple[str, ...]
    validation_tools: tuple[str, ...]
    certification_pipeline: tuple[str, ...]
    documentation_portals: tuple[str, ...]
    ready_for_external_developers: bool
    report_hash: str


class UiefDeploymentPreflightCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    ready: bool
    detail: str
    remediation: str


class UiefDeploymentPreflightReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    external_integration_mode: str
    endpoint_allowlist_ready: bool
    credential_refs_ready: bool
    partner_trust_ready: bool
    gateway_ready: bool
    secrets_manager_ready: bool
    production_operational: bool
    checks: tuple[UiefDeploymentPreflightCheck, ...]
    report_hash: str


@dataclass(frozen=True, slots=True)
class UiefRecordView:
    record_type: str
    record_id: str
    integration_ref: str | None
    lifecycle_state: str | None
    health_status: str | None
    record_document: dict[str, Any]
    record_hash: str


def analyze_compatibility(records: list[UiefRecordView]) -> UiefCompatibilityReport:
    by_type = _by_type(records)
    integrations = by_type.get("integration", [])
    findings = tuple(_compatibility_for_integration(item, by_type) for item in integrations)
    compatible = all(item.compatible for item in findings)
    payload = {
        "compatible": compatible,
        "integration_count": len(integrations),
        "findings": [item.model_dump(mode="json") for item in findings],
    }
    return UiefCompatibilityReport(
        compatible=compatible,
        integration_count=len(integrations),
        findings=findings,
        report_hash=specification_hash(payload),
    )


def build_generation_plan(records: list[UiefRecordView]) -> UiefGenerationPlan:
    integrations = _by_type(records).get("integration", [])
    plans = tuple(_artifact_plan(item) for item in integrations)
    payload = {
        "integration_count": len(integrations),
        "artifact_plans": [item.model_dump(mode="json") for item in plans],
    }
    return UiefGenerationPlan(
        integration_count=len(integrations),
        artifact_plans=plans,
        plan_hash=specification_hash(payload),
    )


def build_test_plan(records: list[UiefRecordView]) -> UiefTestPlanReport:
    compatibility = analyze_compatibility(records)
    integrations = _by_type(records).get("integration", [])
    plans = tuple(
        UiefIntegrationTestPlan(
            integration_ref=_integration_ref(item),
            tests=(
                "contract",
                "authentication",
                "authorization",
                "mapping",
                "transformation",
                "error_handling",
                "retry",
                "load",
                "compatibility",
                "recovery",
            ),
            certification_ready=compatibility.compatible,
        )
        for item in integrations
    )
    payload = {
        "integration_count": len(integrations),
        "test_plans": [item.model_dump(mode="json") for item in plans],
        "certification_ready": compatibility.compatible,
    }
    return UiefTestPlanReport(
        integration_count=len(integrations),
        test_plans=plans,
        certification_ready=compatibility.compatible,
        report_hash=specification_hash(payload),
    )


def reconcile_integrations(records: list[UiefRecordView]) -> UiefReconciliationReport:
    differences: list[UiefReconciliationDifference] = []
    for twin in _by_type(records).get("digital_twin", []):
        document = twin.record_document
        integration_ref = str(document.get("integration_ref", twin.integration_ref or "unknown"))
        health = str(document.get("health", "unknown"))
        if health in {"degraded", "unavailable", "unknown"}:
            differences.append(
                UiefReconciliationDifference(
                    integration_ref=integration_ref,
                    category="health",
                    detail=f"integration twin health is {health}",
                )
            )
        if document.get("contract_status") != "compatible":
            differences.append(
                UiefReconciliationDifference(
                    integration_ref=integration_ref,
                    category="contract",
                    detail="integration contract status is not compatible",
                )
            )
        if document.get("security_status") != "valid":
            differences.append(
                UiefReconciliationDifference(
                    integration_ref=integration_ref,
                    category="security",
                    detail="integration security status is not valid",
                )
            )
    payload = {"differences": [item.model_dump(mode="json") for item in differences]}
    return UiefReconciliationReport(
        difference_count=len(differences),
        differences=tuple(differences),
        report_hash=specification_hash(payload),
    )


def summarize_observability(records: list[UiefRecordView]) -> UiefObservabilitySnapshot:
    twins = _by_type(records).get("digital_twin", [])
    health_counts = {"healthy": 0, "degraded": 0, "unavailable": 0, "disabled": 0, "unknown": 0}
    metrics: dict[str, float] = {
        "request_count": 0.0,
        "success_rate": 0.0,
        "error_rate": 0.0,
        "latency": 0.0,
        "throughput": 0.0,
        "retry_count": 0.0,
        "queue_depth": 0.0,
        "rejected_payloads": 0.0,
        "contract_violations": 0.0,
        "dependency_availability": 0.0,
    }
    for twin in twins:
        health = str(twin.record_document.get("health", "unknown"))
        health_counts[health if health in health_counts else "unknown"] += 1
        for key, value in twin.record_document.get("performance_metrics", {}).items():
            if key in metrics:
                metrics[key] += float(value)
    if twins and metrics["success_rate"]:
        metrics["success_rate"] = metrics["success_rate"] / len(twins)
    if twins and metrics["error_rate"]:
        metrics["error_rate"] = metrics["error_rate"] / len(twins)
    if twins and metrics["dependency_availability"]:
        metrics["dependency_availability"] = metrics["dependency_availability"] / len(twins)
    payload = {"health_counts": health_counts, "metrics": metrics, "integration_count": len(twins)}
    return UiefObservabilitySnapshot(
        integration_count=len(twins),
        healthy_count=health_counts["healthy"],
        degraded_count=health_counts["degraded"],
        unavailable_count=health_counts["unavailable"],
        disabled_count=health_counts["disabled"],
        unknown_count=health_counts["unknown"],
        metrics=metrics,
        snapshot_hash=specification_hash(payload),
    )


def build_topology_map(records: list[UiefRecordView]) -> UiefTopologyMap:
    by_type = _by_type(records)
    nodes: dict[str, UiefTopologyNode] = {}
    edges: set[tuple[str, str, str, str]] = set()

    for integration in by_type.get("integration", []):
        document = integration.record_document
        integration_ref = _integration_ref(integration)
        _add_node(
            nodes,
            integration_ref,
            "integration",
            str(document.get("name") or integration_ref),
            {
                "domain": str(document.get("domain", "")),
                "protocol": str(document.get("protocol", "")),
                "lifecycle_state": str(document.get("lifecycle_state", "")),
            },
        )
        _connect_ref(
            nodes,
            edges,
            str(document.get("source_ref", "")),
            integration_ref,
            "external_system",
            "feeds",
            integration_ref,
        )
        _connect_ref(
            nodes,
            edges,
            integration_ref,
            str(document.get("destination_ref", "")),
            "external_system",
            "delivers_to",
            integration_ref,
        )
        for key, node_type, relationship in (
            ("contract_ref", "contract", "uses_contract"),
            ("mapping_ref", "mapping", "uses_mapping"),
            ("retry_policy_ref", "retry_policy", "uses_retry_policy"),
            ("authentication_ref", "security_policy", "authenticates_with"),
            ("authorization_ref", "security_policy", "authorizes_with"),
            ("error_strategy_ref", "error_strategy", "handles_errors_with"),
            ("owner_ref", "owner", "owned_by"),
            ("monitoring_ref", "monitor", "observed_by"),
        ):
            _connect_ref(
                nodes,
                edges,
                integration_ref,
                str(document.get(key, "")),
                node_type,
                relationship,
                integration_ref,
            )

    for twin in by_type.get("digital_twin", []):
        document = twin.record_document
        integration_ref = str(document.get("integration_ref", twin.integration_ref or ""))
        connector_ref = str(document.get("deployed_connector_ref", ""))
        endpoint_ref = str(document.get("endpoint_ref", ""))
        _connect_ref(
            nodes,
            edges,
            integration_ref,
            connector_ref,
            "connector",
            "deployed_as",
            integration_ref,
        )
        _connect_ref(
            nodes,
            edges,
            connector_ref,
            endpoint_ref,
            "endpoint",
            "exposes_endpoint",
            integration_ref,
        )
        for dependency_ref in document.get("dependency_refs", ()):
            _connect_ref(
                nodes,
                edges,
                connector_ref,
                str(dependency_ref),
                "dependency",
                "depends_on",
                integration_ref,
            )
        for flow_ref in document.get("data_flow_refs", ()):
            _connect_ref(
                nodes,
                edges,
                integration_ref,
                str(flow_ref),
                "data_flow",
                "realizes_flow",
                integration_ref,
            )

    sorted_nodes = tuple(sorted(nodes.values(), key=lambda item: item.node_id))
    sorted_edges = tuple(
        UiefTopologyEdge(
            source=source,
            target=target,
            relationship=relationship,
            integration_ref=integration_ref,
        )
        for source, target, relationship, integration_ref in sorted(edges)
    )
    payload = {
        "nodes": [item.model_dump(mode="json") for item in sorted_nodes],
        "edges": [item.model_dump(mode="json") for item in sorted_edges],
    }
    return UiefTopologyMap(
        node_count=len(sorted_nodes),
        edge_count=len(sorted_edges),
        nodes=sorted_nodes,
        edges=sorted_edges,
        topology_hash=specification_hash(payload),
    )


def generate_integration_documentation(
    records: list[UiefRecordView],
) -> UiefDocumentationBundle:
    by_type = _by_type(records)
    integrations = by_type.get("integration", [])
    test_report = build_test_plan(records)
    test_ready = {
        item.integration_ref: item.certification_ready for item in test_report.test_plans
    }
    documents = tuple(
        _documentation_for_integration(integration, records, test_ready)
        for integration in sorted(integrations, key=_integration_ref)
    )
    payload = {"documents": [item.model_dump(mode="json") for item in documents]}
    return UiefDocumentationBundle(
        document_count=len(documents),
        documents=documents,
        bundle_hash=specification_hash(payload),
    )


def build_sandbox_plan(records: list[UiefRecordView]) -> UiefSandboxPlanReport:
    by_type = _by_type(records)
    plans = tuple(
        _sandbox_plan_for_integration(integration, records)
        for integration in sorted(by_type.get("integration", []), key=_integration_ref)
    )
    payload = {
        "integration_count": len(plans),
        "sandbox_plans": [item.model_dump(mode="json") for item in plans],
    }
    return UiefSandboxPlanReport(
        integration_count=len(plans),
        sandbox_plans=plans,
        ready_for_isolated_testing=all(item.production_separated for item in plans),
        report_hash=specification_hash(payload),
    )


def validate_security_readiness(records: list[UiefRecordView]) -> UiefSecurityReadinessReport:
    by_type = _by_type(records)
    findings: list[UiefSecurityReadinessFinding] = []
    for integration in sorted(by_type.get("integration", []), key=_integration_ref):
        findings.extend(_security_findings_for_integration(integration, records))
    ordered_findings = tuple(
        sorted(
            findings,
            key=lambda item: (
                item.integration_ref,
                item.severity,
                item.category,
                item.detail,
            ),
        )
    )
    payload = {
        "integration_count": len(by_type.get("integration", [])),
        "findings": [item.model_dump(mode="json") for item in ordered_findings],
    }
    return UiefSecurityReadinessReport(
        integration_count=len(by_type.get("integration", [])),
        finding_count=len(ordered_findings),
        activation_allowed=not any(item.severity == "error" for item in ordered_findings),
        findings=ordered_findings,
        report_hash=specification_hash(payload),
    )


def analyze_integration_impact(
    records: list[UiefRecordView],
    changed_ref: str | None = None,
) -> UiefImpactAnalysisReport:
    integrations = tuple(
        sorted(_by_type(records).get("integration", []), key=_integration_ref)
    )
    impacts = tuple(
        impact
        for integration in integrations
        if (
            impact := _impact_for_integration(
                integration,
                records,
                changed_ref or _integration_ref(integration),
            )
        )
        is not None
    )
    payload = {
        "changed_ref": changed_ref,
        "impacts": [item.model_dump(mode="json") for item in impacts],
    }
    return UiefImpactAnalysisReport(
        changed_ref=changed_ref,
        impact_count=len(impacts),
        impacts=impacts,
        report_hash=specification_hash(payload),
    )


def build_migration_plan(records: list[UiefRecordView]) -> UiefMigrationPlanReport:
    plans = tuple(
        _migration_plan_for_integration(integration, records)
        for integration in sorted(_by_type(records).get("integration", []), key=_integration_ref)
        if _is_migration_candidate(integration.record_document)
    )
    payload = {"migration_plans": [item.model_dump(mode="json") for item in plans]}
    return UiefMigrationPlanReport(
        migration_count=len(plans),
        migration_plans=plans,
        report_hash=specification_hash(payload),
    )


def assess_ecosystem_readiness(records: list[UiefRecordView]) -> UiefEcosystemReadinessReport:
    findings: list[UiefEcosystemReadinessFinding] = []
    findings.extend(_connector_registry_findings(records))
    findings.extend(_gateway_findings(records))
    findings.extend(_marketplace_findings(records))
    findings.extend(_partner_findings(records))
    findings.extend(_data_governance_findings(records))
    ordered = tuple(
        sorted(
            findings,
            key=lambda item: (item.category, item.severity, item.subject_ref, item.detail),
        )
    )
    connector_ready = not _has_error(ordered, "connector_registry")
    gateway_ready = not _has_error(ordered, "gateway")
    marketplace_ready = not _has_error(ordered, "marketplace")
    partner_ready = not _has_error(ordered, "partner")
    data_ready = not _has_error(ordered, "data_governance")
    production_ready = all(
        (connector_ready, gateway_ready, marketplace_ready, partner_ready, data_ready)
    )
    payload = {
        "connector_registry_ready": connector_ready,
        "gateway_ready": gateway_ready,
        "marketplace_ready": marketplace_ready,
        "partner_ready": partner_ready,
        "data_governance_ready": data_ready,
        "findings": [item.model_dump(mode="json") for item in ordered],
    }
    return UiefEcosystemReadinessReport(
        connector_registry_ready=connector_ready,
        gateway_ready=gateway_ready,
        marketplace_ready=marketplace_ready,
        partner_ready=partner_ready,
        data_governance_ready=data_ready,
        production_ready=production_ready,
        finding_count=len(ordered),
        findings=ordered,
        report_hash=specification_hash(payload),
    )


def describe_developer_surface() -> UiefDeveloperSurfaceReport:
    commands = tuple(
        UiefDeveloperSurfaceCommand(
            capability=capability,
            method=method,
            path=path,
            kernel_managed=True,
            human_approval_required=capability in {"publish", "activate", "deactivate"},
        )
        for capability, method, path in (
            ("discover", "GET", "/api/v1/projects/{project_id}/uief/runtime/topology"),
            ("validate", "GET", "/api/v1/projects/{project_id}/uief/runtime/security-readiness"),
            ("generate", "GET", "/api/v1/projects/{project_id}/uief/runtime/generation-plan"),
            ("test", "GET", "/api/v1/projects/{project_id}/uief/runtime/test-plan"),
            ("publish", "POST", "/api/v1/projects/{project_id}/uief/marketplace-assets"),
            ("activate", "POST", "/api/v1/projects/{project_id}/uief/integrations"),
            ("observe", "GET", "/api/v1/projects/{project_id}/uief/runtime/observability"),
            ("deactivate", "GET", "/api/v1/projects/{project_id}/uief/runtime/migration-plan"),
        )
    )
    payload = {"commands": [item.model_dump(mode="json") for item in commands]}
    return UiefDeveloperSurfaceReport(
        public_api_count=len(commands),
        cli_capabilities=tuple(command.capability for command in commands),
        commands=commands,
        sdk_surfaces=(
            "connector_development_kit",
            "generator_development_kit",
            "kernel_api_client",
        ),
        validation_tools=(
            "compatibility_report",
            "security_readiness_report",
            "sandbox_plan",
            "impact_analysis",
        ),
        certification_pipeline=(
            "contract_validation",
            "security_readiness",
            "sandbox_test_plan",
            "marketplace_isolation_check",
            "human_approval_gate",
        ),
        documentation_portals=(
            "integration_documentation",
            "developer_cli_surface",
            "integration_topology",
        ),
        ready_for_external_developers=all(command.kernel_managed for command in commands),
        report_hash=specification_hash(payload),
    )


def r11_deployment_preflight(settings: object) -> UiefDeploymentPreflightReport:
    mode = str(getattr(settings, "r11_external_integration_mode", "local"))
    endpoint_allowlist = _csv_settings(getattr(settings, "r11_external_endpoint_allowlist", ""))
    credential_refs = _csv_settings(getattr(settings, "r11_external_credential_refs", ""))
    partner_trust_refs = _csv_settings(getattr(settings, "r11_partner_trust_refs", ""))
    gateway_base_url = getattr(settings, "r11_gateway_base_url", None)
    secrets_manager_ref = getattr(settings, "r11_secrets_manager_ref", None)
    checks = (
        _deployment_check(
            "external_integration_mode",
            mode in {"local", "configured", "disabled"},
            f"R11 external integration mode is {mode}.",
            "Set R11_EXTERNAL_INTEGRATION_MODE to local, configured, or disabled.",
        ),
        _deployment_check(
            "endpoint_allowlist",
            mode != "configured" or bool(endpoint_allowlist),
            f"{len(endpoint_allowlist)} external endpoint pattern(s) configured.",
            "Set R11_EXTERNAL_ENDPOINT_ALLOWLIST to approved partner/service endpoint patterns.",
        ),
        _deployment_check(
            "credential_refs",
            mode != "configured"
            or (
                bool(credential_refs)
                and all(_safe_credential_ref(ref) for ref in credential_refs)
            ),
            f"{len(credential_refs)} credential reference(s) configured.",
            "Set R11_EXTERNAL_CREDENTIAL_REFS to secret-manager or mounted-secret "
            "references, not raw secrets.",
        ),
        _deployment_check(
            "partner_trust_refs",
            mode != "configured" or bool(partner_trust_refs),
            f"{len(partner_trust_refs)} partner trust reference(s) configured.",
            "Set R11_PARTNER_TRUST_REFS to approved partner trust/agreement references.",
        ),
        _deployment_check(
            "gateway_base_url",
            mode != "configured" or bool(gateway_base_url),
            "R11 governed gateway base URL is configured."
            if gateway_base_url
            else "R11 governed gateway base URL is not configured.",
            "Set R11_GATEWAY_BASE_URL to the governed external API gateway.",
        ),
        _deployment_check(
            "secrets_manager_ref",
            mode != "configured" or bool(secrets_manager_ref),
            "R11 secrets manager reference is configured."
            if secrets_manager_ref
            else "R11 secrets manager reference is not configured.",
            "Set R11_SECRETS_MANAGER_REF to the server-side secrets manager namespace.",
        ),
    )
    endpoint_ready = checks[1].ready
    credential_ready = checks[2].ready
    partner_ready = checks[3].ready
    gateway_ready = checks[4].ready
    secrets_ready = checks[5].ready
    production_operational = (
        mode in {"local", "disabled"}
        or endpoint_ready
        and credential_ready
        and partner_ready
        and gateway_ready
        and secrets_ready
    )
    payload = {
        "mode": mode,
        "checks": [item.model_dump(mode="json") for item in checks],
        "production_operational": production_operational,
    }
    return UiefDeploymentPreflightReport(
        external_integration_mode=mode,
        endpoint_allowlist_ready=endpoint_ready,
        credential_refs_ready=credential_ready,
        partner_trust_ready=partner_ready,
        gateway_ready=gateway_ready,
        secrets_manager_ready=secrets_ready,
        production_operational=production_operational,
        checks=checks,
        report_hash=specification_hash(payload),
    )


def _compatibility_for_integration(
    integration: UiefRecordView,
    by_type: dict[str, list[UiefRecordView]],
) -> UiefCompatibilityFinding:
    document = integration.record_document
    required_refs = (
        str(document["contract_ref"]),
        str(document["mapping_ref"]),
        str(document["retry_policy_ref"]),
        str(document["authentication_ref"]),
        str(document["authorization_ref"]),
    )
    available_refs = _available_refs(by_type)
    findings = tuple(
        f"missing required integration ref: {ref}"
        for ref in required_refs
        if ref not in available_refs
    )
    return UiefCompatibilityFinding(
        integration_ref=_integration_ref(integration),
        compatible=not findings,
        findings=findings,
        required_refs=required_refs,
    )


def _artifact_plan(integration: UiefRecordView) -> UiefGeneratedArtifactPlan:
    document = integration.record_document
    domain = document.get("domain")
    artifacts = [
        "connector_configuration",
        "data_mappings",
        "transformation_code",
        "authentication_configuration",
        "retry_policies",
        "monitoring_dashboard",
        "documentation",
        "automated_tests",
        "deployment_assets",
    ]
    if domain == "api":
        artifacts.extend(("api_client", "api_endpoint"))
    if domain == "event":
        artifacts.extend(("event_producer", "event_consumer"))
    if domain == "file":
        artifacts.extend(("file_parser", "file_rejection_rules"))
    return UiefGeneratedArtifactPlan(
        integration_ref=_integration_ref(integration),
        artifacts=tuple(sorted(set(artifacts))),
        synchronized_with_manifest=bool(document.get("manifest_owned")),
    )


def _available_refs(by_type: dict[str, list[UiefRecordView]]) -> set[str]:
    refs: set[str] = set()
    for records in by_type.values():
        for record in records:
            refs.add(record.record_id)
            refs.add(record.record_hash)
            for key, value in record.record_document.items():
                if key.endswith("_id") and isinstance(value, str):
                    refs.add(value)
    return refs


def _documentation_for_integration(
    integration: UiefRecordView,
    records: list[UiefRecordView],
    test_ready: dict[str, bool],
) -> UiefIntegrationDocumentation:
    document = integration.record_document
    integration_ref = _integration_ref(integration)
    sections = {
        "business_purpose": str(document.get("purpose", "")),
        "participating_systems": (
            f"Source {document.get('source_ref')} sends to "
            f"destination {document.get('destination_ref')}."
        ),
        "data_exchanged": (
            f"Domain {document.get('domain')} over protocol {document.get('protocol')} "
            f"with trigger {document.get('trigger')} and frequency {document.get('frequency')}."
        ),
        "contracts": f"Contract reference: {document.get('contract_ref')}.",
        "mapping": f"Mapping reference: {document.get('mapping_ref')}.",
        "authentication": f"Authentication policy: {document.get('authentication_ref')}.",
        "authorization": f"Authorization policy: {document.get('authorization_ref')}.",
        "error_handling": f"Error strategy: {document.get('error_strategy_ref')}.",
        "retry_policy": f"Retry policy: {document.get('retry_policy_ref')}.",
        "support_ownership": f"Owner: {document.get('owner_ref')}.",
        "testing": (
            "Certification test plan is ready."
            if test_ready.get(integration_ref)
            else "Certification test plan is blocked by unresolved references."
        ),
        "monitoring": f"Monitoring reference: {document.get('monitoring_ref')}.",
        "lifecycle": (
            f"Lifecycle state {document.get('lifecycle_state')} with activation approval "
            f"{document.get('approved_for_activation')}."
        ),
        "change_history": (
            f"Generated from append-only R11 record {integration.record_id} "
            f"with hash {integration.record_hash}."
        ),
    }
    source_hashes = _related_record_hashes(integration, records)
    payload = {
        "integration_ref": integration_ref,
        "title": str(document.get("name") or integration_ref),
        "sections": sections,
        "source_record_hashes": source_hashes,
    }
    return UiefIntegrationDocumentation(
        integration_ref=integration_ref,
        title=str(document.get("name") or integration_ref),
        sections=sections,
        source_record_hashes=source_hashes,
        documentation_hash=specification_hash(payload),
    )


def _sandbox_plan_for_integration(
    integration: UiefRecordView,
    records: list[UiefRecordView],
) -> UiefSandboxEnvironmentPlan:
    document = integration.record_document
    integration_ref = _integration_ref(integration)
    related = _related_records(integration, records)
    contract = _first_record_by_ref(records, str(document.get("contract_ref", "")))
    connector = _connector_for_integration(integration, records)
    virtualized_behaviors = {
        "error_conditions",
        "latency",
        "rate_limits",
        "unavailable_dependencies",
        "malformed_payloads",
    }
    domain = str(document.get("domain", ""))
    if domain == "api":
        virtualized_behaviors.add("api_responses")
    if domain == "event":
        virtualized_behaviors.add("event_streams")
    if domain == "file":
        virtualized_behaviors.add("file_payloads")
    sandbox_assets = {
        "simulated_credentials",
        "synthetic_data",
        "mock_services",
        "controlled_rate_limits",
    }
    if contract is not None:
        sandbox_assets.add("test_contracts")
    operations = tuple(
        sorted(
            set(
                _string_tuple(contract.record_document.get("operations") if contract else ())
                + _string_tuple(
                    connector.record_document.get("operations") if connector else ()
                )
            )
        )
    )
    production_separated = not any(
        "prod" in value.lower() or "production" in value.lower()
        for record in related
        for value in _document_ref_values(record.record_document)
    )
    payload = {
        "integration_ref": integration_ref,
        "virtualized_behaviors": sorted(virtualized_behaviors),
        "sandbox_assets": sorted(sandbox_assets),
        "limited_operations": operations,
        "controlled_rate_limits": connector.record_document.get("rate_limits", {})
        if connector is not None
        else {},
        "production_separated": production_separated,
    }
    return UiefSandboxEnvironmentPlan(
        integration_ref=integration_ref,
        virtualized_behaviors=tuple(payload["virtualized_behaviors"]),
        sandbox_assets=tuple(payload["sandbox_assets"]),
        limited_operations=operations,
        controlled_rate_limits={
            str(key): float(value)
            for key, value in dict(payload["controlled_rate_limits"]).items()
        },
        production_separated=production_separated,
    )


def _security_findings_for_integration(
    integration: UiefRecordView,
    records: list[UiefRecordView],
) -> list[UiefSecurityReadinessFinding]:
    document = integration.record_document
    integration_ref = _integration_ref(integration)
    findings: list[UiefSecurityReadinessFinding] = []
    for ref_key, category in (
        ("authentication_ref", "authentication"),
        ("authorization_ref", "authorization"),
        ("retry_policy_ref", "retry"),
        ("contract_ref", "contract"),
        ("mapping_ref", "mapping"),
    ):
        ref = str(document.get(ref_key, ""))
        if not ref or _first_record_by_ref(records, ref) is None:
            findings.append(
                UiefSecurityReadinessFinding(
                    integration_ref=integration_ref,
                    severity="error",
                    category=category,
                    detail=f"{ref_key} is not backed by a registered R11 record: {ref}",
                )
            )
    for policy in _security_policies_for_integration(integration, records):
        policy_doc = policy.record_document
        if policy_doc.get("secret_values_embedded"):
            findings.append(
                UiefSecurityReadinessFinding(
                    integration_ref=integration_ref,
                    severity="error",
                    category="credential_handling",
                    detail=f"security policy {policy.record_id} embeds secret values",
                )
            )
        credential_ref = str(policy_doc.get("credential_ref", ""))
        if not credential_ref.startswith("secret-ref:"):
            findings.append(
                UiefSecurityReadinessFinding(
                    integration_ref=integration_ref,
                    severity="error",
                    category="credential_handling",
                    detail=f"credential reference must use secret-ref:, got {credential_ref}",
                )
            )
        encryption = str(policy_doc.get("transport_encryption", "")).lower()
        if encryption in {"", "none", "plaintext", "plain"}:
            findings.append(
                UiefSecurityReadinessFinding(
                    integration_ref=integration_ref,
                    severity="error",
                    category="transport_encryption",
                    detail=f"security policy {policy.record_id} lacks transport encryption",
                )
            )
        if not policy_doc.get("authorization_scope_refs"):
            findings.append(
                UiefSecurityReadinessFinding(
                    integration_ref=integration_ref,
                    severity="error",
                    category="authorization",
                    detail=f"security policy {policy.record_id} has no authorization scopes",
                )
            )
    retry = _first_record_by_ref(records, str(document.get("retry_policy_ref", "")))
    if retry is not None and not retry.record_document.get("idempotency_required", True):
        findings.append(
            UiefSecurityReadinessFinding(
                integration_ref=integration_ref,
                severity="error",
                category="idempotency",
                detail=f"retry policy {retry.record_id} disables idempotency protection",
            )
        )
    if _critical_transactional_integration(document) and retry is None:
        findings.append(
            UiefSecurityReadinessFinding(
                integration_ref=integration_ref,
                severity="error",
                category="idempotency",
                detail="critical or transactional integration requires retry/idempotency policy",
            )
        )
    if str(document.get("lifecycle_state")) == "activated" and not document.get(
        "approved_for_activation"
    ):
        findings.append(
            UiefSecurityReadinessFinding(
                integration_ref=integration_ref,
                severity="error",
                category="approval",
                detail="activated integration lacks human activation approval",
            )
        )
    return findings


def _connector_registry_findings(
    records: list[UiefRecordView],
) -> list[UiefEcosystemReadinessFinding]:
    findings: list[UiefEcosystemReadinessFinding] = []
    connectors = _by_type(records).get("connector", [])
    connector_refs = _available_refs({"connector": connectors})
    required_operations = {
        "configure",
        "authenticate",
        "discover",
        "read",
        "write",
        "transform",
        "validate",
        "observe",
        "recover",
    }
    for connector in connectors:
        operations = set(_string_tuple(connector.record_document.get("operations")))
        missing = sorted(required_operations - operations)
        if missing:
            findings.append(
                _ecosystem_finding(
                    "connector_registry",
                    "error",
                    connector.record_id,
                    f"connector missing universal operations: {', '.join(missing)}",
                )
            )
        if connector.record_document.get("lifecycle_status") not in {
            "registered",
            "certified",
        }:
            findings.append(
                _ecosystem_finding(
                    "connector_registry",
                    "error",
                    connector.record_id,
                    "connector lifecycle status is not executable",
                )
            )
    for twin in _by_type(records).get("digital_twin", []):
        connector_ref = str(twin.record_document.get("deployed_connector_ref", ""))
        if connector_ref not in connector_refs:
            findings.append(
                _ecosystem_finding(
                    "connector_registry",
                    "error",
                    twin.record_id,
                    f"digital twin references unregistered connector {connector_ref}",
                )
            )
    return findings


def _deployment_check(
    name: str,
    ready: bool,
    detail: str,
    remediation: str,
) -> UiefDeploymentPreflightCheck:
    return UiefDeploymentPreflightCheck(
        name=name,
        ready=ready,
        detail=detail,
        remediation=remediation,
    )


def _csv_settings(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return tuple(sorted(item.strip() for item in value.split(",") if item.strip()))
    if isinstance(value, list | tuple):
        return tuple(sorted(str(item).strip() for item in value if str(item).strip()))
    return ()


def _safe_credential_ref(ref: str) -> bool:
    lowered = ref.lower()
    if not ref:
        return False
    if any(token in lowered for token in ("password=", "token=", "secret=", "apikey=")):
        return False
    return lowered.startswith(
        (
            "secret-ref:",
            "secret-manager:",
            "vault:",
            "aws-secretsmanager:",
            "gcp-secretmanager:",
            "azure-keyvault:",
            "mounted-secret:",
            "iam-role:",
        )
    )


def _gateway_findings(records: list[UiefRecordView]) -> list[UiefEcosystemReadinessFinding]:
    findings: list[UiefEcosystemReadinessFinding] = []
    for integration in _by_type(records).get("integration", []):
        document = integration.record_document
        if document.get("domain") != "api":
            continue
        integration_ref = _integration_ref(integration)
        connector = _connector_for_integration(integration, records)
        if connector is None:
            findings.append(
                _ecosystem_finding(
                    "gateway",
                    "error",
                    integration_ref,
                    "API integration has no registered deployed connector",
                )
            )
            continue
        if not connector.record_document.get("rate_limits"):
            findings.append(
                _ecosystem_finding(
                    "gateway",
                    "error",
                    connector.record_id,
                    "API gateway requires connector rate limits for throttling",
                )
            )
        for required in ("authentication_ref", "authorization_ref", "contract_ref"):
            if _first_record_by_ref(records, str(document.get(required, ""))) is None:
                findings.append(
                    _ecosystem_finding(
                        "gateway",
                        "error",
                        integration_ref,
                        f"API gateway cannot enforce missing {required}",
                    )
                )
    return findings


def _marketplace_findings(records: list[UiefRecordView]) -> list[UiefEcosystemReadinessFinding]:
    findings: list[UiefEcosystemReadinessFinding] = []
    for asset in _by_type(records).get("marketplace_asset", []):
        document = asset.record_document
        if not document.get("signature_ref"):
            findings.append(
                _ecosystem_finding(
                    "marketplace",
                    "error",
                    asset.record_id,
                    "marketplace asset is unsigned",
                )
            )
        if not document.get("license_ref"):
            findings.append(
                _ecosystem_finding(
                    "marketplace",
                    "error",
                    asset.record_id,
                    "marketplace asset lacks license reference",
                )
            )
        if not document.get("isolated_execution_required", True):
            findings.append(
                _ecosystem_finding(
                    "marketplace",
                    "error",
                    asset.record_id,
                    "marketplace asset does not require isolated execution",
                )
            )
        if document.get("certification_level") == "community":
            findings.append(
                _ecosystem_finding(
                    "marketplace",
                    "warning",
                    asset.record_id,
                    "community asset requires certification before enterprise publication",
                )
            )
    return findings


def _partner_findings(records: list[UiefRecordView]) -> list[UiefEcosystemReadinessFinding]:
    findings: list[UiefEcosystemReadinessFinding] = []
    for integration in _by_type(records).get("integration", []):
        document = integration.record_document
        if not _is_partner_ref(str(document.get("source_ref", ""))) and not _is_partner_ref(
            str(document.get("destination_ref", ""))
        ):
            continue
        integration_ref = _integration_ref(integration)
        policies = _security_policies_for_integration(integration, records)
        if not policies:
            findings.append(
                _ecosystem_finding(
                    "partner",
                    "error",
                    integration_ref,
                    "partner integration lacks registered security policy",
                )
            )
        if not document.get("owner_ref") or not document.get("compliance_classification"):
            findings.append(
                _ecosystem_finding(
                    "partner",
                    "error",
                    integration_ref,
                    "partner integration lacks ownership or compliance classification",
                )
            )
        if not any(
            _is_partner_ref(str(asset.record_document.get("publisher_ref", "")))
            or _is_partner_ref(str(asset.record_document.get("creator_ref", "")))
            for asset in _by_type(records).get("marketplace_asset", [])
        ):
            findings.append(
                _ecosystem_finding(
                    "partner",
                    "warning",
                    integration_ref,
                    "partner agreement is represented only by integration metadata",
                )
            )
    return findings


def _data_governance_findings(
    records: list[UiefRecordView],
) -> list[UiefEcosystemReadinessFinding]:
    findings: list[UiefEcosystemReadinessFinding] = []
    for integration in _by_type(records).get("integration", []):
        document = integration.record_document
        integration_ref = _integration_ref(integration)
        if not document.get("purpose"):
            findings.append(
                _ecosystem_finding(
                    "data_governance",
                    "error",
                    integration_ref,
                    "integration lacks declared data movement purpose",
                )
            )
        if not document.get("compliance_classification"):
            findings.append(
                _ecosystem_finding(
                    "data_governance",
                    "error",
                    integration_ref,
                    "integration lacks data classification",
                )
            )
        policies = _security_policies_for_integration(integration, records)
        if policies and not any(
            policy.record_document.get("residency_rules") for policy in policies
        ):
            findings.append(
                _ecosystem_finding(
                    "data_governance",
                    "error",
                    integration_ref,
                    "integration lacks residency rules",
                )
            )
        if policies and not any(
            policy.record_document.get("data_protection_rules") for policy in policies
        ):
            findings.append(
                _ecosystem_finding(
                    "data_governance",
                    "error",
                    integration_ref,
                    "integration lacks sensitive data protection rules",
                )
            )
    return findings


def _ecosystem_finding(
    category: str,
    severity: str,
    subject_ref: str,
    detail: str,
) -> UiefEcosystemReadinessFinding:
    return UiefEcosystemReadinessFinding(
        category=category,
        severity=severity,
        subject_ref=subject_ref,
        detail=detail,
    )


def _has_error(
    findings: tuple[UiefEcosystemReadinessFinding, ...],
    category: str,
) -> bool:
    return any(item.category == category and item.severity == "error" for item in findings)


def _is_partner_ref(ref: str) -> bool:
    return ref.startswith(("partner:", "vendor:", "supplier:", "customer:"))


def _impact_for_integration(
    integration: UiefRecordView,
    records: list[UiefRecordView],
    changed_ref: str,
) -> UiefImpactAssessment | None:
    related = _related_records(integration, records)
    if not any(_record_mentions(record, changed_ref) for record in related):
        return None
    document = integration.record_document
    integration_ref = _integration_ref(integration)
    twins = tuple(record for record in related if record.record_type == "digital_twin")
    contracts = tuple(record for record in related if record.record_type == "contract")
    mappings = tuple(record for record in related if record.record_type == "mapping")
    events = tuple(record for record in related if record.record_type == "event")
    marketplace_assets = tuple(
        record for record in related if record.record_type == "marketplace_asset"
    )
    provider_abstractions = tuple(
        record for record in related if record.record_type == "provider_abstraction"
    )
    connector_refs = {
        str(twin.record_document.get("deployed_connector_ref", "")) for twin in twins
    }
    connectors = tuple(
        record
        for record in related
        if record.record_type == "connector" or record.record_id in connector_refs
    )
    api_clients = tuple(
        sorted(
            {
                f"api_client:{integration_ref}"
                for contract in contracts
                if contract.record_document.get("contract_type") in {"openapi", "graphql"}
                or str(document.get("domain")) == "api"
            }
        )
    )
    event_consumers = tuple(
        sorted(
            {
                str(consumer)
                for event in events
                for consumer in _string_tuple(event.record_document.get("consumer_refs"))
            }
        )
    )
    tests = tuple(sorted({f"certification_tests:{integration_ref}"} | _test_refs(mappings)))
    runtime_deployments = tuple(
        sorted(
            {
                str(twin.record_document.get("endpoint_ref"))
                for twin in twins
                if twin.record_document.get("endpoint_ref")
            }
        )
    )
    provider_refs = {
        str(ref)
        for provider in provider_abstractions
        for ref in (
            provider.record_document.get("primary_provider_ref"),
            *_string_tuple(provider.record_document.get("backup_provider_refs")),
            *_string_tuple(provider.record_document.get("regional_provider_refs")),
        )
        if ref
    }
    dependent_services = tuple(
        sorted(
            {str(document.get("destination_ref"))}
            | {
                str(dep)
                for twin in twins
                for dep in _string_tuple(twin.record_document.get("dependency_refs"))
            }
            | provider_refs
        )
    )
    partner_agreements = tuple(
        sorted(
            {
                str(asset.record_document.get("publisher_ref"))
                for asset in marketplace_assets
                if asset.record_document.get("publisher_ref")
            }
        )
    )
    return UiefImpactAssessment(
        integration_ref=integration_ref,
        changed_ref=changed_ref,
        affected_connectors=tuple(sorted(record.record_id for record in connectors)),
        dependent_services=dependent_services,
        event_consumers=event_consumers,
        api_clients=api_clients,
        mappings=tuple(sorted(record.record_id for record in mappings)),
        tests=tests,
        documentation_refs=(f"documentation:{integration_ref}",),
        partner_agreements=partner_agreements,
        runtime_deployments=runtime_deployments,
        risk_level=_impact_risk_level(
            contracts=contracts,
            twins=twins,
            marketplace_assets=marketplace_assets,
            document=document,
        ),
    )


def _migration_plan_for_integration(
    integration: UiefRecordView,
    records: list[UiefRecordView],
) -> UiefMigrationPlan:
    document = integration.record_document
    mappings = tuple(
        record
        for record in _related_records(integration, records)
        if record.record_type == "mapping"
    )
    stages = (
        _migration_stage(
            "discover",
            "Discover source schemas, operations, fields, permissions, and dependencies.",
            ("dependency_inventory", "discovery_snapshot"),
        ),
        _migration_stage(
            "model",
            "Model the target canonical contract and desired Manifest state.",
            ("manifest_change_proposal", "target_contract"),
        ),
        _migration_stage(
            "map",
            "Map source fields and events to the canonical model.",
            tuple(sorted(record.record_id for record in mappings)) or ("mapping_record",),
        ),
        _migration_stage(
            "validate",
            "Validate contracts, mappings, security policy, and generated tests.",
            ("compatibility_report", "security_readiness_report", "test_plan"),
        ),
        _migration_stage(
            "synchronize",
            "Synchronize source and target data with reconciliation checkpoints.",
            ("reconciliation_report", "sync_checkpoint"),
        ),
        _migration_stage(
            "parallel_run",
            "Run source and target side by side before production cutover.",
            ("business_signoff", "parallel_run_metrics"),
        ),
        _migration_stage(
            "cut_over",
            "Move traffic to the target integration under approval control.",
            ("activation_approval", "runtime_health_snapshot"),
        ),
        _migration_stage(
            "retire",
            "Deactivate legacy route and preserve audit evidence.",
            ("deactivation_record", "retention_evidence"),
        ),
    )
    return UiefMigrationPlan(
        integration_ref=_integration_ref(integration),
        strategy=_migration_strategy(document),
        source_ref=str(document.get("source_ref", "")),
        target_ref=str(document.get("destination_ref", "")),
        stages=stages,
        rollback_required=True,
        parallel_run_required=True,
    )


def _migration_stage(
    stage: str,
    objective: str,
    required_evidence: tuple[str, ...],
) -> UiefMigrationStagePlan:
    return UiefMigrationStagePlan(
        stage=stage,
        objective=objective,
        required_evidence=tuple(sorted(set(required_evidence))),
    )


def _related_record_hashes(
    integration: UiefRecordView,
    records: list[UiefRecordView],
) -> tuple[str, ...]:
    integration_ref = _integration_ref(integration)
    refs = _document_ref_values(integration.record_document) | {integration_ref}
    hashes = {
        record.record_hash
        for record in records
        if record is integration
        or record.integration_ref == integration_ref
        or bool(refs & _document_id_values(record.record_document))
    }
    return tuple(sorted(hashes))


def _related_records(
    integration: UiefRecordView,
    records: list[UiefRecordView],
) -> tuple[UiefRecordView, ...]:
    integration_ref = _integration_ref(integration)
    refs = _document_ref_values(integration.record_document) | {integration_ref}
    return tuple(
        record
        for record in records
        if record is integration
        or record.integration_ref == integration_ref
        or bool(refs & _document_id_values(record.record_document))
    )


def _first_record_by_ref(
    records: list[UiefRecordView],
    ref: str,
) -> UiefRecordView | None:
    if not ref:
        return None
    for record in records:
        if ref in {record.record_id, record.record_hash} | _document_id_values(
            record.record_document
        ):
            return record
    return None


def _connector_for_integration(
    integration: UiefRecordView,
    records: list[UiefRecordView],
) -> UiefRecordView | None:
    integration_ref = _integration_ref(integration)
    for record in records:
        if (
            record.record_type == "digital_twin"
            and record.record_document.get("integration_ref") == integration_ref
        ):
            connector_ref = str(record.record_document.get("deployed_connector_ref", ""))
            return _first_record_by_ref(records, connector_ref)
    return None


def _security_policies_for_integration(
    integration: UiefRecordView,
    records: list[UiefRecordView],
) -> tuple[UiefRecordView, ...]:
    refs = {
        str(integration.record_document.get("authentication_ref", "")),
        str(integration.record_document.get("authorization_ref", "")),
    }
    return tuple(
        record
        for ref in refs
        if (record := _first_record_by_ref(records, ref)) is not None
        and record.record_type == "security_policy"
    )


def _critical_transactional_integration(document: dict[str, Any]) -> bool:
    haystack = " ".join(
        str(document.get(key, ""))
        for key in (
            "name",
            "purpose",
            "domain",
            "trigger",
            "compliance_classification",
        )
    ).lower()
    return any(
        token in haystack
        for token in (
            "critical",
            "financial",
            "payment",
            "transaction",
            "regulated",
        )
    )


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, list | tuple):
        return tuple(str(item) for item in value)
    return ()


def _record_mentions(record: UiefRecordView, ref: str) -> bool:
    if ref in {record.record_id, record.record_hash}:
        return True
    if ref in _document_id_values(record.record_document):
        return True
    if ref in _document_ref_values(record.record_document):
        return True
    return any(ref == value for value in _document_scalar_values(record.record_document))


def _document_scalar_values(document: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for value in document.values():
        if isinstance(value, str):
            values.add(value)
        elif isinstance(value, list | tuple):
            values.update(str(item) for item in value if isinstance(item, str))
    return values


def _test_refs(mappings: tuple[UiefRecordView, ...]) -> set[str]:
    return {
        str(ref)
        for mapping in mappings
        for ref in _string_tuple(mapping.record_document.get("test_refs"))
    }


def _impact_risk_level(
    *,
    contracts: tuple[UiefRecordView, ...],
    twins: tuple[UiefRecordView, ...],
    marketplace_assets: tuple[UiefRecordView, ...],
    document: dict[str, Any],
) -> str:
    if _critical_transactional_integration(document):
        return "high"
    if marketplace_assets:
        return "high"
    if any(twin.health_status in {"degraded", "unavailable", "unknown"} for twin in twins):
        return "high"
    if any(
        contract.record_document.get("contract_type") in {"openapi", "asyncapi"}
        for contract in contracts
    ):
        return "medium"
    return "low"


def _is_migration_candidate(document: dict[str, Any]) -> bool:
    haystack = " ".join(
        str(document.get(key, ""))
        for key in (
            "name",
            "purpose",
            "source_ref",
            "destination_ref",
            "protocol",
            "trigger",
        )
    ).lower()
    return any(
        token in haystack
        for token in (
            "legacy",
            "migrate",
            "migration",
            "cutover",
            "parallel",
            "mainframe",
            "soap",
            "edi",
            "file",
            "terminal",
        )
    )


def _migration_strategy(document: dict[str, Any]) -> str:
    haystack = " ".join(
        str(document.get(key, ""))
        for key in ("name", "purpose", "protocol", "source_ref")
    ).lower()
    if "terminal" in haystack or "screen" in haystack:
        return "screen_or_terminal_mediation"
    if "database" in haystack or "db:" in haystack:
        return "database_mediation"
    if "file" in haystack or "edi" in haystack:
        return "file_exchange"
    if "soap" in haystack or "legacy" in haystack:
        return "api_wrapping"
    return "staged_replacement"


def _document_ref_values(document: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for key, value in document.items():
        if key.endswith("_ref") and isinstance(value, str):
            refs.add(value)
        elif key.endswith("_refs") and isinstance(value, list | tuple):
            refs.update(str(item) for item in value)
    return refs


def _document_id_values(document: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for key, value in document.items():
        if key.endswith("_id") and isinstance(value, str):
            ids.add(value)
    return ids


def _connect_ref(
    nodes: dict[str, UiefTopologyNode],
    edges: set[tuple[str, str, str, str]],
    source: str,
    target: str,
    target_type: str,
    relationship: str,
    integration_ref: str,
) -> None:
    if not source or not target:
        return
    _add_node(nodes, source, _node_type_for_ref(source, "integration"), source, {})
    _add_node(nodes, target, _node_type_for_ref(target, target_type), target, {})
    edges.add((source, target, relationship, integration_ref))


def _add_node(
    nodes: dict[str, UiefTopologyNode],
    node_id: str,
    node_type: str,
    label: str,
    metadata: dict[str, str],
) -> None:
    if not node_id:
        return
    existing = nodes.get(node_id)
    if existing is not None:
        merged = {**existing.metadata, **{k: v for k, v in metadata.items() if v}}
        nodes[node_id] = existing.model_copy(update={"metadata": merged})
        return
    nodes[node_id] = UiefTopologyNode(
        node_id=node_id,
        node_type=node_type,
        label=label,
        metadata={key: value for key, value in metadata.items() if value},
    )


def _node_type_for_ref(ref: str, fallback: str) -> str:
    if ref.startswith("UIEF-INT-"):
        return "integration"
    if ref.startswith("UIEF-CONN-"):
        return "connector"
    if ref.startswith("UIEF-CTR-"):
        return "contract"
    if ref.startswith("UIEF-MAP-"):
        return "mapping"
    if ref.startswith("UIEF-RETRY-"):
        return "retry_policy"
    if ref.startswith("UIEF-SEC-"):
        return "security_policy"
    if ref.startswith("UIEF-TWIN-"):
        return "digital_twin"
    return fallback


def _by_type(records: list[UiefRecordView]) -> dict[str, list[UiefRecordView]]:
    result: dict[str, list[UiefRecordView]] = {}
    for record in records:
        result.setdefault(record.record_type, []).append(record)
    return result


def _integration_ref(record: UiefRecordView) -> str:
    return str(
        record.record_document.get("integration_id")
        or record.integration_ref
        or record.record_id
    )
