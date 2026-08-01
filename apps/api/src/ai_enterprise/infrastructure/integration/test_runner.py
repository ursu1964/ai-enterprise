from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from collections.abc import Iterable
from pathlib import Path

from .exceptions import ApprovedTestError
from .models import ApprovedTestCommand, TestRunEvidence

_ALLOWED_ENV = frozenset({"PYTHONHASHSEED", "TZ", "LANG", "LC_ALL"})


class ApprovedTestRunner:
    """Run an authoritative argv allowlist with no shell or ambient credentials."""

    def __init__(
        self,
        *,
        allowed_executables: Iterable[str],
        maximum_output_bytes: int = 2 * 1024 * 1024,
    ) -> None:
        self._allowed_executables = frozenset(allowed_executables)
        self._maximum_output_bytes = maximum_output_bytes

    def run(
        self,
        *,
        repository: Path,
        commands: tuple[ApprovedTestCommand, ...],
        temporary_home: Path,
        temporary_directory: Path,
    ) -> tuple[TestRunEvidence, ...]:
        evidence: list[TestRunEvidence] = []
        for index, command in enumerate(commands):
            self._validate(command)
            environment = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": str(temporary_home),
                "TMPDIR": str(temporary_directory),
                "PYTHONHASHSEED": "0",
                "TZ": "UTC",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                **dict(command.environment),
            }
            started = time.monotonic()
            try:
                result = subprocess.run(
                    command.argv,
                    cwd=repository,
                    env=environment,
                    shell=False,
                    check=False,
                    capture_output=True,
                    timeout=command.timeout_seconds,
                )
                status = "passed" if result.returncode == 0 else "failed"
                exit_code: int | None = result.returncode
                stdout = self._bounded(result.stdout)
                stderr = self._bounded(result.stderr)
            except subprocess.TimeoutExpired as exc:
                status = "timed_out"
                exit_code = None
                stdout = self._bounded(exc.stdout or b"")
                stderr = self._bounded(exc.stderr or b"")
            duration = int((time.monotonic() - started) * 1000)
            digest = hashlib.sha256(
                json.dumps(list(command.argv), separators=(",", ":")).encode()
            ).hexdigest()
            item = TestRunEvidence(
                command_index=index,
                argv=command.argv,
                command_sha256=digest,
                status=status,
                exit_code=exit_code,
                duration_ms=duration,
                stdout=stdout,
                stderr=stderr,
            )
            evidence.append(item)
            if status != "passed":
                raise ApprovedTestError(status.upper(), evidence=tuple(evidence))
        return tuple(evidence)

    def _validate(self, command: ApprovedTestCommand) -> None:
        if not command.argv or command.argv[0] not in self._allowed_executables:
            raise ApprovedTestError("UNAPPROVED_EXECUTABLE")
        if command.timeout_seconds <= 0:
            raise ApprovedTestError("INVALID_TEST_TIMEOUT")
        if not set(command.environment).issubset(_ALLOWED_ENV):
            raise ApprovedTestError("UNAPPROVED_ENVIRONMENT")
        if any("\x00" in value for value in command.argv):
            raise ApprovedTestError("INVALID_TEST_ARGUMENT")

    def _bounded(self, value: bytes) -> str:
        suffix = ""
        if len(value) > self._maximum_output_bytes:
            value = value[: self._maximum_output_bytes]
            suffix = "\n[output truncated]"
        return value.decode("utf-8", errors="replace") + suffix
