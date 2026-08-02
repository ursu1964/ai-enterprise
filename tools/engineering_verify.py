#!/usr/bin/env python3
"""P9 specification, contract, consistency, quality-gate, and determinism verifier."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import etra_conformance
import generate_engineering_artifacts

SPEC_FILES = (
    "infrastructure.v1.json",
    "configuration.v1.json",
    "security.v1.json",
    "contracts.v1.json",
    "quality-gates.v1.json",
    "determinism.v1.json",
)
REQUIRED_GATES = (
    "specification-complete",
    "static-validation",
    "generated-artifacts",
    "compilation",
    "unit-tests",
    "integration-tests",
    "contract-tests",
    "security-validation",
    "performance-validation",
    "independent-review",
    "promotion-eligibility",
)
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
SAFE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9.-]*$")
REQUIRED_INFRASTRUCTURE_TARGETS = {
    "compose",
    "kubernetes",
    "terraform",
    "monitoring",
    "networking",
    "secrets",
}
EXPECTED_GATE_COMMANDS = {
    "specification-complete": "python tools/engineering_verify.py --static",
    "static-validation": "ruff check",
    "generated-artifacts": "python tools/generate_engineering_artifacts.py --check",
    "compilation": "python -m compileall",
    "unit-tests": "pytest",
    "integration-tests": "pytest integration",
    "contract-tests": "pytest contract",
    "security-validation": "pytest security",
    "performance-validation": "pytest performance",
    "independent-review": "review evidence",
    "promotion-eligibility": "verify signed evidence",
}


@dataclass(frozen=True, slots=True)
class Finding:
    check: str
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class VerificationReport:
    conformant: bool
    checks: int
    evidence_hash: str
    findings: tuple[Finding, ...]


def _inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _strict_json(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        document: dict[str, Any] = {}
        for key, value in items:
            if key in document:
                raise ValueError(f"duplicate JSON key: {key}")
            document[key] = value
        return document

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"invalid number: {value}")
        ),
    )
    if not isinstance(value, dict):
        raise TypeError("specification must be an object")
    return value


def _load_specs(root: Path, findings: list[Finding]) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for name in SPEC_FILES:
        path = root / "specifications" / "engineering" / name
        try:
            if not _inside(root, path) or path.is_symlink():
                raise ValueError("specification must be a regular in-repository file")
            document = _strict_json(path)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            findings.append(
                Finding("specification", str(path.relative_to(root)), str(exc))
            )
            continue
        specs[name] = document
    return specs


def _dependency_cycles(root: Path) -> tuple[str, ...]:
    package = root / "apps" / "api" / "src" / "ai_enterprise"
    graph: dict[str, set[str]] = {}
    for path in package.rglob("*.py"):
        relative_parts = path.relative_to(package.parent).with_suffix("").parts
        is_package = relative_parts[-1] == "__init__"
        module = ".".join(relative_parts[:-1] if is_package else relative_parts)
        graph[module] = set()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    package_parts = (
                        module.split(".") if is_package else module.split(".")[:-1]
                    )
                    keep = max(1, len(package_parts) - node.level + 1)
                    imported = ".".join(
                        package_parts[:keep] + (node.module or "").split(".")
                    ).rstrip(".")
                else:
                    imported = node.module or ""
                if imported.startswith("ai_enterprise"):
                    graph[module].add(imported)
                    graph[module].update(
                        f"{imported}.{alias.name}"
                        for alias in node.names
                        if alias.name != "*"
                    )
            elif isinstance(node, ast.Import):
                graph[module].update(
                    alias.name
                    for alias in node.names
                    if alias.name.startswith("ai_enterprise")
                )
    cycles: set[str] = set()
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(module: str) -> None:
        if module in visiting:
            cycle = visiting[visiting.index(module) :] + [module]
            cycles.add(" -> ".join(cycle))
            return
        if module in visited:
            return
        visiting.append(module)
        for dependency in sorted(graph.get(module, ())):
            if dependency in graph:
                visit(dependency)
        visiting.pop()
        visited.add(module)

    for module in sorted(graph):
        visit(module)
    return tuple(sorted(cycles))


def _unmigrated_models(root: Path) -> tuple[str, ...]:
    infrastructure = root / "apps" / "api" / "src" / "ai_enterprise" / "infrastructure"
    migration_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((root / "migrations" / "versions").glob("*.py"))
    )
    missing: list[str] = []
    for path in sorted(infrastructure.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            table_name: str | None = None
            for statement in node.body:
                if (
                    isinstance(statement, ast.Assign)
                    and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name)
                    and statement.targets[0].id == "__tablename__"
                    and isinstance(statement.value, ast.Constant)
                    and isinstance(statement.value.value, str)
                ):
                    table_name = statement.value.value
            if (
                table_name
                and node.name not in migration_text
                and table_name not in migration_text
            ):
                missing.append(f"{node.name}:{table_name}")
    return tuple(missing)


def verify(root: Path) -> VerificationReport:
    root = root.resolve()
    findings: list[Finding] = []
    checks = 0
    etra = etra_conformance.validate(root)
    checks += etra.checks
    findings.extend(
        Finding(item.check, item.path, item.message) for item in etra.findings
    )
    specs = _load_specs(root, findings)
    checks += len(SPEC_FILES)
    identifiers: set[str] = set()
    for name, document in specs.items():
        identifier = document.get("specification_id")
        if not isinstance(identifier, str) or identifier in identifiers:
            findings.append(
                Finding("specification-identity", name, "missing or duplicate ID")
            )
        else:
            identifiers.add(identifier)
        if document.get("status") != "approved":
            findings.append(
                Finding("specification-approval", name, "specification is not approved")
            )
        if not isinstance(document.get("version"), str) or not SEMVER.fullmatch(
            document["version"]
        ):
            findings.append(
                Finding("specification-version", name, "invalid semantic version")
            )

    infrastructure = specs.get("infrastructure.v1.json", {})
    services = infrastructure.get("services", [])
    service_ids = [
        service.get("service_id") for service in services if isinstance(service, dict)
    ]
    checks += 1
    if len(service_ids) != len(set(service_ids)) or not service_ids:
        findings.append(
            Finding(
                "infrastructure",
                "infrastructure.v1.json",
                "service IDs must be present and unique",
            )
        )
    if set(infrastructure.get("targets", [])) != REQUIRED_INFRASTRUCTURE_TARGETS:
        findings.append(
            Finding(
                "infrastructure",
                "infrastructure.v1.json",
                "all required generation targets must be declared exactly once",
            )
        )
    required_service_fields = {
        "service_id",
        "replicas",
        "cpu",
        "memory",
        "volumes",
        "ports",
        "health_checks",
        "ingress",
        "dependencies",
        "secret_references",
    }
    for service in services:
        checks += 1
        if not isinstance(service, dict) or not required_service_fields <= set(service):
            findings.append(
                Finding(
                    "infrastructure",
                    "infrastructure.v1.json",
                    "service is structurally incomplete",
                )
            )
            continue
        unknown = set(service["dependencies"]) - set(service_ids)
        if unknown:
            findings.append(
                Finding(
                    "infrastructure",
                    "infrastructure.v1.json",
                    f"unknown dependencies: {sorted(unknown)}",
                )
            )
        if (
            not isinstance(service["service_id"], str)
            or not SAFE_IDENTIFIER.fullmatch(service["service_id"])
            or not isinstance(service["replicas"], int)
            or isinstance(service["replicas"], bool)
            or service["replicas"] < 1
            or not service["health_checks"]
            or any(
                not isinstance(port, int)
                or isinstance(port, bool)
                or not 1 <= port <= 65535
                for port in service["ports"]
            )
        ):
            findings.append(
                Finding(
                    "infrastructure",
                    "infrastructure.v1.json",
                    f"invalid service limits or identity: {service.get('service_id')}",
                )
            )

    configuration = specs.get("configuration.v1.json", {})
    fields = configuration.get("fields", [])
    keys = [
        field["key"]
        for field in fields
        if isinstance(field, dict) and isinstance(field.get("key"), str)
    ]
    checks += 1
    if len(keys) != len(set(keys)) or not keys:
        findings.append(
            Finding(
                "configuration",
                "configuration.v1.json",
                "configuration keys must be present and unique",
            )
        )
    for field in fields:
        checks += 1
        if not isinstance(field, dict) or not {
            "key",
            "type",
            "required",
            "secret",
            "environments",
        } <= set(field):
            findings.append(
                Finding(
                    "configuration",
                    "configuration.v1.json",
                    "configuration field is untyped or incomplete",
                )
            )
        if isinstance(field, dict) and field.get("secret") is True:
            leaked_keys = {"default", "value", "example", "literal"} & set(field)
            if leaked_keys:
                findings.append(
                    Finding(
                        "configuration-secret",
                        "configuration.v1.json",
                        f"secret field {field.get('key')} embeds values: {sorted(leaked_keys)}",
                    )
                )
    profiles = configuration.get("profiles", {})
    for protected in ("staging", "production"):
        if (
            not isinstance(profiles.get(protected), dict)
            or profiles[protected].get("fail_closed") is not True
        ):
            findings.append(
                Finding(
                    "configuration",
                    "configuration.v1.json",
                    f"{protected} profile must fail closed",
                )
            )
    config_implementation = (
        root / "apps" / "api" / "src" / "ai_enterprise" / "config.py"
    )
    config_text = (
        config_implementation.read_text(encoding="utf-8")
        if config_implementation.is_file()
        else ""
    )
    missing_config = [key.lower() for key in keys if key.lower() not in config_text]
    checks += 1
    if missing_config:
        findings.append(
            Finding(
                "configuration-drift",
                str(config_implementation.relative_to(root)),
                f"typed settings missing: {missing_config}",
            )
        )

    security = specs.get("security.v1.json", {})
    checks += 1
    if security.get("default_decision") != "deny":
        findings.append(Finding("security", "security.v1.json", "default must be deny"))
    role_ids = [role.get("role_id") for role in security.get("roles", [])]
    if len(role_ids) != len(set(role_ids)):
        findings.append(Finding("security", "security.v1.json", "duplicate role ID"))
    human_only = set(security.get("human_only_permissions", []))
    for role in security.get("roles", []):
        permissions = role.get("permissions", [])
        if len(permissions) != len(set(permissions)):
            findings.append(
                Finding("security", "security.v1.json", "duplicate role permission")
            )
        if set(permissions) & human_only and role.get("role_id") != "human-authority":
            findings.append(
                Finding(
                    "security",
                    "security.v1.json",
                    f"human-only authority assigned to general role: {role.get('role_id')}",
                )
            )

    contracts = specs.get("contracts.v1.json", {}).get("contracts", [])
    contract_ids = [contract.get("contract_id") for contract in contracts]
    checks += len(contracts)
    if len(contract_ids) != len(set(contract_ids)):
        findings.append(
            Finding("contracts", "contracts.v1.json", "duplicate contract ID")
        )
    for contract in contracts:
        relative_implementation = contract.get("implementation", "")
        implementation = (
            root / relative_implementation
            if isinstance(relative_implementation, str)
            else root
        )
        safe_implementation = (
            isinstance(relative_implementation, str)
            and not Path(relative_implementation).is_absolute()
            and _inside(root, implementation)
            and implementation.is_file()
            and not implementation.is_symlink()
        )
        if not safe_implementation:
            findings.append(
                Finding(
                    "contract-path",
                    str(relative_implementation),
                    "implementation must be a regular in-repository file",
                )
            )
        text = implementation.read_text(encoding="utf-8") if safe_implementation else ""
        missing = [
            token for token in contract.get("required_tokens", []) if token not in text
        ]
        if missing:
            findings.append(
                Finding(
                    "contract-drift",
                    str(contract.get("implementation")),
                    f"missing tokens: {missing}",
                )
            )

    gates = specs.get("quality-gates.v1.json", {}).get("gates", [])
    gate_ids = [gate.get("gate_id") for gate in gates]
    checks += 1
    if tuple(gate_ids) != REQUIRED_GATES:
        findings.append(
            Finding(
                "quality-gates",
                "quality-gates.v1.json",
                "mandatory gates are missing, duplicated, or out of order",
            )
        )
    for index, gate in enumerate(gates):
        expected_predecessors = [] if index == 0 else [gates[index - 1].get("gate_id")]
        if gate.get("predecessors") != expected_predecessors:
            findings.append(
                Finding(
                    "quality-gates",
                    "quality-gates.v1.json",
                    f"gate predecessor is not immediate and mandatory: {gate.get('gate_id')}",
                )
            )
        if gate.get("command") != EXPECTED_GATE_COMMANDS.get(gate.get("gate_id")):
            findings.append(
                Finding(
                    "quality-gates",
                    "quality-gates.v1.json",
                    f"gate command is weakened or changed: {gate.get('gate_id')}",
                )
            )
    evidence = specs.get("quality-gates.v1.json", {}).get("evidence", {})
    if evidence.get("bypass_allowed") is not False or not evidence.get(
        "signature_required_for_promotion"
    ):
        findings.append(
            Finding(
                "quality-gates",
                "quality-gates.v1.json",
                "promotion evidence can be bypassed or unsigned",
            )
        )

    determinism = specs.get("determinism.v1.json", {})
    checks += 1
    if any(
        not determinism.get(key)
        for key in (
            "generator_version_required",
            "approved_specification_required",
            "generated_artifact_manifest_required",
        )
    ):
        findings.append(
            Finding(
                "determinism",
                "determinism.v1.json",
                "traceability requirements are disabled",
            )
        )
    first = generate_engineering_artifacts.render(root)
    second = generate_engineering_artifacts.render(root)
    checks += 2
    if first != second:
        findings.append(
            Finding(
                "determinism",
                str(generate_engineering_artifacts.OUTPUT),
                "generator output differs across identical runs",
            )
        )
    output_path = root / generate_engineering_artifacts.OUTPUT
    if not output_path.is_file() or output_path.read_text(encoding="utf-8") != first:
        findings.append(
            Finding(
                "generated-artifact-drift",
                str(generate_engineering_artifacts.OUTPUT),
                "regeneration required",
            )
        )

    cycles = _dependency_cycles(root)
    checks += 1
    for cycle in cycles:
        findings.append(
            Finding("dependency-cycle", "apps/api/src/ai_enterprise", cycle)
        )
    unmigrated = _unmigrated_models(root)
    checks += 1
    for model in unmigrated:
        findings.append(
            Finding("schema-drift", "apps/api/src/ai_enterprise/infrastructure", model)
        )

    workflow_path = root / ".github" / "workflows" / "engineering-verification.yml"
    safe_workflow = (
        _inside(root, workflow_path)
        and workflow_path.is_file()
        and not workflow_path.is_symlink()
    )
    workflow_text = workflow_path.read_text(encoding="utf-8") if safe_workflow else ""
    for command in (
        "python tools/engineering_verify.py --static --json",
        "python tools/engineering_verify.py --full --json",
    ):
        checks += 1
        if command not in workflow_text:
            findings.append(
                Finding(
                    "continuous-verification",
                    str(workflow_path.relative_to(root)),
                    f"mandatory CI command missing: {command}",
                )
            )

    implementation_hashes: dict[str, str] = {}
    for contract in contracts:
        relative = contract.get("implementation")
        if isinstance(relative, str):
            path = root / relative
            if _inside(root, path) and path.is_file() and not path.is_symlink():
                implementation_hashes[relative] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
    canonical = json.dumps(
        {
            "specifications": specs,
            "contract_implementation_hashes": implementation_hashes,
            "generated_artifact_hash": hashlib.sha256(first.encode()).hexdigest(),
            "findings": [asdict(item) for item in findings],
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return VerificationReport(
        not findings,
        checks,
        hashlib.sha256(canonical.encode()).hexdigest(),
        tuple(findings),
    )


def _run_full_gates(root: Path) -> int:
    commands = (
        (
            "apps/api/.venv/bin/ruff",
            "check",
            "apps/api/src",
            "apps/api/tests",
            "migrations",
            "tools",
        ),
        ("bash", "-lc", "cd apps/api && .venv/bin/mypy src"),
        (
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "apps/api/src",
            "apps/api/tests",
            "tools",
        ),
        ("apps/api/.venv/bin/pytest", "-q", "apps/api/tests"),
    )
    for command in commands:
        if subprocess.run(command, cwd=root, check=False).returncode != 0:
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--static", action="store_true")
    mode.add_argument("--full", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args(argv)
    report = verify(args.root)
    if args.as_json:
        print(json.dumps(asdict(report), sort_keys=True))
    else:
        print(
            f"P9 engineering verification: {'PASS' if report.conformant else 'FAIL'} "
            f"({report.checks} checks, evidence {report.evidence_hash})"
        )
        for finding in report.findings:
            print(f"- [{finding.check}] {finding.path}: {finding.message}")
    if not report.conformant:
        return 1
    return _run_full_gates(args.root) if args.full else 0


if __name__ == "__main__":
    sys.exit(main())
