from ai_enterprise.domain.updl_registry import (
    ActorReference,
    AdditionalPropertiesPolicy,
    AdoptionScope,
    ChangeAdoptionCompletionResult,
    ChangeAdoptionDefinition,
    ChangeAdoptionFailureType,
    ChangeAdoptionStatus,
    ChangeAdoptionVerificationResult,
    ConditionClauseType,
    ConditionDependency,
    ConditionDependencyType,
    ConditionFailureDetectionMode,
    ConditionFailureEffect,
    ConditionFailurePolicy,
    ConditionFailureScope,
    ConditionFailureSeverity,
    ConditionFailureTransitionType,
    ConditionOutcome,
    ConstraintDefinition,
    ConstraintEvaluationResult,
    ConstraintRequirement,
    ConstraintViolationState,
    ControlCriticality,
    ControlDefinition,
    ControlEffectivenessResult,
    ControlEnforcementMode,
    ControlEnforcementOutcome,
    ControlEvaluationOutcome,
    ControlExecutionModality,
    ControlExecutionStatus,
    ControlResult,
    ControlState,
    ControlType,
    DecisionAdvice,
    DecisionAuthorityRequirement,
    DecisionConstraint,
    DecisionDefinition,
    DecisionEffect,
    DecisionEvaluationStatus,
    DecisionEvidenceRequirement,
    DecisionOutcome,
    DecisionQuestion,
    DecisionRequest,
    DecisionType,
    InMemoryUPDLRegistry,
    LikelihoodType,
    NamespaceDefinition,
    ObjectReference,
    ObligationActivationOutcome,
    ObligationAssignmentStrategy,
    ObligationBreach,
    ObligationDefinition,
    ObligationDuty,
    ObligationFulfillmentResult,
    ObligationLifecycleState,
    ObligationResponsibility,
    ObligationSubject,
    ObligationTiming,
    ObligationTrigger,
    ObligationTriggerSource,
    PlanLifecycleState,
    PlanValidationResult,
    PolicyDefinition,
    PolicyEffect,
    PolicyObligation,
    PreemptionDefinition,
    PreemptionEffect,
    PreemptionMode,
    PreemptionRequest,
    PriorityClass,
    PriorityDefinition,
    PropertyDefinition,
    RecurrenceClassification,
    RecurrenceConsequence,
    RecurrenceDefinition,
    RecurrenceDeterminationSource,
    RecurrenceEffectiveSeverity,
    RecurrenceSeverityPolicy,
    RecurrenceState,
    RegistryError,
    RelationshipCardinality,
    RelationshipTypeDefinition,
    RemediationAcceptanceResult,
    RemediationDeadlines,
    RemediationDefinition,
    RemediationEffectivenessResult,
    RemediationPriority,
    RemediationSeverity,
    RemediationStatus,
    RemediationTrigger,
    RemediationTriggerType,
    RemediationVerificationResult,
    ReservationDefinition,
    ReservationLifecycleState,
    ResolutionMode,
    ResolutionStatus,
    RiskAcceptanceStatus,
    RiskDefinition,
    RiskDomain,
    RiskLevel,
    RiskLifecycleState,
    RiskScenario,
    RiskTreatmentStatus,
    RiskTreatmentStrategy,
    SemanticConditionClause,
    SemanticConditionDefinition,
    StateDefinition,
    StateMachineDefinition,
    StateTransitionDefinition,
    TaskCompletionResult,
    TaskDependency,
    TaskDependencyType,
    TaskLifecycleState,
    TaskOutputDefinition,
    TaskOutputSource,
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
    registry.register_type(
        TypeDefinition(
            kind_name="Evidence",
            properties={
                "evidence_type": PropertyDefinition("string", required=True),
                "summary": PropertyDefinition("string", required=True),
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


def _requirement(registry: InMemoryUPDLRegistry, local_id: str, statement: str):
    try:
        person = registry.get_object("commerce.orders.PERSON-001")
    except RegistryError:
        person = _person(registry)
    return registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id=local_id,
        spec={
            "statement": statement,
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )


def _evidence(registry: InMemoryUPDLRegistry, local_id: str, evidence_type: str):
    return registry.create_object(
        kind="Evidence",
        namespace="commerce.orders",
        local_id=local_id,
        spec={
            "evidence_type": evidence_type,
            "summary": f"{evidence_type} evidence",
        },
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
            "lifecycle": {"state": "ACTIVE"},
        },
    )
    audit_records = registry.list_relationship_audit_records("commerce.orders.REL-001")
    assert len(audit_records) == 1
    assert audit_records[0].id == "RELAUD-000001"
    assert audit_records[0].action == "RELATIONSHIP_CREATED"
    assert audit_records[0].relationship_type_id == "commerce.orders.relationship.owned-by"
    assert audit_records[0].source_id == requirement.metadata.id
    assert audit_records[0].target_id == person.metadata.id
    assert audit_records[0].new_source_revision == 2

    updated = registry.update_object(
        object_id=requirement.metadata.id,
        expected_revision=2,
        semantic_patch={"spec": {"statement": "Suspended users shall be denied authentication."}},
        actor=_actor(),
    )

    assert updated.metadata.revision == 3
    assert updated.relationships == related.relationships


def test_updl_registry_enforces_relationship_cardinality_and_evidence() -> None:
    registry = _registry()
    registry.register_relationship_type(
        RelationshipTypeDefinition(
            id="commerce.orders.relationship.accountable-to",
            name="accountableTo",
            source_kinds=("Requirement",),
            target_kinds=("Person",),
            cardinality=RelationshipCardinality.MANY_TO_ONE,
            required_evidence=("ownership_decision",),
        )
    )
    person = _person(registry)
    backup_owner = registry.create_object(
        kind="Person",
        namespace="commerce.orders",
        local_id="PERSON-002",
        spec={"display_name": "Jamie Lee", "active": True},
        actor=_actor(),
    )
    evidence = registry.create_object(
        kind="Evidence",
        namespace="commerce.orders",
        local_id="EVIDENCE-001",
        spec={
            "evidence_type": "ownership_decision",
            "summary": "Architecture owner decision record.",
        },
        actor=_actor(),
    )
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-019",
        spec={
            "statement": "Privileged access shall be reviewed.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )

    try:
        registry.create_relationship(
            relationship_id="commerce.orders.REL-004",
            type_id="commerce.orders.relationship.accountable-to",
            source_id=requirement.metadata.id,
            target=ObjectReference(person.metadata.id),
            actor=_actor(),
        )
    except RegistryError as exc:
        assert exc.code == "RELATIONSHIP_EVIDENCE_INCOMPLETE"
    else:
        raise AssertionError("relationship without required evidence was accepted")

    related = registry.create_relationship(
        relationship_id="commerce.orders.REL-005",
        type_id="commerce.orders.relationship.accountable-to",
        source_id=requirement.metadata.id,
        target=ObjectReference(person.metadata.id),
        actor=_actor(),
        evidence={"ownership_decision": ObjectReference(evidence.metadata.id)},
    )

    assert related.metadata.revision == 2
    assert related.relationships[0]["evidence"] == [
        {
            "type": "ownership_decision",
            "$ref": {"id": evidence.metadata.id, "revision": 1},
        },
    ]
    audit_records = registry.list_relationship_audit_records("commerce.orders.REL-005")
    assert audit_records[0].evidence_types == ("ownership_decision",)

    try:
        registry.create_relationship(
            relationship_id="commerce.orders.REL-006",
            type_id="commerce.orders.relationship.accountable-to",
            source_id=requirement.metadata.id,
            target=ObjectReference(backup_owner.metadata.id),
            actor=_actor(),
            evidence={"ownership_decision": ObjectReference(evidence.metadata.id)},
        )
    except RegistryError as exc:
        assert exc.code == "RELATIONSHIP_CARDINALITY_VIOLATION"
    else:
        raise AssertionError("relationship cardinality was not enforced")


def test_updl_registry_evaluates_semantic_conditions_over_relationships() -> None:
    registry = _relationship_registry()
    registry.register_condition(
        SemanticConditionDefinition(
            id="commerce.orders.condition.requirement-owned",
            name="requirementOwned",
            subject_kinds=("Requirement",),
            clauses=(
                SemanticConditionClause(
                    ConditionClauseType.SPEC_EQUALS,
                    path="priority",
                    expected="MUST",
                ),
                SemanticConditionClause(
                    ConditionClauseType.RELATIONSHIP_COUNT,
                    relationship_type_id="commerce.orders.relationship.owned-by",
                    target_kind="Person",
                    min_count=1,
                    max_count=1,
                ),
            ),
        )
    )
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-020",
        spec={
            "statement": "Payment audit requirements shall have an owner.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )

    incomplete = registry.evaluate_condition(
        condition_id="commerce.orders.condition.requirement-owned",
        subject_id=requirement.metadata.id,
    )

    assert incomplete.outcome is ConditionOutcome.NOT_SATISFIED
    assert [finding.code for finding in incomplete.findings] == [
        "CONDITION_RELATIONSHIP_NOT_SATISFIED"
    ]
    assert incomplete.proof_hash.startswith("sha256:")

    registry.create_relationship(
        relationship_id="commerce.orders.REL-007",
        type_id="commerce.orders.relationship.owned-by",
        source_id=requirement.metadata.id,
        target=ObjectReference(person.metadata.id),
        actor=_actor(),
    )

    satisfied = registry.evaluate_condition(
        condition_id="commerce.orders.condition.requirement-owned",
        subject_id=requirement.metadata.id,
    )

    assert satisfied.outcome is ConditionOutcome.SATISFIED
    assert satisfied.findings == ()
    assert satisfied.subject_revision == 2
    assert satisfied.proof["inputs"][2]["count"] == 1
    assert satisfied.canonical_document()["outcome"] == "SATISFIED"


def test_updl_registry_preserves_unknown_semantic_condition_inputs() -> None:
    registry = _relationship_registry()
    registry.register_condition(
        SemanticConditionDefinition(
            id="commerce.orders.condition.requirement-classified",
            name="requirementClassified",
            subject_kinds=("Requirement",),
            clauses=(
                SemanticConditionClause(
                    ConditionClauseType.SPEC_EQUALS,
                    path="classification",
                    expected="regulated",
                ),
            ),
        )
    )
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-021",
        spec={
            "statement": "Records retention shall be classified.",
            "priority": "SHOULD",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )

    evaluation = registry.evaluate_condition(
        condition_id="commerce.orders.condition.requirement-classified",
        subject_id=requirement.metadata.id,
    )
    missing_subject = registry.evaluate_condition(
        condition_id="commerce.orders.condition.requirement-classified",
        subject_id="commerce.orders.REQ-404",
    )

    assert evaluation.outcome is ConditionOutcome.UNKNOWN
    assert [finding.code for finding in evaluation.findings] == ["CONDITION_INPUT_UNKNOWN"]
    assert missing_subject.outcome is ConditionOutcome.UNKNOWN
    assert [finding.code for finding in missing_subject.findings] == [
        "CONDITION_SUBJECT_NOT_FOUND"
    ]


def test_updl_registry_evaluates_must_hold_constraints_and_records_violation() -> None:
    registry = _relationship_registry()
    registry.register_condition(
        SemanticConditionDefinition(
            id="commerce.orders.condition.requirement-must-priority",
            name="requirementMustPriority",
            subject_kinds=("Requirement",),
            clauses=(
                SemanticConditionClause(
                    ConditionClauseType.SPEC_EQUALS,
                    path="priority",
                    expected="MUST",
                ),
            ),
        )
    )
    registry.register_constraint(
        ConstraintDefinition(
            id="commerce.orders.constraint.requirement-must-priority",
            name="requirementMustPriority",
            requirement=ConstraintRequirement.MUST_HOLD,
            condition_id="commerce.orders.condition.requirement-must-priority",
            subject_kinds=("Requirement",),
            severity="HIGH",
        )
    )
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-026",
        spec={
            "statement": "Hard constraints shall detect non-MUST priority.",
            "priority": "SHOULD",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )

    evaluation = registry.evaluate_constraint(
        constraint_id="commerce.orders.constraint.requirement-must-priority",
        subject_id=requirement.metadata.id,
    )
    repeated = registry.evaluate_constraint(
        constraint_id="commerce.orders.constraint.requirement-must-priority",
        subject_id=requirement.metadata.id,
    )
    violations = registry.list_constraint_violations(
        constraint_id="commerce.orders.constraint.requirement-must-priority",
        subject_id=requirement.metadata.id,
        state=ConstraintViolationState.OPEN,
    )

    assert evaluation.result is ConstraintEvaluationResult.VIOLATED
    assert repeated.violation_id == evaluation.violation_id
    assert len(violations) == 1
    assert violations[0].severity == "HIGH"
    assert violations[0].constraint_version == "1.0.0"
    assert evaluation.proof_hash.startswith("sha256:")
    assert evaluation.canonical_document()["result"] == "VIOLATED"


def test_updl_registry_evaluates_must_not_hold_constraints() -> None:
    registry = _relationship_registry()
    registry.register_condition(
        SemanticConditionDefinition(
            id="commerce.orders.condition.requirement-is-may",
            name="requirementIsMay",
            subject_kinds=("Requirement",),
            clauses=(
                SemanticConditionClause(
                    ConditionClauseType.SPEC_EQUALS,
                    path="priority",
                    expected="MAY",
                ),
            ),
        )
    )
    registry.register_constraint(
        ConstraintDefinition(
            id="commerce.orders.constraint.requirement-must-not-be-may",
            name="requirementMustNotBeMay",
            requirement=ConstraintRequirement.MUST_NOT_HOLD,
            condition_id="commerce.orders.condition.requirement-is-may",
            subject_kinds=("Requirement",),
            severity="MEDIUM",
        )
    )
    person = _person(registry)
    allowed = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-027",
        spec={
            "statement": "Non-MAY requirements satisfy the prohibition.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )
    violating = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-028",
        spec={
            "statement": "MAY requirements violate this prohibition.",
            "priority": "MAY",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )

    satisfied = registry.evaluate_constraint(
        constraint_id="commerce.orders.constraint.requirement-must-not-be-may",
        subject_id=allowed.metadata.id,
    )
    violated = registry.evaluate_constraint(
        constraint_id="commerce.orders.constraint.requirement-must-not-be-may",
        subject_id=violating.metadata.id,
    )

    assert satisfied.result is ConstraintEvaluationResult.SATISFIED
    assert satisfied.violation_id is None
    assert violated.result is ConstraintEvaluationResult.VIOLATED
    assert violated.violation_id == "VIO-000001"


def test_updl_registry_preserves_unknown_constraint_evaluation() -> None:
    registry = _relationship_registry()
    registry.register_condition(
        SemanticConditionDefinition(
            id="commerce.orders.condition.requirement-classified",
            name="requirementClassified",
            subject_kinds=("Requirement",),
            clauses=(
                SemanticConditionClause(
                    ConditionClauseType.SPEC_EQUALS,
                    path="classification",
                    expected="regulated",
                ),
            ),
        )
    )
    registry.register_constraint(
        ConstraintDefinition(
            id="commerce.orders.constraint.requirement-classified",
            name="requirementClassified",
            requirement=ConstraintRequirement.MUST_HOLD,
            condition_id="commerce.orders.condition.requirement-classified",
            subject_kinds=("Requirement",),
        )
    )
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-029",
        spec={
            "statement": "Missing classification remains unknown.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )

    evaluation = registry.evaluate_constraint(
        constraint_id="commerce.orders.constraint.requirement-classified",
        subject_id=requirement.metadata.id,
    )

    assert evaluation.result is ConstraintEvaluationResult.UNKNOWN
    assert evaluation.violation_id is None
    assert evaluation.condition_evaluation is not None
    assert evaluation.condition_evaluation.outcome is ConditionOutcome.UNKNOWN


def test_updl_registry_completes_task_only_through_completion_condition() -> None:
    registry = _relationship_registry()
    registry.register_condition(
        SemanticConditionDefinition(
            id="commerce.orders.condition.requirement-ready",
            name="requirementReady",
            subject_kinds=("Requirement",),
            clauses=(
                SemanticConditionClause(
                    ConditionClauseType.SPEC_EQUALS,
                    path="priority",
                    expected="MUST",
                ),
            ),
        )
    )
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-030",
        spec={
            "statement": "Task completion shall be condition-backed.",
            "priority": "SHOULD",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )
    task = registry.create_task(
        goal_ref="goal.restore-api",
        assignee_ref="agent.production-recovery",
        subject_ref=ObjectReference(requirement.metadata.id),
        actor=_actor(),
        completion_condition_id="commerce.orders.condition.requirement-ready",
        allowed_actions=("inspect",),
        parent_allowed_actions=("inspect", "repair"),
    )

    ready = registry.transition_task(
        task_id=task.id,
        target_state=TaskLifecycleState.READY,
    )
    started = registry.transition_task(
        task_id=ready.id,
        target_state=TaskLifecycleState.IN_PROGRESS,
    )
    incomplete = registry.evaluate_task_completion(started.id)

    assert incomplete.result is TaskCompletionResult.NOT_COMPLETED
    assert registry.get_task(task.id).state is TaskLifecycleState.IN_PROGRESS

    registry.update_object(
        object_id=requirement.metadata.id,
        expected_revision=1,
        semantic_patch={"spec": {"priority": "MUST"}},
        actor=_actor(),
    )
    completed = registry.evaluate_task_completion(task.id)

    assert completed.result is TaskCompletionResult.COMPLETED
    assert completed.state is TaskLifecycleState.COMPLETED
    assert registry.get_task(task.id).state is TaskLifecycleState.COMPLETED
    assert completed.proof_hash.startswith("sha256:")


def test_updl_registry_rejects_task_authority_and_constraint_weakening() -> None:
    registry = _relationship_registry()
    registry.register_condition(
        SemanticConditionDefinition(
            id="commerce.orders.condition.requirement-must-priority",
            name="requirementMustPriority",
            subject_kinds=("Requirement",),
            clauses=(
                SemanticConditionClause(
                    ConditionClauseType.SPEC_EQUALS,
                    path="priority",
                    expected="MUST",
                ),
            ),
        )
    )
    registry.register_constraint(
        ConstraintDefinition(
            id="commerce.orders.constraint.requirement-must-priority",
            name="requirementMustPriority",
            requirement=ConstraintRequirement.MUST_HOLD,
            condition_id="commerce.orders.condition.requirement-must-priority",
            subject_kinds=("Requirement",),
        )
    )
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-031",
        spec={
            "statement": "Task envelopes shall narrow goal authority.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )

    try:
        registry.create_task(
            goal_ref="goal.restore-api",
            assignee_ref="agent.production-recovery",
            subject_ref=ObjectReference(requirement.metadata.id),
            actor=_actor(),
            allowed_actions=("delete-database",),
            parent_allowed_actions=("inspect",),
        )
    except RegistryError as exc:
        assert exc.code == "TASK_AUTHORITY_EXCEEDS_GOAL"
    else:
        raise AssertionError("task authority expansion was accepted")

    try:
        registry.create_task(
            goal_ref="goal.restore-api",
            assignee_ref="agent.production-recovery",
            subject_ref=ObjectReference(requirement.metadata.id),
            actor=_actor(),
            parent_required_constraint_ids=(
                "commerce.orders.constraint.requirement-must-priority",
            ),
        )
    except RegistryError as exc:
        assert exc.code == "TASK_CONSTRAINT_WEAKENING"
    else:
        raise AssertionError("task constraint weakening was accepted")


def test_updl_registry_enforces_task_dependencies_and_rejects_cycles() -> None:
    registry = _relationship_registry()
    registry.register_condition(
        SemanticConditionDefinition(
            id="commerce.orders.condition.requirement-ready",
            name="requirementReady",
            subject_kinds=("Requirement",),
            clauses=(
                SemanticConditionClause(
                    ConditionClauseType.SPEC_EQUALS,
                    path="priority",
                    expected="MUST",
                ),
            ),
        )
    )
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-032",
        spec={
            "statement": "Task dependencies shall form a DAG.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )
    first = registry.create_task(
        goal_ref="goal.restore-api",
        assignee_ref="agent.production-recovery",
        subject_ref=ObjectReference(requirement.metadata.id),
        actor=_actor(),
        completion_condition_id="commerce.orders.condition.requirement-ready",
    )
    second = registry.create_task(
        goal_ref="goal.restore-api",
        assignee_ref="agent.production-recovery",
        subject_ref=ObjectReference(requirement.metadata.id),
        actor=_actor(),
        dependencies=(TaskDependency(first.id, TaskDependencyType.COMPLETE_AFTER),),
    )

    registry.transition_task(task_id=second.id, target_state=TaskLifecycleState.READY)
    try:
        registry.transition_task(
            task_id=second.id,
            target_state=TaskLifecycleState.IN_PROGRESS,
        )
    except RegistryError as exc:
        assert exc.code == "TASK_DEPENDENCY_UNSATISFIED"
    else:
        raise AssertionError("task started with unsatisfied dependency")

    try:
        registry.set_task_dependencies(
            task_id=first.id,
            dependencies=(TaskDependency(second.id, TaskDependencyType.COMPLETE_AFTER),),
        )
    except RegistryError as exc:
        assert exc.code == "TASK_DEPENDENCY_CYCLE"
    else:
        raise AssertionError("cyclic task dependencies were accepted")

    assert registry.get_task(first.id).dependencies == ()


def test_updl_registry_records_task_outputs_with_provenance() -> None:
    registry = _relationship_registry()
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-033",
        spec={
            "statement": "Task outputs shall preserve provenance.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )
    task = registry.create_task(
        goal_ref="goal.restore-api",
        assignee_ref="agent.production-recovery",
        subject_ref=ObjectReference(requirement.metadata.id),
        actor=_actor(),
        outputs=(
            TaskOutputDefinition(
                id="diagnosis",
                type="enum",
                enum_values=("CONFIGURATION_ERROR", "CODE_REGRESSION"),
            ),
        ),
    )

    updated = registry.record_task_output(
        task_id=task.id,
        output_id="diagnosis",
        value="CODE_REGRESSION",
        source=TaskOutputSource.AI_INFERRED,
        provenance={"model": "agent.production-recovery@1"},
    )

    assert updated.output_values[0].source is TaskOutputSource.AI_INFERRED
    assert updated.canonical_document()["outputValues"][0]["provenance"] == {
        "model": "agent.production-recovery@1"
    }


def test_updl_registry_versions_plan_instances_without_in_place_mutation() -> None:
    registry = _relationship_registry()
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-034",
        spec={
            "statement": "Plan revisions shall preserve provenance.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )
    first = registry.create_task(
        goal_ref="goal.restore-api",
        assignee_ref="agent.production-recovery",
        subject_ref=ObjectReference(requirement.metadata.id),
        actor=_actor(),
    )
    second = registry.create_task(
        goal_ref="goal.restore-api",
        assignee_ref="agent.production-recovery",
        subject_ref=ObjectReference(requirement.metadata.id),
        actor=_actor(),
        dependencies=(TaskDependency(first.id),),
    )
    plan = registry.create_plan(
        goal_ref="goal.restore-api",
        planner_ref="agent.production-recovery",
        task_ids=(first.id, second.id),
        expected_outcome_ref="outcome.production-service-restored",
    )
    validation = registry.validate_plan(plan.id)
    revised = registry.revise_plan(
        plan_id=plan.id,
        reason="TASK_FAILED",
        task_ids=(first.id,),
    )

    assert validation.result is PlanValidationResult.VALID
    assert registry.get_plan(plan.id).state is PlanLifecycleState.SUPERSEDED
    assert registry.get_plan(plan.id).superseded_by == revised.id
    assert revised.version == 2
    assert revised.previous_plan_id == plan.id
    assert revised.revision_reason == "TASK_FAILED"


def test_updl_registry_preempts_preemptible_reservation_atomically() -> None:
    registry = _relationship_registry()
    registry.register_priority(
        PriorityDefinition(
            id="commerce.orders.priority.normal",
            name="Normal",
            rank=500,
            priority_class=PriorityClass.NORMAL,
        )
    )
    registry.register_priority(
        PriorityDefinition(
            id="commerce.orders.priority.security-critical",
            name="Security Critical",
            rank=900,
            priority_class=PriorityClass.CRITICAL,
        )
    )
    registry.register_reservation_definition(
        ReservationDefinition(
            id="commerce.orders.reservation.deployment-capacity",
            name="Deployment capacity",
            resource_type="DeploymentCapacity",
            preemption_mode=PreemptionMode.PREEMPTIBLE,
            expiration_required=False,
        )
    )
    target = registry.create_reservation(
        definition_id="commerce.orders.reservation.deployment-capacity",
        holder_ref="goal.release-optimization",
        resource_ref="resource.production-deployment-slot",
        priority_id="commerce.orders.priority.normal",
    )
    registry.register_preemption(
        PreemptionDefinition(
            id="commerce.orders.preemption.production-capacity",
            name="Production capacity preemption",
            resource_types=("DeploymentCapacity",),
            minimum_priority_id="commerce.orders.priority.security-critical",
            target_modes=(PreemptionMode.PREEMPTIBLE,),
            minimum_priority_delta=200,
            required_evidence=(
                "preemption.reason",
                "displaced.reservation",
                "replacement.reservation",
            ),
        )
    )

    decision = registry.evaluate_preemption(
        PreemptionRequest(
            id="commerce.orders.preemption-request.84721",
            preemption_definition_id="commerce.orders.preemption.production-capacity",
            requester_ref="goal.patch-critical-vulnerability",
            requested_resource_ref="resource.production-deployment-slot",
            target_reservation_id=target.id,
            replacement_holder_ref="goal.patch-critical-vulnerability",
            priority_id="commerce.orders.priority.security-critical",
            reason_code="SECURITY_CRITICAL",
        )
    )

    assert decision.effect is PreemptionEffect.PERMIT
    assert decision.replacement_reservation_id is not None
    displaced = registry.get_reservation(target.id)
    replacement = registry.get_reservation(decision.replacement_reservation_id)
    assert displaced.state is ReservationLifecycleState.PREEMPTED
    assert displaced.preempted_by == replacement.id
    assert displaced.preemption_decision_id == decision.id
    assert replacement.state is ReservationLifecycleState.ACTIVE
    assert replacement.resource_ref == target.resource_ref
    assert replacement.priority_id == "commerce.orders.priority.security-critical"
    assert decision.proof_hash.startswith("sha256:")


def test_updl_registry_denies_non_preemptible_reservation() -> None:
    registry = _relationship_registry()
    registry.register_priority(
        PriorityDefinition(
            id="commerce.orders.priority.normal",
            name="Normal",
            rank=500,
        )
    )
    registry.register_priority(
        PriorityDefinition(
            id="commerce.orders.priority.critical",
            name="Critical",
            rank=900,
            priority_class=PriorityClass.CRITICAL,
        )
    )
    registry.register_reservation_definition(
        ReservationDefinition(
            id="commerce.orders.reservation.legal-execution",
            name="Legal execution slot",
            resource_type="LegalExecution",
            preemption_mode=PreemptionMode.NON_PREEMPTIBLE,
            expiration_required=False,
        )
    )
    target = registry.create_reservation(
        definition_id="commerce.orders.reservation.legal-execution",
        holder_ref="goal.contract-signing",
        resource_ref="resource.contract-signing-slot",
        priority_id="commerce.orders.priority.normal",
    )
    registry.register_preemption(
        PreemptionDefinition(
            id="commerce.orders.preemption.legal-execution",
            name="Legal execution preemption",
            resource_types=("LegalExecution",),
            minimum_priority_id="commerce.orders.priority.critical",
            target_modes=(PreemptionMode.PREEMPTIBLE,),
        )
    )

    decision = registry.evaluate_preemption(
        PreemptionRequest(
            id="commerce.orders.preemption-request.84722",
            preemption_definition_id="commerce.orders.preemption.legal-execution",
            requester_ref="goal.emergency-review",
            requested_resource_ref="resource.contract-signing-slot",
            target_reservation_id=target.id,
            replacement_holder_ref="goal.emergency-review",
            priority_id="commerce.orders.priority.critical",
            reason_code="EMERGENCY_REVIEW",
        )
    )

    assert decision.effect is PreemptionEffect.DENY
    assert decision.reason_code == "PREEMPTION_TARGET_NOT_PREEMPTIBLE"
    assert decision.replacement_reservation_id is None
    assert registry.get_reservation(target.id).state is ReservationLifecycleState.ACTIVE


def test_updl_registry_enforces_preemption_priority_delta() -> None:
    registry = _relationship_registry()
    registry.register_priority(
        PriorityDefinition(
            id="commerce.orders.priority.normal",
            name="Normal",
            rank=600,
        )
    )
    registry.register_priority(
        PriorityDefinition(
            id="commerce.orders.priority.high",
            name="High",
            rank=700,
            priority_class=PriorityClass.HIGH,
        )
    )
    registry.register_reservation_definition(
        ReservationDefinition(
            id="commerce.orders.reservation.batch-capacity",
            name="Batch capacity",
            resource_type="BatchCapacity",
            preemption_mode=PreemptionMode.PREEMPTIBLE,
            expiration_required=False,
        )
    )
    target = registry.create_reservation(
        definition_id="commerce.orders.reservation.batch-capacity",
        holder_ref="goal.batch-reporting",
        resource_ref="resource.batch-slot",
        priority_id="commerce.orders.priority.normal",
    )
    registry.register_preemption(
        PreemptionDefinition(
            id="commerce.orders.preemption.batch-capacity",
            name="Batch capacity preemption",
            resource_types=("BatchCapacity",),
            minimum_priority_id="commerce.orders.priority.high",
            target_modes=(PreemptionMode.PREEMPTIBLE,),
            minimum_priority_delta=200,
        )
    )

    decision = registry.evaluate_preemption(
        PreemptionRequest(
            id="commerce.orders.preemption-request.84723",
            preemption_definition_id="commerce.orders.preemption.batch-capacity",
            requester_ref="goal.faster-reporting",
            requested_resource_ref="resource.batch-slot",
            target_reservation_id=target.id,
            replacement_holder_ref="goal.faster-reporting",
            priority_id="commerce.orders.priority.high",
            reason_code="REPORTING_PRIORITY",
        )
    )

    assert decision.effect is PreemptionEffect.DENY
    assert decision.reason_code == "PREEMPTION_PRIORITY_DELTA_INSUFFICIENT"
    assert decision.replacement_reservation_id is None
    assert registry.get_reservation(target.id).state is ReservationLifecycleState.ACTIVE


def test_updl_registry_assesses_risk_with_dimensional_impact_and_controls() -> None:
    registry = _relationship_registry()
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-035",
        spec={
            "statement": "Payments API shall protect customer data.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )
    evidence = registry.create_object(
        kind="Evidence",
        namespace="commerce.orders",
        local_id="EVIDENCE-035",
        spec={
            "evidence_type": "control-test",
            "summary": "Phishing-resistant MFA configuration was verified.",
        },
        actor=_actor(),
    )
    registry.register_risk_definition(
        RiskDefinition(
            id="commerce.orders.risk-definition.customer-data-exposure",
            name="customerDataExposure",
            domain=RiskDomain.SECURITY,
            subject_kinds=("Requirement",),
            likelihood_model_ref="likelihood.enterprise.qualitative",
            impact_model_ref="impact.enterprise.default",
        )
    )
    registry.register_risk_scenario(
        RiskScenario(
            id="commerce.orders.risk-scenario.admin-compromise",
            name="adminCompromise",
            subject_ref=ObjectReference(requirement.metadata.id),
            threat_ref="threat.credential-theft",
            vulnerability_ref="vulnerability.weak-admin-authentication",
            adverse_outcome_ref="outcome.customer-data-exposed",
        )
    )
    registry.register_control_definition(
        ControlDefinition(
            id="commerce.orders.control.admin-mfa",
            name="adminMfa",
            control_type=ControlType.PREVENTIVE,
            applies_to_kinds=("Requirement",),
            required_evidence=("control-test",),
            objective_refs=("control-objective.admin-access-authorized",),
            requirement_refs=("control-requirement.admin-mfa-before-access",),
            owner_ref="role.security-control-owner",
            operator_refs=("role.identity-operations",),
            applicability_ref="control-applicability.admin-requirements",
            trigger_refs=("control-trigger.admin-access-requested",),
            failure_policy_ref="policy.control-failure.admin-mfa",
            execution_modality=ControlExecutionModality.AUTOMATED,
            enforcement_mode=ControlEnforcementMode.BLOCKING,
            criticality=ControlCriticality.CRITICAL,
        )
    )
    control = registry.create_control_implementation(
        definition_id="commerce.orders.control.admin-mfa",
        subject_ref=ObjectReference(requirement.metadata.id),
        state=ControlState.ACTIVE,
        effectiveness=ControlEffectivenessResult.EFFECTIVE,
        evidence_refs=(ObjectReference(evidence.metadata.id),),
        result=ControlResult(
            execution_status=ControlExecutionStatus.SUCCEEDED,
            evaluation_outcome=ControlEvaluationOutcome.PASS,
            enforcement_outcome=ControlEnforcementOutcome.ALLOWED,
            evidence_refs=(ObjectReference(evidence.metadata.id),),
        ),
        effectiveness_assessment_ref="control-effectiveness.admin-mfa.current",
    )
    risk = registry.create_risk(
        definition_id="commerce.orders.risk-definition.customer-data-exposure",
        subject_ref=ObjectReference(requirement.metadata.id),
        scenario_id="commerce.orders.risk-scenario.admin-compromise",
        accountable_ref="role.payments-risk-owner",
    )

    assessment = registry.assess_risk(
        risk_id=risk.id,
        likelihood_type=LikelihoodType.QUALITATIVE,
        likelihood_level=RiskLevel.MEDIUM,
        impact={
            "security": RiskLevel.HIGH,
            "regulatory": RiskLevel.CRITICAL,
            "customer": RiskLevel.HIGH,
        },
        result_level=RiskLevel.CRITICAL,
        confidence=RiskLevel.MEDIUM,
        evidence_refs=(ObjectReference(evidence.metadata.id),),
        control_refs=(control.id,),
    )

    assert risk.state is RiskLifecycleState.OPEN
    assert assessment.result_level is RiskLevel.CRITICAL
    assert assessment.impact["regulatory"] is RiskLevel.CRITICAL
    assert assessment.control_refs == (control.id,)
    assert assessment.proof["controls"][0]["effectiveness"] == "EFFECTIVE"
    assert assessment.proof_hash.startswith("sha256:")
    assert assessment.canonical_document()["impact"] == {
        "customer": "HIGH",
        "regulatory": "CRITICAL",
        "security": "HIGH",
    }


def test_updl_registry_rejects_active_control_missing_contract_anchors() -> None:
    registry = _relationship_registry()

    try:
        registry.register_control_definition(
            ControlDefinition(
                id="commerce.orders.control.weak-admin-mfa",
                name="weakAdminMfa",
                control_type=ControlType.PREVENTIVE,
                applies_to_kinds=("Requirement",),
                required_evidence=("control-test",),
            )
        )
    except RegistryError as exc:
        assert exc.code == "CONTROL_OBJECTIVE_MISSING"
    else:
        raise AssertionError("active control without objective was accepted")


def test_updl_registry_rejects_effective_control_without_assessment_basis() -> None:
    registry = _relationship_registry()
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-036",
        spec={
            "statement": "Admin changes shall be governed.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )
    registry.register_control_definition(
        ControlDefinition(
            id="commerce.orders.control.admin-change-approval",
            name="adminChangeApproval",
            control_type=ControlType.PREVENTIVE,
            applies_to_kinds=("Requirement",),
            required_evidence=("approval-record",),
            objective_refs=("control-objective.admin-change-authorized",),
            requirement_refs=("control-requirement.admin-change-approval",),
            owner_ref="role.security-control-owner",
            applicability_ref="control-applicability.admin-changes",
            trigger_refs=("control-trigger.admin-change-requested",),
        )
    )

    try:
        registry.create_control_implementation(
            definition_id="commerce.orders.control.admin-change-approval",
            subject_ref=ObjectReference(requirement.metadata.id),
            state=ControlState.ACTIVE,
            effectiveness=ControlEffectivenessResult.EFFECTIVE,
        )
    except RegistryError as exc:
        assert exc.code == "CONTROL_EVIDENCE_INCOMPLETE"
    else:
        raise AssertionError("effective control without evidence was accepted")


def test_updl_registry_rejects_pass_result_without_evidence() -> None:
    registry = _relationship_registry()
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-037",
        spec={
            "statement": "Production changes shall be approved.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )
    registry.register_control_definition(
        ControlDefinition(
            id="commerce.orders.control.production-change-approval",
            name="productionChangeApproval",
            control_type=ControlType.PREVENTIVE,
            applies_to_kinds=("Requirement",),
            objective_refs=("control-objective.production-change-authorized",),
            requirement_refs=("control-requirement.production-change-approval",),
            owner_ref="role.release-control-owner",
            applicability_ref="control-applicability.production-changes",
            trigger_refs=("control-trigger.production-change-requested",),
            evidence_requirement_refs=("control-evidence.approval-record",),
        )
    )

    try:
        registry.create_control_implementation(
            definition_id="commerce.orders.control.production-change-approval",
            subject_ref=ObjectReference(requirement.metadata.id),
            state=ControlState.ACTIVE,
            result=ControlResult(
                execution_status=ControlExecutionStatus.SUCCEEDED,
                evaluation_outcome=ControlEvaluationOutcome.PASS,
                enforcement_outcome=ControlEnforcementOutcome.ALLOWED,
            ),
        )
    except RegistryError as exc:
        assert exc.code == "CONTROL_PASS_EVIDENCE_REQUIRED"
    else:
        raise AssertionError("pass result without evidence was accepted")


def test_updl_registry_risk_treatment_does_not_change_current_assessment() -> None:
    registry = _relationship_registry()
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-036",
        spec={
            "statement": "Treatment plans shall not silently reduce risk.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )
    registry.register_risk_definition(
        RiskDefinition(
            id="commerce.orders.risk-definition.outage",
            name="serviceOutage",
            domain=RiskDomain.OPERATIONAL,
            subject_kinds=("Requirement",),
            scenario_required=False,
        )
    )
    risk = registry.create_risk(
        definition_id="commerce.orders.risk-definition.outage",
        subject_ref=ObjectReference(requirement.metadata.id),
        accountable_ref="role.service-owner",
    )
    assessment = registry.assess_risk(
        risk_id=risk.id,
        likelihood_level=RiskLevel.HIGH,
        impact={"operational": RiskLevel.HIGH},
        result_level=RiskLevel.HIGH,
    )

    plan = registry.create_risk_treatment_plan(
        risk_id=risk.id,
        strategy=RiskTreatmentStrategy.MITIGATE,
        action_refs=("action.add-failover-capacity",),
        target_level=RiskLevel.MEDIUM,
    )

    assert plan.status is RiskTreatmentStatus.NOT_STARTED
    assert plan.target_level is RiskLevel.MEDIUM
    assert assessment.result_level is RiskLevel.HIGH
    assert registry.get_risk(risk.id).state is RiskLifecycleState.OPEN


def test_updl_registry_accepts_risk_against_specific_assessment() -> None:
    registry = _relationship_registry()
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-037",
        spec={
            "statement": "Acceptance shall bind a concrete residual assessment.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )
    registry.register_policy(
        PolicyDefinition(
            id="commerce.orders.POL-risk-acceptance",
            revision=1,
            effect=PolicyEffect.ALLOW,
            actions=("ACCEPT_RISK",),
            resource_kinds=("Requirement",),
        )
    )
    registry.register_risk_definition(
        RiskDefinition(
            id="commerce.orders.risk-definition.supplier-outage",
            name="supplierOutage",
            domain=RiskDomain.SUPPLIER,
            subject_kinds=("Requirement",),
            scenario_required=False,
            acceptance_policy_id="commerce.orders.POL-risk-acceptance",
        )
    )
    risk = registry.create_risk(
        definition_id="commerce.orders.risk-definition.supplier-outage",
        subject_ref=ObjectReference(requirement.metadata.id),
        accountable_ref="role.supplier-risk-owner",
    )
    assessment = registry.assess_risk(
        risk_id=risk.id,
        likelihood_level=RiskLevel.LOW,
        impact={"operational": RiskLevel.MEDIUM},
        result_level=RiskLevel.MEDIUM,
    )

    acceptance = registry.accept_risk(
        risk_id=risk.id,
        assessment_id=assessment.id,
        accepted_by_ref="role.supplier-risk-owner",
        rationale_code="TREATMENT_COST_NOT_JUSTIFIED",
        valid_until=None,
    )

    assert acceptance.status is RiskAcceptanceStatus.ACTIVE
    assert acceptance.assessment_id == assessment.id
    assert acceptance.risk_id == risk.id
    assert acceptance.proof["assessment"]["result"]["level"] == "MEDIUM"
    assert acceptance.proof_hash.startswith("sha256:")


def test_updl_registry_rejects_risk_without_required_scenario() -> None:
    registry = _relationship_registry()
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-038",
        spec={
            "statement": "Scenario-required risks shall name a scenario.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )
    registry.register_risk_definition(
        RiskDefinition(
            id="commerce.orders.risk-definition.privacy-exposure",
            name="privacyExposure",
            domain=RiskDomain.PRIVACY,
            subject_kinds=("Requirement",),
        )
    )

    try:
        registry.create_risk(
            definition_id="commerce.orders.risk-definition.privacy-exposure",
            subject_ref=ObjectReference(requirement.metadata.id),
            accountable_ref="role.privacy-owner",
        )
    except RegistryError as exc:
        assert exc.code == "RISK_SCENARIO_REQUIRED"
    else:
        raise AssertionError("risk without required scenario was accepted")


def test_updl_registry_defers_decisions_when_required_condition_is_unknown() -> None:
    registry = _relationship_registry()
    registry.register_condition(
        SemanticConditionDefinition(
            id="commerce.orders.condition.requirement-classified",
            name="requirementClassified",
            subject_kinds=("Requirement",),
            clauses=(
                SemanticConditionClause(
                    ConditionClauseType.SPEC_EQUALS,
                    path="classification",
                    expected="regulated",
                ),
            ),
        )
    )
    registry.register_decision(
        DecisionDefinition(
            id="commerce.orders.decision.requirement-change",
            name="requirementChange",
            action="APPLY_CHANGE",
            resource_kinds=("Requirement",),
            condition_ids=("commerce.orders.condition.requirement-classified",),
        )
    )
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-022",
        spec={
            "statement": "Retention requirement shall be governed.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )

    decision = registry.evaluate_decision(
        decision_id="commerce.orders.decision.requirement-change",
        resource_id=requirement.metadata.id,
        actor=_actor(),
    )

    assert decision.effect is DecisionEffect.DEFER
    assert decision.outcome == "DEFER"
    assert [finding.code for finding in decision.findings] == ["DECISION_CONDITION_UNKNOWN"]
    assert decision.condition_evaluations[0].outcome is ConditionOutcome.UNKNOWN
    assert decision.proof_hash.startswith("sha256:")


def test_updl_registry_decision_definition_preserves_contract_semantics() -> None:
    registry = _relationship_registry()
    registry.register_decision(
        DecisionDefinition(
            id="commerce.orders.decision.production-release",
            name="productionRelease",
            action="DEPLOY",
            resource_kinds=("Requirement",),
            decision_type=DecisionType.APPROVAL,
            question=DecisionQuestion(
                "May the specified release be deployed to production?"
            ),
            outcome_set=(
                DecisionOutcome.APPROVED,
                DecisionOutcome.CONDITIONALLY_APPROVED,
                DecisionOutcome.REJECTED,
                DecisionOutcome.ESCALATED,
            ),
            alternatives=("deploy-now", "deploy-after-remediation", "cancel-release"),
            criteria_ids=(
                "decision-criterion.release-controls-effective",
                "decision-criterion.release-risk-acceptable",
            ),
            authority_requirement=DecisionAuthorityRequirement(
                operator="ALL_OF",
                authority_refs=(
                    "authority.release.operations",
                    "authority.release.security",
                ),
            ),
            evidence_requirement=DecisionEvidenceRequirement(
                required_types=(
                    "RELEASE_ARTIFACT_INTEGRITY",
                    "CONTROL_EFFECTIVENESS",
                    "RESIDUAL_RISK_ASSESSMENT",
                ),
                freshness="P1D",
            ),
            validity_policy_ref="decision-validity.production-release",
            effect_ref="decision-effect.production-release",
        )
    )

    document = registry.get_decision_definition(
        "commerce.orders.decision.production-release"
    ).canonical_document()

    assert document["question"]["statement"].startswith("May the specified release")
    assert document["outcomeSet"] == [
        "APPROVED",
        "CONDITIONALLY_APPROVED",
        "REJECTED",
        "ESCALATED",
    ]
    assert document["authorityRequirement"]["operator"] == "ALL_OF"
    assert document["evidenceRequirement"]["missingEvidenceEffect"] == "DEFER"


def test_updl_registry_records_condition_failure_transition_and_impact() -> None:
    registry = _relationship_registry()
    registry.register_condition(
        SemanticConditionDefinition(
            id="commerce.orders.condition.owner-active",
            name="ownerActive",
            subject_kinds=("Person",),
            clauses=(
                SemanticConditionClause(
                    ConditionClauseType.SPEC_EQUALS,
                    path="active",
                    expected=True,
                ),
            ),
        )
    )
    registry.register_condition_failure_policy(
        ConditionFailurePolicy(
            id="commerce.orders.condition-failure-policy.owner-active",
            condition_ids=("commerce.orders.condition.owner-active",),
            transitions_from=(ConditionOutcome.SATISFIED,),
            transitions_to=(ConditionOutcome.NOT_SATISFIED, ConditionOutcome.UNKNOWN),
            effects=(
                ConditionFailureEffect.DECISION_SUSPENDED,
                ConditionFailureEffect.EXECUTION_BLOCKED,
                ConditionFailureEffect.REMEDIATION_REQUIRED,
            ),
            scope=ConditionFailureScope(type="SUBJECT"),
            severity=ConditionFailureSeverity.HIGH,
        )
    )
    person = _person(registry)
    previous = registry.evaluate_condition(
        condition_id="commerce.orders.condition.owner-active",
        subject_id=person.metadata.id,
    )
    updated = registry.update_object(
        object_id=person.metadata.id,
        expected_revision=person.metadata.revision,
        semantic_patch={"spec": {"active": False}},
        actor=_actor(),
    )
    current = registry.evaluate_condition(
        condition_id="commerce.orders.condition.owner-active",
        subject_id=updated.metadata.id,
    )

    failure = registry.record_condition_failure(
        previous_evaluation=previous,
        current_evaluation=current,
        transition_type=ConditionFailureTransitionType.BECAME_FALSE,
        detection_mode=ConditionFailureDetectionMode.EVENT_DRIVEN,
        cause="UNDERLYING_FACT_CHANGED",
    )
    duplicate = registry.record_condition_failure(
        previous_evaluation=previous,
        current_evaluation=current,
        transition_type=ConditionFailureTransitionType.BECAME_FALSE,
    )
    impact = registry.calculate_condition_failure_impact(
        failure_id=failure.id,
        decisions=("decision.release-038",),
        executions=("workflow-run.038",),
        states=("Requirement:ACTIVE",),
    )

    assert previous.outcome is ConditionOutcome.SATISFIED
    assert current.outcome is ConditionOutcome.NOT_SATISFIED
    assert duplicate.id == failure.id
    assert failure.effects == (
        ConditionFailureEffect.DECISION_SUSPENDED,
        ConditionFailureEffect.EXECUTION_BLOCKED,
        ConditionFailureEffect.REMEDIATION_REQUIRED,
    )
    assert failure.policy_ref == "commerce.orders.condition-failure-policy.owner-active"
    assert impact.failure_ref == failure.id
    assert impact.decisions == ("decision.release-038",)


def test_updl_registry_rejects_condition_dependency_cycle() -> None:
    registry = _relationship_registry()
    for condition_id, path in (
        ("commerce.orders.condition.a", "a"),
        ("commerce.orders.condition.b", "b"),
    ):
        registry.register_condition(
            SemanticConditionDefinition(
                id=condition_id,
                name=path,
                subject_kinds=("Requirement",),
                clauses=(
                    SemanticConditionClause(
                        ConditionClauseType.SPEC_EQUALS,
                        path=path,
                        expected=True,
                    ),
                ),
            )
        )
    registry.register_condition_dependency(
        ConditionDependency(
            id="commerce.orders.condition-dependency.a-on-b",
            dependent_condition_id="commerce.orders.condition.a",
            dependency_condition_id="commerce.orders.condition.b",
            dependency_type=ConditionDependencyType.REQUIRES,
        )
    )

    try:
        registry.register_condition_dependency(
            ConditionDependency(
                id="commerce.orders.condition-dependency.b-on-a",
                dependent_condition_id="commerce.orders.condition.b",
                dependency_condition_id="commerce.orders.condition.a",
                dependency_type=ConditionDependencyType.REQUIRES,
            )
        )
    except RegistryError as exc:
        assert exc.code == "CONDITION_FAILURE_CIRCULAR_DEPENDENCY"
    else:
        raise AssertionError("cyclic condition dependency was accepted")


def test_updl_registry_remediation_closure_requires_effectiveness_proof() -> None:
    registry = _relationship_registry()
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-039",
        spec={
            "statement": "Critical condition failure must be remediated.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )
    evidence = registry.create_object(
        kind="Evidence",
        namespace="commerce.orders",
        local_id="EVIDENCE-039",
        spec={
            "evidence_type": "remediation-verification",
            "summary": "Owner reassigned and condition retested.",
        },
        actor=_actor(),
    )
    previous = registry._condition_evaluation(  # noqa: SLF001
        condition_id="commerce.orders.condition.owner-present",
        condition_version="1.0.0",
        subject_id=requirement.metadata.id,
        subject_revision=requirement.metadata.revision,
        outcome=ConditionOutcome.SATISFIED,
        findings=(),
        proof={"synthetic": "previous"},
        evaluated_at=requirement.metadata.created_at,
    )
    current = registry._condition_evaluation(  # noqa: SLF001
        condition_id="commerce.orders.condition.owner-present",
        condition_version="1.0.0",
        subject_id=requirement.metadata.id,
        subject_revision=requirement.metadata.revision,
        outcome=ConditionOutcome.UNKNOWN,
        findings=(),
        proof={"synthetic": "current"},
        evaluated_at=requirement.metadata.updated_at,
    )
    failure = registry.record_condition_failure(
        previous_evaluation=previous,
        current_evaluation=current,
        transition_type=ConditionFailureTransitionType.BECAME_UNKNOWN,
    )
    registry.register_remediation_definition(
        RemediationDefinition(
            id="commerce.orders.remediation-definition.condition-failure",
            name="conditionFailureRemediation",
            trigger_types=(RemediationTriggerType.CONDITION_FAILURE,),
            independent_verification_required=True,
            effectiveness_evidence_required=("remediation-effectiveness",),
        )
    )
    remediation_case = registry.open_remediation_case(
        definition_id="commerce.orders.remediation-definition.condition-failure",
        trigger=RemediationTrigger(RemediationTriggerType.CONDITION_FAILURE, failure.id),
        subject_ref=ObjectReference(requirement.metadata.id),
        objective="Restore owner-present condition with high assurance.",
        owner_ref="role.governance-owner",
        severity=RemediationSeverity.HIGH,
        priority=RemediationPriority.P1,
        deadlines=RemediationDeadlines(remediation_by=requirement.metadata.updated_at),
    )

    try:
        registry.verify_remediation(
            case_id=remediation_case.id,
            result=RemediationVerificationResult.VERIFIED,
            verifier_ref="principal.operator",
            evidence_refs=(ObjectReference(evidence.metadata.id),),
            independent=False,
        )
    except RegistryError as exc:
        assert exc.code == "REMEDIATION_INDEPENDENCE_REQUIRED"
    else:
        raise AssertionError("non-independent remediation verification was accepted")

    verification = registry.verify_remediation(
        case_id=remediation_case.id,
        result=RemediationVerificationResult.VERIFIED,
        verifier_ref="principal.independent-verifier",
        evidence_refs=(ObjectReference(evidence.metadata.id),),
        independent=True,
    )
    effectiveness = registry.assess_remediation_effectiveness(
        case_id=remediation_case.id,
        verification_id=verification.id,
        result=RemediationEffectivenessResult.EFFECTIVE,
        assessor_ref="principal.assurance-reviewer",
        evidence_refs=(ObjectReference(evidence.metadata.id),),
    )
    acceptance = registry.accept_remediation(
        case_id=remediation_case.id,
        effectiveness_id=effectiveness.id,
        accepted_by_ref="principal.control-owner",
        result=RemediationAcceptanceResult.ACCEPTED,
    )
    closure = registry.close_remediation_case(
        case_id=remediation_case.id,
        verification_id=verification.id,
        effectiveness_id=effectiveness.id,
        acceptance_id=acceptance.id,
        evidence_refs=(ObjectReference(evidence.metadata.id),),
        closed_by_ref="principal.assurance-owner",
    )

    assert closure.case_ref == remediation_case.id
    assert registry.get_remediation_case(remediation_case.id).status is RemediationStatus.CLOSED


def test_updl_registry_escalates_post_remediation_recurrence() -> None:
    registry = _relationship_registry()
    person = _person(registry)
    first_subject = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-040",
        spec={
            "statement": "First owner failure.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )
    second_subject = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-041",
        spec={
            "statement": "Second owner failure.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )
    first_failure = registry.record_condition_failure(
        previous_evaluation=registry._condition_evaluation(  # noqa: SLF001
            condition_id="commerce.orders.condition.owner-present",
            condition_version="1.0.0",
            subject_id=first_subject.metadata.id,
            subject_revision=first_subject.metadata.revision,
            outcome=ConditionOutcome.SATISFIED,
            findings=(),
            proof={"episode": 1, "state": "previous"},
            evaluated_at=first_subject.metadata.created_at,
        ),
        current_evaluation=registry._condition_evaluation(  # noqa: SLF001
            condition_id="commerce.orders.condition.owner-present",
            condition_version="1.0.0",
            subject_id=first_subject.metadata.id,
            subject_revision=first_subject.metadata.revision,
            outcome=ConditionOutcome.NOT_SATISFIED,
            findings=(),
            proof={"episode": 1, "state": "current"},
            evaluated_at=first_subject.metadata.updated_at,
        ),
        transition_type=ConditionFailureTransitionType.BECAME_FALSE,
    )
    registry.register_remediation_definition(
        RemediationDefinition(
            id="commerce.orders.remediation-definition.recurrence-seed",
            name="recurrenceSeed",
            trigger_types=(RemediationTriggerType.CONDITION_FAILURE,),
        )
    )
    remediation_case = registry.open_remediation_case(
        definition_id="commerce.orders.remediation-definition.recurrence-seed",
        trigger=RemediationTrigger(
            RemediationTriggerType.CONDITION_FAILURE,
            first_failure.id,
        ),
        subject_ref=ObjectReference(first_subject.metadata.id),
        objective="Restore condition and prevent repeat failures.",
        owner_ref="role.governance-owner",
        severity=RemediationSeverity.HIGH,
        priority=RemediationPriority.P1,
    )
    second_failure = registry.record_condition_failure(
        previous_evaluation=registry._condition_evaluation(  # noqa: SLF001
            condition_id="commerce.orders.condition.owner-present",
            condition_version="1.0.0",
            subject_id=second_subject.metadata.id,
            subject_revision=second_subject.metadata.revision,
            outcome=ConditionOutcome.SATISFIED,
            findings=(),
            proof={"episode": 2, "state": "previous"},
            evaluated_at=second_subject.metadata.created_at,
        ),
        current_evaluation=registry._condition_evaluation(  # noqa: SLF001
            condition_id="commerce.orders.condition.owner-present",
            condition_version="1.0.0",
            subject_id=second_subject.metadata.id,
            subject_revision=second_subject.metadata.revision,
            outcome=ConditionOutcome.NOT_SATISFIED,
            findings=(),
            proof={"episode": 2, "state": "current"},
            evaluated_at=second_subject.metadata.updated_at,
        ),
        transition_type=ConditionFailureTransitionType.BECAME_FALSE,
    )
    registry.register_recurrence_definition(
        RecurrenceDefinition(
            id="commerce.orders.recurrence-definition.owner-condition",
            name="ownerConditionRecurrence",
            applies_to_kinds=("ConditionFailure",),
            correlation_dimensions=("condition", "failureMode"),
            occurrence_threshold=2,
        )
    )
    registry.register_recurrence_severity_policy(
        RecurrenceSeverityPolicy(
            id="commerce.orders.recurrence-severity.owner-condition",
            name="ownerConditionSeverity",
            systemic_post_validation_threshold=2,
            systemic_minimum_occurrences=3,
        )
    )

    correlation, decision = registry.assess_recurrence(
        definition_id="commerce.orders.recurrence-definition.owner-condition",
        occurrence_refs=(first_failure.id, second_failure.id),
        dimensions={
            "condition": "commerce.orders.condition.owner-present",
            "failureMode": "OWNER_MISSING",
        },
        determined_by_ref="principal.governance-engine",
        confidence=0.96,
        base_severity=RecurrenceEffectiveSeverity.HIGH,
        severity_policy_id="commerce.orders.recurrence-severity.owner-condition",
        prior_remediation_refs=(remediation_case.id,),
        post_validation_count=1,
        same_root_cause_count=2,
        same_scope_count=2,
        source=RecurrenceDeterminationSource.RULE_CONFIRMED,
    )
    blast_radius = registry.calculate_recurrence_blast_radius(
        recurrence_id=correlation.id,
        controls=("control.production-owner-governance",),
        assurance_claims=("assurance.owner-governance-effective",),
        decisions=("decision.production-release",),
        risks=("risk.ownerless-production-change",),
    )

    assert correlation.determination is RecurrenceState.CONFIRMED
    assert decision.effective_severity is RecurrenceEffectiveSeverity.CRITICAL
    assert RecurrenceClassification.POST_REMEDIATION_RECURRENCE in decision.classifications
    assert RecurrenceClassification.POST_VALIDATION_RECURRENCE in decision.classifications
    assert RecurrenceConsequence.REMEDIATION_EFFECTIVENESS_INVALIDATED in decision.consequences
    assert RecurrenceConsequence.TEST_METHOD_REVIEW_REQUIRED in decision.consequences
    assert blast_radius.decisions == ("decision.production-release",)


def test_updl_registry_marks_systemic_recurrence_from_shared_root_cause() -> None:
    registry = _relationship_registry()
    person = _person(registry)
    subjects = tuple(
        registry.create_object(
            kind="Requirement",
            namespace="commerce.orders",
            local_id=f"REQ-04{index}",
            spec={
                "statement": f"Recurring owner failure {index}.",
                "priority": "MUST",
                "owner": {"$ref": {"id": person.metadata.id}},
            },
            actor=_actor(),
        )
        for index in range(2, 5)
    )
    failures = tuple(
        registry.record_condition_failure(
            previous_evaluation=registry._condition_evaluation(  # noqa: SLF001
                condition_id="commerce.orders.condition.owner-present",
                condition_version="1.0.0",
                subject_id=subject.metadata.id,
                subject_revision=subject.metadata.revision,
                outcome=ConditionOutcome.SATISFIED,
                findings=(),
                proof={"index": index, "state": "previous"},
                evaluated_at=subject.metadata.created_at,
            ),
            current_evaluation=registry._condition_evaluation(  # noqa: SLF001
                condition_id="commerce.orders.condition.owner-present",
                condition_version="1.0.0",
                subject_id=subject.metadata.id,
                subject_revision=subject.metadata.revision,
                outcome=ConditionOutcome.NOT_SATISFIED,
                findings=(),
                proof={"index": index, "state": "current"},
                evaluated_at=subject.metadata.updated_at,
            ),
            transition_type=ConditionFailureTransitionType.BECAME_FALSE,
        )
        for index, subject in enumerate(subjects, start=1)
    )
    registry.register_recurrence_definition(
        RecurrenceDefinition(
            id="commerce.orders.recurrence-definition.systemic-owner-condition",
            name="systemicOwnerConditionRecurrence",
            applies_to_kinds=("ConditionFailure",),
            correlation_dimensions=("condition", "failureMode", "rootCause"),
            occurrence_threshold=2,
        )
    )
    registry.register_recurrence_severity_policy(
        RecurrenceSeverityPolicy(
            id="commerce.orders.recurrence-severity.systemic-owner-condition",
            name="systemicOwnerConditionSeverity",
            systemic_minimum_occurrences=3,
        )
    )

    correlation, decision = registry.assess_recurrence(
        definition_id="commerce.orders.recurrence-definition.systemic-owner-condition",
        occurrence_refs=tuple(failure.id for failure in failures),
        dimensions={
            "condition": "commerce.orders.condition.owner-present",
            "failureMode": "OWNER_MISSING",
            "rootCause": "OWNERSHIP_SYNC_GAP",
        },
        determined_by_ref="principal.governance-engine",
        confidence=0.91,
        base_severity=RecurrenceEffectiveSeverity.HIGH,
        severity_policy_id="commerce.orders.recurrence-severity.systemic-owner-condition",
        same_root_cause_count=3,
        same_scope_count=3,
    )
    systemic = registry.assess_systemic_failure(
        recurrence_id=correlation.id,
        affected_business_units=2,
        affected_controls=3,
        affected_systems=5,
        shared_root_cause_present=True,
        prior_remediation_failures=1,
    )

    assert correlation.determination is RecurrenceState.SYSTEMIC
    assert decision.effective_severity is RecurrenceEffectiveSeverity.CRITICAL_SYSTEMIC
    assert RecurrenceClassification.SYSTEMIC_RECURRENCE in decision.classifications
    assert systemic.determination is RecurrenceState.SYSTEMIC
    assert systemic.severity is RecurrenceEffectiveSeverity.CRITICAL_SYSTEMIC


def test_updl_registry_rejects_recurrence_without_governed_correlation() -> None:
    registry = _relationship_registry()

    try:
        registry.register_recurrence_definition(
            RecurrenceDefinition(
                id="commerce.orders.recurrence-definition.invalid",
                name="invalidRecurrence",
                applies_to_kinds=("ConditionFailure",),
                correlation_dimensions=(),
                occurrence_threshold=1,
            )
        )
    except RegistryError as exc:
        assert exc.code == "RECURRENCE_THRESHOLD_INVALID"
    else:
        raise AssertionError("recurrence definition without valid threshold was accepted")


def test_updl_registry_change_adoption_requires_evidence_before_verification() -> None:
    registry = _registry()
    governance = _requirement(
        registry,
        "REQ-050",
        "Payment processing policy version three must be adopted.",
    )
    consumer = _requirement(
        registry,
        "REQ-051",
        "Payment API must consume the active payment policy.",
    )
    deployment_evidence = _evidence(registry, "EVIDENCE-050", "DEPLOYMENT")
    test_evidence = _evidence(registry, "EVIDENCE-051", "TEST_RESULT")
    registry.register_change_adoption_definition(
        ChangeAdoptionDefinition(
            id="commerce.orders.adoption-definition.payment-policy-v3",
            name="paymentPolicyV3Adoption",
            governance_ref=ObjectReference(governance.metadata.id),
            target_version="3.0.0",
            required_evidence_types=("DEPLOYMENT", "TEST_RESULT"),
        )
    )

    try:
        registry.declare_change_adoption(
            definition_id="commerce.orders.adoption-definition.payment-policy-v3",
            consumer_ref=ObjectReference(consumer.metadata.id),
            declared_by_ref="principal.payment-platform-owner",
            evidence_refs=(ObjectReference(deployment_evidence.metadata.id),),
            scope=AdoptionScope(environments=("production",)),
        )
    except RegistryError as exc:
        assert exc.code == "ADOPTION_EVIDENCE_MISSING"
    else:
        raise AssertionError("adoption declaration without required evidence was accepted")

    adoption = registry.declare_change_adoption(
        definition_id="commerce.orders.adoption-definition.payment-policy-v3",
        consumer_ref=ObjectReference(consumer.metadata.id),
        declared_by_ref="principal.payment-platform-owner",
        evidence_refs=(
            ObjectReference(deployment_evidence.metadata.id),
            ObjectReference(test_evidence.metadata.id),
        ),
        scope=AdoptionScope(environments=("production",)),
    )

    assert adoption.status is ChangeAdoptionStatus.ADOPTED

    verification = registry.verify_change_adoption(
        adoption_id=adoption.id,
        verifier_ref="control.governance-adoption-verifier",
        checks={
            "governance-version-active": "PASS",
            "deployment-version-matches": "PASS",
            "runtime-policy-conformance": "PASS",
        },
        evidence_refs=(),
    )
    verified = registry.get_change_adoption(adoption.id)

    assert verification.result is ChangeAdoptionVerificationResult.VERIFIED
    assert verified.status is ChangeAdoptionStatus.VERIFIED
    assert verified.verification_ref == verification.id
    assert verified.target.version == "3.0.0"


def test_updl_registry_adoption_coverage_separates_declared_from_verified() -> None:
    registry = _registry()
    governance = _requirement(registry, "REQ-052", "Payment policy v3.")
    first_consumer = _requirement(registry, "REQ-053", "Payment API consumer.")
    second_consumer = _requirement(registry, "REQ-054", "Checkout worker consumer.")
    deployment_evidence = _evidence(registry, "EVIDENCE-052", "DEPLOYMENT")
    test_evidence = _evidence(registry, "EVIDENCE-053", "TEST_RESULT")
    registry.register_change_adoption_definition(
        ChangeAdoptionDefinition(
            id="commerce.orders.adoption-definition.payment-policy-v3-coverage",
            name="paymentPolicyV3Coverage",
            governance_ref=ObjectReference(governance.metadata.id),
            target_version="3.0.0",
            required_evidence_types=("DEPLOYMENT", "TEST_RESULT"),
        )
    )
    first_adoption = registry.declare_change_adoption(
        definition_id="commerce.orders.adoption-definition.payment-policy-v3-coverage",
        consumer_ref=ObjectReference(first_consumer.metadata.id),
        declared_by_ref="principal.payment-platform-owner",
        evidence_refs=(
            ObjectReference(deployment_evidence.metadata.id),
            ObjectReference(test_evidence.metadata.id),
        ),
    )
    second_adoption = registry.declare_change_adoption(
        definition_id="commerce.orders.adoption-definition.payment-policy-v3-coverage",
        consumer_ref=ObjectReference(second_consumer.metadata.id),
        declared_by_ref="principal.checkout-owner",
        evidence_refs=(
            ObjectReference(deployment_evidence.metadata.id),
            ObjectReference(test_evidence.metadata.id),
        ),
    )
    registry.verify_change_adoption(
        adoption_id=first_adoption.id,
        verifier_ref="control.governance-adoption-verifier",
        checks={"runtime-policy-conformance": "PASS"},
        evidence_refs=(),
    )

    coverage = registry.calculate_adoption_coverage(
        governance_ref=ObjectReference(governance.metadata.id),
        target_version="3.0.0",
        required_consumers=(
            ObjectReference(first_consumer.metadata.id),
            ObjectReference(second_consumer.metadata.id),
        ),
        population_complete=True,
    )
    completion = registry.decide_change_adoption_completion(
        coverage_ref=coverage.id,
        minimum_verification_coverage=1.0,
    )

    assert second_adoption.status is ChangeAdoptionStatus.ADOPTED
    assert coverage.adoption_ratio == 1.0
    assert coverage.verification_ratio == 0.5
    assert completion.result is ChangeAdoptionCompletionResult.INCOMPLETE


def test_updl_registry_change_completion_requires_resolved_population() -> None:
    registry = _registry()
    governance = _requirement(registry, "REQ-055", "Payment policy v3.")
    consumer = _requirement(registry, "REQ-056", "Payment API consumer.")
    deployment_evidence = _evidence(registry, "EVIDENCE-054", "DEPLOYMENT")
    registry.register_change_adoption_definition(
        ChangeAdoptionDefinition(
            id="commerce.orders.adoption-definition.payment-policy-v3-complete",
            name="paymentPolicyV3Completion",
            governance_ref=ObjectReference(governance.metadata.id),
            target_version="3.0.0",
            required_evidence_types=("DEPLOYMENT",),
        )
    )
    adoption = registry.declare_change_adoption(
        definition_id="commerce.orders.adoption-definition.payment-policy-v3-complete",
        consumer_ref=ObjectReference(consumer.metadata.id),
        declared_by_ref="principal.payment-platform-owner",
        evidence_refs=(ObjectReference(deployment_evidence.metadata.id),),
    )
    registry.verify_change_adoption(
        adoption_id=adoption.id,
        verifier_ref="control.governance-adoption-verifier",
        checks={"deployment-version-matches": "PASS"},
        evidence_refs=(),
    )

    unknown_population = registry.calculate_adoption_coverage(
        governance_ref=ObjectReference(governance.metadata.id),
        target_version="3.0.0",
        required_consumers=(ObjectReference(consumer.metadata.id),),
        population_complete=False,
    )
    unknown_decision = registry.decide_change_adoption_completion(
        coverage_ref=unknown_population.id,
        minimum_verification_coverage=1.0,
    )
    resolved_population = registry.calculate_adoption_coverage(
        governance_ref=ObjectReference(governance.metadata.id),
        target_version="3.0.0",
        required_consumers=(ObjectReference(consumer.metadata.id),),
        population_complete=True,
    )
    complete_decision = registry.decide_change_adoption_completion(
        coverage_ref=resolved_population.id,
        minimum_verification_coverage=1.0,
    )

    assert unknown_decision.result is ChangeAdoptionCompletionResult.UNKNOWN
    assert complete_decision.result is ChangeAdoptionCompletionResult.COMPLETE


def test_updl_registry_records_change_adoption_failure_as_governed_fact() -> None:
    registry = _registry()
    governance = _requirement(registry, "REQ-057", "Payment policy v3.")
    consumer = _requirement(registry, "REQ-058", "Payment API consumer.")
    deployment_evidence = _evidence(registry, "EVIDENCE-055", "DEPLOYMENT")
    runtime_evidence = _evidence(registry, "EVIDENCE-056", "RUNTIME_VALIDATION")
    registry.register_change_adoption_definition(
        ChangeAdoptionDefinition(
            id="commerce.orders.adoption-definition.payment-policy-v3-failure",
            name="paymentPolicyV3Failure",
            governance_ref=ObjectReference(governance.metadata.id),
            target_version="3.0.0",
            required_evidence_types=("DEPLOYMENT",),
        )
    )
    adoption = registry.declare_change_adoption(
        definition_id="commerce.orders.adoption-definition.payment-policy-v3-failure",
        consumer_ref=ObjectReference(consumer.metadata.id),
        declared_by_ref="principal.payment-platform-owner",
        evidence_refs=(ObjectReference(deployment_evidence.metadata.id),),
    )

    failure = registry.record_change_adoption_failure(
        adoption_id=adoption.id,
        failure_type=ChangeAdoptionFailureType.RUNTIME_NONCONFORMANCE,
        reason_code="RUNTIME_POLICY_MISMATCH",
        evidence_refs=(ObjectReference(runtime_evidence.metadata.id),),
    )

    assert failure.failure_type is ChangeAdoptionFailureType.RUNTIME_NONCONFORMANCE
    assert registry.get_change_adoption(adoption.id).status is ChangeAdoptionStatus.FAILED


def test_updl_registry_combines_decision_policy_contributions_with_deny_overrides() -> None:
    registry = _relationship_registry()
    registry.register_condition(
        SemanticConditionDefinition(
            id="commerce.orders.condition.requirement-owned",
            name="requirementOwned",
            subject_kinds=("Requirement",),
            clauses=(
                SemanticConditionClause(
                    ConditionClauseType.RELATIONSHIP_EXISTS,
                    relationship_type_id="commerce.orders.relationship.owned-by",
                    target_kind="Person",
                ),
            ),
        )
    )
    registry.register_policy(
        PolicyDefinition(
            id="commerce.orders.POL-change-window",
            revision=1,
            effect=PolicyEffect.ALLOW,
            actions=("APPLY_CHANGE",),
            resource_kinds=("Requirement",),
            obligations=(PolicyObligation("AUDIT"),),
        )
    )
    registry.register_policy(
        PolicyDefinition(
            id="commerce.orders.POL-freeze-sensitive",
            revision=2,
            effect=PolicyEffect.DENY,
            actions=("APPLY_CHANGE",),
            resource_kinds=("Requirement",),
        )
    )
    registry.register_decision(
        DecisionDefinition(
            id="commerce.orders.decision.requirement-change",
            name="requirementChange",
            action="APPLY_CHANGE",
            resource_kinds=("Requirement",),
            condition_ids=("commerce.orders.condition.requirement-owned",),
            policy_ids=(
                "commerce.orders.POL-change-window",
                "commerce.orders.POL-freeze-sensitive",
            ),
        )
    )
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-023",
        spec={
            "statement": "Sensitive requirements shall obey freezes.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )
    registry.create_relationship(
        relationship_id="commerce.orders.REL-008",
        type_id="commerce.orders.relationship.owned-by",
        source_id=requirement.metadata.id,
        target=ObjectReference(person.metadata.id),
        actor=_actor(),
    )

    decision = registry.evaluate_decision(
        decision_id="commerce.orders.decision.requirement-change",
        resource_id=requirement.metadata.id,
        actor=_actor(),
        context={"purpose": "change-request"},
    )

    assert decision.effect is DecisionEffect.PROHIBIT
    assert decision.outcome == "DENY"
    assert [item.effect for item in decision.policy_contributions] == [
        PolicyEffect.ALLOW,
        PolicyEffect.DENY,
    ]
    assert [obligation.type for obligation in decision.obligations] == ["AUDIT"]
    assert decision.condition_evaluations[0].outcome is ConditionOutcome.SATISFIED
    assert decision.canonical_document()["effect"] == "PROHIBIT"


def test_updl_registry_evaluates_explicit_decision_request_contract() -> None:
    registry = _relationship_registry()
    registry.register_policy(
        PolicyDefinition(
            id="commerce.orders.POL-change-allow",
            revision=1,
            effect=PolicyEffect.ALLOW,
            actions=("APPLY_CHANGE",),
            resource_kinds=("Requirement",),
        )
    )
    registry.register_decision(
        DecisionDefinition(
            id="commerce.orders.decision.requirement-change",
            name="requirementChange",
            action="APPLY_CHANGE",
            resource_kinds=("Requirement",),
            policy_ids=("commerce.orders.POL-change-allow",),
            constraints=(
                DecisionConstraint(
                    type="RESOURCE_KIND",
                    value="Requirement",
                ),
            ),
            advice=(
                DecisionAdvice(
                    code="REVIEW_CHANGE_WINDOW",
                    message="Review the active change window before execution.",
                ),
            ),
            validity_seconds=300,
        )
    )
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-024",
        spec={
            "statement": "Decision requests shall be explicit.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )

    decision = registry.evaluate_decision_request(
        DecisionRequest(
            id="commerce.orders.decision-request.REQ-024",
            decision_id="commerce.orders.decision.requirement-change",
            resource_id=requirement.metadata.id,
            actor=_actor(),
            requested_action="APPLY_CHANGE",
            context={"purpose": "change-request"},
        )
    )

    document = decision.canonical_document()
    assert decision.evaluation_status is DecisionEvaluationStatus.COMPLETED
    assert decision.effect is DecisionEffect.PERMIT
    assert decision.request_id == "commerce.orders.decision-request.REQ-024"
    assert decision.valid_until is not None
    assert decision.valid_until > decision.evaluated_at
    assert document["constraints"] == [
        {"type": "RESOURCE_KIND", "value": "Requirement"},
    ]
    assert document["advice"] == [
        {
            "code": "REVIEW_CHANGE_WINDOW",
            "message": "Review the active change window before execution.",
        },
    ]
    assert document["validUntil"] == decision.valid_until.isoformat()


def test_updl_registry_defers_decision_request_on_action_mismatch() -> None:
    registry = _relationship_registry()
    registry.register_policy(
        PolicyDefinition(
            id="commerce.orders.POL-change-allow",
            revision=1,
            effect=PolicyEffect.ALLOW,
            actions=("APPLY_CHANGE",),
            resource_kinds=("Requirement",),
        )
    )
    registry.register_decision(
        DecisionDefinition(
            id="commerce.orders.decision.requirement-change",
            name="requirementChange",
            action="APPLY_CHANGE",
            resource_kinds=("Requirement",),
            policy_ids=("commerce.orders.POL-change-allow",),
        )
    )
    person = _person(registry)
    requirement = registry.create_object(
        kind="Requirement",
        namespace="commerce.orders",
        local_id="REQ-025",
        spec={
            "statement": "Mismatched requested actions shall not permit execution.",
            "priority": "MUST",
            "owner": {"$ref": {"id": person.metadata.id}},
        },
        actor=_actor(),
    )

    decision = registry.evaluate_decision_request(
        DecisionRequest(
            id="commerce.orders.decision-request.REQ-025",
            decision_id="commerce.orders.decision.requirement-change",
            resource_id=requirement.metadata.id,
            actor=_actor(),
            requested_action="DELETE",
        )
    )

    assert decision.effect is DecisionEffect.DEFER
    assert decision.outcome == "DEFER"
    assert [finding.code for finding in decision.findings] == [
        "DECISION_ACTION_MISMATCH"
    ]


def test_updl_registry_activates_decision_obligation_idempotently() -> None:
    registry = _state_machine_registry()
    registry.register_condition(
        SemanticConditionDefinition(
            id="commerce.orders.condition.production-deployment",
            name="productionDeployment",
            subject_kinds=("Deployment",),
            clauses=(
                SemanticConditionClause(
                    ConditionClauseType.SPEC_EQUALS,
                    path="environment",
                    expected="production",
                ),
            ),
        )
    )
    registry.register_policy(
        PolicyDefinition(
            id="commerce.orders.POL-production-deploy",
            revision=1,
            effect=PolicyEffect.ALLOW,
            actions=("DEPLOY",),
            resource_kinds=("Deployment",),
        )
    )
    registry.register_decision(
        DecisionDefinition(
            id="commerce.orders.decision.production-deploy",
            name="productionDeploy",
            action="DEPLOY",
            resource_kinds=("Deployment",),
            policy_ids=("commerce.orders.POL-production-deploy",),
        )
    )
    registry.register_obligation(
        ObligationDefinition(
            id="commerce.orders.obligation.monitor-production-release",
            name="monitorProductionRelease",
            trigger=ObligationTrigger(
                source=ObligationTriggerSource.POLICY_DECISION,
                decision_effect=DecisionEffect.PERMIT,
                policy_id="commerce.orders.POL-production-deploy",
            ),
            applicability_condition_id="commerce.orders.condition.production-deployment",
            subject=ObligationSubject(),
            duty=ObligationDuty(action_ref="commerce.orders.action.monitor-release"),
            responsibility=ObligationResponsibility(
                strategy=ObligationAssignmentStrategy.ROLE,
                assignee_ref="role.production-operator",
            ),
            timing=ObligationTiming(completion_within="PT24H"),
            required_evidence=(
                "monitoring-session",
                "release-health-report",
            ),
        )
    )
    deployment = registry.create_object(
        kind="Deployment",
        namespace="commerce.orders",
        local_id="DEP-002",
        spec={"artifact": "artifact:checkout@1.0.0", "environment": "production"},
        actor=_actor(),
        lifecycle_state="requested",
    )

    decision = registry.evaluate_decision_request(
        DecisionRequest(
            id="commerce.orders.decision-request.DEP-002",
            decision_id="commerce.orders.decision.production-deploy",
            resource_id=deployment.metadata.id,
            actor=_actor(),
            requested_action="DEPLOY",
        )
    )
    activations = registry.evaluate_decision_obligations(decision)
    repeated = registry.evaluate_decision_obligations(decision)

    assert [activation.outcome for activation in activations] == [
        ObligationActivationOutcome.ACTIVATED
    ]
    assert activations[0].reason_code == "OBLIGATION_ACTIVATED"
    assert repeated[0].reason_code == "OBLIGATION_ALREADY_ACTIVATED"
    assert repeated[0].instance_id == activations[0].instance_id
    assert len(registry.list_obligations(subject_id=deployment.metadata.id)) == 1

    obligation = registry.get_obligation(activations[0].instance_id or "")
    assert obligation.definition_version == "1.0.0"
    assert obligation.subject_ref.id == deployment.metadata.id
    assert obligation.assignee_ref == "role.production-operator"
    assert obligation.state is ObligationLifecycleState.ACTIVE
    assert obligation.due_at is not None


def test_updl_registry_requires_obligation_fulfillment_evidence() -> None:
    registry = _state_machine_registry()
    registry.register_policy(
        PolicyDefinition(
            id="commerce.orders.POL-production-deploy",
            revision=1,
            effect=PolicyEffect.ALLOW,
            actions=("DEPLOY",),
            resource_kinds=("Deployment",),
        )
    )
    registry.register_decision(
        DecisionDefinition(
            id="commerce.orders.decision.production-deploy",
            name="productionDeploy",
            action="DEPLOY",
            resource_kinds=("Deployment",),
            policy_ids=("commerce.orders.POL-production-deploy",),
        )
    )
    registry.register_obligation(
        ObligationDefinition(
            id="commerce.orders.obligation.capture-production-evidence",
            name="captureProductionEvidence",
            trigger=ObligationTrigger(
                source=ObligationTriggerSource.POLICY_DECISION,
                decision_effect=DecisionEffect.PERMIT,
            ),
            subject=ObligationSubject(),
            duty=ObligationDuty(action_ref="commerce.orders.action.capture-evidence"),
            responsibility=ObligationResponsibility(
                strategy=ObligationAssignmentStrategy.ROLE,
                assignee_ref="role.release-owner",
            ),
            required_evidence=("release-health-report",),
        )
    )
    deployment = registry.create_object(
        kind="Deployment",
        namespace="commerce.orders",
        local_id="DEP-003",
        spec={"artifact": "artifact:checkout@1.0.0", "environment": "production"},
        actor=_actor(),
        lifecycle_state="requested",
    )
    evidence = registry.create_object(
        kind="Evidence",
        namespace="commerce.orders",
        local_id="EVIDENCE-003",
        spec={
            "evidence_type": "release-health-report",
            "summary": "Release health report was captured.",
        },
        actor=_actor(),
    )
    decision = registry.evaluate_decision(
        decision_id="commerce.orders.decision.production-deploy",
        resource_id=deployment.metadata.id,
        actor=_actor(),
    )
    activation = registry.evaluate_decision_obligations(decision)[0]
    obligation_id = activation.instance_id or ""

    pending = registry.evaluate_obligation(obligation_id)
    assert pending.result is ObligationFulfillmentResult.NOT_FULFILLED
    assert [finding.code for finding in pending.findings] == [
        "OBLIGATION_REQUIRED_EVIDENCE_MISSING"
    ]

    registry.attach_obligation_evidence(
        obligation_id=obligation_id,
        evidence_type="release-health-report",
        evidence_ref=ObjectReference(evidence.metadata.id),
    )
    fulfilled = registry.evaluate_obligation(obligation_id)

    assert fulfilled.result is ObligationFulfillmentResult.FULFILLED
    assert fulfilled.state is ObligationLifecycleState.FULFILLED
    assert registry.get_obligation(obligation_id).state is ObligationLifecycleState.FULFILLED
    assert fulfilled.proof_hash.startswith("sha256:")
    assert fulfilled.canonical_document()["evidence"][0]["type"] == "release-health-report"


def test_updl_registry_evaluates_obligation_breach_condition() -> None:
    registry = _state_machine_registry()
    registry.register_condition(
        SemanticConditionDefinition(
            id="commerce.orders.condition.production-deployment",
            name="productionDeployment",
            subject_kinds=("Deployment",),
            clauses=(
                SemanticConditionClause(
                    ConditionClauseType.SPEC_EQUALS,
                    path="environment",
                    expected="production",
                ),
            ),
        )
    )
    registry.register_policy(
        PolicyDefinition(
            id="commerce.orders.POL-production-deploy",
            revision=1,
            effect=PolicyEffect.ALLOW,
            actions=("DEPLOY",),
            resource_kinds=("Deployment",),
        )
    )
    registry.register_decision(
        DecisionDefinition(
            id="commerce.orders.decision.production-deploy",
            name="productionDeploy",
            action="DEPLOY",
            resource_kinds=("Deployment",),
            policy_ids=("commerce.orders.POL-production-deploy",),
        )
    )
    registry.register_obligation(
        ObligationDefinition(
            id="commerce.orders.obligation.monitor-production-release",
            name="monitorProductionRelease",
            trigger=ObligationTrigger(
                source=ObligationTriggerSource.POLICY_DECISION,
                decision_effect=DecisionEffect.PERMIT,
            ),
            subject=ObligationSubject(),
            duty=ObligationDuty(action_ref="commerce.orders.action.monitor-release"),
            responsibility=ObligationResponsibility(
                strategy=ObligationAssignmentStrategy.ROLE,
                assignee_ref="role.production-operator",
            ),
            required_evidence=("monitoring-session",),
            breach=ObligationBreach(
                condition_id="commerce.orders.condition.production-deployment",
                severity="HIGH",
            ),
        )
    )
    deployment = registry.create_object(
        kind="Deployment",
        namespace="commerce.orders",
        local_id="DEP-004",
        spec={"artifact": "artifact:checkout@1.0.0", "environment": "production"},
        actor=_actor(),
        lifecycle_state="requested",
    )
    decision = registry.evaluate_decision(
        decision_id="commerce.orders.decision.production-deploy",
        resource_id=deployment.metadata.id,
        actor=_actor(),
    )
    activation = registry.evaluate_decision_obligations(decision)[0]

    evaluation = registry.evaluate_obligation(activation.instance_id or "")

    assert evaluation.result is ObligationFulfillmentResult.NOT_FULFILLED
    assert evaluation.state is ObligationLifecycleState.BREACHED
    assert [finding.code for finding in evaluation.findings] == [
        "OBLIGATION_REQUIRED_EVIDENCE_MISSING",
        "OBLIGATION_BREACHED",
    ]


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

    events = registry.list_state_transition_events(deployment.metadata.id)
    audit_records = registry.list_state_transition_audit_records(deployment.metadata.id)

    assert len(events) == 1
    assert events[0].id == "EVT-000001"
    assert events[0].sequence == 1
    assert events[0].event_type == "StateTransitioned"
    assert events[0].object_id == deployment.metadata.id
    assert events[0].previous_revision == 1
    assert events[0].new_revision == 2
    assert events[0].state_machine_id == "commerce.orders.lifecycle.deployment"
    assert events[0].state_machine_version == "1.0.0"
    assert events[0].transition == "approve"
    assert events[0].from_state == "requested"
    assert events[0].to_state == "approved"
    assert events[0].actor == _actor()
    assert events[0].action_id == "commerce.orders.action.approve-deployment"

    assert len(audit_records) == 1
    assert audit_records[0].id == "AUD-000001"
    assert audit_records[0].event_id == events[0].id
    assert audit_records[0].decision.permitted
    assert audit_records[0].previous_state == "requested"
    assert audit_records[0].new_state == "approved"

    event_document = events[0].canonical_document()
    assert event_document["object"] == {
        "id": deployment.metadata.id,
        "kind": "Deployment",
        "previousRevision": 1,
        "newRevision": 2,
    }
    assert audit_records[0].canonical_document()["decision"]["permitted"] is True


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
    assert registry.list_state_transition_events(deployment.metadata.id) == ()
    assert registry.list_state_transition_audit_records(deployment.metadata.id) == ()


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
