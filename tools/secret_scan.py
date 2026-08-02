#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from ai_enterprise.infrastructure.review.secret_scanner import SecretScanner  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan repository content for secret material.")
    parser.add_argument("--all", action="store_true", help="Scan the full repository tree.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of text.",
    )
    parser.add_argument("repository", nargs="?", default=".")
    args = parser.parse_args()

    repository = Path(args.repository).resolve()
    scanner = SecretScanner()
    findings = scanner.scan_all(repository) if args.all else scanner.scan(repository)
    payload = {
        "repository": str(repository),
        "mode": "all" if args.all else "staged",
        "finding_count": len(findings),
        "findings": [
            {
                "rule_id": finding.rule_id,
                "severity": finding.severity.value,
                "file_path": finding.file_path,
                "line_start": finding.line_start,
                "line_end": finding.line_end,
                "title": finding.title,
            }
            for finding in findings
        ],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif findings:
        for finding in findings:
            print(
                f"{finding.severity.value}: {finding.rule_id} "
                f"{finding.file_path}:{finding.line_start}"
            )
    else:
        print("No secret material detected.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
