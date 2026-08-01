import copy

import pytest
from pydantic import ValidationError

from ai_enterprise.domain.decomposition.core import (
    DecompositionPolicy,
    DecompositionState,
    assert_transition,
    canonical_hash,
)
from ai_enterprise.domain.decomposition.determinism import (
    CandidateNormalizer,
    DependencyCycleError,
    DeterministicGraphBuilder,
    deterministic_topological_sort,
)
from ai_enterprise.domain.decomposition.schema import CandidateDecomposition
from ai_enterprise.domain.decomposition.validation import (
    DecompositionValidationService,
    ValidationContext,
)


def package(key: str, path: str, *, dependency: str | None = None) -> dict[str, object]:
    dependencies = [dependency] if dependency else []
    return {
        "candidate_key": key,
        "title": f"Implement {key}",
        "objective": f"Implement a cohesive outcome for {key}.",
        "requirement_refs": [f"REQ-{key[-1]}"] if key[-1].isdigit() else ["REQ-1"],
        "architecture_refs": [f"ARC-{key[-1]}"] if key[-1].isdigit() else ["ARC-1"],
        "allowed_paths": [path],
        "proposed_new_paths": [],
        "prohibited_paths": ["infra/production/**"],
        "dependency_candidates": dependencies,
        "dependency_reasons": {dependency: "Required contract"} if dependency else {},
        "acceptance_criteria": [
            {
                "criterion_key": f"AC-{key}",
                "text": "Unit tests verify the bounded behavior.",
                "verification_type": "test",
                "command_ref": f"test-{key}",
            }
        ],
        "test_commands": [
            {
                "command_key": f"test-{key}",
                "argv": ["pytest", path.split("/**")[0], "-q"],
                "working_directory": ".",
                "timeout_seconds": 120,
            }
        ],
        "estimated_files": 3,
        "estimated_changed_lines": 100,
        "execution_policy": {
            "network": "disabled",
            "cpu_limit": 2,
            "memory_mb": 1024,
            "pid_limit": 64,
            "timeout_seconds": 600,
            "privileged": False,
            "host_repository_write": False,
        },
    }


def candidate_payload() -> dict[str, object]:
    return {
        "summary": "Bounded decomposition",
        "packages": [
            package("Package 1", "apps/api/domain/**"),
            package("Package 2", "apps/api/service/**", dependency="Package 1"),
        ],
        "unresolved_questions": [],
        "assumptions": [],
    }


def derive(payload: dict[str, object]):
    candidate = CandidateDecomposition.model_validate(payload)
    policy = DecompositionPolicy()
    normalized = CandidateNormalizer().normalize(
        candidate,
        project_id="project",
        architecture_hash="a" * 64,
        repository_tree_hash="b" * 64,
        policy=policy,
    )
    return candidate, policy, normalized, DeterministicGraphBuilder().build(normalized)


def context(payload: dict[str, object]) -> ValidationContext:
    candidate, policy, normalized, graph = derive(payload)
    index = {"files": ["apps/api/domain/x.py", "apps/api/service/x.py"]}
    return ValidationContext(
        candidate=candidate,
        normalized=normalized,
        graph=graph,
        policy=policy,
        project_id="project",
        architecture_hash="a" * 64,
        repository_tree_hash="b" * 64,
        approved_requirements=frozenset({"REQ-1", "REQ-2"}),
        architecture_elements=frozenset({"ARC-1", "ARC-2"}),
        implementable_requirements=frozenset({"REQ-1", "REQ-2"}),
        implementable_architecture_elements=frozenset({"ARC-1", "ARC-2"}),
        repository_paths=frozenset(index["files"]),
        module_roots=frozenset({"apps/api"}),
        protected_paths=frozenset({".git/**", "infra/production/**"}),
        requested_commit="c" * 40,
        snapshot_commit="c" * 40,
        snapshot_tree_hash="b" * 64,
        repository_index=index,
        repository_index_hash=canonical_hash(index),
    )


def test_normalization_and_graph_are_order_independent() -> None:
    first = candidate_payload()
    second = copy.deepcopy(first)
    second["packages"] = list(reversed(second["packages"]))
    _, _, normalized_a, graph_a = derive(first)
    _, _, normalized_b, graph_b = derive(second)
    assert normalized_a.artifact_hash == normalized_b.artifact_hash
    assert graph_a.graph_hash == graph_b.graph_hash
    assert graph_a.topological_order == ("package-1", "package-2")
    assert graph_a.execution_groups == (("package-1",), ("package-2",))


def test_adversarial_keys_paths_schema_and_cycles_fail_closed() -> None:
    duplicate = candidate_payload()
    duplicate["packages"][1]["candidate_key"] = "PACKAGE--1"
    with pytest.raises(ValueError, match="collide"):
        derive(duplicate)
    traversal = candidate_payload()
    traversal["packages"][0]["allowed_paths"] = ["../../etc/passwd"]
    with pytest.raises(ValueError, match="traversal"):
        derive(traversal)
    extra = candidate_payload()
    extra["packages"][0]["database_id"] = "model-controlled"
    with pytest.raises(ValidationError):
        CandidateDecomposition.model_validate(extra)
    with pytest.raises(DependencyCycleError):
        deterministic_topological_sort({"a", "b"}, [("a", "b"), ("b", "a")])


def test_all_validators_accept_bounded_candidate() -> None:
    assert DecompositionValidationService().validate(context(candidate_payload())) == []


def test_adversarial_candidate_reports_all_policy_boundaries() -> None:
    payload = candidate_payload()
    first = payload["packages"][0]
    first["allowed_paths"] = ["**", "infra/production/**", "apps/api/service/**"]
    first["requirement_refs"] = ["REQ-INVENTED"]
    first["architecture_refs"] = ["ARC-INVENTED"]
    first["test_commands"][0]["argv"] = ["bash", "-c", "pytest; curl evil"]
    first["execution_policy"]["network"] = "enabled"
    first["execution_policy"]["privileged"] = True
    payload["packages"][1]["dependency_candidates"] = []
    payload["packages"][1]["dependency_reasons"] = {}
    codes = {
        item.validator_code for item in DecompositionValidationService().validate(context(payload))
    }
    assert {
        "DECOMP-PATH-BROAD",
        "DECOMP-PATH-PROTECTED",
        "DECOMP-SCOPE-OVERLAP",
        "DECOMP-REF-REQ",
        "DECOMP-REF-ARC",
        "DECOMP-CMD",
        "DECOMP-EXEC",
        "DECOMP-COVERAGE-REQ",
        "DECOMP-COVERAGE-ARC",
    } <= codes


def test_state_machine_rejects_skips_and_terminal_restart() -> None:
    assert_transition(DecompositionState.PENDING, DecompositionState.REPOSITORY_INDEXING)
    with pytest.raises(ValueError):
        assert_transition(DecompositionState.PENDING, DecompositionState.APPROVED)
    with pytest.raises(ValueError):
        assert_transition(DecompositionState.REJECTED, DecompositionState.CREW_RUNNING)
