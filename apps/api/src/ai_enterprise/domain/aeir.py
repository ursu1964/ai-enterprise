from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_enterprise.domain.aepm import AepmManifest
from ai_enterprise.domain.specification.kernel import specification_hash

AEIR_VERSION = "0.1.0"
AEIR_SYSTEM_ACTOR = "aepm-deterministic-compiler"
AEIR_CANONICAL_TIMESTAMP = "2026-08-04T00:00:00Z"
AEIR_CANONICAL_VALID_FROM = "2026-08-04"


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


class LifecycleStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class TruthStatus(StrEnum):
    ASSERTED = "asserted"
    INFERRED = "inferred"
    ASSUMED = "assumed"
    VERIFIED = "verified"
    DISPUTED = "disputed"


class ApprovalStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RelationshipType(StrEnum):
    CONTAINS = "contains"
    OWNED_BY = "owned_by"
    SUPPORTS = "supports"
    CONSTRAINS = "constrains"
    REALIZES = "realizes"
    TRACES_TO = "traces_to"
    DEPENDS_ON = "depends_on"


class AeirStatus(StrEnum):
    """Compatibility enum for callers that still name the old mixed status concept."""

    PROPOSED = "proposed"
    INFERRED = "inferred"
    UNVERIFIED = "unverified"
    APPROVED = "approved"
    REJECTED = "rejected"


class AeirValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AeirSource(AeirValue):
    kind: Literal["aepm_manifest", "human_clarification", "ai_operation"] = "aepm_manifest"
    reference: str = Field(min_length=1)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_references: tuple[str, ...] = ()


class AiOperationProvenance(AeirValue):
    model_provider: str = Field(min_length=1, max_length=200)
    model_name: str = Field(min_length=1, max_length=200)
    operation_type: str = Field(min_length=1, max_length=80)
    prompt_version: str = Field(min_length=1, max_length=80)
    schema_version: Literal["AEIR-0.1"] = "AEIR-0.1"
    generated_at: str = Field(min_length=1, max_length=40)
    input_source_refs: tuple[str, ...] = Field(min_length=1)
    review_required: bool = True


class AeirObject(AeirValue):
    id: str = Field(pattern=r"^[A-Z][A-Z0-9-]{2,63}$")
    type: AeirObjectType
    name: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=4000)
    status: AeirStatus
    lifecycle_status: LifecycleStatus
    truth_status: TruthStatus
    approval_status: ApprovalStatus
    source_refs: tuple[str, ...] = Field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    relationship_refs: tuple[str, ...] = Field(default_factory=tuple)
    confidence: float = Field(ge=0, le=1)
    version: str = Field(pattern=r"^0\.1\.0$")
    created_at: str = Field(min_length=1, max_length=40)
    created_by: str = Field(min_length=1, max_length=200)
    updated_at: str = Field(min_length=1, max_length=40)
    updated_by: str = Field(min_length=1, max_length=200)
    source: AeirSource
    ai_operation: AiOperationProvenance | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def relationships(self) -> tuple[str, ...]:
        return self.relationship_refs

    @model_validator(mode="after")
    def validate_provenance(self) -> AeirObject:
        if not self.source_refs:
            raise ValueError("AEIR objects require at least one source reference")
        if self.truth_status in {TruthStatus.INFERRED, TruthStatus.ASSUMED}:
            if self.approval_status is ApprovalStatus.APPROVED:
                raise ValueError("inferred or assumed AEIR objects cannot be silently approved")
            if self.ai_operation is None and self.source.kind == "ai_operation":
                raise ValueError("AI-derived AEIR objects require AI operation provenance")
        return self


class AeirRelationship(AeirValue):
    id: str = Field(pattern=r"^REL-[0-9]{3}$")
    type: Literal[AeirObjectType.RELATIONSHIP] = AeirObjectType.RELATIONSHIP
    relationship_type: RelationshipType
    source_object_id: str = Field(pattern=r"^[A-Z][A-Z0-9-]{2,63}$")
    target_object_id: str = Field(pattern=r"^[A-Z][A-Z0-9-]{2,63}$")
    status: AeirStatus
    lifecycle_status: LifecycleStatus
    truth_status: TruthStatus
    approval_status: ApprovalStatus
    source_refs: tuple[str, ...] = Field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    confidence: float = Field(ge=0, le=1)
    version: str = Field(pattern=r"^0\.1\.0$")
    created_at: str = Field(min_length=1, max_length=40)
    created_by: str = Field(min_length=1, max_length=200)
    updated_at: str = Field(min_length=1, max_length=40)
    updated_by: str = Field(min_length=1, max_length=200)
    valid_from: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    valid_to: str | None = Field(default=None, pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    source: AeirSource
    attributes: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_relationship(self) -> AeirRelationship:
        if self.source_object_id == self.target_object_id:
            raise ValueError("AEIR relationship endpoints must be distinct")
        if not self.source_refs:
            raise ValueError("AEIR relationships require at least one source reference")
        return self


class ProjectSnapshot(AeirValue):
    schema_version: Literal["aeir-snapshot-0.1"] = "aeir-snapshot-0.1"
    snapshot_id: str = Field(pattern=r"^SNP-[0-9]{4}$")
    project_id: str = Field(pattern=r"^[A-Z][A-Z0-9-]{2,63}$")
    aepm_version: Literal["0.1"] = "0.1"
    aeir_version: Literal["0.1"] = "0.1"
    source_model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    object_versions: tuple[dict[str, str], ...]
    relationship_versions: tuple[dict[str, str], ...]
    status: Literal["draft", "approved"]
    created_at: str = Field(min_length=1, max_length=40)
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_snapshot_hash(self) -> ProjectSnapshot:
        if self.snapshot_sha256 != _snapshot_hash(self):
            raise ValueError("AEIR snapshot hash does not match canonical content")
        return self


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
        referenced = {value for item in self.objects for value in item.relationship_refs}
        if referenced != set(relationship_ids):
            raise ValueError("AEIR object relationship references are inconsistent")
        if self.model_sha256 != _model_hash(
            self.source_manifest_sha256, self.objects, self.relationships
        ):
            raise ValueError("AEIR model hash does not match canonical content")
        return self


class AeirSnapshotStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"


class AeirProjectSnapshot(AeirValue):
    schema_version: Literal["aeir-snapshot-0.1"] = "aeir-snapshot-0.1"
    snapshot_id: str = Field(pattern=r"^SNP-[0-9]{4}$")
    project_id: str = Field(min_length=1, max_length=200)
    aepm_version: Literal["0.1"] = "0.1"
    aeir_version: Literal["0.1"] = "0.1"
    source_model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    object_versions: tuple[str, ...] = Field(min_length=1)
    status: AeirSnapshotStatus
    created_at: str = "1970-01-01T00:00:00Z"
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_snapshot_hash(self) -> AeirProjectSnapshot:
        if tuple(sorted(self.object_versions)) != self.object_versions:
            raise ValueError("snapshot object versions must be sorted")
        if self.snapshot_sha256 != _snapshot_hash(self):
            raise ValueError("AEIR snapshot hash does not match canonical content")
        return self


def compile_aepm(manifest: AepmManifest) -> AeirProjectModel:
    manifest_sha256 = specification_hash(manifest)
    objects: list[AeirObject] = []
    relationship_specs: list[tuple[str, str, str, RelationshipType]] = []

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
        truth_status: TruthStatus = TruthStatus.ASSERTED,
        approval_status: ApprovalStatus = ApprovalStatus.PENDING,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        objects.append(
            AeirObject(
                id=object_id,
                type=object_type,
                name=name,
                description=description,
                status=status,
                lifecycle_status=LifecycleStatus.DRAFT,
                truth_status=truth_status,
                approval_status=approval_status,
                source_refs=(reference,),
                evidence_refs=(),
                relationship_refs=(),
                source=source(reference),
                confidence=1.0 if truth_status is TruthStatus.ASSERTED else 0.75,
                version=AEIR_VERSION,
                created_at=AEIR_CANONICAL_TIMESTAMP,
                created_by=AEIR_SYSTEM_ACTOR,
                updated_at=AEIR_CANONICAL_TIMESTAMP,
                updated_by=AEIR_SYSTEM_ACTOR,
                attributes=attributes or {},
                metadata={},
            )
        )
        if object_id != "PROJ-001":
            relationship_specs.append(
                (
                    f"REL-{len(relationship_specs) + 1:03d}",
                    "PROJ-001",
                    object_id,
                    RelationshipType.CONTAINS,
                )
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
            attributes={
                "responsibilities": list(stakeholder.responsibilities),
                "decision_authority": getattr(stakeholder, "decision_authority", False),
            },
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
                RelationshipType.OWNED_BY,
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
                RelationshipType.OWNED_BY,
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
                truth_status=TruthStatus.ASSUMED,
                approval_status=ApprovalStatus.PENDING,
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
                relationship_type=relationship_type,
                source_object_id=source_id,
                target_object_id=target_id,
                status=AeirStatus.UNVERIFIED,
                lifecycle_status=LifecycleStatus.ACTIVE,
                truth_status=TruthStatus.ASSERTED,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                source_refs=("relationships",),
                evidence_refs=(),
                source=source("relationships"),
                confidence=1.0,
                version=AEIR_VERSION,
                created_at=AEIR_CANONICAL_TIMESTAMP,
                created_by=AEIR_SYSTEM_ACTOR,
                updated_at=AEIR_CANONICAL_TIMESTAMP,
                updated_by=AEIR_SYSTEM_ACTOR,
                valid_from=AEIR_CANONICAL_VALID_FROM,
                valid_to=None,
            )
        )
    bound_objects = tuple(
        item.model_copy(update={"relationship_refs": tuple(relationship_map[item.id])})
        for item in objects
    )
    bound_relationships = tuple(relationships)
    return AeirProjectModel(
        source_manifest_sha256=manifest_sha256,
        objects=bound_objects,
        relationships=bound_relationships,
        model_sha256=_model_hash(manifest_sha256, bound_objects, bound_relationships),
    )


def compile_project_snapshot(
    model: AeirProjectModel,
    *,
    snapshot_id: str = "SNP-0001",
    status: Literal["draft", "approved"] | AeirSnapshotStatus = AeirSnapshotStatus.DRAFT,
) -> AeirProjectSnapshot:
    object_versions = tuple(
        f"{item.id}:{item.version}"
        for item in sorted(model.objects, key=lambda item: item.id)
    )
    project_id = next(item.id for item in model.objects if item.type is AeirObjectType.PROJECT)
    snapshot_status = (
        status
        if isinstance(status, AeirSnapshotStatus)
        else AeirSnapshotStatus.APPROVED
        if status == "approved"
        else AeirSnapshotStatus.DRAFT
    )
    provisional = AeirProjectSnapshot.model_construct(
        schema_version="aeir-snapshot-0.1",
        snapshot_id=snapshot_id,
        project_id=project_id,
        aepm_version="0.1",
        aeir_version="0.1",
        source_model_sha256=model.model_sha256,
        object_versions=object_versions,
        status=snapshot_status,
        created_at=AEIR_CANONICAL_TIMESTAMP,
        snapshot_sha256="0" * 64,
    )
    return AeirProjectSnapshot(
        snapshot_id=snapshot_id,
        project_id=project_id,
        source_model_sha256=model.model_sha256,
        object_versions=object_versions,
        status=snapshot_status,
        created_at=AEIR_CANONICAL_TIMESTAMP,
        snapshot_sha256=_snapshot_hash(provisional),
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


def _snapshot_hash(snapshot: ProjectSnapshot | AeirProjectSnapshot) -> str:
    return specification_hash(snapshot.model_dump(mode="json", exclude={"snapshot_sha256"}))


def rebuild_aeir(
    model: AeirProjectModel, *, objects: tuple[AeirObject, ...]
) -> AeirProjectModel:
    original = {item.id: item for item in model.objects}
    replacements = {item.id: item for item in objects}
    if original.keys() != replacements.keys():
        raise ValueError("AEIR rebuild cannot add or remove object identities")
    if any(original[key].type is not replacements[key].type for key in original):
        raise ValueError("AEIR rebuild cannot change object types")
    ordered = tuple(replacements[item.id] for item in model.objects)
    return AeirProjectModel(
        source_manifest_sha256=model.source_manifest_sha256,
        objects=ordered,
        relationships=model.relationships,
        model_sha256=_model_hash(model.source_manifest_sha256, ordered, model.relationships),
    )
