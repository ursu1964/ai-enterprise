from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath

from ai_enterprise.domain.execution.policies import ExecutionScope

from .exceptions import PatchVerificationError
from .git_client import GitClient
from .models import IntegrationBinding

_HEADER = re.compile(rb"^(?:diff --git|---|\+\++) (?:a/|b/)?(.+)$")


class VerifiedPatchApplier:
    def __init__(self, *, git: GitClient | None = None, maximum_bytes: int = 1_048_576) -> None:
        self._git = git or GitClient()
        self._maximum_bytes = maximum_bytes

    def verify_and_apply(
        self,
        *,
        repository: Path,
        patch_path: Path,
        binding: IntegrationBinding,
        scope: ExecutionScope,
    ) -> str:
        patch = patch_path.read_bytes()
        if len(patch) > self._maximum_bytes:
            raise PatchVerificationError("PATCH_TOO_LARGE")
        actual = hashlib.sha256(patch).hexdigest()
        hashes = {
            actual,
            binding.patch_sha256,
            binding.artifact_sha256,
            binding.audit_patch_sha256,
            binding.approved_patch_sha256,
        }
        if len(hashes) != 1:
            raise PatchVerificationError("PATCH_ARTIFACT_MISMATCH")

        for path in self._paths(patch):
            self._validate_path(path, scope)
        forbidden_markers = (b".gitmodules", b".git/hooks", b"new file mode 160000")
        if any(marker in patch for marker in forbidden_markers):
            raise PatchVerificationError("FORBIDDEN_GIT_METADATA")

        self._git.run(
            (
                "apply", "--check", "--binary", "--whitespace=error",
                "--recount", "--", str(patch_path),
            ),
            cwd=repository,
        )
        self._git.run(
            (
                "apply", "--index", "--binary", "--whitespace=error",
                "--recount", "--", str(patch_path),
            ),
            cwd=repository,
        )
        return actual

    @staticmethod
    def _paths(patch: bytes) -> tuple[str, ...]:
        paths: set[str] = set()
        for line in patch.splitlines():
            match = _HEADER.match(line)
            if match is None:
                continue
            raw = match.group(1)
            # A diff --git header has two paths. Quoted/escaped paths are rejected,
            # rather than interpreted differently from Git.
            for part in raw.split(b" "):
                if part == b"/dev/null":
                    continue
                if part.startswith((b"a/", b"b/")):
                    part = part[2:]
                if not part or part.startswith(b'"') or b"\\" in part:
                    raise PatchVerificationError("UNSUPPORTED_PATCH_PATH")
                try:
                    paths.add(part.decode("utf-8", errors="strict"))
                except UnicodeDecodeError as exc:
                    raise PatchVerificationError("INVALID_PATCH_PATH") from exc
        if not paths:
            raise PatchVerificationError("PATCH_HAS_NO_PATHS")
        return tuple(sorted(paths))

    @staticmethod
    def _validate_path(value: str, scope: ExecutionScope) -> None:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise PatchVerificationError("PATH_ESCAPE_DETECTED")
        if path.parts[0] == ".git" or value == ".gitmodules":
            raise PatchVerificationError("FORBIDDEN_GIT_METADATA")
        try:
            allowed = scope.is_allowed(value)
        except ValueError:
            allowed = False
        if not allowed:
            raise PatchVerificationError(f"PATCH_SCOPE_VIOLATION: {value}")
