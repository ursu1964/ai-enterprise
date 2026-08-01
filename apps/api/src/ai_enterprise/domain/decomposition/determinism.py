from __future__ import annotations

import heapq
from dataclasses import asdict, dataclass
from typing import Any, cast

from ai_enterprise.domain.decomposition.core import (
    DecompositionPolicy,
    canonical_hash,
    canonical_slug,
    derive_package_id,
    normalize_repository_path,
    normalize_text,
)
from ai_enterprise.domain.decomposition.schema import CandidateDecomposition


@dataclass(frozen=True, slots=True)
class NormalizedCriterion:
    key: str
    text: str
    verification_type: str
    command_ref: str | None


@dataclass(frozen=True, slots=True)
class NormalizedCommand:
    key: str
    argv: tuple[str, ...]
    working_directory: str
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class NormalizedPackage:
    id: str
    key: str
    title: str
    objective: str
    requirement_refs: tuple[str, ...]
    architecture_refs: tuple[str, ...]
    allowed_paths: tuple[str, ...]
    proposed_new_paths: tuple[str, ...]
    prohibited_paths: tuple[str, ...]
    dependencies: tuple[str, ...]
    dependency_reasons: tuple[tuple[str, str], ...]
    acceptance_criteria: tuple[NormalizedCriterion, ...]
    test_commands: tuple[NormalizedCommand, ...]
    estimated_files: int
    estimated_changed_lines: int
    execution_policy: tuple[tuple[str, object], ...]
    package_hash: str


@dataclass(frozen=True, slots=True)
class NormalizedDecomposition:
    summary: str
    packages: tuple[NormalizedPackage, ...]
    assumptions: tuple[str, ...]
    unresolved_questions: tuple[str, ...]
    artifact_hash: str


class CandidateNormalizer:
    def normalize(
        self,
        candidate: CandidateDecomposition,
        *,
        project_id: str,
        architecture_hash: str,
        repository_tree_hash: str,
        policy: DecompositionPolicy,
    ) -> NormalizedDecomposition:
        keys = [canonical_slug(item.candidate_key) for item in candidate.packages]
        if len(keys) != len(set(keys)):
            raise ValueError("Candidate package keys collide after normalization")
        key_map = dict(zip((item.candidate_key for item in candidate.packages), keys, strict=True))
        packages: list[NormalizedPackage] = []
        for source, key in sorted(zip(candidate.packages, keys, strict=True), key=lambda x: x[1]):
            dependencies = tuple(
                sorted(
                    {
                        key_map.get(item, canonical_slug(item))
                        for item in source.dependency_candidates
                    }
                )
            )
            criteria = tuple(
                sorted(
                    (
                        NormalizedCriterion(
                            canonical_slug(item.criterion_key),
                            normalize_text(item.text),
                            item.verification_type,
                            canonical_slug(item.command_ref) if item.command_ref else None,
                        )
                        for item in source.acceptance_criteria
                    ),
                    key=lambda item: item.key,
                )
            )
            commands = tuple(
                sorted(
                    (
                        NormalizedCommand(
                            canonical_slug(item.command_key),
                            tuple(normalize_text(arg) for arg in item.argv),
                            normalize_repository_path(item.working_directory)
                            if item.working_directory != "."
                            else ".",
                            item.timeout_seconds,
                        )
                        for item in source.test_commands
                    ),
                    key=lambda item: item.key,
                )
            )
            data: dict[str, Any] = {
                "key": key,
                "title": normalize_text(source.title),
                "objective": normalize_text(source.objective),
                "requirement_refs": sorted(set(source.requirement_refs)),
                "architecture_refs": sorted(set(source.architecture_refs)),
                "allowed_paths": sorted(
                    {normalize_repository_path(x) for x in source.allowed_paths}
                ),
                "proposed_new_paths": sorted(
                    {normalize_repository_path(x) for x in source.proposed_new_paths}
                ),
                "prohibited_paths": sorted(
                    {normalize_repository_path(x) for x in source.prohibited_paths}
                ),
                "dependencies": dependencies,
                "dependency_reasons": sorted(
                    (key_map.get(k, canonical_slug(k)), normalize_text(v))
                    for k, v in source.dependency_reasons.items()
                ),
                "acceptance_criteria": [asdict(x) for x in criteria],
                "test_commands": [asdict(x) for x in commands],
                "estimated_files": source.estimated_files,
                "estimated_changed_lines": source.estimated_changed_lines,
                "execution_policy": source.execution_policy.model_dump(mode="json"),
            }
            packages.append(
                NormalizedPackage(
                    id=str(
                        derive_package_id(
                            project_id=project_id,
                            architecture_hash=architecture_hash,
                            repository_tree_hash=repository_tree_hash,
                            policy_version=policy.version,
                            package_key=key,
                        )
                    ),
                    key=key,
                    title=cast(str, data["title"]),
                    objective=cast(str, data["objective"]),
                    requirement_refs=tuple(cast(list[str], data["requirement_refs"])),
                    architecture_refs=tuple(cast(list[str], data["architecture_refs"])),
                    allowed_paths=tuple(cast(list[str], data["allowed_paths"])),
                    proposed_new_paths=tuple(cast(list[str], data["proposed_new_paths"])),
                    prohibited_paths=tuple(cast(list[str], data["prohibited_paths"])),
                    dependencies=dependencies,
                    dependency_reasons=tuple(
                        cast(list[tuple[str, str]], data["dependency_reasons"])
                    ),
                    acceptance_criteria=criteria,
                    test_commands=commands,
                    estimated_files=source.estimated_files,
                    estimated_changed_lines=source.estimated_changed_lines,
                    execution_policy=tuple(
                        sorted(cast(dict[str, object], data["execution_policy"]).items())
                    ),
                    package_hash=canonical_hash(data),
                )
            )
        artifact_body: dict[str, Any] = {
            "summary": normalize_text(candidate.summary),
            "packages": [asdict(item) for item in packages],
            "assumptions": sorted({normalize_text(x) for x in candidate.assumptions}),
            "unresolved_questions": sorted(
                {normalize_text(x) for x in candidate.unresolved_questions}
            ),
        }
        return NormalizedDecomposition(
            summary=cast(str, artifact_body["summary"]),
            packages=tuple(packages),
            assumptions=tuple(cast(list[str], artifact_body["assumptions"])),
            unresolved_questions=tuple(cast(list[str], artifact_body["unresolved_questions"])),
            artifact_hash=canonical_hash(artifact_body),
        )


class DependencyCycleError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DecompositionGraph:
    nodes: tuple[tuple[str, str, str], ...]
    edges: tuple[tuple[str, str, str, str], ...]
    topological_order: tuple[str, ...]
    execution_groups: tuple[tuple[str, ...], ...]
    graph_hash: str


def deterministic_topological_sort(nodes: set[str], edges: list[tuple[str, str]]) -> list[str]:
    adjacency: dict[str, list[str]] = {node: [] for node in nodes}
    indegree = {node: 0 for node in nodes}
    for predecessor, successor in sorted(set(edges)):
        if predecessor not in nodes or successor not in nodes:
            raise ValueError("Dependency references an unknown package")
        adjacency[predecessor].append(successor)
        indegree[successor] += 1
    ready = [node for node, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    result: list[str] = []
    while ready:
        node = heapq.heappop(ready)
        result.append(node)
        for successor in sorted(adjacency[node]):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                heapq.heappush(ready, successor)
    if len(result) != len(nodes):
        raise DependencyCycleError("Work-package dependency graph contains a cycle")
    return result


class DeterministicGraphBuilder:
    def build(self, decomposition: NormalizedDecomposition) -> DecompositionGraph:
        keys = {item.key for item in decomposition.packages}
        edges = sorted(
            (
                dependency,
                item.key,
                "blocking",
                dict(item.dependency_reasons).get(dependency, "required"),
            )
            for item in decomposition.packages
            for dependency in item.dependencies
        )
        order = deterministic_topological_sort(keys, [(a, b) for a, b, _, _ in edges])
        remaining = set(keys)
        groups: list[tuple[str, ...]] = []
        while remaining:
            ready = tuple(
                sorted(
                    node
                    for node in remaining
                    if not any(
                        successor == node and predecessor in remaining
                        for predecessor, successor, _, _ in edges
                    )
                )
            )
            if not ready:
                raise DependencyCycleError("Work-package dependency graph contains a cycle")
            groups.append(ready)
            remaining.difference_update(ready)
        nodes = tuple(
            sorted((item.id, item.key, item.package_hash) for item in decomposition.packages)
        )
        body = {
            "nodes": nodes,
            "edges": edges,
            "topological_order": order,
            "execution_groups": groups,
        }
        return DecompositionGraph(
            nodes, tuple(edges), tuple(order), tuple(groups), canonical_hash(body)
        )
