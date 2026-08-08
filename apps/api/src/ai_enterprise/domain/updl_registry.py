from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from ai_enterprise.domain.specification.kernel import specification_hash

API_VERSION = "updl.ai-enterprise/v1alpha1"
VALIDATOR_VERSION = "0.1.0"
IDENTIFIER = re.compile(
    r"^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+\.[A-Za-z0-9][A-Za-z0-9_-]*$"
)
NAMESPACE = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)*$")
RESERVED_NAMESPACE_ROOTS = frozenset({"core", "system", "updl", "ai-enterprise"})
_MISSING = object()
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


class AdditionalPropertiesPolicy(StrEnum):
    FORBID = "forbid"
    ALLOW = "allow"
    WARN = "warn"


class TransitionClassification(StrEnum):
    NORMAL = "normal"
    APPROVAL = "approval"
    REJECTION = "rejection"
    ROLLBACK = "rollback"
    RECOVERY = "recovery"
    TIMEOUT = "timeout"
    AUTOMATIC = "automatic"
    ADMINISTRATIVE = "administrative"
    MIGRATION = "migration"


class RelationshipCardinality(StrEnum):
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"


class RelationshipLifecycle(StrEnum):
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"


class ConditionOutcome(StrEnum):
    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    UNKNOWN = "UNKNOWN"
    EXEMPTED = "EXEMPTED"


class ConditionEvaluationValidity(StrEnum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"
    SUPERSEDED = "SUPERSEDED"


class ConditionFailureTransitionType(StrEnum):
    BECAME_FALSE = "BECAME_FALSE"
    BECAME_UNKNOWN = "BECAME_UNKNOWN"
    BECAME_UNVERIFIABLE = "BECAME_UNVERIFIABLE"
    EVIDENCE_EXPIRED = "EVIDENCE_EXPIRED"
    EVIDENCE_REVOKED = "EVIDENCE_REVOKED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SOURCE_CONTRADICTED = "SOURCE_CONTRADICTED"
    EXEMPTION_EXPIRED = "EXEMPTION_EXPIRED"
    EXEMPTION_REVOKED = "EXEMPTION_REVOKED"
    THRESHOLD_BREACHED = "THRESHOLD_BREACHED"
    DEPENDENCY_FAILED = "DEPENDENCY_FAILED"
    SEMANTIC_ERROR = "SEMANTIC_ERROR"
    EVALUATION_ERROR = "EVALUATION_ERROR"
    TEMPORAL_WINDOW_CLOSED = "TEMPORAL_WINDOW_CLOSED"
    APPLICABILITY_CHANGED = "APPLICABILITY_CHANGED"


class ConditionFailureEffect(StrEnum):
    NO_EFFECT = "NO_EFFECT"
    WARN = "WARN"
    RECORD_ONLY = "RECORD_ONLY"
    EXECUTION_BLOCKED = "EXECUTION_BLOCKED"
    EXECUTION_TERMINATED = "EXECUTION_TERMINATED"
    EXECUTION_QUARANTINED = "EXECUTION_QUARANTINED"
    DECISION_REASSESSMENT_REQUIRED = "DECISION_REASSESSMENT_REQUIRED"
    DECISION_SUSPENDED = "DECISION_SUSPENDED"
    DECISION_INVALIDATED = "DECISION_INVALIDATED"
    AUTHORIZATION_SUSPENDED = "AUTHORIZATION_SUSPENDED"
    AUTHORIZATION_REVOKED = "AUTHORIZATION_REVOKED"
    STATE_TRANSITION_REQUIRED = "STATE_TRANSITION_REQUIRED"
    STATE_QUARANTINE_REQUIRED = "STATE_QUARANTINE_REQUIRED"
    CONTROL_REASSESSMENT_REQUIRED = "CONTROL_REASSESSMENT_REQUIRED"
    CONTROL_FAILURE = "CONTROL_FAILURE"
    CONTROL_DEFICIENCY_CREATED = "CONTROL_DEFICIENCY_CREATED"
    OBLIGATION_TRIGGERED = "OBLIGATION_TRIGGERED"
    EVIDENCE_REFRESH_REQUIRED = "EVIDENCE_REFRESH_REQUIRED"
    EVIDENCE_INVALIDATED = "EVIDENCE_INVALIDATED"
    COMPENSATING_CONTROL_REQUIRED = "COMPENSATING_CONTROL_REQUIRED"
    REMEDIATION_REQUIRED = "REMEDIATION_REQUIRED"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    INCIDENT_REQUIRED = "INCIDENT_REQUIRED"


class ConditionFailureSeverity(StrEnum):
    INFORMATIONAL = "INFORMATIONAL"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConditionFailureStatus(StrEnum):
    DETECTED = "DETECTED"
    IMPACT_ANALYSIS_PENDING = "IMPACT_ANALYSIS_PENDING"
    ACTIVE = "ACTIVE"
    REMEDIATION_IN_PROGRESS = "REMEDIATION_IN_PROGRESS"
    REASSESSMENT_PENDING = "REASSESSMENT_PENDING"
    RESOLVED = "RESOLVED"
    ACCEPTED = "ACCEPTED"
    SUPERSEDED = "SUPERSEDED"


class ConditionFailureDetectionMode(StrEnum):
    EVENT_DRIVEN = "EVENT_DRIVEN"
    POLLING = "POLLING"
    SCHEDULED_REEVALUATION = "SCHEDULED_REEVALUATION"
    DEPENDENCY_PROPAGATION = "DEPENDENCY_PROPAGATION"
    EVIDENCE_EXPIRATION = "EVIDENCE_EXPIRATION"
    MANUAL_REASSESSMENT = "MANUAL_REASSESSMENT"
    CONTROL_MONITORING = "CONTROL_MONITORING"
    EXTERNAL_NOTIFICATION = "EXTERNAL_NOTIFICATION"
    STATE_TRANSITION = "STATE_TRANSITION"
    POLICY_REEVALUATION = "POLICY_REEVALUATION"


class ConditionDependencyType(StrEnum):
    REQUIRES = "REQUIRES"
    IMPLIES = "IMPLIES"
    SUPPORTS = "SUPPORTS"
    CORROBORATES = "CORROBORATES"
    FALLBACK = "FALLBACK"
    OVERRIDES = "OVERRIDES"
    EXCLUDES = "EXCLUDES"


class ConditionClauseType(StrEnum):
    OBJECT_KIND_IS = "object_kind_is"
    LIFECYCLE_STATE_IS = "lifecycle_state_is"
    SPEC_EQUALS = "spec_equals"
    RELATIONSHIP_EXISTS = "relationship_exists"
    RELATIONSHIP_COUNT = "relationship_count"


class DecisionEffect(StrEnum):
    PERMIT = "PERMIT"
    PROHIBIT = "PROHIBIT"
    REQUIRE = "REQUIRE"
    DEFER = "DEFER"
    ESCALATE = "ESCALATE"
    ABSTAIN = "ABSTAIN"


class DecisionEvaluationStatus(StrEnum):
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class DecisionCombiningAlgorithm(StrEnum):
    DENY_OVERRIDES = "DENY_OVERRIDES"
    PERMIT_OVERRIDES = "PERMIT_OVERRIDES"


class DecisionType(StrEnum):
    APPROVAL = "APPROVAL"
    SELECTION = "SELECTION"
    CLASSIFICATION = "CLASSIFICATION"
    ACCEPTANCE = "ACCEPTANCE"
    REJECTION = "REJECTION"
    PRIORITIZATION = "PRIORITIZATION"
    ALLOCATION = "ALLOCATION"
    CERTIFICATION = "CERTIFICATION"
    DETERMINATION = "DETERMINATION"
    ADJUDICATION = "ADJUDICATION"
    ESCALATION = "ESCALATION"
    EXCEPTION = "EXCEPTION"
    OVERRIDE = "OVERRIDE"


class DecisionOutcome(StrEnum):
    APPROVED = "APPROVED"
    CONDITIONALLY_APPROVED = "CONDITIONALLY_APPROVED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"
    ESCALATED = "ESCALATED"
    ABSTAINED = "ABSTAINED"
    WITHDRAWN = "WITHDRAWN"
    NO_DECISION = "NO_DECISION"


class DecisionEvidenceCompleteness(StrEnum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    STALE = "STALE"
    CONFLICTING = "CONFLICTING"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


class DecisionValidityResult(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    SUSPENDED = "SUSPENDED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


class ObligationTriggerSource(StrEnum):
    POLICY_DECISION = "POLICY_DECISION"


class ObligationSubjectBinding(StrEnum):
    DECISION_RESOURCE = "DECISION_RESOURCE"


class ObligationAssignmentStrategy(StrEnum):
    ROLE = "ROLE"
    STATIC = "STATIC"


class ObligationTimingActivation(StrEnum):
    IMMEDIATE = "IMMEDIATE"


class ObligationLifecycleState(StrEnum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    IN_PROGRESS = "IN_PROGRESS"
    FULFILLED = "FULFILLED"
    BREACHED = "BREACHED"
    WAIVED = "WAIVED"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class ObligationFulfillmentResult(StrEnum):
    FULFILLED = "FULFILLED"
    NOT_FULFILLED = "NOT_FULFILLED"
    PARTIALLY_FULFILLED = "PARTIALLY_FULFILLED"
    UNKNOWN = "UNKNOWN"
    EXEMPTED = "EXEMPTED"


class ObligationActivationOutcome(StrEnum):
    ACTIVATED = "ACTIVATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class ConstraintRequirement(StrEnum):
    MUST_HOLD = "MUST_HOLD"
    MUST_NOT_HOLD = "MUST_NOT_HOLD"
    MUST_REMAIN = "MUST_REMAIN"
    MUST_BECOME = "MUST_BECOME"
    MUST_CEASE = "MUST_CEASE"


class ConstraintEvaluationResult(StrEnum):
    SATISFIED = "SATISFIED"
    VIOLATED = "VIOLATED"
    UNKNOWN = "UNKNOWN"
    EXEMPTED = "EXEMPTED"


class ConstraintViolationState(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    WAIVED = "WAIVED"


class TaskLifecycleState(StrEnum):
    CREATED = "CREATED"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    SUSPENDED = "SUSPENDED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class TaskMode(StrEnum):
    DEFINED = "DEFINED"
    AD_HOC = "AD_HOC"


class TaskDependencyType(StrEnum):
    START_AFTER = "START_AFTER"
    COMPLETE_AFTER = "COMPLETE_AFTER"
    REQUIRES_SUCCESS = "REQUIRES_SUCCESS"
    REQUIRES_OUTPUT = "REQUIRES_OUTPUT"
    REQUIRES_EVIDENCE = "REQUIRES_EVIDENCE"


class TaskCompletionResult(StrEnum):
    COMPLETED = "COMPLETED"
    NOT_COMPLETED = "NOT_COMPLETED"
    UNKNOWN = "UNKNOWN"


class TaskOutputSource(StrEnum):
    OBSERVED = "OBSERVED"
    AI_INFERRED = "AI_INFERRED"
    HUMAN_DECLARED = "HUMAN_DECLARED"


class PlanLifecycleState(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"
    COMPLETED = "COMPLETED"


class PlanValidationResult(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    CONDITIONALLY_VALID = "CONDITIONALLY_VALID"
    UNKNOWN = "UNKNOWN"


class PriorityClass(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PreemptionMode(StrEnum):
    NON_PREEMPTIBLE = "NON_PREEMPTIBLE"
    PREEMPTIBLE = "PREEMPTIBLE"
    CONDITIONALLY_PREEMPTIBLE = "CONDITIONALLY_PREEMPTIBLE"


class ReservationLifecycleState(StrEnum):
    REQUESTED = "REQUESTED"
    ACTIVE = "ACTIVE"
    CONSUMED = "CONSUMED"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    PREEMPTED = "PREEMPTED"


class PreemptionEffect(StrEnum):
    PERMIT = "PERMIT"
    DENY = "DENY"
    CONDITIONAL = "CONDITIONAL"
    INDETERMINATE = "INDETERMINATE"


class RiskDomain(StrEnum):
    SECURITY = "SECURITY"
    PRIVACY = "PRIVACY"
    OPERATIONAL = "OPERATIONAL"
    FINANCIAL = "FINANCIAL"
    LEGAL = "LEGAL"
    REGULATORY = "REGULATORY"
    SAFETY = "SAFETY"
    MODEL = "MODEL"
    SUPPLIER = "SUPPLIER"
    STRATEGIC = "STRATEGIC"
    REPUTATIONAL = "REPUTATIONAL"


class RiskLifecycleState(StrEnum):
    IDENTIFIED = "IDENTIFIED"
    ASSESSING = "ASSESSING"
    OPEN = "OPEN"
    TREATING = "TREATING"
    MONITORING = "MONITORING"
    CLOSED = "CLOSED"
    DEFERRED = "DEFERRED"
    TRANSFERRED = "TRANSFERRED"
    INVALIDATED = "INVALIDATED"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class LikelihoodType(StrEnum):
    QUALITATIVE = "QUALITATIVE"
    PROBABILITY = "PROBABILITY"
    FREQUENCY = "FREQUENCY"


class ControlType(StrEnum):
    PREVENTIVE = "PREVENTIVE"
    DETECTIVE = "DETECTIVE"
    CORRECTIVE = "CORRECTIVE"
    RECOVERY = "RECOVERY"
    COMPENSATING = "COMPENSATING"
    DIRECTIVE = "DIRECTIVE"
    ASSURANCE = "ASSURANCE"
    DETERRENT = "DETERRENT"


class ControlState(StrEnum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"


class ControlEffectivenessResult(StrEnum):
    EFFECTIVE = "EFFECTIVE"
    PARTIALLY_EFFECTIVE = "PARTIALLY_EFFECTIVE"
    INEFFECTIVE = "INEFFECTIVE"
    NOT_TESTED = "NOT_TESTED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ControlExecutionModality(StrEnum):
    MANUAL = "MANUAL"
    AUTOMATED = "AUTOMATED"
    HYBRID = "HYBRID"


class ControlEnforcementMode(StrEnum):
    BLOCKING = "BLOCKING"
    NON_BLOCKING = "NON_BLOCKING"
    ADVISORY = "ADVISORY"
    OBSERVATIONAL = "OBSERVATIONAL"


class ControlCriticality(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ControlExecutionStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    STARTED = "STARTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"
    MISSING = "MISSING"


class ControlEvaluationOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    EXEMPT = "EXEMPT"
    PARTIAL = "PARTIAL"


class ControlEnforcementOutcome(StrEnum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    QUARANTINED = "QUARANTINED"
    REMEDIATED = "REMEDIATED"
    ESCALATED = "ESCALATED"
    NO_ACTION = "NO_ACTION"
    NOT_REQUIRED = "NOT_REQUIRED"
    ERROR = "ERROR"


class RiskTreatmentStrategy(StrEnum):
    AVOID = "AVOID"
    MITIGATE = "MITIGATE"
    TRANSFER = "TRANSFER"
    ACCEPT = "ACCEPT"
    SHARE = "SHARE"
    MONITOR = "MONITOR"


class RiskTreatmentStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


class RiskAcceptanceStatus(StrEnum):
    REQUESTED = "REQUESTED"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class RemediationTriggerType(StrEnum):
    CONTROL_FAILURE = "CONTROL_FAILURE"
    CONTROL_DEFICIENCY = "CONTROL_DEFICIENCY"
    CONDITION_FAILURE = "CONDITION_FAILURE"
    EVIDENCE_GAP = "EVIDENCE_GAP"
    EVIDENCE_INVALIDATION = "EVIDENCE_INVALIDATION"
    ASSURANCE_GAP = "ASSURANCE_GAP"
    ASSURANCE_DEFICIENCY = "ASSURANCE_DEFICIENCY"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    OBLIGATION_BREACH = "OBLIGATION_BREACH"
    AUTHORIZATION_FAILURE = "AUTHORIZATION_FAILURE"
    INCIDENT = "INCIDENT"
    AUDIT_FINDING = "AUDIT_FINDING"
    RISK_DECISION = "RISK_DECISION"
    MANUAL_FINDING = "MANUAL_FINDING"
    EXTERNAL_FINDING = "EXTERNAL_FINDING"
    RECURRENCE = "RECURRENCE"


class RemediationSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RemediationPriority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class RemediationStatus(StrEnum):
    DETECTED = "DETECTED"
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    CONTAINMENT_IN_PROGRESS = "CONTAINMENT_IN_PROGRESS"
    CONTAINED = "CONTAINED"
    ANALYSIS_IN_PROGRESS = "ANALYSIS_IN_PROGRESS"
    PLAN_APPROVED = "PLAN_APPROVED"
    IMPLEMENTATION_IN_PROGRESS = "IMPLEMENTATION_IN_PROGRESS"
    IMPLEMENTED = "IMPLEMENTED"
    VERIFICATION_IN_PROGRESS = "VERIFICATION_IN_PROGRESS"
    VERIFIED = "VERIFIED"
    MONITORING = "MONITORING"
    ACCEPTED = "ACCEPTED"
    CLOSED = "CLOSED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"
    EXCEPTION_ACTIVE = "EXCEPTION_ACTIVE"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"


class RemediationVerificationResult(StrEnum):
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"


class RemediationEffectivenessResult(StrEnum):
    EFFECTIVE = "EFFECTIVE"
    PARTIALLY_EFFECTIVE = "PARTIALLY_EFFECTIVE"
    INEFFECTIVE = "INEFFECTIVE"
    UNKNOWN = "UNKNOWN"


class RemediationAcceptanceResult(StrEnum):
    ACCEPTED = "ACCEPTED"
    CONDITIONALLY_ACCEPTED = "CONDITIONALLY_ACCEPTED"
    REJECTED = "REJECTED"


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
    schema_version: str = "1.0.0"
    additional_properties: AdditionalPropertiesPolicy = AdditionalPropertiesPolicy.FORBID


@dataclass(frozen=True, slots=True)
class NamespaceDefinition:
    id: str
    parent: str | None = None
    active: bool = True
    owners: tuple[ActorReference, ...] = ()


@dataclass(frozen=True, slots=True)
class RelationshipTypeDefinition:
    id: str
    name: str
    source_kinds: tuple[str, ...]
    target_kinds: tuple[str, ...]
    version: str = "1.0.0"
    symmetric: bool = False
    transitive: bool = False
    inverse_name: str | None = None
    cardinality: RelationshipCardinality = RelationshipCardinality.MANY_TO_MANY
    lifecycle: RelationshipLifecycle = RelationshipLifecycle.ACTIVE
    required_evidence: tuple[str, ...] = ()
    description: str | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "sourceKinds": list(self.source_kinds),
            "targetKinds": list(self.target_kinds),
            "symmetric": self.symmetric,
            "transitive": self.transitive,
            "inverseName": self.inverse_name,
            "cardinality": self.cardinality.value,
            "lifecycle": self.lifecycle.value,
            "requiredEvidence": list(self.required_evidence),
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class RelationshipEvidence:
    type: str
    reference: ObjectReference

    def canonical_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "type": self.type,
            "$ref": {"id": self.reference.id},
        }
        if self.reference.revision is not None:
            document["$ref"]["revision"] = self.reference.revision
        if self.reference.resolution is not ResolutionMode.LATEST:
            document["$ref"]["resolution"] = self.reference.resolution.value
        return document


@dataclass(frozen=True, slots=True)
class RelationshipInstance:
    id: str
    type_id: str
    source: ObjectReference
    target: ObjectReference
    lifecycle: RelationshipLifecycle = RelationshipLifecycle.ACTIVE
    evidence: tuple[RelationshipEvidence, ...] = ()

    def canonical_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "id": self.id,
            "type": {"$ref": {"id": self.type_id}},
            "source": {"$ref": {"id": self.source.id}},
            "target": {"$ref": {"id": self.target.id}},
        }
        if self.source.revision is not None:
            document["source"]["$ref"]["revision"] = self.source.revision
        if self.target.revision is not None:
            document["target"]["$ref"]["revision"] = self.target.revision
        if self.source.resolution is not ResolutionMode.LATEST:
            document["source"]["$ref"]["resolution"] = self.source.resolution.value
        if self.target.resolution is not ResolutionMode.LATEST:
            document["target"]["$ref"]["resolution"] = self.target.resolution.value
        document["lifecycle"] = {"state": self.lifecycle.value}
        if self.evidence:
            document["evidence"] = [
                evidence.canonical_document()
                for evidence in sorted(self.evidence, key=lambda item: item.type)
            ]
        return document


@dataclass(frozen=True, slots=True)
class SemanticConditionClause:
    clause_type: ConditionClauseType
    path: str | None = None
    expected: Any = None
    relationship_type_id: str | None = None
    target_kind: str | None = None
    target_id: str | None = None
    min_count: int | None = None
    max_count: int | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "type": self.clause_type.value,
            "path": self.path,
            "expected": self.expected,
            "relationshipTypeId": self.relationship_type_id,
            "targetKind": self.target_kind,
            "targetId": self.target_id,
            "minCount": self.min_count,
            "maxCount": self.max_count,
        }


@dataclass(frozen=True, slots=True)
class SemanticConditionDefinition:
    id: str
    name: str
    subject_kinds: tuple[str, ...]
    clauses: tuple[SemanticConditionClause, ...]
    version: str = "1.0.0"
    description: str | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "subjectKinds": list(self.subject_kinds),
            "clauses": [clause.canonical_document() for clause in self.clauses],
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class ConstraintDefinition:
    id: str
    name: str
    requirement: ConstraintRequirement
    condition_id: str
    subject_kinds: tuple[str, ...]
    version: str = "1.0.0"
    status: str = "ACTIVE"
    severity: str = "HIGH"
    description: str | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "status": self.status,
            "description": self.description,
            "requirement": self.requirement.value,
            "conditionId": self.condition_id,
            "subjectKinds": list(self.subject_kinds),
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class PriorityDefinition:
    id: str
    name: str
    rank: int
    priority_class: PriorityClass = PriorityClass.NORMAL
    version: str = "1.0.0"
    status: str = "ACTIVE"
    description: str | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "status": self.status,
            "description": self.description,
            "rank": self.rank,
            "class": self.priority_class.value,
        }


@dataclass(frozen=True, slots=True)
class ReservationDefinition:
    id: str
    name: str
    resource_type: str
    quantity_type: str = "unit"
    preemption_mode: PreemptionMode = PreemptionMode.NON_PREEMPTIBLE
    expiration_required: bool = True
    version: str = "1.0.0"
    status: str = "ACTIVE"
    description: str | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "status": self.status,
            "description": self.description,
            "resourceType": self.resource_type,
            "quantityType": self.quantity_type,
            "preemption": {"mode": self.preemption_mode.value},
            "lifecycle": {"expirationRequired": self.expiration_required},
        }


@dataclass(frozen=True, slots=True)
class PreemptionDefinition:
    id: str
    name: str
    resource_types: tuple[str, ...]
    minimum_priority_id: str
    target_modes: tuple[PreemptionMode, ...]
    condition_ids: tuple[str, ...] = ()
    policy_id: str | None = None
    compensation_required: bool = False
    required_evidence: tuple[str, ...] = ()
    minimum_priority_delta: int = 0
    version: str = "1.0.0"
    status: str = "ACTIVE"
    description: str | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "status": self.status,
            "description": self.description,
            "resourceTypes": list(self.resource_types),
            "requester": {
                "minimumPriority": {
                    "ref": self.minimum_priority_id,
                }
            },
            "target": {
                "requiredModes": [mode.value for mode in self.target_modes],
            },
            "conditions": [{"ref": condition_id} for condition_id in self.condition_ids],
            "authorization": (
                {"policy": {"ref": self.policy_id}}
                if self.policy_id is not None
                else None
            ),
            "compensation": {"required": self.compensation_required},
            "evidence": {"required": list(self.required_evidence)},
            "priorityDelta": {"minimum": self.minimum_priority_delta},
        }


@dataclass(frozen=True, slots=True)
class RiskDefinition:
    id: str
    name: str
    domain: RiskDomain
    subject_kinds: tuple[str, ...]
    version: str = "1.0.0"
    status: str = "ACTIVE"
    scenario_required: bool = True
    likelihood_model_ref: str | None = None
    impact_model_ref: str | None = None
    treatment_definition_ref: str | None = None
    acceptance_policy_id: str | None = None
    description: str | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "status": self.status,
            "description": self.description,
            "domain": self.domain.value,
            "subjectKinds": list(self.subject_kinds),
            "scenarios": {"required": self.scenario_required},
            "assessment": {
                "likelihood": {"ref": self.likelihood_model_ref},
                "impact": {"ref": self.impact_model_ref},
            },
            "treatment": {"ref": self.treatment_definition_ref},
            "acceptance": {"policyRef": self.acceptance_policy_id},
        }


@dataclass(frozen=True, slots=True)
class RiskScenario:
    id: str
    name: str
    subject_ref: ObjectReference
    adverse_outcome_ref: str
    threat_ref: str | None = None
    vulnerability_ref: str | None = None
    source_ref: str | None = None
    version: str = "1.0.0"
    status: str = "ACTIVE"
    description: str | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "status": self.status,
            "description": self.description,
            "subject": {
                "id": self.subject_ref.id,
                "revision": self.subject_ref.revision,
            },
            "sourceRef": self.source_ref,
            "threatRef": self.threat_ref,
            "vulnerabilityRef": self.vulnerability_ref,
            "adverseOutcomeRef": self.adverse_outcome_ref,
        }


@dataclass(frozen=True, slots=True)
class ControlDefinition:
    id: str
    name: str
    control_type: ControlType
    applies_to_kinds: tuple[str, ...]
    version: str = "1.0.0"
    status: str = "ACTIVE"
    required_evidence: tuple[str, ...] = ()
    objective_ref: str | None = None
    objective_refs: tuple[str, ...] = ()
    requirement_refs: tuple[str, ...] = ()
    owner_ref: str | None = None
    operator_refs: tuple[str, ...] = ()
    applicability_ref: str | None = None
    implementation_refs: tuple[str, ...] = ()
    trigger_refs: tuple[str, ...] = ()
    frequency_ref: str | None = None
    evidence_requirement_refs: tuple[str, ...] = ()
    test_definition_refs: tuple[str, ...] = ()
    monitoring_ref: str | None = None
    dependency_refs: tuple[str, ...] = ()
    failure_policy_ref: str | None = None
    lifecycle_ref: str | None = None
    ai_policy_ref: str | None = None
    execution_modality: ControlExecutionModality = ControlExecutionModality.AUTOMATED
    enforcement_mode: ControlEnforcementMode = ControlEnforcementMode.BLOCKING
    criticality: ControlCriticality = ControlCriticality.MODERATE
    description: str | None = None

    def canonical_document(self) -> dict[str, Any]:
        objective_refs = self.objective_refs
        if self.objective_ref is not None and self.objective_ref not in objective_refs:
            objective_refs = (self.objective_ref, *objective_refs)
        evidence_requirement_refs = self.evidence_requirement_refs
        for evidence_type in self.required_evidence:
            if evidence_type not in evidence_requirement_refs:
                evidence_requirement_refs = (*evidence_requirement_refs, evidence_type)
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "status": self.status,
            "description": self.description,
            "objectiveRefs": list(objective_refs),
            "requirementRefs": list(self.requirement_refs),
            "classification": {
                "purpose": self.control_type.value,
                "execution": self.execution_modality.value,
                "enforcement": self.enforcement_mode.value,
                "criticality": self.criticality.value,
            },
            "appliesToKinds": list(self.applies_to_kinds),
            "applicabilityRef": self.applicability_ref,
            "implementationRefs": list(self.implementation_refs),
            "triggerRefs": list(self.trigger_refs),
            "ownerRef": self.owner_ref,
            "operatorRefs": list(self.operator_refs),
            "frequencyRef": self.frequency_ref,
            "evidenceRequirementRefs": list(evidence_requirement_refs),
            "testDefinitionRefs": list(self.test_definition_refs),
            "monitoringRef": self.monitoring_ref,
            "dependencyRefs": list(self.dependency_refs),
            "failurePolicyRef": self.failure_policy_ref,
            "lifecycleRef": self.lifecycle_ref,
            "aiPolicyRef": self.ai_policy_ref,
        }


@dataclass(frozen=True, slots=True)
class ControlResult:
    execution_status: ControlExecutionStatus
    evaluation_outcome: ControlEvaluationOutcome
    enforcement_outcome: ControlEnforcementOutcome
    evidence_refs: tuple[ObjectReference, ...] = ()
    finding_codes: tuple[str, ...] = ()

    def canonical_document(self) -> dict[str, Any]:
        return {
            "executionStatus": self.execution_status.value,
            "evaluationOutcome": self.evaluation_outcome.value,
            "enforcementOutcome": self.enforcement_outcome.value,
            "evidenceRefs": [
                {"id": reference.id, "revision": reference.revision}
                for reference in self.evidence_refs
            ],
            "findingCodes": list(self.finding_codes),
        }


@dataclass(frozen=True, slots=True)
class ControlCoverage:
    expected_population: int
    evaluated_population: int
    passed_population: int
    failed_population: int = 0
    unknown_population: int = 0
    exempt_population: int = 0
    missing_population: int = 0

    def __post_init__(self) -> None:
        populations = (
            self.expected_population,
            self.evaluated_population,
            self.passed_population,
            self.failed_population,
            self.unknown_population,
            self.exempt_population,
            self.missing_population,
        )
        if any(population < 0 for population in populations):
            raise RegistryError("CONTROL_COVERAGE_POPULATION_INVALID", "negative")
        if self.evaluated_population > self.expected_population:
            raise RegistryError("CONTROL_COVERAGE_POPULATION_INVALID", "evaluated")
        classified_population = (
            self.passed_population
            + self.failed_population
            + self.unknown_population
            + self.exempt_population
            + self.missing_population
        )
        if classified_population > self.expected_population:
            raise RegistryError("CONTROL_COVERAGE_POPULATION_INVALID", "classified")

    def canonical_document(self) -> dict[str, Any]:
        coverage_ratio = (
            self.evaluated_population / self.expected_population
            if self.expected_population
            else None
        )
        pass_ratio = (
            self.passed_population / self.evaluated_population
            if self.evaluated_population
            else None
        )
        return {
            "expectedPopulation": self.expected_population,
            "evaluatedPopulation": self.evaluated_population,
            "passedPopulation": self.passed_population,
            "failedPopulation": self.failed_population,
            "unknownPopulation": self.unknown_population,
            "exemptPopulation": self.exempt_population,
            "missingPopulation": self.missing_population,
            "coverageRatio": coverage_ratio,
            "passRatio": pass_ratio,
        }


@dataclass(frozen=True, slots=True)
class ControlEffectivenessAssessment:
    id: str
    control_ref: str
    design_effectiveness: ControlEffectivenessResult
    operating_effectiveness: ControlEffectivenessResult
    coverage_effectiveness: ControlEffectivenessResult
    conclusion: ControlEffectivenessResult
    evidence_refs: tuple[ObjectReference, ...]
    assessed_at: datetime
    assessor_ref: str
    valid_until: datetime | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "controlRef": self.control_ref,
            "designEffectiveness": self.design_effectiveness.value,
            "operatingEffectiveness": self.operating_effectiveness.value,
            "coverageEffectiveness": self.coverage_effectiveness.value,
            "conclusion": self.conclusion.value,
            "evidenceRefs": [
                {"id": reference.id, "revision": reference.revision}
                for reference in self.evidence_refs
            ],
            "assessedAt": self.assessed_at.isoformat(),
            "assessorRef": self.assessor_ref,
            "validUntil": self.valid_until.isoformat() if self.valid_until else None,
        }


@dataclass(frozen=True, slots=True)
class TaskOutputDefinition:
    id: str
    type: str
    target_kind: str | None = None
    enum_values: tuple[str, ...] = ()

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "targetKind": self.target_kind,
            "enumValues": list(self.enum_values),
        }


@dataclass(frozen=True, slots=True)
class TaskDefinition:
    id: str
    name: str
    version: str = "1.0.0"
    completion_condition_id: str | None = None
    allowed_actions: tuple[str, ...] = ()
    required_constraint_ids: tuple[str, ...] = ()
    outputs: tuple[TaskOutputDefinition, ...] = ()
    status: str = "ACTIVE"

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "status": self.status,
            "completionConditionId": self.completion_condition_id,
            "allowedActions": list(self.allowed_actions),
            "requiredConstraintIds": list(self.required_constraint_ids),
            "outputs": [output.canonical_document() for output in self.outputs],
        }


@dataclass(frozen=True, slots=True)
class TaskDependency:
    task_id: str
    dependency_type: TaskDependencyType = TaskDependencyType.COMPLETE_AFTER
    output_id: str | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "taskId": self.task_id,
            "type": self.dependency_type.value,
            "outputId": self.output_id,
        }


@dataclass(frozen=True, slots=True)
class DecisionConstraint:
    type: str
    value: Any

    def canonical_document(self) -> dict[str, Any]:
        return {"type": self.type, "value": self.value}


@dataclass(frozen=True, slots=True)
class DecisionAdvice:
    code: str
    message: str

    def canonical_document(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True, slots=True)
class DecisionQuestion:
    statement: str

    def canonical_document(self) -> dict[str, Any]:
        return {"statement": self.statement}


@dataclass(frozen=True, slots=True)
class DecisionEvidenceRequirement:
    required_types: tuple[str, ...]
    freshness: str | None = None
    missing_evidence_effect: DecisionEffect = DecisionEffect.DEFER

    def canonical_document(self) -> dict[str, Any]:
        return {
            "requiredTypes": list(self.required_types),
            "freshness": self.freshness,
            "missingEvidenceEffect": self.missing_evidence_effect.value,
        }


@dataclass(frozen=True, slots=True)
class DecisionAuthorityRequirement:
    operator: str
    authority_refs: tuple[str, ...]

    def canonical_document(self) -> dict[str, Any]:
        return {
            "operator": self.operator,
            "authorityRefs": list(self.authority_refs),
        }


@dataclass(frozen=True, slots=True)
class DecisionBinding:
    subject_ref: ObjectReference
    subject_digest: str | None = None
    evidence_set_digest: str | None = None
    policy_version: str | None = None
    authority_resolution_version: str | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "subject": {
                "id": self.subject_ref.id,
                "revision": self.subject_ref.revision,
            },
            "subjectDigest": self.subject_digest,
            "evidenceSetDigest": self.evidence_set_digest,
            "policyVersion": self.policy_version,
            "authorityResolutionVersion": self.authority_resolution_version,
        }


@dataclass(frozen=True, slots=True)
class DecisionValidity:
    decision_ref: str
    result: DecisionValidityResult
    evaluated_at: datetime
    checks: dict[str, str]
    valid_until: datetime | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "decisionRef": self.decision_ref,
            "result": self.result.value,
            "evaluatedAt": self.evaluated_at.isoformat(),
            "validUntil": self.valid_until.isoformat() if self.valid_until else None,
            "checks": dict(sorted(self.checks.items())),
        }


@dataclass(frozen=True, slots=True)
class DecisionDefinition:
    id: str
    name: str
    action: str
    resource_kinds: tuple[str, ...] = ()
    decision_type: DecisionType = DecisionType.APPROVAL
    question: DecisionQuestion | None = None
    outcome_set: tuple[DecisionOutcome, ...] = ()
    alternatives: tuple[str, ...] = ()
    criteria_ids: tuple[str, ...] = ()
    authority_requirement: DecisionAuthorityRequirement | None = None
    evidence_requirement: DecisionEvidenceRequirement | None = None
    validity_policy_ref: str | None = None
    effect_ref: str | None = None
    condition_ids: tuple[str, ...] = ()
    policy_ids: tuple[str, ...] = ()
    combining_algorithm: DecisionCombiningAlgorithm = DecisionCombiningAlgorithm.DENY_OVERRIDES
    version: str = "1.0.0"
    unknown_condition_effect: DecisionEffect = DecisionEffect.DEFER
    unsatisfied_condition_effect: DecisionEffect = DecisionEffect.PROHIBIT
    constraints: tuple[DecisionConstraint, ...] = ()
    advice: tuple[DecisionAdvice, ...] = ()
    validity_seconds: int | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "decisionType": self.decision_type.value,
            "question": (
                self.question.canonical_document() if self.question is not None else None
            ),
            "outcomeSet": [outcome.value for outcome in self.outcome_set],
            "alternatives": list(self.alternatives),
            "criteriaIds": list(self.criteria_ids),
            "authorityRequirement": (
                self.authority_requirement.canonical_document()
                if self.authority_requirement is not None
                else None
            ),
            "evidenceRequirement": (
                self.evidence_requirement.canonical_document()
                if self.evidence_requirement is not None
                else None
            ),
            "validityPolicyRef": self.validity_policy_ref,
            "effectRef": self.effect_ref,
            "action": self.action,
            "resourceKinds": list(self.resource_kinds),
            "conditionIds": list(self.condition_ids),
            "policyIds": list(self.policy_ids),
            "combiningAlgorithm": self.combining_algorithm.value,
            "unknownConditionEffect": self.unknown_condition_effect.value,
            "unsatisfiedConditionEffect": self.unsatisfied_condition_effect.value,
            "constraints": [
                constraint.canonical_document() for constraint in self.constraints
            ],
            "advice": [advice.canonical_document() for advice in self.advice],
            "validity": {
                "maximumAgeSeconds": self.validity_seconds,
            },
        }


@dataclass(frozen=True, slots=True)
class DecisionRequest:
    id: str
    decision_id: str
    resource_id: str
    actor: ActorReference
    requested_action: str | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "decisionId": self.decision_id,
            "resourceId": self.resource_id,
            "actor": self.actor.id,
            "requestedAction": self.requested_action,
            "context": self.context,
        }


@dataclass(frozen=True, slots=True)
class ObligationTrigger:
    source: ObligationTriggerSource
    decision_effect: DecisionEffect | None = None
    policy_id: str | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "decisionEffect": (
                self.decision_effect.value if self.decision_effect is not None else None
            ),
            "policyId": self.policy_id,
        }


@dataclass(frozen=True, slots=True)
class ObligationSubject:
    binding: ObligationSubjectBinding = ObligationSubjectBinding.DECISION_RESOURCE

    def canonical_document(self) -> dict[str, Any]:
        return {"binding": self.binding.value}


@dataclass(frozen=True, slots=True)
class ObligationResponsibility:
    strategy: ObligationAssignmentStrategy
    assignee_ref: str

    def canonical_document(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy.value,
            "assigneeRef": self.assignee_ref,
        }


@dataclass(frozen=True, slots=True)
class ObligationDuty:
    action_ref: str | None = None
    condition_id: str | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "actionRef": self.action_ref,
            "conditionId": self.condition_id,
        }


@dataclass(frozen=True, slots=True)
class ObligationTiming:
    activation: ObligationTimingActivation = ObligationTimingActivation.IMMEDIATE
    completion_within: str | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "activation": self.activation.value,
            "completionWithin": self.completion_within,
        }


@dataclass(frozen=True, slots=True)
class ObligationBreach:
    condition_id: str | None = None
    severity: str | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "conditionId": self.condition_id,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class ObligationWaiverPolicy:
    allowed: bool = False
    policy_id: str | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "policyId": self.policy_id,
        }


@dataclass(frozen=True, slots=True)
class ObligationDefinition:
    id: str
    name: str
    trigger: ObligationTrigger
    subject: ObligationSubject
    duty: ObligationDuty
    responsibility: ObligationResponsibility
    version: str = "1.0.0"
    status: str = "ACTIVE"
    applicability_condition_id: str | None = None
    timing: ObligationTiming = field(default_factory=ObligationTiming)
    fulfillment_condition_id: str | None = None
    required_evidence: tuple[str, ...] = ()
    breach: ObligationBreach | None = None
    waiver: ObligationWaiverPolicy = field(default_factory=ObligationWaiverPolicy)
    description: str | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "status": self.status,
            "description": self.description,
            "trigger": self.trigger.canonical_document(),
            "applicabilityConditionId": self.applicability_condition_id,
            "subject": self.subject.canonical_document(),
            "duty": self.duty.canonical_document(),
            "responsibility": self.responsibility.canonical_document(),
            "timing": self.timing.canonical_document(),
            "fulfillmentConditionId": self.fulfillment_condition_id,
            "requiredEvidence": list(self.required_evidence),
            "breach": self.breach.canonical_document() if self.breach is not None else None,
            "waiver": self.waiver.canonical_document(),
        }


@dataclass(frozen=True, slots=True)
class StateDefinition:
    name: str
    label: str | None = None
    terminal: bool = False


@dataclass(frozen=True, slots=True)
class StateTransitionDefinition:
    name: str
    source_states: tuple[str, ...]
    target_state: str
    action_id: str | None = None
    classification: TransitionClassification = TransitionClassification.NORMAL


@dataclass(frozen=True, slots=True)
class StateMachineDefinition:
    id: str
    applies_to_kind: str
    initial_state: str
    states: tuple[StateDefinition, ...]
    transitions: tuple[StateTransitionDefinition, ...]
    version: str = "1.0.0"

    @property
    def terminal_states(self) -> frozenset[str]:
        return frozenset(state.name for state in self.states if state.terminal)


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
class ValidationFinding:
    code: str
    path: str
    message: str
    expected: Any = None
    actual: Any = None
    constraint: str | None = None
    schema_ref: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    type_ref: str
    schema_version: str
    errors: tuple[ValidationFinding, ...]
    warnings: tuple[ValidationFinding, ...]
    validated_at: datetime
    validator_version: str = VALIDATOR_VERSION


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


@dataclass(frozen=True, slots=True)
class ConditionFinding:
    code: str
    message: str
    clause: str | None = None


@dataclass(frozen=True, slots=True)
class ConditionEvaluation:
    condition_id: str
    condition_version: str | None
    subject_id: str
    subject_revision: int | None
    outcome: ConditionOutcome
    findings: tuple[ConditionFinding, ...]
    proof: dict[str, Any]
    proof_hash: str
    evaluated_at: datetime

    def canonical_document(self) -> dict[str, Any]:
        return {
            "condition": {
                "id": self.condition_id,
                "version": self.condition_version,
            },
            "subject": {
                "id": self.subject_id,
                "revision": self.subject_revision,
            },
            "outcome": self.outcome.value,
            "findings": [
                {
                    "code": finding.code,
                    "message": finding.message,
                    "clause": finding.clause,
                }
                for finding in self.findings
            ],
            "proof": self.proof,
            "proofHash": self.proof_hash,
            "evaluatedAt": self.evaluated_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ConditionFailureScope:
    type: str
    refs: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()

    def canonical_document(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "refs": list(self.refs),
            "actions": list(self.actions),
        }


@dataclass(frozen=True, slots=True)
class ConditionFailurePolicy:
    id: str
    condition_ids: tuple[str, ...]
    transitions_from: tuple[ConditionOutcome, ...]
    transitions_to: tuple[ConditionOutcome, ...]
    effects: tuple[ConditionFailureEffect, ...]
    scope: ConditionFailureScope
    version: str = "1.0.0"
    severity: ConditionFailureSeverity = ConditionFailureSeverity.MEDIUM
    grace_period: str | None = None
    reassessment_deadline: str | None = None
    recovery_mode: str = "REASSESS_BEFORE_RESTORE"
    ai_may_resolve: bool = False
    ai_may_create_exception: bool = False

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "appliesTo": {"conditionIds": list(self.condition_ids)},
            "transitions": {
                "from": [outcome.value for outcome in self.transitions_from],
                "to": [outcome.value for outcome in self.transitions_to],
            },
            "classification": {"severity": self.severity.value},
            "timing": {
                "gracePeriod": self.grace_period,
                "reassessmentDeadline": self.reassessment_deadline,
            },
            "effects": [effect.value for effect in self.effects],
            "scope": self.scope.canonical_document(),
            "recovery": {"mode": self.recovery_mode},
            "ai": {
                "mayResolve": self.ai_may_resolve,
                "mayCreateException": self.ai_may_create_exception,
            },
        }


@dataclass(frozen=True, slots=True)
class ConditionDependency:
    id: str
    dependent_condition_id: str
    dependency_condition_id: str
    dependency_type: ConditionDependencyType = ConditionDependencyType.REQUIRES
    on_not_satisfied: ConditionOutcome = ConditionOutcome.NOT_SATISFIED
    on_unknown: ConditionOutcome = ConditionOutcome.UNKNOWN
    on_expired: ConditionOutcome = ConditionOutcome.UNKNOWN
    version: str = "1.0.0"

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "dependentCondition": {"id": self.dependent_condition_id},
            "dependency": {
                "id": self.dependency_condition_id,
                "type": self.dependency_type.value,
            },
            "semantics": {
                "onNotSatisfied": self.on_not_satisfied.value,
                "onUnknown": self.on_unknown.value,
                "onExpired": self.on_expired.value,
            },
        }


@dataclass(frozen=True, slots=True)
class ConditionFailure:
    id: str
    condition_id: str
    condition_version: str | None
    subject_ref: ObjectReference
    previous_evaluation: ConditionEvaluation
    current_evaluation: ConditionEvaluation
    transition_type: ConditionFailureTransitionType
    severity: ConditionFailureSeverity
    effects: tuple[ConditionFailureEffect, ...]
    policy_ref: str | None
    detected_at: datetime
    effective_at: datetime
    detection_mode: ConditionFailureDetectionMode
    status: ConditionFailureStatus = ConditionFailureStatus.ACTIVE
    cause: str = "UNKNOWN"

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "condition": {
                "id": self.condition_id,
                "version": self.condition_version,
            },
            "subject": {
                "id": self.subject_ref.id,
                "revision": self.subject_ref.revision,
            },
            "previousEvaluation": self.previous_evaluation.canonical_document(),
            "currentEvaluation": self.current_evaluation.canonical_document(),
            "transition": {
                "from": self.previous_evaluation.outcome.value,
                "to": self.current_evaluation.outcome.value,
                "type": self.transition_type.value,
            },
            "classification": {"severity": self.severity.value},
            "effects": [effect.value for effect in self.effects],
            "policyRef": self.policy_ref,
            "detectedAt": self.detected_at.isoformat(),
            "effectiveAt": self.effective_at.isoformat(),
            "detectionMode": self.detection_mode.value,
            "status": self.status.value,
            "cause": self.cause,
        }


@dataclass(frozen=True, slots=True)
class ConditionFailureImpact:
    id: str
    failure_ref: str
    decisions: tuple[str, ...] = ()
    authorizations: tuple[str, ...] = ()
    executions: tuple[str, ...] = ()
    controls: tuple[str, ...] = ()
    obligations: tuple[str, ...] = ()
    states: tuple[str, ...] = ()
    calculated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "failureRef": self.failure_ref,
            "affected": {
                "decisions": list(self.decisions),
                "authorizations": list(self.authorizations),
                "executions": list(self.executions),
                "controls": list(self.controls),
                "obligations": list(self.obligations),
                "states": list(self.states),
            },
            "calculatedAt": self.calculated_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class DecisionFinding:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class PolicyContribution:
    policy_id: str
    policy_revision: int
    effect: PolicyEffect
    obligations: tuple[PolicyObligation, ...] = ()

    def canonical_document(self) -> dict[str, Any]:
        return {
            "policy": {
                "id": self.policy_id,
                "revision": self.policy_revision,
            },
            "effect": self.effect.value,
            "obligations": [
                {
                    "type": obligation.type,
                    "authority": obligation.authority,
                    "evidenceType": obligation.evidence_type,
                }
                for obligation in self.obligations
            ],
        }


@dataclass(frozen=True, slots=True)
class DecisionEvaluation:
    request_id: str | None
    decision_id: str
    decision_version: str | None
    action: str
    resource_id: str
    resource_revision: int | None
    evaluation_status: DecisionEvaluationStatus
    outcome: str
    effect: DecisionEffect
    condition_evaluations: tuple[ConditionEvaluation, ...]
    policy_contributions: tuple[PolicyContribution, ...]
    obligations: tuple[PolicyObligation, ...]
    constraints: tuple[DecisionConstraint, ...]
    advice: tuple[DecisionAdvice, ...]
    findings: tuple[DecisionFinding, ...]
    proof: dict[str, Any]
    proof_hash: str
    evaluated_at: datetime
    valid_until: datetime | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "decision": {
                "id": self.decision_id,
                "version": self.decision_version,
            },
            "action": self.action,
            "resource": {
                "id": self.resource_id,
                "revision": self.resource_revision,
            },
            "evaluationStatus": self.evaluation_status.value,
            "outcome": self.outcome,
            "effect": self.effect.value,
            "conditions": [
                evaluation.canonical_document()
                for evaluation in self.condition_evaluations
            ],
            "policyContributions": [
                contribution.canonical_document()
                for contribution in self.policy_contributions
            ],
            "obligations": [
                {
                    "type": obligation.type,
                    "authority": obligation.authority,
                    "evidenceType": obligation.evidence_type,
                }
                for obligation in self.obligations
            ],
            "constraints": [
                constraint.canonical_document() for constraint in self.constraints
            ],
            "advice": [advice.canonical_document() for advice in self.advice],
            "findings": [
                {"code": finding.code, "message": finding.message}
                for finding in self.findings
            ],
            "proof": self.proof,
            "proofHash": self.proof_hash,
            "evaluatedAt": self.evaluated_at.isoformat(),
            "validUntil": (
                self.valid_until.isoformat() if self.valid_until is not None else None
            ),
        }


@dataclass(frozen=True, slots=True)
class ObligationEvidence:
    evidence_type: str
    reference: ObjectReference
    attached_at: datetime

    def canonical_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "type": self.evidence_type,
            "$ref": {"id": self.reference.id},
            "attachedAt": self.attached_at.isoformat(),
        }
        if self.reference.revision is not None:
            document["$ref"]["revision"] = self.reference.revision
        return document


@dataclass(frozen=True, slots=True)
class ObligationInstance:
    id: str
    activation_key: str
    definition_id: str
    definition_version: str
    source_decision_ref: str
    subject_ref: ObjectReference
    assignee_ref: str
    state: ObligationLifecycleState
    activated_at: datetime
    due_at: datetime | None
    evidence: tuple[ObligationEvidence, ...] = ()

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "activationKey": self.activation_key,
            "definition": {
                "id": self.definition_id,
                "version": self.definition_version,
            },
            "source": {
                "decisionRef": self.source_decision_ref,
            },
            "subject": {
                "id": self.subject_ref.id,
                "revision": self.subject_ref.revision,
            },
            "assigneeRef": self.assignee_ref,
            "state": self.state.value,
            "activatedAt": self.activated_at.isoformat(),
            "dueAt": self.due_at.isoformat() if self.due_at is not None else None,
            "evidence": [item.canonical_document() for item in self.evidence],
        }


@dataclass(frozen=True, slots=True)
class ObligationActivation:
    definition_id: str
    definition_version: str | None
    outcome: ObligationActivationOutcome
    instance_id: str | None
    reason_code: str
    evaluated_at: datetime
    condition_evaluation: ConditionEvaluation | None = None


@dataclass(frozen=True, slots=True)
class ObligationEvaluation:
    obligation_id: str
    definition_id: str
    definition_version: str
    result: ObligationFulfillmentResult
    state: ObligationLifecycleState
    findings: tuple[ConditionFinding, ...]
    evidence: tuple[ObligationEvidence, ...]
    proof: dict[str, Any]
    proof_hash: str
    evaluated_at: datetime

    def canonical_document(self) -> dict[str, Any]:
        return {
            "obligationId": self.obligation_id,
            "definition": {
                "id": self.definition_id,
                "version": self.definition_version,
            },
            "result": self.result.value,
            "state": self.state.value,
            "findings": [
                {
                    "code": finding.code,
                    "message": finding.message,
                    "clause": finding.clause,
                }
                for finding in self.findings
            ],
            "evidence": [item.canonical_document() for item in self.evidence],
            "proof": self.proof,
            "proofHash": self.proof_hash,
            "evaluatedAt": self.evaluated_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ConstraintViolation:
    id: str
    violation_key: str
    constraint_id: str
    constraint_version: str
    subject_ref: ObjectReference
    condition_evaluation: ConditionEvaluation
    severity: str
    state: ConstraintViolationState
    detected_at: datetime

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "violationKey": self.violation_key,
            "constraint": {
                "id": self.constraint_id,
                "version": self.constraint_version,
            },
            "subject": {
                "id": self.subject_ref.id,
                "revision": self.subject_ref.revision,
            },
            "conditionEvaluation": self.condition_evaluation.canonical_document(),
            "severity": self.severity,
            "state": self.state.value,
            "detectedAt": self.detected_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ConstraintEvaluation:
    constraint_id: str
    constraint_version: str | None
    subject_id: str
    subject_revision: int | None
    result: ConstraintEvaluationResult
    condition_evaluation: ConditionEvaluation | None
    violation_id: str | None
    findings: tuple[ConditionFinding, ...]
    proof: dict[str, Any]
    proof_hash: str
    evaluated_at: datetime

    def canonical_document(self) -> dict[str, Any]:
        return {
            "constraint": {
                "id": self.constraint_id,
                "version": self.constraint_version,
            },
            "subject": {
                "id": self.subject_id,
                "revision": self.subject_revision,
            },
            "result": self.result.value,
            "conditionEvaluation": (
                self.condition_evaluation.canonical_document()
                if self.condition_evaluation is not None
                else None
            ),
            "violationId": self.violation_id,
            "findings": [
                {
                    "code": finding.code,
                    "message": finding.message,
                    "clause": finding.clause,
                }
                for finding in self.findings
            ],
            "proof": self.proof,
            "proofHash": self.proof_hash,
            "evaluatedAt": self.evaluated_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class TaskOutputValue:
    output_id: str
    value: Any
    source: TaskOutputSource
    provenance: dict[str, Any]
    recorded_at: datetime

    def canonical_document(self) -> dict[str, Any]:
        return {
            "outputId": self.output_id,
            "value": self.value,
            "source": self.source.value,
            "provenance": self.provenance,
            "recordedAt": self.recorded_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class TaskInstance:
    id: str
    goal_ref: str
    assignee_ref: str
    subject_ref: ObjectReference
    mode: TaskMode
    state: TaskLifecycleState
    definition_id: str | None = None
    definition_version: str | None = None
    completion_condition_id: str | None = None
    allowed_actions: tuple[str, ...] = ()
    required_constraint_ids: tuple[str, ...] = ()
    dependencies: tuple[TaskDependency, ...] = ()
    outputs: tuple[TaskOutputDefinition, ...] = ()
    output_values: tuple[TaskOutputValue, ...] = ()
    budget: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goalRef": self.goal_ref,
            "assigneeRef": self.assignee_ref,
            "subject": {
                "id": self.subject_ref.id,
                "revision": self.subject_ref.revision,
            },
            "mode": self.mode.value,
            "state": self.state.value,
            "definition": {
                "id": self.definition_id,
                "version": self.definition_version,
            },
            "completionConditionId": self.completion_condition_id,
            "allowedActions": list(self.allowed_actions),
            "requiredConstraintIds": list(self.required_constraint_ids),
            "dependencies": [
                dependency.canonical_document() for dependency in self.dependencies
            ],
            "outputs": [output.canonical_document() for output in self.outputs],
            "outputValues": [value.canonical_document() for value in self.output_values],
            "budget": self.budget,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class TaskCompletionEvaluation:
    task_id: str
    result: TaskCompletionResult
    state: TaskLifecycleState
    condition_evaluation: ConditionEvaluation | None
    findings: tuple[ConditionFinding, ...]
    proof: dict[str, Any]
    proof_hash: str
    evaluated_at: datetime

    def canonical_document(self) -> dict[str, Any]:
        return {
            "taskId": self.task_id,
            "result": self.result.value,
            "state": self.state.value,
            "conditionEvaluation": (
                self.condition_evaluation.canonical_document()
                if self.condition_evaluation is not None
                else None
            ),
            "findings": [
                {
                    "code": finding.code,
                    "message": finding.message,
                    "clause": finding.clause,
                }
                for finding in self.findings
            ],
            "proof": self.proof,
            "proofHash": self.proof_hash,
            "evaluatedAt": self.evaluated_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class PlanInstance:
    id: str
    goal_ref: str
    planner_ref: str
    task_ids: tuple[str, ...]
    version: int
    state: PlanLifecycleState
    expected_outcome_ref: str | None = None
    previous_plan_id: str | None = None
    superseded_by: str | None = None
    revision_reason: str | None = None
    validation_result: PlanValidationResult = PlanValidationResult.UNKNOWN
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goalRef": self.goal_ref,
            "plannerRef": self.planner_ref,
            "taskIds": list(self.task_ids),
            "version": self.version,
            "state": self.state.value,
            "expectedOutcomeRef": self.expected_outcome_ref,
            "previousPlanId": self.previous_plan_id,
            "supersededBy": self.superseded_by,
            "revisionReason": self.revision_reason,
            "validation": {"result": self.validation_result.value},
            "createdAt": self.created_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class PlanValidation:
    plan_id: str
    result: PlanValidationResult
    findings: tuple[ConditionFinding, ...]
    proof: dict[str, Any]
    proof_hash: str
    evaluated_at: datetime


@dataclass(frozen=True, slots=True)
class ReservationInstance:
    id: str
    definition_id: str
    definition_version: str
    holder_ref: str
    resource_ref: str
    resource_type: str
    priority_id: str
    priority_rank: int
    preemption_mode: PreemptionMode
    state: ReservationLifecycleState
    quantity: int
    created_at: datetime
    expires_at: datetime | None = None
    preempted_by: str | None = None
    preemption_decision_id: str | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "definition": {
                "id": self.definition_id,
                "version": self.definition_version,
            },
            "holderRef": self.holder_ref,
            "resourceRef": self.resource_ref,
            "resourceType": self.resource_type,
            "priority": {
                "ref": self.priority_id,
                "rank": self.priority_rank,
            },
            "preemption": {"mode": self.preemption_mode.value},
            "state": self.state.value,
            "quantity": self.quantity,
            "createdAt": self.created_at.isoformat(),
            "expiresAt": (
                self.expires_at.isoformat() if self.expires_at is not None else None
            ),
            "preemptedBy": self.preempted_by,
            "preemptionDecisionId": self.preemption_decision_id,
        }


@dataclass(frozen=True, slots=True)
class PreemptionRequest:
    id: str
    preemption_definition_id: str
    requester_ref: str
    requested_resource_ref: str
    target_reservation_id: str
    replacement_holder_ref: str
    priority_id: str
    reason_code: str
    expected_target_state: ReservationLifecycleState = ReservationLifecycleState.ACTIVE

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "preemptionDefinitionId": self.preemption_definition_id,
            "requesterRef": self.requester_ref,
            "requestedResourceRef": self.requested_resource_ref,
            "targetReservationId": self.target_reservation_id,
            "replacementHolderRef": self.replacement_holder_ref,
            "priorityRef": self.priority_id,
            "reason": {"code": self.reason_code},
            "expectedTargetState": self.expected_target_state.value,
        }


@dataclass(frozen=True, slots=True)
class PreemptionDecision:
    id: str
    request_id: str
    definition_id: str | None
    definition_version: str | None
    effect: PreemptionEffect
    target_reservation_id: str
    replacement_reservation_id: str | None
    reason_code: str
    condition_evaluations: tuple[ConditionEvaluation, ...]
    proof: dict[str, Any]
    proof_hash: str
    decided_at: datetime

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "requestId": self.request_id,
            "definition": {
                "id": self.definition_id,
                "version": self.definition_version,
            },
            "effect": self.effect.value,
            "targetReservationId": self.target_reservation_id,
            "replacementReservationId": self.replacement_reservation_id,
            "reason": {"code": self.reason_code},
            "conditions": [
                evaluation.canonical_document()
                for evaluation in self.condition_evaluations
            ],
            "proof": self.proof,
            "proofHash": self.proof_hash,
            "decidedAt": self.decided_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class RiskInstance:
    id: str
    definition_id: str
    definition_version: str
    subject_ref: ObjectReference
    scenario_id: str | None
    accountable_ref: str
    state: RiskLifecycleState
    created_at: datetime

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "definition": {
                "id": self.definition_id,
                "version": self.definition_version,
            },
            "subject": {
                "id": self.subject_ref.id,
                "revision": self.subject_ref.revision,
            },
            "scenarioRef": self.scenario_id,
            "accountableRef": self.accountable_ref,
            "state": self.state.value,
            "createdAt": self.created_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ControlImplementation:
    id: str
    definition_id: str
    definition_version: str
    subject_ref: ObjectReference
    state: ControlState
    effectiveness: ControlEffectivenessResult
    evidence_refs: tuple[ObjectReference, ...]
    created_at: datetime
    result: ControlResult | None = None
    effectiveness_assessment_ref: str | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "definition": {
                "id": self.definition_id,
                "version": self.definition_version,
            },
            "subject": {
                "id": self.subject_ref.id,
                "revision": self.subject_ref.revision,
            },
            "state": self.state.value,
            "effectiveness": self.effectiveness.value,
            "effectivenessAssessmentRef": self.effectiveness_assessment_ref,
            "result": self.result.canonical_document() if self.result else None,
            "evidenceRefs": [
                {"id": reference.id, "revision": reference.revision}
                for reference in self.evidence_refs
            ],
            "createdAt": self.created_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    id: str
    risk_id: str
    as_of: datetime
    likelihood_type: LikelihoodType
    likelihood_level: RiskLevel
    impact: dict[str, RiskLevel]
    result_level: RiskLevel
    confidence: RiskLevel
    evidence_refs: tuple[ObjectReference, ...]
    control_refs: tuple[str, ...]
    proof: dict[str, Any]
    proof_hash: str
    assessed_at: datetime

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "riskRef": self.risk_id,
            "asOf": self.as_of.isoformat(),
            "likelihood": {
                "type": self.likelihood_type.value,
                "level": self.likelihood_level.value,
            },
            "impact": {
                dimension: level.value for dimension, level in sorted(self.impact.items())
            },
            "result": {"level": self.result_level.value},
            "confidence": {"level": self.confidence.value},
            "evidenceRefs": [
                {"id": reference.id, "revision": reference.revision}
                for reference in self.evidence_refs
            ],
            "controlRefs": list(self.control_refs),
            "proof": self.proof,
            "proofHash": self.proof_hash,
            "assessedAt": self.assessed_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class RiskTreatmentPlan:
    id: str
    risk_id: str
    strategy: RiskTreatmentStrategy
    action_refs: tuple[str, ...]
    target_level: RiskLevel
    status: RiskTreatmentStatus
    created_at: datetime
    deadline_at: datetime | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "riskRef": self.risk_id,
            "strategy": self.strategy.value,
            "actionRefs": list(self.action_refs),
            "targetRisk": {"level": self.target_level.value},
            "status": self.status.value,
            "deadlineAt": (
                self.deadline_at.isoformat() if self.deadline_at is not None else None
            ),
            "createdAt": self.created_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class RiskAcceptance:
    id: str
    risk_id: str
    assessment_id: str
    accepted_by_ref: str
    status: RiskAcceptanceStatus
    rationale_code: str
    accepted_at: datetime
    valid_until: datetime | None
    proof: dict[str, Any]
    proof_hash: str

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "riskRef": self.risk_id,
            "assessmentRef": self.assessment_id,
            "acceptedByRef": self.accepted_by_ref,
            "status": self.status.value,
            "rationale": {"code": self.rationale_code},
            "acceptedAt": self.accepted_at.isoformat(),
            "validUntil": (
                self.valid_until.isoformat() if self.valid_until is not None else None
            ),
            "proof": self.proof,
            "proofHash": self.proof_hash,
        }


@dataclass(frozen=True, slots=True)
class RemediationTrigger:
    trigger_type: RemediationTriggerType
    ref: str

    def canonical_document(self) -> dict[str, Any]:
        return {"type": self.trigger_type.value, "ref": self.ref}


@dataclass(frozen=True, slots=True)
class RemediationDeadlines:
    containment_by: datetime | None = None
    remediation_by: datetime | None = None
    verification_by: datetime | None = None
    closure_by: datetime | None = None

    def canonical_document(self) -> dict[str, Any]:
        return {
            "containmentBy": self.containment_by.isoformat() if self.containment_by else None,
            "remediationBy": self.remediation_by.isoformat() if self.remediation_by else None,
            "verificationBy": self.verification_by.isoformat() if self.verification_by else None,
            "closureBy": self.closure_by.isoformat() if self.closure_by else None,
        }


@dataclass(frozen=True, slots=True)
class RemediationDefinition:
    id: str
    name: str
    trigger_types: tuple[RemediationTriggerType, ...]
    version: str = "1.0.0"
    containment_required: bool = False
    root_cause_required: bool = False
    corrective_action_required: bool = True
    independent_verification_required: bool = False
    action_evidence_required: tuple[str, ...] = ()
    effectiveness_evidence_required: tuple[str, ...] = ()

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "triggers": [trigger.value for trigger in self.trigger_types],
            "requirements": {
                "containmentRequired": self.containment_required,
                "rootCauseRequired": self.root_cause_required,
                "correctiveActionRequired": self.corrective_action_required,
                "independentVerificationRequired": self.independent_verification_required,
            },
            "evidenceRequirements": {
                "actionEvidence": list(self.action_evidence_required),
                "effectivenessEvidence": list(self.effectiveness_evidence_required),
            },
        }


@dataclass(frozen=True, slots=True)
class RemediationCase:
    id: str
    definition_id: str
    definition_version: str
    trigger: RemediationTrigger
    subject_ref: ObjectReference
    objective: str
    owner_ref: str
    severity: RemediationSeverity
    priority: RemediationPriority
    status: RemediationStatus
    opened_at: datetime
    deadlines: RemediationDeadlines = field(default_factory=RemediationDeadlines)

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "definition": {
                "id": self.definition_id,
                "version": self.definition_version,
            },
            "trigger": self.trigger.canonical_document(),
            "subject": {
                "id": self.subject_ref.id,
                "revision": self.subject_ref.revision,
            },
            "objective": self.objective,
            "ownerRef": self.owner_ref,
            "classification": {
                "severity": self.severity.value,
                "priority": self.priority.value,
            },
            "status": self.status.value,
            "openedAt": self.opened_at.isoformat(),
            "deadlines": self.deadlines.canonical_document(),
        }


@dataclass(frozen=True, slots=True)
class RemediationVerification:
    id: str
    case_ref: str
    result: RemediationVerificationResult
    verifier_ref: str
    evidence_refs: tuple[ObjectReference, ...]
    verified_at: datetime
    independent: bool = False

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "caseRef": self.case_ref,
            "result": self.result.value,
            "verifierRef": self.verifier_ref,
            "independent": self.independent,
            "evidenceRefs": [
                {"id": reference.id, "revision": reference.revision}
                for reference in self.evidence_refs
            ],
            "verifiedAt": self.verified_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class RemediationEffectivenessAssessment:
    id: str
    case_ref: str
    result: RemediationEffectivenessResult
    verification_ref: str
    evidence_refs: tuple[ObjectReference, ...]
    assessed_at: datetime
    assessor_ref: str

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "caseRef": self.case_ref,
            "result": self.result.value,
            "verificationRef": self.verification_ref,
            "evidenceRefs": [
                {"id": reference.id, "revision": reference.revision}
                for reference in self.evidence_refs
            ],
            "assessedAt": self.assessed_at.isoformat(),
            "assessorRef": self.assessor_ref,
        }


@dataclass(frozen=True, slots=True)
class RemediationAcceptance:
    id: str
    case_ref: str
    result: RemediationAcceptanceResult
    effectiveness_ref: str
    accepted_by_ref: str
    accepted_at: datetime

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "caseRef": self.case_ref,
            "result": self.result.value,
            "effectivenessRef": self.effectiveness_ref,
            "acceptedByRef": self.accepted_by_ref,
            "acceptedAt": self.accepted_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class RemediationClosure:
    id: str
    case_ref: str
    verification_ref: str
    effectiveness_ref: str
    acceptance_ref: str
    evidence_refs: tuple[ObjectReference, ...]
    closed_by_ref: str
    closed_at: datetime

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "caseRef": self.case_ref,
            "verificationRef": self.verification_ref,
            "effectivenessRef": self.effectiveness_ref,
            "acceptanceRef": self.acceptance_ref,
            "evidenceRefs": [
                {"id": reference.id, "revision": reference.revision}
                for reference in self.evidence_refs
            ],
            "closedByRef": self.closed_by_ref,
            "closedAt": self.closed_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class StateTransitionFinding:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class StateTransitionDecision:
    permitted: bool
    state_machine_id: str | None
    transition: str
    current_state: str
    target_state: str | None
    reasons: tuple[StateTransitionFinding, ...]


@dataclass(frozen=True, slots=True)
class StateTransitionEvent:
    id: str
    sequence: int
    event_type: str
    object_id: str
    object_kind: str
    previous_revision: int
    new_revision: int
    state_machine_id: str
    state_machine_version: str
    transition: str
    from_state: str
    to_state: str
    actor: ActorReference
    action_id: str | None
    occurred_at: datetime

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sequence": self.sequence,
            "eventType": self.event_type,
            "object": {
                "id": self.object_id,
                "kind": self.object_kind,
                "previousRevision": self.previous_revision,
                "newRevision": self.new_revision,
            },
            "stateMachine": {
                "id": self.state_machine_id,
                "version": self.state_machine_version,
            },
            "transition": self.transition,
            "fromState": self.from_state,
            "toState": self.to_state,
            "actor": self.actor.id,
            "actionId": self.action_id,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class StateTransitionAuditRecord:
    id: str
    event_id: str
    object_id: str
    state_machine_id: str
    state_machine_version: str
    transition: str
    action_id: str | None
    actor: ActorReference
    previous_state: str
    new_state: str
    previous_revision: int
    new_revision: int
    decision: StateTransitionDecision
    recorded_at: datetime

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "eventId": self.event_id,
            "objectId": self.object_id,
            "stateMachine": {
                "id": self.state_machine_id,
                "version": self.state_machine_version,
            },
            "transition": self.transition,
            "actionId": self.action_id,
            "actor": self.actor.id,
            "previousState": self.previous_state,
            "newState": self.new_state,
            "previousRevision": self.previous_revision,
            "newRevision": self.new_revision,
            "decision": {
                "permitted": self.decision.permitted,
                "currentState": self.decision.current_state,
                "targetState": self.decision.target_state,
                "reasons": [
                    {"code": reason.code, "message": reason.message}
                    for reason in self.decision.reasons
                ],
            },
            "recordedAt": self.recorded_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class RelationshipAuditRecord:
    id: str
    sequence: int
    relationship_id: str
    relationship_type_id: str
    relationship_type_version: str
    action: str
    source_id: str
    target_id: str
    source_revision: int
    target_revision: int
    new_source_revision: int
    actor: ActorReference
    evidence_types: tuple[str, ...]
    recorded_at: datetime

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sequence": self.sequence,
            "relationshipId": self.relationship_id,
            "relationshipType": {
                "id": self.relationship_type_id,
                "version": self.relationship_type_version,
            },
            "action": self.action,
            "source": {
                "id": self.source_id,
                "previousRevision": self.source_revision,
                "newRevision": self.new_source_revision,
            },
            "target": {
                "id": self.target_id,
                "revision": self.target_revision,
            },
            "actor": self.actor.id,
            "evidenceTypes": list(self.evidence_types),
            "recordedAt": self.recorded_at.isoformat(),
        }


class InMemoryUPDLRegistry:
    def __init__(self) -> None:
        self._types: dict[str, TypeDefinition] = {}
        self._objects: dict[str, list[ObjectEnvelope]] = {}
        self._policies: dict[str, PolicyDefinition] = {}
        self._namespaces: dict[str, NamespaceDefinition] = {}
        self._relationship_types: dict[str, RelationshipTypeDefinition] = {}
        self._conditions: dict[str, SemanticConditionDefinition] = {}
        self._condition_failure_policies: dict[str, ConditionFailurePolicy] = {}
        self._condition_dependencies: dict[str, ConditionDependency] = {}
        self._condition_failures: dict[str, ConditionFailure] = {}
        self._active_condition_failure_keys: dict[str, str] = {}
        self._condition_failure_impacts: dict[str, ConditionFailureImpact] = {}
        self._constraints: dict[str, ConstraintDefinition] = {}
        self._constraint_violations: dict[str, ConstraintViolation] = {}
        self._constraint_violation_keys: dict[str, str] = {}
        self._task_definitions: dict[str, TaskDefinition] = {}
        self._tasks: dict[str, TaskInstance] = {}
        self._plans: dict[str, PlanInstance] = {}
        self._priorities: dict[str, PriorityDefinition] = {}
        self._reservation_definitions: dict[str, ReservationDefinition] = {}
        self._reservations: dict[str, ReservationInstance] = {}
        self._preemption_definitions: dict[str, PreemptionDefinition] = {}
        self._preemption_decisions: dict[str, PreemptionDecision] = {}
        self._risk_definitions: dict[str, RiskDefinition] = {}
        self._risk_scenarios: dict[str, RiskScenario] = {}
        self._risks: dict[str, RiskInstance] = {}
        self._control_definitions: dict[str, ControlDefinition] = {}
        self._control_implementations: dict[str, ControlImplementation] = {}
        self._risk_assessments: dict[str, RiskAssessment] = {}
        self._risk_treatment_plans: dict[str, RiskTreatmentPlan] = {}
        self._risk_acceptances: dict[str, RiskAcceptance] = {}
        self._remediation_definitions: dict[str, RemediationDefinition] = {}
        self._remediation_cases: dict[str, RemediationCase] = {}
        self._remediation_verifications: dict[str, RemediationVerification] = {}
        self._remediation_effectiveness: dict[str, RemediationEffectivenessAssessment] = {}
        self._remediation_acceptances: dict[str, RemediationAcceptance] = {}
        self._remediation_closures: dict[str, RemediationClosure] = {}
        self._decisions: dict[str, DecisionDefinition] = {}
        self._obligation_definitions: dict[str, ObligationDefinition] = {}
        self._obligation_instances: dict[str, ObligationInstance] = {}
        self._obligation_activation_keys: dict[str, str] = {}
        self._state_machines: dict[str, StateMachineDefinition] = {}
        self._transition_events: list[StateTransitionEvent] = []
        self._transition_audit_records: list[StateTransitionAuditRecord] = []
        self._relationship_audit_records: list[RelationshipAuditRecord] = []
        self._event_sequence = 0
        self._relationship_audit_sequence = 0
        self._obligation_sequence = 0
        self._constraint_violation_sequence = 0
        self._task_sequence = 0
        self._plan_sequence = 0
        self._reservation_sequence = 0
        self._preemption_decision_sequence = 0
        self._risk_sequence = 0
        self._control_implementation_sequence = 0
        self._risk_assessment_sequence = 0
        self._risk_treatment_sequence = 0
        self._risk_acceptance_sequence = 0
        self._condition_failure_sequence = 0
        self._condition_failure_impact_sequence = 0
        self._remediation_case_sequence = 0
        self._remediation_verification_sequence = 0
        self._remediation_effectiveness_sequence = 0
        self._remediation_acceptance_sequence = 0
        self._remediation_closure_sequence = 0

    def register_type(self, definition: TypeDefinition) -> None:
        if not definition.kind_name:
            raise RegistryError("TYPE_INVALID", "type kindName is required")
        self._types[definition.kind_name] = definition

    def register_namespace(self, definition: NamespaceDefinition) -> None:
        require_namespace(definition.id)
        if definition.id.split(".", 1)[0] in RESERVED_NAMESPACE_ROOTS:
            raise RegistryError("NAMESPACE_RESERVED", f"reserved namespace: {definition.id}")
        if definition.parent is not None:
            require_namespace(definition.parent)
            if definition.parent not in self._namespaces:
                raise RegistryError("NAMESPACE_PARENT_NOT_FOUND", definition.parent)
            parent: str | None = definition.parent
            while parent is not None:
                if parent == definition.id:
                    raise RegistryError("NAMESPACE_CYCLE", definition.id)
                parent = self._namespaces[parent].parent
        self._namespaces[definition.id] = definition

    def register_relationship_type(self, definition: RelationshipTypeDefinition) -> None:
        require_identifier(definition.id)
        if not definition.name:
            raise RegistryError("RELATIONSHIP_NAME_REQUIRED", definition.id)
        if not definition.source_kinds:
            raise RegistryError("RELATIONSHIP_SOURCE_KIND_REQUIRED", definition.id)
        if not definition.target_kinds:
            raise RegistryError("RELATIONSHIP_TARGET_KIND_REQUIRED", definition.id)
        if definition.symmetric and set(definition.source_kinds) != set(definition.target_kinds):
            raise RegistryError(
                "RELATIONSHIP_SYMMETRIC_KIND_MISMATCH",
                definition.id,
            )
        for kind in (*definition.source_kinds, *definition.target_kinds):
            if kind not in self._types:
                raise RegistryError("RELATIONSHIP_KIND_UNKNOWN", kind)
        self._relationship_types[definition.id] = definition

    def register_state_machine(self, definition: StateMachineDefinition) -> None:
        require_identifier(definition.id)
        if definition.applies_to_kind not in self._types:
            raise RegistryError("STATE_MACHINE_KIND_UNKNOWN", definition.applies_to_kind)
        states = tuple(state.name for state in definition.states)
        if not states:
            raise RegistryError("STATE_MACHINE_NO_STATES", definition.id)
        if len(set(states)) != len(states):
            raise RegistryError("STATE_MACHINE_DUPLICATE_STATE", definition.id)
        if definition.initial_state not in states:
            raise RegistryError("INITIAL_STATE_INVALID", definition.initial_state)
        state_set = set(states)
        for transition in definition.transitions:
            if not transition.source_states:
                raise RegistryError("TRANSITION_SOURCE_REQUIRED", transition.name)
            unknown_sources = sorted(set(transition.source_states) - state_set)
            if unknown_sources:
                raise RegistryError(
                    "SOURCE_STATE_INVALID",
                    f"{transition.name}: {unknown_sources}",
                )
            if transition.target_state not in state_set:
                raise RegistryError("TARGET_STATE_INVALID", transition.target_state)
            if (
                transition.classification is TransitionClassification.NORMAL
                and definition.terminal_states.intersection(transition.source_states)
            ):
                raise RegistryError("TERMINAL_STATE_REACHED", transition.name)
        self._state_machines[definition.id] = definition

    def register_policy(self, definition: PolicyDefinition) -> None:
        require_identifier(definition.id)
        self._policies[definition.id] = definition

    def register_condition(self, definition: SemanticConditionDefinition) -> None:
        require_identifier(definition.id)
        if not definition.name:
            raise RegistryError("CONDITION_NAME_REQUIRED", definition.id)
        if not definition.subject_kinds:
            raise RegistryError("CONDITION_SUBJECT_KIND_REQUIRED", definition.id)
        if not definition.clauses:
            raise RegistryError("CONDITION_CLAUSE_REQUIRED", definition.id)
        for kind in definition.subject_kinds:
            if kind not in self._types:
                raise RegistryError("CONDITION_SUBJECT_KIND_UNKNOWN", kind)
        for clause in definition.clauses:
            self._require_valid_condition_clause(definition, clause)
        self._conditions[definition.id] = definition

    def register_condition_failure_policy(
        self,
        policy: ConditionFailurePolicy,
    ) -> None:
        require_identifier(policy.id)
        if not policy.condition_ids:
            raise RegistryError("CONDITION_FAILURE_POLICY_CONDITION_REQUIRED", policy.id)
        for condition_id in policy.condition_ids:
            if condition_id not in self._conditions:
                raise RegistryError("CONDITION_FAILURE_POLICY_CONDITION_UNKNOWN", condition_id)
        if not policy.transitions_from or not policy.transitions_to:
            raise RegistryError("CONDITION_FAILURE_TRANSITION_INVALID", policy.id)
        if not policy.effects:
            raise RegistryError("CONDITION_FAILURE_EFFECT_UNKNOWN", policy.id)
        if not policy.scope.type:
            raise RegistryError("CONDITION_FAILURE_SCOPE_REQUIRED", policy.id)
        if (
            ConditionFailureEffect.DECISION_INVALIDATED in policy.effects
            and policy.scope.type not in {"DECISION", "AUTHORIZATION", "SUBJECT"}
        ):
            raise RegistryError("CONDITION_FAILURE_SCOPE_REQUIRED", policy.id)
        if policy.ai_may_resolve or policy.ai_may_create_exception:
            raise RegistryError("CONDITION_FAILURE_AI_AUTHORITY_INVALID", policy.id)
        self._condition_failure_policies[policy.id] = policy

    def register_condition_dependency(self, dependency: ConditionDependency) -> None:
        require_identifier(dependency.id)
        if dependency.dependent_condition_id not in self._conditions:
            raise RegistryError(
                "CONDITION_DEPENDENCY_CONDITION_UNKNOWN",
                dependency.dependent_condition_id,
            )
        if dependency.dependency_condition_id not in self._conditions:
            raise RegistryError(
                "CONDITION_DEPENDENCY_CONDITION_UNKNOWN",
                dependency.dependency_condition_id,
            )
        if dependency.dependent_condition_id == dependency.dependency_condition_id:
            raise RegistryError("CONDITION_FAILURE_CIRCULAR_DEPENDENCY", dependency.id)
        if self._condition_dependency_creates_cycle(dependency):
            raise RegistryError("CONDITION_FAILURE_CIRCULAR_DEPENDENCY", dependency.id)
        self._condition_dependencies[dependency.id] = dependency

    def register_constraint(self, definition: ConstraintDefinition) -> None:
        require_identifier(definition.id)
        if not definition.name:
            raise RegistryError("CONSTRAINT_NAME_REQUIRED", definition.id)
        if definition.status not in {"ACTIVE", "DRAFT", "DEPRECATED", "RETIRED"}:
            raise RegistryError("CONSTRAINT_STATUS_INVALID", definition.status)
        if not definition.subject_kinds:
            raise RegistryError("CONSTRAINT_SUBJECT_KIND_REQUIRED", definition.id)
        self._require_registered_condition(
            definition.condition_id,
            "CONSTRAINT_CONDITION_UNKNOWN",
        )
        for kind in definition.subject_kinds:
            if kind not in self._types:
                raise RegistryError("CONSTRAINT_SUBJECT_KIND_UNKNOWN", kind)
        condition = self._conditions[definition.condition_id]
        if not set(definition.subject_kinds).issubset(condition.subject_kinds):
            raise RegistryError("CONSTRAINT_CONDITION_SUBJECT_KIND_MISMATCH", definition.id)
        self._constraints[definition.id] = definition

    def register_task_definition(self, definition: TaskDefinition) -> None:
        require_identifier(definition.id)
        if not definition.name:
            raise RegistryError("TASK_DEFINITION_NAME_REQUIRED", definition.id)
        if definition.status not in {"ACTIVE", "DRAFT", "DEPRECATED", "RETIRED"}:
            raise RegistryError("TASK_DEFINITION_STATUS_INVALID", definition.status)
        if definition.completion_condition_id is not None:
            self._require_registered_condition(
                definition.completion_condition_id,
                "TASK_COMPLETION_CONDITION_UNKNOWN",
            )
        for constraint_id in definition.required_constraint_ids:
            if constraint_id not in self._constraints:
                raise RegistryError("TASK_CONSTRAINT_UNKNOWN", constraint_id)
        self._require_unique_task_outputs(definition.outputs)
        self._task_definitions[definition.id] = definition

    def register_decision(self, definition: DecisionDefinition) -> None:
        require_identifier(definition.id)
        if not definition.name:
            raise RegistryError("DECISION_NAME_REQUIRED", definition.id)
        if not definition.action:
            raise RegistryError("DECISION_ACTION_REQUIRED", definition.id)
        if definition.question is not None and not definition.question.statement:
            raise RegistryError("DECISION_QUESTION_REQUIRED", definition.id)
        if any(not alternative for alternative in definition.alternatives):
            raise RegistryError("DECISION_ALTERNATIVE_INVALID", definition.id)
        definition_outcomes: tuple[str, ...]
        if not definition.outcome_set:
            definition_outcomes = ()
        else:
            definition_outcomes = tuple(outcome.value for outcome in definition.outcome_set)
        if len(set(definition_outcomes)) != len(definition_outcomes):
            raise RegistryError("DECISION_OUTCOME_DUPLICATE", definition.id)
        if definition.authority_requirement is not None:
            if definition.authority_requirement.operator not in {"ALL_OF", "ANY_OF", "AT_LEAST"}:
                raise RegistryError("DECISION_AUTHORITY_OPERATOR_INVALID", definition.id)
            if not definition.authority_requirement.authority_refs:
                raise RegistryError("DECISION_AUTHORITY_REQUIRED", definition.id)
        if (
            definition.evidence_requirement is not None
            and not definition.evidence_requirement.required_types
        ):
            raise RegistryError("DECISION_EVIDENCE_REQUIREMENT_EMPTY", definition.id)
        if (
            definition.validity_seconds is not None
            and definition.validity_seconds <= 0
        ):
            raise RegistryError("DECISION_VALIDITY_INVALID", definition.id)
        for kind in definition.resource_kinds:
            if kind not in self._types:
                raise RegistryError("DECISION_RESOURCE_KIND_UNKNOWN", kind)
        for condition_id in definition.condition_ids:
            if condition_id not in self._conditions:
                raise RegistryError("DECISION_CONDITION_UNKNOWN", condition_id)
        for policy_id in definition.policy_ids:
            if policy_id not in self._policies:
                raise RegistryError("DECISION_POLICY_UNKNOWN", policy_id)
        self._decisions[definition.id] = definition

    def get_decision_definition(self, decision_id: str) -> DecisionDefinition:
        definition = self._decisions.get(decision_id)
        if definition is None:
            raise RegistryError("DECISION_NOT_FOUND", decision_id)
        return definition

    def register_obligation(self, definition: ObligationDefinition) -> None:
        require_identifier(definition.id)
        if not definition.name:
            raise RegistryError("OBLIGATION_NAME_REQUIRED", definition.id)
        if definition.status not in {"ACTIVE", "DRAFT", "DEPRECATED", "RETIRED"}:
            raise RegistryError("OBLIGATION_STATUS_INVALID", definition.status)
        if definition.trigger.source is ObligationTriggerSource.POLICY_DECISION:
            if definition.trigger.decision_effect is None:
                raise RegistryError("OBLIGATION_TRIGGER_EFFECT_REQUIRED", definition.id)
            if (
                definition.trigger.policy_id is not None
                and definition.trigger.policy_id not in self._policies
            ):
                raise RegistryError(
                    "OBLIGATION_TRIGGER_POLICY_UNKNOWN",
                    definition.trigger.policy_id,
                )
        if definition.applicability_condition_id is not None:
            self._require_registered_condition(
                definition.applicability_condition_id,
                "OBLIGATION_APPLICABILITY_CONDITION_UNKNOWN",
            )
        if not definition.duty.action_ref and not definition.duty.condition_id:
            raise RegistryError("OBLIGATION_DUTY_REQUIRED", definition.id)
        if definition.duty.condition_id is not None:
            self._require_registered_condition(
                definition.duty.condition_id,
                "OBLIGATION_DUTY_CONDITION_UNKNOWN",
            )
        if definition.fulfillment_condition_id is not None:
            self._require_registered_condition(
                definition.fulfillment_condition_id,
                "OBLIGATION_FULFILLMENT_CONDITION_UNKNOWN",
            )
        if definition.breach is not None and definition.breach.condition_id is not None:
            self._require_registered_condition(
                definition.breach.condition_id,
                "OBLIGATION_BREACH_CONDITION_UNKNOWN",
            )
        if (
            definition.waiver.policy_id is not None
            and definition.waiver.policy_id not in self._policies
        ):
            raise RegistryError("OBLIGATION_WAIVER_POLICY_UNKNOWN", definition.waiver.policy_id)
        if definition.timing.completion_within is not None:
            _parse_duration(definition.timing.completion_within)
        if not definition.responsibility.assignee_ref:
            raise RegistryError("OBLIGATION_ASSIGNMENT_INVALID", definition.id)
        self._obligation_definitions[definition.id] = definition

    def register_priority(self, definition: PriorityDefinition) -> None:
        require_identifier(definition.id)
        if not definition.name:
            raise RegistryError("PRIORITY_NAME_REQUIRED", definition.id)
        if definition.status not in {"ACTIVE", "DRAFT", "DEPRECATED", "RETIRED"}:
            raise RegistryError("PRIORITY_STATUS_INVALID", definition.status)
        if definition.rank < 0:
            raise RegistryError("PRIORITY_RANK_INVALID", definition.id)
        self._priorities[definition.id] = definition

    def register_reservation_definition(
        self,
        definition: ReservationDefinition,
    ) -> None:
        require_identifier(definition.id)
        if not definition.name:
            raise RegistryError("RESERVATION_DEFINITION_NAME_REQUIRED", definition.id)
        if definition.status not in {"ACTIVE", "DRAFT", "DEPRECATED", "RETIRED"}:
            raise RegistryError("RESERVATION_DEFINITION_STATUS_INVALID", definition.status)
        if not definition.resource_type:
            raise RegistryError("RESERVATION_RESOURCE_TYPE_REQUIRED", definition.id)
        if not definition.quantity_type:
            raise RegistryError("RESERVATION_QUANTITY_TYPE_REQUIRED", definition.id)
        self._reservation_definitions[definition.id] = definition

    def register_preemption(self, definition: PreemptionDefinition) -> None:
        require_identifier(definition.id)
        if not definition.name:
            raise RegistryError("PREEMPTION_NAME_REQUIRED", definition.id)
        if definition.status not in {"ACTIVE", "DRAFT", "DEPRECATED", "RETIRED"}:
            raise RegistryError("PREEMPTION_STATUS_INVALID", definition.status)
        if not definition.resource_types:
            raise RegistryError("PREEMPTION_RESOURCE_TYPE_REQUIRED", definition.id)
        if definition.minimum_priority_id not in self._priorities:
            raise RegistryError(
                "PREEMPTION_MINIMUM_PRIORITY_UNKNOWN",
                definition.minimum_priority_id,
            )
        if not definition.target_modes:
            raise RegistryError("PREEMPTION_TARGET_MODE_REQUIRED", definition.id)
        if PreemptionMode.NON_PREEMPTIBLE in definition.target_modes:
            raise RegistryError("PREEMPTION_TARGET_MODE_INVALID", definition.id)
        for condition_id in definition.condition_ids:
            self._require_registered_condition(
                condition_id,
                "PREEMPTION_CONDITION_UNKNOWN",
            )
        if definition.policy_id is not None and definition.policy_id not in self._policies:
            raise RegistryError("PREEMPTION_POLICY_UNKNOWN", definition.policy_id)
        if definition.minimum_priority_delta < 0:
            raise RegistryError("PREEMPTION_PRIORITY_DELTA_INVALID", definition.id)
        self._preemption_definitions[definition.id] = definition

    def create_reservation(
        self,
        *,
        definition_id: str,
        holder_ref: str,
        resource_ref: str,
        priority_id: str,
        quantity: int = 1,
        expires_at: datetime | None = None,
        preemption_mode: PreemptionMode | None = None,
    ) -> ReservationInstance:
        definition = self._reservation_definitions.get(definition_id)
        if definition is None:
            raise RegistryError("RESERVATION_DEFINITION_NOT_FOUND", definition_id)
        if definition.status != "ACTIVE":
            raise RegistryError("RESERVATION_DEFINITION_INACTIVE", definition_id)
        priority = self._priorities.get(priority_id)
        if priority is None:
            raise RegistryError("RESERVATION_PRIORITY_NOT_FOUND", priority_id)
        if priority.status != "ACTIVE":
            raise RegistryError("RESERVATION_PRIORITY_INACTIVE", priority_id)
        if not holder_ref:
            raise RegistryError("RESERVATION_HOLDER_REQUIRED", definition_id)
        if not resource_ref:
            raise RegistryError("RESERVATION_RESOURCE_REQUIRED", definition_id)
        if quantity <= 0:
            raise RegistryError("RESERVATION_QUANTITY_INVALID", definition_id)
        if definition.expiration_required and expires_at is None:
            raise RegistryError("RESERVATION_EXPIRATION_REQUIRED", definition_id)
        self._reservation_sequence += 1
        reservation = ReservationInstance(
            id=f"RSV-{self._reservation_sequence:06d}",
            definition_id=definition.id,
            definition_version=definition.version,
            holder_ref=holder_ref,
            resource_ref=resource_ref,
            resource_type=definition.resource_type,
            priority_id=priority.id,
            priority_rank=priority.rank,
            preemption_mode=preemption_mode or definition.preemption_mode,
            state=ReservationLifecycleState.ACTIVE,
            quantity=quantity,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
        )
        self._reservations[reservation.id] = reservation
        return reservation

    def get_reservation(self, reservation_id: str) -> ReservationInstance:
        reservation = self._reservations.get(reservation_id)
        if reservation is None:
            raise RegistryError("RESERVATION_NOT_FOUND", reservation_id)
        return reservation

    def get_preemption_decision(self, decision_id: str) -> PreemptionDecision:
        decision = self._preemption_decisions.get(decision_id)
        if decision is None:
            raise RegistryError("PREEMPTION_DECISION_NOT_FOUND", decision_id)
        return decision

    def evaluate_preemption(self, request: PreemptionRequest) -> PreemptionDecision:
        require_identifier(request.id)
        decided_at = datetime.now(UTC)
        definition = self._preemption_definitions.get(request.preemption_definition_id)
        if definition is None:
            return self._preemption_decision(
                request=request,
                definition=None,
                effect=PreemptionEffect.INDETERMINATE,
                reason_code="PREEMPTION_DEFINITION_NOT_FOUND",
                condition_evaluations=(),
                replacement=None,
                decided_at=decided_at,
            )
        if definition.status != "ACTIVE":
            return self._preemption_decision(
                request=request,
                definition=definition,
                effect=PreemptionEffect.DENY,
                reason_code="PREEMPTION_DEFINITION_INACTIVE",
                condition_evaluations=(),
                replacement=None,
                decided_at=decided_at,
            )
        target = self._reservations.get(request.target_reservation_id)
        if target is None:
            return self._preemption_decision(
                request=request,
                definition=definition,
                effect=PreemptionEffect.DENY,
                reason_code="PREEMPTION_TARGET_NOT_FOUND",
                condition_evaluations=(),
                replacement=None,
                decided_at=decided_at,
            )
        structural_reason = self._preemption_structural_denial(
            request=request,
            definition=definition,
            target=target,
        )
        condition_evaluations = self._evaluate_preemption_conditions(
            definition=definition,
            target=target,
        )
        condition_reason = self._preemption_condition_denial(condition_evaluations)
        reason_code = structural_reason or condition_reason
        if reason_code is not None:
            effect = (
                PreemptionEffect.INDETERMINATE
                if reason_code == "PREEMPTION_CONDITION_UNKNOWN"
                else PreemptionEffect.DENY
            )
            return self._preemption_decision(
                request=request,
                definition=definition,
                effect=effect,
                reason_code=reason_code,
                condition_evaluations=condition_evaluations,
                replacement=None,
                decided_at=decided_at,
                target=target,
            )

        replacement = self._create_replacement_reservation(
            request=request,
            target=target,
        )
        decision = self._preemption_decision(
            request=request,
            definition=definition,
            effect=PreemptionEffect.PERMIT,
            reason_code="PREEMPTION_PERMITTED",
            condition_evaluations=condition_evaluations,
            replacement=replacement,
            decided_at=decided_at,
            target=target,
        )
        self._reservations[target.id] = replace(
            target,
            state=ReservationLifecycleState.PREEMPTED,
            preempted_by=replacement.id,
            preemption_decision_id=decision.id,
        )
        return decision

    def register_risk_definition(self, definition: RiskDefinition) -> None:
        require_identifier(definition.id)
        if not definition.name:
            raise RegistryError("RISK_DEFINITION_NAME_REQUIRED", definition.id)
        if definition.status not in {"ACTIVE", "DRAFT", "DEPRECATED", "RETIRED"}:
            raise RegistryError("RISK_DEFINITION_STATUS_INVALID", definition.status)
        if not definition.subject_kinds:
            raise RegistryError("RISK_SUBJECT_KIND_REQUIRED", definition.id)
        for kind in definition.subject_kinds:
            if kind not in self._types:
                raise RegistryError("RISK_SUBJECT_KIND_UNKNOWN", kind)
        if (
            definition.acceptance_policy_id is not None
            and definition.acceptance_policy_id not in self._policies
        ):
            raise RegistryError("RISK_ACCEPTANCE_POLICY_UNKNOWN", definition.id)
        self._risk_definitions[definition.id] = definition

    def register_risk_scenario(self, scenario: RiskScenario) -> None:
        require_identifier(scenario.id)
        if not scenario.name:
            raise RegistryError("RISK_SCENARIO_NAME_REQUIRED", scenario.id)
        if scenario.status not in {"ACTIVE", "DRAFT", "DEPRECATED", "RETIRED"}:
            raise RegistryError("RISK_SCENARIO_STATUS_INVALID", scenario.status)
        if not scenario.adverse_outcome_ref:
            raise RegistryError("RISK_SCENARIO_OUTCOME_REQUIRED", scenario.id)
        resolved = self.resolve_reference(scenario.subject_ref)
        if resolved.status is not ResolutionStatus.RESOLVED or resolved.resolved is None:
            raise RegistryError(resolved.status.value, scenario.subject_ref.id)
        self._risk_scenarios[scenario.id] = replace(
            scenario,
            subject_ref=ObjectReference(
                resolved.resolved.metadata.id,
                revision=resolved.resolved.metadata.revision,
            ),
        )

    def register_control_definition(self, definition: ControlDefinition) -> None:
        require_identifier(definition.id)
        if not definition.name:
            raise RegistryError("CONTROL_DEFINITION_NAME_REQUIRED", definition.id)
        if definition.status not in {"ACTIVE", "DRAFT", "DEPRECATED", "RETIRED"}:
            raise RegistryError("CONTROL_DEFINITION_STATUS_INVALID", definition.status)
        if not definition.applies_to_kinds:
            raise RegistryError("CONTROL_APPLIES_TO_KIND_REQUIRED", definition.id)
        for kind in definition.applies_to_kinds:
            if kind not in self._types:
                raise RegistryError("CONTROL_APPLIES_TO_KIND_UNKNOWN", kind)
        objective_refs = set(definition.objective_refs)
        if definition.objective_ref is not None:
            objective_refs.add(definition.objective_ref)
        evidence_refs = set(definition.evidence_requirement_refs)
        evidence_refs.update(definition.required_evidence)
        if definition.status == "ACTIVE":
            if not objective_refs:
                raise RegistryError("CONTROL_OBJECTIVE_MISSING", definition.id)
            if not definition.requirement_refs:
                raise RegistryError("CONTROL_REQUIREMENT_MISSING", definition.id)
            if definition.owner_ref is None:
                raise RegistryError("CONTROL_OWNER_MISSING", definition.id)
            if definition.applicability_ref is None:
                raise RegistryError("CONTROL_APPLICABILITY_MISSING", definition.id)
            if not definition.trigger_refs:
                raise RegistryError("CONTROL_TRIGGER_MISSING", definition.id)
            if not evidence_refs:
                raise RegistryError("CONTROL_EVIDENCE_REQUIREMENT_MISSING", definition.id)
            if (
                definition.criticality is ControlCriticality.CRITICAL
                and definition.failure_policy_ref is None
            ):
                raise RegistryError("CONTROL_FAILURE_POLICY_MISSING", definition.id)
        self._control_definitions[definition.id] = definition

    def create_control_implementation(
        self,
        *,
        definition_id: str,
        subject_ref: ObjectReference,
        state: ControlState = ControlState.PLANNED,
        effectiveness: ControlEffectivenessResult = ControlEffectivenessResult.NOT_TESTED,
        evidence_refs: tuple[ObjectReference, ...] = (),
        result: ControlResult | None = None,
        effectiveness_assessment_ref: str | None = None,
    ) -> ControlImplementation:
        definition = self._control_definitions.get(definition_id)
        if definition is None:
            raise RegistryError("CONTROL_DEFINITION_NOT_FOUND", definition_id)
        if definition.status != "ACTIVE":
            raise RegistryError("CONTROL_DEFINITION_INACTIVE", definition_id)
        subject = self.resolve_reference(subject_ref)
        if subject.status is not ResolutionStatus.RESOLVED or subject.resolved is None:
            raise RegistryError(subject.status.value, subject_ref.id)
        if subject.resolved.kind not in definition.applies_to_kinds:
            raise RegistryError("CONTROL_SUBJECT_KIND_INVALID", subject.resolved.kind)
        if len(evidence_refs) < len(definition.required_evidence):
            raise RegistryError("CONTROL_EVIDENCE_INCOMPLETE", definition.id)
        resolved_evidence = self._resolve_object_references(
            evidence_refs,
            "CONTROL_EVIDENCE_INVALID",
        )
        if effectiveness is ControlEffectivenessResult.EFFECTIVE:
            if not resolved_evidence:
                raise RegistryError("CONTROL_EFFECTIVENESS_EVIDENCE_REQUIRED", definition.id)
            if effectiveness_assessment_ref is None:
                raise RegistryError(
                    "CONTROL_EFFECTIVENESS_ASSESSMENT_REQUIRED",
                    definition.id,
                )
        if result is not None and result.evaluation_outcome is ControlEvaluationOutcome.PASS:
            result_evidence = result.evidence_refs or resolved_evidence
            if not result_evidence:
                raise RegistryError("CONTROL_PASS_EVIDENCE_REQUIRED", definition.id)
        self._control_implementation_sequence += 1
        implementation = ControlImplementation(
            id=f"CTRL-{self._control_implementation_sequence:06d}",
            definition_id=definition.id,
            definition_version=definition.version,
            subject_ref=ObjectReference(
                subject.resolved.metadata.id,
                revision=subject.resolved.metadata.revision,
            ),
            state=state,
            effectiveness=effectiveness,
            evidence_refs=resolved_evidence,
            created_at=datetime.now(UTC),
            result=result,
            effectiveness_assessment_ref=effectiveness_assessment_ref,
        )
        self._control_implementations[implementation.id] = implementation
        return implementation

    def create_risk(
        self,
        *,
        definition_id: str,
        subject_ref: ObjectReference,
        accountable_ref: str,
        scenario_id: str | None = None,
        state: RiskLifecycleState = RiskLifecycleState.OPEN,
    ) -> RiskInstance:
        definition = self._risk_definitions.get(definition_id)
        if definition is None:
            raise RegistryError("RISK_DEFINITION_NOT_FOUND", definition_id)
        if definition.status != "ACTIVE":
            raise RegistryError("RISK_DEFINITION_INACTIVE", definition_id)
        if not accountable_ref:
            raise RegistryError("RISK_ACCOUNTABLE_REQUIRED", definition_id)
        subject = self.resolve_reference(subject_ref)
        if subject.status is not ResolutionStatus.RESOLVED or subject.resolved is None:
            raise RegistryError(subject.status.value, subject_ref.id)
        if subject.resolved.kind not in definition.subject_kinds:
            raise RegistryError("RISK_SUBJECT_KIND_INVALID", subject.resolved.kind)
        if definition.scenario_required and scenario_id is None:
            raise RegistryError("RISK_SCENARIO_REQUIRED", definition_id)
        if scenario_id is not None:
            scenario = self._risk_scenarios.get(scenario_id)
            if scenario is None:
                raise RegistryError("RISK_SCENARIO_NOT_FOUND", scenario_id)
            if scenario.status != "ACTIVE":
                raise RegistryError("RISK_SCENARIO_INACTIVE", scenario_id)
            if scenario.subject_ref.id != subject.resolved.metadata.id:
                raise RegistryError("RISK_SCENARIO_SUBJECT_MISMATCH", scenario_id)
        self._risk_sequence += 1
        risk = RiskInstance(
            id=f"RISK-{self._risk_sequence:06d}",
            definition_id=definition.id,
            definition_version=definition.version,
            subject_ref=ObjectReference(
                subject.resolved.metadata.id,
                revision=subject.resolved.metadata.revision,
            ),
            scenario_id=scenario_id,
            accountable_ref=accountable_ref,
            state=state,
            created_at=datetime.now(UTC),
        )
        self._risks[risk.id] = risk
        return risk

    def get_risk(self, risk_id: str) -> RiskInstance:
        risk = self._risks.get(risk_id)
        if risk is None:
            raise RegistryError("RISK_NOT_FOUND", risk_id)
        return risk

    def assess_risk(
        self,
        *,
        risk_id: str,
        likelihood_level: RiskLevel,
        impact: dict[str, RiskLevel],
        result_level: RiskLevel,
        confidence: RiskLevel = RiskLevel.MEDIUM,
        likelihood_type: LikelihoodType = LikelihoodType.QUALITATIVE,
        evidence_refs: tuple[ObjectReference, ...] = (),
        control_refs: tuple[str, ...] = (),
        as_of: datetime | None = None,
    ) -> RiskAssessment:
        risk = self.get_risk(risk_id)
        if not impact:
            raise RegistryError("RISK_IMPACT_REQUIRED", risk_id)
        for control_ref in control_refs:
            if control_ref not in self._control_implementations:
                raise RegistryError("RISK_CONTROL_NOT_FOUND", control_ref)
        resolved_evidence = self._resolve_object_references(
            evidence_refs,
            "RISK_EVIDENCE_INVALID",
        )
        assessed_at = datetime.now(UTC)
        effective_as_of = as_of or assessed_at
        controls = tuple(self._control_implementations[ref] for ref in control_refs)
        proof = {
            "risk": risk.canonical_document(),
            "likelihood": {
                "type": likelihood_type.value,
                "level": likelihood_level.value,
            },
            "impact": {
                dimension: level.value for dimension, level in sorted(impact.items())
            },
            "result": {"level": result_level.value},
            "confidence": {"level": confidence.value},
            "evidenceRefs": [
                {"id": reference.id, "revision": reference.revision}
                for reference in resolved_evidence
            ],
            "controls": [control.canonical_document() for control in controls],
            "asOf": effective_as_of.isoformat(),
        }
        self._risk_assessment_sequence += 1
        assessment = RiskAssessment(
            id=f"RA-{self._risk_assessment_sequence:06d}",
            risk_id=risk.id,
            as_of=effective_as_of,
            likelihood_type=likelihood_type,
            likelihood_level=likelihood_level,
            impact=dict(sorted(impact.items())),
            result_level=result_level,
            confidence=confidence,
            evidence_refs=resolved_evidence,
            control_refs=control_refs,
            proof=proof,
            proof_hash=f"sha256:{specification_hash(proof)}",
            assessed_at=assessed_at,
        )
        self._risk_assessments[assessment.id] = assessment
        return assessment

    def create_risk_treatment_plan(
        self,
        *,
        risk_id: str,
        strategy: RiskTreatmentStrategy,
        action_refs: tuple[str, ...],
        target_level: RiskLevel,
        deadline_at: datetime | None = None,
    ) -> RiskTreatmentPlan:
        self.get_risk(risk_id)
        if strategy in {
            RiskTreatmentStrategy.AVOID,
            RiskTreatmentStrategy.MITIGATE,
            RiskTreatmentStrategy.TRANSFER,
            RiskTreatmentStrategy.SHARE,
        } and not action_refs:
            raise RegistryError("RISK_TREATMENT_ACTION_REQUIRED", risk_id)
        self._risk_treatment_sequence += 1
        plan = RiskTreatmentPlan(
            id=f"RTP-{self._risk_treatment_sequence:06d}",
            risk_id=risk_id,
            strategy=strategy,
            action_refs=action_refs,
            target_level=target_level,
            status=RiskTreatmentStatus.NOT_STARTED,
            deadline_at=deadline_at,
            created_at=datetime.now(UTC),
        )
        self._risk_treatment_plans[plan.id] = plan
        return plan

    def accept_risk(
        self,
        *,
        risk_id: str,
        assessment_id: str,
        accepted_by_ref: str,
        rationale_code: str,
        valid_until: datetime | None,
    ) -> RiskAcceptance:
        risk = self.get_risk(risk_id)
        assessment = self._risk_assessments.get(assessment_id)
        if assessment is None:
            raise RegistryError("RISK_ASSESSMENT_NOT_FOUND", assessment_id)
        if assessment.risk_id != risk.id:
            raise RegistryError("RISK_ACCEPTANCE_ASSESSMENT_MISMATCH", assessment_id)
        if not accepted_by_ref:
            raise RegistryError("RISK_ACCEPTANCE_ACTOR_REQUIRED", risk_id)
        if not rationale_code:
            raise RegistryError("RISK_ACCEPTANCE_RATIONALE_REQUIRED", risk_id)
        accepted_at = datetime.now(UTC)
        proof = {
            "risk": risk.canonical_document(),
            "assessment": assessment.canonical_document(),
            "acceptedByRef": accepted_by_ref,
            "rationale": {"code": rationale_code},
            "validUntil": (
                valid_until.isoformat() if valid_until is not None else None
            ),
        }
        self._risk_acceptance_sequence += 1
        acceptance = RiskAcceptance(
            id=f"RAC-{self._risk_acceptance_sequence:06d}",
            risk_id=risk.id,
            assessment_id=assessment.id,
            accepted_by_ref=accepted_by_ref,
            status=RiskAcceptanceStatus.ACTIVE,
            rationale_code=rationale_code,
            accepted_at=accepted_at,
            valid_until=valid_until,
            proof=proof,
            proof_hash=f"sha256:{specification_hash(proof)}",
        )
        self._risk_acceptances[acceptance.id] = acceptance
        return acceptance

    def register_remediation_definition(
        self,
        definition: RemediationDefinition,
    ) -> None:
        require_identifier(definition.id)
        if not definition.name:
            raise RegistryError("REMEDIATION_DEFINITION_NAME_REQUIRED", definition.id)
        if not definition.trigger_types:
            raise RegistryError("REMEDIATION_TRIGGER_REQUIRED", definition.id)
        if (
            definition.independent_verification_required
            and not definition.effectiveness_evidence_required
        ):
            raise RegistryError("REMEDIATION_EVIDENCE_REQUIRED", definition.id)
        self._remediation_definitions[definition.id] = definition

    def open_remediation_case(
        self,
        *,
        definition_id: str,
        trigger: RemediationTrigger,
        subject_ref: ObjectReference,
        objective: str,
        owner_ref: str,
        severity: RemediationSeverity,
        priority: RemediationPriority,
        deadlines: RemediationDeadlines | None = None,
    ) -> RemediationCase:
        definition = self._remediation_definitions.get(definition_id)
        if definition is None:
            raise RegistryError("REMEDIATION_DEFINITION_NOT_FOUND", definition_id)
        if trigger.trigger_type not in definition.trigger_types:
            raise RegistryError("REMEDIATION_TRIGGER_INVALID", trigger.trigger_type.value)
        if not trigger.ref:
            raise RegistryError("REMEDIATION_TRIGGER_REF_REQUIRED", definition_id)
        if trigger.trigger_type is RemediationTriggerType.CONDITION_FAILURE:
            self.get_condition_failure(trigger.ref)
        subject = self.resolve_reference(subject_ref)
        if subject.status is not ResolutionStatus.RESOLVED or subject.resolved is None:
            raise RegistryError(subject.status.value, subject_ref.id)
        if not objective:
            raise RegistryError("REMEDIATION_OBJECTIVE_REQUIRED", definition_id)
        if not owner_ref:
            raise RegistryError("REMEDIATION_OWNER_REQUIRED", definition_id)
        self._remediation_case_sequence += 1
        remediation_case = RemediationCase(
            id=f"REM-{self._remediation_case_sequence:06d}",
            definition_id=definition.id,
            definition_version=definition.version,
            trigger=trigger,
            subject_ref=ObjectReference(
                subject.resolved.metadata.id,
                revision=subject.resolved.metadata.revision,
            ),
            objective=objective,
            owner_ref=owner_ref,
            severity=severity,
            priority=priority,
            status=RemediationStatus.OPEN,
            opened_at=datetime.now(UTC),
            deadlines=deadlines or RemediationDeadlines(),
        )
        self._remediation_cases[remediation_case.id] = remediation_case
        return remediation_case

    def verify_remediation(
        self,
        *,
        case_id: str,
        result: RemediationVerificationResult,
        verifier_ref: str,
        evidence_refs: tuple[ObjectReference, ...],
        independent: bool = False,
    ) -> RemediationVerification:
        remediation_case = self.get_remediation_case(case_id)
        definition = self._remediation_definitions[remediation_case.definition_id]
        if not verifier_ref:
            raise RegistryError("REMEDIATION_VERIFIER_REQUIRED", case_id)
        if definition.independent_verification_required and not independent:
            raise RegistryError("REMEDIATION_INDEPENDENCE_REQUIRED", case_id)
        if not evidence_refs:
            raise RegistryError("REMEDIATION_EVIDENCE_REQUIRED", case_id)
        resolved_evidence = self._resolve_object_references(
            evidence_refs,
            "REMEDIATION_EVIDENCE_INVALID",
        )
        self._remediation_verification_sequence += 1
        verification = RemediationVerification(
            id=f"REMV-{self._remediation_verification_sequence:06d}",
            case_ref=case_id,
            result=result,
            verifier_ref=verifier_ref,
            evidence_refs=resolved_evidence,
            verified_at=datetime.now(UTC),
            independent=independent,
        )
        self._remediation_verifications[verification.id] = verification
        if result is RemediationVerificationResult.VERIFIED:
            self._remediation_cases[case_id] = replace(
                remediation_case,
                status=RemediationStatus.VERIFIED,
            )
        return verification

    def assess_remediation_effectiveness(
        self,
        *,
        case_id: str,
        verification_id: str,
        result: RemediationEffectivenessResult,
        assessor_ref: str,
        evidence_refs: tuple[ObjectReference, ...],
    ) -> RemediationEffectivenessAssessment:
        self.get_remediation_case(case_id)
        verification = self._remediation_verifications.get(verification_id)
        if verification is None:
            raise RegistryError("REMEDIATION_VERIFICATION_NOT_FOUND", verification_id)
        if verification.case_ref != case_id:
            raise RegistryError("REMEDIATION_VERIFICATION_CASE_MISMATCH", verification_id)
        if verification.result is not RemediationVerificationResult.VERIFIED:
            raise RegistryError("REMEDIATION_VERIFICATION_NOT_VERIFIED", verification_id)
        if not assessor_ref:
            raise RegistryError("REMEDIATION_ASSESSOR_REQUIRED", case_id)
        if not evidence_refs:
            raise RegistryError("REMEDIATION_EFFECTIVENESS_EVIDENCE_REQUIRED", case_id)
        resolved_evidence = self._resolve_object_references(
            evidence_refs,
            "REMEDIATION_EVIDENCE_INVALID",
        )
        self._remediation_effectiveness_sequence += 1
        assessment = RemediationEffectivenessAssessment(
            id=f"REME-{self._remediation_effectiveness_sequence:06d}",
            case_ref=case_id,
            result=result,
            verification_ref=verification_id,
            evidence_refs=resolved_evidence,
            assessed_at=datetime.now(UTC),
            assessor_ref=assessor_ref,
        )
        self._remediation_effectiveness[assessment.id] = assessment
        return assessment

    def accept_remediation(
        self,
        *,
        case_id: str,
        effectiveness_id: str,
        accepted_by_ref: str,
        result: RemediationAcceptanceResult = RemediationAcceptanceResult.ACCEPTED,
    ) -> RemediationAcceptance:
        self.get_remediation_case(case_id)
        assessment = self._remediation_effectiveness.get(effectiveness_id)
        if assessment is None:
            raise RegistryError("REMEDIATION_EFFECTIVENESS_NOT_FOUND", effectiveness_id)
        if assessment.case_ref != case_id:
            raise RegistryError("REMEDIATION_EFFECTIVENESS_CASE_MISMATCH", effectiveness_id)
        if assessment.result is not RemediationEffectivenessResult.EFFECTIVE:
            raise RegistryError("REMEDIATION_NOT_EFFECTIVE", effectiveness_id)
        if not accepted_by_ref:
            raise RegistryError("REMEDIATION_ACCEPTOR_REQUIRED", case_id)
        self._remediation_acceptance_sequence += 1
        acceptance = RemediationAcceptance(
            id=f"REMA-{self._remediation_acceptance_sequence:06d}",
            case_ref=case_id,
            result=result,
            effectiveness_ref=effectiveness_id,
            accepted_by_ref=accepted_by_ref,
            accepted_at=datetime.now(UTC),
        )
        self._remediation_acceptances[acceptance.id] = acceptance
        if result is RemediationAcceptanceResult.ACCEPTED:
            self._remediation_cases[case_id] = replace(
                self._remediation_cases[case_id],
                status=RemediationStatus.ACCEPTED,
            )
        return acceptance

    def close_remediation_case(
        self,
        *,
        case_id: str,
        verification_id: str,
        effectiveness_id: str,
        acceptance_id: str,
        evidence_refs: tuple[ObjectReference, ...],
        closed_by_ref: str,
    ) -> RemediationClosure:
        remediation_case = self.get_remediation_case(case_id)
        verification = self._remediation_verifications.get(verification_id)
        effectiveness = self._remediation_effectiveness.get(effectiveness_id)
        acceptance = self._remediation_acceptances.get(acceptance_id)
        if verification is None or verification.case_ref != case_id:
            raise RegistryError("REMEDIATION_VERIFICATION_NOT_FOUND", verification_id)
        if effectiveness is None or effectiveness.case_ref != case_id:
            raise RegistryError("REMEDIATION_EFFECTIVENESS_NOT_FOUND", effectiveness_id)
        if acceptance is None or acceptance.case_ref != case_id:
            raise RegistryError("REMEDIATION_ACCEPTANCE_NOT_FOUND", acceptance_id)
        if verification.result is not RemediationVerificationResult.VERIFIED:
            raise RegistryError("REMEDIATION_CLOSURE_VERIFICATION_REQUIRED", case_id)
        if effectiveness.result is not RemediationEffectivenessResult.EFFECTIVE:
            raise RegistryError("REMEDIATION_CLOSURE_EFFECTIVENESS_REQUIRED", case_id)
        if acceptance.result is not RemediationAcceptanceResult.ACCEPTED:
            raise RegistryError("REMEDIATION_CLOSURE_ACCEPTANCE_REQUIRED", case_id)
        if not evidence_refs:
            raise RegistryError("REMEDIATION_CLOSURE_EVIDENCE_REQUIRED", case_id)
        if not closed_by_ref:
            raise RegistryError("REMEDIATION_CLOSER_REQUIRED", case_id)
        resolved_evidence = self._resolve_object_references(
            evidence_refs,
            "REMEDIATION_EVIDENCE_INVALID",
        )
        self._remediation_closure_sequence += 1
        closure = RemediationClosure(
            id=f"REMC-{self._remediation_closure_sequence:06d}",
            case_ref=case_id,
            verification_ref=verification_id,
            effectiveness_ref=effectiveness_id,
            acceptance_ref=acceptance_id,
            evidence_refs=resolved_evidence,
            closed_by_ref=closed_by_ref,
            closed_at=datetime.now(UTC),
        )
        self._remediation_closures[closure.id] = closure
        self._remediation_cases[case_id] = replace(
            remediation_case,
            status=RemediationStatus.CLOSED,
        )
        return closure

    def get_remediation_case(self, case_id: str) -> RemediationCase:
        remediation_case = self._remediation_cases.get(case_id)
        if remediation_case is None:
            raise RegistryError("REMEDIATION_CASE_NOT_FOUND", case_id)
        return remediation_case

    def evaluate_decision_obligations(
        self,
        decision: DecisionEvaluation,
    ) -> tuple[ObligationActivation, ...]:
        evaluated_at = datetime.now(UTC)
        activations: list[ObligationActivation] = []
        for definition in sorted(
            self._obligation_definitions.values(),
            key=lambda item: item.id,
        ):
            if definition.status != "ACTIVE":
                continue
            activation = self._activate_obligation_from_decision(
                definition,
                decision,
                evaluated_at,
            )
            activations.append(activation)
        return tuple(activations)

    def get_obligation(self, obligation_id: str) -> ObligationInstance:
        instance = self._obligation_instances.get(obligation_id)
        if instance is None:
            raise RegistryError("OBLIGATION_NOT_FOUND", obligation_id)
        return instance

    def list_obligations(
        self,
        *,
        state: ObligationLifecycleState | None = None,
        subject_id: str | None = None,
        definition_id: str | None = None,
    ) -> tuple[ObligationInstance, ...]:
        instances = sorted(self._obligation_instances.values(), key=lambda item: item.id)
        return tuple(
            instance
            for instance in instances
            if (state is None or instance.state is state)
            and (subject_id is None or instance.subject_ref.id == subject_id)
            and (definition_id is None or instance.definition_id == definition_id)
        )

    def attach_obligation_evidence(
        self,
        *,
        obligation_id: str,
        evidence_type: str,
        evidence_ref: ObjectReference,
    ) -> ObligationInstance:
        instance = self.get_obligation(obligation_id)
        definition = self._obligation_definitions.get(instance.definition_id)
        if definition is None:
            raise RegistryError("OBLIGATION_DEFINITION_NOT_FOUND", instance.definition_id)
        if (
            definition.required_evidence
            and evidence_type not in definition.required_evidence
        ):
            raise RegistryError("OBLIGATION_EVIDENCE_TYPE_INVALID", evidence_type)
        resolution = self.resolve_reference(evidence_ref)
        if resolution.status is not ResolutionStatus.RESOLVED or resolution.resolved is None:
            raise RegistryError(resolution.status.value, evidence_ref.id)
        attached = ObligationEvidence(
            evidence_type=evidence_type,
            reference=ObjectReference(
                resolution.resolved.metadata.id,
                revision=resolution.resolved.metadata.revision,
            ),
            attached_at=datetime.now(UTC),
        )
        updated = replace(instance, evidence=(*instance.evidence, attached))
        self._obligation_instances[obligation_id] = updated
        return updated

    def evaluate_obligation(
        self,
        obligation_id: str,
    ) -> ObligationEvaluation:
        instance = self.get_obligation(obligation_id)
        definition = self._obligation_definitions.get(instance.definition_id)
        evaluated_at = datetime.now(UTC)
        if definition is None:
            raise RegistryError("OBLIGATION_DEFINITION_NOT_FOUND", instance.definition_id)
        findings: list[ConditionFinding] = []
        evidence_types = {item.evidence_type for item in instance.evidence}
        missing_evidence = tuple(
            evidence_type
            for evidence_type in definition.required_evidence
            if evidence_type not in evidence_types
        )
        if missing_evidence:
            findings.append(
                ConditionFinding(
                    "OBLIGATION_REQUIRED_EVIDENCE_MISSING",
                    f"Missing required evidence: {list(missing_evidence)}.",
                )
            )
        fulfillment_evaluation: ConditionEvaluation | None = None
        if definition.fulfillment_condition_id is not None:
            fulfillment_evaluation = self.evaluate_condition(
                condition_id=definition.fulfillment_condition_id,
                subject_id=instance.subject_ref.id,
            )
            if fulfillment_evaluation.outcome is ConditionOutcome.UNKNOWN:
                findings.extend(fulfillment_evaluation.findings)
            elif fulfillment_evaluation.outcome is not ConditionOutcome.SATISFIED:
                findings.extend(fulfillment_evaluation.findings)
        breach_evaluation: ConditionEvaluation | None = None
        breach_satisfied = False
        if definition.breach is not None and definition.breach.condition_id is not None:
            breach_evaluation = self.evaluate_condition(
                condition_id=definition.breach.condition_id,
                subject_id=instance.subject_ref.id,
            )
            breach_satisfied = breach_evaluation.outcome is ConditionOutcome.SATISFIED
        deadline_breached = instance.due_at is not None and evaluated_at > instance.due_at
        fulfilled_by_condition = (
            fulfillment_evaluation is None
            or fulfillment_evaluation.outcome is ConditionOutcome.SATISFIED
        )
        if not missing_evidence and fulfilled_by_condition:
            result = ObligationFulfillmentResult.FULFILLED
            state = ObligationLifecycleState.FULFILLED
        elif breach_satisfied or deadline_breached:
            result = ObligationFulfillmentResult.NOT_FULFILLED
            state = ObligationLifecycleState.BREACHED
            findings.append(
                ConditionFinding(
                    "OBLIGATION_BREACHED",
                    "Obligation breach condition or deadline was reached.",
                )
            )
        elif (
            fulfillment_evaluation is not None
            and fulfillment_evaluation.outcome is ConditionOutcome.UNKNOWN
        ):
            result = ObligationFulfillmentResult.UNKNOWN
            state = instance.state
        else:
            result = ObligationFulfillmentResult.NOT_FULFILLED
            state = instance.state
        updated = replace(instance, state=state)
        self._obligation_instances[obligation_id] = updated
        proof = {
            "definition": definition.canonical_document(),
            "instance": updated.canonical_document(),
            "fulfillmentCondition": (
                fulfillment_evaluation.canonical_document()
                if fulfillment_evaluation is not None
                else None
            ),
            "breachCondition": (
                breach_evaluation.canonical_document()
                if breach_evaluation is not None
                else None
            ),
        }
        return ObligationEvaluation(
            obligation_id=updated.id,
            definition_id=updated.definition_id,
            definition_version=updated.definition_version,
            result=result,
            state=state,
            findings=tuple(findings),
            evidence=updated.evidence,
            proof=proof,
            proof_hash=f"sha256:{specification_hash(proof)}",
            evaluated_at=evaluated_at,
        )

    def evaluate_decision_request(
        self,
        request: DecisionRequest,
    ) -> DecisionEvaluation:
        require_identifier(request.id)
        return self.evaluate_decision(
            decision_id=request.decision_id,
            resource_id=request.resource_id,
            actor=request.actor,
            context=request.context,
            request_id=request.id,
            requested_action=request.requested_action,
        )

    def create_task(
        self,
        *,
        goal_ref: str,
        assignee_ref: str,
        subject_ref: ObjectReference,
        actor: ActorReference,
        mode: TaskMode = TaskMode.AD_HOC,
        definition_id: str | None = None,
        completion_condition_id: str | None = None,
        allowed_actions: tuple[str, ...] = (),
        required_constraint_ids: tuple[str, ...] = (),
        dependencies: tuple[TaskDependency, ...] = (),
        outputs: tuple[TaskOutputDefinition, ...] = (),
        budget: int | None = None,
        parent_allowed_actions: tuple[str, ...] = (),
        parent_required_constraint_ids: tuple[str, ...] = (),
        parent_budget: int | None = None,
    ) -> TaskInstance:
        if not goal_ref:
            raise RegistryError("TASK_GOAL_REQUIRED", "goalRef is required")
        if not assignee_ref:
            raise RegistryError("TASK_ASSIGNEE_INVALID", "assigneeRef is required")
        subject_resolution = self.resolve_reference(subject_ref)
        if subject_resolution.status is not ResolutionStatus.RESOLVED:
            raise RegistryError(subject_resolution.status.value, subject_ref.id)
        definition: TaskDefinition | None = None
        if mode is TaskMode.DEFINED:
            if definition_id is None:
                raise RegistryError("TASK_DEFINITION_REQUIRED", goal_ref)
            definition = self._task_definitions.get(definition_id)
            if definition is None:
                raise RegistryError("TASK_DEFINITION_NOT_FOUND", definition_id)
            if definition.status != "ACTIVE":
                raise RegistryError("TASK_DEFINITION_INACTIVE", definition_id)
            completion_condition_id = definition.completion_condition_id
            allowed_actions = definition.allowed_actions
            required_constraint_ids = definition.required_constraint_ids
            outputs = definition.outputs
        elif definition_id is not None:
            raise RegistryError("TASK_AD_HOC_DEFINITION_FORBIDDEN", definition_id)
        if completion_condition_id is not None:
            self._require_registered_condition(
                completion_condition_id,
                "TASK_COMPLETION_CONDITION_UNKNOWN",
            )
        for constraint_id in required_constraint_ids:
            if constraint_id not in self._constraints:
                raise RegistryError("TASK_CONSTRAINT_UNKNOWN", constraint_id)
        if parent_allowed_actions and not set(allowed_actions).issubset(parent_allowed_actions):
            raise RegistryError("TASK_AUTHORITY_EXCEEDS_GOAL", goal_ref)
        if not set(parent_required_constraint_ids).issubset(required_constraint_ids):
            raise RegistryError("TASK_CONSTRAINT_WEAKENING", goal_ref)
        if budget is not None and parent_budget is not None and budget > parent_budget:
            raise RegistryError("TASK_BUDGET_EXCEEDS_GOAL", goal_ref)
        self._require_unique_task_outputs(outputs)
        self._require_task_dependencies_resolvable(dependencies)
        self._task_sequence += 1
        task_id = f"TASK-{self._task_sequence:06d}"
        now = datetime.now(UTC)
        task = TaskInstance(
            id=task_id,
            goal_ref=goal_ref,
            assignee_ref=assignee_ref,
            subject_ref=ObjectReference(
                (
                    subject_resolution.resolved.metadata.id
                    if subject_resolution.resolved
                    else subject_ref.id
                ),
                revision=(
                    subject_resolution.resolved.metadata.revision
                    if subject_resolution.resolved
                    else subject_ref.revision
                ),
            ),
            mode=mode,
            state=TaskLifecycleState.CREATED,
            definition_id=definition.id if definition is not None else None,
            definition_version=definition.version if definition is not None else None,
            completion_condition_id=completion_condition_id,
            allowed_actions=allowed_actions,
            required_constraint_ids=required_constraint_ids,
            dependencies=dependencies,
            outputs=outputs,
            budget=budget,
            created_at=now,
            updated_at=now,
        )
        self._tasks[task_id] = task
        self._require_no_task_dependency_cycle()
        return task

    def get_task(self, task_id: str) -> TaskInstance:
        task = self._tasks.get(task_id)
        if task is None:
            raise RegistryError("TASK_NOT_FOUND", task_id)
        return task

    def set_task_dependencies(
        self,
        *,
        task_id: str,
        dependencies: tuple[TaskDependency, ...],
    ) -> TaskInstance:
        task = self.get_task(task_id)
        self._require_task_dependencies_resolvable(dependencies)
        updated = replace(task, dependencies=dependencies, updated_at=datetime.now(UTC))
        self._tasks[task_id] = updated
        try:
            self._require_no_task_dependency_cycle()
        except RegistryError:
            self._tasks[task_id] = task
            raise
        return updated

    def transition_task(
        self,
        *,
        task_id: str,
        target_state: TaskLifecycleState,
    ) -> TaskInstance:
        task = self.get_task(task_id)
        allowed = {
            TaskLifecycleState.CREATED: {TaskLifecycleState.READY},
            TaskLifecycleState.READY: {
                TaskLifecycleState.IN_PROGRESS,
                TaskLifecycleState.BLOCKED,
                TaskLifecycleState.CANCELLED,
            },
            TaskLifecycleState.IN_PROGRESS: {
                TaskLifecycleState.BLOCKED,
                TaskLifecycleState.FAILED,
                TaskLifecycleState.SUSPENDED,
            },
            TaskLifecycleState.BLOCKED: {TaskLifecycleState.READY},
            TaskLifecycleState.SUSPENDED: {TaskLifecycleState.READY},
        }
        if target_state not in allowed.get(task.state, set()):
            raise RegistryError(
                "TASK_TRANSITION_INVALID",
                f"{task.state.value} -> {target_state.value}",
            )
        if target_state is TaskLifecycleState.IN_PROGRESS:
            self._require_task_dependencies_satisfied(task)
        updated = replace(task, state=target_state, updated_at=datetime.now(UTC))
        self._tasks[task_id] = updated
        return updated

    def evaluate_task_completion(self, task_id: str) -> TaskCompletionEvaluation:
        task = self.get_task(task_id)
        evaluated_at = datetime.now(UTC)
        findings: list[ConditionFinding] = []
        condition_evaluation: ConditionEvaluation | None = None
        if task.state is not TaskLifecycleState.IN_PROGRESS:
            findings.append(
                ConditionFinding(
                    "TASK_NOT_IN_PROGRESS",
                    f"Task state is {task.state.value}.",
                )
            )
        if task.completion_condition_id is None:
            findings.append(
                ConditionFinding(
                    "TASK_COMPLETION_CONDITION_REQUIRED",
                    "Task completion requires a governed condition.",
                )
            )
        else:
            condition_evaluation = self.evaluate_condition(
                condition_id=task.completion_condition_id,
                subject_id=task.subject_ref.id,
            )
        result = TaskCompletionResult.NOT_COMPLETED
        state = task.state
        if not findings and condition_evaluation is not None:
            if condition_evaluation.outcome is ConditionOutcome.SATISFIED:
                result = TaskCompletionResult.COMPLETED
                state = TaskLifecycleState.COMPLETED
                self._tasks[task_id] = replace(
                    task,
                    state=state,
                    updated_at=evaluated_at,
                )
            elif condition_evaluation.outcome is ConditionOutcome.UNKNOWN:
                result = TaskCompletionResult.UNKNOWN
                findings.extend(condition_evaluation.findings)
            else:
                findings.extend(condition_evaluation.findings)
        proof = {
            "task": self.get_task(task_id).canonical_document(),
            "conditionEvaluation": (
                condition_evaluation.canonical_document()
                if condition_evaluation is not None
                else None
            ),
        }
        return TaskCompletionEvaluation(
            task_id=task_id,
            result=result,
            state=state,
            condition_evaluation=condition_evaluation,
            findings=tuple(findings),
            proof=proof,
            proof_hash=f"sha256:{specification_hash(proof)}",
            evaluated_at=evaluated_at,
        )

    def record_task_output(
        self,
        *,
        task_id: str,
        output_id: str,
        value: Any,
        source: TaskOutputSource,
        provenance: dict[str, Any],
    ) -> TaskInstance:
        task = self.get_task(task_id)
        output = next((item for item in task.outputs if item.id == output_id), None)
        if output is None:
            raise RegistryError("TASK_OUTPUT_NOT_DECLARED", output_id)
        if output.type == "enum" and output.enum_values and value not in output.enum_values:
            raise RegistryError("TASK_OUTPUT_VALUE_INVALID", output_id)
        recorded = TaskOutputValue(
            output_id=output_id,
            value=value,
            source=source,
            provenance=provenance,
            recorded_at=datetime.now(UTC),
        )
        updated = replace(
            task,
            output_values=(*task.output_values, recorded),
            updated_at=recorded.recorded_at,
        )
        self._tasks[task_id] = updated
        return updated

    def create_plan(
        self,
        *,
        goal_ref: str,
        planner_ref: str,
        task_ids: tuple[str, ...],
        expected_outcome_ref: str | None = None,
    ) -> PlanInstance:
        if not goal_ref:
            raise RegistryError("PLAN_GOAL_REQUIRED", "goalRef is required")
        if not planner_ref:
            raise RegistryError("PLAN_PLANNER_REQUIRED", "plannerRef is required")
        self._require_plan_tasks(goal_ref, task_ids)
        self._plan_sequence += 1
        plan = PlanInstance(
            id=f"PLAN-{self._plan_sequence:06d}-v1",
            goal_ref=goal_ref,
            planner_ref=planner_ref,
            task_ids=task_ids,
            version=1,
            state=PlanLifecycleState.ACTIVE,
            expected_outcome_ref=expected_outcome_ref,
        )
        self._plans[plan.id] = plan
        return plan

    def get_plan(self, plan_id: str) -> PlanInstance:
        plan = self._plans.get(plan_id)
        if plan is None:
            raise RegistryError("PLAN_NOT_FOUND", plan_id)
        return plan

    def validate_plan(self, plan_id: str) -> PlanValidation:
        plan = self.get_plan(plan_id)
        evaluated_at = datetime.now(UTC)
        findings: list[ConditionFinding] = []
        try:
            self._require_plan_tasks(plan.goal_ref, plan.task_ids)
            self._require_no_task_dependency_cycle(plan.task_ids)
        except RegistryError as exc:
            findings.append(ConditionFinding(exc.code, exc.message))
        result = PlanValidationResult.VALID if not findings else PlanValidationResult.INVALID
        updated = replace(plan, validation_result=result)
        self._plans[plan_id] = updated
        proof = {
            "plan": updated.canonical_document(),
            "tasks": [self._tasks[task_id].canonical_document() for task_id in plan.task_ids],
        }
        return PlanValidation(
            plan_id=plan_id,
            result=result,
            findings=tuple(findings),
            proof=proof,
            proof_hash=f"sha256:{specification_hash(proof)}",
            evaluated_at=evaluated_at,
        )

    def revise_plan(
        self,
        *,
        plan_id: str,
        reason: str,
        task_ids: tuple[str, ...],
    ) -> PlanInstance:
        current = self.get_plan(plan_id)
        if current.state is PlanLifecycleState.SUPERSEDED:
            raise RegistryError("PLAN_ALREADY_SUPERSEDED", plan_id)
        self._require_plan_tasks(current.goal_ref, task_ids)
        new_id = f"{plan_id.rsplit('-v', 1)[0]}-v{current.version + 1}"
        revised = PlanInstance(
            id=new_id,
            goal_ref=current.goal_ref,
            planner_ref=current.planner_ref,
            task_ids=task_ids,
            version=current.version + 1,
            state=PlanLifecycleState.ACTIVE,
            expected_outcome_ref=current.expected_outcome_ref,
            previous_plan_id=current.id,
            revision_reason=reason,
        )
        self._plans[new_id] = revised
        self._plans[plan_id] = replace(
            current,
            state=PlanLifecycleState.SUPERSEDED,
            superseded_by=new_id,
        )
        return revised

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
        self._require_active_namespace(namespace)
        if object_id in self._objects:
            raise RegistryError("IDENTITY_CONFLICT", f"object already exists: {object_id}")
        self._require_valid_spec(kind, spec)
        self._require_valid_initial_lifecycle(kind, lifecycle_state)
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

    def create_relationship(
        self,
        *,
        relationship_id: str,
        type_id: str,
        source_id: str,
        target: ObjectReference,
        actor: ActorReference,
        evidence: dict[str, ObjectReference] | None = None,
    ) -> ObjectEnvelope:
        require_identifier(relationship_id)
        relationship_type = self._relationship_types.get(type_id)
        if relationship_type is None:
            raise RegistryError("RELATIONSHIP_TYPE_NOT_REGISTERED", type_id)
        if relationship_type.lifecycle is not RelationshipLifecycle.ACTIVE:
            raise RegistryError("RELATIONSHIP_TYPE_INACTIVE", type_id)
        source = self.get_object(source_id)
        target_resolution = self.resolve_reference(
            target,
            target_kinds=relationship_type.target_kinds,
        )
        if target_resolution.status is not ResolutionStatus.RESOLVED:
            raise RegistryError(target_resolution.status.value, f"target: {target_resolution.code}")
        if target_resolution.resolved is None:
            raise RegistryError("REFERENCE_NOT_FOUND", f"target: {target.id}")
        if source.kind not in relationship_type.source_kinds:
            raise RegistryError(
                "RELATIONSHIP_SOURCE_KIND_INVALID",
                f"{source.kind} is not valid for {type_id}",
            )
        source_type = self._types[source.kind]
        if (
            source_type.allowed_relationships
            and type_id not in source_type.allowed_relationships
        ):
            raise RegistryError(
                "RELATIONSHIP_NOT_ALLOWED_FOR_SOURCE_TYPE",
                f"{source.kind} does not allow {type_id}",
            )
        if any(item["id"] == relationship_id for item in source.relationships):
            raise RegistryError(
                "RELATIONSHIP_IDENTITY_CONFLICT",
                f"relationship already exists on source: {relationship_id}",
            )
        if target_resolution.resolved is None:
            raise RegistryError("REFERENCE_NOT_FOUND", f"target: {target.id}")
        self._require_relationship_cardinality(
            relationship_type,
            source_id=source.metadata.id,
            target_id=target_resolution.resolved.metadata.id,
        )
        resolved_evidence = self._resolve_relationship_evidence(
            relationship_type,
            evidence or {},
        )
        relationship = RelationshipInstance(
            id=relationship_id,
            type_id=type_id,
            source=ObjectReference(source.metadata.id, revision=source.metadata.revision),
            target=ObjectReference(
                target_resolution.resolved.metadata.id,
                revision=target_resolution.resolved.metadata.revision,
            ),
            evidence=resolved_evidence,
        )
        occurred_at = datetime.now(UTC)
        updated = self._object_envelope(
            kind=source.kind,
            object_id=source.metadata.id,
            namespace=source.metadata.namespace,
            revision=source.metadata.revision + 1,
            spec=source.spec,
            actor=actor,
            created_at=source.metadata.created_at,
            updated_at=occurred_at,
            lifecycle_state=source.lifecycle.state,
            relationships=(*source.relationships, relationship.canonical_document()),
        )
        self._objects[source_id].append(updated)
        self._record_relationship_audit(
            relationship_type=relationship_type,
            relationship=relationship,
            new_source_revision=updated.metadata.revision,
            actor=actor,
            occurred_at=occurred_at,
        )
        return updated

    def list_relationship_audit_records(
        self,
        relationship_id: str | None = None,
    ) -> tuple[RelationshipAuditRecord, ...]:
        if relationship_id is None:
            return tuple(self._relationship_audit_records)
        return tuple(
            record
            for record in self._relationship_audit_records
            if record.relationship_id == relationship_id
        )

    def evaluate_condition(
        self,
        *,
        condition_id: str,
        subject_id: str,
    ) -> ConditionEvaluation:
        definition = self._conditions.get(condition_id)
        evaluated_at = datetime.now(UTC)
        if definition is None:
            return self._condition_evaluation(
                condition_id=condition_id,
                condition_version=None,
                subject_id=subject_id,
                subject_revision=None,
                outcome=ConditionOutcome.UNKNOWN,
                findings=(
                    ConditionFinding(
                        "CONDITION_DEFINITION_NOT_FOUND",
                        f"Condition '{condition_id}' is not registered.",
                    ),
                ),
                proof={"inputs": []},
                evaluated_at=evaluated_at,
            )
        try:
            subject = self.get_object(subject_id)
        except RegistryError as exc:
            return self._condition_evaluation(
                condition_id=condition_id,
                condition_version=definition.version,
                subject_id=subject_id,
                subject_revision=None,
                outcome=ConditionOutcome.UNKNOWN,
                findings=(
                    ConditionFinding(
                        "CONDITION_SUBJECT_NOT_FOUND",
                        exc.message,
                    ),
                ),
                proof={"definition": definition.canonical_document(), "inputs": []},
                evaluated_at=evaluated_at,
            )
        findings: list[ConditionFinding] = []
        proof_inputs: list[dict[str, Any]] = [
            {
                "kind": "subject",
                "id": subject.metadata.id,
                "revision": subject.metadata.revision,
                "objectKind": subject.kind,
                "lifecycleState": subject.lifecycle.state,
            }
        ]
        if subject.kind not in definition.subject_kinds:
            findings.append(
                ConditionFinding(
                    "CONDITION_SUBJECT_KIND_INVALID",
                    f"{subject.kind} is not valid for {condition_id}.",
                )
            )
        for clause in definition.clauses:
            finding, proof = self._evaluate_condition_clause(subject, clause)
            proof_inputs.append(proof)
            if finding is not None:
                findings.append(finding)
        unknown = any(finding.code.endswith("_UNKNOWN") for finding in findings)
        outcome = (
            ConditionOutcome.UNKNOWN
            if unknown
            else ConditionOutcome.NOT_SATISFIED
            if findings
            else ConditionOutcome.SATISFIED
        )
        return self._condition_evaluation(
            condition_id=condition_id,
            condition_version=definition.version,
            subject_id=subject.metadata.id,
            subject_revision=subject.metadata.revision,
            outcome=outcome,
            findings=tuple(findings),
            proof={
                "definition": definition.canonical_document(),
                "inputs": proof_inputs,
            },
            evaluated_at=evaluated_at,
        )

    def record_condition_failure(
        self,
        *,
        previous_evaluation: ConditionEvaluation,
        current_evaluation: ConditionEvaluation,
        transition_type: ConditionFailureTransitionType,
        policy_id: str | None = None,
        detection_mode: ConditionFailureDetectionMode = (
            ConditionFailureDetectionMode.SCHEDULED_REEVALUATION
        ),
        cause: str = "UNKNOWN",
        effective_at: datetime | None = None,
    ) -> ConditionFailure:
        if previous_evaluation.condition_id != current_evaluation.condition_id:
            raise RegistryError(
                "CONDITION_FAILURE_TRANSITION_INVALID",
                previous_evaluation.condition_id,
            )
        if previous_evaluation.subject_id != current_evaluation.subject_id:
            raise RegistryError(
                "CONDITION_FAILURE_TRANSITION_INVALID",
                previous_evaluation.subject_id,
            )
        if previous_evaluation.outcome not in {
            ConditionOutcome.SATISFIED,
            ConditionOutcome.EXEMPTED,
        }:
            raise RegistryError("CONDITION_FAILURE_TRANSITION_INVALID", previous_evaluation.outcome)
        if current_evaluation.outcome in {
            ConditionOutcome.SATISFIED,
            ConditionOutcome.EXEMPTED,
        }:
            raise RegistryError("CONDITION_FAILURE_TRANSITION_INVALID", current_evaluation.outcome)
        policy = self._resolve_condition_failure_policy(
            previous_evaluation,
            current_evaluation,
            policy_id,
        )
        effects = (
            policy.effects
            if policy is not None
            else (ConditionFailureEffect.DECISION_REASSESSMENT_REQUIRED,)
        )
        severity = (
            policy.severity
            if policy is not None
            else ConditionFailureSeverity.MEDIUM
        )
        episode_key = self._condition_failure_episode_key(
            previous_evaluation,
            current_evaluation,
        )
        active_failure_id = self._active_condition_failure_keys.get(episode_key)
        if active_failure_id is not None:
            return self._condition_failures[active_failure_id]
        self._condition_failure_sequence += 1
        detected_at = datetime.now(UTC)
        failure = ConditionFailure(
            id=f"CF-{self._condition_failure_sequence:06d}",
            condition_id=current_evaluation.condition_id,
            condition_version=current_evaluation.condition_version,
            subject_ref=ObjectReference(
                current_evaluation.subject_id,
                revision=current_evaluation.subject_revision,
            ),
            previous_evaluation=previous_evaluation,
            current_evaluation=current_evaluation,
            transition_type=transition_type,
            severity=severity,
            effects=effects,
            policy_ref=policy.id if policy is not None else None,
            detected_at=detected_at,
            effective_at=effective_at or current_evaluation.evaluated_at,
            detection_mode=detection_mode,
            cause=cause,
        )
        self._condition_failures[failure.id] = failure
        self._active_condition_failure_keys[episode_key] = failure.id
        return failure

    def get_condition_failure(self, failure_id: str) -> ConditionFailure:
        failure = self._condition_failures.get(failure_id)
        if failure is None:
            raise RegistryError("CONDITION_FAILURE_NOT_FOUND", failure_id)
        return failure

    def calculate_condition_failure_impact(
        self,
        *,
        failure_id: str,
        decisions: tuple[str, ...] = (),
        authorizations: tuple[str, ...] = (),
        executions: tuple[str, ...] = (),
        controls: tuple[str, ...] = (),
        obligations: tuple[str, ...] = (),
        states: tuple[str, ...] = (),
    ) -> ConditionFailureImpact:
        self.get_condition_failure(failure_id)
        for control_id in controls:
            if (
                control_id not in self._control_definitions
                and control_id not in self._control_implementations
            ):
                raise RegistryError("CONDITION_FAILURE_IMPACT_CONTROL_UNKNOWN", control_id)
        self._condition_failure_impact_sequence += 1
        impact = ConditionFailureImpact(
            id=f"CFI-{self._condition_failure_impact_sequence:06d}",
            failure_ref=failure_id,
            decisions=decisions,
            authorizations=authorizations,
            executions=executions,
            controls=controls,
            obligations=obligations,
            states=states,
            calculated_at=datetime.now(UTC),
        )
        self._condition_failure_impacts[impact.id] = impact
        return impact

    def evaluate_constraint(
        self,
        *,
        constraint_id: str,
        subject_id: str,
    ) -> ConstraintEvaluation:
        definition = self._constraints.get(constraint_id)
        evaluated_at = datetime.now(UTC)
        if definition is None:
            proof: dict[str, Any] = {"inputs": []}
            return ConstraintEvaluation(
                constraint_id=constraint_id,
                constraint_version=None,
                subject_id=subject_id,
                subject_revision=None,
                result=ConstraintEvaluationResult.UNKNOWN,
                condition_evaluation=None,
                violation_id=None,
                findings=(
                    ConditionFinding(
                        "CONSTRAINT_DEFINITION_NOT_FOUND",
                        f"Constraint '{constraint_id}' is not registered.",
                    ),
                ),
                proof=proof,
                proof_hash=f"sha256:{specification_hash(proof)}",
                evaluated_at=evaluated_at,
            )
        try:
            subject = self.get_object(subject_id)
        except RegistryError as exc:
            proof = {
                "definition": definition.canonical_document(),
                "inputs": [],
            }
            return ConstraintEvaluation(
                constraint_id=definition.id,
                constraint_version=definition.version,
                subject_id=subject_id,
                subject_revision=None,
                result=ConstraintEvaluationResult.UNKNOWN,
                condition_evaluation=None,
                violation_id=None,
                findings=(ConditionFinding("CONSTRAINT_SUBJECT_NOT_FOUND", exc.message),),
                proof=proof,
                proof_hash=f"sha256:{specification_hash(proof)}",
                evaluated_at=evaluated_at,
            )
        findings: list[ConditionFinding] = []
        if subject.kind not in definition.subject_kinds:
            findings.append(
                ConditionFinding(
                    "CONSTRAINT_SUBJECT_KIND_INVALID",
                    f"{subject.kind} is not valid for {definition.id}.",
                )
            )
        condition_evaluation = self.evaluate_condition(
            condition_id=definition.condition_id,
            subject_id=subject.metadata.id,
        )
        result = self._constraint_result_from_condition(
            definition.requirement,
            condition_evaluation.outcome,
        )
        violation_id: str | None = None
        if findings:
            result = ConstraintEvaluationResult.UNKNOWN
        elif result is ConstraintEvaluationResult.VIOLATED:
            violation_id = self._record_constraint_violation(
                definition=definition,
                subject=subject,
                condition_evaluation=condition_evaluation,
                detected_at=evaluated_at,
            ).id
        proof = {
            "definition": definition.canonical_document(),
            "subject": {
                "id": subject.metadata.id,
                "revision": subject.metadata.revision,
                "kind": subject.kind,
            },
            "conditionEvaluation": condition_evaluation.canonical_document(),
            "violationId": violation_id,
        }
        return ConstraintEvaluation(
            constraint_id=definition.id,
            constraint_version=definition.version,
            subject_id=subject.metadata.id,
            subject_revision=subject.metadata.revision,
            result=result,
            condition_evaluation=condition_evaluation,
            violation_id=violation_id,
            findings=tuple(findings),
            proof=proof,
            proof_hash=f"sha256:{specification_hash(proof)}",
            evaluated_at=evaluated_at,
        )

    def list_constraint_violations(
        self,
        *,
        constraint_id: str | None = None,
        subject_id: str | None = None,
        state: ConstraintViolationState | None = None,
    ) -> tuple[ConstraintViolation, ...]:
        violations = sorted(self._constraint_violations.values(), key=lambda item: item.id)
        return tuple(
            violation
            for violation in violations
            if (constraint_id is None or violation.constraint_id == constraint_id)
            and (subject_id is None or violation.subject_ref.id == subject_id)
            and (state is None or violation.state is state)
        )

    def evaluate_decision(
        self,
        *,
        decision_id: str,
        resource_id: str,
        actor: ActorReference,
        context: dict[str, Any] | None = None,
        request_id: str | None = None,
        requested_action: str | None = None,
    ) -> DecisionEvaluation:
        definition = self._decisions.get(decision_id)
        evaluated_at = datetime.now(UTC)
        if definition is None:
            return self._decision_evaluation(
                decision_id=decision_id,
                decision_version=None,
                request_id=request_id,
                action="",
                resource_id=resource_id,
                resource_revision=None,
                evaluation_status=DecisionEvaluationStatus.FAILED,
                outcome="DEFER",
                effect=DecisionEffect.DEFER,
                condition_evaluations=(),
                policy_contributions=(),
                obligations=(),
                constraints=(),
                advice=(),
                findings=(
                    DecisionFinding(
                        "DECISION_DEFINITION_NOT_FOUND",
                        f"Decision '{decision_id}' is not registered.",
                    ),
                ),
                proof={"inputs": []},
                evaluated_at=evaluated_at,
            )
        try:
            resource = self.get_object(resource_id)
        except RegistryError as exc:
            return self._decision_evaluation(
                decision_id=definition.id,
                decision_version=definition.version,
                request_id=request_id,
                action=definition.action,
                resource_id=resource_id,
                resource_revision=None,
                evaluation_status=DecisionEvaluationStatus.FAILED,
                outcome="DEFER",
                effect=DecisionEffect.DEFER,
                condition_evaluations=(),
                policy_contributions=(),
                obligations=(),
                constraints=definition.constraints,
                advice=definition.advice,
                findings=(
                    DecisionFinding(
                        "DECISION_RESOURCE_NOT_FOUND",
                        exc.message,
                    ),
                ),
                proof={"definition": definition.canonical_document(), "inputs": []},
                evaluated_at=evaluated_at,
            )
        findings: list[DecisionFinding] = []
        if definition.resource_kinds and resource.kind not in definition.resource_kinds:
            findings.append(
                DecisionFinding(
                    "DECISION_RESOURCE_KIND_INVALID",
                    f"{resource.kind} is not valid for {definition.id}.",
                )
            )
        if requested_action is not None and requested_action != definition.action:
            findings.append(
                DecisionFinding(
                    "DECISION_ACTION_MISMATCH",
                    f"Requested action '{requested_action}' does not match "
                    f"decision action '{definition.action}'.",
                )
            )
        condition_evaluations = tuple(
            self.evaluate_condition(condition_id=condition_id, subject_id=resource.metadata.id)
            for condition_id in definition.condition_ids
        )
        condition_effect = self._decision_effect_from_conditions(
            definition,
            condition_evaluations,
            findings,
        )
        policy_contributions = self._policy_contributions_for_decision(
            definition,
            resource,
        )
        policy_effect = self._decision_effect_from_policies(
            definition,
            policy_contributions,
        )
        effect = self._combine_decision_effects(
            definition.combining_algorithm,
            tuple(item for item in (condition_effect, policy_effect) if item is not None),
        )
        obligations = tuple(
            obligation
            for contribution in policy_contributions
            for obligation in contribution.obligations
        )
        proof = {
            "definition": definition.canonical_document(),
            "request": {
                "id": request_id,
                "requestedAction": requested_action,
            },
            "actor": actor.id,
            "context": context or {},
            "conditions": [
                evaluation.canonical_document()
                for evaluation in condition_evaluations
            ],
            "policies": [
                contribution.canonical_document()
                for contribution in policy_contributions
            ],
        }
        if any(
            finding.code
            in {"DECISION_RESOURCE_KIND_INVALID", "DECISION_ACTION_MISMATCH"}
            for finding in findings
        ):
            effect = DecisionEffect.DEFER
        return self._decision_evaluation(
            decision_id=definition.id,
            decision_version=definition.version,
            request_id=request_id,
            action=definition.action,
            resource_id=resource.metadata.id,
            resource_revision=resource.metadata.revision,
            evaluation_status=DecisionEvaluationStatus.COMPLETED,
            outcome=self._outcome_from_decision_effect(effect),
            effect=effect,
            condition_evaluations=condition_evaluations,
            policy_contributions=policy_contributions,
            obligations=obligations,
            constraints=definition.constraints,
            advice=definition.advice,
            findings=tuple(findings),
            proof=proof,
            evaluated_at=evaluated_at,
            valid_until=(
                evaluated_at + timedelta(seconds=definition.validity_seconds)
                if definition.validity_seconds is not None
                else None
            ),
        )

    def evaluate_state_transition(
        self,
        *,
        object_id: str,
        transition_name: str,
        expected_revision: int | None = None,
        action_id: str | None = None,
    ) -> StateTransitionDecision:
        current = self.get_object(object_id)
        state_machine = self._state_machine_for_kind(current.kind)
        current_state = current.lifecycle.state
        if state_machine is None:
            return StateTransitionDecision(
                permitted=False,
                state_machine_id=None,
                transition=transition_name,
                current_state=current_state,
                target_state=None,
                reasons=(
                    StateTransitionFinding(
                        "STATE_MACHINE_NOT_FOUND",
                        f"No state machine is registered for kind '{current.kind}'.",
                    ),
                ),
            )
        if current_state not in {state.name for state in state_machine.states}:
            return StateTransitionDecision(
                permitted=False,
                state_machine_id=state_machine.id,
                transition=transition_name,
                current_state=current_state,
                target_state=None,
                reasons=(
                    StateTransitionFinding(
                        "STATE_UNKNOWN",
                        f"Current state '{current_state}' is not defined.",
                    ),
                ),
            )
        if expected_revision is not None and current.metadata.revision != expected_revision:
            return StateTransitionDecision(
                permitted=False,
                state_machine_id=state_machine.id,
                transition=transition_name,
                current_state=current_state,
                target_state=None,
                reasons=(
                    StateTransitionFinding(
                        "STATE_VERSION_CONFLICT",
                        "Expected revision "
                        f"{expected_revision}, found {current.metadata.revision}.",
                    ),
                ),
            )
        transition = self._find_transition(state_machine, transition_name, current_state)
        if transition is None:
            terminal_code = (
                "TERMINAL_STATE_REACHED"
                if current_state in state_machine.terminal_states
                else "TRANSITION_NOT_FOUND"
            )
            return StateTransitionDecision(
                permitted=False,
                state_machine_id=state_machine.id,
                transition=transition_name,
                current_state=current_state,
                target_state=None,
                reasons=(
                    StateTransitionFinding(
                        terminal_code,
                        f"Transition '{transition_name}' is not allowed from '{current_state}'.",
                    ),
                ),
            )
        if action_id is not None and transition.action_id != action_id:
            return StateTransitionDecision(
                permitted=False,
                state_machine_id=state_machine.id,
                transition=transition_name,
                current_state=current_state,
                target_state=transition.target_state,
                reasons=(
                    StateTransitionFinding(
                        "TRANSITION_ACTION_MISMATCH",
                        f"Transition '{transition_name}' is not bound to action '{action_id}'.",
                    ),
                ),
            )
        return StateTransitionDecision(
            permitted=True,
            state_machine_id=state_machine.id,
            transition=transition.name,
            current_state=current_state,
            target_state=transition.target_state,
            reasons=(),
        )

    def transition_object(
        self,
        *,
        object_id: str,
        expected_revision: int,
        transition_name: str,
        actor: ActorReference,
        action_id: str | None = None,
    ) -> ObjectEnvelope:
        decision = self.evaluate_state_transition(
            object_id=object_id,
            transition_name=transition_name,
            expected_revision=expected_revision,
            action_id=action_id,
        )
        if not decision.permitted:
            first_reason = decision.reasons[0]
            raise RegistryError(first_reason.code, first_reason.message)
        current = self.get_object(object_id)
        if decision.target_state is None:
            raise RegistryError("TARGET_STATE_INVALID", transition_name)
        state_machine = self._state_machine_for_kind(current.kind)
        if state_machine is None:
            raise RegistryError("STATE_MACHINE_NOT_FOUND", current.kind)
        transition = self._find_transition(state_machine, transition_name, current.lifecycle.state)
        if transition is None:
            raise RegistryError("TRANSITION_NOT_FOUND", transition_name)
        occurred_at = datetime.now(UTC)
        updated = self._object_envelope(
            kind=current.kind,
            object_id=current.metadata.id,
            namespace=current.metadata.namespace,
            revision=current.metadata.revision + 1,
            spec=current.spec,
            actor=actor,
            created_at=current.metadata.created_at,
            updated_at=occurred_at,
            lifecycle_state=decision.target_state,
            relationships=current.relationships,
        )
        self._objects[object_id].append(updated)
        self._record_transition_evidence(
            current=current,
            updated=updated,
            state_machine=state_machine,
            transition=transition,
            decision=decision,
            actor=actor,
            action_id=action_id,
            occurred_at=occurred_at,
        )
        return updated

    def list_state_transition_events(
        self,
        object_id: str | None = None,
    ) -> tuple[StateTransitionEvent, ...]:
        if object_id is None:
            return tuple(self._transition_events)
        return tuple(event for event in self._transition_events if event.object_id == object_id)

    def list_state_transition_audit_records(
        self,
        object_id: str | None = None,
    ) -> tuple[StateTransitionAuditRecord, ...]:
        if object_id is None:
            return tuple(self._transition_audit_records)
        return tuple(
            record for record in self._transition_audit_records if record.object_id == object_id
        )

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
        self._require_valid_spec(current.kind, spec)
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
            relationships=current.relationships,
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

    def validate_spec(self, kind: str, spec: dict[str, Any]) -> ValidationResult:
        type_definition = self._types.get(kind)
        if type_definition is None:
            return ValidationResult(
                valid=False,
                type_ref=kind,
                schema_version="unknown",
                errors=(
                    ValidationFinding(
                        code="TYPE_NOT_REGISTERED",
                        path="kind",
                        message=f"Type '{kind}' is not registered.",
                        expected="registered TypeDefinition",
                        actual=kind,
                    ),
                ),
                warnings=(),
                validated_at=datetime.now(UTC),
            )
        errors: list[ValidationFinding] = []
        warnings: list[ValidationFinding] = []
        known_properties = set(type_definition.properties)
        unknown_properties = sorted(set(spec) - known_properties)
        if type_definition.additional_properties is AdditionalPropertiesPolicy.FORBID:
            errors.extend(
                ValidationFinding(
                    code="PROPERTY_UNKNOWN",
                    path=f"spec.{name}",
                    message=f"Property '{name}' is not declared by type '{kind}'.",
                    expected="declared property",
                    actual=name,
                )
                for name in unknown_properties
            )
        elif type_definition.additional_properties is AdditionalPropertiesPolicy.WARN:
            warnings.extend(
                ValidationFinding(
                    code="PROPERTY_UNKNOWN",
                    path=f"spec.{name}",
                    message=f"Property '{name}' is not declared by type '{kind}'.",
                    expected="declared property",
                    actual=name,
                )
                for name in unknown_properties
            )
        for name, property_definition in type_definition.properties.items():
            if name not in spec:
                if property_definition.required and property_definition.default is None:
                    errors.append(
                        ValidationFinding(
                            code="PROPERTY_REQUIRED",
                            path=f"spec.{name}",
                            message=f"Required property '{name}' is missing.",
                            expected=property_definition.type,
                            actual="absent",
                        )
                    )
                continue
            value = spec[name]
            if value is None:
                if not property_definition.nullable:
                    errors.append(
                        ValidationFinding(
                            code="PROPERTY_TYPE_INVALID",
                            path=f"spec.{name}",
                            message=f"Property '{name}' cannot be null.",
                            expected=property_definition.type,
                            actual="null",
                        )
                    )
                continue
            try:
                _validate_value_type(name, value, property_definition)
            except RegistryError as exc:
                errors.append(
                    ValidationFinding(
                        code=exc.code,
                        path=f"spec.{name}",
                        message=_validation_message(name, value, property_definition, exc),
                        expected=_expected_type(property_definition),
                        actual=_actual_type(value),
                    )
                )
                continue
            if property_definition.type == "reference":
                reference = _reference_from_value(name, value)
                resolution = self.resolve_reference(
                    reference,
                    target_kinds=property_definition.target_kinds,
                )
                if resolution.status is not ResolutionStatus.RESOLVED:
                    errors.append(
                        ValidationFinding(
                            code=resolution.status.value,
                            path=f"spec.{name}",
                            message=f"Reference property '{name}' could not be resolved.",
                            expected=property_definition.target_kinds or "resolvable reference",
                            actual=reference.id,
                        )
                    )
        return ValidationResult(
            valid=not errors,
            type_ref=kind,
            schema_version=type_definition.schema_version,
            errors=tuple(errors),
            warnings=tuple(warnings),
            validated_at=datetime.now(UTC),
        )

    def _require_valid_spec(self, kind: str, spec: dict[str, Any]) -> None:
        result = self.validate_spec(kind, spec)
        if not result.valid:
            first_error = result.errors[0]
            raise RegistryError(first_error.code, first_error.message)

    def _require_valid_initial_lifecycle(self, kind: str, lifecycle_state: str) -> None:
        state_machine = self._state_machine_for_kind(kind)
        if state_machine is None:
            return
        if lifecycle_state != state_machine.initial_state:
            raise RegistryError(
                "INITIAL_STATE_INVALID",
                f"expected initial state '{state_machine.initial_state}', "
                f"received '{lifecycle_state}'",
            )

    def _require_active_namespace(self, namespace: str) -> None:
        definition = self._namespaces.get(namespace)
        if definition is None:
            raise RegistryError("NAMESPACE_NOT_FOUND", namespace)
        if not definition.active:
            raise RegistryError("NAMESPACE_INACTIVE", namespace)

    def _state_machine_for_kind(self, kind: str) -> StateMachineDefinition | None:
        type_definition = self._types.get(kind)
        if type_definition is None or type_definition.lifecycle is None:
            return None
        return self._state_machines.get(type_definition.lifecycle.id)

    def _require_registered_condition(self, condition_id: str, error_code: str) -> None:
        if condition_id not in self._conditions:
            raise RegistryError(error_code, condition_id)

    @staticmethod
    def _require_unique_task_outputs(outputs: tuple[TaskOutputDefinition, ...]) -> None:
        output_ids = tuple(output.id for output in outputs)
        if len(set(output_ids)) != len(output_ids):
            raise RegistryError("TASK_OUTPUT_SCHEMA_INVALID", "duplicate output id")
        for output in outputs:
            if not output.id:
                raise RegistryError("TASK_OUTPUT_SCHEMA_INVALID", "output id is required")

    def _require_task_dependencies_resolvable(
        self,
        dependencies: tuple[TaskDependency, ...],
    ) -> None:
        for dependency in dependencies:
            if dependency.task_id not in self._tasks:
                raise RegistryError("TASK_DEPENDENCY_INVALID", dependency.task_id)
            if dependency.dependency_type is TaskDependencyType.REQUIRES_OUTPUT:
                dependency_task = self._tasks[dependency.task_id]
                if dependency.output_id is None or dependency.output_id not in {
                    output.id for output in dependency_task.outputs
                }:
                    raise RegistryError("TASK_OUTPUT_SCHEMA_INVALID", dependency.task_id)

    def _require_task_dependencies_satisfied(self, task: TaskInstance) -> None:
        for dependency in task.dependencies:
            dependency_task = self.get_task(dependency.task_id)
            if dependency.dependency_type is TaskDependencyType.START_AFTER:
                if dependency_task.state is TaskLifecycleState.CREATED:
                    raise RegistryError("TASK_DEPENDENCY_UNSATISFIED", dependency.task_id)
                continue
            if dependency.dependency_type in {
                TaskDependencyType.COMPLETE_AFTER,
                TaskDependencyType.REQUIRES_SUCCESS,
            }:
                if dependency_task.state is not TaskLifecycleState.COMPLETED:
                    raise RegistryError("TASK_DEPENDENCY_UNSATISFIED", dependency.task_id)
                continue
            if dependency.dependency_type is TaskDependencyType.REQUIRES_OUTPUT:
                if not any(
                    value.output_id == dependency.output_id
                    for value in dependency_task.output_values
                ):
                    raise RegistryError("TASK_DEPENDENCY_UNSATISFIED", dependency.task_id)
                continue
            if dependency.dependency_type is TaskDependencyType.REQUIRES_EVIDENCE:
                raise RegistryError("TASK_DEPENDENCY_UNSATISFIED", dependency.task_id)

    def _require_no_task_dependency_cycle(
        self,
        task_ids: tuple[str, ...] | None = None,
    ) -> None:
        scoped = set(task_ids or self._tasks.keys())
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visited:
                return
            if task_id in visiting:
                raise RegistryError("TASK_DEPENDENCY_CYCLE", task_id)
            visiting.add(task_id)
            task = self._tasks[task_id]
            for dependency in task.dependencies:
                if dependency.task_id in scoped:
                    visit(dependency.task_id)
            visiting.remove(task_id)
            visited.add(task_id)

        for task_id in sorted(scoped):
            if task_id in self._tasks:
                visit(task_id)

    def _require_plan_tasks(self, goal_ref: str, task_ids: tuple[str, ...]) -> None:
        if not task_ids:
            raise RegistryError("PLAN_TASK_INVALID", "plan requires at least one task")
        if len(set(task_ids)) != len(task_ids):
            raise RegistryError("PLAN_TASK_INVALID", "duplicate task id")
        for task_id in task_ids:
            task = self.get_task(task_id)
            if task.goal_ref != goal_ref:
                raise RegistryError("PLAN_SCOPE_VIOLATION", task_id)

    @staticmethod
    def _constraint_result_from_condition(
        requirement: ConstraintRequirement,
        outcome: ConditionOutcome,
    ) -> ConstraintEvaluationResult:
        if outcome is ConditionOutcome.UNKNOWN:
            return ConstraintEvaluationResult.UNKNOWN
        if outcome is ConditionOutcome.EXEMPTED:
            return ConstraintEvaluationResult.EXEMPTED
        if requirement in {
            ConstraintRequirement.MUST_HOLD,
            ConstraintRequirement.MUST_REMAIN,
            ConstraintRequirement.MUST_BECOME,
        }:
            return (
                ConstraintEvaluationResult.SATISFIED
                if outcome is ConditionOutcome.SATISFIED
                else ConstraintEvaluationResult.VIOLATED
            )
        if requirement in {
            ConstraintRequirement.MUST_NOT_HOLD,
            ConstraintRequirement.MUST_CEASE,
        }:
            return (
                ConstraintEvaluationResult.VIOLATED
                if outcome is ConditionOutcome.SATISFIED
                else ConstraintEvaluationResult.SATISFIED
            )
        return ConstraintEvaluationResult.UNKNOWN

    def _record_constraint_violation(
        self,
        *,
        definition: ConstraintDefinition,
        subject: ObjectEnvelope,
        condition_evaluation: ConditionEvaluation,
        detected_at: datetime,
    ) -> ConstraintViolation:
        violation_key = self._constraint_violation_key(
            definition=definition,
            subject_id=subject.metadata.id,
        )
        existing_id = self._constraint_violation_keys.get(violation_key)
        if existing_id is not None:
            return self._constraint_violations[existing_id]
        self._constraint_violation_sequence += 1
        violation_id = f"VIO-{self._constraint_violation_sequence:06d}"
        violation = ConstraintViolation(
            id=violation_id,
            violation_key=violation_key,
            constraint_id=definition.id,
            constraint_version=definition.version,
            subject_ref=ObjectReference(
                subject.metadata.id,
                revision=subject.metadata.revision,
            ),
            condition_evaluation=condition_evaluation,
            severity=definition.severity,
            state=ConstraintViolationState.OPEN,
            detected_at=detected_at,
        )
        self._constraint_violations[violation_id] = violation
        self._constraint_violation_keys[violation_key] = violation_id
        return violation

    @staticmethod
    def _constraint_violation_key(
        *,
        definition: ConstraintDefinition,
        subject_id: str,
    ) -> str:
        key_document = {
            "constraint": {
                "id": definition.id,
                "version": definition.version,
            },
            "subjectId": subject_id,
        }
        return f"sha256:{specification_hash(key_document)}"

    def _preemption_structural_denial(
        self,
        *,
        request: PreemptionRequest,
        definition: PreemptionDefinition,
        target: ReservationInstance,
    ) -> str | None:
        requester_priority = self._priorities.get(request.priority_id)
        minimum_priority = self._priorities.get(definition.minimum_priority_id)
        if requester_priority is None:
            return "PREEMPTION_REQUESTER_PRIORITY_NOT_FOUND"
        if requester_priority.status != "ACTIVE":
            return "PREEMPTION_REQUESTER_PRIORITY_INACTIVE"
        if minimum_priority is None:
            return "PREEMPTION_MINIMUM_PRIORITY_UNKNOWN"
        if target.state is not request.expected_target_state:
            return "PREEMPTION_TARGET_STATE_INVALID"
        if target.state is not ReservationLifecycleState.ACTIVE:
            return "PREEMPTION_TARGET_NOT_ACTIVE"
        if target.resource_ref != request.requested_resource_ref:
            return "PREEMPTION_RESOURCE_MISMATCH"
        if target.resource_type not in definition.resource_types:
            return "PREEMPTION_RESOURCE_TYPE_NOT_APPLICABLE"
        if target.preemption_mode not in definition.target_modes:
            return "PREEMPTION_TARGET_NOT_PREEMPTIBLE"
        if requester_priority.rank < minimum_priority.rank:
            return "PREEMPTION_PRIORITY_INSUFFICIENT"
        if requester_priority.rank - target.priority_rank < definition.minimum_priority_delta:
            return "PREEMPTION_PRIORITY_DELTA_INSUFFICIENT"
        return None

    def _evaluate_preemption_conditions(
        self,
        *,
        definition: PreemptionDefinition,
        target: ReservationInstance,
    ) -> tuple[ConditionEvaluation, ...]:
        return tuple(
            self.evaluate_condition(
                condition_id=condition_id,
                subject_id=target.resource_ref,
            )
            for condition_id in definition.condition_ids
        )

    @staticmethod
    def _preemption_condition_denial(
        condition_evaluations: tuple[ConditionEvaluation, ...],
    ) -> str | None:
        if any(
            evaluation.outcome is ConditionOutcome.UNKNOWN
            for evaluation in condition_evaluations
        ):
            return "PREEMPTION_CONDITION_UNKNOWN"
        if any(
            evaluation.outcome is not ConditionOutcome.SATISFIED
            for evaluation in condition_evaluations
        ):
            return "PREEMPTION_CONDITION_NOT_SATISFIED"
        return None

    def _create_replacement_reservation(
        self,
        *,
        request: PreemptionRequest,
        target: ReservationInstance,
    ) -> ReservationInstance:
        priority = self._priorities[request.priority_id]
        self._reservation_sequence += 1
        replacement = ReservationInstance(
            id=f"RSV-{self._reservation_sequence:06d}",
            definition_id=target.definition_id,
            definition_version=target.definition_version,
            holder_ref=request.replacement_holder_ref,
            resource_ref=target.resource_ref,
            resource_type=target.resource_type,
            priority_id=priority.id,
            priority_rank=priority.rank,
            preemption_mode=target.preemption_mode,
            state=ReservationLifecycleState.ACTIVE,
            quantity=target.quantity,
            created_at=datetime.now(UTC),
            expires_at=target.expires_at,
        )
        self._reservations[replacement.id] = replacement
        return replacement

    def _preemption_decision(
        self,
        *,
        request: PreemptionRequest,
        definition: PreemptionDefinition | None,
        effect: PreemptionEffect,
        reason_code: str,
        condition_evaluations: tuple[ConditionEvaluation, ...],
        replacement: ReservationInstance | None,
        decided_at: datetime,
        target: ReservationInstance | None = None,
    ) -> PreemptionDecision:
        self._preemption_decision_sequence += 1
        proof = {
            "request": request.canonical_document(),
            "definition": (
                definition.canonical_document() if definition is not None else None
            ),
            "targetBefore": (
                target.canonical_document() if target is not None else None
            ),
            "replacement": (
                replacement.canonical_document() if replacement is not None else None
            ),
            "conditions": [
                evaluation.canonical_document()
                for evaluation in condition_evaluations
            ],
            "effect": effect.value,
            "reason": {"code": reason_code},
        }
        decision = PreemptionDecision(
            id=f"PDEC-{self._preemption_decision_sequence:06d}",
            request_id=request.id,
            definition_id=definition.id if definition is not None else None,
            definition_version=definition.version if definition is not None else None,
            effect=effect,
            target_reservation_id=request.target_reservation_id,
            replacement_reservation_id=(
                replacement.id if replacement is not None else None
            ),
            reason_code=reason_code,
            condition_evaluations=condition_evaluations,
            proof=proof,
            proof_hash=f"sha256:{specification_hash(proof)}",
            decided_at=decided_at,
        )
        self._preemption_decisions[decision.id] = decision
        return decision

    def _activate_obligation_from_decision(
        self,
        definition: ObligationDefinition,
        decision: DecisionEvaluation,
        evaluated_at: datetime,
    ) -> ObligationActivation:
        if definition.trigger.source is not ObligationTriggerSource.POLICY_DECISION:
            return ObligationActivation(
                definition_id=definition.id,
                definition_version=definition.version,
                outcome=ObligationActivationOutcome.NOT_APPLICABLE,
                instance_id=None,
                reason_code="OBLIGATION_TRIGGER_SOURCE_UNSUPPORTED",
                evaluated_at=evaluated_at,
            )
        if definition.trigger.decision_effect is not decision.effect:
            return ObligationActivation(
                definition_id=definition.id,
                definition_version=definition.version,
                outcome=ObligationActivationOutcome.NOT_APPLICABLE,
                instance_id=None,
                reason_code="OBLIGATION_TRIGGER_EFFECT_NOT_MATCHED",
                evaluated_at=evaluated_at,
            )
        if definition.trigger.policy_id is not None and not any(
            contribution.policy_id == definition.trigger.policy_id
            for contribution in decision.policy_contributions
        ):
            return ObligationActivation(
                definition_id=definition.id,
                definition_version=definition.version,
                outcome=ObligationActivationOutcome.NOT_APPLICABLE,
                instance_id=None,
                reason_code="OBLIGATION_TRIGGER_POLICY_NOT_MATCHED",
                evaluated_at=evaluated_at,
            )
        condition_evaluation: ConditionEvaluation | None = None
        if definition.applicability_condition_id is not None:
            condition_evaluation = self.evaluate_condition(
                condition_id=definition.applicability_condition_id,
                subject_id=decision.resource_id,
            )
            if condition_evaluation.outcome is ConditionOutcome.UNKNOWN:
                return ObligationActivation(
                    definition_id=definition.id,
                    definition_version=definition.version,
                    outcome=ObligationActivationOutcome.UNKNOWN,
                    instance_id=None,
                    reason_code="OBLIGATION_APPLICABILITY_UNKNOWN",
                    evaluated_at=evaluated_at,
                    condition_evaluation=condition_evaluation,
                )
            if condition_evaluation.outcome is not ConditionOutcome.SATISFIED:
                return ObligationActivation(
                    definition_id=definition.id,
                    definition_version=definition.version,
                    outcome=ObligationActivationOutcome.NOT_APPLICABLE,
                    instance_id=None,
                    reason_code="OBLIGATION_APPLICABILITY_NOT_SATISFIED",
                    evaluated_at=evaluated_at,
                    condition_evaluation=condition_evaluation,
                )
        if definition.subject.binding is not ObligationSubjectBinding.DECISION_RESOURCE:
            return ObligationActivation(
                definition_id=definition.id,
                definition_version=definition.version,
                outcome=ObligationActivationOutcome.UNKNOWN,
                instance_id=None,
                reason_code="OBLIGATION_SUBJECT_BINDING_UNSUPPORTED",
                evaluated_at=evaluated_at,
                condition_evaluation=condition_evaluation,
            )
        source_decision_ref = decision.request_id or decision.proof_hash
        activation_key = self._obligation_activation_key(
            definition=definition,
            source_decision_ref=source_decision_ref,
            subject_id=decision.resource_id,
        )
        existing_id = self._obligation_activation_keys.get(activation_key)
        if existing_id is not None:
            return ObligationActivation(
                definition_id=definition.id,
                definition_version=definition.version,
                outcome=ObligationActivationOutcome.ACTIVATED,
                instance_id=existing_id,
                reason_code="OBLIGATION_ALREADY_ACTIVATED",
                evaluated_at=evaluated_at,
                condition_evaluation=condition_evaluation,
            )
        due_at = (
            evaluated_at + _parse_duration(definition.timing.completion_within)
            if definition.timing.completion_within is not None
            else None
        )
        self._obligation_sequence += 1
        instance_id = f"OBL-{self._obligation_sequence:06d}"
        instance = ObligationInstance(
            id=instance_id,
            activation_key=activation_key,
            definition_id=definition.id,
            definition_version=definition.version,
            source_decision_ref=source_decision_ref,
            subject_ref=ObjectReference(
                decision.resource_id,
                revision=decision.resource_revision,
            ),
            assignee_ref=definition.responsibility.assignee_ref,
            state=ObligationLifecycleState.ACTIVE,
            activated_at=evaluated_at,
            due_at=due_at,
        )
        self._obligation_instances[instance_id] = instance
        self._obligation_activation_keys[activation_key] = instance_id
        return ObligationActivation(
            definition_id=definition.id,
            definition_version=definition.version,
            outcome=ObligationActivationOutcome.ACTIVATED,
            instance_id=instance_id,
            reason_code="OBLIGATION_ACTIVATED",
            evaluated_at=evaluated_at,
            condition_evaluation=condition_evaluation,
        )

    @staticmethod
    def _obligation_activation_key(
        *,
        definition: ObligationDefinition,
        source_decision_ref: str,
        subject_id: str,
    ) -> str:
        key_document = {
            'definition': {
                'id': definition.id,
                'version': definition.version,
            },
            'sourceDecisionRef': source_decision_ref,
            'subjectId': subject_id,
        }
        return f"sha256:{specification_hash(key_document)}"

    def _require_valid_condition_clause(
        self,
        definition: SemanticConditionDefinition,
        clause: SemanticConditionClause,
    ) -> None:
        if clause.clause_type is ConditionClauseType.OBJECT_KIND_IS:
            if not isinstance(clause.expected, str):
                raise RegistryError("CONDITION_EXPECTED_VALUE_REQUIRED", definition.id)
            if clause.expected not in self._types:
                raise RegistryError("CONDITION_EXPECTED_KIND_UNKNOWN", clause.expected)
            return
        if clause.clause_type is ConditionClauseType.LIFECYCLE_STATE_IS:
            if not isinstance(clause.expected, str):
                raise RegistryError("CONDITION_EXPECTED_VALUE_REQUIRED", definition.id)
            return
        if clause.clause_type is ConditionClauseType.SPEC_EQUALS:
            if not clause.path:
                raise RegistryError("CONDITION_PATH_REQUIRED", definition.id)
            return
        if clause.clause_type in {
            ConditionClauseType.RELATIONSHIP_EXISTS,
            ConditionClauseType.RELATIONSHIP_COUNT,
        }:
            if clause.relationship_type_id is None:
                raise RegistryError("CONDITION_RELATIONSHIP_TYPE_REQUIRED", definition.id)
            relationship_type = self._relationship_types.get(clause.relationship_type_id)
            if relationship_type is None:
                raise RegistryError(
                    "CONDITION_RELATIONSHIP_TYPE_UNKNOWN",
                    clause.relationship_type_id,
                )
            if not set(definition.subject_kinds).intersection(relationship_type.source_kinds):
                raise RegistryError(
                    "CONDITION_RELATIONSHIP_SOURCE_KIND_INVALID",
                    clause.relationship_type_id,
                )
            if clause.target_kind is not None and clause.target_kind not in self._types:
                raise RegistryError("CONDITION_TARGET_KIND_UNKNOWN", clause.target_kind)
            if clause.clause_type is ConditionClauseType.RELATIONSHIP_COUNT:
                if clause.min_count is None and clause.max_count is None:
                    raise RegistryError("CONDITION_COUNT_BOUND_REQUIRED", definition.id)
                if clause.min_count is not None and clause.min_count < 0:
                    raise RegistryError("CONDITION_COUNT_BOUND_INVALID", definition.id)
                if clause.max_count is not None and clause.max_count < 0:
                    raise RegistryError("CONDITION_COUNT_BOUND_INVALID", definition.id)
                if (
                    clause.min_count is not None
                    and clause.max_count is not None
                    and clause.min_count > clause.max_count
                ):
                    raise RegistryError("CONDITION_COUNT_BOUND_INVALID", definition.id)
            return
        raise RegistryError("CONDITION_CLAUSE_TYPE_UNKNOWN", clause.clause_type.value)

    def _condition_dependency_creates_cycle(
        self,
        candidate: ConditionDependency,
    ) -> bool:
        edges = {
            dependency.dependent_condition_id: dependency.dependency_condition_id
            for dependency in self._condition_dependencies.values()
        }
        edges[candidate.dependent_condition_id] = candidate.dependency_condition_id
        current = candidate.dependency_condition_id
        visited: set[str] = set()
        while current in edges:
            if current == candidate.dependent_condition_id:
                return True
            if current in visited:
                return True
            visited.add(current)
            current = edges[current]
        return False

    def _resolve_condition_failure_policy(
        self,
        previous_evaluation: ConditionEvaluation,
        current_evaluation: ConditionEvaluation,
        policy_id: str | None,
    ) -> ConditionFailurePolicy | None:
        policies: tuple[ConditionFailurePolicy, ...]
        if policy_id is not None:
            policy = self._condition_failure_policies.get(policy_id)
            if policy is None:
                raise RegistryError("CONDITION_FAILURE_POLICY_NOT_FOUND", policy_id)
            policies = (policy,)
        else:
            policies = tuple(
                policy
                for policy in sorted(
                    self._condition_failure_policies.values(),
                    key=lambda item: item.id,
                )
                if previous_evaluation.condition_id in policy.condition_ids
            )
        for policy in policies:
            if (
                previous_evaluation.outcome in policy.transitions_from
                and current_evaluation.outcome in policy.transitions_to
            ):
                return policy
        if policy_id is not None:
            raise RegistryError("CONDITION_FAILURE_POLICY_NOT_APPLICABLE", policy_id)
        return None

    @staticmethod
    def _condition_failure_episode_key(
        previous_evaluation: ConditionEvaluation,
        current_evaluation: ConditionEvaluation,
    ) -> str:
        document = {
            "conditionId": current_evaluation.condition_id,
            "subjectId": current_evaluation.subject_id,
            "subjectRevision": current_evaluation.subject_revision,
            "from": previous_evaluation.outcome.value,
            "to": current_evaluation.outcome.value,
        }
        return f"sha256:{specification_hash(document)}"

    def _evaluate_condition_clause(
        self,
        subject: ObjectEnvelope,
        clause: SemanticConditionClause,
    ) -> tuple[ConditionFinding | None, dict[str, Any]]:
        clause_document = clause.canonical_document()
        if clause.clause_type is ConditionClauseType.OBJECT_KIND_IS:
            proof = {
                "clause": clause_document,
                "actual": subject.kind,
                "satisfied": subject.kind == clause.expected,
            }
            if proof["satisfied"]:
                return None, proof
            return (
                ConditionFinding(
                    "CONDITION_OBJECT_KIND_NOT_SATISFIED",
                    f"Expected kind {clause.expected}, found {subject.kind}.",
                    clause.clause_type.value,
                ),
                proof,
            )
        if clause.clause_type is ConditionClauseType.LIFECYCLE_STATE_IS:
            proof = {
                "clause": clause_document,
                "actual": subject.lifecycle.state,
                "satisfied": subject.lifecycle.state == clause.expected,
            }
            if proof["satisfied"]:
                return None, proof
            return (
                ConditionFinding(
                    "CONDITION_LIFECYCLE_STATE_NOT_SATISFIED",
                    f"Expected lifecycle {clause.expected}, found {subject.lifecycle.state}.",
                    clause.clause_type.value,
                ),
                proof,
            )
        if clause.clause_type is ConditionClauseType.SPEC_EQUALS:
            actual = _value_at_path(subject.spec, clause.path or "")
            proof = {
                "clause": clause_document,
                "actual": actual,
                "satisfied": actual == clause.expected,
            }
            if actual is _MISSING:
                proof["actual"] = None
                return (
                    ConditionFinding(
                        "CONDITION_INPUT_UNKNOWN",
                        f"Spec path '{clause.path}' is not present.",
                        clause.clause_type.value,
                    ),
                    proof,
                )
            if proof["satisfied"]:
                return None, proof
            return (
                ConditionFinding(
                    "CONDITION_SPEC_NOT_SATISFIED",
                    f"Expected spec.{clause.path}={clause.expected!r}, found {actual!r}.",
                    clause.clause_type.value,
                ),
                proof,
            )
        if clause.clause_type in {
            ConditionClauseType.RELATIONSHIP_EXISTS,
            ConditionClauseType.RELATIONSHIP_COUNT,
        }:
            matches = self._matching_relationships(subject, clause)
            min_count = clause.min_count
            max_count = clause.max_count
            if clause.clause_type is ConditionClauseType.RELATIONSHIP_EXISTS:
                min_count = 1
            count = len(matches)
            min_satisfied = min_count is None or count >= min_count
            max_satisfied = max_count is None or count <= max_count
            proof = {
                "clause": clause_document,
                "count": count,
                "relationships": matches,
                "satisfied": min_satisfied and max_satisfied,
            }
            if proof["satisfied"]:
                return None, proof
            return (
                ConditionFinding(
                    "CONDITION_RELATIONSHIP_NOT_SATISFIED",
                    f"Relationship count {count} does not satisfy bounds.",
                    clause.clause_type.value,
                ),
                proof,
            )
        return (
            ConditionFinding(
                "CONDITION_CLAUSE_UNKNOWN",
                f"Clause type '{clause.clause_type.value}' is not evaluable.",
                clause.clause_type.value,
            ),
            {"clause": clause_document, "satisfied": False},
        )

    def _matching_relationships(
        self,
        subject: ObjectEnvelope,
        clause: SemanticConditionClause,
    ) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        for relationship in subject.relationships:
            if relationship["type"]["$ref"]["id"] != clause.relationship_type_id:
                continue
            target_ref = relationship["target"]["$ref"]["id"]
            if clause.target_id is not None and target_ref != clause.target_id:
                continue
            if clause.target_kind is not None:
                target_resolution = self.resolve_reference(ObjectReference(target_ref))
                if target_resolution.status is not ResolutionStatus.RESOLVED:
                    continue
                if (
                    target_resolution.resolved is None
                    or target_resolution.resolved.kind != clause.target_kind
                ):
                    continue
            matches.append(
                {
                    "id": relationship["id"],
                    "type": relationship["type"]["$ref"]["id"],
                    "target": target_ref,
                    "lifecycle": relationship.get("lifecycle", {}).get("state"),
                }
            )
        return matches

    @staticmethod
    def _condition_evaluation(
        *,
        condition_id: str,
        condition_version: str | None,
        subject_id: str,
        subject_revision: int | None,
        outcome: ConditionOutcome,
        findings: tuple[ConditionFinding, ...],
        proof: dict[str, Any],
        evaluated_at: datetime,
    ) -> ConditionEvaluation:
        proof_hash = f"sha256:{specification_hash(proof)}"
        return ConditionEvaluation(
            condition_id=condition_id,
            condition_version=condition_version,
            subject_id=subject_id,
            subject_revision=subject_revision,
            outcome=outcome,
            findings=findings,
            proof=proof,
            proof_hash=proof_hash,
            evaluated_at=evaluated_at,
        )

    def _decision_effect_from_conditions(
        self,
        definition: DecisionDefinition,
        condition_evaluations: tuple[ConditionEvaluation, ...],
        findings: list[DecisionFinding],
    ) -> DecisionEffect | None:
        if not condition_evaluations:
            return None
        outcomes = tuple(evaluation.outcome for evaluation in condition_evaluations)
        if ConditionOutcome.UNKNOWN in outcomes:
            findings.append(
                DecisionFinding(
                    "DECISION_CONDITION_UNKNOWN",
                    "At least one required condition evaluated to UNKNOWN.",
                )
            )
            return definition.unknown_condition_effect
        if ConditionOutcome.NOT_SATISFIED in outcomes:
            findings.append(
                DecisionFinding(
                    "DECISION_CONDITION_UNSATISFIED",
                    "At least one required condition evaluated to NOT_SATISFIED.",
                )
            )
            return definition.unsatisfied_condition_effect
        if all(
            outcome in {ConditionOutcome.SATISFIED, ConditionOutcome.EXEMPTED}
            for outcome in outcomes
        ):
            return DecisionEffect.PERMIT
        return DecisionEffect.DEFER

    def _policy_contributions_for_decision(
        self,
        definition: DecisionDefinition,
        resource: ObjectEnvelope,
    ) -> tuple[PolicyContribution, ...]:
        policies = (
            tuple(self._policies[policy_id] for policy_id in definition.policy_ids)
            if definition.policy_ids
            else tuple(self._policies.values())
        )
        return tuple(
            PolicyContribution(
                policy_id=policy.id,
                policy_revision=policy.revision,
                effect=policy.effect,
                obligations=policy.obligations,
            )
            for policy in sorted(policies, key=lambda item: item.id)
            if policy.applies_to(definition.action, resource)
        )

    @staticmethod
    def _decision_effect_from_policies(
        definition: DecisionDefinition,
        policy_contributions: tuple[PolicyContribution, ...],
    ) -> DecisionEffect | None:
        if not policy_contributions:
            return None
        effects = tuple(contribution.effect for contribution in policy_contributions)
        if definition.combining_algorithm is DecisionCombiningAlgorithm.PERMIT_OVERRIDES:
            if PolicyEffect.ALLOW in effects:
                return DecisionEffect.PERMIT
            if PolicyEffect.DENY in effects:
                return DecisionEffect.PROHIBIT
        if PolicyEffect.DENY in effects:
            return DecisionEffect.PROHIBIT
        if PolicyEffect.ESCALATE in effects:
            return DecisionEffect.ESCALATE
        if PolicyEffect.REQUIRE in effects:
            return DecisionEffect.REQUIRE
        if PolicyEffect.ALLOW in effects or PolicyEffect.WARN in effects:
            return DecisionEffect.PERMIT
        return DecisionEffect.ABSTAIN

    @staticmethod
    def _combine_decision_effects(
        algorithm: DecisionCombiningAlgorithm,
        effects: tuple[DecisionEffect, ...],
    ) -> DecisionEffect:
        if not effects:
            return DecisionEffect.ABSTAIN
        if algorithm is DecisionCombiningAlgorithm.PERMIT_OVERRIDES:
            precedence = (
                DecisionEffect.PERMIT,
                DecisionEffect.PROHIBIT,
                DecisionEffect.ESCALATE,
                DecisionEffect.REQUIRE,
                DecisionEffect.DEFER,
                DecisionEffect.ABSTAIN,
            )
        else:
            precedence = (
                DecisionEffect.PROHIBIT,
                DecisionEffect.ESCALATE,
                DecisionEffect.REQUIRE,
                DecisionEffect.DEFER,
                DecisionEffect.PERMIT,
                DecisionEffect.ABSTAIN,
            )
        for effect in precedence:
            if effect in effects:
                return effect
        return DecisionEffect.ABSTAIN

    @staticmethod
    def _outcome_from_decision_effect(effect: DecisionEffect) -> str:
        outcomes = {
            DecisionEffect.PERMIT: "ALLOW",
            DecisionEffect.PROHIBIT: "DENY",
            DecisionEffect.REQUIRE: "REQUIRE",
            DecisionEffect.DEFER: "DEFER",
            DecisionEffect.ESCALATE: "ESCALATE",
            DecisionEffect.ABSTAIN: "ABSTAIN",
        }
        return outcomes[effect]

    @staticmethod
    def _decision_evaluation(
        *,
        decision_id: str,
        decision_version: str | None,
        request_id: str | None,
        action: str,
        resource_id: str,
        resource_revision: int | None,
        evaluation_status: DecisionEvaluationStatus,
        outcome: str,
        effect: DecisionEffect,
        condition_evaluations: tuple[ConditionEvaluation, ...],
        policy_contributions: tuple[PolicyContribution, ...],
        obligations: tuple[PolicyObligation, ...],
        constraints: tuple[DecisionConstraint, ...],
        advice: tuple[DecisionAdvice, ...],
        findings: tuple[DecisionFinding, ...],
        proof: dict[str, Any],
        evaluated_at: datetime,
        valid_until: datetime | None = None,
    ) -> DecisionEvaluation:
        proof_hash = f"sha256:{specification_hash(proof)}"
        return DecisionEvaluation(
            request_id=request_id,
            decision_id=decision_id,
            decision_version=decision_version,
            action=action,
            resource_id=resource_id,
            resource_revision=resource_revision,
            evaluation_status=evaluation_status,
            outcome=outcome,
            effect=effect,
            condition_evaluations=condition_evaluations,
            policy_contributions=policy_contributions,
            obligations=obligations,
            constraints=constraints,
            advice=advice,
            findings=findings,
            proof=proof,
            proof_hash=proof_hash,
            evaluated_at=evaluated_at,
            valid_until=valid_until,
        )

    @staticmethod
    def _find_transition(
        state_machine: StateMachineDefinition,
        transition_name: str,
        current_state: str,
    ) -> StateTransitionDefinition | None:
        return next(
            (
                transition
                for transition in state_machine.transitions
                if transition.name == transition_name
                and current_state in transition.source_states
            ),
            None,
        )

    def _resolve_relationship_evidence(
        self,
        relationship_type: RelationshipTypeDefinition,
        evidence: dict[str, ObjectReference],
    ) -> tuple[RelationshipEvidence, ...]:
        missing = sorted(set(relationship_type.required_evidence) - set(evidence))
        if missing:
            raise RegistryError(
                "RELATIONSHIP_EVIDENCE_INCOMPLETE",
                f"{relationship_type.id}: missing {missing}",
            )
        resolved: list[RelationshipEvidence] = []
        for evidence_type, reference in sorted(evidence.items()):
            resolution = self.resolve_reference(reference)
            if resolution.status is not ResolutionStatus.RESOLVED:
                raise RegistryError(
                    "RELATIONSHIP_EVIDENCE_INVALID",
                    f"{evidence_type}: {resolution.code}",
                )
            if resolution.resolved is None:
                raise RegistryError("RELATIONSHIP_EVIDENCE_INVALID", evidence_type)
            resolved.append(
                RelationshipEvidence(
                    type=evidence_type,
                    reference=ObjectReference(
                        resolution.resolved.metadata.id,
                        revision=resolution.resolved.metadata.revision,
                    ),
                )
            )
        return tuple(resolved)

    def _resolve_object_references(
        self,
        references: tuple[ObjectReference, ...],
        error_code: str,
    ) -> tuple[ObjectReference, ...]:
        resolved: list[ObjectReference] = []
        for reference in references:
            resolution = self.resolve_reference(reference)
            if resolution.status is not ResolutionStatus.RESOLVED:
                raise RegistryError(error_code, f"{reference.id}: {resolution.code}")
            if resolution.resolved is None:
                raise RegistryError(error_code, reference.id)
            resolved.append(
                ObjectReference(
                    resolution.resolved.metadata.id,
                    revision=resolution.resolved.metadata.revision,
                )
            )
        return tuple(resolved)

    def _require_relationship_cardinality(
        self,
        relationship_type: RelationshipTypeDefinition,
        *,
        source_id: str,
        target_id: str,
    ) -> None:
        if relationship_type.cardinality in {
            RelationshipCardinality.ONE_TO_ONE,
            RelationshipCardinality.MANY_TO_ONE,
        }:
            source = self.get_object(source_id)
            if any(
                item["type"]["$ref"]["id"] == relationship_type.id
                for item in source.relationships
            ):
                raise RegistryError(
                    "RELATIONSHIP_CARDINALITY_VIOLATION",
                    f"{relationship_type.id} already exists from {source_id}",
                )
        if relationship_type.cardinality not in {
            RelationshipCardinality.ONE_TO_ONE,
            RelationshipCardinality.ONE_TO_MANY,
        }:
            return
        for revisions in self._objects.values():
            current = revisions[-1]
            for relationship in current.relationships:
                relationship_ref = relationship["type"]["$ref"]["id"]
                target_ref = relationship["target"]["$ref"]["id"]
                if relationship_ref == relationship_type.id and target_ref == target_id:
                    raise RegistryError(
                        "RELATIONSHIP_CARDINALITY_VIOLATION",
                        f"{relationship_type.id} already targets {target_id}",
                    )

    def _record_relationship_audit(
        self,
        *,
        relationship_type: RelationshipTypeDefinition,
        relationship: RelationshipInstance,
        new_source_revision: int,
        actor: ActorReference,
        occurred_at: datetime,
    ) -> None:
        self._relationship_audit_sequence += 1
        if relationship.source.revision is None or relationship.target.revision is None:
            raise RegistryError("RELATIONSHIP_REVISION_REQUIRED", relationship.id)
        self._relationship_audit_records.append(
            RelationshipAuditRecord(
                id=f"RELAUD-{self._relationship_audit_sequence:06d}",
                sequence=self._relationship_audit_sequence,
                relationship_id=relationship.id,
                relationship_type_id=relationship_type.id,
                relationship_type_version=relationship_type.version,
                action="RELATIONSHIP_CREATED",
                source_id=relationship.source.id,
                target_id=relationship.target.id,
                source_revision=relationship.source.revision,
                target_revision=relationship.target.revision,
                new_source_revision=new_source_revision,
                actor=actor,
                evidence_types=tuple(
                    evidence.type
                    for evidence in sorted(
                        relationship.evidence,
                        key=lambda item: item.type,
                    )
                ),
                recorded_at=occurred_at,
            )
        )

    def _record_transition_evidence(
        self,
        *,
        current: ObjectEnvelope,
        updated: ObjectEnvelope,
        state_machine: StateMachineDefinition,
        transition: StateTransitionDefinition,
        decision: StateTransitionDecision,
        actor: ActorReference,
        action_id: str | None,
        occurred_at: datetime,
    ) -> None:
        self._event_sequence += 1
        event = StateTransitionEvent(
            id=f"EVT-{self._event_sequence:06d}",
            sequence=self._event_sequence,
            event_type="StateTransitioned",
            object_id=current.metadata.id,
            object_kind=current.kind,
            previous_revision=current.metadata.revision,
            new_revision=updated.metadata.revision,
            state_machine_id=state_machine.id,
            state_machine_version=state_machine.version,
            transition=transition.name,
            from_state=current.lifecycle.state,
            to_state=updated.lifecycle.state,
            actor=actor,
            action_id=action_id,
            occurred_at=occurred_at,
        )
        audit_record = StateTransitionAuditRecord(
            id=f"AUD-{self._event_sequence:06d}",
            event_id=event.id,
            object_id=current.metadata.id,
            state_machine_id=state_machine.id,
            state_machine_version=state_machine.version,
            transition=transition.name,
            action_id=action_id,
            actor=actor,
            previous_state=current.lifecycle.state,
            new_state=updated.lifecycle.state,
            previous_revision=current.metadata.revision,
            new_revision=updated.metadata.revision,
            decision=decision,
            recorded_at=occurred_at,
        )
        self._transition_events.append(event)
        self._transition_audit_records.append(audit_record)

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
        relationships: tuple[dict[str, Any], ...] = (),
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
            relationships=relationships,
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


def _value_at_path(document: dict[str, Any], path: str) -> Any:
    current: Any = document
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return _MISSING
        current = current[segment]
    return current


def _parse_duration(value: str) -> timedelta:
    match = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?"
        r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?",
        value,
    )
    if match is None:
        raise RegistryError("OBLIGATION_TIMING_INVALID", value)
    duration = timedelta(
        days=int(match.group("days") or 0),
        hours=int(match.group("hours") or 0),
        minutes=int(match.group("minutes") or 0),
        seconds=int(match.group("seconds") or 0),
    )
    if duration <= timedelta(0):
        raise RegistryError("OBLIGATION_TIMING_INVALID", value)
    return duration


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


def _expected_type(property_definition: PropertyDefinition) -> Any:
    if property_definition.type == "enum":
        return tuple(property_definition.enum)
    if property_definition.type == "reference" and property_definition.target_kinds:
        return {"type": "reference", "targetKinds": tuple(property_definition.target_kinds)}
    if property_definition.type == "list" and property_definition.item_type is not None:
        return {"type": "list", "items": property_definition.item_type}
    return property_definition.type


def _actual_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "decimal"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "map"
    return type(value).__name__


def _validation_message(
    name: str,
    value: Any,
    property_definition: PropertyDefinition,
    error: RegistryError,
) -> str:
    if error.code == "ENUM_VALUE_INVALID":
        return f"Property '{name}' must be one of {tuple(property_definition.enum)}."
    if error.code == "REFERENCE_INVALID":
        return f"Property '{name}' must be a valid registry reference."
    if error.code == "PROPERTY_TYPE_UNKNOWN":
        return f"Property '{name}' has unknown type '{property_definition.type}'."
    return (
        f"Property '{name}' must be {_expected_type(property_definition)}; "
        f"received {_actual_type(value)}."
    )


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
