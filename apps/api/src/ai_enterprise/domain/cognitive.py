import hashlib
import json
from dataclasses import dataclass, fields, replace
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any, cast
from uuid import UUID


class CognitiveError(ValueError):
    pass


def _canonical(value: object) -> object:
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise CognitiveError("non-finite values cannot enter strategic reasoning")
        return format(value.normalize(), "f")
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise CognitiveError("cognitive timestamps must be timezone-aware")
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, list | tuple | set | frozenset):
        return [_canonical(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise CognitiveError("semantic keys must be strings")
        return {key: _canonical(item) for key, item in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        dataclass_value = cast(Any, value)
        return {
            field.name: _canonical(getattr(dataclass_value, field.name))
            for field in fields(dataclass_value)
        }
    raise CognitiveError(f"unsupported cognitive value {type(value).__name__}")


def cognitive_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(_canonical(value), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def require_evidence(values: tuple[str, ...]) -> None:
    if (
        not values
        or len(values) != len(set(values))
        or any(
            len(value) != 64 or any(character not in "0123456789abcdef" for character in value)
            for value in values
        )
    ):
        raise CognitiveError("unique immutable evidence hashes are required")


@dataclass(frozen=True, slots=True)
class SemanticObject:
    id: UUID
    object_type: str
    key: str
    name: str
    source_system: str
    source_id: UUID
    source_hash: str
    classification: str
    observed_at: datetime

    def __post_init__(self) -> None:
        require_evidence((self.source_hash,))
        if self.classification not in {"public", "internal", "confidential", "restricted"}:
            raise CognitiveError("unknown semantic classification")


@dataclass(frozen=True, slots=True)
class OntologyRelation:
    relation_key: str
    source_type: str
    target_type: str
    inverse_relation_key: str | None
    transitive: bool
    ontology_version: str
    approved_by_human_id: UUID
    relation_hash: str

    @classmethod
    def create(cls, **values: object) -> "OntologyRelation":
        return cls(relation_hash=cognitive_hash(values), **values)  # type: ignore[arg-type]

    def verify(self) -> bool:
        return self.relation_hash == cognitive_hash(
            {
                field.name: getattr(self, field.name)
                for field in fields(self)
                if field.name != "relation_hash"
            }
        )


@dataclass(frozen=True, slots=True)
class SemanticEdge:
    id: UUID
    source_id: UUID
    target_id: UUID
    relation_key: str
    evidence_hashes: tuple[str, ...]
    valid_from: datetime
    valid_until: datetime | None
    edge_hash: str

    @classmethod
    def create(cls, **values: object) -> "SemanticEdge":
        evidence = values.get("evidence_hashes")
        if not isinstance(evidence, tuple):
            raise CognitiveError("edge evidence must be immutable")
        require_evidence(evidence)
        return cls(edge_hash=cognitive_hash(values), **values)  # type: ignore[arg-type]


def validate_edge(
    edge: SemanticEdge,
    *,
    source: SemanticObject,
    target: SemanticObject,
    relation: OntologyRelation,
) -> None:
    if (
        edge.source_id != source.id
        or edge.target_id != target.id
        or edge.relation_key != relation.relation_key
        or source.object_type != relation.source_type
        or target.object_type != relation.target_type
        or not relation.verify()
        or edge.edge_hash
        != cognitive_hash(
            {
                field.name: getattr(edge, field.name)
                for field in fields(edge)
                if field.name != "edge_hash"
            }
        )
    ):
        raise CognitiveError("semantic edge violates ontology or provenance")


def validate_ontology_acyclic(
    edges: tuple[SemanticEdge, ...], *, hierarchical_relations: frozenset[str]
) -> None:
    graph: dict[UUID, set[UUID]] = {}
    for edge in edges:
        if edge.relation_key in hierarchical_relations:
            graph.setdefault(edge.source_id, set()).add(edge.target_id)
    visiting: set[UUID] = set()
    visited: set[UUID] = set()

    def visit(node: UUID) -> None:
        if node in visiting:
            raise CognitiveError("hierarchical ontology cycle detected")
        if node in visited:
            return
        visiting.add(node)
        for target in sorted(graph.get(node, set()), key=str):
            visit(target)
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph, key=str):
        visit(node)


@dataclass(frozen=True, slots=True)
class StrategicSignal:
    id: UUID
    signal_type: str
    subject_id: UUID
    value: Decimal
    baseline: Decimal
    trend: Decimal
    evidence_hashes: tuple[str, ...]
    classification: str = "internal"

    def __post_init__(self) -> None:
        require_evidence(self.evidence_hashes)
        if not all(value.is_finite() for value in (self.value, self.baseline, self.trend)):
            raise CognitiveError("strategic signals must be finite")
        if self.classification not in {"public", "internal", "confidential", "restricted"}:
            raise CognitiveError("unknown strategic classification")


@dataclass(frozen=True, slots=True)
class StrategicFinding:
    finding_type: str
    subject_id: UUID
    severity: str
    explanation: str
    confidence_band: str
    evidence_hashes: tuple[str, ...]
    rule_version: str
    classification: str


def reason(
    signals: tuple[StrategicSignal, ...], *, rule_version: str
) -> tuple[StrategicFinding, ...]:
    findings: list[StrategicFinding] = []
    for signal in sorted(signals, key=lambda item: (item.signal_type, str(item.subject_id))):
        deviation = signal.value - signal.baseline
        severity = (
            "high"
            if abs(deviation) >= abs(signal.baseline) * Decimal("0.5")
            else "medium"
            if abs(deviation) >= abs(signal.baseline) * Decimal("0.2")
            else "low"
        )
        findings.append(
            StrategicFinding(
                signal.signal_type,
                signal.subject_id,
                severity,
                f"Observed {signal.value} versus baseline {signal.baseline}; trend {signal.trend}.",
                "high" if len(signal.evidence_hashes) >= 3 else "moderate",
                signal.evidence_hashes,
                rule_version,
                signal.classification,
            )
        )
    return tuple(findings)


@dataclass(frozen=True, slots=True)
class ExecutiveQuestion:
    id: UUID
    question_text: str
    requested_object_types: tuple[str, ...]
    maximum_classification: str


@dataclass(frozen=True, slots=True)
class ExecutiveAnswer:
    question_id: UUID
    answer: str
    explanation_steps: tuple[str, ...]
    semantic_object_ids: tuple[UUID, ...]
    evidence_hashes: tuple[str, ...]
    answer_hash: str


def answer_question(
    question: ExecutiveQuestion, findings: tuple[StrategicFinding, ...]
) -> ExecutiveAnswer:
    if not findings:
        raise CognitiveError("executive answers require evidence-backed findings")
    ranks = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
    if question.maximum_classification not in ranks or any(
        ranks[finding.classification] > ranks[question.maximum_classification]
        for finding in findings
    ):
        raise CognitiveError("executive question clearance is insufficient")
    ordered = tuple(sorted(findings, key=lambda item: (item.severity, str(item.subject_id))))
    evidence = tuple(sorted({digest for finding in ordered for digest in finding.evidence_hashes}))
    document = {
        "question": question,
        "findings": ordered,
        "evidence": evidence,
    }
    return ExecutiveAnswer(
        question.id,
        "; ".join(finding.explanation for finding in ordered),
        tuple(f"Applied {finding.rule_version} to {finding.finding_type}" for finding in ordered),
        tuple(finding.subject_id for finding in ordered),
        evidence,
        cognitive_hash(document),
    )


@dataclass(frozen=True, slots=True)
class StrategicScenario:
    id: UUID
    version: int
    title: str
    assumptions: tuple[str, ...]
    assumption_evidence_hashes: tuple[str, ...]
    affected_system_ids: tuple[UUID, ...]
    risk_factors: tuple[Decimal, ...]
    benefit_factors: tuple[Decimal, ...]
    estimated_cost: Decimal
    estimated_duration_days: int
    evidence_hashes: tuple[str, ...]
    scenario_hash: str

    @classmethod
    def create(cls, **values: object) -> "StrategicScenario":
        evidence = values.get("evidence_hashes")
        if not isinstance(evidence, tuple):
            raise CognitiveError("scenario evidence is required")
        require_evidence(evidence)
        assumption_evidence = values.get("assumption_evidence_hashes")
        assumptions = values.get("assumptions")
        systems = values.get("affected_system_ids")
        if (
            not isinstance(assumptions, tuple)
            or assumptions != tuple(sorted(set(assumptions)))
            or not isinstance(systems, tuple)
            or systems != tuple(sorted(set(systems), key=str))
            or not isinstance(assumption_evidence, tuple)
            or len(assumption_evidence) != len(assumptions)
            or not set(assumption_evidence).issubset(evidence)
        ):
            raise CognitiveError("scenario assumptions and systems must be unique and sorted")
        values["version"] = 1
        return cls(scenario_hash=cognitive_hash(values), **values)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class StrategicSimulation:
    scenario_id: UUID
    risk_score: Decimal
    benefit_score: Decimal
    net_value: Decimal
    second_order_effects: tuple[str, ...]
    model_version: str
    result_hash: str


def simulate_scenario(scenario: StrategicScenario, *, model_version: str) -> StrategicSimulation:
    if scenario.scenario_hash != cognitive_hash(
        {
            field.name: getattr(scenario, field.name)
            for field in fields(scenario)
            if field.name != "scenario_hash"
        }
    ):
        raise CognitiveError("scenario was tampered")
    values = scenario.risk_factors + scenario.benefit_factors + (scenario.estimated_cost,)
    if not all(value.is_finite() for value in values) or scenario.estimated_duration_days < 1:
        raise CognitiveError("scenario inputs are invalid")
    if (
        any(
            value < Decimal("0") or value > Decimal("1")
            for value in scenario.risk_factors + scenario.benefit_factors
        )
        or scenario.estimated_cost < 0
    ):
        raise CognitiveError("scenario factors must use bounded policy units")
    risk = (sum(scenario.risk_factors, Decimal(0)) / max(1, len(scenario.risk_factors))).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
    benefit = (
        sum(scenario.benefit_factors, Decimal(0)) / max(1, len(scenario.benefit_factors))
    ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    net = (benefit - risk - scenario.estimated_cost).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
    effects = tuple(sorted({f"affects:{system_id}" for system_id in scenario.affected_system_ids}))
    document = {
        "scenario_hash": scenario.scenario_hash,
        "risk": risk,
        "benefit": benefit,
        "net": net,
        "effects": effects,
        "model": model_version,
    }
    return StrategicSimulation(
        scenario.id, risk, benefit, net, effects, model_version, cognitive_hash(document)
    )


@dataclass(frozen=True, slots=True)
class DigitalTwinSnapshot:
    id: UUID
    version: int
    captured_at: datetime
    source_hashes: tuple[str, ...]
    expected_source_hashes: frozenset[str]
    semantic_object_ids: tuple[UUID, ...]
    active_policy_hashes: tuple[str, ...]
    snapshot_hash: str

    @classmethod
    def capture(cls, **values: object) -> "DigitalTwinSnapshot":
        sources = values.get("source_hashes")
        policies = values.get("active_policy_hashes")
        expected = values.get("expected_source_hashes")
        if (
            not isinstance(sources, tuple)
            or not isinstance(policies, tuple)
            or not isinstance(expected, frozenset)
        ):
            raise CognitiveError("digital twin sources must be immutable")
        require_evidence(sources)
        require_evidence(policies)
        if set(sources) != set(expected):
            raise CognitiveError("digital twin snapshot is incomplete")
        return cls(snapshot_hash=cognitive_hash(values), **values)  # type: ignore[arg-type]

    def current_at(self, now: datetime, *, maximum_age_seconds: int) -> bool:
        _canonical(now)
        return 0 <= (now - self.captured_at).total_seconds() <= maximum_age_seconds


@dataclass(frozen=True, slots=True)
class CognitiveMemoryItem:
    id: UUID
    memory_type: str
    statement: str
    outcome: str
    scope_ids: tuple[UUID, ...]
    evidence_hashes: tuple[str, ...]
    proposed_by_actor_id: UUID
    promoted_by_human_id: UUID
    valid_from: datetime
    valid_until: datetime | None

    def __post_init__(self) -> None:
        require_evidence(self.evidence_hashes)
        if self.proposed_by_actor_id == self.promoted_by_human_id:
            raise CognitiveError("cognitive memory requires independent human promotion")
        _canonical(self.valid_from)
        if self.valid_until is not None:
            _canonical(self.valid_until)
            if self.valid_until <= self.valid_from:
                raise CognitiveError("cognitive memory validity is invalid")


@dataclass(frozen=True, slots=True)
class KnowledgeSynthesis:
    id: UUID
    claim: str
    contributing_memory_ids: tuple[UUID, ...]
    evidence_hashes: tuple[str, ...]
    explanation: tuple[str, ...]
    synthesis_hash: str


def synthesize(
    *,
    synthesis_id: UUID,
    claim: str,
    memories: tuple[CognitiveMemoryItem, ...],
    expected_memory_ids: frozenset[UUID],
) -> KnowledgeSynthesis:
    if len({memory.id for memory in memories}) < 2 or {memory.id for memory in memories} != set(
        expected_memory_ids
    ):
        raise CognitiveError("knowledge synthesis requires multiple curated memories")
    evidence = tuple(sorted({digest for memory in memories for digest in memory.evidence_hashes}))
    explanation = tuple(
        f"Derived from curated memory {memory.id}"
        for memory in sorted(memories, key=lambda item: str(item.id))
    )
    document = {
        "claim": claim,
        "memories": tuple(memory.id for memory in memories),
        "evidence": evidence,
    }
    return KnowledgeSynthesis(
        synthesis_id,
        claim,
        tuple(memory.id for memory in memories),
        evidence,
        explanation,
        cognitive_hash(document),
    )


class RecommendationStatus(StrEnum):
    GENERATED = "generated"
    REVIEWED = "reviewed"
    ACCEPTED = "accepted"
    PLANNED = "planned"
    IMPLEMENTED = "implemented"
    MEASURED = "measured"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class StrategicRecommendation:
    id: UUID
    version: int
    recommendation_type: str
    statement: str
    expected_benefit: str
    confidence_band: str
    risks: tuple[str, ...]
    affected_system_ids: tuple[UUID, ...]
    required_investment: Decimal
    evidence_hashes: tuple[str, ...]
    generated_by_actor_id: UUID
    decision_actor_ids: tuple[UUID, ...]
    status: RecommendationStatus
    recommendation_hash: str
    self_executing: bool = False

    @classmethod
    def generate(cls, **values: object) -> "StrategicRecommendation":
        evidence = values.get("evidence_hashes")
        if not isinstance(evidence, tuple):
            raise CognitiveError("recommendation evidence is required")
        require_evidence(evidence)
        values.update(
            version=1,
            confidence_band="high" if len(evidence) >= 3 else "moderate",
            status=RecommendationStatus.GENERATED,
            decision_actor_ids=(),
            self_executing=False,
        )
        investment = values.get("required_investment")
        if not isinstance(investment, Decimal) or not investment.is_finite() or investment < 0:
            raise CognitiveError("recommendation investment must be finite and nonnegative")
        return cls(recommendation_hash=cognitive_hash(values), **values)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class RecommendationDecision:
    recommendation_id: UUID
    recommendation_hash: str
    decision: str
    decided_by_human_id: UUID
    decided_at: datetime


def review_recommendation(
    recommendation: StrategicRecommendation, decision: RecommendationDecision
) -> StrategicRecommendation:
    if recommendation.recommendation_hash != cognitive_hash(
        {
            field.name: getattr(recommendation, field.name)
            for field in fields(recommendation)
            if field.name != "recommendation_hash"
        }
    ):
        raise CognitiveError("recommendation was tampered")
    if (
        decision.recommendation_id != recommendation.id
        or decision.recommendation_hash != recommendation.recommendation_hash
    ):
        raise CognitiveError("decision is not bound to the recommendation")
    transitions = {
        (RecommendationStatus.GENERATED, "review"): RecommendationStatus.REVIEWED,
        (RecommendationStatus.GENERATED, "reject"): RecommendationStatus.REJECTED,
        (RecommendationStatus.REVIEWED, "accept"): RecommendationStatus.ACCEPTED,
        (RecommendationStatus.REVIEWED, "reject"): RecommendationStatus.REJECTED,
        (RecommendationStatus.ACCEPTED, "plan"): RecommendationStatus.PLANNED,
        (RecommendationStatus.PLANNED, "implement"): RecommendationStatus.IMPLEMENTED,
        (RecommendationStatus.IMPLEMENTED, "measure"): RecommendationStatus.MEASURED,
    }
    target = transitions.get((recommendation.status, decision.decision))
    if target is None:
        raise CognitiveError("human decision is invalid for recommendation state")
    _canonical(decision.decided_at)
    if (
        decision.decided_by_human_id == recommendation.generated_by_actor_id
        or decision.decided_by_human_id in recommendation.decision_actor_ids
    ):
        raise CognitiveError("recommendation lifecycle requires independent human decisions")
    values = {
        field.name: getattr(recommendation, field.name)
        for field in fields(recommendation)
        if field.name != "recommendation_hash"
    }
    actors = recommendation.decision_actor_ids + (decision.decided_by_human_id,)
    values.update(version=recommendation.version + 1, status=target, decision_actor_ids=actors)
    return replace(
        recommendation,
        version=recommendation.version + 1,
        status=target,
        decision_actor_ids=actors,
        recommendation_hash=cognitive_hash(values),
    )
