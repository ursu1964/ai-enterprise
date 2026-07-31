from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ai_enterprise.domain.execution.exceptions import PatchGenerationError


@dataclass(frozen=True, slots=True)
class PatchArtifact:
    path: Path
    sha256: str
    size_bytes: int


class PatchBuilder:
    def __init__(self, artifacts_root: Path) -> None:
        self._artifacts_root = artifacts_root.resolve()

    def build(
        self,
        *,
        execution_id: str,
        repository: Path,
        maximum_patch_bytes: int,
    ) -> PatchArtifact:
        execution_dir = self._artifacts_root / execution_id
        execution_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        patch_path = execution_dir / "changes.patch"

        self._stage_intent_to_add(repository)

        result = subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "diff",
                "--binary",
                "--full-index",
                "--no-ext-diff",
                "--no-renames",
                "HEAD",
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )

        patch_bytes = result.stdout

        if not patch_bytes:
            raise PatchGenerationError("Execution produced no patch")

        if len(patch_bytes) > maximum_patch_bytes:
            raise PatchGenerationError(
                f"Patch size {len(patch_bytes)} exceeds maximum "
                f"{maximum_patch_bytes}"
            )

        patch_path.write_bytes(patch_bytes)

        return PatchArtifact(
            path=patch_path,
            sha256=hashlib.sha256(patch_bytes).hexdigest(),
            size_bytes=len(patch_bytes),
        )

    @staticmethod
    def _stage_intent_to_add(repository: Path) -> None:
        subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "add",
                "--intent-to-add",
                "--all",
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
