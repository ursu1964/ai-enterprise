from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ai_enterprise.domain.review.exceptions import (
    PatchApplyError,
    PatchHashMismatchError,
)


@dataclass(frozen=True, slots=True)
class AppliedPatch:
    patch_sha256: str
    patch_size_bytes: int


class PatchApplier:
    def verify_and_apply(
        self,
        *,
        repository: Path,
        patch_path: Path,
        expected_sha256: str,
        maximum_patch_bytes: int,
    ) -> AppliedPatch:
        patch_bytes = patch_path.read_bytes()
        actual_sha256 = hashlib.sha256(patch_bytes).hexdigest()

        if actual_sha256 != expected_sha256:
            raise PatchHashMismatchError(
                f"Expected patch SHA-256 {expected_sha256}, "
                f"received {actual_sha256}"
            )

        if len(patch_bytes) > maximum_patch_bytes:
            raise PatchApplyError(
                f"Patch size {len(patch_bytes)} exceeds limit "
                f"{maximum_patch_bytes}"
            )

        self._validate_patch(repository, patch_path)
        self._apply_patch(repository, patch_path)

        return AppliedPatch(
            patch_sha256=actual_sha256,
            patch_size_bytes=len(patch_bytes),
        )

    @staticmethod
    def _validate_patch(repository: Path, patch_path: Path) -> None:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "apply",
                "--check",
                "--binary",
                "--whitespace=error-all",
                str(patch_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
            env={
                **os.environ,
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_TERMINAL_PROMPT": "0",
            },
        )

        if result.returncode != 0:
            raise PatchApplyError(
                "Patch validation failed: "
                + result.stderr.strip()
            )

    @staticmethod
    def _apply_patch(repository: Path, patch_path: Path) -> None:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "apply",
                "--binary",
                "--index",
                "--whitespace=error-all",
                str(patch_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
            env={
                **os.environ,
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_TERMINAL_PROMPT": "0",
            },
        )

        if result.returncode != 0:
            raise PatchApplyError(
                "Patch application failed: "
                + result.stderr.strip()
            )
