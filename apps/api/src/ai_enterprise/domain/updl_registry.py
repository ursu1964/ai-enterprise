from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from ai_enterprise.domain.specification.kernel import specification_hash

API_VERSION = "updl.ai-enterprise/v1alpha1"
IDENTIFIER = re.compile(
    r"^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+\.[A-Za-z0-9][A-Za-z0-9_-]*$"
)
NAMESPACE = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)*$")
RESERVED_NAMESPACE_ROOTS = frozenset({"core", "system", "updl", "ai-enterprise"})
PRIMITIVE_TYPES = frozenset(
    {
        "string",
        "boolean",
        "integer",
        "decimal",
        "timestamp",
        "date",
        "duration",
        "map",
        "object",
    }
)


class RegistryError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class ResolutionMode(StrEnum):
    EXACT = "EXACT"
    LATEST = "LATEST"
    LATEST_APPROVED = "LATEST_APPROVED"
    EFFECTIVE = "EFFECTIVE"
    SNAPSHOT = "SNAPSHOT"


class ResolutionStatus(StrEnum):
    RESOLVED = "RESOLVED"
    REFERENCE_NOT_FOUND = "REFERENCE_NOT_FOUND"
    REFERENCE_REVISION_NOT_FOUND = "REFERENCE_REVISION_NOT_FOUND"
    REFERENCE_TYPE_MISMATCH = "REFERENCE_TYPE_MISMATCH"
    REFERENCE_NO_EFFECTIVE_REVISION = "REFERENCE_NO_EFFECTIVE_REVISION"


class PolicyEffect(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE = "REQUIRE"
    WARN = "WARN"
    ESCALATE = "ESCALATE"


class EpistemicStatus(StrEnum):
    OBSERVED = "OBSERVED"
    DECLARED = "DECLARED"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    ASSUMED = "ASSUMED"
    PREDICTED = "PREDICTED"
    UNKNOWN = "UNKNOWN"


class ValidationStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    VALID = "VALID"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class ActorReference:
    id: str


@dataclass(frozen=True, slots=True)
class ObjectReference:
    id: str
    revision: int | None = None
    resolution: ResolutionMode = ResolutionMode.LATEST


@dataclass(frozen=True, slots=True)
class PropertyDefinition:
    type: str
    required: bool = False
    enum: tuple[str, ...] = ()
    target_kinds: tuple[str, ...] = ()
    item_type: str | None = None
    nullable: bool = False
    default: Any = None


@dataclass(frozen=True, slots=True)
class TypeDefinition:
    kind_name: str
    properties: dict[str, PropertyDefinition]
    lifecycle: ObjectReference | None = None
    allowed_relationships: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Metadata:
    id: str
    namespace: str
    revision: int
    created_at: datetime
    created_by: ActorReference
    updated_at: datetime
    updated_by: ActorReference
    content_hash: str
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LifecycleState:
    state: str = "DRAFT"


@dataclass(frozen=True, slots=True)
class Epistemics:
    status: EpistemicStatus = EpistemicStatus.DECLARED
    confidence: float | None = None
    reason: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ObjectEnvelope:
    kind: str
    metadata: Metadata
    spec: dict[str, Any]
    api_version: str = API_VERSION
    relationships: tuple[dict[str, Any], ...] = ()
    governance: dict[str, Any] = field(default_factory=lambda: {"owner": None})
    provenance: dict[str, Any] = field(default_factory=lambda: {"sources": []})
    epistemics: Epistemics = field(default_factory=Epistemics)
    lifecycle: LifecycleState = field(default_factory=LifecycleState)
    status: dict[str, Any] = field(
        default_factory=lambda: {"validation": ValidationStatus.UNKNOWN.value}
    )

    def canonical_document(self) -> dict[str, Any]:
        return {
            "apiVersion": self.api_version,
            "kind": self.kind,
            "metadata": {
                "id": self.metadata.id,
                "namespace": self.metadata.namespace,
                "revision": self.metadata.revision,
                "labels": self.metadata.labels,
                "annotations": self.metadata.annotations,
                "createdAt": self.metadata.created_at.isoformat(),
                "createdBy": self.metadata.created_by.id,
                "updatedAt": self.metadata.updated_at.isoformat(),
                "updatedBy": self.metadata.updated_by.id,
            },
            "spec": self.spec,
            "relationships": list(self.relationships),
            "governance": self.governance,
            "provenance": self.provenance,
            "epistemics": {
                "status": self.epistemics.status.value,
                "confidence": self.epistemics.confidence,
                "reason": list(self.epistemics.reason),
            },
            "lifecycle": {"state": self.lifecycle.state},
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    status: ResolutionStatus
    requested: ObjectReference
    resolved: ObjectEnvelope | None = None
    code: str | None = None


@dataclass(frozen=True, slots=True)
class PolicyObligation:
    type: str
    authority: str | None = None
    evidence_type: str | None = None


@dataclass(frozen=True, slots=True)
class PolicyDefinition:
    id: str
    revision: int
    effect: PolicyEffect
    actions: tuple[str, ...]
    resource_kinds: tuple[str, ...] = ()
    obligations: tuple[PolicyObligation, ...] = ()

    def applies_to(self, action: str, resource: ObjectEnvelope) -> bool:
        return action in self.actions and (
            not self.resource_kinds or resource.kind in self.resource_kinds
        )


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    decision: PolicyEffect
    matched_policies: tuple[tuple[str, int], ...]
    obligations: tuple[PolicyObligation, ...]
    context_hash: str


class InMemoryUPDLRegistry:
    def __init__(self) -> None:
        self._types: dict[str, TypeDefinition] = {}
        self._objects: dict[str, list[ObjectEnvelope]] = {}
        self._policies: dict[str, PolicyDefinition] = {}

    def register_type(self, definition: TypeDefinition) -> None:
        if not definition.kind_name:
            raise RegistryError("TYPE_INVALID", "type kindName is required")
        self._types[definition.kind_name] = definition

    def register_policy(self, definition: PolicyDefinition) -> None:
        require_identifier(definition.id)
        self._policies[definition.id] = definition

    def create_object(
        self,
        *,
        kind: str,
        namespace: str,
        local_id: str,
        spec: dict[str, Any],
        actor: ActorReference,
        lifecycle_state: str = "DRAFT",
    ) -> ObjectEnvelope:
        object_id = f"{namespace}.{local_id}"
        require_identifier(object_id)
        require_namespace(namespace)
        if namespace.split(".", 1)[0] in RESERVED_NAMESPACE_ROOTS:
            raise RegistryError("NAMESPACE_RESERVED", f"reserved namespace: {namespace}")
        if object_id in self._objects:
            raise RegistryError("IDENTITY_CONFLICT", f"object already exists: {object_id}")
        self._validate_spec(kind, spec)
        now = datetime.now(UTC)
        envelope = self._object_envelope(
            kind=kind,
            object_id=object_id,
            namespace=namespace,
            revision=1,
            spec=spec,
            actor=actor,
            created_at=now,
            updated_at=now,
            lifecycle_state=lifecycle_state,
        )
        self._objects[object_id] = [envelope]
        return envelope

    def update_object(
        self,
        *,
        object_id: str,
        expected_revision: int,
        semantic_patch: dict[str, Any],
        actor: ActorReference,
    ) -> ObjectEnvelope:
        current = self.get_object(object_id)
        if current.metadata.revision != expected_revision:
            raise RegistryError(
                "REVISION_CONFLICT",
                f"expected {expected_revision}, found {current.metadata.revision}",
            )
        forbidden = {"metadata", "apiVersion", "kind", "lifecycle"}
        forged = forbidden & set(semantic_patch)
        if forged:
            raise RegistryError(
                "SYSTEM_FIELD_FORGED",
                f"ordinary update cannot modify system fields: {sorted(forged)}",
            )
        spec = {**current.spec, **semantic_patch.get("spec", {})}
        self._validate_spec(current.kind, spec)
        updated = self._object_envelope(
            kind=current.kind,
            object_id=current.metadata.id,
            namespace=current.metadata.namespace,
            revision=current.metadata.revision + 1,
            spec=spec,
            actor=actor,
            created_at=current.metadata.created_at,
            updated_at=datetime.now(UTC),
            lifecycle_state=current.lifecycle.state,
        )
        self._objects[object_id].append(updated)
        return updated

    def get_object(self, object_id: str, revision: int | None = None) -> ObjectEnvelope:
        revisions = self._objects.get(object_id)
        if not revisions:
            raise RegistryError("OBJECT_NOT_FOUND", object_id)
        if revision is None:
            return revisions[-1]
        for candidate in revisions:
            if candidate.metadata.revision == revision:
                return candidate
        raise RegistryError("REFERENCE_REVISION_NOT_FOUND", f"{object_id}@{revision}")

    def resolve_reference(
        self,
        reference: ObjectReference,
        *,
        target_kinds: tuple[str, ...] = (),
    ) -> ResolutionResult:
        revisions = self._objects.get(reference.id)
        if not revisions:
            return ResolutionResult(
                ResolutionStatus.REFERENCE_NOT_FOUND,
                reference,
                code=ResolutionStatus.REFERENCE_NOT_FOUND.value,
            )
        resolved: ObjectEnvelope | None
        if reference.revision is not None or reference.resolution is ResolutionMode.EXACT:
            revision = reference.revision
            if revision is None:
                return ResolutionResult(
                    ResolutionStatus.REFERENCE_REVISION_NOT_FOUND,
                    reference,
                    code=ResolutionStatus.REFERENCE_REVISION_NOT_FOUND.value,
                )
            resolved = next(
                (candidate for candidate in revisions if candidate.metadata.revision == revision),
                None,
            )
            if resolved is None:
                return ResolutionResult(
                    ResolutionStatus.REFERENCE_REVISION_NOT_FOUND,
                    reference,
                    code=ResolutionStatus.REFERENCE_REVISION_NOT_FOUND.value,
                )
        elif reference.resolution is ResolutionMode.LATEST:
            resolved = revisions[-1]
        elif reference.resolution in {
            ResolutionMode.LATEST_APPROVED,
            ResolutionMode.EFFECTIVE,
        }:
            resolved = next(
                (
                    candidate
                    for candidate in reversed(revisions)
                    if candidate.lifecycle.state == "APPROVED"
                ),
                None,
            )
            if resolved is None:
                return ResolutionResult(
                    ResolutionStatus.REFERENCE_NO_EFFECTIVE_REVISION,
                    reference,
                    code=ResolutionStatus.REFERENCE_NO_EFFECTIVE_REVISION.value,
                )
        else:
            return ResolutionResult(
                ResolutionStatus.REFERENCE_REVISION_NOT_FOUND,
                reference,
                code="SNAPSHOT_RESOLUTION_REQUIRES_SNAPSHOT",
            )
        if target_kinds and resolved.kind not in target_kinds:
            return ResolutionResult(
                ResolutionStatus.REFERENCE_TYPE_MISMATCH,
                reference,
                code=ResolutionStatus.REFERENCE_TYPE_MISMATCH.value,
            )
        return ResolutionResult(ResolutionStatus.RESOLVED, reference, resolved)

    def evaluate_policy(
        self,
        *,
        actor: ActorReference,
        action: str,
        resource: ObjectEnvelope,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        matched = tuple(
            policy
            for policy in sorted(self._policies.values(), key=lambda item: item.id)
            if policy.applies_to(action, resource)
        )
        decision = _combine_effects(tuple(policy.effect for policy in matched))
        obligations = tuple(
            obligation for policy in matched for obligation in policy.obligations
        )
        context_hash = specification_hash(
            {
                "actor": actor.id,
                "action": action,
                "resource": {
                    "id": resource.metadata.id,
                    "revision": resource.metadata.revision,
                    "kind": resource.kind,
                },
                "context": context or {},
                "policies": [
                    {
                        "id": policy.id,
                        "revision": policy.revision,
                        "effect": policy.effect.value,
                    }
                    for policy in matched
                ],
            }
        )
        return PolicyDecision(
            decision=decision,
            matched_policies=tuple((policy.id, policy.revision) for policy in matched),
            obligations=obligations,
            context_hash=f"sha256:{context_hash}",
        )

    def _validate_spec(self, kind: str, spec: dict[str, Any]) -> None:
        type_definition = self._types.get(kind)
        if type_definition is None:
            raise RegistryError("TYPE_NOT_REGISTERED", kind)
        for name, property_definition in type_definition.properties.items():
            if name not in spec:
                if property_definition.required and property_definition.default is None:
                    raise RegistryError("PROPERTY_REQUIRED", name)
                continue
            value = spec[name]
            if value is None:
                if not property_definition.nullable:
                    raise RegistryError("PROPERTY_TYPE_INVALID", f"{name} cannot be null")
                continue
            _validate_value_type(name, value, property_definition)
            if property_definition.type == "reference":
                reference = _reference_from_value(name, value)
                resolution = self.resolve_reference(
                    reference,
                    target_kinds=property_definition.target_kinds,
                )
                if resolution.status is not ResolutionStatus.RESOLVED:
                    raise RegistryError(resolution.status.value, f"{name}: {resolution.code}")

    def _object_envelope(
        self,
        *,
        kind: str,
        object_id: str,
        namespace: str,
        revision: int,
        spec: dict[str, Any],
        actor: ActorReference,
        created_at: datetime,
        updated_at: datetime,
        lifecycle_state: str,
    ) -> ObjectEnvelope:
        metadata_without_hash = Metadata(
            id=object_id,
            namespace=namespace,
            revision=revision,
            created_at=created_at,
            created_by=actor,
            updated_at=updated_at,
            updated_by=actor,
            content_hash="",
        )
        envelope = ObjectEnvelope(
            kind=kind,
            metadata=metadata_without_hash,
            spec=spec,
            lifecycle=LifecycleState(lifecycle_state),
            status={"validation": ValidationStatus.VALID.value},
        )
        content_hash = f"sha256:{specification_hash(envelope.canonical_document())}"
        return replace(
            envelope,
            metadata=replace(metadata_without_hash, content_hash=content_hash),
        )


def require_identifier(value: str) -> None:
    if IDENTIFIER.fullmatch(value) is None:
        raise RegistryError("IDENTIFIER_INVALID", value)


def require_namespace(value: str) -> None:
    if NAMESPACE.fullmatch(value) is None:
        raise RegistryError("NAMESPACE_INVALID", value)


def _validate_value_type(
    name: str,
    value: Any,
    property_definition: PropertyDefinition,
) -> None:
    property_type = property_definition.type
    if property_type == "string" and not isinstance(value, str):
        raise RegistryError("PROPERTY_TYPE_INVALID", name)
    if property_type == "boolean" and not isinstance(value, bool):
        raise RegistryError("PROPERTY_TYPE_INVALID", name)
    if property_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        raise RegistryError("PROPERTY_TYPE_INVALID", name)
    if property_type == "decimal" and (
        not isinstance(value, int | float) or isinstance(value, bool)
    ):
        raise RegistryError("PROPERTY_TYPE_INVALID", name)
    if property_type == "enum":
        if not isinstance(value, str) or value not in property_definition.enum:
            raise RegistryError("ENUM_VALUE_INVALID", f"{name}: {value!r}")
    if property_type == "reference":
        _reference_from_value(name, value)
    if property_type == "list" and not isinstance(value, list):
        raise RegistryError("PROPERTY_TYPE_INVALID", name)
    if property_type == "map" and not isinstance(value, dict):
        raise RegistryError("PROPERTY_TYPE_INVALID", name)
    if property_type not in PRIMITIVE_TYPES | {"enum", "reference", "list"}:
        raise RegistryError("PROPERTY_TYPE_UNKNOWN", property_type)


def _reference_from_value(name: str, value: Any) -> ObjectReference:
    if isinstance(value, ObjectReference):
        return value
    if isinstance(value, dict) and isinstance(value.get("$ref"), dict):
        ref = value["$ref"]
        identifier = ref.get("id")
        if not isinstance(identifier, str):
            raise RegistryError("REFERENCE_INVALID", name)
        return ObjectReference(
            id=identifier,
            revision=ref.get("revision"),
            resolution=ResolutionMode(ref.get("resolution", ResolutionMode.LATEST.value)),
        )
    raise RegistryError("REFERENCE_INVALID", name)


def _combine_effects(effects: tuple[PolicyEffect, ...]) -> PolicyEffect:
    if not effects:
        return PolicyEffect.ALLOW
    precedence = (
        PolicyEffect.DENY,
        PolicyEffect.ESCALATE,
        PolicyEffect.REQUIRE,
        PolicyEffect.WARN,
        PolicyEffect.ALLOW,
    )
    for effect in precedence:
        if effect in effects:
            return effect
    return PolicyEffect.ALLOW
