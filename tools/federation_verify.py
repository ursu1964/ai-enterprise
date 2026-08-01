#!/usr/bin/env python3
"""Deterministic security and conformance verifier for governed enterprise federation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import engineering_verify

SPEC_FILES = (
    "evidence.v1.json",
    "regulatory.v1.json",
    "multi-cloud.v1.json",
    "external-events.v1.json",
    "ecosystem-graph.v1.json",
    "dashboard.v1.json",
    "protocol.v1.json",
)
REQUIRED_VIEWS = {
    "partner-health",
    "supply-chain",
    "federation",
    "regulatory",
    "external-operations",
}
REQUIRED_VIEW_METRICS = {
    "partner-health": {
        "integration-status",
        "sla-compliance",
        "contract-version",
        "trust-level",
    },
    "supply-chain": {
        "approved-dependencies",
        "vulnerable-components",
        "pending-updates",
        "licensing-issues",
    },
    "federation": {
        "participating-enterprises",
        "shared-capabilities",
        "cross-enterprise-workflows",
    },
    "regulatory": {
        "jurisdiction-coverage",
        "policy-compliance",
        "outstanding-obligations",
    },
    "external-operations": {
        "provider-health",
        "cloud-utilization",
        "connector-status",
        "synchronization-latency",
    },
}
CLASSIFICATION = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
REQUIRED_PROTOCOL_STAGES = [
    "identity-exchange",
    "capability-discovery",
    "contract-negotiation",
    "evidence-sharing",
    "workflow-delegation",
    "audit-interoperability",
    "policy-negotiation",
    "trust-establishment",
]


@dataclass(frozen=True, slots=True)
class Finding:
    check: str
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class FederationReport:
    conformant: bool
    checks: int
    evidence_hash: str
    findings: tuple[Finding, ...]


def _load(root: Path, findings: list[Finding]) -> dict[str, dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    for name in SPEC_FILES:
        path = root / "specifications" / "federation" / name
        try:
            if not engineering_verify._inside(root, path) or path.is_symlink():
                raise ValueError("must be a regular in-repository file")
            documents[name] = engineering_verify._strict_json(path)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            findings.append(Finding("federation-specification", str(path), str(exc)))
    return documents


def verify(root: Path) -> FederationReport:
    root = root.resolve()
    findings: list[Finding] = []
    specs = _load(root, findings)
    checks = len(SPEC_FILES)
    ids: set[str] = set()
    for name, document in specs.items():
        identifier = document.get("specification_id")
        if not isinstance(identifier, str) or identifier in ids:
            findings.append(
                Finding("identity", name, "missing or duplicate specification ID")
            )
        else:
            ids.add(identifier)
        if document.get("status") != "approved":
            findings.append(Finding("approval", name, "specification is not approved"))

    evidence_items = specs.get("evidence.v1.json", {}).get("evidence", [])
    evidence: dict[str, str] = {}
    for item in evidence_items:
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
            findings.append(
                Finding("evidence", str(key), "invalid identity, type, or hash")
            )
        else:
            evidence[key] = item["type"]

    regulatory = specs.get("regulatory.v1.json", {})
    modules = regulatory.get("modules", [])
    module_ids = {item.get("module_id") for item in modules}
    for module in modules:
        checks += 1
        if (
            not module.get("jurisdictions")
            or not module.get("customer_classes")
            or not module.get("workload_classes")
            or not module.get("obligations")
            or module.get("evidence_id") not in evidence
            or evidence.get(module.get("evidence_id")) != "approved-legal-analysis"
            or module.get("approval") != "human-legal-approved"
        ):
            findings.append(
                Finding(
                    "regulatory-module",
                    str(module.get("module_id")),
                    "module lacks scope, obligations, or legal approval evidence",
                )
            )
    for deployment in regulatory.get("deployments", []):
        checks += 1
        applicable = {
            module["module_id"]
            for module in modules
            if (
                deployment.get("location") in module.get("jurisdictions", [])
                or "GLOBAL" in module.get("jurisdictions", [])
            )
            and (
                deployment.get("customer_class") in module.get("customer_classes", [])
                or "all" in module.get("customer_classes", [])
            )
            and set(deployment.get("workload_classes", []))
            & set(module.get("workload_classes", []))
        }
        inherited = set(deployment.get("inherited_modules", []))
        if (
            not applicable
            or inherited - module_ids
            or applicable - inherited
            or evidence.get(deployment.get("classification_evidence_id"))
            != "deployment-classification"
        ):
            findings.append(
                Finding(
                    "regulatory-inheritance",
                    str(deployment.get("deployment_id")),
                    "applicable regulatory modules are missing or unknown",
                )
            )
    if regulatory.get("default") != "deny-unclassified-deployment":
        findings.append(
            Finding("regulatory-default", "regulatory.v1.json", "default is not deny")
        )

    cloud = specs.get("multi-cloud.v1.json", {})
    providers = {item.get("provider_id"): item for item in cloud.get("providers", [])}
    regulatory_deployments = {
        item.get("deployment_id"): item for item in regulatory.get("deployments", [])
    }
    if set(cloud.get("targets", [])) != {"aws", "azure", "gcp", "on-premises", "edge"}:
        findings.append(
            Finding("multi-cloud", "multi-cloud.v1.json", "provider targets incomplete")
        )
    for workload in cloud.get("workloads", []):
        checks += 1
        selected = [
            workload.get("primary_provider"),
            *workload.get("fallback_providers", []),
        ]
        required = set(workload.get("required_jurisdictions", []))
        regulatory_deployment = regulatory_deployments.get(
            workload.get("regulatory_deployment_id")
        )
        if (
            len(selected) != len(set(selected))
            or any(item not in providers for item in selected)
            or any(
                not required <= set(providers[item].get("jurisdictions", []))
                for item in selected
                if item in providers
            )
            or any(
                evidence.get(providers[item].get("jurisdiction_evidence_id"))
                != "provider-jurisdiction-attestation"
                for item in selected
                if item in providers
            )
            or not regulatory_deployment
            or regulatory_deployment.get("location") not in required
            or workload.get("generator_evidence_id") not in evidence
            or workload.get("automatic_failover") is not False
            or workload.get("human_activation_required") is not True
        ):
            findings.append(
                Finding(
                    "multi-cloud",
                    str(workload.get("workload_id")),
                    "placement, failover, generator evidence, or jurisdiction unsafe",
                )
            )
    if cloud.get("failover_policy") != [
        "verify-provider-health",
        "verify-jurisdiction",
        "verify-regulatory-inheritance",
        "verify-data-residency",
        "obtain-human-approval",
        "record-audit",
        "activate-fallback",
    ]:
        findings.append(
            Finding(
                "multi-cloud-failover",
                "multi-cloud.v1.json",
                "ordered failover policy is incomplete or bypassable",
            )
        )

    events = specs.get("external-events.v1.json", {})
    required_envelope = {
        "event_id",
        "event_type",
        "occurred_at",
        "correlation_id",
        "causation_id",
        "issuer",
        "organization",
        "payload",
        "schema_version",
        "signature",
        "signature_algorithm",
        "key_id",
        "nonce",
    }
    required_pipeline = [
        "authenticate-issuer",
        "verify-signature",
        "reject-replay",
        "validate-time-window",
        "validate-schema",
        "evaluate-policy",
        "classify-payload",
        "create-candidate-enterprise-event",
    ]
    checks += 1
    envelope = events.get("required_envelope", [])
    signed_fields = events.get("signed_fields", [])
    if (
        set(envelope) != required_envelope
        or len(envelope) != len(required_envelope)
        or events.get("gateway_pipeline") != required_pipeline
        or events.get("accepted_algorithms") != ["Ed25519"]
        or events.get("signature_canonicalization") != "jcs-rfc8785"
        or set(signed_fields) != required_envelope - {"signature"}
        or len(signed_fields) != len(required_envelope) - 1
        or events.get("occurred_at_format") != "UTC-RFC3339"
        or events.get("replay_cache_required") is not True
        or events.get("replay_policy")
        != {
            "key": ["issuer", "key_id", "nonce"],
            "retention_seconds": 86400,
            "atomic_insert_required": True,
        }
        or events.get("direct_internal_state_mutation") is not False
        or not isinstance(events.get("maximum_clock_skew_seconds"), int)
        or not 1 <= events.get("maximum_clock_skew_seconds", 0) <= 300
    ):
        findings.append(
            Finding(
                "external-events",
                "external-events.v1.json",
                "gateway envelope, ordering, cryptography, replay, or state safety weakened",
            )
        )
    graph = specs.get("ecosystem-graph.v1.json", {})
    node_items = graph.get("nodes", [])
    nodes = {item.get("node_id"): item for item in node_items}
    event_identities: set[tuple[str, str]] = set()
    for schema in events.get("schemas", []):
        identity = (str(schema.get("event_type")), str(schema.get("schema_version")))
        if (
            schema.get("contract_evidence_id") not in evidence
            or evidence.get(schema.get("contract_evidence_id")) != "signed-contract"
            or schema.get("permitted_result") != "candidate-event"
            or schema.get("issuer") not in nodes
            or nodes.get(schema.get("issuer"), {}).get("type") != "partner"
            or identity in event_identities
        ):
            findings.append(
                Finding(
                    "external-event-schema",
                    str(schema.get("event_type")),
                    "schema lacks contract evidence or permits trusted state",
                )
            )
        event_identities.add(identity)

    if len(nodes) != len(node_items):
        findings.append(
            Finding("graph-node", "ecosystem-graph.v1.json", "duplicate node identity")
        )
    edge_ids: set[str] = set()
    for node in nodes.values():
        checks += 1
        if (
            node.get("evidence_id") not in evidence
            or node.get("classification") not in CLASSIFICATION
            or not node.get("visibility_scope")
        ):
            findings.append(
                Finding("graph-node", str(node.get("node_id")), "evidence missing")
            )
    for edge in graph.get("edges", []):
        checks += 1
        edge_id = edge.get("edge_id")
        source, target = nodes.get(edge.get("source")), nodes.get(edge.get("target"))
        if (
            edge_id in edge_ids
            or source is None
            or target is None
            or edge.get("source") == edge.get("target")
            or edge.get("relationship") not in graph.get("allowed_relationships", [])
            or edge.get("evidence_id") not in evidence
            or edge.get("visibility_scope") != source.get("visibility_scope")
            or edge.get("visibility_scope") != target.get("visibility_scope")
            or CLASSIFICATION.get(str(edge.get("classification")), -1)
            < max(
                CLASSIFICATION.get(str(source.get("classification")), 99),
                CLASSIFICATION.get(str(target.get("classification")), 99),
            )
        ):
            findings.append(
                Finding(
                    "graph-edge",
                    str(edge_id),
                    "duplicate, dangling, unsupported, or unevidenced edge",
                )
            )
        edge_ids.add(edge_id)
    if graph.get("external_claims_trusted_by_default") is not False:
        findings.append(
            Finding(
                "graph-trust",
                "ecosystem-graph.v1.json",
                "external graph claims are trusted automatically",
            )
        )

    dashboard = specs.get("dashboard.v1.json", {})
    views = dashboard.get("views", [])
    if {item.get("view_id") for item in views} != REQUIRED_VIEWS:
        findings.append(
            Finding(
                "dashboard", "dashboard.v1.json", "required executive views missing"
            )
        )
    metric_ids: set[tuple[str, str]] = set()
    for view in views:
        view_id = str(view.get("view_id"))
        if {
            item.get("metric_id") for item in view.get("metrics", [])
        } != REQUIRED_VIEW_METRICS.get(view_id, set()):
            findings.append(
                Finding("dashboard", view_id, "required view metrics missing or added")
            )
        for metric in view.get("metrics", []):
            checks += 1
            identity = (str(view.get("view_id")), str(metric.get("metric_id")))
            if identity in metric_ids or metric.get("evidence_id") not in evidence:
                findings.append(
                    Finding(
                        "dashboard-metric",
                        ".".join(identity),
                        "duplicate metric or immutable evidence missing",
                    )
                )
            metric_ids.add(identity)
    if dashboard.get("requirements") != {
        "immutable_evidence": True,
        "classification_filtering": True,
        "authorization_before_aggregation": True,
        "relational_scope_filtering": True,
        "jurisdiction_filtering": True,
        "provenance_in_every_result": True,
        "raw_secrets_forbidden": True,
        "aggregation_minimum_group_size": 5,
    }:
        findings.append(
            Finding(
                "dashboard-security",
                "dashboard.v1.json",
                "evidence, classification, authorization, or secret controls weakened",
            )
        )

    protocol = specs.get("protocol.v1.json", {})
    checks += 1
    if (
        protocol.get("stages") != REQUIRED_PROTOCOL_STAGES
        or protocol.get("identity")
        != {
            "mutual_authentication": True,
            "signed_challenge": True,
            "key_rotation": True,
        }
        or protocol.get("delegation")
        != {
            "local_authority_evaluation_required": True,
            "scope_and_expiry_required": True,
            "capability_subset_required": True,
            "receiving_authority_ceiling_required": True,
            "transitive_delegation": False,
            "redelegation": False,
            "maximum_hops": 1,
        }
        or protocol.get("trust")
        != {
            "measured": True,
            "substitutes_for_validation": False,
            "inherited_authority": False,
        }
        or protocol.get("sovereignty")
        != {
            "local_policy_precedence": True,
            "local_approval_required": True,
            "local_evidence_retained": True,
            "remote_state_mutation": False,
        }
        or protocol.get("negotiation")
        != {
            "local_rejection_supported": True,
            "policy_conflict_result": "deny",
            "contract_downgrade_allowed": False,
            "classification_downgrade_allowed": False,
        }
        or protocol.get("failure")
        != {
            "fail_closed": True,
            "replay_protection": True,
            "audit_required": True,
            "revocation_supported": True,
        }
    ):
        findings.append(
            Finding(
                "federation-protocol",
                "protocol.v1.json",
                "identity, delegation, trust, sovereignty, or failure controls weakened",
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
    if "run: python tools/federation_verify.py --json" not in lines:
        findings.append(
            Finding(
                "continuous-federation",
                str(workflow.relative_to(root)),
                "federation verification absent from CI",
            )
        )
    canonical = json.dumps(
        {
            "specifications": specs,
            "ci_workflow_hash": hashlib.sha256(workflow_text.encode()).hexdigest(),
            "findings": [asdict(item) for item in findings],
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return FederationReport(
        not findings,
        checks,
        hashlib.sha256(canonical.encode()).hexdigest(),
        tuple(findings),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    report = verify(args.root)
    print(
        json.dumps(asdict(report), sort_keys=True)
        if args.as_json
        else f"P15 governed federation: {'PASS' if report.conformant else 'FAIL'} "
        f"({report.checks} checks, evidence {report.evidence_hash})"
    )
    return 0 if report.conformant else 1


if __name__ == "__main__":
    sys.exit(main())
