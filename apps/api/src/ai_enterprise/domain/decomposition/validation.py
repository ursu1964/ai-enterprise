from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any, Protocol

from ai_enterprise.domain.decomposition.core import (
    DecompositionPolicy,
    canonical_hash,
    path_matches_scope,
)
from ai_enterprise.domain.decomposition.determinism import (
    CandidateNormalizer,
    DecompositionGraph,
    DependencyCycleError,
    DeterministicGraphBuilder,
    NormalizedDecomposition,
    deterministic_topological_sort,
)
from ai_enterprise.domain.decomposition.schema import CandidateDecomposition


class FindingSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    validator_code: str
    severity: FindingSeverity
    message: str
    package_key: str | None = None
    path: str | None = None
    evidence: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ValidationContext:
    candidate: CandidateDecomposition
    normalized: NormalizedDecomposition
    graph: DecompositionGraph
    policy: DecompositionPolicy
    project_id: str
    architecture_hash: str
    repository_tree_hash: str
    approved_requirements: frozenset[str]
    architecture_elements: frozenset[str]
    implementable_requirements: frozenset[str]
    implementable_architecture_elements: frozenset[str]
    repository_paths: frozenset[str]
    module_roots: frozenset[str]
    protected_paths: frozenset[str]
    requirements_approved: bool = True
    architecture_approved: bool = True
    lineage_matches: bool = True
    project_matches: bool = True
    artifacts_superseded: bool = False
    requested_commit: str = ""
    snapshot_commit: str = ""
    snapshot_tree_hash: str = ""
    index_snapshot_matches: bool = True
    repository_index: dict[str, Any] | None = None
    repository_index_hash: str = ""


class Validator(Protocol):
    def validate(self, context: ValidationContext) -> list[ValidationFinding]: ...


def error(
    code: str,
    message: str,
    package: str | None = None,
    path: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> ValidationFinding:
    return ValidationFinding(code, FindingSeverity.ERROR, message, package, path, evidence)


class InputApprovalValidator:
    def validate(self, c: ValidationContext) -> list[ValidationFinding]:
        findings = []
        if not c.requirements_approved or not c.architecture_approved:
            findings.append(error("DECOMP-INPUT-001", "Inputs must be approved"))
        if not c.lineage_matches or not c.project_matches:
            findings.append(error("DECOMP-INPUT-002", "Input lineage or project differs"))
        if c.artifacts_superseded:
            findings.append(error("DECOMP-INPUT-003", "Superseded inputs are prohibited"))
        return findings


class RepositoryIdentityValidator:
    def validate(self, c: ValidationContext) -> list[ValidationFinding]:
        findings = []
        if not c.requested_commit or c.requested_commit != c.snapshot_commit:
            findings.append(error("DECOMP-REPO-001", "Snapshot commit mismatch"))
        if c.snapshot_tree_hash != c.repository_tree_hash:
            findings.append(error("DECOMP-REPO-002", "Repository tree hash mismatch"))
        if not c.index_snapshot_matches:
            findings.append(error("DECOMP-REPO-003", "Index does not belong to snapshot"))
        if (
            c.repository_index is not None
            and canonical_hash(c.repository_index) != c.repository_index_hash
        ):
            findings.append(error("DECOMP-REPO-004", "Repository index hash mismatch"))
        return findings


class SchemaValidator:
    def validate(self, c: ValidationContext) -> list[ValidationFinding]:
        count = len(c.normalized.packages)
        if not c.policy.minimum_packages <= count <= c.policy.maximum_packages:
            return [error("DECOMP-SCHEMA-001", "Package count violates policy")]
        return []


class PackageKeyValidator:
    def validate(self, c: ValidationContext) -> list[ValidationFinding]:
        keys = [item.key for item in c.normalized.packages]
        findings = []
        if len(keys) != len(set(keys)):
            findings.append(error("DECOMP-KEY-001", "Canonical keys must be unique"))
        for key in keys:
            if len(key) > 160 or key in c.policy.reserved_keys:
                findings.append(error("DECOMP-KEY-002", "Reserved or oversized key", key))
        return findings


class RequirementCoverageValidator:
    def validate(self, c: ValidationContext) -> list[ValidationFinding]:
        covered = {ref for item in c.normalized.packages for ref in item.requirement_refs}
        return [
            error(
                "DECOMP-COVERAGE-REQ",
                "Implementable requirement is uncovered",
                evidence={"requirement": ref},
            )
            for ref in sorted(c.implementable_requirements - covered)
        ]


class ArchitectureCoverageValidator:
    def validate(self, c: ValidationContext) -> list[ValidationFinding]:
        covered = {ref for item in c.normalized.packages for ref in item.architecture_refs}
        return [
            error(
                "DECOMP-COVERAGE-ARC",
                "Architecture element is uncovered",
                evidence={"element": ref},
            )
            for ref in sorted(c.implementable_architecture_elements - covered)
        ]


class ReferenceIntegrityValidator:
    def validate(self, c: ValidationContext) -> list[ValidationFinding]:
        findings = []
        for item in c.normalized.packages:
            for ref in sorted(set(item.requirement_refs) - c.approved_requirements):
                findings.append(error("DECOMP-REF-REQ", f"Unknown requirement {ref}", item.key))
            for ref in sorted(set(item.architecture_refs) - c.architecture_elements):
                findings.append(
                    error("DECOMP-REF-ARC", f"Unknown architecture element {ref}", item.key)
                )
        return findings


def _overlaps(left: str, right: str) -> bool:
    left_root = left[:-3] if left.endswith("/**") else left
    right_root = right[:-3] if right.endswith("/**") else right
    return path_matches_scope(left_root, right) or path_matches_scope(right_root, left)


class RepositoryPathValidator:
    def validate(self, c: ValidationContext) -> list[ValidationFinding]:
        findings = []
        for item in c.normalized.packages:
            proposed = set(item.proposed_new_paths)
            for path in (*item.allowed_paths, *item.proposed_new_paths):
                if path in {"*", "**", "**/**"}:
                    findings.append(
                        error(
                            "DECOMP-PATH-BROAD", "Unbounded wildcard is prohibited", item.key, path
                        )
                    )
                    continue
                if any(_overlaps(path, protected) for protected in c.protected_paths):
                    findings.append(
                        error("DECOMP-PATH-PROTECTED", "Protected path overlap", item.key, path)
                    )
                exists = any(path_matches_scope(existing, path) for existing in c.repository_paths)
                module = any(
                    path_matches_scope(path[:-3] if path.endswith("/**") else path, root + "/**")
                    for root in c.module_roots
                )
                if not exists and path not in proposed and not module:
                    findings.append(
                        error(
                            "DECOMP-PATH-UNKNOWN",
                            "Path is outside repository index",
                            item.key,
                            path,
                        )
                    )
        return findings


class ScopeOverlapValidator:
    def validate(self, c: ValidationContext) -> list[ValidationFinding]:
        findings = []
        packages = c.normalized.packages
        edges = {(a, b) for a, b, _, _ in c.graph.edges}
        for index, left in enumerate(packages):
            for right in packages[index + 1 :]:
                for first in (*left.allowed_paths, *left.proposed_new_paths):
                    for second in (*right.allowed_paths, *right.proposed_new_paths):
                        if (
                            _overlaps(first, second)
                            and (left.key, right.key) not in edges
                            and (right.key, left.key) not in edges
                        ):
                            findings.append(
                                error(
                                    "DECOMP-SCOPE-OVERLAP",
                                    "Unsequenced write scope overlap",
                                    left.key,
                                    first,
                                    {"other_package": right.key, "other_path": second},
                                )
                            )
        return findings


class DependencyIntegrityValidator:
    def validate(self, c: ValidationContext) -> list[ValidationFinding]:
        keys = {item.key for item in c.normalized.packages}
        findings = []
        for item in c.normalized.packages:
            if len(item.dependencies) > c.policy.maximum_dependencies_per_package:
                findings.append(error("DECOMP-DEP-SIZE", "Too many dependencies", item.key))
            if len(item.dependencies) != len(set(item.dependencies)):
                findings.append(error("DECOMP-DEP-DUP", "Duplicate dependency", item.key))
            for dependency in item.dependencies:
                if dependency == item.key or dependency not in keys:
                    findings.append(error("DECOMP-DEP-REF", "Invalid dependency", item.key))
                if not dict(item.dependency_reasons).get(dependency, "").strip():
                    findings.append(
                        error("DECOMP-DEP-REASON", "Dependency reason is required", item.key)
                    )
        return findings


class CycleValidator:
    def validate(self, c: ValidationContext) -> list[ValidationFinding]:
        try:
            deterministic_topological_sort(
                {item.key for item in c.normalized.packages},
                [(a, b) for a, b, _, _ in c.graph.edges],
            )
        except DependencyCycleError as exc:
            return [error("DECOMP-CYCLE", str(exc))]
        return []


class PackageSizeValidator:
    def validate(self, c: ValidationContext) -> list[ValidationFinding]:
        findings = []
        for p in c.normalized.packages:
            values = (
                len(p.allowed_paths) > c.policy.maximum_allowed_scopes_per_package,
                len(p.proposed_new_paths) > c.policy.maximum_proposed_paths_per_package,
                len(p.acceptance_criteria) > c.policy.maximum_acceptance_criteria_per_package,
                len(p.test_commands) > c.policy.maximum_test_commands_per_package,
                p.estimated_files > c.policy.maximum_estimated_files,
                p.estimated_changed_lines > c.policy.maximum_estimated_changed_lines,
            )
            if any(values):
                findings.append(error("DECOMP-SIZE", "Package exceeds bounded-size policy", p.key))
        return findings


class CohesionValidator:
    def validate(self, c: ValidationContext) -> list[ValidationFinding]:
        findings = []
        for p in c.normalized.packages:
            roots = {
                PurePosixPath(path[:-3] if path.endswith("/**") else path).parts[0]
                for path in p.allowed_paths
            }
            if len(roots) > 2 or len(p.architecture_refs) > 8:
                findings.append(error("DECOMP-COHESION", "Package combines unrelated areas", p.key))
        return findings


class AcceptanceCriteriaValidator:
    VAGUE = ("should work", "should be good", "architecture should be followed", "works correctly")

    def validate(self, c: ValidationContext) -> list[ValidationFinding]:
        findings = []
        for p in c.normalized.packages:
            command_keys = {item.key for item in p.test_commands}
            for criterion in p.acceptance_criteria:
                vague = any(value in criterion.text.lower() for value in self.VAGUE)
                needs_command = criterion.verification_type in {
                    "test",
                    "static-analysis",
                    "contract-test",
                    "migration-check",
                }
                if vague or (needs_command and criterion.command_ref not in command_keys):
                    findings.append(
                        error("DECOMP-CRITERIA", "Criterion is vague or unverifiable", p.key)
                    )
        return findings


class TestCommandValidator:
    def validate(self, c: ValidationContext) -> list[ValidationFinding]:
        findings = []
        shell_tokens = {"|", ";", "&&", "||", ">", "<"}
        for p in c.normalized.packages:
            for command in p.test_commands:
                executable = command.argv[0] if command.argv else ""
                if executable not in c.policy.allowed_executables or any(
                    token in shell_tokens for token in command.argv
                ):
                    findings.append(error("DECOMP-CMD", "Command violates argv allowlist", p.key))
        return findings


class ExecutionPolicyValidator:
    def validate(self, c: ValidationContext) -> list[ValidationFinding]:
        findings = []
        for p in c.normalized.packages:
            policy = dict(p.execution_policy)
            cpu = policy.get("cpu_limit", 0)
            memory = policy.get("memory_mb", 0)
            pids = policy.get("pid_limit", 0)
            timeout = policy.get("timeout_seconds", 0)
            invalid = (
                policy.get("network") != "disabled"
                or policy.get("privileged") is True
                or policy.get("host_repository_write") is True
                or not isinstance(cpu, (int, float))
                or cpu > c.policy.maximum_cpu
                or not isinstance(memory, int)
                or memory > c.policy.maximum_memory_mb
                or not isinstance(pids, int)
                or pids > c.policy.maximum_pid_limit
                or not isinstance(timeout, int)
                or timeout > c.policy.maximum_timeout_seconds
            )
            if invalid:
                findings.append(
                    error("DECOMP-EXEC", "Execution policy exceeds platform boundary", p.key)
                )
        return findings


class GraphCompletenessValidator:
    def validate(self, c: ValidationContext) -> list[ValidationFinding]:
        keys = [item.key for item in c.normalized.packages]
        node_keys = [item[1] for item in c.graph.nodes]
        if (
            sorted(keys) != sorted(node_keys)
            or sorted(keys) != sorted(c.graph.topological_order)
            or len(set(c.graph.topological_order)) != len(keys)
        ):
            return [error("DECOMP-GRAPH", "Graph does not contain every package exactly once")]
        return []


class DeterminismValidator:
    def validate(self, c: ValidationContext) -> list[ValidationFinding]:
        normalizer = CandidateNormalizer()
        builder = DeterministicGraphBuilder()
        again = normalizer.normalize(
            c.candidate,
            project_id=c.project_id,
            architecture_hash=c.architecture_hash,
            repository_tree_hash=c.repository_tree_hash,
            policy=c.policy,
        )
        graph = builder.build(again)
        if (again.artifact_hash, graph.graph_hash, graph.topological_order) != (
            c.normalized.artifact_hash,
            c.graph.graph_hash,
            c.graph.topological_order,
        ):
            return [error("DECOMP-DETERMINISM", "Repeated derivation differs")]
        return []


ALL_VALIDATORS: tuple[Validator, ...] = (
    InputApprovalValidator(),
    RepositoryIdentityValidator(),
    SchemaValidator(),
    PackageKeyValidator(),
    RequirementCoverageValidator(),
    ArchitectureCoverageValidator(),
    ReferenceIntegrityValidator(),
    RepositoryPathValidator(),
    ScopeOverlapValidator(),
    DependencyIntegrityValidator(),
    CycleValidator(),
    PackageSizeValidator(),
    CohesionValidator(),
    AcceptanceCriteriaValidator(),
    TestCommandValidator(),
    ExecutionPolicyValidator(),
    GraphCompletenessValidator(),
    DeterminismValidator(),
)


class DecompositionValidationService:
    def __init__(self, validators: tuple[Validator, ...] = ALL_VALIDATORS) -> None:
        self._validators = validators

    def validate(self, context: ValidationContext) -> list[ValidationFinding]:
        findings = [
            finding for validator in self._validators for finding in validator.validate(context)
        ]
        return sorted(
            findings,
            key=lambda item: (
                item.severity.value,
                item.validator_code,
                item.package_key or "",
                item.path or "",
                item.message,
            ),
        )
