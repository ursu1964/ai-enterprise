#!/usr/bin/env python3
"""Check repository tooling invariants that commonly fail only in CI."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

ACTION_MINIMUM_MAJORS = {
    "actions/checkout": 5,
    "actions/setup-python": 6,
    "actions/upload-artifact": 4,
    "actions/download-artifact": 4,
}
ACTION_PATTERN = re.compile(r"^\s*-?\s*uses:\s*([^\s@]+)@v(\d+)(?:\b|\.)", re.MULTILINE)


def check_tooling_invariants(root: Path) -> dict[str, Any]:
    root = root.resolve()
    findings: list[str] = []
    checked_tools = 0
    checked_actions = 0

    for tool in sorted((root / "tools").glob("*.py")):
        checked_tools += 1
        first_line = tool.read_bytes().splitlines()[:1]
        has_shebang = bool(first_line and first_line[0].startswith(b"#!"))
        if has_shebang and not os.access(tool, os.X_OK):
            findings.append(f"{tool.relative_to(root)}: shebang script is not executable")

    workflow_dir = root / ".github" / "workflows"
    workflows = sorted((*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")))
    for workflow in workflows:
        content = workflow.read_text(encoding="utf-8")
        for action, major_text in ACTION_PATTERN.findall(content):
            checked_actions += 1
            minimum = ACTION_MINIMUM_MAJORS.get(action)
            if minimum is not None and int(major_text) < minimum:
                findings.append(
                    f"{workflow.relative_to(root)}: {action}@v{major_text} is older than "
                    f"the required v{minimum}"
                )

    return {
        "conformant": not findings,
        "checked_tools": checked_tools,
        "checked_actions": checked_actions,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = check_tooling_invariants(args.root)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["conformant"]:
        print(
            "Tooling invariants passed: "
            f"{report['checked_tools']} tools and "
            f"{report['checked_actions']} workflow actions checked."
        )
    else:
        for finding in report["findings"]:
            print(f"ERROR: {finding}")
    return 0 if report["conformant"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
