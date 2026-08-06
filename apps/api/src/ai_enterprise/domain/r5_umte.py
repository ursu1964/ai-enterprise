from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_enterprise.domain.aeir import (
    AeirObject,
    AeirObjectType,
    AeirProjectModel,
    AeirSnapshotStatus,
    LifecycleStatus,
    ProjectSnapshot,
)
from ai_enterprise.domain.specification.kernel import specification_hash


class UmteValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TransformationLayer(StrEnum):
    SEMANTIC_VALIDATION = "semantic_validation"
    NORMALIZATION = "normalization"
    DEPENDENCY_RESOLUTION = "dependency_resolution"
    OBJECT_EXPANSION = "object_expansion"
    ARTIFACT_SPECIFICATION = "artifact_specification"
    VERIFICATION = "verification"


class UmteArtifactKind(StrEnum):
    DATABASE_MODEL = "database_model"
    DATABASE_MIGRATION = "database_migration"
    DOMAIN_MODEL = "domain_model"
    SERVICE_DEFINITION = "service_definition"
    REST_API = "rest_api"
    GRAPHQL_API = "graphql_api"
    GRPC_API = "grpc_api"
    UI_SPECIFICATION = "ui_specification"
    WORKFLOW_STATE_MACHINE = "workflow_state_machine"
    SECURITY_PERMISSION_MODEL = "security_permission_model"
    EVENT_CONTRACT = "event_contract"
    INTEGRATION_SPECIFICATION = "integration_specification"
    TEST_SUITE = "test_suite"
    DOCUMENTATION = "documentation"
    DEPLOYMENT_DESCRIPTOR = "deployment_descriptor"
    OBSERVABILITY_CONFIGURATION = "observability_configuration"
    AI_IMPLEMENTATION_PROMPT = "ai_implementation_prompt"
    TRACEABILITY_REPORT = "traceability_report"
    COMPLIANCE_ARTIFACT = "compliance_artifact"


class UmteFindingSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFORMATION = "information"


class UmteVerificationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class UmteTemplateRef(UmteValue):
    template_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,119}$")
    template_version: str = Field(pattern=r"^[0-9]+\.[0-9]+$")
    target: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,79}$")
    renderer: Literal["deterministic-template", "ai-constrained-template"] = (
        "deterministic-template"
    )

    @property
    def ref(self) -> str:
        return f"{self.template_id}.v{self.template_version}"


class UmteRegistryRule(UmteValue):
    rule_id: str = Field(pattern=r"^UMTE\.[A-Z0-9_.]+$")
    rule_version: str = Field(pattern=r"^[0-9]+\.[0-9]+$")
    layer: TransformationLayer
    source_object_types: tuple[AeirObjectType, ...] = Field(min_length=1)
    output_artifact_kinds: tuple[UmteArtifactKind, ...] = Field(min_length=1)
    template_refs: tuple[UmteTemplateRef, ...] = Field(min_length=1)
    deterministic: bool = True

    @model_validator(mode="after")
    def validate_rule(self) -> UmteRegistryRule:
        if len(self.source_object_types) != len(set(self.source_object_types)):
            raise ValueError("UMTE rule source object types must be unique")
        if len(self.output_artifact_kinds) != len(set(self.output_artifact_kinds)):
            raise ValueError("UMTE rule output artifact kinds must be unique")
        if not self.deterministic:
            raise ValueError("UMTE registry rules must be deterministic")
        return self


class UmteArtifactProvenance(UmteValue):
    source_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshot_id: str = Field(pattern=r"^SNP-[0-9]{4}$")
    source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_object_id: str = Field(pattern=r"^[A-Z][A-Z0-9-]{2,63}$")
    registry_rule_id: str = Field(pattern=r"^UMTE\.[A-Z0-9_.]+$")
    registry_rule_version: str = Field(pattern=r"^[0-9]+\.[0-9]+$")
    template_ref: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,119}\.v[0-9]+\.[0-9]+$")
    transformation_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class UmteArtifactSpec(UmteValue):
    artifact_key: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,179}$")
    artifact_kind: UmteArtifactKind
    target: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,79}$")
    source_object_id: str = Field(pattern=r"^[A-Z][A-Z0-9-]{2,63}$")
    source_object_type: AeirObjectType
    canonical_name: str = Field(min_length=1, max_length=300)
    depends_on_object_ids: tuple[str, ...] = ()
    specification_document: dict[str, object]
    provenance: UmteArtifactProvenance
    artifact_spec_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_artifact_spec(self) -> UmteArtifactSpec:
        if tuple(sorted(set(self.depends_on_object_ids))) != self.depends_on_object_ids:
            raise ValueError("UMTE artifact dependencies must be unique and sorted")
        if self.source_object_id in self.depends_on_object_ids:
            raise ValueError("UMTE artifact cannot depend on its own source object")
        if self.artifact_spec_hash != _artifact_spec_hash(self):
            raise ValueError("UMTE artifact spec hash does not match canonical content")
        return self


class UmteGeneratedArtifact(UmteValue):
    artifact_key: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,179}$")
    artifact_kind: UmteArtifactKind
    target: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,79}$")
    media_type: str = Field(min_length=1, max_length=120)
    source_artifact_spec_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_document: dict[str, object]
    generated_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_generated_artifact(self) -> UmteGeneratedArtifact:
        if self.content_document.get("artifact_key") != self.artifact_key:
            raise ValueError("UMTE generated artifact content must identify its artifact key")
        if self.content_document.get("source_artifact_spec_hash") != self.source_artifact_spec_hash:
            raise ValueError("UMTE generated artifact content must identify its source spec")
        if self.generated_hash != _generated_artifact_hash(self):
            raise ValueError("UMTE generated artifact hash does not match canonical content")
        return self


class UmteTransformationPlan(UmteValue):
    schema_version: Literal["umte-transformation-plan-0.1"] = "umte-transformation-plan-0.1"
    registry_version: str = Field(pattern=r"^[0-9]+\.[0-9]+$")
    template_pack_version: str = Field(pattern=r"^[0-9]+\.[0-9]+$")
    source_model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshot_id: str = Field(pattern=r"^SNP-[0-9]{4}$")
    source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_stack: tuple[str, ...] = Field(min_length=1)
    layers: tuple[TransformationLayer, ...] = Field(min_length=6)
    registry_rules: tuple[UmteRegistryRule, ...] = Field(min_length=1)
    plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_plan(self) -> UmteTransformationPlan:
        if self.layers != tuple(TransformationLayer):
            raise ValueError("UMTE transformation plan must include all layers in order")
        rule_ids = [rule.rule_id for rule in self.registry_rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("UMTE transformation plan rule identifiers must be unique")
        if tuple(sorted(set(self.target_stack))) != self.target_stack:
            raise ValueError("UMTE target stack must be unique and sorted")
        if self.plan_hash != _plan_hash(self):
            raise ValueError("UMTE transformation plan hash does not match canonical content")
        return self


class UmteVerificationFinding(UmteValue):
    finding_id: str = Field(pattern=r"^UMTE-FIND-[0-9]{3}$")
    rule_id: str = Field(pattern=r"^UMTE\.VERIFY\.[A-Z0-9_.]+$")
    layer: TransformationLayer
    severity: UmteFindingSeverity
    message: str = Field(min_length=1)
    artifact_keys: tuple[str, ...] = ()
    object_ids: tuple[str, ...] = ()
    blocking: bool
    suggested_action: str = Field(min_length=1)


class UmteVerificationReport(UmteValue):
    schema_version: Literal["umte-verification-report-0.1"] = "umte-verification-report-0.1"
    source_model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    transformation_plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_set_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: UmteVerificationStatus
    findings: tuple[UmteVerificationFinding, ...]
    report_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_report(self) -> UmteVerificationReport:
        expected = (
            UmteVerificationStatus.FAILED
            if any(finding.blocking for finding in self.findings)
            else UmteVerificationStatus.PASSED
        )
        if self.status is not expected:
            raise ValueError("UMTE verification status must match blocking findings")
        if self.report_hash != _verification_report_hash(self):
            raise ValueError("UMTE verification report hash does not match canonical content")
        return self


class UmteTransformationResult(UmteValue):
    schema_version: Literal["umte-transformation-result-0.1"] = "umte-transformation-result-0.1"
    plan: UmteTransformationPlan
    artifact_specs: tuple[UmteArtifactSpec, ...]
    generated_artifacts: tuple[UmteGeneratedArtifact, ...]
    verification_report: UmteVerificationReport
    result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_result(self) -> UmteTransformationResult:
        keys = [item.artifact_key for item in self.artifact_specs]
        if len(keys) != len(set(keys)):
            raise ValueError("UMTE artifact keys must be unique")
        if tuple(sorted(keys)) != tuple(keys):
            raise ValueError("UMTE artifacts must be sorted by key")
        generated_keys = [item.artifact_key for item in self.generated_artifacts]
        if tuple(generated_keys) != tuple(keys):
            raise ValueError("UMTE generated artifacts must match artifact specs in order")
        spec_hashes = {item.artifact_key: item.artifact_spec_hash for item in self.artifact_specs}
        for generated in self.generated_artifacts:
            if generated.source_artifact_spec_hash != spec_hashes[generated.artifact_key]:
                raise ValueError("UMTE generated artifact does not match source spec")
        if self.verification_report.transformation_plan_hash != self.plan.plan_hash:
            raise ValueError("UMTE verification report does not belong to transformation plan")
        if self.verification_report.artifact_set_hash != _artifact_set_hash(self.artifact_specs):
            raise ValueError("UMTE verification report does not match artifact set")
        if self.result_hash != _result_hash(self):
            raise ValueError("UMTE transformation result hash does not match canonical content")
        return self


class UmteExportBundleEntry(UmteValue):
    artifact_key: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,179}$")
    artifact_kind: UmteArtifactKind
    target: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,79}$")
    media_type: str = Field(min_length=1, max_length=120)
    source_artifact_spec_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_address: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class UmteExportBundle(UmteValue):
    schema_version: Literal["umte-export-bundle-0.1"] = "umte-export-bundle-0.1"
    transformation_result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshot_id: str = Field(pattern=r"^SNP-[0-9]{4}$")
    source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    registry_version: str = Field(pattern=r"^[0-9]+\.[0-9]+$")
    template_pack_version: str = Field(pattern=r"^[0-9]+\.[0-9]+$")
    artifact_count: int = Field(ge=1)
    entries: tuple[UmteExportBundleEntry, ...] = Field(min_length=1)
    verification_report_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    bundle_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_bundle(self) -> UmteExportBundle:
        keys = [entry.artifact_key for entry in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("UMTE export bundle artifact keys must be unique")
        if tuple(sorted(keys)) != tuple(keys):
            raise ValueError("UMTE export bundle entries must be sorted by artifact key")
        if self.artifact_count != len(self.entries):
            raise ValueError("UMTE export bundle artifact count must match entries")
        if self.bundle_hash != _export_bundle_hash(self):
            raise ValueError("UMTE export bundle hash does not match canonical content")
        return self


def compile_umte_transformation(
    model: AeirProjectModel,
    snapshot: ProjectSnapshot | None = None,
    *,
    target_stack: tuple[str, ...] = ("postgresql", "python", "react"),
    registry_version: str = "1.0",
    template_pack_version: str = "1.0",
) -> UmteTransformationResult:
    snapshot_id = "SNP-0000" if snapshot is None else snapshot.snapshot_id
    snapshot_sha256 = model.model_sha256 if snapshot is None else snapshot.snapshot_sha256
    if snapshot is not None and snapshot.source_model_sha256 != model.model_sha256:
        raise ValueError("UMTE snapshot does not belong to AEIR model")

    rules = default_registry_rules(template_pack_version=template_pack_version)
    plan = _plan(
        model,
        snapshot_id=snapshot_id,
        snapshot_sha256=snapshot_sha256,
        target_stack=target_stack,
        registry_version=registry_version,
        template_pack_version=template_pack_version,
        rules=rules,
    )
    artifact_specs = tuple(
        sorted(
            _artifact_specs(model, snapshot_id, snapshot_sha256, rules),
            key=lambda item: item.artifact_key,
        )
    )
    generated_artifacts = tuple(_generated_artifact(spec) for spec in artifact_specs)
    verification = verify_umte_transformation(model, plan, artifact_specs)
    provisional = UmteTransformationResult.model_construct(
        schema_version="umte-transformation-result-0.1",
        plan=plan,
        artifact_specs=artifact_specs,
        generated_artifacts=generated_artifacts,
        verification_report=verification,
        result_hash="0" * 64,
    )
    return UmteTransformationResult(
        plan=plan,
        artifact_specs=artifact_specs,
        generated_artifacts=generated_artifacts,
        verification_report=verification,
        result_hash=_result_hash(provisional),
    )


def compile_umte_export_bundle(result: UmteTransformationResult) -> UmteExportBundle:
    if result.verification_report.status is not UmteVerificationStatus.PASSED:
        raise ValueError("UMTE export bundle requires a passing verification report")
    entries = tuple(
        UmteExportBundleEntry(
            artifact_key=artifact.artifact_key,
            artifact_kind=artifact.artifact_kind,
            target=artifact.target,
            media_type=artifact.media_type,
            source_artifact_spec_hash=artifact.source_artifact_spec_hash,
            generated_hash=artifact.generated_hash,
            content_address=f"sha256:{artifact.generated_hash}",
        )
        for artifact in result.generated_artifacts
    )
    provisional = UmteExportBundle.model_construct(
        schema_version="umte-export-bundle-0.1",
        transformation_result_hash=result.result_hash,
        source_model_sha256=result.plan.source_model_sha256,
        source_snapshot_id=result.plan.source_snapshot_id,
        source_snapshot_sha256=result.plan.source_snapshot_sha256,
        registry_version=result.plan.registry_version,
        template_pack_version=result.plan.template_pack_version,
        artifact_count=len(entries),
        entries=entries,
        verification_report_hash=result.verification_report.report_hash,
        bundle_hash="0" * 64,
    )
    return UmteExportBundle(
        transformation_result_hash=result.result_hash,
        source_model_sha256=result.plan.source_model_sha256,
        source_snapshot_id=result.plan.source_snapshot_id,
        source_snapshot_sha256=result.plan.source_snapshot_sha256,
        registry_version=result.plan.registry_version,
        template_pack_version=result.plan.template_pack_version,
        artifact_count=len(entries),
        entries=entries,
        verification_report_hash=result.verification_report.report_hash,
        bundle_hash=_export_bundle_hash(provisional),
    )


def default_registry_rules(
    *, template_pack_version: str = "1.0"
) -> tuple[UmteRegistryRule, ...]:
    def template(kind: UmteArtifactKind, target: str) -> UmteTemplateRef:
        return UmteTemplateRef(
            template_id=f"umte.{kind.value}.{target}",
            template_version=template_pack_version,
            target=target,
        )

    specs: tuple[
        tuple[str, tuple[AeirObjectType, ...], tuple[tuple[UmteArtifactKind, str], ...]],
        ...,
    ] = (
        (
            "UMTE.PROJECT.DELIVERY_SURFACE.001",
            (AeirObjectType.PROJECT,),
            (
                (UmteArtifactKind.DOCUMENTATION, "markdown"),
                (UmteArtifactKind.TRACEABILITY_REPORT, "json"),
                (UmteArtifactKind.COMPLIANCE_ARTIFACT, "json"),
            ),
        ),
        (
            "UMTE.BUSINESS_CONTEXT.DOCUMENTATION_SURFACE.001",
            (
                AeirObjectType.INTENT,
                AeirObjectType.OUTCOME,
                AeirObjectType.STAKEHOLDER,
            ),
            (
                (UmteArtifactKind.DOCUMENTATION, "markdown"),
                (UmteArtifactKind.TRACEABILITY_REPORT, "json"),
            ),
        ),
        (
            "UMTE.CAPABILITY.SERVICE_SURFACE.001",
            (AeirObjectType.CAPABILITY,),
            (
                (UmteArtifactKind.DOMAIN_MODEL, "python"),
                (UmteArtifactKind.SERVICE_DEFINITION, "python"),
                (UmteArtifactKind.REST_API, "openapi"),
                (UmteArtifactKind.TEST_SUITE, "pytest"),
                (UmteArtifactKind.DOCUMENTATION, "markdown"),
            ),
        ),
        (
            "UMTE.PROCESS.WORKFLOW_SURFACE.001",
            (AeirObjectType.PROCESS,),
            (
                (UmteArtifactKind.WORKFLOW_STATE_MACHINE, "json"),
                (UmteArtifactKind.REST_API, "openapi"),
                (UmteArtifactKind.UI_SPECIFICATION, "react"),
                (UmteArtifactKind.TEST_SUITE, "pytest"),
                (UmteArtifactKind.OBSERVABILITY_CONFIGURATION, "prometheus"),
            ),
        ),
        (
            "UMTE.REQUIREMENT.TEST_SURFACE.001",
            (AeirObjectType.REQUIREMENT, AeirObjectType.RULE),
            (
                (UmteArtifactKind.TEST_SUITE, "pytest"),
                (UmteArtifactKind.REST_API, "openapi"),
                (UmteArtifactKind.UI_SPECIFICATION, "react"),
                (UmteArtifactKind.AI_IMPLEMENTATION_PROMPT, "prompt"),
                (UmteArtifactKind.DOCUMENTATION, "markdown"),
            ),
        ),
        (
            "UMTE.ENTITY.DATA_SURFACE.001",
            (AeirObjectType.ENTITY,),
            (
                (UmteArtifactKind.DATABASE_MODEL, "postgresql"),
                (UmteArtifactKind.DATABASE_MIGRATION, "alembic"),
                (UmteArtifactKind.DOMAIN_MODEL, "python"),
                (UmteArtifactKind.REST_API, "openapi"),
                (UmteArtifactKind.UI_SPECIFICATION, "react"),
                (UmteArtifactKind.SECURITY_PERMISSION_MODEL, "json"),
                (UmteArtifactKind.EVENT_CONTRACT, "json"),
                (UmteArtifactKind.TEST_SUITE, "pytest"),
                (UmteArtifactKind.DOCUMENTATION, "markdown"),
            ),
        ),
        (
            "UMTE.INTEGRATION.CONTRACT_SURFACE.001",
            (AeirObjectType.INTEGRATION,),
            (
                (UmteArtifactKind.INTEGRATION_SPECIFICATION, "openapi"),
                (UmteArtifactKind.EVENT_CONTRACT, "json"),
                (UmteArtifactKind.TEST_SUITE, "pytest"),
                (UmteArtifactKind.DOCUMENTATION, "markdown"),
            ),
        ),
        (
            "UMTE.CONSTRAINT.GOVERNANCE_SURFACE.001",
            (AeirObjectType.CONSTRAINT, AeirObjectType.RISK, AeirObjectType.DECISION),
            (
                (UmteArtifactKind.SECURITY_PERMISSION_MODEL, "json"),
                (UmteArtifactKind.COMPLIANCE_ARTIFACT, "json"),
                (UmteArtifactKind.TEST_SUITE, "pytest"),
                (UmteArtifactKind.DEPLOYMENT_DESCRIPTOR, "yaml"),
                (UmteArtifactKind.DOCUMENTATION, "markdown"),
            ),
        ),
    )
    return tuple(
        UmteRegistryRule(
            rule_id=rule_id,
            rule_version="1.0",
            layer=TransformationLayer.OBJECT_EXPANSION,
            source_object_types=source_types,
            output_artifact_kinds=tuple(kind for kind, _ in outputs),
            template_refs=tuple(template(kind, target) for kind, target in outputs),
        )
        for rule_id, source_types, outputs in specs
    )


def verify_umte_transformation(
    model: AeirProjectModel,
    plan: UmteTransformationPlan,
    artifact_specs: tuple[UmteArtifactSpec, ...],
) -> UmteVerificationReport:
    findings: list[UmteVerificationFinding] = []
    known_object_ids = {item.id for item in model.objects}
    generatable_object_ids = {
        item.id for item in model.objects if _is_generatable(item)
    }
    artifact_source_ids = {item.source_object_id for item in artifact_specs}
    rule_ids = {rule.rule_id for rule in plan.registry_rules}

    if missing := tuple(sorted(generatable_object_ids - artifact_source_ids)):
        findings.append(
            _finding(
                len(findings) + 1,
                "UMTE.VERIFY.COVERAGE.ACTIVE_OBJECTS",
                TransformationLayer.VERIFICATION,
                UmteFindingSeverity.ERROR,
                "Canonical non-archived objects must produce at least one UMTE artifact spec.",
                (),
                missing,
                True,
                "Add registry coverage for each active canonical object type.",
            )
        )
    for artifact in artifact_specs:
        if artifact.source_object_id not in known_object_ids:
            findings.append(
                _finding(
                    len(findings) + 1,
                    "UMTE.VERIFY.PROVENANCE.KNOWN_SOURCE",
                    TransformationLayer.VERIFICATION,
                    UmteFindingSeverity.ERROR,
                    "Artifact provenance references an unknown source object.",
                    (artifact.artifact_key,),
                    (artifact.source_object_id,),
                    True,
                    "Regenerate the artifact from the current knowledge graph.",
                )
            )
        if artifact.provenance.registry_rule_id not in rule_ids:
            findings.append(
                _finding(
                    len(findings) + 1,
                    "UMTE.VERIFY.REGISTRY.RULE_BOUND",
                    TransformationLayer.VERIFICATION,
                    UmteFindingSeverity.ERROR,
                    "Artifact was not produced by a registered UMTE rule.",
                    (artifact.artifact_key,),
                    (artifact.source_object_id,),
                    True,
                    "Bind every generated artifact spec to a versioned registry rule.",
                )
            )
        unknown_dependencies = tuple(
            dep for dep in artifact.depends_on_object_ids if dep not in known_object_ids
        )
        if unknown_dependencies:
            findings.append(
                _finding(
                    len(findings) + 1,
                    "UMTE.VERIFY.DEPENDENCY.KNOWN_OBJECTS",
                    TransformationLayer.VERIFICATION,
                    UmteFindingSeverity.ERROR,
                    "Artifact dependency resolution references unknown objects.",
                    (artifact.artifact_key,),
                    unknown_dependencies,
                    True,
                    "Resolve dependencies only against the approved knowledge graph.",
                )
            )
    if not artifact_specs:
        findings.append(
            _finding(
                len(findings) + 1,
                "UMTE.VERIFY.ARTIFACTS.NON_EMPTY",
                TransformationLayer.VERIFICATION,
                UmteFindingSeverity.ERROR,
                "UMTE transformation produced no artifact specifications.",
                (),
                (),
                True,
                "Add manifest objects covered by the UMTE registry.",
            )
        )
    artifact_set_hash = _artifact_set_hash(artifact_specs)
    provisional = UmteVerificationReport.model_construct(
        schema_version="umte-verification-report-0.1",
        source_model_sha256=model.model_sha256,
        transformation_plan_hash=plan.plan_hash,
        artifact_set_hash=artifact_set_hash,
        status=(
            UmteVerificationStatus.FAILED
            if any(finding.blocking for finding in findings)
            else UmteVerificationStatus.PASSED
        ),
        findings=tuple(findings),
        report_hash="0" * 64,
    )
    return UmteVerificationReport(
        source_model_sha256=model.model_sha256,
        transformation_plan_hash=plan.plan_hash,
        artifact_set_hash=artifact_set_hash,
        status=provisional.status,
        findings=tuple(findings),
        report_hash=_verification_report_hash(provisional),
    )


def affected_umte_artifact_keys(
    previous_model: AeirProjectModel,
    current_model: AeirProjectModel,
    result: UmteTransformationResult,
) -> tuple[str, ...]:
    previous = {item.id: _source_hash(item) for item in previous_model.objects}
    current = {item.id: _source_hash(item) for item in current_model.objects}
    changed = {
        object_id
        for object_id in set(previous) | set(current)
        if previous.get(object_id) != current.get(object_id)
    }
    return tuple(
        spec.artifact_key
        for spec in result.artifact_specs
        if spec.source_object_id in changed
        or any(dep in changed for dep in spec.depends_on_object_ids)
    )


def require_approved_snapshot(snapshot: ProjectSnapshot | None) -> None:
    if snapshot is None or str(snapshot.status) != AeirSnapshotStatus.APPROVED.value:
        raise ValueError("UMTE requires an approved AEIR snapshot before production generation")


def _plan(
    model: AeirProjectModel,
    *,
    snapshot_id: str,
    snapshot_sha256: str,
    target_stack: tuple[str, ...],
    registry_version: str,
    template_pack_version: str,
    rules: tuple[UmteRegistryRule, ...],
) -> UmteTransformationPlan:
    normalized_stack = tuple(sorted(set(target_stack)))
    provisional = UmteTransformationPlan.model_construct(
        schema_version="umte-transformation-plan-0.1",
        registry_version=registry_version,
        template_pack_version=template_pack_version,
        source_model_sha256=model.model_sha256,
        source_snapshot_id=snapshot_id,
        source_snapshot_sha256=snapshot_sha256,
        target_stack=normalized_stack,
        layers=tuple(TransformationLayer),
        registry_rules=rules,
        plan_hash="0" * 64,
    )
    return UmteTransformationPlan(
        registry_version=registry_version,
        template_pack_version=template_pack_version,
        source_model_sha256=model.model_sha256,
        source_snapshot_id=snapshot_id,
        source_snapshot_sha256=snapshot_sha256,
        target_stack=normalized_stack,
        layers=tuple(TransformationLayer),
        registry_rules=rules,
        plan_hash=_plan_hash(provisional),
    )


def _artifact_specs(
    model: AeirProjectModel,
    snapshot_id: str,
    snapshot_sha256: str,
    rules: tuple[UmteRegistryRule, ...],
) -> tuple[UmteArtifactSpec, ...]:
    specs: list[UmteArtifactSpec] = []
    for source_object in sorted(model.objects, key=lambda item: item.id):
        if not _is_generatable(source_object):
            continue
        dependencies = _object_dependencies(model, source_object.id)
        for rule in rules:
            if source_object.type not in rule.source_object_types:
                continue
            templates_by_kind = {
                kind: template
                for kind, template in zip(
                    rule.output_artifact_kinds, rule.template_refs, strict=True
                )
            }
            for artifact_kind in rule.output_artifact_kinds:
                template = templates_by_kind[artifact_kind]
                specs.append(
                    _artifact_spec(
                        model,
                        source_object,
                        snapshot_id,
                        snapshot_sha256,
                        dependencies,
                        rule,
                        artifact_kind,
                        template,
                    )
                )
    return tuple(specs)


def _artifact_spec(
    model: AeirProjectModel,
    source_object: AeirObject,
    snapshot_id: str,
    snapshot_sha256: str,
    dependencies: tuple[str, ...],
    rule: UmteRegistryRule,
    artifact_kind: UmteArtifactKind,
    template: UmteTemplateRef,
) -> UmteArtifactSpec:
    artifact_key = (
        f"{_slug(source_object.type.value)}."
        f"{_slug(source_object.id)}."
        f"{_slug(artifact_kind.value)}."
        f"{template.target}"
    )
    spec_document: dict[str, object] = {
        "schema_version": "umte-artifact-spec-0.1",
        "artifact_kind": artifact_kind.value,
        "target": template.target,
        "source_object": {
            "id": source_object.id,
            "type": source_object.type.value,
            "name": source_object.name,
            "description": source_object.description,
            "attributes": source_object.attributes,
        },
        "dependencies": list(dependencies),
        "derived_operations": _derived_operations(artifact_kind),
        "ai_boundary": "transform_only_no_business_invention",
    }
    transform_hash = specification_hash(
        {
            "source_model_sha256": model.model_sha256,
            "source_object_id": source_object.id,
            "source_object_sha256": _source_hash(source_object),
            "dependencies": dependencies,
            "registry_rule_id": rule.rule_id,
            "registry_rule_version": rule.rule_version,
            "template_ref": template.ref,
            "artifact_kind": artifact_kind.value,
            "target": template.target,
        }
    )
    provenance = UmteArtifactProvenance(
        source_manifest_sha256=model.source_manifest_sha256,
        source_model_sha256=model.model_sha256,
        source_snapshot_id=snapshot_id,
        source_snapshot_sha256=snapshot_sha256,
        source_object_id=source_object.id,
        registry_rule_id=rule.rule_id,
        registry_rule_version=rule.rule_version,
        template_ref=template.ref,
        transformation_hash=transform_hash,
    )
    provisional = UmteArtifactSpec.model_construct(
        artifact_key=artifact_key,
        artifact_kind=artifact_kind,
        target=template.target,
        source_object_id=source_object.id,
        source_object_type=source_object.type,
        canonical_name=source_object.name,
        depends_on_object_ids=dependencies,
        specification_document=spec_document,
        provenance=provenance,
        artifact_spec_hash="0" * 64,
    )
    return UmteArtifactSpec(
        artifact_key=artifact_key,
        artifact_kind=artifact_kind,
        target=template.target,
        source_object_id=source_object.id,
        source_object_type=source_object.type,
        canonical_name=source_object.name,
        depends_on_object_ids=dependencies,
        specification_document=spec_document,
        provenance=provenance,
        artifact_spec_hash=_artifact_spec_hash(provisional),
    )


def _object_dependencies(model: AeirProjectModel, source_object_id: str) -> tuple[str, ...]:
    dependencies: set[str] = set()
    for relationship in model.relationships:
        if relationship.source_object_id == source_object_id:
            dependencies.add(relationship.target_object_id)
        if relationship.target_object_id == source_object_id:
            dependencies.add(relationship.source_object_id)
    dependencies.discard(source_object_id)
    return tuple(sorted(dependencies))


def _is_generatable(source_object: AeirObject) -> bool:
    return source_object.lifecycle_status not in {
        LifecycleStatus.ARCHIVED,
        LifecycleStatus.DEPRECATED,
    }


def _derived_operations(kind: UmteArtifactKind) -> tuple[str, ...]:
    operations: dict[UmteArtifactKind, tuple[str, ...]] = {
        UmteArtifactKind.DATABASE_MODEL: ("table", "indexes", "constraints", "relationships"),
        UmteArtifactKind.DATABASE_MIGRATION: ("create", "alter", "rollback"),
        UmteArtifactKind.DOMAIN_MODEL: ("dto", "validation", "serialization"),
        UmteArtifactKind.SERVICE_DEFINITION: ("create", "read", "update", "delete", "search"),
        UmteArtifactKind.REST_API: ("get", "post", "put", "patch", "delete", "search", "export"),
        UmteArtifactKind.GRAPHQL_API: ("query", "mutation", "subscription"),
        UmteArtifactKind.GRPC_API: ("service", "message", "method"),
        UmteArtifactKind.UI_SPECIFICATION: (
            "list",
            "details",
            "create",
            "edit",
            "delete",
            "search",
            "accessibility",
        ),
        UmteArtifactKind.WORKFLOW_STATE_MACHINE: ("states", "transitions", "guards", "events"),
        UmteArtifactKind.SECURITY_PERMISSION_MODEL: (
            "api_access",
            "ui_visibility",
            "workflow_rights",
            "audit_scope",
        ),
        UmteArtifactKind.EVENT_CONTRACT: ("created", "updated", "deleted", "state_changed"),
        UmteArtifactKind.INTEGRATION_SPECIFICATION: ("request", "response", "errors", "timeouts"),
        UmteArtifactKind.TEST_SUITE: ("unit", "integration", "api", "workflow", "regression"),
        UmteArtifactKind.DOCUMENTATION: ("business", "technical", "relationships", "examples"),
        UmteArtifactKind.DEPLOYMENT_DESCRIPTOR: ("environment", "configuration", "dependencies"),
        UmteArtifactKind.OBSERVABILITY_CONFIGURATION: ("metrics", "logs", "alerts"),
        UmteArtifactKind.AI_IMPLEMENTATION_PROMPT: ("system", "task", "schema", "constraints"),
        UmteArtifactKind.TRACEABILITY_REPORT: ("source", "rule", "template", "artifact"),
        UmteArtifactKind.COMPLIANCE_ARTIFACT: ("policy", "evidence", "control"),
    }
    return operations[kind]


def _generated_artifact(spec: UmteArtifactSpec) -> UmteGeneratedArtifact:
    media_type = _media_type(spec.target)
    body = {
        "title": f"{spec.canonical_name} — {spec.artifact_kind.value.replace('_', ' ')}",
        "source_object_id": spec.source_object_id,
        "source_object_type": spec.source_object_type.value,
        "target": spec.target,
        "operations": list(spec.specification_document["derived_operations"]),
        "dependencies": list(spec.depends_on_object_ids),
        "provenance": spec.provenance.model_dump(mode="json"),
    }
    content_document: dict[str, object] = {
        "schema_version": "umte-generated-artifact-0.1",
        "artifact_key": spec.artifact_key,
        "artifact_kind": spec.artifact_kind.value,
        "target": spec.target,
        "media_type": media_type,
        "source_artifact_spec_hash": spec.artifact_spec_hash,
        "body": body,
    }
    provisional = UmteGeneratedArtifact.model_construct(
        artifact_key=spec.artifact_key,
        artifact_kind=spec.artifact_kind,
        target=spec.target,
        media_type=media_type,
        source_artifact_spec_hash=spec.artifact_spec_hash,
        content_document=content_document,
        generated_hash="0" * 64,
    )
    return UmteGeneratedArtifact(
        artifact_key=spec.artifact_key,
        artifact_kind=spec.artifact_kind,
        target=spec.target,
        media_type=media_type,
        source_artifact_spec_hash=spec.artifact_spec_hash,
        content_document=content_document,
        generated_hash=_generated_artifact_hash(provisional),
    )


def _media_type(target: str) -> str:
    return {
        "alembic": "application/vnd.ai-enterprise.alembic+json",
        "json": "application/json",
        "markdown": "text/markdown",
        "openapi": "application/vnd.oai.openapi+json",
        "postgresql": "application/sql",
        "prometheus": "application/vnd.prometheus.rules+json",
        "prompt": "application/vnd.ai-enterprise.prompt+json",
        "pytest": "text/x-python",
        "python": "text/x-python",
        "react": "application/vnd.ai-enterprise.react-spec+json",
        "yaml": "application/yaml",
    }.get(target, "application/json")


def _finding(
    index: int,
    rule_id: str,
    layer: TransformationLayer,
    severity: UmteFindingSeverity,
    message: str,
    artifact_keys: tuple[str, ...],
    object_ids: tuple[str, ...],
    blocking: bool,
    suggested_action: str,
) -> UmteVerificationFinding:
    return UmteVerificationFinding(
        finding_id=f"UMTE-FIND-{index:03d}",
        rule_id=rule_id,
        layer=layer,
        severity=severity,
        message=message,
        artifact_keys=tuple(sorted(set(artifact_keys))),
        object_ids=tuple(sorted(set(object_ids))),
        blocking=blocking,
        suggested_action=suggested_action,
    )


def _slug(value: str) -> str:
    return (
        value.lower()
        .replace("_", "-")
        .replace(" ", "-")
        .replace("/", "-")
    )


def _source_hash(source_object: AeirObject) -> str:
    return specification_hash(source_object.model_dump(mode="json"))


def _artifact_spec_hash(spec: UmteArtifactSpec) -> str:
    return specification_hash(spec.model_dump(mode="json", exclude={"artifact_spec_hash"}))


def _artifact_set_hash(specs: tuple[UmteArtifactSpec, ...]) -> str:
    return specification_hash([spec.model_dump(mode="json") for spec in specs])


def _generated_artifact_hash(artifact: UmteGeneratedArtifact) -> str:
    return specification_hash(artifact.model_dump(mode="json", exclude={"generated_hash"}))


def _plan_hash(plan: UmteTransformationPlan) -> str:
    return specification_hash(plan.model_dump(mode="json", exclude={"plan_hash"}))


def _verification_report_hash(report: UmteVerificationReport) -> str:
    return specification_hash(report.model_dump(mode="json", exclude={"report_hash"}))


def _result_hash(result: UmteTransformationResult) -> str:
    return specification_hash(result.model_dump(mode="json", exclude={"result_hash"}))


def _export_bundle_hash(bundle: UmteExportBundle) -> str:
    return specification_hash(bundle.model_dump(mode="json", exclude={"bundle_hash"}))
