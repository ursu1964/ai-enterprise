#!/usr/bin/env python3
"""Deterministic verifier for advisory, evidence-bound enterprise strategic intelligence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

import engineering_verify
import jsonschema

INTELLIGENCE_REPORT_SCHEMA_REF = (
    "schemas/release-artifacts/intelligence-verification-report.schema.json"
)
SPEC_FILES = (
    "evidence.v1.json",
    "objective-optimizer.v1.json",
    "dashboard.v1.json",
    "cross-domain-reasoning.v1.json",
    "strategic-memory.v1.json",
    "cognitive-governance.v1.json",
    "strategic-intelligence.v1.json",
)
REQUIRED_VIEWS = {
    "strategic-health": {"objective-progress", "investment-alignment", "delivery-confidence"},
    "organizational-intelligence": {
        "emerging-bottlenecks",
        "capability-maturity",
        "collaboration-patterns",
    },
    "technology-landscape": {
        "framework-adoption",
        "technology-lifecycle",
        "modernization-opportunities",
    },
    "risk-intelligence": {
        "projected-architectural-debt",
        "concentration-risks",
        "dependency-risks",
        "organizational-fragility",
    },
}


@dataclass(frozen=True, slots=True)
class Finding:
    check: str
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class IntelligenceReport:
    conformant: bool
    checks: int
    evidence_hash: str
    investment_ranking: tuple[dict[str, Any], ...]
    findings: tuple[Finding, ...]
    schema_version: str = "1.0"
    schema_ref: str = INTELLIGENCE_REPORT_SCHEMA_REF


def _load(root: Path, findings: list[Finding]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name in SPEC_FILES:
        path = root / "specifications" / "intelligence" / name
        try:
            if not engineering_verify._inside(root, path) or path.is_symlink():
                raise ValueError("must be a regular in-repository file")
            result[name] = engineering_verify._strict_json(path)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            findings.append(Finding("intelligence-specification", str(path), str(exc)))
    return result


def _cycles(items: list[dict[str, Any]], identity: str, dependencies: str) -> tuple[str, ...]:
    graph = {str(item.get(identity)): tuple(item.get(dependencies, ())) for item in items}
    visiting: list[str] = []
    visited: set[str] = set()
    cycles: set[str] = set()

    def visit(item: str) -> None:
        if item in visiting:
            cycles.add(" -> ".join(visiting[visiting.index(item) :] + [item]))
            return
        if item in visited:
            return
        visiting.append(item)
        for dependency in sorted(graph.get(item, ())):
            if dependency in graph:
                visit(dependency)
        visiting.pop()
        visited.add(item)

    for item in sorted(graph):
        visit(item)
    return tuple(sorted(cycles))


def verify(root: Path) -> IntelligenceReport:
    root = root.resolve()
    findings: list[Finding] = []
    specs = _load(root, findings)
    checks = len(SPEC_FILES)
    expected_shapes: dict[str, dict[str, type[Any]]] = {
        "evidence.v1.json": {"evidence": list},
        "objective-optimizer.v1.json": {"weights": dict, "investments": list, "authority": dict},
        "dashboard.v1.json": {"views": list, "requirements": dict},
        "cross-domain-reasoning.v1.json": {
            "domains": list,
            "inferences": list,
            "requirements": dict,
        },
        "strategic-memory.v1.json": {"items": list, "policy": dict},
        "cognitive-governance.v1.json": {"policy": dict},
        "strategic-intelligence.v1.json": {
            "capabilities": list,
            "recommendations": list,
            "lifecycle": list,
            "layer_boundaries": dict,
        },
    }
    for name, shapes in expected_shapes.items():
        document = specs.get(name)
        invalid_shape = not isinstance(document, dict)
        if isinstance(document, dict):
            invalid_shape = any(
                not isinstance(document.get(field), expected) for field, expected in shapes.items()
            )
        if invalid_shape:
            findings.append(
                Finding("intelligence-shape", name, "required object or collection has wrong type")
            )
    collections = (
        ("evidence.v1.json", "evidence"),
        ("objective-optimizer.v1.json", "investments"),
        ("dashboard.v1.json", "views"),
        ("cross-domain-reasoning.v1.json", "inferences"),
        ("strategic-memory.v1.json", "items"),
        ("strategic-intelligence.v1.json", "recommendations"),
    )
    for name, field in collections:
        value = specs.get(name, {}).get(field, [])
        if isinstance(value, list) and any(not isinstance(item, dict) for item in value):
            findings.append(Finding("intelligence-shape", name, f"{field} must contain objects"))
    nested_collections = (
        ("objective-optimizer.v1.json", "investments", ("dependencies", "affected_systems"), False),
        ("dashboard.v1.json", "views", ("metrics",), True),
        (
            "cross-domain-reasoning.v1.json",
            "inferences",
            ("source_evidence", "counterevidence", "affected_systems"),
            False,
        ),
        ("strategic-memory.v1.json", "items", ("evidence",), False),
        (
            "strategic-intelligence.v1.json",
            "recommendations",
            (
                "history",
                "required_investment_ids",
                "source_inference_ids",
                "evidence",
                "affected_systems",
            ),
            False,
        ),
    )
    for name, parent_field, fields, object_items in nested_collections:
        parents = specs.get(name, {}).get(parent_field, [])
        if not isinstance(parents, list):
            continue
        for parent in parents:
            if not isinstance(parent, dict):
                continue
            for field in fields:
                value = parent.get(field)
                string_items = not object_items and not (
                    name == "cross-domain-reasoning.v1.json" and field == "source_evidence"
                )
                if (
                    not isinstance(value, list)
                    or (object_items and any(not isinstance(item, dict) for item in value))
                    or (
                        isinstance(value, list)
                        and string_items
                        and any(not isinstance(item, str) for item in value)
                    )
                ):
                    findings.append(
                        Finding(
                            "intelligence-shape", name, f"{parent_field}.{field} has wrong type"
                        )
                    )
    recommendations = specs.get("strategic-intelligence.v1.json", {}).get("recommendations", [])
    if isinstance(recommendations, list) and any(
        isinstance(item, dict) and not isinstance(item.get("review"), dict)
        for item in recommendations
    ):
        findings.append(
            Finding(
                "intelligence-shape",
                "strategic-intelligence.v1.json",
                "recommendation review must be an object",
            )
        )
    inferences = specs.get("cross-domain-reasoning.v1.json", {}).get("inferences", [])
    if isinstance(inferences, list) and any(
        isinstance(inference, dict)
        and isinstance(inference.get("source_evidence"), list)
        and any(not isinstance(source, dict) for source in inference["source_evidence"])
        for inference in inferences
    ):
        findings.append(
            Finding(
                "intelligence-shape",
                "cross-domain-reasoning.v1.json",
                "source evidence must contain objects",
            )
        )
    if any(item.check == "intelligence-shape" for item in findings):
        workflow = root / ".github" / "workflows" / "engineering-verification.yml"
        workflow_text = (
            workflow.read_text(encoding="utf-8")
            if (
                engineering_verify._inside(root, workflow)
                and workflow.is_file()
                and not workflow.is_symlink()
            )
            else ""
        )
        active_lines = {
            line.strip()
            for line in workflow_text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        checks += 1
        if "run: python tools/intelligence_verify.py --json" not in active_lines:
            findings.append(
                Finding(
                    "continuous-intelligence",
                    str(workflow.relative_to(root)),
                    "strategic intelligence verification absent from CI",
                )
            )
        canonical = json.dumps(
            {"specifications": specs, "findings": [asdict(item) for item in findings]},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        report = IntelligenceReport(
            False,
            checks,
            hashlib.sha256(canonical.encode()).hexdigest(),
            (),
            tuple(findings),
        )
        _validate_report(report)
        return report
    specification_ids: set[str] = set()
    for name, document in specs.items():
        identifier = document.get("specification_id")
        if not isinstance(identifier, str) or identifier in specification_ids:
            findings.append(Finding("identity", name, "missing or duplicate specification ID"))
        else:
            specification_ids.add(identifier)
        if document.get("status") != "approved":
            findings.append(Finding("approval", name, "specification is not approved"))

    evidence: dict[str, str] = {}
    for item in specs.get("evidence.v1.json", {}).get("evidence", []):
        checks += 1
        key, digest = item.get("evidence_id"), item.get("hash")
        if (
            not isinstance(key, str)
            or key in evidence
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or not item.get("type")
        ):
            findings.append(Finding("evidence", str(key), "invalid identity, type, or hash"))
        else:
            evidence[key] = item["type"]

    governance = specs.get("cognitive-governance.v1.json", {})
    policy = governance.get("policy", {})
    required_explanation = {
        "claim",
        "source_evidence",
        "reasoning_rule",
        "confidence",
        "counterevidence",
        "affected_systems",
    }
    prohibited = {
        "constitutional-amendment",
        "human-authority-grant",
        "production-secret-access",
        "autonomous-funding",
        "autonomous-deployment",
    }
    mandatory = {
        "investment-prioritization",
        "organizational-restructure",
        "technology-retirement",
        "policy-change",
        "high-risk-architecture",
    }
    if (
        evidence.get(str(governance.get("approval_evidence_id"))) != "human-governance-approval"
        or policy.get("minimum_evidence_sources") != 2
        or policy.get("minimum_distinct_domains") != 2
        or policy.get("confidence_minimum") != 0.5
        or policy.get("confidence_maximum") != 0.95
        or set(policy.get("explanation_fields", [])) != required_explanation
        or set(policy.get("prohibited_recommendation_domains", [])) != prohibited
        or set(policy.get("mandatory_human_review_categories", [])) != mandatory
        or policy.get("abstain_below_threshold") is not True
        or policy.get("conflicts_block_recommendation") is not True
        or policy.get("model_output_trusted") is not False
    ):
        findings.append(
            Finding(
                "cognitive-governance",
                "cognitive-governance.v1.json",
                "evidence, confidence, explanation, prohibition, or abstention weakened",
            )
        )

    optimizer = specs.get("objective-optimizer.v1.json", {})
    weights = optimizer.get("weights", {})
    required_weights = {
        "expected_value",
        "confidence",
        "risk_inverse",
        "capacity_fit",
        "constraint_fit",
    }
    numeric_weights = all(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in weights.values()
    )
    optimizer_fields = {
        "specification_id",
        "version",
        "status",
        "objective_evidence_id",
        "capacity_evidence_id",
        "dependency_evidence_id",
        "capacity_budget",
        "dependency_declarations_complete",
        "weights",
        "investments",
        "authority",
    }
    if (
        set(optimizer) != optimizer_fields
        or set(weights) != required_weights
        or not numeric_weights
        or not math.isclose(
            sum(weights.values()) if numeric_weights else -1, 1.0, rel_tol=0.0, abs_tol=1e-12
        )
        or any(isinstance(value, (int, float)) and value < 0 for value in weights.values())
        or evidence.get(str(optimizer.get("objective_evidence_id"))) != "human-approved-strategy"
        or evidence.get(str(optimizer.get("capacity_evidence_id"))) != "capacity-snapshot"
        or optimizer.get("dependency_evidence_id") not in evidence
        or optimizer.get("dependency_declarations_complete") is not True
        or not isinstance(optimizer.get("capacity_budget"), (int, float))
        or isinstance(optimizer.get("capacity_budget"), bool)
        or optimizer.get("capacity_budget", 0) <= 0
    ):
        findings.append(
            Finding(
                "objective-optimizer",
                "objective-optimizer.v1.json",
                "weights or approved objective/capacity evidence invalid",
            )
        )
    investments = optimizer.get("investments", [])
    investment_ids = {item.get("investment_id") for item in investments}
    ranking: list[dict[str, Any]] = []
    for item in investments:
        checks += 1
        values = [
            item.get("expected_value"),
            item.get("risk"),
            item.get("required_capacity"),
            item.get("available_capacity"),
            item.get("constraint_fit"),
        ]
        investment_fields = {
            "investment_id",
            "expected_value",
            "confidence",
            "risk",
            "required_capacity",
            "available_capacity",
            "constraint_fit",
            "dependencies",
            "affected_systems",
            "status",
        }
        if (
            set(item) != investment_fields
            or len(investment_ids) != len(investments)
            or set(item.get("dependencies", [])) - investment_ids
            or any(
                not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0
                for value in values
            )
            or any(
                item.get(field, 101) > 100 for field in ("expected_value", "risk", "constraint_fit")
            )
            or not 0 <= item.get("confidence", -1) <= 1
            or item.get("available_capacity") != optimizer.get("capacity_budget")
            or item.get("required_capacity", 1) > item.get("available_capacity", 0)
            or item.get("status") != "candidate"
        ):
            findings.append(
                Finding(
                    "investment",
                    str(item.get("investment_id")),
                    "duplicate, infeasible, dangling, or pre-decided investment",
                )
            )
            continue
        score = (
            weights["expected_value"] * item["expected_value"] / 100
            + weights["confidence"] * item["confidence"]
            + weights["risk_inverse"] * (1 - item["risk"] / 100)
            + weights["capacity_fit"] * (1 - item["required_capacity"] / item["available_capacity"])
            + weights["constraint_fit"] * item["constraint_fit"] / 100
        )
        ranking.append(
            {
                "investment_id": item["investment_id"],
                "score": round(score, 8),
                "dependencies": item["dependencies"],
            }
        )
    ranking.sort(key=lambda item: (-item["score"], item["investment_id"]))
    for cycle in _cycles(investments, "investment_id", "dependencies"):
        findings.append(Finding("investment-cycle", "objective-optimizer.v1.json", cycle))
    if optimizer.get("authority") != {
        "recommendations_only": True,
        "final_prioritization": "external-human-governance",
        "automatic_funding": False,
        "automatic_execution": False,
    }:
        findings.append(
            Finding(
                "optimizer-authority",
                "objective-optimizer.v1.json",
                "optimizer can prioritize, fund, or execute autonomously",
            )
        )

    dashboard = specs.get("dashboard.v1.json", {})
    views = dashboard.get("views", [])
    view_ids = {item.get("view_id") for item in views}
    if view_ids != set(REQUIRED_VIEWS) or len(views) != len(REQUIRED_VIEWS):
        findings.append(Finding("dashboard", "dashboard.v1.json", "required views missing"))
    for view in dashboard.get("views", []):
        metrics = view.get("metrics", [])
        checks += len(metrics)
        if (
            len(metrics) != len(REQUIRED_VIEWS.get(view.get("view_id"), set()))
            or {item.get("metric_id") for item in metrics}
            != REQUIRED_VIEWS.get(view.get("view_id"), set())
            or any(
                set(item)
                != {"metric_id", "evidence_id", "confidence", "counterevidence", "classification"}
                or item.get("evidence_id") not in evidence
                or not isinstance(item.get("confidence"), (int, float))
                or isinstance(item.get("confidence"), bool)
                or not 0 <= item.get("confidence", -1) <= 1
                or not isinstance(item.get("counterevidence"), list)
                or set(item.get("counterevidence", [])) - set(evidence)
                or item.get("classification") not in {"internal", "restricted"}
                for item in metrics
            )
        ):
            findings.append(
                Finding(
                    "dashboard", str(view.get("view_id")), "metric set or provenance incomplete"
                )
            )
    if dashboard.get("requirements") != {
        "provenance_per_metric": True,
        "confidence_visible": True,
        "counterevidence_visible": True,
        "classification_filtering": True,
        "authorization_before_aggregation": True,
        "recommendations_not_decisions": True,
    }:
        findings.append(
            Finding(
                "dashboard-governance",
                "dashboard.v1.json",
                "provenance, explanation, filtering, or authority boundary weakened",
            )
        )

    reasoning = specs.get("cross-domain-reasoning.v1.json", {})
    inference_ids: set[str] = set()
    allowed_domains = set(reasoning.get("domains", []))
    for inference in reasoning.get("inferences", []):
        checks += 1
        sources = inference.get("source_evidence", [])
        domains = {item.get("domain") for item in sources}
        evidence_ids = [item.get("evidence_id") for item in sources]
        inference_fields = {
            "inference_id",
            "claim",
            "source_evidence",
            "reasoning_rule",
            "confidence",
            "counterevidence",
            "causality_claimed",
            "affected_systems",
            "status",
        }
        if (
            set(inference) != inference_fields
            or inference.get("inference_id") in inference_ids
            or len(sources) < policy.get("minimum_evidence_sources", 999)
            or len(domains) < policy.get("minimum_distinct_domains", 999)
            or set(evidence_ids) - set(evidence)
            or len(evidence_ids) != len(set(evidence_ids))
            or not domains <= allowed_domains
            or not policy.get("confidence_minimum", 1)
            <= inference.get("confidence", -1)
            <= policy.get("confidence_maximum", 0)
            or not inference.get("counterevidence")
            or set(inference.get("counterevidence", [])) - set(evidence)
            or inference.get("causality_claimed") is not False
            or inference.get("status") != "candidate-insight"
            or not required_explanation <= set(inference)
        ):
            findings.append(
                Finding(
                    "cross-domain-reasoning",
                    str(inference.get("inference_id")),
                    "evidence diversity, confidence, explanation, or causality invalid",
                )
            )
        inference_ids.add(inference.get("inference_id"))

    memory = specs.get("strategic-memory.v1.json", {})
    memory_items = memory.get("items", [])
    memory_ids = {item.get("memory_id") for item in memory_items}
    memory_hashes: set[str] = set()
    for item in memory_items:
        checks += 1
        digest = item.get("memory_hash")
        hash_payload = {key: value for key, value in item.items() if key != "memory_hash"}
        expected_hash = hashlib.sha256(
            json.dumps(
                hash_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()
        try:
            recorded = datetime.fromisoformat(str(item.get("recorded_at")).replace("Z", "+00:00"))
            valid_from = datetime.fromisoformat(str(item.get("valid_from")).replace("Z", "+00:00"))
            dates_valid = recorded <= valid_from
            if item.get("valid_until") is not None:
                dates_valid = dates_valid and valid_from < datetime.fromisoformat(
                    str(item.get("valid_until")).replace("Z", "+00:00")
                )
        except ValueError:
            dates_valid = False
        memory_fields = {
            "memory_id",
            "memory_type",
            "statement",
            "recorded_at",
            "valid_from",
            "valid_until",
            "temporal_status",
            "evidence",
            "classification",
            "memory_hash",
            "supersedes",
        }
        if (
            set(item) != memory_fields
            or len(memory_ids) != len(memory_items)
            or not isinstance(digest, str)
            or digest != expected_hash
            or digest in memory_hashes
            or not item.get("evidence")
            or set(item.get("evidence", [])) - set(evidence)
            or item.get("temporal_status")
            not in {"current", "stale", "superseded", "expired", "withdrawn", "disputed"}
            or item.get("supersedes") == item.get("memory_id")
            or item.get("supersedes") not in memory_ids | {None}
            or not dates_valid
        ):
            findings.append(
                Finding(
                    "strategic-memory",
                    str(item.get("memory_id")),
                    "identity, evidence, temporal state, hash, or supersession invalid",
                )
            )
        if isinstance(digest, str):
            memory_hashes.add(digest)
    if memory.get("policy") != {
        "immutable_items": True,
        "versioned_corrections": True,
        "evidence_required": True,
        "contradictions_explicit": True,
        "expiry_evaluated": True,
        "raw_reasoning_forbidden": True,
        "retention_years": 10,
    }:
        findings.append(
            Finding(
                "strategic-memory-policy",
                "strategic-memory.v1.json",
                "immutability, evidence, contradiction, expiry, or reasoning boundary weakened",
            )
        )

    intelligence = specs.get("strategic-intelligence.v1.json", {})
    lifecycle = intelligence.get("lifecycle", [])
    required_capabilities = {
        "strategic-recommendations",
        "investment-analysis",
        "enterprise-simulations",
        "organizational-diagnostics",
        "long-term-forecasting",
        "capability-roadmaps",
        "executive-decision-support",
    }
    if set(intelligence.get("capabilities", [])) != required_capabilities:
        findings.append(
            Finding(
                "intelligence-layer",
                "strategic-intelligence.v1.json",
                "strategic capability surface incomplete",
            )
        )
    for recommendation in intelligence.get("recommendations", []):
        checks += 1
        history = recommendation.get("history", [])
        indexes = [lifecycle.index(item) for item in history if item in lifecycle]
        review = recommendation.get("review", {})
        required_ids = recommendation.get("required_investment_ids", [])
        portfolio_capacity = sum(
            item.get("required_capacity", 0)
            for item in investments
            if item.get("investment_id") in required_ids
        )
        recommendation_fields = {
            "recommendation_id",
            "category",
            "objective",
            "expected_benefit",
            "confidence",
            "risk",
            "affected_systems",
            "required_investment_ids",
            "source_inference_ids",
            "evidence",
            "proposed_by",
            "status",
            "history",
            "review",
            "authority",
        }
        if (
            set(recommendation) != recommendation_fields
            or set(review) != {"actor_type", "actor_id", "evidence_id"}
            or not history
            or recommendation.get("status") != history[-1]
            or len(indexes) != len(history)
            or any(second != first + 1 for first, second in pairwise(indexes))
            or len(required_ids) != len(set(required_ids))
            or set(required_ids) - investment_ids
            or portfolio_capacity > optimizer.get("capacity_budget", 0)
            or set(recommendation.get("source_inference_ids", [])) - inference_ids
            or set(recommendation.get("evidence", [])) - set(evidence)
            or not isinstance(recommendation.get("confidence"), (int, float))
            or isinstance(recommendation.get("confidence"), bool)
            or recommendation.get("confidence", -1) < policy.get("confidence_minimum", 1)
            or recommendation.get("confidence", 2) > policy.get("confidence_maximum", 0)
            or recommendation.get("authority") != "advisory-only"
            or recommendation.get("category") not in mandatory
            or review.get("actor_type") != "human"
            or review.get("actor_id") == recommendation.get("proposed_by")
            or evidence.get(review.get("evidence_id")) != "human-review"
        ):
            findings.append(
                Finding(
                    "strategic-recommendation",
                    str(recommendation.get("recommendation_id")),
                    "lineage, confidence, evidence, review, or authority invalid",
                )
            )
    if intelligence.get("layer_boundaries") != {
        "operational_layer": "executes-approved-work",
        "governance_layer": "determines-permitted-actions",
        "cognitive_layer": "proposes-considerations",
        "cognitive_execution_authority": False,
        "cognitive_approval_authority": False,
    }:
        findings.append(
            Finding(
                "layer-boundary",
                "strategic-intelligence.v1.json",
                "cognition, governance, and execution are not separated",
            )
        )

    workflow = root / ".github" / "workflows" / "engineering-verification.yml"
    workflow_text = (
        workflow.read_text(encoding="utf-8")
        if (
            engineering_verify._inside(root, workflow)
            and workflow.is_file()
            and not workflow.is_symlink()
        )
        else ""
    )
    lines = {
        line.strip()
        for line in workflow_text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    checks += 1
    if "run: python tools/intelligence_verify.py --json" not in lines:
        findings.append(
            Finding(
                "continuous-intelligence",
                str(workflow.relative_to(root)),
                "strategic intelligence verification absent from CI",
            )
        )
    canonical = json.dumps(
        {
            "specifications": specs,
            "investment_ranking": ranking,
            "ci_workflow_hash": hashlib.sha256(workflow_text.encode()).hexdigest(),
            "findings": [asdict(item) for item in findings],
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    report = IntelligenceReport(
        not findings,
        checks,
        hashlib.sha256(canonical.encode()).hexdigest(),
        tuple(ranking),
        tuple(findings),
    )
    _validate_report(report)
    return report


def _schema() -> dict[str, Any]:
    for candidate in Path(__file__).resolve().parents:
        schema_path = candidate / INTELLIGENCE_REPORT_SCHEMA_REF
        if schema_path.is_file():
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)
            return schema
    raise RuntimeError(f"{INTELLIGENCE_REPORT_SCHEMA_REF} schema file is missing")


def _report_document(report: IntelligenceReport) -> dict[str, Any]:
    return json.loads(json.dumps(asdict(report), sort_keys=True))


def _validate_report(report: IntelligenceReport) -> None:
    try:
        jsonschema.validate(_report_document(report), _schema())
    except jsonschema.ValidationError as exc:
        raise RuntimeError(
            f"{INTELLIGENCE_REPORT_SCHEMA_REF}: generated intelligence verification report "
            f"does not validate: {exc.message}"
        ) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    report = verify(args.root)
    print(
        json.dumps(_report_document(report), sort_keys=True)
        if args.as_json
        else f"P16 governed intelligence: {'PASS' if report.conformant else 'FAIL'} "
        f"({report.checks} checks, evidence {report.evidence_hash})"
    )
    return 0 if report.conformant else 1


if __name__ == "__main__":
    sys.exit(main())
