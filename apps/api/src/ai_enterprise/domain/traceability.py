from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_enterprise.domain.aeir import (
    AeirObject,
    AeirObjectType,
    AeirProjectModel,
    AeirRelationship,
    ApprovalStatus,
    LifecycleStatus,
    RelationshipType,
    TruthStatus,
)
from ai_enterprise.domain.artifact_compilers import ArtifactBundle, ArtifactSection, ArtifactType
from ai_enterprise.domain.specification.kernel import specification_hash


class TraceabilityValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TraceSourceObject(TraceabilityValue):
    object_id: str = Field(pattern=r"^[A-Z][A-Z0-9-]{2,63}$")
    object_type: AeirObjectType
    lifecycle_status: LifecycleStatus
    truth_status: TruthStatus
    approval_status: ApprovalStatus
    source_kind: Literal["aepm_manifest", "human_clarification", "ai_operation"]
    source_reference: str = Field(min_length=1)
    source_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_references: tuple[str, ...] = ()
    object_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class TraceSourceRelationship(TraceabilityValue):
    relationship_id: str = Field(pattern=r"^[A-Z][A-Z0-9-]{2,63}$")
    relationship_type: RelationshipType
    source_object_id: str = Field(pattern=r"^[A-Z][A-Z0-9-]{2,63}$")
    target_object_id: str = Field(pattern=r"^[A-Z][A-Z0-9-]{2,63}$")
    lifecycle_status: LifecycleStatus
    truth_status: TruthStatus
    approval_status: ApprovalStatus
    relationship_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ArtifactSectionTrace(TraceabilityValue):
    artifact_type: ArtifactType
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    section_key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    section_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_object_ids: tuple[str, ...] = Field(min_length=1)
    relationship_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_sources(self) -> ArtifactSectionTrace:
        if tuple(sorted(set(self.source_object_ids))) != self.source_object_ids:
            raise ValueError("section source object identifiers must be unique and sorted")
        if tuple(sorted(set(self.relationship_ids))) != self.relationship_ids:
            raise ValueError("section relationship identifiers must be unique and sorted")
        return self


class ArtifactEntryTrace(TraceabilityValue):
    artifact_type: ArtifactType
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    section_key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    entry_index: int = Field(ge=0)
    entry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_object_ids: tuple[str, ...] = Field(min_length=1)
    relationship_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_sources(self) -> ArtifactEntryTrace:
        if tuple(sorted(set(self.source_object_ids))) != self.source_object_ids:
            raise ValueError("entry source object identifiers must be unique and sorted")
        if tuple(sorted(set(self.relationship_ids))) != self.relationship_ids:
            raise ValueError("entry relationship identifiers must be unique and sorted")
        return self


class ArtifactTraceabilityManifest(TraceabilityValue):
    schema_version: Literal["traceability-0.1"] = "traceability-0.1"
    source_model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_objects: tuple[TraceSourceObject, ...] = Field(min_length=1)
    source_relationships: tuple[TraceSourceRelationship, ...] = ()
    section_traces: tuple[ArtifactSectionTrace, ...] = Field(min_length=1)
    entry_traces: tuple[ArtifactEntryTrace, ...] = Field(min_length=1)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_manifest(self) -> ArtifactTraceabilityManifest:
        source_ids = [item.object_id for item in self.source_objects]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("traceability source object identifiers must be unique")
        if tuple(sorted(source_ids)) != tuple(source_ids):
            raise ValueError("traceability source objects must be sorted by identifier")
        relationship_ids = [item.relationship_id for item in self.source_relationships]
        if len(relationship_ids) != len(set(relationship_ids)):
            raise ValueError("traceability source relationship identifiers must be unique")
        if tuple(sorted(relationship_ids)) != tuple(relationship_ids):
            raise ValueError("traceability source relationships must be sorted by identifier")

        known_sources = set(source_ids)
        known_relationships = set(relationship_ids)
        section_keys = [
            (item.artifact_type, item.artifact_sha256, item.section_key)
            for item in self.section_traces
        ]
        if len(section_keys) != len(set(section_keys)):
            raise ValueError("traceability section mappings must be unique")
        entry_keys = [
            (item.artifact_type, item.artifact_sha256, item.section_key, item.entry_index)
            for item in self.entry_traces
        ]
        if len(entry_keys) != len(set(entry_keys)):
            raise ValueError("traceability entry mappings must be unique")
        for section_trace in self.section_traces:
            if any(
                object_id not in known_sources
                for object_id in section_trace.source_object_ids
            ):
                raise ValueError("traceability mapping references an unknown source object")
            if any(rel_id not in known_relationships for rel_id in section_trace.relationship_ids):
                raise ValueError("traceability mapping references an unknown relationship")
        for entry_trace in self.entry_traces:
            if any(
                object_id not in known_sources
                for object_id in entry_trace.source_object_ids
            ):
                raise ValueError("traceability mapping references an unknown source object")
            if any(rel_id not in known_relationships for rel_id in entry_trace.relationship_ids):
                raise ValueError("traceability mapping references an unknown relationship")
        if self.manifest_sha256 != _manifest_hash(self):
            raise ValueError("traceability manifest hash does not match canonical content")
        return self


def compile_traceability_manifest(
    model: AeirProjectModel, bundle: ArtifactBundle
) -> ArtifactTraceabilityManifest:
    verify_artifact_bundle(model, bundle)
    source_objects = tuple(_trace_object(item) for item in _active_objects(model))
    source_relationships = tuple(
        _trace_relationship(item) for item in sorted(model.relationships, key=lambda item: item.id)
    )
    section_traces: list[ArtifactSectionTrace] = []
    entry_traces: list[ArtifactEntryTrace] = []
    for artifact in bundle.artifacts:
        for section in artifact.sections:
            entry_sources = _entry_sources(model, artifact.artifact_type, section)
            if len(entry_sources) != len(section.entries):
                raise ValueError("traceability entry mapping does not match section entries")
            source_ids = _sorted_unique(
                object_id for sources, _ in entry_sources for object_id in sources
            )
            relationship_ids = _sorted_unique(
                relationship_id
                for _, relationships in entry_sources
                for relationship_id in relationships
            )
            section_traces.append(
                ArtifactSectionTrace(
                    artifact_type=artifact.artifact_type,
                    artifact_sha256=artifact.artifact_sha256,
                    section_key=section.key,
                    section_sha256=_section_hash(section),
                    source_object_ids=source_ids,
                    relationship_ids=relationship_ids,
                )
            )
            for index, (sources, relationships) in enumerate(entry_sources):
                entry_traces.append(
                    ArtifactEntryTrace(
                        artifact_type=artifact.artifact_type,
                        artifact_sha256=artifact.artifact_sha256,
                        section_key=section.key,
                        entry_index=index,
                        entry_sha256=_entry_hash(section.entries[index]),
                        source_object_ids=sources,
                        relationship_ids=relationships,
                    )
                )
    provisional = ArtifactTraceabilityManifest.model_construct(
        schema_version="traceability-0.1",
        source_model_sha256=model.model_sha256,
        source_manifest_sha256=model.source_manifest_sha256,
        artifact_bundle_sha256=bundle.bundle_sha256,
        source_objects=source_objects,
        source_relationships=source_relationships,
        section_traces=tuple(section_traces),
        entry_traces=tuple(entry_traces),
        manifest_sha256="0" * 64,
    )
    return ArtifactTraceabilityManifest(
        source_model_sha256=model.model_sha256,
        source_manifest_sha256=model.source_manifest_sha256,
        artifact_bundle_sha256=bundle.bundle_sha256,
        source_objects=source_objects,
        source_relationships=source_relationships,
        section_traces=tuple(section_traces),
        entry_traces=tuple(entry_traces),
        manifest_sha256=_manifest_hash(provisional),
    )


def verify_traceability_manifest(
    manifest: ArtifactTraceabilityManifest,
    model: AeirProjectModel,
    bundle: ArtifactBundle,
) -> None:
    verify_artifact_bundle(model, bundle)
    expected = compile_traceability_manifest(model, bundle)
    if manifest != expected:
        raise ValueError("traceability manifest does not match AEIR model and artifact bundle")


def render_traceable_artifact_markdown(
    artifact_type: ArtifactType,
    bundle: ArtifactBundle,
    manifest: ArtifactTraceabilityManifest,
) -> str:
    artifacts = {artifact.artifact_type: artifact for artifact in bundle.artifacts}
    artifact = artifacts[artifact_type]
    traces = {
        trace.section_key: trace
        for trace in manifest.section_traces
        if trace.artifact_type is artifact.artifact_type
        and trace.artifact_sha256 == artifact.artifact_sha256
    }
    entry_traces = {
        (trace.section_key, trace.entry_index): trace
        for trace in manifest.entry_traces
        if trace.artifact_type is artifact.artifact_type
        and trace.artifact_sha256 == artifact.artifact_sha256
    }
    source_catalog = {item.object_id: item for item in manifest.source_objects}
    lines = [f"# {artifact.title}", ""]
    for section in artifact.sections:
        trace = traces[section.key]
        lines.extend((f"## {section.title}", ""))
        for index, entry in enumerate(section.entries):
            entry_trace = entry_traces[(section.key, index)]
            lines.append(f"- {entry}")
            lines.append(
                "  Trace: " + _trace_reference_line(entry_trace.source_object_ids, source_catalog)
            )
        lines.append("")
        lines.append(
            "Sources: "
            + _trace_reference_line(trace.source_object_ids, source_catalog)
        )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def verify_artifact_bundle(model: AeirProjectModel, bundle: ArtifactBundle) -> None:
    if bundle.source_model_sha256 != model.model_sha256:
        raise ValueError("artifact bundle is not bound to the supplied AEIR model")


def _entry_sources(
    model: AeirProjectModel, artifact_type: ArtifactType, section: ArtifactSection
) -> tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]:
    mapping = _section_source_mapping(model, artifact_type, section.key)
    if section.entries == ("No items declared in AEIR.",):
        return (((_one_id(model, AeirObjectType.PROJECT),), ()),)
    return mapping


def _section_source_mapping(
    model: AeirProjectModel, artifact_type: ArtifactType, section_key: str
) -> tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]:
    project = (_one_id(model, AeirObjectType.PROJECT),)
    table: dict[tuple[ArtifactType, str], tuple[tuple[str, ...], tuple[str, ...]]] = {
        (ArtifactType.EXECUTIVE_BRIEF, "project_intent"): (
            _sorted_unique((*project, _one_id(model, AeirObjectType.INTENT))),
            (),
        ),
        (ArtifactType.SOFTWARE_REQUIREMENTS, "purpose"): (project, ()),
        (ArtifactType.SOLUTION_ARCHITECTURE, "architecture_scope"): (project, ()),
        (ArtifactType.DELIVERY_BACKLOG, "delivery_goal"): (project, ()),
    }
    direct = table.get((artifact_type, section_key))
    if direct is not None:
        return (direct,)

    object_types = _section_object_types(artifact_type, section_key)
    if object_types:
        return tuple(((item.id,), ()) for item in _of_types(model, *object_types))

    if artifact_type is ArtifactType.DOMAIN_DATA_MODEL and section_key == "data_ownership":
        entity_ids = {item.id for item in _objects(model, AeirObjectType.ENTITY)}
        ownership = tuple(
            relationship
            for relationship in sorted(model.relationships, key=lambda item: item.id)
            if relationship.relationship_type is RelationshipType.OWNED_BY
            and relationship.source_object_id in entity_ids
        )
        return tuple(
            (
                _sorted_unique((relationship.source_object_id, relationship.target_object_id)),
                (relationship.id,),
            )
            for relationship in ownership
        )
    raise ValueError(f"unsupported traceability section: {artifact_type.value}/{section_key}")


def _section_object_types(
    artifact_type: ArtifactType, section_key: str
) -> tuple[AeirObjectType, ...]:
    mapping: dict[tuple[ArtifactType, str], tuple[AeirObjectType, ...]] = {
        (ArtifactType.EXECUTIVE_BRIEF, "business_outcomes"): (AeirObjectType.OUTCOME,),
        (ArtifactType.EXECUTIVE_BRIEF, "stakeholders"): (AeirObjectType.STAKEHOLDER,),
        (ArtifactType.EXECUTIVE_BRIEF, "capabilities"): (AeirObjectType.CAPABILITY,),
        (ArtifactType.EXECUTIVE_BRIEF, "constraints"): (AeirObjectType.CONSTRAINT,),
        (ArtifactType.SOFTWARE_REQUIREMENTS, "functional_requirements"): (
            AeirObjectType.CAPABILITY,
            AeirObjectType.PROCESS,
            AeirObjectType.RULE,
            AeirObjectType.INTEGRATION,
        ),
        (ArtifactType.SOFTWARE_REQUIREMENTS, "quality_requirements"): (
            AeirObjectType.REQUIREMENT,
        ),
        (ArtifactType.SOFTWARE_REQUIREMENTS, "business_rules"): (AeirObjectType.RULE,),
        (ArtifactType.SOFTWARE_REQUIREMENTS, "constraints"): (AeirObjectType.CONSTRAINT,),
        (ArtifactType.DOMAIN_DATA_MODEL, "domain_capabilities"): (
            AeirObjectType.CAPABILITY,
        ),
        (ArtifactType.DOMAIN_DATA_MODEL, "core_processes"): (AeirObjectType.PROCESS,),
        (ArtifactType.DOMAIN_DATA_MODEL, "data_entities"): (AeirObjectType.ENTITY,),
        (ArtifactType.DOMAIN_DATA_MODEL, "integrations"): (AeirObjectType.INTEGRATION,),
        (ArtifactType.SOLUTION_ARCHITECTURE, "capability_context"): (
            AeirObjectType.CAPABILITY,
        ),
        (ArtifactType.SOLUTION_ARCHITECTURE, "interfaces"): (AeirObjectType.INTEGRATION,),
        (ArtifactType.SOLUTION_ARCHITECTURE, "quality_drivers"): (
            AeirObjectType.REQUIREMENT,
        ),
        (ArtifactType.SOLUTION_ARCHITECTURE, "technology_targets"): (
            AeirObjectType.DECISION,
        ),
        (ArtifactType.SOLUTION_ARCHITECTURE, "architecture_constraints"): (
            AeirObjectType.CONSTRAINT,
        ),
        (ArtifactType.DELIVERY_BACKLOG, "backlog_items"): (
            AeirObjectType.CAPABILITY,
            AeirObjectType.PROCESS,
            AeirObjectType.REQUIREMENT,
        ),
        (ArtifactType.DELIVERY_BACKLOG, "acceptance_criteria"): (
            AeirObjectType.REQUIREMENT,
        ),
        (ArtifactType.DELIVERY_BACKLOG, "delivery_constraints"): (
            AeirObjectType.CONSTRAINT,
        ),
    }
    return mapping.get((artifact_type, section_key), ())


def _active_objects(model: AeirProjectModel) -> tuple[AeirObject, ...]:
    return tuple(
        sorted(
            (item for item in model.objects if item.approval_status is not ApprovalStatus.REJECTED),
            key=lambda item: item.id,
        )
    )


def _objects(model: AeirProjectModel, object_type: AeirObjectType) -> tuple[AeirObject, ...]:
    return tuple(item for item in _active_objects(model) if item.type is object_type)


def _of_types(model: AeirProjectModel, *types: AeirObjectType) -> tuple[AeirObject, ...]:
    allowed = set(types)
    rank = {value: index for index, value in enumerate(types)}
    return tuple(
        sorted(
            (item for item in _active_objects(model) if item.type in allowed),
            key=lambda item: (rank[item.type], item.id),
        )
    )


def _one_id(model: AeirProjectModel, object_type: AeirObjectType) -> str:
    values = _objects(model, object_type)
    if len(values) != 1:
        raise ValueError(f"traceability requires exactly one {object_type.value} object")
    return values[0].id


def _trace_object(item: AeirObject) -> TraceSourceObject:
    return TraceSourceObject(
        object_id=item.id,
        object_type=item.type,
        lifecycle_status=item.lifecycle_status,
        truth_status=item.truth_status,
        approval_status=item.approval_status,
        source_kind=item.source.kind,
        source_reference=item.source.reference,
        source_manifest_sha256=item.source.manifest_sha256,
        evidence_references=item.source.evidence_references,
        object_sha256=specification_hash(item),
    )


def _trace_relationship(item: AeirRelationship) -> TraceSourceRelationship:
    return TraceSourceRelationship(
        relationship_id=item.id,
        relationship_type=item.relationship_type,
        source_object_id=item.source_object_id,
        target_object_id=item.target_object_id,
        lifecycle_status=item.lifecycle_status,
        truth_status=item.truth_status,
        approval_status=item.approval_status,
        relationship_sha256=specification_hash(item),
    )


def _section_hash(section: ArtifactSection) -> str:
    return specification_hash(section)


def _entry_hash(entry: str) -> str:
    return specification_hash({"entry": entry})


def _trace_reference_line(
    object_ids: tuple[str, ...], source_catalog: dict[str, TraceSourceObject]
) -> str:
    source_refs = tuple(source_catalog[object_id].source_reference for object_id in object_ids)
    return ", ".join(object_ids) + " | Client references: " + ", ".join(source_refs)


def _manifest_hash(manifest: ArtifactTraceabilityManifest) -> str:
    return specification_hash(manifest.model_dump(mode="json", exclude={"manifest_sha256"}))


def _sorted_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))
