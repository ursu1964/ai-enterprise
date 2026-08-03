#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _safe_name(name: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in name)


def run_gate(
    *,
    root: Path,
    name: str,
    command: str,
    output_dir: Path,
    timeout: int,
) -> dict[str, Any]:
    started = time.monotonic()
    target_dir = output_dir if output_dir.is_absolute() else root / output_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / f"{_safe_name(name)}.log"
    result = subprocess.run(
        command,
        cwd=root,
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    duration = round(time.monotonic() - started, 3)
    output_path.write_text(
        result.stdout + ("\n" if result.stdout and result.stderr else "") + result.stderr,
        encoding="utf-8",
    )
    return {
        "status": "passed" if result.returncode == 0 else "failed",
        "command": command,
        "return_code": result.returncode,
        "duration_seconds": duration,
        "output_path": str(output_path.relative_to(root)),
        "recorded_at": datetime.now(UTC).isoformat(),
    }


def write_evidence(
    *,
    root: Path,
    gate_commands: dict[str, str],
    output: Path,
    output_dir: Path,
    timeout: int,
) -> dict[str, Any]:
    gates = {
        name: run_gate(
            root=root,
            name=name,
            command=command,
            output_dir=output_dir,
            timeout=timeout,
        )
        for name, command in gate_commands.items()
    }
    document = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "gates": gates,
    }
    target = output if output.is_absolute() else root / output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return document


def _parse_gate_command(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("gate command must use name=command")
    name, command = value.split("=", 1)
    name = name.strip()
    command = command.strip()
    if not name or not command:
        raise argparse.ArgumentTypeError("gate command requires non-empty name and command")
    return name, command


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture release gate command evidence.")
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--gate-command",
        action="append",
        type=_parse_gate_command,
        required=True,
        help="Gate command in name=command form. May be repeated.",
    )
    parser.add_argument("--output", default="artifacts/gate-evidence.json")
    parser.add_argument("--output-dir", default="artifacts/release-gates")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    document = write_evidence(
        root=root,
        gate_commands=dict(args.gate_command),
        output=Path(args.output),
        output_dir=Path(args.output_dir),
        timeout=args.timeout,
    )
    print(json.dumps(document, sort_keys=True))
    return 0 if all(gate["status"] == "passed" for gate in document["gates"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
