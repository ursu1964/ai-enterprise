"""Initialize production evidence input files from templates without approving production."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_FILES: tuple[tuple[str, str, str], ...] = (
    (
        "infrastructure_choices",
        "docs/enterprise/real-world-infrastructure-decisions.template.json",
        "docs/enterprise/real-world-infrastructure-decisions.json",
    ),
    (
        "production_readiness_evidence",
        "docs/enterprise/production-readiness-evidence.template.json",
        "docs/enterprise/production-readiness-evidence.json",
    ),
)


def initialize(
    root: Path,
    *,
    force: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    files: list[dict[str, Any]] = []
    for name, template, target in DEFAULT_FILES:
        template_path = root / template
        target_path = root / target
        if not template_path.is_file():
            files.append(
                {
                    "name": name,
                    "template": template,
                    "target": target,
                    "status": "missing_template",
                    "action": "Restore the template before initializing evidence files.",
                }
            )
            continue
        if target_path.exists() and not force:
            files.append(
                {
                    "name": name,
                    "template": template,
                    "target": target,
                    "status": "already_exists",
                    "action": "Review the existing file or rerun with --force to replace it.",
                }
            )
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
        files.append(
            {
                "name": name,
                "template": template,
                "target": target,
                "status": "created" if not force else "replaced",
                "action": "Fill this file with real production values and evidence references.",
            }
        )

    created_or_replaced = sum(1 for item in files if item["status"] in {"created", "replaced"})
    blocked = any(item["status"] == "missing_template" for item in files)
    report_without_hash: dict[str, Any] = {
        "schema_version": "1.0",
        "status": "blocked" if blocked else "initialized",
        "production_allowed": False,
        "created_or_replaced": created_or_replaced,
        "files": files,
        "next_commands": [
            "rtk make infrastructure-choices-verify",
            "rtk make production-readiness",
            "rtk make production-evidence-plan",
        ],
        "next_action": (
            "Fill generated files with real reviewed values; production remains blocked until "
            "readiness validation passes."
        ),
    }
    return report_without_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = initialize(args.root, force=args.force)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        target = args.output if args.output.is_absolute() else args.root / args.output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "initialized" else 1


if __name__ == "__main__":
    raise SystemExit(main())
