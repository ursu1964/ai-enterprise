from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


WORKSPACE = Path("/workspace")
INPUT_PATH = Path("/runtime-input/review.json")
OUTPUT_PATH = Path("/runtime-output/result.json")
LOG_PATH = Path("/runtime-output/review.log")


class RunnerError(Exception):
    pass


def write_event(event_type: str, **payload: Any) -> None:
    event = {
        "timestamp_ns": time.time_ns(),
        "event_type": event_type,
        "payload": payload,
    }

    encoded = json.dumps(event, separators=(",", ":"), sort_keys=True)

    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(encoded)
        handle.write("\n")


def validate_argv(argv: object) -> list[str]:
    if not isinstance(argv, list) or not argv:
        raise RunnerError("Command must be a non-empty argv array")

    if not all(isinstance(value, str) and value for value in argv):
        raise RunnerError("Every argv member must be a non-empty string")

    prohibited = {
        "docker",
        "podman",
        "nerdctl",
        "mount",
        "umount",
        "sudo",
        "su",
        "ssh",
        "scp",
        "curl",
        "wget",
        "nc",
        "ncat",
        "socat",
    }

    executable = Path(argv[0]).name

    if executable in prohibited:
        raise RunnerError(f"Prohibited executable: {executable}")

    return argv


def run_command(
    *,
    name: str,
    argv: list[str],
    timeout_seconds: int,
    environment: dict[str, str],
) -> dict[str, Any]:
    command = validate_argv(argv)

    write_event(
        "review.check.started",
        name=name,
        argv=command,
        timeout_seconds=timeout_seconds,
    )

    started_ns = time.monotonic_ns()

    try:
        completed = subprocess.run(
            command,
            cwd=WORKSPACE,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
            start_new_session=True,
        )

        duration_ms = (time.monotonic_ns() - started_ns) // 1_000_000

        result = {
            "name": name,
            "argv": command,
            "exit_code": completed.returncode,
            "duration_ms": duration_ms,
            "stdout": completed.stdout.decode("utf-8", errors="replace"),
            "stderr": completed.stderr.decode("utf-8", errors="replace"),
            "timed_out": False,
        }

        write_event(
            "review.check.finished",
            name=name,
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )

        return result
    except subprocess.TimeoutExpired as exc:
        duration_ms = (time.monotonic_ns() - started_ns) // 1_000_000

        result = {
            "name": name,
            "argv": command,
            "exit_code": None,
            "duration_ms": duration_ms,
            "stdout": (exc.stdout or b"").decode("utf-8", errors="replace"),
            "stderr": (exc.stderr or b"").decode("utf-8", errors="replace"),
            "timed_out": True,
        }

        write_event(
            "review.check.timed_out",
            name=name,
            duration_ms=duration_ms,
        )

        return result


def main() -> int:
    config = json.loads(INPUT_PATH.read_text(encoding="utf-8"))

    environment = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ.get("HOME", "/home/reviewer"),
        "TMPDIR": "/tmp",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "CI": "true",
    }

    output: dict[str, Any] = {
        "schema_version": 1,
        "approved_tests": [],
        "review_checks": [],
        "findings": [],
        "success": False,
    }

    all_required_passed = True

    for index, test in enumerate(config["approved_tests"]):
        test_result = run_command(
            name=f"approved-test-{index}",
            argv=test["argv"],
            timeout_seconds=test["timeout_seconds"],
            environment=environment,
        )

        test_result["required"] = bool(test.get("required", True))
        output["approved_tests"].append(test_result)

        if (
            test_result["timed_out"]
            or test_result["exit_code"] != 0
        ) and test_result["required"]:
            all_required_passed = False

    for index, check in enumerate(config["review_checks"]):
        check_result = run_command(
            name=check.get("name", f"review-check-{index}"),
            argv=check["argv"],
            timeout_seconds=check["timeout_seconds"],
            environment=environment,
        )

        check_result["required"] = bool(check.get("required", True))
        output["review_checks"].append(check_result)

        if (
            check_result["timed_out"]
            or check_result["exit_code"] != 0
        ) and check_result["required"]:
            all_required_passed = False

    output["success"] = all_required_passed

    OUTPUT_PATH.write_text(
        json.dumps(output, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return 0 if all_required_passed else 30


if __name__ == "__main__":
    raise SystemExit(main())
