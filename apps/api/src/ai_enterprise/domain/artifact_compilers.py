from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_enterprise.domain.aeir import AeirObject, AeirObjectType, AeirProjectModel, AeirStatus
from ai_enterprise.domain.specification.kernel import specification_hash


class CompilerValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ArtifactType(StrEnum):
    EXECUTIVE_BRIEF = "executive_project_brief"
    SOFTWARE_REQUIREMENTS = "software_requirements_specification"
    DOMAIN_DATA_MODEL = "domain_and_data_model"
    SOLUTION_ARCHITECTURE = "solution_architecture_blueprint"
    DELIVERY_BACKLOG = "delivery_backlog"


class ArtifactSection(CompilerValue):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    title: str = Field(min_length=1, max_length=200)
    entries: tuple[str, ...] = Field(min_length=1)


class CompiledArtifact(CompilerValue):
    schema_version: Literal["artifact-compiler-0.1"] = "artifact-compiler-0.1"
    artifact_type: ArtifactType
    title: str = Field(min_length=1, max_length=300)
    source_model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
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
            self.title,
            self.source_model_sha256,
            self.sections,
            self.content_sha256,
        ):
            raise ValueError("compiled artifact hash does not match canonical content")
        return self


class ArtifactBundle(CompilerValue):
    schema_version: Literal["artifact-bundle-0.1"] = "artifact-bundle-0.1"
    source_model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifacts: tuple[CompiledArtifact, ...]
    bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_bundle(self) -> ArtifactBundle:
        expected_types = tuple(ArtifactType)
        actual_types = tuple(artifact.artifact_type for artifact in self.artifacts)
        if actual_types != expected_types:
            raise ValueError("artifact bundle must contain the exact five outputs in order")
        if any(
            artifact.source_model_sha256 != self.source_model_sha256
            for artifact in self.artifacts
        ):
            raise ValueError("artifact bundle contains an artifact from another AEIR model")
        if self.bundle_sha256 != _bundle_hash(self.source_model_sha256, self.artifacts):
            raise ValueError("artifact bundle hash does not match canonical artifacts")
        return self


def compile_artifact_bundle(model: AeirProjectModel) -> ArtifactBundle:
    artifacts = (
        _executive_brief(model),
        _software_requirements(model),
        _domain_data_model(model),
        _solution_architecture(model),
        _delivery_backlog(model),
    )
    return ArtifactBundle(
        source_model_sha256=model.model_sha256,
        artifacts=artifacts,
        bundle_sha256=_bundle_hash(model.model_sha256, artifacts),
    )


def render_artifact_markdown(artifact: CompiledArtifact) -> str:
    lines = [f"# {artifact.title}", ""]
    for section in artifact.sections:
        lines.extend((f"## {section.title}", ""))
        lines.extend(f"- {entry}" for entry in section.entries)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _executive_brief(model: AeirProjectModel) -> CompiledArtifact:
    project = _one(model, AeirObjectType.PROJECT)
    intent = _one(model, AeirObjectType.INTENT)
    return _build(
        ArtifactType.EXECUTIVE_BRIEF,
        f"Executive Project Brief — {project.name}",
        model,
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


def _software_requirements(model: AeirProjectModel) -> CompiledArtifact:
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
        (
            _section("purpose", "Purpose", (project.description,)),
            _section("functional_requirements", "Functional requirements", functional),
            _section("quality_requirements", "Quality requirements", quality),
            _section("business_rules", "Business rules", _descriptions(model, AeirObjectType.RULE)),
            _section("constraints", "Constraints", _descriptions(model, AeirObjectType.CONSTRAINT)),
        ),
    )


def _domain_data_model(model: AeirProjectModel) -> CompiledArtifact:
    project = _one(model, AeirObjectType.PROJECT)
    entity_ids = {entity.id for entity in _objects(model, AeirObjectType.ENTITY)}
    entities = tuple(
        f"{item.id} [{item.status}] — {item.name}: {item.description}"
        for item in _objects(model, AeirObjectType.ENTITY)
    )
    ownership = tuple(
        f"{item.source_object_id} is owned by {item.target_object_id}"
        for item in sorted(model.relationships, key=lambda value: value.id)
        if item.relationship_type == "owned_by"
        and item.source_object_id in entity_ids
    )
    return _build(
        ArtifactType.DOMAIN_DATA_MODEL,
        f"Domain and Data Model — {project.name}",
        model,
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


def _solution_architecture(model: AeirProjectModel) -> CompiledArtifact:
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
        (
            _section("architecture_scope", "Architecture scope", (project.description,)),
            _section(
                "capability_context",
                "Capability context",
                _named(model, AeirObjectType.CAPABILITY),
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


def _delivery_backlog(model: AeirProjectModel) -> CompiledArtifact:
    project = _one(model, AeirObjectType.PROJECT)
    items = tuple(
        f"BLG-{index:03d} [{item.status}] — {item.name}: {item.description}"
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
    sections: tuple[ArtifactSection, ...],
) -> CompiledArtifact:
    content_sha256 = _content_hash(title, sections)
    return CompiledArtifact(
        artifact_type=artifact_type,
        title=title,
        source_model_sha256=model.model_sha256,
        sections=sections,
        content_sha256=content_sha256,
        artifact_sha256=_artifact_hash(
            artifact_type, title, model.model_sha256, sections, content_sha256
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
        f"{item.id} [{item.status}]: {item.description}"
        for item in _objects(model, object_type)
    )


def _content_hash(title: str, sections: tuple[ArtifactSection, ...]) -> str:
    return specification_hash(
        {"title": title, "sections": [section.model_dump(mode="json") for section in sections]}
    )


def _artifact_hash(
    artifact_type: ArtifactType,
    title: str,
    source_model_sha256: str,
    sections: tuple[ArtifactSection, ...],
    content_sha256: str,
) -> str:
    return specification_hash(
        {
            "schema_version": "artifact-compiler-0.1",
            "artifact_type": artifact_type,
            "title": title,
            "source_model_sha256": source_model_sha256,
            "sections": [section.model_dump(mode="json") for section in sections],
            "content_sha256": content_sha256,
        }
    )


def _bundle_hash(source_model_sha256: str, artifacts: tuple[CompiledArtifact, ...]) -> str:
    return specification_hash(
        {
            "schema_version": "artifact-bundle-0.1",
            "source_model_sha256": source_model_sha256,
            "artifacts": [artifact.model_dump(mode="json") for artifact in artifacts],
        }
    )
