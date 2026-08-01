#!/usr/bin/env python3
"""Generate deterministic infrastructure target descriptors from the approved specification."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

GENERATOR = "engineering-artifact-generator@1.0.0"
SOURCE = Path("specifications/engineering/infrastructure.v1.json")
OUTPUT = Path("infrastructure/generated/engineering-targets.json")


def _inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _load_json(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        document: dict[str, Any] = {}
        for key, value in items:
            if key in document:
                raise ValueError(f"duplicate JSON key: {key}")
            document[key] = value
        return document

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"invalid number: {value}")
        ),
    )
    if not isinstance(value, dict):
        raise TypeError("infrastructure specification must be an object")
    return value


def render(root: Path) -> str:
    source_path = root / SOURCE
    if not _inside(root, source_path) or source_path.is_symlink():
        raise ValueError(
            "infrastructure specification must be a regular in-repository file"
        )
    raw = source_path.read_bytes()
    specification = _load_json(source_path)
    service_ids = sorted(service["service_id"] for service in specification["services"])
    document = {
        "generator": GENERATOR,
        "source": {
            "path": str(SOURCE),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "specification_id": specification["specification_id"],
            "version": specification["version"],
        },
        "service_definitions": sorted(
            specification["services"], key=lambda service: service["service_id"]
        ),
        "targets": {
            target: {"services": service_ids}
            for target in sorted(specification["targets"])
        },
    }
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--print", action="store_true", dest="print_output")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        expected = render(root)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"generation refused: {exc}", file=sys.stderr)
        return 1
    output = root / OUTPUT
    if not _inside(root, output) or output.is_symlink():
        print(
            "generation refused: output must be a regular in-repository file",
            file=sys.stderr,
        )
        return 1
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(expected, encoding="utf-8")
        return 0
    if args.print_output:
        print(expected, end="")
        return 0
    actual = output.read_text(encoding="utf-8") if output.is_file() else ""
    if actual != expected:
        print(f"generated artifact drift: {OUTPUT}", file=sys.stderr)
        return 1
    print(f"generated artifact current: {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
