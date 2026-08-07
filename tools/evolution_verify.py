#!/usr/bin/env python3
"""Deterministic verifier for governed enterprise capability and organizational evolution."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict, dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

import engineering_verify
import jsonschema

EVOLUTION_REPORT_SCHEMA_REF = "schemas/release-artifacts/evolution-verification-report.schema.json"
SPEC_FILES = (
    "evidence.v1.json",
    "capabilities.v1.json",
    "maturity.v1.json",
    "benchmarks.v1.json",
    "roadmap.v1.json",
    "refactoring.v1.json",
    "reflection.v1.json",
)
MINIMUM_MATURITY_EVIDENCE = {
    "architecture": 2,
    "testing": 1,
    "security": 1,
    "automation": 1,
    "documentation": 1,
    "operations": 1,
    "governance": 1,
    "observability": 1,
    "reuse": 1,
    "reliability": 1,
}
MATURITY_SOURCE_TYPES = {
    "architecture": {"architecture-standard", "test-report"},
    "testing": {"test-report"},
    "security": {"policy-report", "test-report"},
    "automation": {"ci-report"},
    "documentation": {"documentation-report"},
    "operations": {"operations-report"},
    "governance": {"governance-report"},
    "observability": {"observability-report"},
    "reuse": {"reuse-report"},
    "reliability": {"reliability-report", "recovery-test"},
}


@dataclass(frozen=True, slots=True)
class Finding:
    check: str
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class EvolutionReport:
    conformant: bool
    checks: int
    evidence_hash: str
    maturity: dict[str, int]
    benchmark_opportunities: tuple[dict[str, Any], ...]
    findings: tuple[Finding, ...]
    schema_version: str = "1.0"
    schema_ref: str = EVOLUTION_REPORT_SCHEMA_REF


def _load(root: Path, findings: list[Finding]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name in SPEC_FILES:
        path = root / "specifications" / "evolution" / name
        try:
            if not engineering_verify._inside(root, path) or path.is_symlink():
                raise ValueError("must be a regular in-repository file")
            result[name] = engineering_verify._strict_json(path)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            findings.append(Finding("evolution-specification", str(path), str(exc)))
    return result


def _roadmap_cycles(proposals: list[dict[str, Any]]) -> tuple[str, ...]:
    graph = {item["proposal_id"]: tuple(item.get("dependencies", ())) for item in proposals}
    cycles: set[str] = set()
    visiting: list[str] = []
    visited: set[str] = set()

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


def verify(root: Path) -> EvolutionReport:
    root = root.resolve()
    findings: list[Finding] = []
    specs = _load(root, findings)
    checks = len(SPEC_FILES)
    identifiers: set[str] = set()
    for name, document in specs.items():
        identifier = document.get("specification_id")
        if not isinstance(identifier, str) or identifier in identifiers:
            findings.append(Finding("identity", name, "missing or duplicate specification ID"))
        else:
            identifiers.add(identifier)
        if document.get("status") != "approved":
            findings.append(Finding("approval", name, "specification must be approved"))

    catalog_items = specs.get("evidence.v1.json", {}).get("evidence", [])
    catalog: dict[str, str] = {}
    catalog_types: dict[str, str] = {}
    checks += len(catalog_items)
    for item in catalog_items:
        evidence_id, source_hash = item.get("evidence_id"), item.get("source_hash")
        if (
            not isinstance(evidence_id, str)
            or evidence_id in catalog
            or not isinstance(source_hash, str)
            or len(source_hash) != 64
            or any(character not in "0123456789abcdef" for character in source_hash)
            or not item.get("source_type")
        ):
            findings.append(
                Finding(
                    "evidence-catalog",
                    str(evidence_id),
                    "evidence identity, immutable hash, or type is invalid",
                )
            )
        else:
            catalog[evidence_id] = source_hash
            catalog_types[evidence_id] = item["source_type"]

    capability_spec = specs.get("capabilities.v1.json", {})
    lifecycle = capability_spec.get("lifecycle", [])
    capabilities = capability_spec.get("capabilities", [])
    capability_ids = [item.get("capability_id") for item in capabilities]
    checks += len(capabilities) + 1
    if len(capability_ids) != len(set(capability_ids)):
        findings.append(Finding("capability", "capabilities.v1.json", "duplicate capability ID"))
    for item in capabilities:
        history = item.get("history", [])
        indexes = [lifecycle.index(state) for state in history if state in lifecycle]
        if (
            not history
            or item.get("state") != history[-1]
            or len(indexes) != len(history)
            or any(second != first + 1 for first, second in pairwise(indexes))
            or not item.get("evidence")
            or bool(set(item.get("evidence", [])) - set(catalog))
        ):
            findings.append(
                Finding(
                    "capability",
                    str(item.get("capability_id")),
                    "invalid lifecycle transition or missing evidence",
                )
            )
    authority = capability_spec.get("authority", {})
    if (
        authority.get("self_transition_allowed") is not False
        or authority.get("human_approval_required") is not True
    ):
        findings.append(
            Finding(
                "authority",
                "capabilities.v1.json",
                "capability transitions are not externally governed",
            )
        )

    maturity_spec = specs.get("maturity.v1.json", {})
    maturity: dict[str, int] = {}
    dimensions = maturity_spec.get("dimensions", [])
    required_dimensions = {
        "architecture",
        "testing",
        "security",
        "automation",
        "documentation",
        "operations",
        "governance",
        "observability",
        "reuse",
        "reliability",
    }
    checks += len(dimensions)
    for dimension in dimensions:
        entries = dimension.get("evidence", [])
        evidence_ids = [entry.get("evidence_id") for entry in entries]
        scores = [entry.get("score") for entry in entries]
        valid = (
            scores
            and all(
                isinstance(score, int) and not isinstance(score, bool) and 0 <= score <= 5
                for score in scores
            )
            and len(evidence_ids) == len(set(evidence_ids))
            and not (set(evidence_ids) - set(catalog))
            and len(entries)
            >= MINIMUM_MATURITY_EVIDENCE.get(str(dimension.get("dimension_id")), 999)
            and all(
                catalog_types.get(str(evidence_id))
                in MATURITY_SOURCE_TYPES.get(str(dimension.get("dimension_id")), set())
                for evidence_id in evidence_ids
            )
        )
        calculated = math.floor(sum(scores) / len(scores)) if valid else -1
        maturity[str(dimension.get("dimension_id"))] = calculated
        if not valid or dimension.get("expected_level") != calculated:
            findings.append(
                Finding(
                    "maturity",
                    str(dimension.get("dimension_id")),
                    "level is not deterministically supported by evidence",
                )
            )
    if set(maturity) != required_dimensions:
        findings.append(Finding("maturity", "maturity.v1.json", "required dimensions missing"))

    benchmark_spec = specs.get("benchmarks.v1.json", {})
    metric_ids: set[str] = set()
    opportunities: list[dict[str, Any]] = []
    for metric in benchmark_spec.get("metrics", []):
        checks += 1
        metric_id = metric.get("metric_id")
        values = (
            metric.get("historical"),
            metric.get("current"),
            metric.get("objective"),
        )
        evidence_keys = (
            metric.get("historical_evidence_id"),
            metric.get("current_evidence_id"),
            metric.get("objective_evidence_id"),
        )
        if (
            metric_id in metric_ids
            or len(set(evidence_keys)) != 3
            or any(key not in catalog for key in evidence_keys)
            or catalog_types.get(str(evidence_keys[0])) != "metric-snapshot"
            or catalog_types.get(str(evidence_keys[1])) != "metric-snapshot"
            or catalog_types.get(str(evidence_keys[2])) != "approved-policy"
            or metric.get("direction") not in {"higher", "lower"}
            or any(
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
                for value in values
            )
        ):
            findings.append(Finding("benchmark", str(metric_id), "invalid metric or evidence"))
            continue
        metric_ids.add(metric_id)
        current, objective = float(metric["current"]), float(metric["objective"])
        remaining = objective - current if metric["direction"] == "higher" else current - objective
        denominator = max(abs(objective), 1.0)
        opportunities.append(
            {
                "metric_id": metric_id,
                "remaining_gap": max(0.0, remaining),
                "normalized_gap": round(max(0.0, remaining) / denominator, 6),
                "direction": metric["direction"],
                "evidence_id": metric["current_evidence_id"],
            }
        )
    opportunities.sort(key=lambda item: (-item["normalized_gap"], item["metric_id"]))
    benchmark_authority = benchmark_spec.get("authority", {})
    if (
        benchmark_authority.get("recommendations_only") is not True
        or benchmark_authority.get("automatic_investment_decisions") is not False
    ):
        findings.append(
            Finding(
                "authority",
                "benchmarks.v1.json",
                "benchmarks can make autonomous decisions",
            )
        )

    roadmap = specs.get("roadmap.v1.json", {}).get("proposals", [])
    proposal_ids = {item.get("proposal_id") for item in roadmap}
    checks += len(roadmap)
    if len(proposal_ids) != len(roadmap):
        findings.append(Finding("roadmap", "roadmap.v1.json", "duplicate proposal ID"))
    for proposal in roadmap:
        approval = proposal.get("approval")
        approved = proposal.get("decision_status") == "human-approved"
        if (
            set(proposal.get("dependencies", [])) - proposal_ids
            or not all(
                proposal.get(key)
                for key in (
                    "current_state",
                    "planned_improvement",
                    "investment",
                    "expected_outcomes",
                    "success_measures",
                )
            )
            or proposal.get("decision_status")
            not in {"human-approved", "awaiting-human-review", "rejected"}
        ):
            findings.append(
                Finding(
                    "roadmap",
                    str(proposal.get("proposal_id")),
                    "incomplete, dangling, or autonomously decided proposal",
                )
            )
        if set(proposal.get("success_measures", [])) - metric_ids:
            findings.append(
                Finding(
                    "roadmap",
                    str(proposal.get("proposal_id")),
                    "success measure lacks approved benchmark",
                )
            )
        if (
            proposal.get("dependency_attestation") is not True
            or proposal.get("dependency_evidence_id") not in catalog
            or catalog_types.get(str(proposal.get("dependency_evidence_id"))) != "review-report"
            or (
                approved
                and (
                    not isinstance(approval, dict)
                    or approval.get("actor_type") != "human"
                    or approval.get("evidence_id") not in catalog
                    or catalog_types.get(str(approval.get("evidence_id"))) != "human-approval"
                )
            )
        ):
            findings.append(
                Finding(
                    "roadmap-governance",
                    str(proposal.get("proposal_id")),
                    "dependency attestation or human approval evidence missing",
                )
            )
    for cycle in _roadmap_cycles(roadmap):
        findings.append(Finding("roadmap-cycle", "roadmap.v1.json", cycle))

    refactoring_spec = specs.get("refactoring.v1.json", {})
    policy = refactoring_spec.get("policy", {})
    if (
        any(
            policy.get(key) is not True
            for key in (
                "work_packages_required",
                "rollback_required",
                "independent_human_approval_required",
            )
        )
        or policy.get("self_execution_allowed") is not False
    ):
        findings.append(
            Finding(
                "refactoring-policy",
                "refactoring.v1.json",
                "refactoring authority or rollback controls weakened",
            )
        )
    for transformation in refactoring_spec.get("transformations", []):
        checks += 1
        approver = transformation.get("approver")
        rollback = transformation.get("rollback", {})
        proposal = next(
            (
                item
                for item in roadmap
                if item.get("proposal_id") == transformation.get("proposal_id")
            ),
            None,
        )
        if (
            not transformation.get("work_packages")
            or not rollback
            or not transformation.get("lineage")
            or approver == transformation.get("proposer")
            or not isinstance(approver, str)
            or approver.endswith("-agent")
            or transformation.get("proposal_id") not in proposal_ids
            or not proposal
            or proposal.get("decision_status") != "human-approved"
            or not isinstance(rollback.get("artifact_hash"), str)
            or len(rollback.get("artifact_hash", "")) != 64
            or not rollback.get("steps")
            or rollback.get("tested_evidence_id") not in catalog
            or catalog_types.get(str(rollback.get("tested_evidence_id"))) != "recovery-test"
            or not isinstance(rollback.get("maximum_recovery_minutes"), int)
            or rollback.get("maximum_recovery_minutes") <= 0
        ):
            findings.append(
                Finding(
                    "refactoring",
                    str(transformation.get("transformation_id")),
                    "missing lineage/rollback or independent human approval",
                )
            )

    reflection = specs.get("reflection.v1.json", {})
    required_loop = [
        "execute",
        "observe",
        "measure",
        "learn",
        "propose",
        "simulate",
        "review",
        "approve",
        "implement",
        "validate",
        "measure-again",
    ]
    if (
        reflection.get("schedule") not in {"monthly", "quarterly", "annual"}
        or len(reflection.get("questions", [])) < 6
        or reflection.get("evolution_loop") != required_loop
    ):
        findings.append(
            Finding(
                "reflection-process",
                "reflection.v1.json",
                "scheduled questions or governed evolution loop is incomplete",
            )
        )
    constraints = reflection.get("constraints", {})
    if constraints != {
        "recommendations_only": True,
        "autonomous_decisions": False,
        "autonomous_implementation": False,
        "human_approval_required": True,
    }:
        findings.append(
            Finding(
                "reflection-authority",
                "reflection.v1.json",
                "self-reflection can authorize or implement change",
            )
        )
    for recommendation in reflection.get("recommendations", []):
        checks += 1
        if (
            not recommendation.get("evidence")
            or bool(set(recommendation.get("evidence", [])) - set(catalog))
            or recommendation.get("roadmap_proposal_id") not in proposal_ids
            or recommendation.get("status") != "proposed"
            or recommendation.get("decision_authority") != "external-human-governance"
        ):
            findings.append(
                Finding(
                    "reflection",
                    str(recommendation.get("recommendation_id")),
                    "recommendation lacks evidence or external governance",
                )
            )

    workflow = root / ".github" / "workflows" / "engineering-verification.yml"
    safe_workflow = (
        engineering_verify._inside(root, workflow)
        and workflow.is_file()
        and not workflow.is_symlink()
    )
    workflow_text = workflow.read_text(encoding="utf-8") if safe_workflow else ""
    checks += 1
    ci_lines = {
        line.strip()
        for line in workflow_text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    if "run: python tools/evolution_verify.py --json" not in ci_lines:
        findings.append(
            Finding(
                "continuous-evolution",
                str(workflow.relative_to(root)),
                "governed evolution verification is absent from CI",
            )
        )

    canonical = json.dumps(
        {
            "specifications": specs,
            "maturity": maturity,
            "benchmark_opportunities": opportunities,
            "ci_workflow_hash": hashlib.sha256(workflow_text.encode()).hexdigest(),
            "findings": [asdict(item) for item in findings],
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    evidence_hash = hashlib.sha256(canonical.encode()).hexdigest()
    report = EvolutionReport(
        not findings,
        checks,
        evidence_hash,
        maturity,
        tuple(opportunities),
        tuple(findings),
    )
    _validate_report(report)
    return report


def _schema() -> dict[str, Any]:
    for candidate in Path(__file__).resolve().parents:
        schema_path = candidate / EVOLUTION_REPORT_SCHEMA_REF
        if schema_path.is_file():
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)
            return schema
    raise RuntimeError(f"{EVOLUTION_REPORT_SCHEMA_REF} schema file is missing")


def _report_document(report: EvolutionReport) -> dict[str, Any]:
    return json.loads(json.dumps(asdict(report), sort_keys=True))


def _validate_report(report: EvolutionReport) -> None:
    try:
        jsonschema.validate(_report_document(report), _schema())
    except jsonschema.ValidationError as exc:
        raise RuntimeError(
            f"{EVOLUTION_REPORT_SCHEMA_REF}: generated evolution verification report "
            f"does not validate: {exc.message}"
        ) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    report = verify(args.root)
    if args.as_json:
        print(json.dumps(_report_document(report), sort_keys=True))
    else:
        print(
            f"P14 governed evolution: {'PASS' if report.conformant else 'FAIL'} "
            f"({report.checks} checks, evidence {report.evidence_hash})"
        )
        for finding in report.findings:
            print(f"- [{finding.check}] {finding.path}: {finding.message}")
    return 0 if report.conformant else 1


if __name__ == "__main__":
    sys.exit(main())
