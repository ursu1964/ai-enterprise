from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


WORKSPACE = Path("/workspace")


class ApplyEditsError(Exception):
    pass


def safe_workspace_path(value: str) -> Path:
    path = Path(value)

    if path.is_absolute():
        raise ApplyEditsError(f"Absolute path is prohibited: {value}")

    if ".." in path.parts:
        raise ApplyEditsError(f"Parent traversal is prohibited: {value}")

    target = (WORKSPACE / path).resolve()

    if target != WORKSPACE.resolve() and WORKSPACE.resolve() not in target.parents:
        raise ApplyEditsError(f"Edit escapes workspace: {value}")

    return target


def apply_edits(edits: list[dict[str, object]]) -> None:
    if not edits:
        raise ApplyEditsError("Edit list is empty")

    for edit in edits:
        if not isinstance(edit, dict):
            raise ApplyEditsError("Edit entries must be objects")

        raw_path = edit.get("path")
        mode = edit.get("mode", "create")
        content = edit.get("content")

        if not isinstance(raw_path, str) or not raw_path:
            raise ApplyEditsError("Edit is missing a path")

        if mode not in {"create", "overwrite", "append"}:
            raise ApplyEditsError(f"Unsupported edit mode: {mode}")

        if not isinstance(content, str):
            raise ApplyEditsError(f"Edit for {raw_path} has non-string content")

        target = safe_workspace_path(raw_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        if mode == "append":
            with target.open("a", encoding="utf-8") as handle:
                handle.write(content)
        else:
            target.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()

    try:
        edits = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"apply_edits: cannot read edits: {exc}", file=sys.stderr)
        return 10

    try:
        apply_edits(edits)
    except ApplyEditsError as exc:
        print(f"apply_edits: {exc}", file=sys.stderr)
        return 10

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
