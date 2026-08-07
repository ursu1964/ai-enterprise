#!/usr/bin/env python3
"""Deterministic Enterprise Technical Reference Architecture fitness checks."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import jsonschema

ETRA_VERSION = "1.0"
ETRA_REPORT_SCHEMA_REF = "schemas/release-artifacts/etra-conformance-report.schema.json"
REQUIRED_PATHS = (
    "apps",
    "apps/api/src",
    "apps/api/tests",
    "docs/architecture",
    "migrations/versions",
    "docs",
    "docs/etra",
    "docs/adrs",
    "docs/reference-architecture",
    "docs/runbooks",
    "tools",
)
ARCHITECTURE_FILES = (
    "README.md",
    "views.md",
    "domain-model.md",
    "context-map.md",
    "agent-catalog.md",
    "crew-catalog.md",
    "workflow-catalog.md",
    "module-catalog.md",
    "mvp-vertical-slice.md",
    "application-kernel.md",
    "security-governance.md",
    "project-formation-orchestration.md",
    "query-platform.md",
    "model-prompt-governance.md",
)
DOCS_INDEX_LINKS = (
    "enterprise/README.md",
    "architecture/README.md",
    "reference-architecture/README.md",
    "etra/README.md",
    "adrs/README.md",
    "runbooks/service-operations.md",
)
STANDARD_FILES = (
    "README.md",
    "repository-standard.md",
    "service-standard.md",
    "api-standard.md",
    "event-standard.md",
    "database-standard.md",
    "domain-standard.md",
    "workflow-standard.md",
    "agent-standard.md",
    "prompt-standard.md",
    "policy-standard.md",
    "observability-standard.md",
    "security-standard.md",
    "testing-standard.md",
    "documentation-standard.md",
    "deployment-standard.md",
    "configuration-standard.md",
    "compatibility-standard.md",
    "extension-standard.md",
    "reference-technologies.md",
    "adr-process.md",
    "adr-template.md",
    "engineering-review-checklist.md",
)
ADR_SECTIONS = (
    "Context",
    "Decision",
    "Alternatives considered",
    "Consequences",
    "Constitutional principles affected",
    "Migration and compatibility implications",
    "Security and privacy implications",
    "Observability and operational implications",
    "Verification and rollback",
    "References",
)
CONTRACT_SECTIONS = (
    "Purpose",
    "Responsibilities",
    "Scope",
    "Non-Scope",
    "Viewpoints",
    "Data Model",
    "Interfaces",
    "Dependencies",
    "Internal Components",
    "Workflow",
    "Implementation Plan",
    "Testing",
    "Security",
    "Observability",
    "Future Evolution",
    "References",
)
FULL_CONTRACT_STATUSES = ("active", "accepted")
REFERENCE_CATALOG_REQUIRED_KEYS = (
    "schema_version",
    "title",
    "chapter_contract",
    "required_viewpoints",
    "sections",
)
DOC_STUB_MARKERS = (
    "will own",
    "will explain",
    "will describe",
    "TODO",
    "TBD",
)
DOC_LINK_ROOTS = (
    "docs/README.md",
    "docs/architecture",
    "docs/reference-architecture",
    "docs/adrs",
)
FORBIDDEN_DOMAIN_IMPORTS = (
    "fastapi",
    "sqlalchemy",
    "crewai",
    "ai_enterprise.api",
    "ai_enterprise.infrastructure",
)


@dataclass(frozen=True, slots=True)
class Finding:
    check: str
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class Report:
    standard_version: str
    conformant: bool
    checks: int
    findings: tuple[Finding, ...]
    schema_version: str = "1.0"
    schema_ref: str = ETRA_REPORT_SCHEMA_REF


def _python_imports(path: Path) -> tuple[set[str], str | None]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        return set(), str(exc)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(f"{'.' * node.level}{node.module or ''}")
        elif isinstance(node, ast.Call):
            dynamic_import = (isinstance(node.func, ast.Name) and node.func.id == "__import__") or (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "importlib"
                and node.func.attr == "import_module"
            )
            if (
                dynamic_import
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                imports.add(node.args[0].value)
    return imports, None


def _is_forbidden_domain_import(name: str) -> bool:
    normalized = name.lstrip(".")
    if normalized == "infrastructure" or normalized.startswith("infrastructure."):
        return True
    return any(
        normalized == forbidden or normalized.startswith(f"{forbidden}.")
        for forbidden in FORBIDDEN_DOMAIN_IMPORTS
    )


def _migration_graph(revision_dir: Path) -> tuple[set[str], tuple[str, ...]]:
    graph: dict[str, tuple[str, ...]] = {}
    issues: list[str] = []
    for path in sorted(revision_dir.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as exc:
            issues.append(f"{path.name}: cannot parse: {exc}")
            continue
        values: dict[str, object] = {}
        for node in tree.body:
            target: ast.expr | None = None
            value: ast.expr | None = None
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target, value = node.targets[0], node.value
            elif isinstance(node, ast.AnnAssign):
                target, value = node.target, node.value
            if (
                isinstance(target, ast.Name)
                and target.id in {"revision", "down_revision"}
                and value
            ):
                try:
                    values[target.id] = ast.literal_eval(value)
                except (ValueError, TypeError):
                    issues.append(f"{path.name}: {target.id} must be a literal")
        revision = values.get("revision")
        down_revision = values.get("down_revision")
        if not isinstance(revision, str) or not revision:
            issues.append(f"{path.name}: missing literal revision")
            continue
        if revision in graph:
            issues.append(f"duplicate revision: {revision}")
        if down_revision is None:
            parents: tuple[str, ...] = ()
        elif isinstance(down_revision, str):
            parents = (down_revision,)
        elif isinstance(down_revision, tuple) and all(
            isinstance(item, str) for item in down_revision
        ):
            parents = down_revision
        else:
            issues.append(f"{path.name}: invalid down_revision")
            parents = ()
        graph[revision] = parents
    revisions = set(graph)
    referenced = {parent for parents in graph.values() for parent in parents}
    for parent in sorted(referenced - revisions):
        issues.append(f"dangling down_revision: {parent}")
    heads = revisions - referenced
    if len(heads) != 1:
        issues.append(f"expected one migration head, found {len(heads)}")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(revision: str) -> None:
        if revision in visiting:
            issues.append(f"migration cycle at {revision}")
            return
        if revision in visited:
            return
        visiting.add(revision)
        for parent in graph.get(revision, ()):
            if parent in graph:
                visit(parent)
        visiting.remove(revision)
        visited.add(revision)

    for revision in sorted(revisions):
        visit(revision)
    return heads, tuple(dict.fromkeys(issues))


def _has_exact_env_ignore(lines: list[str]) -> bool:
    rules = {line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")}
    return bool({".env", "/.env"} & rules)


def _markdown_has_section(text: str, section: str) -> bool:
    return f"## {section}" in text or f"## {section.capitalize()}" in text


def _is_adr_file(path: Path) -> bool:
    return path.name[:4].isdigit() and path.name[4] == "-" and path.suffix == ".md"


def _adr_number(path: Path) -> int:
    return int(path.name[:4])


def _documentation_link_paths(root: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    for relative in DOC_LINK_ROOTS:
        path = root / relative
        if path.is_file():
            paths.append(path)
        elif path.is_dir():
            paths.extend(sorted(path.rglob("*.md")))
    return tuple(dict.fromkeys(paths))


def _local_markdown_links(text: str) -> tuple[str, ...]:
    links: list[str] = []
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
        if not target or target.startswith(("#", "mailto:")) or "://" in target:
            continue
        links.append(target.split("#", 1)[0])
    return tuple(links)


def validate(root: Path) -> Report:
    root = root.resolve()
    findings: list[Finding] = []
    checks = 0

    for relative in REQUIRED_PATHS:
        checks += 1
        if not (root / relative).is_dir():
            findings.append(Finding("repository-layout", relative, "required directory is absent"))

    standards = root / "docs" / "etra"
    docs_index = root / "docs" / "README.md"
    docs_index_text = docs_index.read_text(encoding="utf-8") if docs_index.is_file() else ""
    checks += 1
    if len(docs_index_text.strip()) < 300:
        findings.append(
            Finding(
                "documentation-index",
                "docs/README.md",
                "main documentation index is absent or too small",
            )
        )
    for link in DOCS_INDEX_LINKS:
        checks += 1
        if link not in docs_index_text:
            findings.append(
                Finding(
                    "documentation-index",
                    "docs/README.md",
                    f"missing required link: {link}",
                )
            )

    architecture_root = root / "docs" / "architecture"
    for name in ARCHITECTURE_FILES:
        checks += 1
        path = architecture_root / name
        if not path.is_file() or len(path.read_text(encoding="utf-8").strip()) < 300:
            findings.append(
                Finding(
                    "architecture-knowledge-base",
                    str(path.relative_to(root)),
                    "architecture document is absent or too small",
                )
            )

    reference_catalog = root / "docs" / "reference-architecture" / "catalog.json"
    checks += 1
    try:
        catalog = json.loads(reference_catalog.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        catalog = {}
        findings.append(
            Finding(
                "reference-catalog",
                "docs/reference-architecture/catalog.json",
                f"catalog is absent or invalid: {exc}",
            )
        )
    for key in REFERENCE_CATALOG_REQUIRED_KEYS:
        checks += 1
        if key not in catalog:
            findings.append(
                Finding(
                    "reference-catalog",
                    "docs/reference-architecture/catalog.json",
                    f"missing key: {key}",
                )
            )
    for section in catalog.get("sections", []) if isinstance(catalog, dict) else []:
        checks += 1
        section_path = section.get("path") if isinstance(section, dict) else None
        if not isinstance(section_path, str) or not section_path:
            findings.append(
                Finding(
                    "reference-catalog",
                    "docs/reference-architecture/catalog.json",
                    "section missing path",
                )
            )
            continue
        resolved = root / "docs" / "reference-architecture" / section_path
        if not resolved.is_file():
            findings.append(
                Finding(
                    "reference-catalog",
                    str(resolved.relative_to(root)),
                    "catalog path does not exist",
                )
            )
            continue
        text = resolved.read_text(encoding="utf-8")
        checks += 1
        if len(text.strip()) < 600:
            findings.append(
                Finding(
                    "reference-chapter",
                    str(resolved.relative_to(root)),
                    "reference chapter is too small for professional use",
                )
            )
        lowered = text.lower()
        for marker in DOC_STUB_MARKERS:
            checks += 1
            if marker.lower() in lowered:
                findings.append(
                    Finding(
                        "reference-chapter",
                        str(resolved.relative_to(root)),
                        f"placeholder marker remains: {marker}",
                    )
                )
        status = section.get("status") if isinstance(section, dict) else None
        if status in FULL_CONTRACT_STATUSES:
            for heading in CONTRACT_SECTIONS:
                checks += 1
                if f"## {heading}" not in text:
                    findings.append(
                        Finding(
                            "reference-chapter-contract",
                            str(resolved.relative_to(root)),
                            f"active chapter missing section: {heading}",
                        )
                    )

    for path in _documentation_link_paths(root):
        text = path.read_text(encoding="utf-8")
        for target in _local_markdown_links(text):
            checks += 1
            if not target:
                continue
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                findings.append(
                    Finding(
                        "documentation-link",
                        str(path.relative_to(root)),
                        f"link escapes repository: {target}",
                    )
                )
                continue
            if not resolved.exists():
                findings.append(
                    Finding(
                        "documentation-link",
                        str(path.relative_to(root)),
                        f"missing target: {target}",
                    )
                )

    for name in STANDARD_FILES:
        checks += 1
        path = standards / name
        if not path.is_file() or len(path.read_text(encoding="utf-8").strip()) < 80:
            findings.append(
                Finding(
                    "standard-document",
                    str(path.relative_to(root)),
                    "standard is absent or empty",
                )
            )

    adr_template = standards / "adr-template.md"
    if adr_template.is_file():
        text = adr_template.read_text(encoding="utf-8")
        for section in ADR_SECTIONS:
            checks += 1
            if f"## {section}" not in text:
                findings.append(
                    Finding(
                        "adr-template",
                        str(adr_template.relative_to(root)),
                        f"missing section: {section}",
                    )
                )

    adr_paths = sorted((root / "docs" / "adrs").glob("*.md"))
    numbered_adr_paths = [path for path in adr_paths if _is_adr_file(path)]
    numbers = [_adr_number(path) for path in numbered_adr_paths]
    checks += 1
    if numbers and numbers != list(range(min(numbers), max(numbers) + 1)):
        findings.append(
            Finding(
                "adr-sequence",
                "docs/adrs",
                "ADR numbers must be contiguous with no gaps",
            )
        )
    adr_index = root / "docs" / "adrs" / "README.md"
    adr_index_text = adr_index.read_text(encoding="utf-8") if adr_index.is_file() else ""
    for path in numbered_adr_paths:
        checks += 1
        if path.name not in adr_index_text:
            findings.append(
                Finding(
                    "adr-index",
                    "docs/adrs/README.md",
                    f"ADR is not listed: {path.name}",
                )
            )
    for path in numbered_adr_paths:
        if not _is_adr_file(path):
            continue
        text = path.read_text(encoding="utf-8")
        for metadata in ("- Status:", "- Date:", "- Owners:"):
            checks += 1
            if metadata not in text:
                findings.append(
                    Finding(
                        "adr-record",
                        str(path.relative_to(root)),
                        f"missing metadata: {metadata}",
                    )
                )
        for section in ADR_SECTIONS:
            checks += 1
            if not _markdown_has_section(text, section):
                findings.append(
                    Finding(
                        "adr-record",
                        str(path.relative_to(root)),
                        f"missing section: {section}",
                    )
                )

    checklist = standards / "engineering-review-checklist.md"
    checks += 1
    if checklist.is_file() and checklist.read_text(encoding="utf-8").count("- [ ]") < 10:
        findings.append(
            Finding(
                "review-checklist",
                str(checklist.relative_to(root)),
                "fewer than ten mandatory review gates",
            )
        )

    for runbook_name in ("service-operations.md", "agent-runtime-operations.md"):
        path = root / "docs" / "runbooks" / runbook_name
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        for section in (
            "Startup",
            "Shutdown",
            "Scaling",
            "Recovery",
            "Backup",
            "Restoration",
            "Incident response",
            "Upgrade",
            "Rollback",
        ):
            checks += 1
            if section.lower() not in text.lower():
                findings.append(
                    Finding(
                        "operational-runbook",
                        str(path.relative_to(root)),
                        f"missing operational topic: {section}",
                    )
                )

    domain_root = root / "apps" / "api" / "src" / "ai_enterprise" / "domain"
    for path in sorted(domain_root.rglob("*.py")):
        imports, parse_error = _python_imports(path)
        checks += 1
        if parse_error:
            findings.append(Finding("domain-parse", str(path.relative_to(root)), parse_error))
        violations = sorted(name for name in imports if _is_forbidden_domain_import(name))
        if violations:
            findings.append(
                Finding(
                    "inward-dependencies",
                    str(path.relative_to(root)),
                    f"domain imports forbidden dependencies: {', '.join(violations)}",
                )
            )

    main_path = root / "apps" / "api" / "src" / "ai_enterprise" / "main.py"
    main_text = main_path.read_text(encoding="utf-8") if main_path.is_file() else ""
    for endpoint in (
        '@app.get("/health")',
        '@app.get("/ready")',
        '@app.get("/metrics")',
    ):
        checks += 1
        if endpoint not in main_text:
            findings.append(
                Finding(
                    "service-surface",
                    str(main_path.relative_to(root)),
                    f"required endpoint missing: {endpoint}",
                )
            )
    checks += 1
    if 'prefix="/api/v1"' not in main_text:
        findings.append(
            Finding(
                "api-versioning",
                str(main_path.relative_to(root)),
                "no versioned public router prefix",
            )
        )

    revision_dir = root / "migrations" / "versions"
    checks += 1
    _, migration_issues = _migration_graph(revision_dir)
    for issue in migration_issues:
        findings.append(Finding("migration-linearity", "migrations/versions", issue))

    gitignore = root / ".gitignore"
    checks += 1
    ignored = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.is_file() else []
    if not _has_exact_env_ignore(ignored):
        findings.append(Finding("secret-hygiene", ".gitignore", ".env is not excluded"))

    workflow_path = root / ".github" / "workflows" / "etra-conformance.yml"
    workflow_text = workflow_path.read_text(encoding="utf-8") if workflow_path.is_file() else ""
    for required in (
        "contents: read",
        "actions/checkout@",
        "actions/setup-python@",
        "python tools/etra_conformance.py --root . --json",
    ):
        checks += 1
        if required not in workflow_text:
            findings.append(
                Finding(
                    "ci-enforcement",
                    str(workflow_path.relative_to(root)),
                    f"missing CI requirement: {required}",
                )
            )

    report = Report(ETRA_VERSION, not findings, checks, tuple(findings))
    _validate_report(report)
    return report


def _schema() -> dict:
    for candidate in Path(__file__).resolve().parents:
        schema_path = candidate / ETRA_REPORT_SCHEMA_REF
        if schema_path.is_file():
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)
            return schema
    raise RuntimeError(f"{ETRA_REPORT_SCHEMA_REF} schema file is missing")


def _report_document(report: Report) -> dict:
    return json.loads(json.dumps(asdict(report), sort_keys=True))


def _validate_report(report: Report) -> None:
    try:
        jsonschema.validate(_report_document(report), _schema())
    except jsonschema.ValidationError as exc:
        raise RuntimeError(
            f"{ETRA_REPORT_SCHEMA_REF}: generated ETRA conformance report "
            f"does not validate: {exc.message}"
        ) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    report = validate(args.root)
    if args.as_json:
        print(json.dumps(_report_document(report), sort_keys=True))
    else:
        status = "PASS" if report.conformant else "FAIL"
        print(f"ETRA {report.standard_version}: {status} ({report.checks} checks)")
        for finding in report.findings:
            print(f"- [{finding.check}] {finding.path}: {finding.message}")
    return 0 if report.conformant else 1


if __name__ == "__main__":
    sys.exit(main())
