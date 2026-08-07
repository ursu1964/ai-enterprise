from ai_enterprise.domain.updl_registry import (
    ActorReference,
    AdditionalPropertiesPolicy,
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
    StateDefinition,
    StateMachineDefinition,
    StateTransitionDefinition,
    TransitionClassification,
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


def _state_machine_registry() -> InMemoryUPDLRegistry:
    registry = _registry()
    registry.register_type(
        TypeDefinition(
            kind_name="Deployment",
            properties={
                "artifact": PropertyDefinition("string", required=True),
                "environment": PropertyDefinition("string", required=True),
            },
            lifecycle=ObjectReference("commerce.orders.lifecycle.deployment"),
        )
    )
    registry.register_state_machine(
        StateMachineDefinition(
            id="commerce.orders.lifecycle.deployment",
            applies_to_kind="Deployment",
            initial_state="requested",
            states=(
                StateDefinition("requested"),
                StateDefinition("approved"),
                StateDefinition("deploying"),
                StateDefinition("deployed"),
                StateDefinition("failed"),
                StateDefinition("retired", terminal=True),
            ),
            transitions=(
                StateTransitionDefinition(
                    name="approve",
                    source_states=("requested",),
                    target_state="approved",
                    action_id="commerce.orders.action.approve-deployment",
                    classification=TransitionClassification.APPROVAL,
                ),
                StateTransitionDefinition(
                    name="deploy",
                    source_states=("approved",),
                    target_state="deploying",
                    action_id="commerce.orders.action.deploy-release",
                ),
                StateTransitionDefinition(
                    name="deployment-complete",
                    source_states=("deploying",),
                    target_state="deployed",
                    classification=TransitionClassification.AUTOMATIC,
                ),
                StateTransitionDefinition(
                    name="deployment-failed",
                    source_states=("deploying",),
                    target_state="failed",
                    classification=TransitionClassification.AUTOMATIC,
                ),
                StateTransitionDefinition(
                    name="retire",
                    source_states=("deployed",),
                    target_state="retired",
                    classification=TransitionClassification.ADMINISTRATIVE,
                ),
            ),
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


def _deployment(registry: InMemoryUPDLRegistry):
    return registry.create_object(
        kind="Deployment",
        namespace="commerce.orders",
        local_id="DEP-001",
        spec={"artifact": "artifact:checkout@1.0.0", "environment": "staging"},
        actor=_actor(),
        lifecycle_state="requested",
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


def test_updl_registry_returns_deterministic_schema_validation_result() -> None:
    registry = _registry()
    result = registry.validate_spec(
        "Requirement",
        {
            "statement": 17,
            "priority": "REQUIRED",
            "unknownField": True,
        },
    )

    assert not result.valid
    assert result.type_ref == "Requirement"
    assert result.schema_version == "1.0.0"
    assert result.validator_version == "0.1.0"
    assert [error.code for error in result.errors] == [
        "PROPERTY_UNKNOWN",
        "PROPERTY_TYPE_INVALID",
        "ENUM_VALUE_INVALID",
        "PROPERTY_REQUIRED",
    ]
    assert [error.path for error in result.errors] == [
        "spec.unknownField",
        "spec.statement",
        "spec.priority",
        "spec.owner",
    ]
    assert result.errors[1].expected == "string"
    assert result.errors[1].actual == "integer"
    assert result.warnings == ()


def test_updl_registry_unknown_property_policy_can_warn_or_allow() -> None:
    registry = InMemoryUPDLRegistry()
    registry.register_namespace(NamespaceDefinition("commerce"))
    registry.register_type(
        TypeDefinition(
            kind_name="Capability",
            properties={"name": PropertyDefinition("string", required=True)},
            additional_properties=AdditionalPropertiesPolicy.WARN,
        )
    )

    warning_result = registry.validate_spec(
        "Capability",
        {"name": "Billing", "extra": True},
    )

    assert warning_result.valid
    assert [warning.code for warning in warning_result.warnings] == ["PROPERTY_UNKNOWN"]
    assert warning_result.warnings[0].path == "spec.extra"

    registry.register_type(
        TypeDefinition(
            kind_name="OpenCapability",
            properties={"name": PropertyDefinition("string", required=True)},
            additional_properties=AdditionalPropertiesPolicy.ALLOW,
        )
    )

    allow_result = registry.validate_spec(
        "OpenCapability",
        {"name": "Billing", "extra": True},
    )

    assert allow_result.valid
    assert allow_result.errors == ()
    assert allow_result.warnings == ()


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


def test_updl_registry_registers_state_machine_and_executes_declared_transition() -> None:
    registry = _state_machine_registry()
    deployment = _deployment(registry)

    decision = registry.evaluate_state_transition(
        object_id=deployment.metadata.id,
        transition_name="approve",
        expected_revision=1,
        action_id="commerce.orders.action.approve-deployment",
    )

    assert decision.permitted
    assert decision.state_machine_id == "commerce.orders.lifecycle.deployment"
    assert decision.current_state == "requested"
    assert decision.target_state == "approved"

    approved = registry.transition_object(
        object_id=deployment.metadata.id,
        expected_revision=1,
        transition_name="approve",
        action_id="commerce.orders.action.approve-deployment",
        actor=_actor(),
    )

    assert approved.metadata.revision == 2
    assert approved.lifecycle.state == "approved"
    assert approved.spec == deployment.spec


def test_updl_registry_rejects_invalid_initial_state_for_governed_object() -> None:
    registry = _state_machine_registry()

    try:
        registry.create_object(
            kind="Deployment",
            namespace="commerce.orders",
            local_id="DEP-002",
            spec={"artifact": "artifact:checkout@1.0.0", "environment": "staging"},
            actor=_actor(),
            lifecycle_state="approved",
        )
    except RegistryError as exc:
        assert exc.code == "INITIAL_STATE_INVALID"
    else:
        raise AssertionError("invalid initial lifecycle state was accepted")


def test_updl_registry_denies_undeclared_or_action_mismatched_transition() -> None:
    registry = _state_machine_registry()
    deployment = _deployment(registry)

    missing = registry.evaluate_state_transition(
        object_id=deployment.metadata.id,
        transition_name="deploy",
        expected_revision=1,
    )

    assert not missing.permitted
    assert [reason.code for reason in missing.reasons] == ["TRANSITION_NOT_FOUND"]

    mismatched = registry.evaluate_state_transition(
        object_id=deployment.metadata.id,
        transition_name="approve",
        expected_revision=1,
        action_id="commerce.orders.action.deploy-release",
    )

    assert not mismatched.permitted
    assert [reason.code for reason in mismatched.reasons] == ["TRANSITION_ACTION_MISMATCH"]
    assert registry.get_object(deployment.metadata.id).metadata.revision == 1


def test_updl_registry_rejects_stale_and_terminal_state_transition() -> None:
    registry = _state_machine_registry()
    deployment = _deployment(registry)
    approved = registry.transition_object(
        object_id=deployment.metadata.id,
        expected_revision=1,
        transition_name="approve",
        action_id="commerce.orders.action.approve-deployment",
        actor=_actor(),
    )

    stale = registry.evaluate_state_transition(
        object_id=deployment.metadata.id,
        transition_name="deploy",
        expected_revision=1,
        action_id="commerce.orders.action.deploy-release",
    )

    assert not stale.permitted
    assert [reason.code for reason in stale.reasons] == ["STATE_VERSION_CONFLICT"]
    assert approved.metadata.revision == 2

    deploying = registry.transition_object(
        object_id=deployment.metadata.id,
        expected_revision=2,
        transition_name="deploy",
        action_id="commerce.orders.action.deploy-release",
        actor=_actor(),
    )
    deployed = registry.transition_object(
        object_id=deployment.metadata.id,
        expected_revision=3,
        transition_name="deployment-complete",
        actor=_actor(),
    )
    retired = registry.transition_object(
        object_id=deployment.metadata.id,
        expected_revision=4,
        transition_name="retire",
        actor=_actor(),
    )

    assert deploying.lifecycle.state == "deploying"
    assert deployed.lifecycle.state == "deployed"
    assert retired.lifecycle.state == "retired"

    terminal = registry.evaluate_state_transition(
        object_id=deployment.metadata.id,
        transition_name="deploy",
        expected_revision=5,
    )

    assert not terminal.permitted
    assert [reason.code for reason in terminal.reasons] == ["TERMINAL_STATE_REACHED"]


def test_updl_registry_rejects_invalid_state_machine_definitions() -> None:
    registry = _registry()
    registry.register_type(
        TypeDefinition(
            kind_name="Deployment",
            properties={"artifact": PropertyDefinition("string", required=True)},
            lifecycle=ObjectReference("commerce.orders.lifecycle.bad"),
        )
    )

    try:
        registry.register_state_machine(
            StateMachineDefinition(
                id="commerce.orders.lifecycle.bad",
                applies_to_kind="Deployment",
                initial_state="missing",
                states=(StateDefinition("requested"),),
                transitions=(),
            )
        )
    except RegistryError as exc:
        assert exc.code == "INITIAL_STATE_INVALID"
    else:
        raise AssertionError("state machine with missing initial state was accepted")

    try:
        registry.register_state_machine(
            StateMachineDefinition(
                id="commerce.orders.lifecycle.bad",
                applies_to_kind="Deployment",
                initial_state="requested",
                states=(StateDefinition("requested"), StateDefinition("retired", terminal=True)),
                transitions=(
                    StateTransitionDefinition(
                        name="restart",
                        source_states=("retired",),
                        target_state="requested",
                    ),
                ),
            )
        )
    except RegistryError as exc:
        assert exc.code == "TERMINAL_STATE_REACHED"
    else:
        raise AssertionError("ordinary transition from terminal state was accepted")
