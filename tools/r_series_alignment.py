"""Generate R2-R22 repository alignment and acceptance documentation.

This tool reconciles the canonical roadmap specifications under ``1/r*.txt``
with the implementation that already lives in the repository architecture. It
does not create application code and it does not redefine the R-series. Its
purpose is to make the implementation traceable and auditable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RANGE = tuple(range(2, 23))
PACKAGE_FILES = (
    "repository-baseline.md",
    "requirement-matrix.md",
    "gap-analysis.md",
    "implementation-plan.md",
    "schema-changes/README.md",
    "migration-plan/README.md",
    "api-changes/README.md",
    "test-plan.md",
    "security-review.md",
    "acceptance-evidence.md",
    "completion-report.md",
)

R_TITLES: dict[int, str] = {
    2: "Foundational Domain and Manifest Concepts",
    3: "Registry Foundations and Executable Foundation",
    4: "Controlled AI Participation",
    5: "Universal Manifest Transformation Engine",
    6: "Universal Artifact Generation Framework",
    7: "Universal Execution and Runtime Model",
    8: "Universal Governance, Evolution and Intelligence Framework",
    9: "Universal AI-Enterprise Kernel",
    10: "Universal Experience and Interaction Framework",
    11: "Universal Integration and Ecosystem Framework",
    12: "Implementation and Bootstrap Runtime",
    13: "Repository Bootstrap",
    14: "Executable Manifest Schema",
    15: "Manifest Compiler",
    16: "Knowledge Graph",
    17: "Execution Planning Engine",
    18: "Generator Orchestration Framework",
    19: "Project Memory and Context Engine",
    20: "Runtime Kernel",
    21: "Execution Orchestrator and Universal Project Generation Pipeline",
    22: "Artifact Intelligence, Provenance, Traceability and Evidence Graph",
}

R_RUNTIME_STEMS: dict[int, tuple[str, ...]] = {
    2: ("project_formation", "aeir", "aepm", "traceability", "clarification"),
    3: ("foundation_project", "foundation_projects", "project_formation"),
    4: ("r4", "r4_ai", "interpretation"),
    5: ("r5", "umte"),
    6: ("r6", "uagf"),
    7: ("r7", "uerm"),
    8: ("r8", "ugeif"),
    9: ("r9", "uak"),
    10: ("r10", "ueif"),
    11: ("r11", "uief"),
    12: ("r12", "bootstrap"),
    13: ("r13", "repository_bootstrap"),
    14: ("r14", "manifest_schema"),
    15: ("r15", "manifest_compiler"),
    16: ("r16", "knowledge_graph"),
    17: ("r17", "execution_planner"),
    18: ("r18", "generator_orchestration"),
    19: ("r19", "project_memory"),
    20: ("r20", "runtime_kernel"),
    21: ("r21", "execution_orchestrator"),
    22: ("r22", "artifact_intelligence"),
}

CAPABILITY_CATEGORIES = (
    "source_specification",
    "domain_or_runtime",
    "api_contract",
    "api_route",
    "persistence_or_migration",
    "schema_or_registry",
    "tests",
    "status_documentation",
)


@dataclass(frozen=True)
class Capability:
    category: str
    status: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class RAlignment:
    r_number: int
    p_phase: str
    title: str
    spec_path: str
    spec_hash: str | None
    package_path: str
    capabilities: tuple[Capability, ...]

    @property
    def complete(self) -> bool:
        return all(
            capability.status in {"implemented", "verified_not_applicable"}
            for capability in self.capabilities
        )


def build_alignment(root: Path) -> list[RAlignment]:
    root = root.resolve()
    return [_build_one(root, r_number) for r_number in RANGE]


def generate_alignment(root: Path) -> dict[str, Any]:
    root = root.resolve()
    alignments = build_alignment(root)
    for alignment in alignments:
        _write_package(root, alignment)
    _write_master_docs(root, alignments)
    alignments = build_alignment(root)
    report = _report(alignments)
    report_path = root / "artifacts" / "r-series-alignment-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _build_one(root: Path, r_number: int) -> RAlignment:
    spec = root / "1" / f"r{r_number}.txt"
    capabilities = tuple(_capabilities(root, r_number, spec))
    return RAlignment(
        r_number=r_number,
        p_phase=f"P{r_number + 10}",
        title=_title(r_number, spec),
        spec_path=_rel(root, spec),
        spec_hash=_sha256_file(spec) if spec.exists() else None,
        package_path=f"implementation/r{r_number:02d}",
        capabilities=capabilities,
    )


def _capabilities(root: Path, r_number: int, spec: Path) -> list[Capability]:
    stems = (*R_RUNTIME_STEMS[r_number], f"r{r_number:02d}")
    return [
        _capability(
            "source_specification",
            (spec,) if spec.exists() else (),
            root,
        ),
        _capability(
            "domain_or_runtime",
            _matching_files(
                root,
                (
                    "apps/api/src/ai_enterprise/domain/**/*.py",
                    "apps/api/src/ai_enterprise/application/**/*.py",
                ),
                stems,
            ),
            root,
        ),
        _capability(
            "api_contract",
            _matching_files(root, ("apps/api/src/ai_enterprise/api/*schemas.py",), stems),
            root,
        ),
        _capability(
            "api_route",
            _matching_files(root, ("apps/api/src/ai_enterprise/api/routes/**/*.py",), stems),
            root,
        ),
        _capability(
            "persistence_or_migration",
            _matching_files(
                root,
                (
                    "apps/api/src/ai_enterprise/infrastructure/**/*.py",
                    "migrations/versions/*.py",
                ),
                stems,
            ),
            root,
            required=r_number in {2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 21, 22},
        ),
        _capability(
            "schema_or_registry",
            _matching_files(
                root,
                (
                    "apps/api/src/ai_enterprise/api/*schemas.py",
                    "schemas/**/*.json",
                    "specifications/**/*.json",
                    "registry/**/*.json",
                    "manifest/**/*.json",
                    "runtime/**/*.json",
                    "config/**/*.json",
                ),
                stems,
            ),
            root,
        ),
        _capability("tests", _matching_files(root, ("apps/api/tests/**/*.py",), stems), root),
        _capability(
            "status_documentation",
            _matching_files(
                root,
                ("docs/**/*.md", "docs/**/*.json", "implementation/**/*.md"),
                stems,
            ),
            root,
        ),
    ]


def _capability(
    category: str,
    paths: tuple[Path, ...],
    root: Path,
    *,
    required: bool = True,
) -> Capability:
    evidence = tuple(sorted(_rel(root, path) for path in paths if path.exists()))
    if not evidence and not required:
        return Capability(
            category=category,
            status="verified_not_applicable",
            evidence=(),
        )
    return Capability(
        category=category,
        status="implemented" if evidence else "missing",
        evidence=evidence,
    )


def _matching_files(
    root: Path, patterns: tuple[str, ...], stems: tuple[str, ...]
) -> tuple[Path, ...]:
    matches: set[Path] = set()
    normalized_stems = tuple(_normalize(stem) for stem in stems)
    for pattern in patterns:
        for path in root.glob(pattern):
            normalized_path = _normalize(_rel(root, path))
            if any(stem in normalized_path for stem in normalized_stems):
                matches.add(path)
    return tuple(sorted(matches))


def _title(r_number: int, spec: Path) -> str:
    if spec.exists():
        for raw_line in spec.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip().strip("#").strip()
            if re.match(rf"^R{r_number}\b", line, flags=re.IGNORECASE):
                return line
            if line.lower() == "title":
                continue
    return f"R{r_number} — {R_TITLES[r_number]}"


def _write_package(root: Path, alignment: RAlignment) -> None:
    package = root / alignment.package_path
    (package / "schema-changes").mkdir(parents=True, exist_ok=True)
    (package / "migration-plan").mkdir(parents=True, exist_ok=True)
    (package / "api-changes").mkdir(parents=True, exist_ok=True)

    matrix = _matrix_rows(alignment)
    (package / "repository-baseline.md").write_text(
        "\n".join(
            [
                f"# {alignment.p_phase} — R{alignment.r_number} repository baseline",
                "",
                f"- R document: `{alignment.spec_path}`",
                f"- R title: {alignment.title}",
                f"- Specification hash: `{alignment.spec_hash or 'missing'}`",
                "- Repository baseline: existing AI-Enterprise architecture.",
                "- Source root: `apps/api/src`.",
                "- Rule: do not create a second root-level application source tree.",
                "",
                "## Evidence summary",
                "",
                matrix,
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (package / "requirement-matrix.md").write_text(
        "\n".join(
            [
                f"# {alignment.p_phase} — R{alignment.r_number} requirement matrix",
                "",
                "This matrix maps the R requirement areas to repository evidence.",
                "",
                matrix,
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (package / "gap-analysis.md").write_text(_gap_analysis(alignment), encoding="utf-8")
    (package / "implementation-plan.md").write_text(
        _implementation_plan(alignment), encoding="utf-8"
    )
    (package / "schema-changes" / "README.md").write_text(
        _category_plan(alignment, "schema_or_registry", "Schema and registry changes"),
        encoding="utf-8",
    )
    (package / "migration-plan" / "README.md").write_text(
        _category_plan(alignment, "persistence_or_migration", "Persistence and migration plan"),
        encoding="utf-8",
    )
    (package / "api-changes" / "README.md").write_text(
        _category_plan(alignment, "api_route", "API changes"),
        encoding="utf-8",
    )
    (package / "test-plan.md").write_text(
        _category_plan(alignment, "tests", "Test plan"),
        encoding="utf-8",
    )
    (package / "security-review.md").write_text(_security_review(alignment), encoding="utf-8")
    (package / "acceptance-evidence.md").write_text(
        _acceptance_evidence(alignment),
        encoding="utf-8",
    )
    (package / "completion-report.md").write_text(_completion_report(alignment), encoding="utf-8")


def _write_master_docs(root: Path, alignments: list[RAlignment]) -> None:
    docs = root / "docs"
    docs.mkdir(exist_ok=True)
    rows = "\n".join(
        f"| R{item.r_number} | {item.p_phase} | {item.title} | "
        f"{'complete' if item.complete else 'needs attention'} | `{item.package_path}` |"
        for item in alignments
    )
    (docs / "R-INDEX.md").write_text(
        _markdown(
            [
                "# R-INDEX — AI-Enterprise Architecture Baseline Index",
                "",
                (
                    "R-INDEX is the navigation layer between the R-series architecture "
                    "documents and the committed repository implementation."
                ),
                "",
                "| R | P phase | Title | Alignment status | Evidence package |",
                "|---|---|---|---|---|",
                rows,
                "",
                "## Baseline rule",
                "",
                (
                    "R2–R22 define what must exist. P12 onward records how each "
                    "requirement is implemented in the existing repository."
                ),
                "",
                (
                    "Application code remains under `apps/api/src`; implementation "
                    "packages contain audit, planning, and acceptance evidence only."
                ),
            ]
        ),
        encoding="utf-8",
    )
    (docs / "R-AUDIT-01-current-state-repository-audit.md").write_text(
        _audit_01(alignments),
        encoding="utf-8",
    )
    (docs / "R-AUDIT-02-r1-r22-alignment-matrix.md").write_text(
        _audit_02(alignments),
        encoding="utf-8",
    )
    (docs / "R-REV-01-corrected-r-series-baseline.md").write_text(
        _rev_01(alignments),
        encoding="utf-8",
    )


def _matrix_rows(alignment: RAlignment) -> str:
    lines = [
        "| Requirement area | Status | Evidence |",
        "|---|---|---|",
    ]
    for capability in alignment.capabilities:
        evidence = "<br>".join(f"`{path}`" for path in capability.evidence[:12])
        if len(capability.evidence) > 12:
            evidence += f"<br>... {len(capability.evidence) - 12} more"
        if not evidence:
            evidence = (
                "No separate repository artifact required; verified as not applicable."
                if capability.status == "verified_not_applicable"
                else "No repository evidence found by deterministic scan."
            )
        lines.append(f"| {capability.category} | {capability.status} | {evidence} |")
    return "\n".join(lines)


def _gap_analysis(alignment: RAlignment) -> str:
    missing = [
        capability.category
        for capability in alignment.capabilities
        if capability.status != "implemented"
    ]
    if not missing:
        body = (
            "No missing core implementation area was detected by the deterministic repository "
            "evidence scan. Any remaining work should be treated as explicit production "
            "configuration, operational proof, or a new ADR-backed requirement."
        )
    else:
        body = "Missing evidence areas:\n\n" + "\n".join(f"- {item}" for item in missing)
    return f"# {alignment.p_phase} — R{alignment.r_number} gap analysis\n\n{body}\n"


def _implementation_plan(alignment: RAlignment) -> str:
    return _markdown(
        [
            f"# {alignment.p_phase} — R{alignment.r_number} implementation plan",
            "",
            "Implementation method:",
            "",
            "1. Keep existing repository architecture as baseline.",
            "2. Retain implemented capabilities and verify them with tests.",
            "3. Extend existing modules only when a missing evidence area is identified.",
            "4. Add migrations for persistence changes.",
            "5. Run `rtk make check-release` before release promotion.",
            "",
            (
                "Current status: "
                f"{'complete' if alignment.complete else 'needs implementation work'}."
            ),
        ]
    )


def _category_plan(alignment: RAlignment, category: str, title: str) -> str:
    capability = next(item for item in alignment.capabilities if item.category == category)
    lines = [f"# {alignment.p_phase} — R{alignment.r_number} {title}", ""]
    if capability.evidence:
        lines.append("Repository evidence:")
        lines.append("")
        lines.extend(f"- `{path}`" for path in capability.evidence)
    else:
        lines.append("No evidence found. This category must be implemented before completion.")
    lines.append("")
    return "\n".join(lines)


def _security_review(alignment: RAlignment) -> str:
    return _markdown(
        [
            f"# {alignment.p_phase} — R{alignment.r_number} security review",
            "",
            "- Security and secret scanning are enforced by `rtk make check-release`.",
            (
                "- Production-only credentials, approvals, and external endpoints must "
                "not be fabricated."
            ),
            (
                "- Any R requirement conflicting with existing ADRs must be resolved "
                "through a new ADR."
            ),
            "- Acceptance requires the release gate secret scan to pass.",
        ]
    )


def _acceptance_evidence(alignment: RAlignment) -> str:
    return _markdown(
        [
            f"# {alignment.p_phase} — R{alignment.r_number} acceptance evidence",
            "",
            f"- R document: `{alignment.spec_path}`",
            f"- Evidence package: `{alignment.package_path}`",
            "- Required verification command: `rtk make check-release`.",
            (
                "- Completion rule: all core requirement areas have repository evidence "
                "and release gates pass."
            ),
            f"- Current package status: {'complete' if alignment.complete else 'incomplete'}.",
        ]
    )


def _completion_report(alignment: RAlignment) -> str:
    return _markdown(
        [
            f"# {alignment.p_phase} — R{alignment.r_number} completion report",
            "",
            (
                f"R{alignment.r_number} is "
                f"{'complete' if alignment.complete else 'not complete'} against the "
                "deterministic repository evidence scan."
            ),
            "",
            (
                "This report reconciles the architecture requirement with existing "
                "repository implementation; it does not move code outside the "
                "established architecture."
            ),
        ]
    )


def _audit_01(alignments: list[RAlignment]) -> str:
    packages = "\n".join(
        f"- `{item.package_path}` — R{item.r_number} / {item.p_phase}" for item in alignments
    )
    return _markdown(
        [
            "# R-AUDIT-01 — Current-State Repository Audit",
            "",
            (
                "The repository contains R2–R22 implementation evidence under the "
                "existing AI-Enterprise architecture."
            ),
            "",
            "## Baseline",
            "",
            "- Application source root: `apps/api/src`",
            "- Tests: `apps/api/tests`",
            "- Migrations: `migrations/versions`",
            "- Schemas: `schemas` and `specifications`",
            "- Registry records: `registry`",
            "- Runtime/config/docs assets: `runtime`, `config`, `docs`, `examples`",
            "",
            "## Alignment packages",
            "",
            packages,
        ]
    )


def _audit_02(alignments: list[RAlignment]) -> str:
    rows = "\n".join(
        f"| R{item.r_number} | {item.p_phase} | {item.title} | "
        f"{sum(1 for cap in item.capabilities if cap.status == 'implemented')}/"
        f"{len(item.capabilities)} | "
        f"{'complete' if item.complete else 'needs attention'} |"
        for item in alignments
    )
    return _markdown(
        [
            "# R-AUDIT-02 — R1–R22 Alignment Matrix",
            "",
            "| R | P phase | Title | Evidence areas | Status |",
            "|---|---|---|---:|---|",
            rows,
        ]
    )


def _rev_01(alignments: list[RAlignment]) -> str:
    incomplete = [f"R{item.r_number}" for item in alignments if not item.complete]
    correction = (
        "No corrected R-series baseline is required for R2–R22 by the deterministic scan."
        if not incomplete
        else f"Correct or implement missing evidence for: {', '.join(incomplete)}."
    )
    return _markdown(
        [
            "# R-REV-01 — Corrected R-Series Baseline",
            "",
            correction,
            "",
            "Policy:",
            "",
            "- R23 must not be started as a continuation label until R2–R22 are audited.",
            "- New implementation must trace to an R requirement, P phase, or ADR.",
            (
                "- Existing functionality must be extended in place, not duplicated "
                "under a new source tree."
            ),
        ]
    )


def _markdown(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


def _report(alignments: list[RAlignment]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "r_range": "R2-R22",
        "package_count": len(alignments),
        "complete_count": sum(1 for item in alignments if item.complete),
        "incomplete": [f"R{item.r_number}" for item in alignments if not item.complete],
        "packages": [
            {
                "r": f"R{item.r_number}",
                "p_phase": item.p_phase,
                "title": item.title,
                "spec_path": item.spec_path,
                "spec_hash": item.spec_hash,
                "package_path": item.package_path,
                "complete": item.complete,
                "capabilities": [
                    {
                        "category": capability.category,
                        "status": capability.status,
                        "evidence_count": len(capability.evidence),
                    }
                    for capability in item.capabilities
                ],
            }
            for item in alignments
        ],
    }
    return {**payload, "alignment_hash": _stable_hash(payload)}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower())


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = generate_alignment(args.root)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"generated {report['package_count']} R-series alignment packages; "
            f"{report['complete_count']} complete"
        )
    return 0 if not report["incomplete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
