import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GitResult:
    returncode: int
    stdout: str
    stderr: str


class IsolatedGitRunner:
    """Run Git without a shell, credential helpers, hooks, or user config."""

    def __init__(self, git_binary: str = "git") -> None:
        self._git_binary = git_binary

    def run(
        self,
        repository: Path,
        *arguments: str,
        input_text: str | None = None,
        timeout_seconds: int = 120,
    ) -> GitResult:
        completed = subprocess.run(
            [
                self._git_binary,
                "-c",
                "credential.helper=",
                "-c",
                "core.hooksPath=/dev/null",
                *arguments,
            ],
            cwd=repository,
            env={
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": "/nonexistent",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_EDITOR": "/bin/false",
                "GIT_SEQUENCE_EDITOR": "/bin/false",
                "GIT_TERMINAL_PROMPT": "0",
                "LC_ALL": "C",
            },
            shell=False,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
        return GitResult(completed.returncode, completed.stdout, completed.stderr)
