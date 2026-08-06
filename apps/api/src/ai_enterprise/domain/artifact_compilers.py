from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_enterprise.domain.aeir import (
    AeirObject,
    AeirObjectType,
    AeirProjectModel,
    AeirSnapshotStatus,
    AeirStatus,
    ProjectSnapshot,
)
from ai_enterprise.domain.specification.kernel import specification_hash


class CompilerValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ArtifactType(StrEnum):
    EXECUTIVE_BRIEF = "executive_project_brief"
    SOFTWARE_REQUIREMENTS = "software_requirements_specification"
    DOMAIN_DATA_MODEL = "domain_and_data_model"
    SOLUTION_ARCHITECTURE = "solution_architecture_blueprint"
    DELIVERY_BACKLOG = "delivery_backlog"


class ArtifactCompilationStatus(StrEnum):
    DRAFT = "draft"
    APPROVED_SNAPSHOT = "approved_snapshot"


class ArtifactValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFORMATION = "information"


class ArtifactContract(CompilerValue):
    schema_version: Literal["artifact-contract-0.1"] = "artifact-contract-0.1"
    compiler_id: str = Field(pattern=r"^[a-z][a-z0-9-]{2,119}$")
    compiler_version: Literal["0.1"] = "0.1"
    artifact_type: ArtifactType
    accepted_object_types: tuple[AeirObjectType, ...] = Field(min_length=1)
    required_snapshot_status: AeirSnapshotStatus = AeirSnapshotStatus.APPROVED
    output_formats: tuple[Literal["markdown"], ...] = ("markdown",)
    traceability_required: bool = True
    required_section_keys: tuple[str, ...] = Field(min_length=1)
    contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_contract(self) -> ArtifactContract:
        if len(self.accepted_object_types) != len(set(self.accepted_object_types)):
            raise ValueError("artifact contract object types must be unique")
        if len(self.required_section_keys) != len(set(self.required_section_keys)):
            raise ValueError("artifact contract section keys must be unique")
        if self.contract_sha256 != _contract_hash(self):
            raise ValueError("artifact contract hash does not match canonical content")
        return self


class ArtifactSection(CompilerValue):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    title: str = Field(min_length=1, max_length=200)
    entries: tuple[str, ...] = Field(min_length=1)


class CompiledArtifact(CompilerValue):
    schema_version: Literal["artifact-compiler-0.1"] = "artifact-compiler-0.1"
    artifact_type: ArtifactType
    compiler_id: str = Field(pattern=r"^[a-z][a-z0-9-]{2,119}$")
    compiler_version: Literal["0.1"] = "0.1"
    contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    title: str = Field(min_length=1, max_length=300)
    source_model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshot_id: str = Field(pattern=r"^SNP-[0-9]{4}$")
    source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    compilation_status: ArtifactCompilationStatus
    sections: tuple[ArtifactSection, ...] = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_identity(self) -> CompiledArtifact:
        keys = [section.key for section in self.sections]
        if len(keys) != len(set(keys)):
            raise ValueError("compiled artifact section keys must be unique")
        expected_content = _content_hash(self.title, self.sections)
        if self.content_sha256 != expected_content:
            raise ValueError("compiled artifact content hash does not match sections")
        if self.artifact_sha256 != _artifact_hash(
            self.artifact_type,
            self.compiler_id,
            self.compiler_version,
            self.contract_sha256,
            self.title,
            self.source_model_sha256,
            self.source_snapshot_id,
            self.source_snapshot_sha256,
            self.compilation_status,
            self.sections,
            self.content_sha256,
        ):
            raise ValueError("compiled artifact hash does not match canonical content")
        return self


class ArtifactBundle(CompilerValue):
    schema_version: Literal["artifact-bundle-0.1"] = "artifact-bundle-0.1"
    source_model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshot_id: str = Field(pattern=r"^SNP-[0-9]{4}$")
    source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    compilation_status: ArtifactCompilationStatus
    contracts: tuple[ArtifactContract, ...]
    artifacts: tuple[CompiledArtifact, ...]
    bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_bundle(self) -> ArtifactBundle:
        expected_types = tuple(ArtifactType)
        actual_types = tuple(artifact.artifact_type for artifact in self.artifacts)
        if actual_types != expected_types:
            raise ValueError("artifact bundle must contain the exact five outputs in order")
        contract_types = tuple(contract.artifact_type for contract in self.contracts)
        if contract_types != expected_types:
            raise ValueError("artifact bundle must contain one contract for each output")
        contracts_by_type = {contract.artifact_type: contract for contract in self.contracts}
        for artifact in self.artifacts:
            if artifact.source_model_sha256 != self.source_model_sha256:
                raise ValueError("artifact bundle contains an artifact from another AEIR model")
            if (
                artifact.source_snapshot_id != self.source_snapshot_id
                or artifact.source_snapshot_sha256 != self.source_snapshot_sha256
                or artifact.compilation_status is not self.compilation_status
            ):
                raise ValueError("artifact bundle contains an artifact from another snapshot")
            if (
                artifact.contract_sha256
                != contracts_by_type[artifact.artifact_type].contract_sha256
            ):
                raise ValueError("artifact bundle contains an artifact with the wrong contract")
        if self.bundle_sha256 != _bundle_hash(
            self.source_model_sha256,
            self.source_snapshot_id,
            self.source_snapshot_sha256,
            self.compilation_status,
            self.contracts,
            self.artifacts,
        ):
            raise ValueError("artifact bundle hash does not match canonical artifacts")
        return self


class ArtifactValidationFinding(CompilerValue):
    id: str = Field(pattern=r"^ART-VAL-[0-9]{3}$")
    rule_id: str = Field(pattern=r"^ART\.[A-Z0-9_.]+$")
    severity: ArtifactValidationSeverity
    message: str = Field(min_length=1)
    artifact_types: tuple[ArtifactType, ...] = ()
    object_refs: tuple[str, ...] = ()
    blocking: bool
    suggested_action: str = Field(min_length=1)


class ArtifactValidationReport(CompilerValue):
    schema_version: Literal["artifact-validation-report-0.1"] = "artifact-validation-report-0.1"
    source_model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    valid: bool
    findings: tuple[ArtifactValidationFinding, ...]
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_report(self) -> ArtifactValidationReport:
        if self.valid != all(not finding.blocking for finding in self.findings):
            raise ValueError("artifact validation validity must match blocking findings")
        if self.report_sha256 != _validation_report_hash(self):
            raise ValueError("artifact validation report hash does not match canonical content")
        return self


def compile_artifact_bundle(
    model: AeirProjectModel,
    snapshot: ProjectSnapshot | None = None,
    *,
    allow_draft: bool = True,
) -> ArtifactBundle:
    if snapshot is not None and snapshot.source_model_sha256 != model.model_sha256:
        raise ValueError("artifact compiler snapshot does not belong to AEIR model")
    snapshot_id = "SNP-0000" if snapshot is None else snapshot.snapshot_id
    snapshot_sha256 = model.model_sha256 if snapshot is None else snapshot.snapshot_sha256
    compilation_status = (
        ArtifactCompilationStatus.APPROVED_SNAPSHOT
        if snapshot is not None and str(snapshot.status) == AeirSnapshotStatus.APPROVED.value
        else ArtifactCompilationStatus.DRAFT
    )
    if compilation_status is ArtifactCompilationStatus.DRAFT and not allow_draft:
        raise ValueError("artifact compiler requires an approved AEIR snapshot")
    contracts = artifact_contracts()
    artifacts = (
        _executive_brief(model, snapshot_id, snapshot_sha256, compilation_status, contracts[0]),
        _software_requirements(
            model,
            snapshot_id,
            snapshot_sha256,
            compilation_status,
            contracts[1],
        ),
        _domain_data_model(model, snapshot_id, snapshot_sha256, compilation_status, contracts[2]),
        _solution_architecture(
            model,
            snapshot_id,
            snapshot_sha256,
            compilation_status,
            contracts[3],
        ),
        _delivery_backlog(model, snapshot_id, snapshot_sha256, compilation_status, contracts[4]),
    )
    return ArtifactBundle(
        source_model_sha256=model.model_sha256,
        source_snapshot_id=snapshot_id,
        source_snapshot_sha256=snapshot_sha256,
        compilation_status=compilation_status,
        contracts=contracts,
        artifacts=artifacts,
        bundle_sha256=_bundle_hash(
            model.model_sha256,
            snapshot_id,
            snapshot_sha256,
            compilation_status,
            contracts,
            artifacts,
        ),
    )


def artifact_contracts() -> tuple[ArtifactContract, ...]:
    specs: tuple[tuple[ArtifactType, str, tuple[AeirObjectType, ...], tuple[str, ...]], ...] = (
        (
            ArtifactType.EXECUTIVE_BRIEF,
            "executive-project-brief",
            (
                AeirObjectType.PROJECT,
                AeirObjectType.INTENT,
                AeirObjectType.OUTCOME,
                AeirObjectType.STAKEHOLDER,
                AeirObjectType.CAPABILITY,
                AeirObjectType.CONSTRAINT,
            ),
            ("project_intent", "business_outcomes", "stakeholders", "capabilities", "constraints"),
        ),
        (
            ArtifactType.SOFTWARE_REQUIREMENTS,
            "software-requirements-specification",
            (
                AeirObjectType.PROJECT,
                AeirObjectType.CAPABILITY,
                AeirObjectType.PROCESS,
                AeirObjectType.REQUIREMENT,
                AeirObjectType.RULE,
                AeirObjectType.INTEGRATION,
                AeirObjectType.CONSTRAINT,
            ),
            (
                "purpose",
                "functional_requirements",
                "quality_requirements",
                "business_rules",
                "constraints",
            ),
        ),
        (
            ArtifactType.DOMAIN_DATA_MODEL,
            "domain-and-data-model",
            (
                AeirObjectType.CAPABILITY,
                AeirObjectType.PROCESS,
                AeirObjectType.ENTITY,
                AeirObjectType.STAKEHOLDER,
                AeirObjectType.INTEGRATION,
            ),
            (
                "domain_capabilities",
                "core_processes",
                "data_entities",
                "data_ownership",
                "integrations",
            ),
        ),
        (
            ArtifactType.SOLUTION_ARCHITECTURE,
            "solution-architecture-blueprint",
            (
                AeirObjectType.PROJECT,
                AeirObjectType.CAPABILITY,
                AeirObjectType.INTEGRATION,
                AeirObjectType.REQUIREMENT,
                AeirObjectType.DECISION,
                AeirObjectType.CONSTRAINT,
            ),
            (
                "architecture_scope",
                "capability_context",
                "interfaces",
                "quality_drivers",
                "technology_targets",
                "architecture_constraints",
            ),
        ),
        (
            ArtifactType.DELIVERY_BACKLOG,
            "delivery-backlog",
            (
                AeirObjectType.PROJECT,
                AeirObjectType.CAPABILITY,
                AeirObjectType.PROCESS,
                AeirObjectType.REQUIREMENT,
                AeirObjectType.CONSTRAINT,
            ),
            ("delivery_goal", "backlog_items", "acceptance_criteria", "delivery_constraints"),
        ),
    )
    return tuple(
        _contract(
            artifact_type=artifact_type,
            compiler_id=compiler_id,
            accepted_object_types=accepted_object_types,
            required_section_keys=required_section_keys,
        )
        for artifact_type, compiler_id, accepted_object_types, required_section_keys in specs
    )


def validate_artifact_bundle(
    model: AeirProjectModel, bundle: ArtifactBundle
) -> ArtifactValidationReport:
    findings: list[ArtifactValidationFinding] = []
    artifacts = {artifact.artifact_type: artifact for artifact in bundle.artifacts}

    srs_requirements = _entry_ids(
        artifacts[ArtifactType.SOFTWARE_REQUIREMENTS], "quality_requirements"
    )
    backlog_text = _section_entries(artifacts[ArtifactType.DELIVERY_BACKLOG], "backlog_items")
    backlog_acceptance = _section_entries(
        artifacts[ArtifactType.DELIVERY_BACKLOG], "acceptance_criteria"
    )
    for requirement_id in _object_ids(model, AeirObjectType.REQUIREMENT):
        if requirement_id in srs_requirements and not _contains_id(backlog_text, requirement_id):
            findings.append(
                _finding(
                    len(findings) + 1,
                    "ART.SRS.REQUIREMENT_IN_BACKLOG",
                    ArtifactValidationSeverity.ERROR,
                    (
                        f"Requirement {requirement_id} appears in the SRS "
                        "but not the delivery backlog."
                    ),
                    (ArtifactType.SOFTWARE_REQUIREMENTS, ArtifactType.DELIVERY_BACKLOG),
                    (requirement_id,),
                    True,
                    "Add a backlog item that traces to the requirement.",
                )
            )
        if not _contains_id(backlog_acceptance, requirement_id):
            findings.append(
                _finding(
                    len(findings) + 1,
                    "ART.BACKLOG.ACCEPTANCE_CRITERIA_REQUIRED",
                    ArtifactValidationSeverity.ERROR,
                    f"Requirement {requirement_id} has no backlog acceptance criteria.",
                    (ArtifactType.DELIVERY_BACKLOG,),
                    (requirement_id,),
                    True,
                    "Add at least one backlog acceptance criterion for the requirement.",
                )
            )

    process_and_requirement_entries = (
        *_section_entries(artifacts[ArtifactType.SOFTWARE_REQUIREMENTS], "functional_requirements"),
        *_section_entries(artifacts[ArtifactType.SOFTWARE_REQUIREMENTS], "quality_requirements"),
    )
    for entity_id in _object_ids(model, AeirObjectType.ENTITY):
        if not _contains_id(process_and_requirement_entries, entity_id):
            findings.append(
                _finding(
                    len(findings) + 1,
                    "ART.DOMAIN.ENTITY_REFERENCED",
                    ArtifactValidationSeverity.WARNING,
                    (
                        f"Domain entity {entity_id} is not referenced by a process "
                        "or requirement artifact entry."
                    ),
                    (ArtifactType.DOMAIN_DATA_MODEL, ArtifactType.SOFTWARE_REQUIREMENTS),
                    (entity_id,),
                    False,
                    (
                        "Reference the entity from a process or requirement when "
                        "the domain model matures."
                    ),
                )
            )

    architecture_entries = (
        *_section_entries(artifacts[ArtifactType.SOLUTION_ARCHITECTURE], "capability_context"),
        *_section_entries(artifacts[ArtifactType.SOLUTION_ARCHITECTURE], "interfaces"),
    )
    for capability_id in _object_ids(model, AeirObjectType.CAPABILITY):
        if not _contains_id(architecture_entries, capability_id):
            findings.append(
                _finding(
                    len(findings) + 1,
                    "ART.ARCH.CAPABILITY_TRACE_REQUIRED",
                    ArtifactValidationSeverity.ERROR,
                    f"Capability {capability_id} does not appear in architecture context.",
                    (ArtifactType.SOLUTION_ARCHITECTURE,),
                    (capability_id,),
                    True,
                    "Trace each architecture component or context entry to a capability.",
                )
            )

    constraints = _object_ids(model, AeirObjectType.CONSTRAINT)
    architecture_constraints = _section_entries(
        artifacts[ArtifactType.SOLUTION_ARCHITECTURE], "architecture_constraints"
    )
    backlog_constraints = _section_entries(
        artifacts[ArtifactType.DELIVERY_BACKLOG], "delivery_constraints"
    )
    for constraint_id in constraints:
        if not _contains_id(architecture_constraints, constraint_id):
            findings.append(
                _finding(
                    len(findings) + 1,
                    "ART.CONSTRAINT.ARCHITECTURE_COVERAGE",
                    ArtifactValidationSeverity.ERROR,
                    f"Constraint {constraint_id} does not appear in the architecture artifact.",
                    (ArtifactType.SOLUTION_ARCHITECTURE,),
                    (constraint_id,),
                    True,
                    "Include each canonical constraint in architecture constraints.",
                )
            )
        if not _contains_id(backlog_constraints, constraint_id):
            findings.append(
                _finding(
                    len(findings) + 1,
                    "ART.CONSTRAINT.BACKLOG_COVERAGE",
                    ArtifactValidationSeverity.ERROR,
                    f"Constraint {constraint_id} does not appear in the delivery backlog.",
                    (ArtifactType.DELIVERY_BACKLOG,),
                    (constraint_id,),
                    True,
                    "Include each canonical constraint in delivery constraints.",
                )
            )

    provisional = ArtifactValidationReport.model_construct(
        schema_version="artifact-validation-report-0.1",
        source_model_sha256=model.model_sha256,
        source_snapshot_sha256=bundle.source_snapshot_sha256,
        artifact_bundle_sha256=bundle.bundle_sha256,
        valid=all(not finding.blocking for finding in findings),
        findings=tuple(findings),
        report_sha256="0" * 64,
    )
    return ArtifactValidationReport(
        source_model_sha256=model.model_sha256,
        source_snapshot_sha256=bundle.source_snapshot_sha256,
        artifact_bundle_sha256=bundle.bundle_sha256,
        valid=provisional.valid,
        findings=tuple(findings),
        report_sha256=_validation_report_hash(provisional),
    )


def render_artifact_markdown(artifact: CompiledArtifact) -> str:
    lines = [f"# {artifact.title}", ""]
    for section in artifact.sections:
        lines.extend((f"## {section.title}", ""))
        lines.extend(f"- {entry}" for entry in section.entries)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _executive_brief(
    model: AeirProjectModel,
    snapshot_id: str,
    snapshot_sha256: str,
    compilation_status: ArtifactCompilationStatus,
    contract: ArtifactContract,
) -> CompiledArtifact:
    project = _one(model, AeirObjectType.PROJECT)
    intent = _one(model, AeirObjectType.INTENT)
    return _build(
        ArtifactType.EXECUTIVE_BRIEF,
        f"Executive Project Brief — {project.name}",
        model,
        snapshot_id,
        snapshot_sha256,
        compilation_status,
        contract,
        (
            _section("project_intent", "Project intent", (intent.description,)),
            _section(
                "business_outcomes",
                "Business outcomes",
                _descriptions(model, AeirObjectType.OUTCOME),
            ),
            _section("stakeholders", "Stakeholders", _named(model, AeirObjectType.STAKEHOLDER)),
            _section("capabilities", "Capabilities", _named(model, AeirObjectType.CAPABILITY)),
            _section("constraints", "Constraints", _descriptions(model, AeirObjectType.CONSTRAINT)),
        ),
    )


def _software_requirements(
    model: AeirProjectModel,
    snapshot_id: str,
    snapshot_sha256: str,
    compilation_status: ArtifactCompilationStatus,
    contract: ArtifactContract,
) -> CompiledArtifact:
    project = _one(model, AeirObjectType.PROJECT)
    functional = tuple(
        f"{item.id} [{item.status}]: {item.description}"
        for item in _of_types(
            model,
            AeirObjectType.CAPABILITY,
            AeirObjectType.PROCESS,
            AeirObjectType.RULE,
            AeirObjectType.INTEGRATION,
        )
    )
    quality = tuple(
        f"{item.id} [{item.status}]: {item.description}; acceptance: "
        f"{', '.join(item.attributes.get('acceptance_criteria', []))}"
        for item in _objects(model, AeirObjectType.REQUIREMENT)
    )
    return _build(
        ArtifactType.SOFTWARE_REQUIREMENTS,
        f"Software Requirements Specification — {project.name}",
        model,
        snapshot_id,
        snapshot_sha256,
        compilation_status,
        contract,
        (
            _section("purpose", "Purpose", (project.description,)),
            _section("functional_requirements", "Functional requirements", functional),
            _section("quality_requirements", "Quality requirements", quality),
            _section("business_rules", "Business rules", _descriptions(model, AeirObjectType.RULE)),
            _section("constraints", "Constraints", _descriptions(model, AeirObjectType.CONSTRAINT)),
        ),
    )


def _domain_data_model(
    model: AeirProjectModel,
    snapshot_id: str,
    snapshot_sha256: str,
    compilation_status: ArtifactCompilationStatus,
    contract: ArtifactContract,
) -> CompiledArtifact:
    project = _one(model, AeirObjectType.PROJECT)
    entity_ids = {entity.id for entity in _objects(model, AeirObjectType.ENTITY)}
    entities = tuple(
        f"{item.id} [{item.status}] — {item.name}: {item.description}"
        for item in _objects(model, AeirObjectType.ENTITY)
    )
    ownership = tuple(
        f"{item.source_object_id} is owned by {item.target_object_id}"
        for item in sorted(model.relationships, key=lambda value: value.id)
        if item.relationship_type == "owned_by" and item.source_object_id in entity_ids
    )
    return _build(
        ArtifactType.DOMAIN_DATA_MODEL,
        f"Domain and Data Model — {project.name}",
        model,
        snapshot_id,
        snapshot_sha256,
        compilation_status,
        contract,
        (
            _section(
                "domain_capabilities",
                "Domain capabilities",
                _named(model, AeirObjectType.CAPABILITY),
            ),
            _section("core_processes", "Core processes", _named(model, AeirObjectType.PROCESS)),
            _section("data_entities", "Data entities", entities),
            _section("data_ownership", "Data ownership", ownership),
            _section("integrations", "External systems", _named(model, AeirObjectType.INTEGRATION)),
        ),
    )


def _solution_architecture(
    model: AeirProjectModel,
    snapshot_id: str,
    snapshot_sha256: str,
    compilation_status: ArtifactCompilationStatus,
    contract: ArtifactContract,
) -> CompiledArtifact:
    project = _one(model, AeirObjectType.PROJECT)
    technologies = tuple(
        f"{item.id} [{item.status}] — "
        f"{item.attributes.get('category', 'technology')}: {item.description}"
        for item in _objects(model, AeirObjectType.DECISION)
    )
    interfaces = tuple(
        f"{item.id} [{item.status}] — {item.name}: {item.description}"
        for item in _objects(model, AeirObjectType.INTEGRATION)
    )
    return _build(
        ArtifactType.SOLUTION_ARCHITECTURE,
        f"Solution Architecture Blueprint — {project.name}",
        model,
        snapshot_id,
        snapshot_sha256,
        compilation_status,
        contract,
        (
            _section("architecture_scope", "Architecture scope", (project.description,)),
            _section(
                "capability_context", "Capability context", _named(model, AeirObjectType.CAPABILITY)
            ),
            _section("interfaces", "Integration interfaces", interfaces),
            _section(
                "quality_drivers",
                "Quality drivers",
                _descriptions(model, AeirObjectType.REQUIREMENT),
            ),
            _section("technology_targets", "Technology targets", technologies),
            _section(
                "architecture_constraints",
                "Constraints",
                _descriptions(model, AeirObjectType.CONSTRAINT),
            ),
        ),
    )


def _delivery_backlog(
    model: AeirProjectModel,
    snapshot_id: str,
    snapshot_sha256: str,
    compilation_status: ArtifactCompilationStatus,
    contract: ArtifactContract,
) -> CompiledArtifact:
    project = _one(model, AeirObjectType.PROJECT)
    items = tuple(
        f"BLG-{index:03d} ({item.id}) [{item.status}] — {item.name}: {item.description}"
        for index, item in enumerate(
            _of_types(
                model,
                AeirObjectType.CAPABILITY,
                AeirObjectType.PROCESS,
                AeirObjectType.REQUIREMENT,
            ),
            start=1,
        )
    )
    acceptance = tuple(
        f"{item.id}: {criterion}"
        for item in _objects(model, AeirObjectType.REQUIREMENT)
        for criterion in item.attributes.get("acceptance_criteria", [])
    )
    return _build(
        ArtifactType.DELIVERY_BACKLOG,
        f"Delivery Backlog — {project.name}",
        model,
        snapshot_id,
        snapshot_sha256,
        compilation_status,
        contract,
        (
            _section("delivery_goal", "Delivery goal", (project.description,)),
            _section("backlog_items", "Backlog items", items),
            _section("acceptance_criteria", "Acceptance criteria", acceptance),
            _section(
                "delivery_constraints",
                "Delivery constraints",
                _descriptions(model, AeirObjectType.CONSTRAINT),
            ),
        ),
    )


def _build(
    artifact_type: ArtifactType,
    title: str,
    model: AeirProjectModel,
    snapshot_id: str,
    snapshot_sha256: str,
    compilation_status: ArtifactCompilationStatus,
    contract: ArtifactContract,
    sections: tuple[ArtifactSection, ...],
) -> CompiledArtifact:
    if contract.artifact_type is not artifact_type:
        raise ValueError("artifact compiler contract does not match artifact type")
    section_keys = tuple(section.key for section in sections)
    if section_keys != contract.required_section_keys:
        raise ValueError("artifact compiler output does not match its section contract")
    content_sha256 = _content_hash(title, sections)
    return CompiledArtifact(
        artifact_type=artifact_type,
        compiler_id=contract.compiler_id,
        compiler_version=contract.compiler_version,
        contract_sha256=contract.contract_sha256,
        title=title,
        source_model_sha256=model.model_sha256,
        source_snapshot_id=snapshot_id,
        source_snapshot_sha256=snapshot_sha256,
        compilation_status=compilation_status,
        sections=sections,
        content_sha256=content_sha256,
        artifact_sha256=_artifact_hash(
            artifact_type,
            contract.compiler_id,
            contract.compiler_version,
            contract.contract_sha256,
            title,
            model.model_sha256,
            snapshot_id,
            snapshot_sha256,
            compilation_status,
            sections,
            content_sha256,
        ),
    )


def _section(key: str, title: str, entries: tuple[str, ...]) -> ArtifactSection:
    return ArtifactSection(key=key, title=title, entries=entries or ("No items declared in AEIR.",))


def _objects(model: AeirProjectModel, object_type: AeirObjectType) -> tuple[AeirObject, ...]:
    return tuple(
        sorted(
            (
                item
                for item in model.objects
                if item.type is object_type and item.status is not AeirStatus.REJECTED
            ),
            key=lambda item: item.id,
        )
    )


def _of_types(model: AeirProjectModel, *types: AeirObjectType) -> tuple[AeirObject, ...]:
    allowed = set(types)
    rank = {value: index for index, value in enumerate(types)}
    return tuple(
        sorted(
            (
                item
                for item in model.objects
                if item.type in allowed and item.status is not AeirStatus.REJECTED
            ),
            key=lambda item: (rank[item.type], item.id),
        )
    )


def _one(model: AeirProjectModel, object_type: AeirObjectType) -> AeirObject:
    values = _objects(model, object_type)
    if len(values) != 1:
        raise ValueError(f"artifact compiler requires exactly one {object_type.value} object")
    return values[0]


def _named(model: AeirProjectModel, object_type: AeirObjectType) -> tuple[str, ...]:
    return tuple(
        f"{item.id} [{item.status}] — {item.name}: {item.description}"
        for item in _objects(model, object_type)
    )


def _descriptions(model: AeirProjectModel, object_type: AeirObjectType) -> tuple[str, ...]:
    return tuple(
        f"{item.id} [{item.status}]: {item.description}" for item in _objects(model, object_type)
    )


def _object_ids(model: AeirProjectModel, object_type: AeirObjectType) -> tuple[str, ...]:
    return tuple(item.id for item in _objects(model, object_type))


def _section_entries(artifact: CompiledArtifact, section_key: str) -> tuple[str, ...]:
    return next(section.entries for section in artifact.sections if section.key == section_key)


def _entry_ids(artifact: CompiledArtifact, section_key: str) -> tuple[str, ...]:
    return tuple(
        entry.split(" ", maxsplit=1)[0].rstrip(":")
        for entry in _section_entries(artifact, section_key)
    )


def _contains_id(entries: Iterable[str], object_id: str) -> bool:
    return any(object_id in entry for entry in entries)


def _finding(
    index: int,
    rule_id: str,
    severity: ArtifactValidationSeverity,
    message: str,
    artifact_types: tuple[ArtifactType, ...],
    object_refs: tuple[str, ...],
    blocking: bool,
    suggested_action: str,
) -> ArtifactValidationFinding:
    return ArtifactValidationFinding(
        id=f"ART-VAL-{index:03d}",
        rule_id=rule_id,
        severity=severity,
        message=message,
        artifact_types=artifact_types,
        object_refs=tuple(sorted(object_refs)),
        blocking=blocking,
        suggested_action=suggested_action,
    )


def _contract(
    *,
    artifact_type: ArtifactType,
    compiler_id: str,
    accepted_object_types: tuple[AeirObjectType, ...],
    required_section_keys: tuple[str, ...],
) -> ArtifactContract:
    provisional = ArtifactContract.model_construct(
        schema_version="artifact-contract-0.1",
        compiler_id=compiler_id,
        compiler_version="0.1",
        artifact_type=artifact_type,
        accepted_object_types=accepted_object_types,
        required_snapshot_status=AeirSnapshotStatus.APPROVED,
        output_formats=("markdown",),
        traceability_required=True,
        required_section_keys=required_section_keys,
        contract_sha256="0" * 64,
    )
    return ArtifactContract(
        compiler_id=compiler_id,
        artifact_type=artifact_type,
        accepted_object_types=accepted_object_types,
        required_section_keys=required_section_keys,
        contract_sha256=_contract_hash(provisional),
    )


def _content_hash(title: str, sections: tuple[ArtifactSection, ...]) -> str:
    return specification_hash(
        {"title": title, "sections": [section.model_dump(mode="json") for section in sections]}
    )


def _artifact_hash(
    artifact_type: ArtifactType,
    compiler_id: str,
    compiler_version: str,
    contract_sha256: str,
    title: str,
    source_model_sha256: str,
    source_snapshot_id: str,
    source_snapshot_sha256: str,
    compilation_status: ArtifactCompilationStatus,
    sections: tuple[ArtifactSection, ...],
    content_sha256: str,
) -> str:
    return specification_hash(
        {
            "schema_version": "artifact-compiler-0.1",
            "artifact_type": artifact_type,
            "compiler_id": compiler_id,
            "compiler_version": compiler_version,
            "contract_sha256": contract_sha256,
            "title": title,
            "source_model_sha256": source_model_sha256,
            "source_snapshot_id": source_snapshot_id,
            "source_snapshot_sha256": source_snapshot_sha256,
            "compilation_status": compilation_status,
            "sections": [section.model_dump(mode="json") for section in sections],
            "content_sha256": content_sha256,
        }
    )


def _bundle_hash(
    source_model_sha256: str,
    source_snapshot_id: str,
    source_snapshot_sha256: str,
    compilation_status: ArtifactCompilationStatus,
    contracts: tuple[ArtifactContract, ...],
    artifacts: tuple[CompiledArtifact, ...],
) -> str:
    return specification_hash(
        {
            "schema_version": "artifact-bundle-0.1",
            "source_model_sha256": source_model_sha256,
            "source_snapshot_id": source_snapshot_id,
            "source_snapshot_sha256": source_snapshot_sha256,
            "compilation_status": compilation_status,
            "contracts": [contract.model_dump(mode="json") for contract in contracts],
            "artifacts": [artifact.model_dump(mode="json") for artifact in artifacts],
        }
    )


def _contract_hash(contract: ArtifactContract) -> str:
    return specification_hash(contract.model_dump(mode="json", exclude={"contract_sha256"}))


def _validation_report_hash(report: ArtifactValidationReport) -> str:
    return specification_hash(report.model_dump(mode="json", exclude={"report_sha256"}))
