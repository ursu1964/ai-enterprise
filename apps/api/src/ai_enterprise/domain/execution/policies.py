from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True, slots=True)
class RuntimeLimits:
    timeout_seconds: int = 900
    implementation_timeout_seconds: int = 600
    test_timeout_seconds: int = 300
    nano_cpus: int = 1_000_000_000
    memory_bytes: int = 2 * 1024 * 1024 * 1024
    memory_swap_bytes: int = 2 * 1024 * 1024 * 1024
    pids_limit: int = 256
    tmpfs_size_bytes: int = 256 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ExecutionScope:
    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]

    def is_allowed(self, candidate: str) -> bool:
        path = self._normalize(candidate)

        if any(self._contains(prefix, path) for prefix in self.forbidden_paths):
            return False

        return any(self._contains(prefix, path) for prefix in self.allowed_paths)

    @staticmethod
    def _normalize(value: str) -> PurePosixPath:
        path = PurePosixPath(value)

        if path.is_absolute():
            raise ValueError(f"Absolute paths are prohibited: {value}")

        if ".." in path.parts:
            raise ValueError(f"Parent traversal is prohibited: {value}")

        return path

    @staticmethod
    def _contains(prefix_value: str, candidate: PurePosixPath) -> bool:
        prefix = PurePosixPath(prefix_value)

        if prefix == PurePosixPath("."):
            return True

        return candidate == prefix or prefix in candidate.parents


DEFAULT_FORBIDDEN_PATHS = (
    ".git",
    ".github/workflows",
    ".env",
    ".env.local",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "/etc",
    "/proc",
    "/sys",
)
