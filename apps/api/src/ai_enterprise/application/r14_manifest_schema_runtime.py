from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict

from ai_enterprise.domain.specification.kernel import specification_hash

SCHEMA_VERSION = "ai-enterprise-manifest-1.0"

REQUIRED_SECTIONS: tuple[str, ...] = (
    "metadata",
    "organization",
    "vision",
    "domain",
    "objectives",
    "users",
    "businessEntities",
    "capabilities",
    "workflows",
    "businessRules",
    "policies",
    "integrations",
    "reporting",
    "security",
    "quality",
    "constraints",
    "deploymentPreferences",
    "version",
)

FORBIDDEN_IMPLEMENTATION_FIELDS: tuple[str, ...] = (
    "api",
    "apis",
    "backend",
    "cloudProvider",
    "components",
    "database",
    "databases",
    "framework",
    "frontend",
    "implementation",
    "language",
    "microservices",
    "reactComponents",
    "services",
)


class R14ManifestSchemaContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str
    intake_mode: str
    minimal_intake_supported: bool
    normalization_layer: str
    required_sections: tuple[str, ...]
    forbidden_implementation_fields: tuple[str, ...]
    lifecycle: tuple[str, ...]
    expansion_outputs: tuple[str, ...]
    contract_hash: str


class R14ManifestSchemaFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    severity: str
    code: str
    detail: str


class R14ManifestValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    finding_count: int
    findings: tuple[R14ManifestSchemaFinding, ...]
    manifest_hash: str
    schema_hash: str
    report_hash: str


class R14ManifestEvolutionReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    changed: bool
    previous_manifest_hash: str
    current_manifest_hash: str
    previous_manifest_version: str | None
    current_manifest_version: str | None
    findings: tuple[R14ManifestSchemaFinding, ...]
    report_hash: str


def r14_manifest_schema(schema_path: Path) -> dict[str, Any]:
    return json.loads(schema_path.read_text(encoding="utf-8"))


def r14_manifest_schema_contract() -> R14ManifestSchemaContract:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "intake_mode": "strict_canonical",
        "minimal_intake_supported": False,
        "normalization_layer": "deferred_to_intake_normalization_layer",
        "required_sections": list(REQUIRED_SECTIONS),
        "forbidden_implementation_fields": list(FORBIDDEN_IMPLEMENTATION_FIELDS),
        "lifecycle": [
            "client",
            "manifest",
            "validation",
            "registry_expansion",
            "knowledge_graph",
            "execution_plan",
            "generated_software",
        ],
        "expansion_outputs": [
            "business_graph",
            "semantic_graph",
            "dependency_graph",
            "execution_graph",
            "implementation_graph",
        ],
    }
    return R14ManifestSchemaContract(
        schema_version=SCHEMA_VERSION,
        intake_mode="strict_canonical",
        minimal_intake_supported=False,
        normalization_layer="deferred_to_intake_normalization_layer",
        required_sections=REQUIRED_SECTIONS,
        forbidden_implementation_fields=FORBIDDEN_IMPLEMENTATION_FIELDS,
        lifecycle=tuple(payload["lifecycle"]),
        expansion_outputs=tuple(payload["expansion_outputs"]),
        contract_hash=specification_hash(payload),
    )


def r14_validate_manifest(
    manifest: dict[str, Any],
    schema_path: Path,
    registry_root: Path | None = None,
) -> R14ManifestValidationReport:
    schema = r14_manifest_schema(schema_path)
    findings: list[R14ManifestSchemaFinding] = []
    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(manifest), key=lambda item: list(item.path)):
        path = "/".join(str(part) for part in error.absolute_path) or "$"
        findings.append(
            R14ManifestSchemaFinding(
                path=path,
                severity="error",
                code="R14-SCHEMA",
                detail=error.message,
            )
        )
    _implementation_independence(manifest, findings)
    _strict_canonical_boundary(manifest, findings)
    if registry_root is not None:
        _registry_references(manifest, registry_root, findings)
    _duplicates(manifest, findings)
    _circular_dependencies(manifest, findings)
    _workflow_references(manifest, findings)
    _constraint_consistency(manifest, findings)
    _policy_compatibility(manifest, findings)
    ordered = tuple(sorted(findings, key=lambda item: (item.path, item.code, item.detail)))
    valid = not ordered
    schema_hash = specification_hash(schema)
    manifest_hash = specification_hash(manifest)
    payload = {
        "valid": valid,
        "findings": [item.model_dump(mode="json") for item in ordered],
        "manifest_hash": manifest_hash,
        "schema_hash": schema_hash,
    }
    return R14ManifestValidationReport(
        valid=valid,
        finding_count=len(ordered),
        findings=ordered,
        manifest_hash=manifest_hash,
        schema_hash=schema_hash,
        report_hash=specification_hash(payload),
    )


def r14_validate_manifest_evolution(
    previous_manifest: dict[str, Any],
    current_manifest: dict[str, Any],
) -> R14ManifestEvolutionReport:
    previous_hash = specification_hash(previous_manifest)
    current_hash = specification_hash(current_manifest)
    previous_version = _manifest_version(previous_manifest)
    current_version = _manifest_version(current_manifest)
    changed = previous_hash != current_hash
    findings: list[R14ManifestSchemaFinding] = []
    if changed and previous_version == current_version:
        findings.append(
            R14ManifestSchemaFinding(
                path="version/manifestVersion",
                severity="error",
                code="R14-VERSION-IMMUTABILITY",
                detail="Changed Manifest content must receive a new manifestVersion.",
            )
        )
    ordered = tuple(findings)
    valid = not ordered
    payload = {
        "valid": valid,
        "changed": changed,
        "previous_manifest_hash": previous_hash,
        "current_manifest_hash": current_hash,
        "previous_manifest_version": previous_version,
        "current_manifest_version": current_version,
        "findings": [item.model_dump(mode="json") for item in ordered],
    }
    return R14ManifestEvolutionReport(
        valid=valid,
        changed=changed,
        previous_manifest_hash=previous_hash,
        current_manifest_hash=current_hash,
        previous_manifest_version=previous_version,
        current_manifest_version=current_version,
        findings=ordered,
        report_hash=specification_hash(payload),
    )


def _implementation_independence(
    manifest: dict[str, Any],
    findings: list[R14ManifestSchemaFinding],
) -> None:
    allowed_preference_path = ("deploymentPreferences",)
    for path, value in _walk(manifest):
        if not path:
            continue
        key = path[-1]
        if path[:1] == allowed_preference_path:
            continue
        if key in FORBIDDEN_IMPLEMENTATION_FIELDS:
            findings.append(
                R14ManifestSchemaFinding(
                    path="/".join(path),
                    severity="error",
                    code="R14-INTENT-ONLY",
                    detail=(
                        "Manifest fields must describe business intent, not "
                        "implementation design."
                    ),
                )
            )
        if isinstance(value, str) and _looks_like_implementation_instruction(value):
            findings.append(
                R14ManifestSchemaFinding(
                    path="/".join(path),
                    severity="error",
                    code="R14-INTENT-ONLY",
                    detail=(
                        "Manifest text must not force implementation mechanisms "
                        "outside constraints/preferences."
                    ),
                )
            )


def _strict_canonical_boundary(
    manifest: dict[str, Any],
    findings: list[R14ManifestSchemaFinding],
) -> None:
    missing = sorted(section for section in REQUIRED_SECTIONS if section not in manifest)
    if missing:
        findings.append(
            R14ManifestSchemaFinding(
                path="$",
                severity="error",
                code="R14-STRICT-CANONICAL",
                detail=(
                    "R14 uses strict canonical Manifest intake. Minimal intake "
                    "normalization is intentionally deferred; missing sections: "
                    + ", ".join(missing)
                ),
            )
        )


def _registry_references(
    manifest: dict[str, Any],
    registry_root: Path,
    findings: list[R14ManifestSchemaFinding],
) -> None:
    mappings = (
        ("users", "Roles"),
        ("businessEntities", "Entities"),
        ("capabilities", "Actions"),
        ("workflows", "Workflows"),
        ("policies", "Policies"),
        ("integrations", "Integrations"),
    )
    registry_ids = {
        directory: _registry_ids(registry_root / directory)
        for _section, directory in mappings
    }
    for section, directory in mappings:
        value = manifest.get(section)
        if not isinstance(value, list):
            continue
        for index, item in enumerate(value):
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            identifier = item["id"]
            if identifier not in registry_ids[directory]:
                findings.append(
                    R14ManifestSchemaFinding(
                        path=f"{section}/{index}/id",
                        severity="error",
                        code="R14-REGISTRY-REFERENCE",
                        detail=(
                            f"Manifest object {identifier} is missing from "
                            f"registry/{directory}."
                        ),
                    )
                )


def _duplicates(manifest: dict[str, Any], findings: list[R14ManifestSchemaFinding]) -> None:
    identifiers: dict[str, list[str]] = {}
    for section in (
        "objectives",
        "users",
        "businessEntities",
        "capabilities",
        "workflows",
        "businessRules",
        "policies",
        "integrations",
        "reporting",
        "security",
        "quality",
        "constraints",
    ):
        value = manifest.get(section)
        if not isinstance(value, list):
            continue
        for index, item in enumerate(value):
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                identifiers.setdefault(item["id"], []).append(f"{section}/{index}/id")
    for identifier, paths in identifiers.items():
        if len(paths) > 1:
            findings.append(
                R14ManifestSchemaFinding(
                    path="|".join(sorted(paths)),
                    severity="error",
                    code="R14-DUPLICATE-ID",
                    detail=f"Duplicate Manifest identifier: {identifier}",
                )
            )


def _circular_dependencies(
    manifest: dict[str, Any],
    findings: list[R14ManifestSchemaFinding],
) -> None:
    graph: dict[str, set[str]] = {}
    paths: dict[str, str] = {}
    for section in (
        "objectives",
        "users",
        "businessEntities",
        "capabilities",
        "workflows",
        "businessRules",
        "policies",
    ):
        value = manifest.get(section)
        if not isinstance(value, list):
            continue
        for index, item in enumerate(value):
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            identifier = item["id"]
            paths[identifier] = f"{section}/{index}/dependsOn"
            dependencies = item.get("dependsOn", [])
            graph[identifier] = {
                dependency
                for dependency in dependencies
                if isinstance(dependency, str)
            }
    for cycle in _cycles(graph):
        findings.append(
            R14ManifestSchemaFinding(
                path=paths.get(cycle[0], "$"),
                severity="error",
                code="R14-CIRCULAR-DEPENDENCY",
                detail="Circular business dependency detected: " + " -> ".join(cycle),
            )
        )


def _workflow_references(
    manifest: dict[str, Any],
    findings: list[R14ManifestSchemaFinding],
) -> None:
    capability_ids = _ids(manifest.get("capabilities"))
    entity_ids = _ids(manifest.get("businessEntities"))
    workflows = manifest.get("workflows")
    if not isinstance(workflows, list):
        return
    for workflow_index, workflow in enumerate(workflows):
        if not isinstance(workflow, dict):
            continue
        steps = workflow.get("steps")
        if not isinstance(steps, list):
            continue
        for step_index, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            capability_id = step.get("capabilityId")
            if isinstance(capability_id, str) and capability_id not in capability_ids:
                findings.append(
                    R14ManifestSchemaFinding(
                        path=f"workflows/{workflow_index}/steps/{step_index}/capabilityId",
                        severity="error",
                        code="R14-UNKNOWN-CAPABILITY",
                        detail=f"Workflow references unknown capability: {capability_id}",
                    )
                )
            entity_values = step.get("entityIds", [])
            if isinstance(entity_values, list):
                for entity_id in entity_values:
                    if isinstance(entity_id, str) and entity_id not in entity_ids:
                        findings.append(
                            R14ManifestSchemaFinding(
                                path=(
                                    f"workflows/{workflow_index}/steps/{step_index}/entityIds"
                                ),
                                severity="error",
                                code="R14-UNKNOWN-ENTITY",
                                detail=f"Workflow references unknown business entity: {entity_id}",
                            )
                        )


def _constraint_consistency(
    manifest: dict[str, Any],
    findings: list[R14ManifestSchemaFinding],
) -> None:
    constraints = _descriptions(manifest.get("constraints"))
    pairs = (
        ("cannot leave the eu", "outside eu"),
        ("must remain on-premise", "public cloud required"),
        ("open-source components only", "proprietary component required"),
    )
    for left, right in pairs:
        left_paths = [path for path, text in constraints if left in text]
        right_paths = [path for path, text in constraints if right in text]
        if left_paths and right_paths:
            findings.append(
                R14ManifestSchemaFinding(
                    path="|".join(sorted([*left_paths, *right_paths])),
                    severity="error",
                    code="R14-CONSTRAINT-CONFLICT",
                    detail=(
                        "Constraints are internally inconsistent: "
                        f"{left} conflicts with {right}."
                    ),
                )
            )


def _policy_compatibility(
    manifest: dict[str, Any],
    findings: list[R14ManifestSchemaFinding],
) -> None:
    policies = _descriptions(manifest.get("policies"))
    security_text = " ".join(text for _path, text in _descriptions(manifest.get("security")))
    constraint_text = " ".join(text for _path, text in _descriptions(manifest.get("constraints")))
    for path, policy in policies:
        if "privacy" in policy and not any(
            marker in security_text
            for marker in ("access", "encryption", "audit", "privacy")
        ):
            findings.append(
                R14ManifestSchemaFinding(
                    path=path,
                    severity="error",
                    code="R14-POLICY-COMPATIBILITY",
                    detail="Privacy policy requires compatible security requirements.",
                )
            )
        if "transfer globally" in policy and "cannot leave the eu" in constraint_text:
            findings.append(
                R14ManifestSchemaFinding(
                    path=path,
                    severity="error",
                    code="R14-POLICY-COMPATIBILITY",
                    detail="Policy allowing global transfer conflicts with EU data constraint.",
                )
            )


def _ids(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {
        item["id"]
        for item in value
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def _registry_ids(path: Path) -> set[str]:
    values: set[str] = set()
    if not path.exists():
        return values
    for candidate in sorted(path.glob("*.json")):
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("id"), str):
            values.add(payload["id"])
    return values


def _cycles(graph: dict[str, set[str]]) -> list[tuple[str, ...]]:
    cycles: set[tuple[str, ...]] = set()

    def visit(node: str, stack: tuple[str, ...]) -> None:
        if node in stack:
            cycle = stack[stack.index(node):] + (node,)
            cycles.add(_canonical_cycle(cycle))
            return
        for child in sorted(graph.get(node, set())):
            if child in graph:
                visit(child, (*stack, node))

    for node in sorted(graph):
        visit(node, ())
    return sorted(cycles)


def _canonical_cycle(cycle: tuple[str, ...]) -> tuple[str, ...]:
    body = cycle[:-1]
    rotations = [body[index:] + body[:index] for index in range(len(body))]
    selected = min(rotations)
    return selected + (selected[0],)


def _descriptions(value: Any) -> list[tuple[str, str]]:
    if not isinstance(value, list):
        return []
    descriptions: list[tuple[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        text = " ".join(
            str(item.get(field, ""))
            for field in ("description", "requirement", "purpose", "name")
        ).lower()
        descriptions.append((f"{index}", text))
    return descriptions


def _manifest_version(manifest: dict[str, Any]) -> str | None:
    version = manifest.get("version")
    if isinstance(version, dict) and isinstance(version.get("manifestVersion"), str):
        return version["manifestVersion"]
    return None


def _walk(value: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    items = [(path, value)]
    if isinstance(value, dict):
        for key, item in value.items():
            items.extend(_walk(item, (*path, str(key))))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            items.extend(_walk(item, (*path, str(index))))
    return items


def _looks_like_implementation_instruction(value: str) -> bool:
    lowered = value.lower()
    return any(
        phrase in lowered
        for phrase in (
            "create react component",
            "create microservice",
            "implement api endpoint",
            "use express",
            "use spring boot",
        )
    )
