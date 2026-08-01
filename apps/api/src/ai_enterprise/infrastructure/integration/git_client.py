from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .exceptions import IntegrationGitError


@dataclass(frozen=True, slots=True)
class GitResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class GitClient:
    """Invoke Git without a shell and without ambient user configuration."""

    def __init__(self, *, maximum_output_bytes: int = 2 * 1024 * 1024) -> None:
        self._maximum_output_bytes = maximum_output_bytes

    def run(
        self,
        arguments: Sequence[str],
        *,
        cwd: Path | None = None,
        timeout_seconds: int = 120,
        extra_env: Mapping[str, str] | None = None,
        check: bool = True,
        input_bytes: bytes | None = None,
    ) -> GitResult:
        if not arguments or any("\x00" in value for value in arguments):
            raise ValueError("Git arguments must be non-empty and NUL-free")

        command = (
            "git",
            "-c",
            "credential.helper=",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "protocol.file.allow=always",
            *arguments,
        )
        environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "/bin/false",
            "HOME": "/nonexistent",
        }
        if extra_env:
            environment.update(extra_env)

        completed = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            input=input_bytes,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
        stdout = self._decode(completed.stdout)
        stderr = self._decode(completed.stderr)
        result = GitResult(tuple(arguments), completed.returncode, stdout, stderr)
        if check and completed.returncode != 0:
            raise IntegrationGitError(
                f"Git command {arguments[0]!r} failed with exit code "
                f"{completed.returncode}: {stderr.strip()}"
            )
        return result

    def _decode(self, value: bytes) -> str:
        if len(value) > self._maximum_output_bytes:
            value = value[: self._maximum_output_bytes]
            suffix = "\n[output truncated]"
        else:
            suffix = ""
        return value.decode("utf-8", errors="replace") + suffix
