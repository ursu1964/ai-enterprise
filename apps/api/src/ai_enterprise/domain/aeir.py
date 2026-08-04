from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_enterprise.domain.aepm import AepmManifest
from ai_enterprise.domain.specification.kernel import specification_hash


class AeirObjectType(StrEnum):
    PROJECT = "project"
    INTENT = "intent"
    OUTCOME = "outcome"
    STAKEHOLDER = "stakeholder"
    CAPABILITY = "capability"
    PROCESS = "process"
    REQUIREMENT = "requirement"
    RULE = "rule"
    ENTITY = "entity"
    INTEGRATION = "integration"
    CONSTRAINT = "constraint"
    RISK = "risk"
    DECISION = "decision"
    ARTIFACT = "artifact"
    RELATIONSHIP = "relationship"


class AeirStatus(StrEnum):
    PROPOSED = "proposed"
    INFERRED = "inferred"
    UNVERIFIED = "unverified"
    APPROVED = "approved"
    REJECTED = "rejected"


class AeirValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AeirSource(AeirValue):
    kind: Literal["aepm_manifest"] = "aepm_manifest"
    reference: str = Field(min_length=1)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AeirObject(AeirValue):
    id: str = Field(pattern=r"^[A-Z][A-Z0-9-]{2,63}$")
    type: AeirObjectType
    name: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=4000)
    status: AeirStatus
    source: AeirSource
    confidence: float = Field(ge=0, le=1)
    version: str = Field(pattern=r"^0\.1\.0$")
    relationships: tuple[str, ...] = ()
    attributes: dict[str, Any] = Field(default_factory=dict)


class AeirRelationship(AeirObject):
    type: Literal[AeirObjectType.RELATIONSHIP] = AeirObjectType.RELATIONSHIP
    source_object_id: str
    target_object_id: str
    relationship_type: Literal["contains", "owned_by"]


class AeirProjectModel(AeirValue):
    schema_version: Literal["aeir-0.1"] = "aeir-0.1"
    source_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    objects: tuple[AeirObject, ...]
    relationships: tuple[AeirRelationship, ...]
    model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_graph(self) -> AeirProjectModel:
        object_ids = [item.id for item in self.objects]
        relationship_ids = [item.id for item in self.relationships]
        if len(object_ids) != len(set(object_ids)):
            raise ValueError("AEIR object identifiers must be unique")
        if len(relationship_ids) != len(set(relationship_ids)):
            raise ValueError("AEIR relationship identifiers must be unique")
        known = set(object_ids)
        for relationship in self.relationships:
            if relationship.source_object_id not in known:
                raise ValueError("AEIR relationship source is unavailable")
            if relationship.target_object_id not in known:
                raise ValueError("AEIR relationship target is unavailable")
        referenced = {value for item in self.objects for value in item.relationships}
        if referenced != set(relationship_ids):
            raise ValueError("AEIR object relationship references are inconsistent")
        if self.model_sha256 != _model_hash(
            self.source_manifest_sha256, self.objects, self.relationships
        ):
            raise ValueError("AEIR model hash does not match canonical content")
        return self


def compile_aepm(manifest: AepmManifest) -> AeirProjectModel:
    manifest_sha256 = specification_hash(manifest)
    objects: list[AeirObject] = []
    relationship_specs: list[tuple[str, str, str, Literal["contains", "owned_by"]]] = []

    def source(reference: str) -> AeirSource:
        return AeirSource(reference=reference, manifest_sha256=manifest_sha256)

    def add(
        *,
        object_id: str,
        object_type: AeirObjectType,
        name: str,
        description: str,
        reference: str,
        status: AeirStatus = AeirStatus.UNVERIFIED,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        objects.append(
            AeirObject(
                id=object_id,
                type=object_type,
                name=name,
                description=description,
                status=status,
                source=source(reference),
                confidence=1.0,
                version="0.1.0",
                attributes=attributes or {},
            )
        )
        if object_id != "PROJ-001":
            relationship_specs.append(
                (f"REL-{len(relationship_specs) + 1:03d}", "PROJ-001", object_id, "contains")
            )

    intent = manifest.project_intent
    add(
        object_id="PROJ-001",
        object_type=AeirObjectType.PROJECT,
        name=intent.name,
        description=intent.summary,
        reference="project_intent",
    )
    add(
        object_id="INTENT-001",
        object_type=AeirObjectType.INTENT,
        name=f"Intent for {intent.name}",
        description=intent.summary,
        reference="project_intent",
        attributes={"problem": intent.problem, "opportunity": intent.opportunity},
    )
    for outcome in manifest.business_outcomes:
        add(
            object_id=outcome.id,
            object_type=AeirObjectType.OUTCOME,
            name=f"Business outcome {outcome.id}",
            description=outcome.description,
            reference=f"business_outcomes/{outcome.id}",
            attributes={"indicators": list(outcome.indicators)},
        )
    for stakeholder in manifest.stakeholders:
        add(
            object_id=stakeholder.id,
            object_type=AeirObjectType.STAKEHOLDER,
            name=stakeholder.name,
            description=stakeholder.role,
            reference=f"stakeholders/{stakeholder.id}",
            attributes={"responsibilities": list(stakeholder.responsibilities)},
        )
    for capability in manifest.capabilities:
        add(
            object_id=capability.id,
            object_type=AeirObjectType.CAPABILITY,
            name=capability.name,
            description=capability.description,
            reference=f"capabilities/{capability.id}",
        )
        relationship_specs.append(
            (
                f"REL-{len(relationship_specs) + 1:03d}",
                capability.id,
                capability.owner_stakeholder_id,
                "owned_by",
            )
        )
    for process in manifest.core_processes:
        add(
            object_id=process.id,
            object_type=AeirObjectType.PROCESS,
            name=process.name,
            description=process.description,
            reference=f"core_processes/{process.id}",
            attributes={"trigger": process.trigger, "outputs": list(process.outputs)},
        )
    for rule in manifest.business_rules:
        add(
            object_id=rule.id,
            object_type=AeirObjectType.RULE,
            name=f"Business rule {rule.id}",
            description=rule.description,
            reference=f"business_rules/{rule.id}",
        )
    for entity in manifest.data_entities:
        add(
            object_id=entity.id,
            object_type=AeirObjectType.ENTITY,
            name=entity.name,
            description=entity.description,
            reference=f"data_entities/{entity.id}",
        )
        relationship_specs.append(
            (
                f"REL-{len(relationship_specs) + 1:03d}",
                entity.id,
                entity.owner_stakeholder_id,
                "owned_by",
            )
        )
    for integration in manifest.integrations:
        add(
            object_id=integration.id,
            object_type=AeirObjectType.INTEGRATION,
            name=integration.name,
            description=integration.purpose,
            reference=f"integrations/{integration.id}",
            attributes={
                "system": integration.system,
                "security_rules": list(integration.security_rules),
            },
        )
    for requirement in manifest.quality_requirements:
        add(
            object_id=requirement.id,
            object_type=AeirObjectType.REQUIREMENT,
            name=f"{requirement.category.title()} requirement",
            description=requirement.description,
            reference=f"quality_requirements/{requirement.id}",
            attributes={
                "category": requirement.category,
                "acceptance_criteria": list(requirement.acceptance_criteria),
            },
        )
    for constraint in manifest.constraints:
        add(
            object_id=constraint.id,
            object_type=AeirObjectType.CONSTRAINT,
            name=f"{constraint.category.title()} constraint",
            description=constraint.description,
            reference=f"constraints/{constraint.id}",
            attributes={"category": constraint.category},
        )
    for index, (category, targets) in enumerate(
        manifest.preferred_technology_targets.model_dump(mode="json").items(), start=1
    ):
        if targets:
            add(
                object_id=f"DEC-{index:03d}",
                object_type=AeirObjectType.DECISION,
                name=f"Preferred {category.replace('_', ' ')} targets",
                description=", ".join(targets),
                reference=f"preferred_technology_targets/{category}",
                status=AeirStatus.PROPOSED,
                attributes={"category": category, "targets": targets},
            )

    relationship_map: dict[str, list[str]] = {item.id: [] for item in objects}
    relationships: list[AeirRelationship] = []
    for relationship_id, source_id, target_id, relationship_type in relationship_specs:
        relationship_map[source_id].append(relationship_id)
        relationship_map[target_id].append(relationship_id)
        relationships.append(
            AeirRelationship(
                id=relationship_id,
                name=f"{source_id} {relationship_type} {target_id}",
                description=f"Canonical {relationship_type} relationship.",
                status=AeirStatus.UNVERIFIED,
                source=source("relationships"),
                confidence=1.0,
                version="0.1.0",
                source_object_id=source_id,
                target_object_id=target_id,
                relationship_type=relationship_type,
            )
        )
    bound_objects = tuple(
        item.model_copy(update={"relationships": tuple(relationship_map[item.id])})
        for item in objects
    )
    bound_relationships = tuple(relationships)
    return AeirProjectModel(
        source_manifest_sha256=manifest_sha256,
        objects=bound_objects,
        relationships=bound_relationships,
        model_sha256=_model_hash(manifest_sha256, bound_objects, bound_relationships),
    )


def _model_hash(
    manifest_sha256: str,
    objects: tuple[AeirObject, ...],
    relationships: tuple[AeirRelationship, ...],
) -> str:
    return specification_hash(
        {
            "schema_version": "aeir-0.1",
            "source_manifest_sha256": manifest_sha256,
            "objects": [item.model_dump(mode="json") for item in objects],
            "relationships": [item.model_dump(mode="json") for item in relationships],
        }
    )
