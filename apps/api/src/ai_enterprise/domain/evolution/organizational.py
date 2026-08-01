import hashlib
import json
import re
from dataclasses import dataclass, fields, replace
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from uuid import UUID


class ImprovementStatus(StrEnum):
    PROPOSED = "proposed"
    ANALYZED = "analyzed"
    SIMULATED = "simulated"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    IMPLEMENTED = "implemented"
    MEASURED = "measured"
    ACCEPTED = "accepted"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class EvolutionError(ValueError):
    pass


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _require_hashes(values: tuple[str, ...]) -> None:
    if not values or any(
        len(value) != 64 or any(character not in "0123456789abcdef" for character in value)
        for value in values
    ):
        raise EvolutionError("immutable lowercase SHA-256 evidence is required")
    if len(values) != len(set(values)):
        raise EvolutionError("duplicate evidence replay is forbidden")


@dataclass(frozen=True, slots=True)
class Improvement:
    id: UUID
    version: int
    category: str
    origin: str
    title: str
    expected_benefit: str
    risk: str
    evidence_hashes: tuple[str, ...]
    dependency_ids: tuple[UUID, ...]
    status: ImprovementStatus
    proposed_by: UUID
    content_hash: str

    @classmethod
    def propose(cls, **values: object) -> "Improvement":
        evidence = values.get("evidence_hashes")
        if not isinstance(evidence, tuple):
            raise EvolutionError("evidence must be an immutable tuple")
        _require_hashes(evidence)
        values["status"] = ImprovementStatus.PROPOSED
        values["version"] = 1
        digest = _hash(values)
        return cls(content_hash=digest, **values)  # type: ignore[arg-type]

    def verify(self) -> bool:
        values = {
            field.name: getattr(self, field.name)
            for field in fields(self)
            if field.name != "content_hash"
        }
        return self.content_hash == _hash(values)


_NEXT = {
    ImprovementStatus.PROPOSED: {ImprovementStatus.ANALYZED, ImprovementStatus.REJECTED},
    ImprovementStatus.ANALYZED: {ImprovementStatus.SIMULATED, ImprovementStatus.REJECTED},
    ImprovementStatus.SIMULATED: {ImprovementStatus.REVIEWED, ImprovementStatus.REJECTED},
    ImprovementStatus.REVIEWED: {ImprovementStatus.APPROVED, ImprovementStatus.REJECTED},
    ImprovementStatus.APPROVED: {ImprovementStatus.IMPLEMENTED},
    ImprovementStatus.IMPLEMENTED: {ImprovementStatus.MEASURED},
    ImprovementStatus.MEASURED: {ImprovementStatus.ACCEPTED, ImprovementStatus.REJECTED},
    ImprovementStatus.ACCEPTED: {ImprovementStatus.ARCHIVED},
}


def transition_improvement(
    improvement: Improvement,
    target: ImprovementStatus,
    *,
    stage_evidence_hashes: tuple[str, ...],
) -> Improvement:
    _require_hashes(stage_evidence_hashes)
    if not improvement.verify() or target not in _NEXT.get(improvement.status, set()):
        raise EvolutionError("invalid or tampered improvement transition")
    values = {
        **{field.name: getattr(improvement, field.name) for field in fields(improvement)},
        "version": improvement.version + 1,
        "status": target,
        "evidence_hashes": tuple(sorted(set(improvement.evidence_hashes + stage_evidence_hashes))),
    }
    values.pop("content_hash")
    return replace(improvement, **values, content_hash=_hash(values))


@dataclass(frozen=True, slots=True)
class LearningObservation:
    id: UUID
    subject_key: str
    metric_key: str
    subject_value: Decimal
    baseline_value: Decimal
    sample_size: int
    evidence_hashes: tuple[str, ...]
    workflow_ids: tuple[UUID, ...]
    expected_workflow_ids: frozenset[UUID]

    def __post_init__(self) -> None:
        _require_hashes(self.evidence_hashes)
        if self.sample_size < 1:
            raise EvolutionError("learning requires observed samples")
        if (
            len(self.workflow_ids) != len(set(self.workflow_ids))
            or set(self.workflow_ids) != set(self.expected_workflow_ids)
            or len(self.evidence_hashes) != len(self.workflow_ids)
        ):
            raise EvolutionError("learning evidence must cover the complete workflow population")


@dataclass(frozen=True, slots=True)
class LearningHypothesis:
    id: UUID
    observation_id: UUID
    statement: str
    evidence_hashes: tuple[str, ...]
    recommendation_only: bool = True


def derive_hypothesis(
    observation: LearningObservation, *, hypothesis_id: UUID
) -> LearningHypothesis:
    direction = "above" if observation.subject_value > observation.baseline_value else "below"
    statement = (
        f"{observation.subject_key} {observation.metric_key} is {direction} the audited baseline; "
        "investigate a governed improvement."
    )
    return LearningHypothesis(hypothesis_id, observation.id, statement, observation.evidence_hashes)


@dataclass(frozen=True, slots=True)
class EngineeringPattern:
    id: UUID
    kind: str
    purpose: str
    applicability: str
    benefit: str
    known_risks: tuple[str, ...]
    compatibility: str
    generator_support: str | None
    workflow_ids: tuple[UUID, ...]
    evidence_hashes: tuple[str, ...]
    status: str
    reviewed_by_human_id: UUID | None = None

    def __post_init__(self) -> None:
        _require_hashes(self.evidence_hashes)
        if len(set(self.workflow_ids)) < 2:
            raise EvolutionError("patterns require recurring evidence from distinct workflows")
        if len(self.evidence_hashes) != len(self.workflow_ids):
            raise EvolutionError("each pattern occurrence requires distinct evidence")
        if self.kind not in {"pattern", "anti_pattern"}:
            raise EvolutionError("unsupported pattern kind")
        if self.status not in {"candidate", "validated", "withdrawn", "superseded"}:
            raise EvolutionError("invalid pattern lifecycle")
        if self.status == "validated" and self.reviewed_by_human_id is None:
            raise EvolutionError("validated patterns require human review")


@dataclass(frozen=True, slots=True)
class EngineeringRecommendation:
    id: UUID
    version: int
    category: str
    title: str
    expected_benefits: tuple[str, ...]
    risks: tuple[str, ...]
    estimated_effort: str
    affected_systems: tuple[str, ...]
    evidence_hashes: tuple[str, ...]
    recommendation_hash: str
    self_executing: bool = False

    @classmethod
    def create(cls, **values: object) -> "EngineeringRecommendation":
        evidence = values.get("evidence_hashes")
        if not isinstance(evidence, tuple):
            raise EvolutionError("evidence tuple required")
        _require_hashes(evidence)
        values["version"] = 1
        values["self_executing"] = False
        return cls(recommendation_hash=_hash(values), **values)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class SimulationInput:
    id: UUID
    improvement_hash: str
    architecture_hash: str
    dependency_count: int
    affected_team_count: int
    affected_repository_count: int
    historical_failure_rate: Decimal
    expected_cost_delta: Decimal
    expected_performance_delta: Decimal
    policy_version: str

    def __post_init__(self) -> None:
        _require_hashes((self.improvement_hash, self.architecture_hash))
        if (
            self.dependency_count < 0
            or self.affected_team_count < 0
            or self.affected_repository_count < 0
            or not Decimal("0") <= self.historical_failure_rate <= Decimal("1")
            or not all(
                value.is_finite()
                for value in (
                    self.historical_failure_rate,
                    self.expected_cost_delta,
                    self.expected_performance_delta,
                )
            )
            or not self.policy_version
        ):
            raise EvolutionError("invalid or unbounded simulation input")


@dataclass(frozen=True, slots=True)
class SimulationResult:
    input_id: UUID
    predicted_risk: Decimal
    cost_delta: Decimal
    performance_delta: Decimal
    migration_complexity: str
    simulation_hash: str


def simulate(value: SimulationInput) -> SimulationResult:
    risk = min(
        Decimal("1"),
        value.historical_failure_rate
        + Decimal(value.dependency_count) * Decimal("0.01")
        + Decimal(value.affected_repository_count) * Decimal("0.02"),
    ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    complexity = (
        "high"
        if value.dependency_count >= 10 or value.affected_repository_count >= 5
        else "medium"
        if value.dependency_count >= 4
        else "low"
    )
    document = {
        "input": value,
        "risk": risk,
        "cost": value.expected_cost_delta,
        "performance": value.expected_performance_delta,
        "complexity": complexity,
    }
    return SimulationResult(
        value.id,
        risk,
        value.expected_cost_delta,
        value.expected_performance_delta,
        complexity,
        _hash(document),
    )


@dataclass(frozen=True, slots=True)
class ExperimentPlan:
    id: UUID
    version: int
    hypothesis: str
    success_metric: str
    minimum_improvement: Decimal
    maximum_guardrail_regression: Decimal
    duration_days: int
    participant_ids: tuple[UUID, ...]
    rollback_plan_hash: str
    approved_by_human_id: UUID | None

    def __post_init__(self) -> None:
        _require_hashes((self.rollback_plan_hash,))
        if (
            self.duration_days < 1
            or len(set(self.participant_ids)) < 2
            or len(self.participant_ids) != len(set(self.participant_ids))
            or not self.minimum_improvement.is_finite()
            or not self.maximum_guardrail_regression.is_finite()
            or self.maximum_guardrail_regression < 0
        ):
            raise EvolutionError("experiment design is insufficient")


@dataclass(frozen=True, slots=True)
class ExperimentOutcome:
    experiment_id: UUID
    control_value: Decimal
    treatment_value: Decimal
    guardrail_regression: Decimal
    evidence_hashes: tuple[str, ...]
    decision: str


def evaluate_experiment(
    plan: ExperimentPlan,
    *,
    control_value: Decimal,
    treatment_value: Decimal,
    guardrail_regression: Decimal,
    participant_evidence: tuple[tuple[UUID, str], ...],
) -> ExperimentOutcome:
    if plan.approved_by_human_id is None:
        raise EvolutionError("experiment requires human approval")
    participants = [participant_id for participant_id, _ in participant_evidence]
    evidence_hashes = tuple(evidence_hash for _, evidence_hash in participant_evidence)
    _require_hashes(evidence_hashes)
    if len(participants) != len(set(participants)) or set(participants) != set(
        plan.participant_ids
    ):
        raise EvolutionError("experiment evidence must cover every approved participant")
    if (
        not all(
            value.is_finite() for value in (control_value, treatment_value, guardrail_regression)
        )
        or guardrail_regression < 0
    ):
        raise EvolutionError("experiment measurements must be finite and bounded")
    improvement = treatment_value - control_value
    decision = (
        "stop_guardrail"
        if guardrail_regression > plan.maximum_guardrail_regression
        else "recommend_adoption"
        if improvement >= plan.minimum_improvement
        else "no_effect"
    )
    return ExperimentOutcome(
        plan.id, control_value, treatment_value, guardrail_regression, evidence_hashes, decision
    )


@dataclass(frozen=True, slots=True)
class EvolutionProposal:
    id: UUID
    target_type: str
    target_key: str
    current_version: str
    proposed_version: str
    candidate_hash: str
    evidence_hashes: tuple[str, ...]
    compatibility_evidence_hashes: tuple[str, ...]
    proposed_by_actor_id: UUID
    status: str = "proposed"

    def __post_init__(self) -> None:
        if self.target_type not in {
            "generator",
            "policy",
            "agent",
            "prompt",
            "crew",
            "certification",
        }:
            raise EvolutionError("unsupported evolution target")
        _require_hashes(self.evidence_hashes)
        _require_hashes(self.compatibility_evidence_hashes)
        if len(self.candidate_hash) != 64 or any(
            character not in "0123456789abcdef" for character in self.candidate_hash
        ):
            raise EvolutionError("candidate must be hash-bound")
        version_pattern = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$"
        current = re.fullmatch(version_pattern, self.current_version)
        proposed = re.fullmatch(version_pattern, self.proposed_version)
        if (
            current is None
            or proposed is None
            or tuple(map(int, proposed.groups())) <= tuple(map(int, current.groups()))
            or not self.target_key.startswith(f"{self.target_type}.")
            or self.status != "proposed"
        ):
            raise EvolutionError("evolution begins as a new versioned proposal")


@dataclass(frozen=True, slots=True)
class EvolutionApproval:
    proposal_id: UUID
    decision: str
    decided_by_human_id: UUID
    candidate_hash: str
    decided_at: datetime


def approve_evolution(
    proposal: EvolutionProposal, approval: EvolutionApproval
) -> "ApprovedEvolution":
    if approval.proposal_id != proposal.id or approval.candidate_hash != proposal.candidate_hash:
        raise EvolutionError("approval is not bound to the evolution candidate")
    if approval.decision != "approve":
        raise EvolutionError("explicit human approval is required")
    if approval.decided_by_human_id == proposal.proposed_by_actor_id:
        raise EvolutionError("evolution requires an independent human approver")
    if approval.decided_at.tzinfo is None or approval.decided_at.utcoffset() is None:
        raise EvolutionError("approval time must be timezone-aware")
    return ApprovedEvolution(proposal, approval, "approved")


@dataclass(frozen=True, slots=True)
class ApprovedEvolution:
    proposal: EvolutionProposal
    approval: EvolutionApproval
    status: str
