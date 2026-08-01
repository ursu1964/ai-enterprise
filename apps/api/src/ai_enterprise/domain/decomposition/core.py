from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath


class DecompositionState(StrEnum):
    PENDING = "pending"
    REPOSITORY_INDEXING = "repository_indexing"
    REPOSITORY_INDEXED = "repository_indexed"
    CREW_RUNNING = "crew_running"
    CREW_COMPLETED = "crew_completed"
    NORMALIZING = "normalizing"
    GRAPH_BUILDING = "graph_building"
    VALIDATING = "validating"
    VALIDATION_FAILED = "validation_failed"
    AWAITING_REVIEW = "awaiting_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    FAILED = "failed"


TRANSITIONS = {
    DecompositionState.PENDING: {DecompositionState.REPOSITORY_INDEXING},
    DecompositionState.REPOSITORY_INDEXING: {
        DecompositionState.REPOSITORY_INDEXED,
        DecompositionState.FAILED,
    },
    DecompositionState.REPOSITORY_INDEXED: {DecompositionState.CREW_RUNNING},
    DecompositionState.CREW_RUNNING: {
        DecompositionState.CREW_COMPLETED,
        DecompositionState.FAILED,
    },
    DecompositionState.CREW_COMPLETED: {DecompositionState.NORMALIZING},
    DecompositionState.NORMALIZING: {
        DecompositionState.GRAPH_BUILDING,
        DecompositionState.VALIDATION_FAILED,
    },
    DecompositionState.GRAPH_BUILDING: {
        DecompositionState.VALIDATING,
        DecompositionState.VALIDATION_FAILED,
    },
    DecompositionState.VALIDATING: {
        DecompositionState.AWAITING_REVIEW,
        DecompositionState.VALIDATION_FAILED,
    },
    DecompositionState.AWAITING_REVIEW: {
        DecompositionState.APPROVED,
        DecompositionState.CHANGES_REQUESTED,
        DecompositionState.REJECTED,
    },
    DecompositionState.CHANGES_REQUESTED: {
        DecompositionState.CREW_RUNNING,
        DecompositionState.SUPERSEDED,
    },
    DecompositionState.APPROVED: {DecompositionState.SUPERSEDED},
}


def assert_transition(current: DecompositionState, target: DecompositionState) -> None:
    if target not in TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid decomposition transition: {current} -> {target}")


@dataclass(frozen=True, slots=True)
class DecompositionPolicy:
    version: str = "work-package-policy-v1"
    minimum_packages: int = 1
    maximum_packages: int = 50
    maximum_allowed_scopes_per_package: int = 12
    maximum_proposed_paths_per_package: int = 12
    maximum_dependencies_per_package: int = 8
    maximum_acceptance_criteria_per_package: int = 15
    maximum_test_commands_per_package: int = 10
    maximum_estimated_files: int = 20
    maximum_estimated_changed_lines: int = 800
    maximum_cpu: float = 4
    maximum_memory_mb: int = 4096
    maximum_pid_limit: int = 256
    maximum_timeout_seconds: int = 1800
    allowed_executables: frozenset[str] = frozenset(
        {
            "pytest",
            "python",
            "ruff",
            "mypy",
            "alembic",
            "npm",
            "pnpm",
            "yarn",
            "go",
            "cargo",
            "dotnet",
        }
    )
    reserved_keys: frozenset[str] = frozenset({"all", "root", "system", "admin"})


_SLUG = re.compile(r"[^a-z0-9]+")


def canonical_slug(value: str) -> str:
    result = _SLUG.sub("-", value.strip().lower()).strip("-")
    if not result:
        raise ValueError("Canonical package key is empty")
    return result


def normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def normalize_repository_path(value: str) -> str:
    raw = value.strip().replace("\\", "/")
    if raw.startswith("/"):
        raise ValueError("Absolute repository paths are prohibited")
    path = PurePosixPath(raw)
    if ".." in path.parts:
        raise ValueError("Repository path traversal is prohibited")
    normalized = str(path)
    if normalized in {"", "."}:
        raise ValueError("Repository path cannot be empty")
    return normalized


def path_matches_scope(path: str, scope: str) -> bool:
    candidate = PurePosixPath(normalize_repository_path(path))
    normalized_scope = normalize_repository_path(scope)
    if normalized_scope.endswith("/**"):
        root = PurePosixPath(normalized_scope[:-3])
        return candidate == root or root in candidate.parents
    return candidate.match(normalized_scope)


def canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


WORK_PACKAGE_NAMESPACE = uuid.UUID("ed5eea9f-e19e-4b83-b94f-1220c8879491")


def derive_package_id(
    *,
    project_id: str,
    architecture_hash: str,
    repository_tree_hash: str,
    policy_version: str,
    package_key: str,
) -> uuid.UUID:
    identity = "|".join(
        (project_id, architecture_hash, repository_tree_hash, policy_version, package_key)
    )
    return uuid.uuid5(WORK_PACKAGE_NAMESPACE, hashlib.sha256(identity.encode()).hexdigest())
