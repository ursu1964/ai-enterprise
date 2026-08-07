from ai_enterprise.domain.updl_registry import (
    ActorReference,
    InMemoryUPDLRegistry,
    NamespaceDefinition,
    ObjectReference,
    PolicyDefinition,
    PolicyEffect,
    PolicyObligation,
    PropertyDefinition,
    RegistryError,
    RelationshipTypeDefinition,
    ResolutionMode,
    ResolutionStatus,
    TypeDefinition,
)


def _registry() -> InMemoryUPDLRegistry:
    registry = InMemoryUPDLRegistry()
    registry.register_namespace(NamespaceDefinition("commerce"))
    registry.register_namespace(NamespaceDefinition("commerce.orders", parent="commerce"))
    registry.register_type(
        TypeDefinition(
            kind_name="Person",
            properties={
                "display_name": PropertyDefinition("string", required=True),
                "active": PropertyDefinition("boolean", required=True),
            },
        )
    )
    registry.register_type(
        TypeDefinition(
            kind_name="Requirement",
            properties={
                "statement": PropertyDefinition("string", required=True),
                "priority": PropertyDefinition(
                    "enum",
                    required=True,
                    enum=("MUST", "SHOULD", "MAY"),
                ),
                "owner": PropertyDefinition(
                    "reference",
                    required=True,
                    target_kinds=("Person",),
                ),
            },
        )
    )
    return registry


def _relationship_registry() -> InMemoryUPDLRegistry:
    registry = _registry()
    registry.register_relationship_type(
        RelationshipTypeDefinition(
            id="commerce.orders.relationship.owned-by",
            name="ownedBy",
            source_kinds=("Requirement",),
            target_kinds=("Person",),
        )
    )
    return registry


def _actor() -> ActorReference:
    return ActorReference("actor:user:architect")


def _person(registry: InMemoryUPDLRegistry):
    return registry.create_object(
        kind="Person",
        namespace="commerce.orders",
        local_id="PERSON-001",
        spec={"display_name": "Alex Morgan", "active": True},
        actor=_actor(),
    )


def test_updl_registry_assigns_system_metadata_and_content_hash() -> None:
    registry = _registry()
    person = _person(registry)

    assert person.api_version == "updl.ai-enterprise/v1alpha1"
    assert person.metadata.id == "commerce.orders.PERSON-001"
    assert person.metadata.namespace == "commerce.orders"
    assert person.metadata.revision == 1
    assert person.metadata.created_by == _actor()
    assert person.metadata.content_hash.startswith("sha256:")
    assert person.status["validation"] == "VALID"


def test_updl_registry_rejects_unregistered_types_and_invalid_identifiers() -> None:
    registry = _registry()

    try:
        registry.create_object(
            kind="Unknown",
            namespace="commerce.orders",
            local_id="REQ-001",
            spec={},
            actor=_actor(),
        )
    except RegistryError as exc:
        assert exc.code == "TYPE_NOT_REGISTERED"
    else:
        raise AssertionError("unregistered type was accepted")

    try:
        registry.create_object(
            kind="Person",
            namespace="commerce.Orders",
            local_id="PERSON-001",
            spec={"display_name": "Alex Morgan", "active": True},
            actor=_actor(),
        )
    except RegistryError as exc:
        assert exc.code == "IDENTIFIER_INVALID"
    else:
        raise AssertionError("invalid identifier was accepted")


def test_updl_registry_requires_active_namespace_for_object_creation() -> None:
    registry = _registry()
    registry.register_namespace(
        NamespaceDefinition("commerce.archived", parent="commerce", active=False)
    )

    for namespace, code in (
        ("commerce.missing", "NAMESPACE_NOT_FOUND"),
        ("commerce.archived", "NAMESPACE_INACTIVE"),
    ):
        try:
            registry.create_object(
                kind="Person",
                namespace=namespace,
                local_id="PERSON-001",
                spec={"display_name": "Alex Morgan", "active": True},
                actor=_actor(),
            )
        except RegistryError as exc:
            assert exc.code == code
        else:
            raise AssertionError(f"{code} case was accepted")


def test_updl_registry_validates_required_enum_and_reference_properties() -> None:
    registry = _registry()
    person = _person(registry)

    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-017",
        spec={
            "statement": "Suspended users shall not authenticate.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )

    assert requirement.kind == "Requirement"

    for spec, code in (
        ({"priority": "MUST", "owner": {"$ref": {"id": person.metadata.id}}}, "PROPERTY_REQUIRED"),
        (
            {
                "statement": "Invalid enum.",
                "priority": "REQUIRED",
                "owner": {"$ref": {"id": person.metadata.id}},
            },
            "ENUM_VALUE_INVALID",
        ),
        (
            {
                "statement": "Missing owner.",
                "priority": "MUST",
                "owner": {"$ref": {"id": "commerce.orders.PERSON-404"}},
            },
            "REFERENCE_NOT_FOUND",
        ),
    ):
        try:
            registry.create_object(
                kind="Requirement",
                namespace="commerce.orders",
                local_id=f"{code}-REQ",
                spec=spec,
                actor=_actor(),
            )
        except RegistryError as exc:
            assert exc.code == code
        else:
            raise AssertionError(f"{code} case was accepted")


def test_updl_registry_enforces_revision_concurrency_and_system_field_boundary() -> None:
    registry = _registry()
    person = _person(registry)

    updated = registry.update_object(
        object_id=person.metadata.id,
        expected_revision=1,
        semantic_patch={"spec": {"display_name": "Alex M."}},
        actor=_actor(),
    )

    assert updated.metadata.revision == 2
    assert updated.spec["display_name"] == "Alex M."

    try:
        registry.update_object(
            object_id=person.metadata.id,
            expected_revision=1,
            semantic_patch={"spec": {"display_name": "Stale"}},
            actor=_actor(),
        )
    except RegistryError as exc:
        assert exc.code == "REVISION_CONFLICT"
    else:
        raise AssertionError("stale update was accepted")

    try:
        registry.update_object(
            object_id=person.metadata.id,
            expected_revision=2,
            semantic_patch={"lifecycle": {"state": "APPROVED"}},
            actor=_actor(),
        )
    except RegistryError as exc:
        assert exc.code == "SYSTEM_FIELD_FORGED"
    else:
        raise AssertionError("ordinary update mutated lifecycle state")


def test_updl_registry_resolves_exact_latest_and_effective_references() -> None:
    registry = _registry()
    person = _person(registry)
    registry.update_object(
        object_id=person.metadata.id,
        expected_revision=1,
        semantic_patch={"spec": {"display_name": "Alex M."}},
        actor=_actor(),
    )

    latest = registry.resolve_reference(ObjectReference(person.metadata.id))
    exact = registry.resolve_reference(
        ObjectReference(
            person.metadata.id,
            revision=1,
            resolution=ResolutionMode.EXACT,
        )
    )
    effective = registry.resolve_reference(
        ObjectReference(person.metadata.id, resolution=ResolutionMode.EFFECTIVE)
    )

    assert latest.status is ResolutionStatus.RESOLVED
    assert latest.resolved is not None
    assert latest.resolved.metadata.revision == 2
    assert exact.status is ResolutionStatus.RESOLVED
    assert exact.resolved is not None
    assert exact.resolved.metadata.revision == 1
    assert effective.status is ResolutionStatus.REFERENCE_NO_EFFECTIVE_REVISION


def test_updl_registry_combines_policy_effects_and_accumulates_obligations() -> None:
    registry = _registry()
    person = _person(registry)
    registry.register_policy(
        PolicyDefinition(
            id="commerce.orders.POL-production",
            revision=4,
            effect=PolicyEffect.REQUIRE,
            actions=("APPLY_CHANGE",),
            resource_kinds=("Person",),
            obligations=(PolicyObligation("APPROVAL", authority="role:release-manager"),),
        )
    )
    registry.register_policy(
        PolicyDefinition(
            id="commerce.orders.POL-security",
            revision=2,
            effect=PolicyEffect.REQUIRE,
            actions=("APPLY_CHANGE",),
            resource_kinds=("Person",),
            obligations=(PolicyObligation("EVIDENCE", evidence_type="SECURITY_SCAN"),),
        )
    )

    decision = registry.evaluate_policy(
        actor=_actor(),
        action="APPLY_CHANGE",
        resource=person,
        context={"environment": "production"},
    )

    assert decision.decision is PolicyEffect.REQUIRE
    assert decision.matched_policies == (
        ("commerce.orders.POL-production", 4),
        ("commerce.orders.POL-security", 2),
    )
    assert len(decision.obligations) == 2
    assert decision.context_hash.startswith("sha256:")

    registry.register_policy(
        PolicyDefinition(
            id="commerce.orders.POL-freeze",
            revision=1,
            effect=PolicyEffect.DENY,
            actions=("APPLY_CHANGE",),
            resource_kinds=("Person",),
        )
    )
    denied = registry.evaluate_policy(
        actor=_actor(),
        action="APPLY_CHANGE",
        resource=person,
    )

    assert denied.decision is PolicyEffect.DENY
    assert len(denied.obligations) == 2


def test_updl_registry_registers_typed_relationships_as_source_revisions() -> None:
    registry = _relationship_registry()
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-017",
        spec={
            "statement": "Suspended users shall not authenticate.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )

    related = registry.create_relationship(
        relationship_id="commerce.orders.REL-001",
        type_id="commerce.orders.relationship.owned-by",
        source_id=requirement.metadata.id,
        target=ObjectReference(person.metadata.id),
        actor=_actor(),
    )

    assert related.metadata.revision == 2
    assert related.spec == requirement.spec
    assert related.relationships == (
        {
            "id": "commerce.orders.REL-001",
            "type": {"$ref": {"id": "commerce.orders.relationship.owned-by"}},
            "source": {"$ref": {"id": requirement.metadata.id, "revision": 1}},
            "target": {"$ref": {"id": person.metadata.id, "revision": 1}},
        },
    )

    updated = registry.update_object(
        object_id=requirement.metadata.id,
        expected_revision=2,
        semantic_patch={"spec": {"statement": "Suspended users shall be denied authentication."}},
        actor=_actor(),
    )

    assert updated.metadata.revision == 3
    assert updated.relationships == related.relationships


def test_updl_registry_rejects_invalid_relationship_endpoints_atomically() -> None:
    registry = _relationship_registry()
    person = _person(registry)

    try:
        registry.create_relationship(
            relationship_id="commerce.orders.REL-002",
            type_id="commerce.orders.relationship.owned-by",
            source_id=person.metadata.id,
            target=ObjectReference(person.metadata.id),
            actor=_actor(),
        )
    except RegistryError as exc:
        assert exc.code == "RELATIONSHIP_SOURCE_KIND_INVALID"
    else:
        raise AssertionError("invalid source kind was accepted")

    assert registry.get_object(person.metadata.id).metadata.revision == 1

    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-018",
        spec={
            "statement": "Approved payments shall be auditable.",
            "priority": "SHOULD",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )

    try:
        registry.create_relationship(
            relationship_id="commerce.orders.REL-003",
            type_id="commerce.orders.relationship.owned-by",
            source_id=requirement.metadata.id,
            target=ObjectReference(requirement.metadata.id),
            actor=_actor(),
        )
    except RegistryError as exc:
        assert exc.code == "REFERENCE_TYPE_MISMATCH"
    else:
        raise AssertionError("invalid target kind was accepted")

    assert registry.get_object(requirement.metadata.id).metadata.revision == 1
