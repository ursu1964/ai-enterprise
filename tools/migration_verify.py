#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any


class MigrationFinding(Exception):
    pass


def _literal(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Tuple):
        return tuple(_literal(item) for item in node.elts)
    if isinstance(node, ast.List):
        return [_literal(item) for item in node.elts]
    return None


def _assigned_literal(module: ast.Module, name: str) -> Any:
    for statement in module.body:
        target: ast.expr | None = None
        value: ast.AST | None = None
        if isinstance(statement, ast.Assign):
            target = statement.targets[0] if statement.targets else None
            value = statement.value
        elif isinstance(statement, ast.AnnAssign):
            target = statement.target
            value = statement.value
        if isinstance(target, ast.Name) and target.id == name and value is not None:
            return _literal(value)
    return None


def _function(module: ast.Module, name: str) -> ast.FunctionDef | None:
    return next(
        (
            statement
            for statement in module.body
            if isinstance(statement, ast.FunctionDef) and statement.name == name
        ),
        None,
    )


def _is_empty_rollback(function: ast.FunctionDef | None) -> bool:
    if function is None:
        return True
    body = [
        statement
        for statement in function.body
        if not (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant))
    ]
    if not body:
        return True
    if all(isinstance(statement, ast.Pass) for statement in body):
        return True
    for statement in body:
        if isinstance(statement, ast.Raise):
            return True
    return False


def _normalize_down_revision(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value if item is not None)
    return (str(value),)


def verify(migrations_dir: Path) -> dict[str, Any]:
    findings: list[str] = []
    rows: list[dict[str, Any]] = []
    for path in sorted(migrations_dir.glob("*.py")):
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        revision = _assigned_literal(module, "revision")
        down_revisions = _normalize_down_revision(_assigned_literal(module, "down_revision"))
        upgrade = _function(module, "upgrade")
        downgrade = _function(module, "downgrade")
        if not isinstance(revision, str) or not revision:
            findings.append(f"{path.name}: missing revision")
            continue
        if upgrade is None:
            findings.append(f"{revision}: missing upgrade()")
        if _is_empty_rollback(downgrade):
            findings.append(f"{revision}: downgrade() is missing or not feasible")
        rows.append(
            {
                "path": str(path),
                "revision": revision,
                "down_revisions": down_revisions,
            }
        )

    revisions = {row["revision"] for row in rows}
    duplicates = sorted(
        revision for revision in revisions if sum(row["revision"] == revision for row in rows) > 1
    )
    for revision in duplicates:
        findings.append(f"duplicate revision: {revision}")

    for row in rows:
        for parent in row["down_revisions"]:
            if parent not in revisions:
                findings.append(f"{row['revision']}: dangling down_revision {parent}")

    children: dict[str, list[str]] = {revision: [] for revision in revisions}
    for row in rows:
        for parent in row["down_revisions"]:
            if parent in children:
                children[parent].append(row["revision"])
    bases = sorted(row["revision"] for row in rows if not row["down_revisions"])
    heads = sorted(revision for revision, values in children.items() if not values)
    if len(bases) != 1:
        findings.append(f"expected exactly one base revision, found {len(bases)}")
    if len(heads) != 1:
        findings.append(f"expected exactly one head revision, found {len(heads)}")

    visited: set[str] = set()
    visiting: set[str] = set()
    parent_map = {
        row["revision"]: tuple(parent for parent in row["down_revisions"] if parent in revisions)
        for row in rows
    }

    def visit(revision: str) -> None:
        if revision in visiting:
            findings.append(f"cycle detected at revision {revision}")
            return
        if revision in visited:
            return
        visiting.add(revision)
        for parent in parent_map[revision]:
            visit(parent)
        visiting.remove(revision)
        visited.add(revision)

    for revision in sorted(revisions):
        visit(revision)

    return {
        "conformant": not findings,
        "migration_count": len(rows),
        "base_revisions": bases,
        "head_revisions": heads,
        "rollback_feasible_count": sum(
            1 for row in rows if f"{row['revision']}: downgrade() is missing or not feasible" not in findings
        ),
        "findings": sorted(set(findings)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Alembic migration graph integrity.")
    parser.add_argument("--migrations-dir", default="migrations/versions")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = verify(Path(args.migrations_dir))
    if args.json:
        print(json.dumps(report, sort_keys=True))
    elif report["conformant"]:
        print(f"Migration graph verified: {report['migration_count']} migration(s)")
    else:
        for finding in report["findings"]:
            print(finding)
    return 0 if report["conformant"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
