from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from ai_enterprise.application.r21_execution_orchestrator_runtime import (
    EXECUTION_ORCHESTRATOR_VERSION,
    R21Execution,
)
from ai_enterprise.domain.specification.kernel import specification_hash

ARTIFACT_INTELLIGENCE_VERSION = "artifact-intelligence-1.0"
DETERMINISTIC_ARTIFACT_TIMESTAMP = "1970-01-01T00:00:00Z"

ARTIFACT_CLASSES: tuple[str, ...] = (
    "definition",
    "design",
    "implementation",
    "validation",
    "governance",
    "operational",
    "delivery",
)

LIFECYCLE_STATES: tuple[str, ...] = (
    "PROPOSED",
    "GENERATED",
    "REGISTERED",
    "SCHEMA_VALIDATED",
    "TECHNICALLY_VALIDATED",
    "POLICY_VALIDATED",
    "REVIEW_REQUIRED",
    "REVIEWED",
    "APPROVED",
    "RELEASE_CANDIDATE",
    "RELEASED",
    "SUPERSEDED",
    "DEPRECATED",
    "REVOKED",
    "ARCHIVED",
)

VALIDATION_STATES: tuple[str, ...] = ("NOT_VALIDATED", "PASSED", "FAILED", "WAIVED")
FRESHNESS_STATES: tuple[str, ...] = ("CURRENT", "STALE", "UNKNOWN")
INTEGRITY_STATES: tuple[str, ...] = ("UNVERIFIED", "VERIFIED", "FAILED")
GOVERNANCE_STATES: tuple[str, ...] = ("QUARANTINED", "REVIEW_REQUIRED", "APPROVED", "BLOCKED")

TRACE_RELATIONSHIP_TYPES: tuple[str, ...] = (
    "DERIVED_FROM",
    "REFINES",
    "IMPLEMENTS",
    "IMPLEMENTED_BY",
    "SATISFIES",
    "SATISFIED_BY",
    "CONSTRAINS",
    "CONSTRAINED_BY",
    "VALIDATES",
    "VALIDATED_BY",
    "TESTS",
    "TESTED_BY",
    "MITIGATES",
    "MITIGATED_BY",
    "DEPENDS_ON",
    "REQUIRED_BY",
    "GENERATED_FROM",
    "SUPERSEDES",
    "SUPERSEDED_BY",
    "APPROVES",
    "APPROVED_BY",
    "REJECTS",
    "REJECTED_BY",
    "DOCUMENTS",
    "DOCUMENTED_BY",
    "DEPLOYS",
    "DEPLOYED_BY",
    "OPERATES",
    "OPERATED_BY",
    "EVIDENCES",
    "EVIDENCED_BY",
)

GRAPH_NODE_TYPES: tuple[str, ...] = (
    "PROJECT",
    "MANIFEST",
    "OBJECTIVE",
    "STAKEHOLDER",
    "CAPABILITY",
    "REQUIREMENT",
    "CONSTRAINT",
    "RISK",
    "POLICY",
    "WORK_PACKAGE",
    "EXECUTION",
    "WORKER",
    "TOOL",
    "MODEL",
    "ARTIFACT",
    "ARTIFACT_VERSION",
    "VALIDATION",
    "FINDING",
    "ASSUMPTION",
    "DECISION",
    "APPROVAL",
    "EXCEPTION",
    "DEPLOYMENT",
    "RELEASE",
    "DELIVERY_PACKAGE",
)

GRAPH_EDGE_TYPES: tuple[str, ...] = (
    "CONTAINS",
    "DERIVES",
    "REQUIRES",
    "PRODUCES",
    "CONSUMES",
    "USES",
    "EXECUTES",
    "VALIDATES",
    "FAILS",
    "PASSES",
    "APPROVES",
    "REJECTS",
    "SUPERSEDES",
    "DEPENDS_ON",
    "SATISFIES",
    "MITIGATES",
    "EVIDENCES",
    "DEPLOYS",
    "DELIVERS",
)

FINDING_STATES: tuple[str, ...] = (
    "OPEN",
    "ACKNOWLEDGED",
    "REMEDIATION_IN_PROGRESS",
    "RESOLVED",
    "ACCEPTED_RISK",
    "FALSE_POSITIVE",
    "DEFERRED",
    "SUPERSEDED",
)


class R22Diagnostic(BaseModel):
    model_config = ConfigDict(frozen=True)

    severity: str
    category: str
    code: str
    message: str
    path: str


class R22ArtifactState(BaseModel):
    model_config = ConfigDict(frozen=True)

    lifecycle: str
    validation: str
    freshness: str
    integrity: str
    governance: str


class R22ArtifactContent(BaseModel):
    model_config = ConfigDict(frozen=True)

    media_type: str
    storage_uri: str
    size_bytes: int
    checksum: str
    content_address: str
    content_preview: dict[str, Any]


class R22ProvenanceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    provenance_id: str
    tenant_id: str
    project_id: str
    subject_type: str
    subject_id: str
    producer: dict[str, str]
    initiator: dict[str, str]
    inputs: tuple[dict[str, str], ...]
    instructions: dict[str, Any]
    tools: tuple[dict[str, str], ...]
    model: dict[str, str]
    environment: dict[str, str]
    assumptions: tuple[str, ...]
    started_at: str
    completed_at: str
    integrity: dict[str, str]
    provenance_hash: str


class R22TraceRelationship(BaseModel):
    model_config = ConfigDict(frozen=True)

    relationship_id: str
    tenant_id: str
    project_id: str
    source_type: str
    source_id: str
    relationship_type: str
    target_type: str
    target_id: str
    confidence: str
    verified: bool
    created_by: str
    relationship_hash: str


class R22ArtifactDependency(BaseModel):
    model_config = ConfigDict(frozen=True)

    dependency_id: str
    artifact_version_id: str
    depends_on_version_id: str
    dependency_type: str
    compatibility: str
    dependency_hash: str


class R22Finding(BaseModel):
    model_config = ConfigDict(frozen=True)

    finding_id: str
    artifact_version_id: str
    validation_id: str
    severity: str
    category: str
    message: str
    state: str
    finding_hash: str


class R22ValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    validation_id: str
    artifact_version_id: str
    validator_category: str
    validator_id: str
    status: str
    findings: tuple[R22Finding, ...]
    evidence_refs: tuple[str, ...]
    validated_at: str
    validation_hash: str


class R22ApprovalBinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    approval_id: str
    artifact_version_id: str
    approver_role: str
    approver_id: str
    decision: str
    decided_at: str
    bound_checksum: str
    approval_hash: str


class R22EvidenceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    tenant_id: str
    project_id: str
    claim_id: str | None
    subject_type: str
    subject_id: str
    evidence_type: str
    supports: str
    evaluator: str
    confidence: str
    limitations: tuple[str, ...]
    content_address: str
    evidence_hash: str


class R22Claim(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim_id: str
    tenant_id: str
    project_id: str
    claim_text: str
    subject_type: str
    subject_id: str
    status: str
    supporting_evidence_ids: tuple[str, ...]
    confidence: str
    claim_hash: str


class R22ArtifactVersion(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_version_id: str
    artifact_id: str
    project_id: str
    tenant_id: str
    version_number: int
    semantic_version: str
    revision: str
    state: R22ArtifactState
    content: R22ArtifactContent
    schema_id: str
    schema_version: str
    created_by: str
    created_at: str
    provenance_id: str
    trace_relationship_ids: tuple[str, ...]
    dependency_ids: tuple[str, ...]
    validation_ids: tuple[str, ...]
    approval_ids: tuple[str, ...]
    retention_policy_id: str
    classification: str
    legal_hold: bool
    immutable: bool
    version_hash: str


class R22ArtifactRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: str
    project_id: str
    tenant_id: str
    artifact_type: str
    artifact_class: str
    title: str
    current_version_id: str
    version_ids: tuple[str, ...]
    created_by: str
    registered_at: str
    artifact_hash: str


class R22EvidenceGraphNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    node_id: str
    tenant_id: str
    project_id: str
    node_type: str
    object_id: str
    label: str
    metadata: dict[str, Any]


class R22EvidenceGraphEdge(BaseModel):
    model_config = ConfigDict(frozen=True)

    edge_id: str
    tenant_id: str
    project_id: str
    edge_type: str
    source_node_id: str
    target_node_id: str
    metadata: dict[str, Any]


class R22EvidenceGraph(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: str
    project_id: str
    nodes: tuple[R22EvidenceGraphNode, ...]
    edges: tuple[R22EvidenceGraphEdge, ...]
    graph_hash: str


class R22ArtifactEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    event_type: str
    event_version: int
    occurred_at: str
    tenant_id: str
    project_id: str
    correlation_id: str
    actor: dict[str, str]
    subject: dict[str, str]
    payload: dict[str, Any]
    integrity: dict[str, str]


class R22ArtifactRegistry(BaseModel):
    model_config = ConfigDict(frozen=True)

    registry_id: str
    tenant_id: str
    project_id: str
    version: str
    artifacts: tuple[R22ArtifactRecord, ...]
    versions: tuple[R22ArtifactVersion, ...]
    provenance_records: tuple[R22ProvenanceRecord, ...]
    trace_relationships: tuple[R22TraceRelationship, ...]
    dependencies: tuple[R22ArtifactDependency, ...]
    validations: tuple[R22ValidationResult, ...]
    findings: tuple[R22Finding, ...]
    approvals: tuple[R22ApprovalBinding, ...]
    evidence_records: tuple[R22EvidenceRecord, ...]
    claims: tuple[R22Claim, ...]
    graph: R22EvidenceGraph
    events: tuple[R22ArtifactEvent, ...]
    registry_hash: str


class R22RegistrationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    accepted: bool
    registry: R22ArtifactRegistry
    artifact_id: str | None
    artifact_version_id: str | None
    diagnostics: tuple[R22Diagnostic, ...]


class R22IntegrityReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_version_id: str
    checksum_status: str
    content_address_status: str
    provenance_chain_status: str
    signature_status: str
    conclusion: str
    diagnostics: tuple[R22Diagnostic, ...]
    report_hash: str


class R22PromotionReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_version_id: str
    target_lifecycle: str
    allowed: bool
    diagnostics: tuple[R22Diagnostic, ...]
    registry: R22ArtifactRegistry
    report_hash: str


class R22ImpactAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    analysis_id: str
    tenant_id: str
    project_id: str
    changed_object_type: str
    changed_object_id: str
    affected_artifact_version_ids: tuple[str, ...]
    affected_approval_ids: tuple[str, ...]
    affected_validation_ids: tuple[str, ...]
    required_actions: tuple[str, ...]
    analysis_hash: str


class R22FreshnessEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True)

    evaluation_id: str
    artifact_version_id: str
    freshness: str
    stale_reason: str | None
    upstream_object_id: str | None
    evaluation_hash: str


class R22EvidenceCoverage(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    total_artifacts: int
    traced_artifacts: int
    validated_artifacts: int
    approved_artifacts: int
    released_artifacts: int
    critical_gaps: tuple[dict[str, Any], ...]
    coverage_hash: str


class R22EvidencePackage(BaseModel):
    model_config = ConfigDict(frozen=True)

    package_id: str
    tenant_id: str
    project_id: str
    execution_id: str | None
    generated_at: str
    contents: dict[str, Any]
    integrity: dict[str, str]
    package_hash: str


class R22ReproducibilityRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    reproducibility_id: str
    artifact_version_id: str
    status: str
    required_inputs: dict[str, str]
    reproduction_test: dict[str, Any]
    limitations: tuple[str, ...]
    reproducibility_hash: str


class R22OperationalBackendCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    backend: str
    status: str
    required_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    findings: tuple[R22Diagnostic, ...]


class R22OperationalReadinessReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str
    production: bool
    status: str
    ready: bool
    checks: tuple[R22OperationalBackendCheck, ...]
    findings: tuple[R22Diagnostic, ...]
    next_action: str
    report_hash: str


def r22_empty_registry(project_id: str, tenant_id: str = "default") -> R22ArtifactRegistry:
    graph = _build_graph(
        tenant_id=tenant_id,
        project_id=project_id,
        artifacts=(),
        versions=(),
        traces=(),
        validations=(),
        findings=(),
        approvals=(),
        evidence=(),
    )
    registry_seed = {"tenant_id": tenant_id, "project_id": project_id}
    registry_id = f"r22-registry-{specification_hash(registry_seed)[:16]}"
    return _rehash_registry(
        R22ArtifactRegistry(
            registry_id=registry_id,
            tenant_id=tenant_id,
            project_id=project_id,
            version=ARTIFACT_INTELLIGENCE_VERSION,
            artifacts=(),
            versions=(),
            provenance_records=(),
            trace_relationships=(),
            dependencies=(),
            validations=(),
            findings=(),
            approvals=(),
            evidence_records=(),
            claims=(),
            graph=graph,
            events=(),
            registry_hash="",
        )
    )


def r22_register_artifact(
    registry: dict[str, Any] | R22ArtifactRegistry,
    *,
    artifact_type: str,
    artifact_class: str,
    title: str,
    content: dict[str, Any] | str,
    media_type: str = "application/json",
    schema_id: str = "artifact.schema.json",
    schema_version: str = "1.0",
    created_by: str = "system",
    provenance: dict[str, Any] | None = None,
    manifest_traces: tuple[dict[str, str], ...] = (),
    work_package_ids: tuple[str, ...] = (),
    dependencies: tuple[str, ...] = (),
    validations: tuple[dict[str, Any], ...] = (),
    approvals: tuple[dict[str, str], ...] = (),
    declared_checksum: str | None = None,
    classification: str = "INTERNAL",
    retention_policy_id: str = "default-retention",
) -> R22RegistrationResult:
    current = _registry(registry)
    diagnostics = _artifact_input_diagnostics(
        artifact_type, artifact_class, content, declared_checksum
    )
    content_payload = _content_payload(content)
    checksum = f"sha256:{specification_hash(content_payload)}"
    if declared_checksum and declared_checksum != checksum:
        diagnostics += (
            _diag(
                "error",
                "integrity",
                "R22_CHECKSUM_MISMATCH",
                "Declared checksum does not match submitted content",
                "$.content.checksum",
            ),
        )
    if diagnostics:
        failed = _append_event(
            current,
            "artifact.integrity.failed",
            {"artifact_type": artifact_type, "title": title},
            {"diagnostics": [item.model_dump(mode="json") for item in diagnostics]},
            created_by,
        )
        return R22RegistrationResult(
            accepted=False,
            registry=failed,
            artifact_id=None,
            artifact_version_id=None,
            diagnostics=diagnostics,
        )

    artifact_seed = {
        "tenant_id": current.tenant_id,
        "project_id": current.project_id,
        "artifact_type": artifact_type,
        "artifact_class": artifact_class,
        "title": title,
    }
    artifact_id = f"art-{specification_hash(artifact_seed)[:20]}"
    version_number = 1 + sum(
        1 for version in current.versions if version.artifact_id == artifact_id
    )
    version_seed = {**artifact_seed, "version": version_number, "checksum": checksum}
    version_id = f"artver-{specification_hash(version_seed)[:20]}"
    content_record = R22ArtifactContent(
        media_type=media_type,
        storage_uri=f"cas://{checksum}",
        size_bytes=len(json.dumps(content_payload, sort_keys=True, separators=(",", ":")).encode()),
        checksum=checksum,
        content_address=f"sha256/{checksum.removeprefix('sha256:')}",
        content_preview=content_payload
        if isinstance(content_payload, dict)
        else {"value": content_payload},
    )
    prov = _create_provenance(
        current,
        subject_type="ARTIFACT_VERSION",
        subject_id=version_id,
        producer=provenance.get("producer", {"actor_type": "worker", "actor_id": created_by})
        if provenance
        else {"actor_type": "worker", "actor_id": created_by},
        initiator=provenance.get("initiator", {"actor_type": "system", "actor_id": "r22"})
        if provenance
        else {"actor_type": "system", "actor_id": "r22"},
        inputs=tuple(provenance.get("inputs", ())) if provenance else (),
        instructions=provenance.get("instructions", {}) if provenance else {},
        tools=tuple(provenance.get("tools", ())) if provenance else (),
        model=provenance.get("model", {}) if provenance else {},
        environment=provenance.get("environment", {"runtime": ARTIFACT_INTELLIGENCE_VERSION})
        if provenance
        else {"runtime": ARTIFACT_INTELLIGENCE_VERSION},
        assumptions=tuple(provenance.get("assumptions", ())) if provenance else (),
    )
    trace_records = tuple(
        _trace(
            current,
            source_type=trace["source_type"],
            source_id=trace["source_id"],
            relationship_type=trace.get("relationship_type", "SATISFIES"),
            target_type="ARTIFACT_VERSION",
            target_id=version_id,
            created_by=created_by,
        )
        for trace in manifest_traces
    ) + tuple(
        _trace(
            current,
            source_type="WORK_PACKAGE",
            source_id=work_package_id,
            relationship_type="PRODUCES",
            target_type="ARTIFACT_VERSION",
            target_id=version_id,
            created_by=created_by,
        )
        for work_package_id in work_package_ids
    )
    dependency_records = tuple(
        _dependency(version_id, dependency_version_id, dependency_type="DEPENDS_ON")
        for dependency_version_id in dependencies
    )
    finding_records: list[R22Finding] = []
    validation_records: list[R22ValidationResult] = []
    for validation in validations:
        validation_record = _validation(version_id, validation)
        validation_records.append(validation_record)
        finding_records.extend(validation_record.findings)
    approval_records = tuple(_approval(version_id, checksum, approval) for approval in approvals)
    validation_state = _version_validation_state(tuple(validation_records))
    governance_state = (
        "APPROVED" if approval_records and validation_state == "PASSED" else "REVIEW_REQUIRED"
    )
    lifecycle = "APPROVED" if governance_state == "APPROVED" else "REGISTERED"
    if validation_state == "FAILED":
        governance_state = "BLOCKED"
    version = R22ArtifactVersion(
        artifact_version_id=version_id,
        artifact_id=artifact_id,
        project_id=current.project_id,
        tenant_id=current.tenant_id,
        version_number=version_number,
        semantic_version=f"1.0.{version_number}",
        revision=specification_hash({"artifact_id": artifact_id, "version_number": version_number})[
            :12
        ],
        state=R22ArtifactState(
            lifecycle=lifecycle,
            validation=validation_state,
            freshness="CURRENT",
            integrity="VERIFIED",
            governance=governance_state,
        ),
        content=content_record,
        schema_id=schema_id,
        schema_version=schema_version,
        created_by=created_by,
        created_at=DETERMINISTIC_ARTIFACT_TIMESTAMP,
        provenance_id=prov.provenance_id,
        trace_relationship_ids=tuple(trace.relationship_id for trace in trace_records),
        dependency_ids=tuple(item.dependency_id for item in dependency_records),
        validation_ids=tuple(item.validation_id for item in validation_records),
        approval_ids=tuple(item.approval_id for item in approval_records),
        retention_policy_id=retention_policy_id,
        classification=classification,
        legal_hold=False,
        immutable=True,
        version_hash="",
    )
    version = version.model_copy(
        update={
            "version_hash": specification_hash(
                version.model_dump(mode="json", exclude={"version_hash"})
            )
        }
    )
    existing = _artifact_by_id(current, artifact_id)
    if existing is None:
        artifact = R22ArtifactRecord(
            artifact_id=artifact_id,
            project_id=current.project_id,
            tenant_id=current.tenant_id,
            artifact_type=artifact_type,
            artifact_class=artifact_class,
            title=title,
            current_version_id=version_id,
            version_ids=(version_id,),
            created_by=created_by,
            registered_at=DETERMINISTIC_ARTIFACT_TIMESTAMP,
            artifact_hash="",
        )
        artifacts = current.artifacts + (
            artifact.model_copy(
                update={
                    "artifact_hash": specification_hash(
                        artifact.model_dump(mode="json", exclude={"artifact_hash"})
                    )
                }
            ),
        )
    else:
        updated = existing.model_copy(
            update={
                "current_version_id": version_id,
                "version_ids": existing.version_ids + (version_id,),
            }
        )
        updated = updated.model_copy(
            update={
                "artifact_hash": specification_hash(
                    updated.model_dump(mode="json", exclude={"artifact_hash"})
                )
            }
        )
        artifacts = tuple(
            updated if item.artifact_id == artifact_id else item for item in current.artifacts
        )
    next_registry = current.model_copy(
        update={
            "artifacts": artifacts,
            "versions": current.versions + (version,),
            "provenance_records": current.provenance_records + (prov,),
            "trace_relationships": current.trace_relationships + trace_records,
            "dependencies": current.dependencies + dependency_records,
            "validations": current.validations + tuple(validation_records),
            "findings": current.findings + tuple(finding_records),
            "approvals": current.approvals + approval_records,
        }
    )
    next_registry = _refresh(next_registry)
    next_registry = _append_event(
        next_registry,
        "artifact.version.created" if existing else "artifact.registered",
        {"artifact_id": artifact_id, "artifact_version_id": version_id},
        {"checksum": checksum, "artifact_class": artifact_class},
        created_by,
    )
    return R22RegistrationResult(
        accepted=True,
        registry=next_registry,
        artifact_id=artifact_id,
        artifact_version_id=version_id,
        diagnostics=(),
    )


def r22_verify_integrity(
    registry: dict[str, Any] | R22ArtifactRegistry,
    artifact_version_id: str,
    *,
    content: dict[str, Any] | str | None = None,
) -> R22IntegrityReport:
    current = _registry(registry)
    version = _version_by_id(current, artifact_version_id)
    diagnostics: tuple[R22Diagnostic, ...] = ()
    checksum_status = "VERIFIED"
    address_status = "VERIFIED"
    if version is None:
        diagnostics += (
            _diag(
                "error",
                "integrity",
                "R22_VERSION_NOT_FOUND",
                "Artifact version not found",
                "$.artifact_version_id",
            ),
        )
        checksum_status = "FAILED"
        address_status = "FAILED"
    elif content is not None:
        actual = f"sha256:{specification_hash(_content_payload(content))}"
        if actual != version.content.checksum:
            diagnostics += (
                _diag(
                    "error",
                    "integrity",
                    "R22_CONTENT_MISMATCH",
                    "Provided content does not match registered checksum",
                    "$.content",
                ),
            )
            checksum_status = "FAILED"
            address_status = "FAILED"
    conclusion = "AUTHENTIC" if not diagnostics else "INVALID"
    payload = {
        "artifact_version_id": artifact_version_id,
        "checksum_status": checksum_status,
        "content_address_status": address_status,
        "diagnostics": [item.model_dump(mode="json") for item in diagnostics],
    }
    return R22IntegrityReport(
        artifact_version_id=artifact_version_id,
        checksum_status=checksum_status,
        content_address_status=address_status,
        provenance_chain_status="VERIFIED"
        if version and _provenance_by_id(current, version.provenance_id)
        else "FAILED",
        signature_status="NOT_CONFIGURED",
        conclusion=conclusion,
        diagnostics=diagnostics,
        report_hash=specification_hash(payload),
    )


def r22_promote_artifact_version(
    registry: dict[str, Any] | R22ArtifactRegistry,
    artifact_version_id: str,
    target_lifecycle: str,
    *,
    actor_id: str = "system",
) -> R22PromotionReport:
    current = _registry(registry)
    diagnostics = _promotion_diagnostics(current, artifact_version_id, target_lifecycle)
    if diagnostics:
        return R22PromotionReport(
            artifact_version_id=artifact_version_id,
            target_lifecycle=target_lifecycle,
            allowed=False,
            diagnostics=diagnostics,
            registry=current,
            report_hash=specification_hash(
                {
                    "artifact_version_id": artifact_version_id,
                    "allowed": False,
                    "diagnostics": [item.model_dump(mode="json") for item in diagnostics],
                }
            ),
        )
    version = _version_by_id(current, artifact_version_id)
    assert version is not None
    updated_version = version.model_copy(
        update={"state": version.state.model_copy(update={"lifecycle": target_lifecycle})}
    )
    updated_version = updated_version.model_copy(
        update={
            "version_hash": specification_hash(
                updated_version.model_dump(mode="json", exclude={"version_hash"})
            )
        }
    )
    next_registry = current.model_copy(
        update={
            "versions": tuple(
                updated_version if item.artifact_version_id == artifact_version_id else item
                for item in current.versions
            )
        }
    )
    next_registry = _refresh(next_registry)
    event_type = "artifact.released" if target_lifecycle == "RELEASED" else "artifact.promoted"
    next_registry = _append_event(
        next_registry,
        event_type,
        {"artifact_version_id": artifact_version_id},
        {"previous_state": version.state.lifecycle, "new_state": target_lifecycle},
        actor_id,
    )
    return R22PromotionReport(
        artifact_version_id=artifact_version_id,
        target_lifecycle=target_lifecycle,
        allowed=True,
        diagnostics=(),
        registry=next_registry,
        report_hash=specification_hash(
            {
                "artifact_version_id": artifact_version_id,
                "allowed": True,
                "target_lifecycle": target_lifecycle,
            }
        ),
    )


def r22_supersede_artifact_version(
    registry: dict[str, Any] | R22ArtifactRegistry,
    previous_version_id: str,
    replacement_version_id: str,
    *,
    reason: str,
    actor_id: str = "system",
) -> R22ArtifactRegistry:
    current = _registry(registry)
    previous = _version_by_id(current, previous_version_id)
    replacement = _version_by_id(current, replacement_version_id)
    if previous is None or replacement is None:
        return current
    superseded = previous.model_copy(
        update={
            "state": previous.state.model_copy(
                update={"lifecycle": "SUPERSEDED", "freshness": "STALE"}
            ),
            "version_hash": specification_hash(
                {
                    **previous.model_dump(mode="json"),
                    "superseded_by": replacement_version_id,
                    "reason": reason,
                }
            ),
        }
    )
    trace = _trace(
        current,
        source_type="ARTIFACT_VERSION",
        source_id=replacement_version_id,
        relationship_type="SUPERSEDES",
        target_type="ARTIFACT_VERSION",
        target_id=previous_version_id,
        created_by=actor_id,
    )
    next_registry = current.model_copy(
        update={
            "versions": tuple(
                superseded if item.artifact_version_id == previous_version_id else item
                for item in current.versions
            ),
            "trace_relationships": current.trace_relationships + (trace,),
        }
    )
    next_registry = _refresh(next_registry)
    return _append_event(
        next_registry,
        "artifact.superseded",
        {"artifact_version_id": previous_version_id},
        {"replacement_version_id": replacement_version_id, "reason": reason},
        actor_id,
    )


def r22_mark_downstream_stale(
    registry: dict[str, Any] | R22ArtifactRegistry,
    source_object_id: str,
    *,
    actor_id: str = "system",
) -> tuple[R22ArtifactRegistry, R22ImpactAnalysis]:
    current = _registry(registry)
    affected = _downstream_artifact_versions(current, source_object_id)
    affected_set = set(affected)
    versions = tuple(
        item.model_copy(update={"state": item.state.model_copy(update={"freshness": "STALE"})})
        if item.artifact_version_id in affected_set
        else item
        for item in current.versions
    )
    approvals = tuple(
        approval.approval_id
        for approval in current.approvals
        if approval.artifact_version_id in affected_set
    )
    validations = tuple(
        validation.validation_id
        for validation in current.validations
        if validation.artifact_version_id in affected_set
    )
    analysis_payload = {
        "tenant_id": current.tenant_id,
        "project_id": current.project_id,
        "changed_object_id": source_object_id,
        "affected": affected,
    }
    analysis = R22ImpactAnalysis(
        analysis_id=f"r22-impact-{specification_hash(analysis_payload)[:16]}",
        tenant_id=current.tenant_id,
        project_id=current.project_id,
        changed_object_type="OBJECT",
        changed_object_id=source_object_id,
        affected_artifact_version_ids=affected,
        affected_approval_ids=approvals,
        affected_validation_ids=validations,
        required_actions=("revalidate_affected_artifacts", "review_invalidated_approvals")
        if affected
        else (),
        analysis_hash=specification_hash(analysis_payload),
    )
    next_registry = _refresh(current.model_copy(update={"versions": versions}))
    if affected:
        next_registry = _append_event(
            next_registry,
            "impact.analysis.completed",
            {"object_id": source_object_id},
            analysis.model_dump(mode="json"),
            actor_id,
        )
    return next_registry, analysis


def r22_evidence_coverage(registry: dict[str, Any] | R22ArtifactRegistry) -> R22EvidenceCoverage:
    current = _registry(registry)
    total = len(current.versions)
    traced = sum(1 for version in current.versions if version.trace_relationship_ids)
    validated = sum(
        1 for version in current.versions if version.state.validation in {"PASSED", "WAIVED"}
    )
    approved = sum(1 for version in current.versions if version.approval_ids)
    released = sum(1 for version in current.versions if version.state.lifecycle == "RELEASED")
    gaps: list[dict[str, Any]] = []
    for version in current.versions:
        missing: list[str] = []
        if not version.trace_relationship_ids:
            missing.append("manifest_trace")
        if version.state.validation not in {"PASSED", "WAIVED"}:
            missing.append("validation_evidence")
        if (
            version.state.lifecycle in {"APPROVED", "RELEASE_CANDIDATE", "RELEASED"}
            and not version.approval_ids
        ):
            missing.append("approval")
        if missing:
            gaps.append({"object_id": version.artifact_version_id, "missing": missing})
    payload = {"project_id": current.project_id, "total": total, "gaps": gaps}
    return R22EvidenceCoverage(
        project_id=current.project_id,
        total_artifacts=total,
        traced_artifacts=traced,
        validated_artifacts=validated,
        approved_artifacts=approved,
        released_artifacts=released,
        critical_gaps=tuple(gaps),
        coverage_hash=specification_hash(payload),
    )


def r22_generate_evidence_package(
    registry: dict[str, Any] | R22ArtifactRegistry,
    *,
    execution_id: str | None = None,
) -> R22EvidencePackage:
    current = _registry(registry)
    coverage = r22_evidence_coverage(current)
    contents = {
        "registry_snapshot": current.model_dump(mode="json", exclude={"events"}),
        "artifact_inventory": [artifact.model_dump(mode="json") for artifact in current.artifacts],
        "artifact_checksums": {
            version.artifact_version_id: version.content.checksum for version in current.versions
        },
        "provenance_export": [
            record.model_dump(mode="json") for record in current.provenance_records
        ],
        "traceability_export": current.graph.model_dump(mode="json"),
        "validation_results": [record.model_dump(mode="json") for record in current.validations],
        "open_findings": [
            finding.model_dump(mode="json")
            for finding in current.findings
            if finding.state == "OPEN"
        ],
        "resolved_findings": [
            finding.model_dump(mode="json")
            for finding in current.findings
            if finding.state != "OPEN"
        ],
        "approvals": [approval.model_dump(mode="json") for approval in current.approvals],
        "evidence_coverage": coverage.model_dump(mode="json"),
    }
    package_hash = specification_hash(contents)
    package_seed = {"project_id": current.project_id, "package_hash": package_hash}
    return R22EvidencePackage(
        package_id=f"r22-evidence-package-{specification_hash(package_seed)[:16]}",
        tenant_id=current.tenant_id,
        project_id=current.project_id,
        execution_id=execution_id,
        generated_at=DETERMINISTIC_ARTIFACT_TIMESTAMP,
        contents=contents,
        integrity={"package_checksum": f"sha256:{package_hash}", "signed_by": "not-configured"},
        package_hash=package_hash,
    )


def r22_graph_neighbors(
    registry: dict[str, Any] | R22ArtifactRegistry,
    node_id: str,
    *,
    direction: str = "downstream",
    actor_tenant_id: str | None = None,
) -> dict[str, Any]:
    current = _registry(registry)
    if actor_tenant_id is not None and actor_tenant_id != current.tenant_id:
        return {
            "authorized": False,
            "nodes": [],
            "edges": [],
            "diagnostics": [
                _diag(
                    "error",
                    "security",
                    "R22_TENANT_ISOLATION",
                    "Tenant graph traversal denied",
                    "$.tenant_id",
                ).model_dump(mode="json")
            ],
        }
    edges = tuple(
        edge
        for edge in current.graph.edges
        if (direction == "downstream" and edge.source_node_id == node_id)
        or (direction == "upstream" and edge.target_node_id == node_id)
    )
    node_ids = {
        edge.target_node_id if direction == "downstream" else edge.source_node_id for edge in edges
    }
    nodes = tuple(node for node in current.graph.nodes if node.node_id in node_ids)
    return {
        "authorized": True,
        "nodes": [node.model_dump(mode="json") for node in nodes],
        "edges": [edge.model_dump(mode="json") for edge in edges],
        "diagnostics": [],
    }


def r22_graph_path(
    registry: dict[str, Any] | R22ArtifactRegistry,
    source_node_id: str,
    target_node_id: str,
    *,
    actor_tenant_id: str | None = None,
) -> dict[str, Any]:
    current = _registry(registry)
    if actor_tenant_id is not None and actor_tenant_id != current.tenant_id:
        return {
            "authorized": False,
            "path": [],
            "diagnostics": [
                _diag(
                    "error",
                    "security",
                    "R22_TENANT_ISOLATION",
                    "Tenant graph traversal denied",
                    "$.tenant_id",
                ).model_dump(mode="json")
            ],
        }
    adjacency: dict[str, list[str]] = {}
    for edge in current.graph.edges:
        adjacency.setdefault(edge.source_node_id, []).append(edge.target_node_id)
    queue: deque[tuple[str, tuple[str, ...]]] = deque([(source_node_id, (source_node_id,))])
    visited = {source_node_id}
    while queue:
        node, path = queue.popleft()
        if node == target_node_id:
            return {"authorized": True, "path": list(path), "diagnostics": []}
        for child in sorted(adjacency.get(node, [])):
            if child not in visited:
                visited.add(child)
                queue.append((child, path + (child,)))
    return {
        "authorized": True,
        "path": [],
        "diagnostics": [
            _diag(
                "warning", "graph", "R22_PATH_NOT_FOUND", "No graph path found", "$.graph"
            ).model_dump(mode="json")
        ],
    }


def r22_search_artifacts(
    registry: dict[str, Any] | R22ArtifactRegistry,
    *,
    artifact_class: str | None = None,
    lifecycle: str | None = None,
    classification: str | None = None,
) -> tuple[R22ArtifactVersion, ...]:
    current = _registry(registry)
    artifact_by_id = {artifact.artifact_id: artifact for artifact in current.artifacts}
    results: list[R22ArtifactVersion] = []
    for version in current.versions:
        artifact = artifact_by_id.get(version.artifact_id)
        if artifact_class and (artifact is None or artifact.artifact_class != artifact_class):
            continue
        if lifecycle and version.state.lifecycle != lifecycle:
            continue
        if classification and version.classification != classification:
            continue
        results.append(version)
    return tuple(sorted(results, key=lambda item: item.artifact_version_id))


def r22_reproducibility_record(
    registry: dict[str, Any] | R22ArtifactRegistry,
    artifact_version_id: str,
) -> R22ReproducibilityRecord:
    current = _registry(registry)
    version = _version_by_id(current, artifact_version_id)
    provenance = _provenance_by_id(current, version.provenance_id) if version else None
    required_inputs = {
        "manifest_snapshot": "available"
        if any(
            t.target_id == artifact_version_id and t.source_type in {"MANIFEST", "REQUIREMENT"}
            for t in current.trace_relationships
        )
        else "unavailable",
        "registry_snapshot": "available",
        "policy_snapshot": "available",
        "source_inputs": "available" if provenance and provenance.inputs else "unavailable",
        "tool_versions": "available" if provenance and provenance.tools else "unavailable",
        "worker_version": "available" if provenance else "unavailable",
        "model_version": "available"
        if provenance and provenance.model.get("model_id")
        else "unavailable_exact",
        "environment_image": "available"
        if provenance and provenance.environment
        else "unavailable",
    }
    missing = [key for key, value in required_inputs.items() if value.startswith("unavailable")]
    status = (
        "EXACTLY_REPRODUCIBLE"
        if not missing
        else "PARTIALLY_REPRODUCIBLE"
        if len(missing) <= 3
        else "NON_REPRODUCIBLE"
    )
    payload = {"artifact_version_id": artifact_version_id, "required_inputs": required_inputs}
    return R22ReproducibilityRecord(
        reproducibility_id=f"r22-repro-{specification_hash(payload)[:16]}",
        artifact_version_id=artifact_version_id,
        status=status,
        required_inputs=required_inputs,
        reproduction_test={
            "attempted": False,
            "output_checksum_match": None,
            "semantic_equivalence": "not_attempted",
        },
        limitations=tuple(f"{key} is {required_inputs[key]}" for key in missing),
        reproducibility_hash=specification_hash(payload),
    )


def r22_operational_readiness(
    config: dict[str, Any] | None = None,
    *,
    production: bool = True,
) -> R22OperationalReadinessReport:
    payload = config or {}
    checks = (
        _signature_readiness(payload.get("signature"), production=production),
        _object_storage_readiness(payload.get("object_storage"), production=production),
        _graph_backend_readiness(payload.get("graph_backend"), production=production),
    )
    findings = tuple(finding for check in checks for finding in check.findings)
    ready = not findings
    report_seed = {
        "production": production,
        "checks": [check.model_dump(mode="json") for check in checks],
        "ready": ready,
    }
    return R22OperationalReadinessReport(
        schema_version="1.0",
        production=production,
        status="ready" if ready else "blocked",
        ready=ready,
        checks=checks,
        findings=findings,
        next_action=(
            "R22 operational integrations are configured for the requested environment."
            if ready
            else (
                "Provide real signature/KMS, object-storage, and graph-backend "
                "configuration references, then rerun R22 operational readiness."
            )
        ),
        report_hash=specification_hash(report_seed),
    )


def _signature_readiness(raw: Any, *, production: bool) -> R22OperationalBackendCheck:
    data = raw if isinstance(raw, dict) else {}
    provider = str(data.get("provider", "")).strip().lower()
    required = ("provider", "key_ref", "algorithm", "verification_ref")
    findings: list[R22Diagnostic] = []
    missing = _missing_fields(data, required)
    if missing:
        findings.append(
            _diag(
                "error",
                "signature",
                "R22_SIGNATURE_CONFIG_REQUIRED",
                "Signature provider, key reference, algorithm, and verification "
                "reference are required",
                "$.signature",
            )
        )
    if production and provider in {"", "disabled", "mock", "local"}:
        findings.append(
            _diag(
                "error",
                "signature",
                "R22_PRODUCTION_SIGNATURE_PROVIDER_INVALID",
                "Production R22 signatures require a non-mock external provider "
                "such as kms, hsm, or custom",
                "$.signature.provider",
            )
        )
    return R22OperationalBackendCheck(
        backend="signature",
        status="ready" if not findings else "blocked",
        required_fields=required,
        missing_fields=missing,
        findings=tuple(findings),
    )


def _object_storage_readiness(raw: Any, *, production: bool) -> R22OperationalBackendCheck:
    data = raw if isinstance(raw, dict) else {}
    provider = str(data.get("provider", "")).strip().lower()
    required = ("provider", "bucket", "region", "credentials_ref", "encryption")
    findings: list[R22Diagnostic] = []
    missing = _missing_fields(data, required)
    if missing:
        findings.append(
            _diag(
                "error",
                "object_storage",
                "R22_OBJECT_STORAGE_CONFIG_REQUIRED",
                "Object storage provider, bucket, region, credentials reference, "
                "and encryption are required",
                "$.object_storage",
            )
        )
    if production and provider in {"", "filesystem", "local", "mock"}:
        findings.append(
            _diag(
                "error",
                "object_storage",
                "R22_PRODUCTION_OBJECT_STORAGE_PROVIDER_INVALID",
                "Production R22 artifact storage requires external object storage "
                "such as s3, gcs, azure, or custom",
                "$.object_storage.provider",
            )
        )
    if str(data.get("credentials_ref", "")).startswith(("AKIA", "secret:", "token:")):
        findings.append(
            _diag(
                "error",
                "object_storage",
                "R22_INLINE_STORAGE_SECRET_FORBIDDEN",
                "Object storage configuration must reference managed credentials, "
                "not inline secret values",
                "$.object_storage.credentials_ref",
            )
        )
    return R22OperationalBackendCheck(
        backend="object_storage",
        status="ready" if not findings else "blocked",
        required_fields=required,
        missing_fields=missing,
        findings=tuple(findings),
    )


def _graph_backend_readiness(raw: Any, *, production: bool) -> R22OperationalBackendCheck:
    data = raw if isinstance(raw, dict) else {}
    backend = str(data.get("backend", "")).strip().lower()
    required = ("backend", "endpoint", "repository", "credentials_ref", "partition_strategy")
    findings: list[R22Diagnostic] = []
    missing = _missing_fields(data, required)
    if missing:
        findings.append(
            _diag(
                "error",
                "graph_backend",
                "R22_GRAPH_BACKEND_CONFIG_REQUIRED",
                "Graph backend, endpoint, repository, credentials reference, and "
                "partition strategy are required",
                "$.graph_backend",
            )
        )
    if production and backend in {"", "in-memory", "memory", "filesystem", "local", "mock"}:
        findings.append(
            _diag(
                "error",
                "graph_backend",
                "R22_PRODUCTION_GRAPH_BACKEND_INVALID",
                "Production R22 graph intelligence requires an external graph "
                "backend such as neo4j, rdf, or custom",
                "$.graph_backend.backend",
            )
        )
    return R22OperationalBackendCheck(
        backend="graph_backend",
        status="ready" if not findings else "blocked",
        required_fields=required,
        missing_fields=missing,
        findings=tuple(findings),
    )


def _missing_fields(data: dict[str, Any], required: tuple[str, ...]) -> tuple[str, ...]:
    missing: list[str] = []
    for field in required:
        value = data.get(field)
        if value is None or value == "" or value == () or value == []:
            missing.append(field)
    return tuple(missing)


def r22_ingest_r21_execution(
    execution: dict[str, Any] | R21Execution,
    *,
    tenant_id: str = "default",
) -> R22ArtifactRegistry:
    r21 = (
        execution if isinstance(execution, R21Execution) else R21Execution.model_validate(execution)
    )
    registry = r22_empty_registry(r21.project_id, tenant_id)
    worker_requests = {item.work_package_id: item for item in r21.worker_requests}
    validations_by_artifact: dict[str, list[dict[str, Any]]] = {}
    for validation in r21.validations:
        for artifact_id in validation.artifact_ids:
            validations_by_artifact.setdefault(artifact_id, []).append(
                {
                    "validator_category": "traceability",
                    "validator_id": ",".join(validation.validators),
                    "status": "PASSED" if validation.passed else "FAILED",
                    "findings": validation.findings,
                    "evidence_refs": (),
                }
            )
    for artifact in r21.artifacts:
        worker_request = worker_requests.get(artifact.work_package_id)
        trace_context = worker_request.context.get("manifest_trace", {}) if worker_request else {}
        source_objects = tuple(trace_context.get("source_objects", ()))
        traces = tuple(
            {
                "source_type": str(source.get("object_type", "object")).upper(),
                "source_id": str(source.get("object_id", artifact.manifest_trace_hash)),
                "relationship_type": "SATISFIES"
                if str(source.get("object_type", "")).lower()
                in {"requirement", "quality_requirement", "security_requirement"}
                else "DERIVED_FROM",
            }
            for source in source_objects
        ) or (
            {
                "source_type": "MANIFEST",
                "source_id": artifact.manifest_trace_hash,
                "relationship_type": "DERIVED_FROM",
            },
        )
        approvals = tuple(
            {
                "approval_id": decision.decision_id,
                "approver_role": decision.actor_role,
                "approver_id": decision.actor_id,
                "decision": decision.decision,
            }
            for gate in r21.approval_gates
            for decision in gate.decisions
            if artifact.artifact_hash in decision.bound_artifact_hashes
            or artifact.checksum in decision.bound_artifact_hashes
        )
        registration = r22_register_artifact(
            registry,
            artifact_type=artifact.artifact_type,
            artifact_class=_class_for_artifact_type(artifact.artifact_type),
            title=f"{artifact.artifact_type} from {artifact.work_package_id}",
            content={
                "source_uri": artifact.uri,
                "artifact_id": artifact.artifact_id,
                "work_package_id": artifact.work_package_id,
                "promotion_level": artifact.promotion_level,
                "source_checksum": artifact.checksum,
            },
            schema_id=f"{artifact.artifact_type}.schema.json",
            created_by=artifact.work_package_id,
            provenance={
                "producer": {"actor_type": "worker", "actor_id": artifact.work_package_id},
                "initiator": {"actor_type": "execution_orchestrator", "actor_id": r21.execution_id},
                "inputs": tuple(
                    {
                        "object_type": str(source.get("object_type", "object")),
                        "object_id": str(source.get("object_id", artifact.manifest_trace_hash)),
                    }
                    for source in source_objects
                ),
                "instructions": {"work_package_id": artifact.work_package_id},
                "tools": (
                    {
                        "tool_id": "r21_execution_orchestrator",
                        "version": EXECUTION_ORCHESTRATOR_VERSION,
                    },
                ),
                "model": {"provider": "rule-engine", "model_id": "deterministic"},
                "environment": {"runtime": EXECUTION_ORCHESTRATOR_VERSION},
            },
            manifest_traces=traces,
            work_package_ids=(artifact.work_package_id,),
            validations=tuple(validations_by_artifact.get(artifact.artifact_id, [])),
            approvals=approvals,
        )
        registry = registration.registry
    for evidence in r21.evidence:
        record = _evidence(
            registry,
            claim_id=None,
            subject_type=evidence.entity_type.upper(),
            subject_id=evidence.entity_id,
            evidence_type=evidence.evidence_type,
            content_address=f"sha256/{evidence.checksum.removeprefix('sha256:')}",
        )
        registry = registry.model_copy(
            update={"evidence_records": registry.evidence_records + (record,)}
        )
    return _refresh(registry)


def r22_write_registry(registry: dict[str, Any] | R22ArtifactRegistry, path: Path) -> str:
    current = _registry(registry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(current.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8"
    )
    return current.registry_hash


def r22_read_registry(path: Path) -> R22ArtifactRegistry | None:
    if not path.exists():
        return None
    return R22ArtifactRegistry.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _registry(registry: dict[str, Any] | R22ArtifactRegistry) -> R22ArtifactRegistry:
    return (
        registry
        if isinstance(registry, R22ArtifactRegistry)
        else R22ArtifactRegistry.model_validate(registry)
    )


def _content_payload(content: dict[str, Any] | str) -> dict[str, Any] | str:
    return content


def _artifact_input_diagnostics(
    artifact_type: str,
    artifact_class: str,
    content: dict[str, Any] | str,
    declared_checksum: str | None,
) -> tuple[R22Diagnostic, ...]:
    diagnostics: list[R22Diagnostic] = []
    if not artifact_type:
        diagnostics.append(
            _diag(
                "error",
                "schema",
                "R22_ARTIFACT_TYPE_REQUIRED",
                "Artifact type is required",
                "$.artifact_type",
            )
        )
    if artifact_class not in ARTIFACT_CLASSES:
        diagnostics.append(
            _diag(
                "error",
                "schema",
                "R22_ARTIFACT_CLASS_INVALID",
                "Artifact class is not in the R22 taxonomy",
                "$.artifact_class",
            )
        )
    if content in ({}, ""):
        diagnostics.append(
            _diag(
                "error",
                "schema",
                "R22_CONTENT_REQUIRED",
                "Artifact content is required",
                "$.content",
            )
        )
    if declared_checksum and not declared_checksum.startswith("sha256:"):
        diagnostics.append(
            _diag(
                "error",
                "integrity",
                "R22_CHECKSUM_FORMAT",
                "Declared checksum must use sha256:<hex>",
                "$.content.checksum",
            )
        )
    return tuple(diagnostics)


def _create_provenance(
    registry: R22ArtifactRegistry,
    *,
    subject_type: str,
    subject_id: str,
    producer: dict[str, str],
    initiator: dict[str, str],
    inputs: tuple[dict[str, str], ...],
    instructions: dict[str, Any],
    tools: tuple[dict[str, str], ...],
    model: dict[str, str],
    environment: dict[str, str],
    assumptions: tuple[str, ...],
) -> R22ProvenanceRecord:
    payload = {
        "tenant_id": registry.tenant_id,
        "project_id": registry.project_id,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "producer": producer,
        "inputs": inputs,
    }
    provenance_hash = specification_hash(payload)
    return R22ProvenanceRecord(
        provenance_id=f"r22-prov-{provenance_hash[:16]}",
        tenant_id=registry.tenant_id,
        project_id=registry.project_id,
        subject_type=subject_type,
        subject_id=subject_id,
        producer=producer,
        initiator=initiator,
        inputs=inputs,
        instructions=instructions,
        tools=tools,
        model=model,
        environment=environment,
        assumptions=assumptions,
        started_at=DETERMINISTIC_ARTIFACT_TIMESTAMP,
        completed_at=DETERMINISTIC_ARTIFACT_TIMESTAMP,
        integrity={"checksum": f"sha256:{provenance_hash}"},
        provenance_hash=provenance_hash,
    )


def _trace(
    registry: R22ArtifactRegistry,
    *,
    source_type: str,
    source_id: str,
    relationship_type: str,
    target_type: str,
    target_id: str,
    created_by: str,
) -> R22TraceRelationship:
    relation = (
        relationship_type if relationship_type in TRACE_RELATIONSHIP_TYPES else "DERIVED_FROM"
    )
    payload = {
        "tenant_id": registry.tenant_id,
        "project_id": registry.project_id,
        "source_type": source_type,
        "source_id": source_id,
        "relationship_type": relation,
        "target_type": target_type,
        "target_id": target_id,
    }
    relation_hash = specification_hash(payload)
    return R22TraceRelationship(
        relationship_id=f"r22-trace-{relation_hash[:16]}",
        tenant_id=registry.tenant_id,
        project_id=registry.project_id,
        source_type=source_type,
        source_id=source_id,
        relationship_type=relation,
        target_type=target_type,
        target_id=target_id,
        confidence="HIGH",
        verified=True,
        created_by=created_by,
        relationship_hash=relation_hash,
    )


def _dependency(
    version_id: str, dependency_version_id: str, *, dependency_type: str
) -> R22ArtifactDependency:
    payload = {
        "artifact_version_id": version_id,
        "depends_on_version_id": dependency_version_id,
        "dependency_type": dependency_type,
    }
    dependency_hash = specification_hash(payload)
    return R22ArtifactDependency(
        dependency_id=f"r22-dep-{dependency_hash[:16]}",
        artifact_version_id=version_id,
        depends_on_version_id=dependency_version_id,
        dependency_type=dependency_type,
        compatibility="UNKNOWN",
        dependency_hash=dependency_hash,
    )


def _validation(version_id: str, validation: dict[str, Any]) -> R22ValidationResult:
    validation_seed = {"artifact_version_id": version_id, "validation": validation}
    validation_id = f"r22-val-{specification_hash(validation_seed)[:16]}"
    findings = tuple(
        _finding(version_id, validation_id, finding) for finding in validation.get("findings", ())
    )
    status = validation.get("status", "PASSED" if not findings else "FAILED")
    payload = {
        "artifact_version_id": version_id,
        "validator": validation.get("validator_id"),
        "status": status,
        "findings": [item.model_dump(mode="json") for item in findings],
    }
    return R22ValidationResult(
        validation_id=validation_id,
        artifact_version_id=version_id,
        validator_category=validation.get("validator_category", "schema"),
        validator_id=validation.get("validator_id", "r22-schema-validator"),
        status=status,
        findings=findings,
        evidence_refs=tuple(validation.get("evidence_refs", ())),
        validated_at=DETERMINISTIC_ARTIFACT_TIMESTAMP,
        validation_hash=specification_hash(payload),
    )


def _finding(version_id: str, validation_id: str, finding: dict[str, Any]) -> R22Finding:
    payload = {
        "artifact_version_id": version_id,
        "validation_id": validation_id,
        "finding": finding,
    }
    finding_hash = specification_hash(payload)
    return R22Finding(
        finding_id=f"r22-find-{finding_hash[:16]}",
        artifact_version_id=version_id,
        validation_id=validation_id,
        severity=finding.get("severity", "medium"),
        category=finding.get("category", "validation"),
        message=finding.get("message", "Validation finding"),
        state=finding.get("state", "OPEN")
        if finding.get("state", "OPEN") in FINDING_STATES
        else "OPEN",
        finding_hash=finding_hash,
    )


def _approval(version_id: str, checksum: str, approval: dict[str, str]) -> R22ApprovalBinding:
    payload = {"artifact_version_id": version_id, "checksum": checksum, "approval": approval}
    approval_hash = specification_hash(payload)
    return R22ApprovalBinding(
        approval_id=approval.get("approval_id", f"r22-appr-{approval_hash[:16]}"),
        artifact_version_id=version_id,
        approver_role=approval.get("approver_role", "owner"),
        approver_id=approval.get("approver_id", "system"),
        decision=approval.get("decision", "APPROVED"),
        decided_at=DETERMINISTIC_ARTIFACT_TIMESTAMP,
        bound_checksum=checksum,
        approval_hash=approval_hash,
    )


def _evidence(
    registry: R22ArtifactRegistry,
    *,
    claim_id: str | None,
    subject_type: str,
    subject_id: str,
    evidence_type: str,
    content_address: str,
) -> R22EvidenceRecord:
    payload = {
        "tenant_id": registry.tenant_id,
        "project_id": registry.project_id,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "evidence_type": evidence_type,
        "content_address": content_address,
    }
    evidence_hash = specification_hash(payload)
    return R22EvidenceRecord(
        evidence_id=f"r22-evid-{evidence_hash[:16]}",
        tenant_id=registry.tenant_id,
        project_id=registry.project_id,
        claim_id=claim_id,
        subject_type=subject_type,
        subject_id=subject_id,
        evidence_type=evidence_type,
        supports="SUPPORTED",
        evaluator="r22-evidence-engine",
        confidence="HIGH",
        limitations=(),
        content_address=content_address,
        evidence_hash=evidence_hash,
    )


def _version_validation_state(validations: tuple[R22ValidationResult, ...]) -> str:
    if not validations:
        return "NOT_VALIDATED"
    if any(
        validation.status == "FAILED"
        or any(finding.state == "OPEN" for finding in validation.findings)
        for validation in validations
    ):
        return "FAILED"
    return "PASSED"


def _promotion_diagnostics(
    registry: R22ArtifactRegistry,
    artifact_version_id: str,
    target_lifecycle: str,
) -> tuple[R22Diagnostic, ...]:
    version = _version_by_id(registry, artifact_version_id)
    diagnostics: list[R22Diagnostic] = []
    if version is None:
        return (
            _diag(
                "error",
                "promotion",
                "R22_VERSION_NOT_FOUND",
                "Artifact version not found",
                "$.artifact_version_id",
            ),
        )
    if target_lifecycle not in LIFECYCLE_STATES:
        diagnostics.append(
            _diag(
                "error",
                "promotion",
                "R22_LIFECYCLE_INVALID",
                "Target lifecycle is invalid",
                "$.target_lifecycle",
            )
        )
    if version.state.integrity != "VERIFIED":
        diagnostics.append(
            _diag(
                "error",
                "integrity",
                "R22_INTEGRITY_REQUIRED",
                "Artifact integrity must be verified before promotion",
                "$.state.integrity",
            )
        )
    if target_lifecycle in {"APPROVED", "RELEASE_CANDIDATE", "RELEASED"}:
        if not _provenance_by_id(registry, version.provenance_id):
            diagnostics.append(
                _diag(
                    "error",
                    "provenance",
                    "R22_PROVENANCE_REQUIRED",
                    "Generated artifact requires provenance before approval or release",
                    "$.provenance_id",
                )
            )
        if not version.trace_relationship_ids:
            diagnostics.append(
                _diag(
                    "error",
                    "traceability",
                    "R22_TRACE_REQUIRED",
                    "Artifact requires Manifest/work-package trace before approval or release",
                    "$.trace_relationship_ids",
                )
            )
        if version.state.validation != "PASSED":
            diagnostics.append(
                _diag(
                    "error",
                    "validation",
                    "R22_VALIDATION_REQUIRED",
                    "Artifact requires passing validation before approval or release",
                    "$.state.validation",
                )
            )
    if target_lifecycle in {"RELEASE_CANDIDATE", "RELEASED"} and not version.approval_ids:
        diagnostics.append(
            _diag(
                "error",
                "governance",
                "R22_APPROVAL_REQUIRED",
                "Release requires approval bound to the exact artifact version",
                "$.approval_ids",
            )
        )
    if any(
        finding.artifact_version_id == artifact_version_id and finding.state == "OPEN"
        for finding in registry.findings
    ):
        diagnostics.append(
            _diag(
                "error",
                "findings",
                "R22_OPEN_FINDING_BLOCKS_PROMOTION",
                "Open findings block promotion",
                "$.findings",
            )
        )
    return tuple(diagnostics)


def _build_graph(
    *,
    tenant_id: str,
    project_id: str,
    artifacts: tuple[R22ArtifactRecord, ...],
    versions: tuple[R22ArtifactVersion, ...],
    traces: tuple[R22TraceRelationship, ...],
    validations: tuple[R22ValidationResult, ...],
    findings: tuple[R22Finding, ...],
    approvals: tuple[R22ApprovalBinding, ...],
    evidence: tuple[R22EvidenceRecord, ...],
) -> R22EvidenceGraph:
    nodes: dict[str, R22EvidenceGraphNode] = {}
    edges: dict[str, R22EvidenceGraphEdge] = {}

    def add_node(
        node_type: str, object_id: str, label: str, metadata: dict[str, Any] | None = None
    ) -> str:
        node_id = f"{node_type}:{object_id}"
        nodes[node_id] = R22EvidenceGraphNode(
            node_id=node_id,
            tenant_id=tenant_id,
            project_id=project_id,
            node_type=node_type,
            object_id=object_id,
            label=label,
            metadata=metadata or {},
        )
        return node_id

    def add_edge(
        edge_type: str, source: str, target: str, metadata: dict[str, Any] | None = None
    ) -> None:
        payload = {"edge_type": edge_type, "source": source, "target": target}
        edge_id = f"r22-edge-{specification_hash(payload)[:16]}"
        edges[edge_id] = R22EvidenceGraphEdge(
            edge_id=edge_id,
            tenant_id=tenant_id,
            project_id=project_id,
            edge_type=edge_type,
            source_node_id=source,
            target_node_id=target,
            metadata=metadata or {},
        )

    project_node = add_node("PROJECT", project_id, project_id)
    for artifact in artifacts:
        artifact_node = add_node(
            "ARTIFACT",
            artifact.artifact_id,
            artifact.title,
            {"artifact_class": artifact.artifact_class},
        )
        add_edge("CONTAINS", project_node, artifact_node)
    for version in versions:
        artifact_node = add_node("ARTIFACT", version.artifact_id, version.artifact_id)
        version_node = add_node(
            "ARTIFACT_VERSION",
            version.artifact_version_id,
            version.artifact_version_id,
            {"lifecycle": version.state.lifecycle},
        )
        add_edge("CONTAINS", artifact_node, version_node)
    for trace in traces:
        source_node = add_node(
            trace.source_type if trace.source_type in GRAPH_NODE_TYPES else "ARTIFACT",
            trace.source_id,
            trace.source_id,
        )
        target_node = add_node(
            trace.target_type if trace.target_type in GRAPH_NODE_TYPES else "ARTIFACT",
            trace.target_id,
            trace.target_id,
        )
        add_edge(
            "SATISFIES"
            if trace.relationship_type in {"SATISFIES", "IMPLEMENTS", "VALIDATES"}
            else "DERIVES",
            source_node,
            target_node,
            {"relationship_type": trace.relationship_type},
        )
    for validation in validations:
        validation_node = add_node(
            "VALIDATION",
            validation.validation_id,
            validation.validator_id,
            {"status": validation.status},
        )
        version_node = add_node(
            "ARTIFACT_VERSION", validation.artifact_version_id, validation.artifact_version_id
        )
        add_edge("VALIDATES", validation_node, version_node)
    for finding in findings:
        finding_node = add_node(
            "FINDING",
            finding.finding_id,
            finding.message,
            {"state": finding.state, "severity": finding.severity},
        )
        version_node = add_node(
            "ARTIFACT_VERSION", finding.artifact_version_id, finding.artifact_version_id
        )
        add_edge("FAILS", finding_node, version_node)
    for approval in approvals:
        approval_node = add_node(
            "APPROVAL",
            approval.approval_id,
            approval.decision,
            {"approver_role": approval.approver_role},
        )
        version_node = add_node(
            "ARTIFACT_VERSION", approval.artifact_version_id, approval.artifact_version_id
        )
        add_edge("APPROVES", approval_node, version_node)
    for record in evidence:
        evidence_node = add_node(
            "VALIDATION",
            record.evidence_id,
            record.evidence_type,
            {"confidence": record.confidence},
        )
        subject_node = add_node(
            record.subject_type if record.subject_type in GRAPH_NODE_TYPES else "ARTIFACT",
            record.subject_id,
            record.subject_id,
        )
        add_edge("EVIDENCES", evidence_node, subject_node)
    graph_payload = {"nodes": sorted(nodes), "edges": sorted(edges)}
    return R22EvidenceGraph(
        tenant_id=tenant_id,
        project_id=project_id,
        nodes=tuple(nodes[key] for key in sorted(nodes)),
        edges=tuple(edges[key] for key in sorted(edges)),
        graph_hash=specification_hash(graph_payload),
    )


def _refresh(registry: R22ArtifactRegistry) -> R22ArtifactRegistry:
    graph = _build_graph(
        tenant_id=registry.tenant_id,
        project_id=registry.project_id,
        artifacts=registry.artifacts,
        versions=registry.versions,
        traces=registry.trace_relationships,
        validations=registry.validations,
        findings=registry.findings,
        approvals=registry.approvals,
        evidence=registry.evidence_records,
    )
    return _rehash_registry(registry.model_copy(update={"graph": graph}))


def _rehash_registry(registry: R22ArtifactRegistry) -> R22ArtifactRegistry:
    return registry.model_copy(
        update={
            "registry_hash": specification_hash(
                registry.model_dump(mode="json", exclude={"registry_hash"})
            )
        }
    )


def _append_event(
    registry: R22ArtifactRegistry,
    event_type: str,
    subject: dict[str, str],
    payload: dict[str, Any],
    actor_id: str,
) -> R22ArtifactRegistry:
    event_payload = {
        "event_type": event_type,
        "tenant_id": registry.tenant_id,
        "project_id": registry.project_id,
        "subject": subject,
        "payload": payload,
        "sequence": len(registry.events) + 1,
    }
    event_hash = specification_hash(event_payload)
    event = R22ArtifactEvent(
        event_id=f"r22-event-{event_hash[:16]}",
        event_type=event_type,
        event_version=1,
        occurred_at=DETERMINISTIC_ARTIFACT_TIMESTAMP,
        tenant_id=registry.tenant_id,
        project_id=registry.project_id,
        correlation_id=f"r22-corr-{event_hash[:12]}",
        actor={"actor_type": "artifact_service", "actor_id": actor_id},
        subject=subject,
        payload=payload,
        integrity={"checksum": f"sha256:{event_hash}"},
    )
    return _rehash_registry(registry.model_copy(update={"events": registry.events + (event,)}))


def _downstream_artifact_versions(
    registry: R22ArtifactRegistry, source_object_id: str
) -> tuple[str, ...]:
    adjacency: dict[str, set[str]] = {}
    for trace in registry.trace_relationships:
        adjacency.setdefault(trace.source_id, set()).add(trace.target_id)
    for dependency in registry.dependencies:
        adjacency.setdefault(dependency.depends_on_version_id, set()).add(
            dependency.artifact_version_id
        )
    affected: set[str] = set()
    queue: deque[str] = deque([source_object_id])
    seen = {source_object_id}
    version_ids = {version.artifact_version_id for version in registry.versions}
    while queue:
        node = queue.popleft()
        for child in sorted(adjacency.get(node, set())):
            if child in seen:
                continue
            seen.add(child)
            if child in version_ids:
                affected.add(child)
            queue.append(child)
    return tuple(sorted(affected))


def _version_by_id(
    registry: R22ArtifactRegistry, artifact_version_id: str
) -> R22ArtifactVersion | None:
    return next(
        (item for item in registry.versions if item.artifact_version_id == artifact_version_id),
        None,
    )


def _artifact_by_id(registry: R22ArtifactRegistry, artifact_id: str) -> R22ArtifactRecord | None:
    return next((item for item in registry.artifacts if item.artifact_id == artifact_id), None)


def _provenance_by_id(
    registry: R22ArtifactRegistry, provenance_id: str
) -> R22ProvenanceRecord | None:
    return next(
        (item for item in registry.provenance_records if item.provenance_id == provenance_id), None
    )


def _class_for_artifact_type(artifact_type: str) -> str:
    lowered = artifact_type.lower()
    if any(token in lowered for token in ("test", "validation", "report")):
        return "validation"
    if any(token in lowered for token in ("approval", "decision", "policy")):
        return "governance"
    if any(token in lowered for token in ("release", "delivery", "package")):
        return "delivery"
    if any(token in lowered for token in ("code", "service", "implementation", "api", "openapi")):
        return "implementation"
    if any(token in lowered for token in ("architecture", "design")):
        return "design"
    return "definition"


def _diag(severity: str, category: str, code: str, message: str, path: str) -> R22Diagnostic:
    return R22Diagnostic(
        severity=severity, category=category, code=code, message=message, path=path
    )
