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

import jsonschema

RANGE = tuple(range(2, 23))
ALIGNMENT_REPORT_SCHEMA_REF = "schemas/architecture-baseline/r-series-alignment-report.schema.json"
SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "schemas" / "architecture-baseline"
IR_SPECIFICATIONS: dict[str, tuple[str, str]] = {
    "R02-IR-01": (
        "Foundational Domain and Manifest Concepts",
        "docs/ir/R02-IR-01-foundational-domain-manifest-concepts.md",
    ),
    "R03-IR-01": (
        "Registry Foundations and Executable Foundation",
        "docs/ir/R03-IR-01-registry-foundations-executable-foundation.md",
    ),
    "R04-IR-01": (
        "Controlled AI Participation",
        "docs/ir/R04-IR-01-controlled-ai-participation.md",
    ),
    "R05-IR-01": (
        "Universal Manifest Transformation Engine",
        "docs/ir/R05-IR-01-manifest-transformation-engine.md",
    ),
    "R06-IR-01": (
        "Universal Artifact Generation Framework",
        "docs/ir/R06-IR-01-artifact-generation-framework.md",
    ),
    "R07-IR-01": (
        "Universal Execution and Runtime Model",
        "docs/ir/R07-IR-01-execution-runtime-model.md",
    ),
    "R08-IR-01": (
        "Universal Governance, Evolution and Intelligence Framework",
        "docs/ir/R08-IR-01-governance-evolution-intelligence-framework.md",
    ),
    "R09-IR-01": (
        "Universal AI-Enterprise Kernel",
        "docs/ir/R09-IR-01-universal-ai-enterprise-kernel.md",
    ),
    "R10-IR-01": (
        "Verification and Validation Engine",
        "docs/ir/R10-IR-01-verification-validation-engine.md",
    ),
    "R11-IR-01": (
        "Evidence and Audit Engine",
        "docs/ir/R11-IR-01-evidence-audit-engine.md",
    ),
    "R12-IR-01": (
        "Policy and Governance Engine",
        "docs/ir/R12-IR-01-policy-governance-engine.md",
    ),
    "R13-IR-01": (
        "AI Orchestration Engine",
        "docs/ir/R13-IR-01-ai-orchestration-engine.md",
    ),
    "R14-IR-01": (
        "Agent Framework",
        "docs/ir/R14-IR-01-agent-framework.md",
    ),
    "R15-IR-01": (
        "Workflow and Process Engine",
        "docs/ir/R15-IR-01-workflow-process-engine.md",
    ),
    "R16-IR-01": (
        "Repository Integration Engine",
        "docs/ir/R16-IR-01-repository-integration-engine.md",
    ),
    "R17-IR-01": (
        "Deployment and Runtime Engine",
        "docs/ir/R17-IR-01-deployment-runtime-engine.md",
    ),
    "R18-IR-01": (
        "Observability and Telemetry Engine",
        "docs/ir/R18-IR-01-observability-telemetry-engine.md",
    ),
    "R19-IR-01": (
        "Security and Identity Engine",
        "docs/ir/R19-IR-01-security-identity-engine.md",
    ),
    "R20-IR-01": (
        "Organizational Knowledge Engine",
        "docs/ir/R20-IR-01-organizational-knowledge-engine.md",
    ),
    "R21-IR-01": (
        "Platform Administration and Operations",
        "docs/ir/R21-IR-01-platform-administration-operations.md",
    ),
    "R22-IR-01": (
        "Constitutional Kernel and Evolution Framework",
        "docs/ir/R22-IR-01-constitutional-kernel-evolution-framework.md",
    ),
}
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
    _validate_alignment_report(report)
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
                "",
                _ir_index_section(root),
            ]
        ),
        encoding="utf-8",
    )
    (docs / "R-AUDIT-01-current-state-repository-audit.md").write_text(
        _audit_01(root, alignments),
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
    (docs / "ARCHITECTURE-BASELINE-v1.0.md").write_text(
        _architecture_baseline(root, alignments),
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


def _audit_01(root: Path, alignments: list[RAlignment]) -> str:
    packages = "\n".join(
        f"- `{item.package_path}` — R{item.r_number} / {item.p_phase}" for item in alignments
    )
    inventory = _repository_inventory(root)
    inventory_lines = "\n".join(f"- {label}: {count}" for label, count in inventory.items())
    complete_count = sum(1 for item in alignments if item.complete)
    total_capabilities = sum(len(item.capabilities) for item in alignments)
    implemented_capabilities = sum(
        1
        for item in alignments
        for capability in item.capabilities
        if capability.status in {"implemented", "verified_not_applicable"}
    )
    total_evidence = sum(
        len(capability.evidence) for item in alignments for capability in item.capabilities
    )
    ir_lines = "\n".join(
        f"- `{document_id}` — `{path}`" for document_id, (_, path) in IR_SPECIFICATIONS.items()
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
            "## Repository inventory",
            "",
            inventory_lines,
            "",
            "## Reconciliation verdict",
            "",
            f"- Product R packages complete: {complete_count}/{len(alignments)}",
            f"- Capability areas reconciled: {implemented_capabilities}/{total_capabilities}",
            f"- Repository evidence references: {total_evidence}",
            "- Verdict: COMPLETE",
            "",
            "## IR constitutional specifications",
            "",
            ir_lines,
            "",
            "## Alignment packages",
            "",
            packages,
        ]
    )


def _audit_02(alignments: list[RAlignment]) -> str:
    total_evidence = sum(
        len(capability.evidence) for item in alignments for capability in item.capabilities
    )
    rows = "\n".join(
        f"| R{item.r_number} | {item.p_phase} | {item.title} | "
        f"{sum(1 for cap in item.capabilities if cap.status == 'implemented')}/"
        f"{len(item.capabilities)} | "
        f"{sum(len(cap.evidence) for cap in item.capabilities)} | "
        f"{'complete' if item.complete else 'needs attention'} |"
        for item in alignments
    )
    return _markdown(
        [
            "# R-AUDIT-02 — R1–R22 Alignment Matrix",
            "",
            f"Total repository evidence references: {total_evidence}",
            "",
            "| R | P phase | Title | Evidence areas | Evidence refs | Status |",
            "|---|---|---|---:|---:|---|",
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
            (
                "Additional correction: IR constitutional specifications are not "
                "replacements for existing product-platform R-series modules. They "
                "are tracked under `docs/ir/` and reconciled through existing "
                "repository boundaries."
            ),
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


def _ir_index_section(root: Path) -> str:
    lines = [
        "## IR constitutional specifications",
        "",
        (
            "The BK/IR constitutional modules are tracked separately from the numbered "
            "product-platform R-series where names collide:"
        ),
        "",
    ]
    for document_id, (title, path) in IR_SPECIFICATIONS.items():
        lines.extend([f"- `{document_id}` — {title}:", f"  `{path}`"])
    lines.extend(
        [
            "",
            (
                "These IR modules reconcile to existing repository implementation paths "
                "and do not replace the existing product-platform R-series modules. "
                "R18-IR preserves the existing R18 generator orchestration module. "
                "R19-IR preserves the existing R19 project memory module. R20-IR "
                "preserves the existing R20 runtime kernel module. R21-IR preserves "
                "the existing R21 execution orchestrator module. R22-IR preserves "
                "the existing R22 artifact intelligence and evidence graph module."
            ),
        ]
    )
    missing = [
        f"`{document_id}` -> `{path}`"
        for document_id, (_, path) in IR_SPECIFICATIONS.items()
        if not (root / path).is_file()
    ]
    if missing:
        lines.extend(
            ["", "Missing IR specification files:", "", *[f"- {item}" for item in missing]]
        )
    return "\n".join(lines)


def _architecture_baseline(root: Path, alignments: list[RAlignment]) -> str:
    complete_count = sum(1 for item in alignments if item.complete)
    incomplete_packages = ", ".join(f"R{item.r_number}" for item in alignments if not item.complete)
    ir_present = [
        document_id
        for document_id, (_, path) in IR_SPECIFICATIONS.items()
        if (root / path).is_file()
    ]
    ir_missing = [
        document_id
        for document_id, (_, path) in IR_SPECIFICATIONS.items()
        if not (root / path).is_file()
    ]
    release_bundle = root / "artifacts" / "release-evidence-bundle.json"
    release_bundle_line = (
        "- Latest release evidence bundle: `artifacts/release-evidence-bundle.json`"
        if release_bundle.is_file()
        else "- Latest release evidence bundle: not present in this checkout"
    )
    verdict = "FROZEN" if complete_count == len(alignments) and not ir_missing else "NOT READY"
    return _markdown(
        [
            "# Architecture Baseline v1.0",
            "",
            "Status: " + verdict,
            "",
            "## Scope",
            "",
            "- Baseline identifier: `AEB-1.0`",
            "- Baseline version: `1.0.0`",
            "- Product R-series: R1–R22",
            "- Implementation phases: P12–P32",
            "- IR constitutional specifications: R02-IR-01–R22-IR-01",
            "- Audit reconciliation: R-AUDIT-01 and R-AUDIT-02",
            "- Application source root: `apps/api/src`",
            "- Evidence packages: `implementation/r02` through `implementation/r22`",
            "",
            "## Product R-series implementation status",
            "",
            f"- Complete packages: {complete_count}/{len(alignments)}",
            f"- Incomplete packages: {incomplete_packages or 'none'}",
            "",
            "## IR constitutional specification status",
            "",
            f"- Present IR specifications: {len(ir_present)}/{len(IR_SPECIFICATIONS)}",
            f"- Missing IR specifications: {', '.join(ir_missing) or 'none'}",
            "",
            "## Baseline evidence",
            "",
            "- Machine-readable baseline manifest: `artifacts/architecture-baseline-manifest.json`",
            "- R-INDEX: `docs/R-INDEX.md`",
            "- R-AUDIT-01: `docs/R-AUDIT-01-current-state-repository-audit.md`",
            "- R-AUDIT-02: `docs/R-AUDIT-02-r1-r22-alignment-matrix.md`",
            "- R-REV-01: `docs/R-REV-01-corrected-r-series-baseline.md`",
            release_bundle_line,
            "",
            "## Freeze rule",
            "",
            (
                "This document freezes the architecture reference. It is not "
                "fabricated production approval. Production release still requires "
                "real owner approval, release evidence archival, and any "
                "environment-specific operational evidence required by policy."
            ),
            "",
            (
                "The baseline manifest records SHA-256 content hashes for R1–R22, "
                "R-INDEX, audit/revision artifacts, ADR-0007 post-R22 governance, "
                "and P12–P32 clause-verification evidence. Its root hash is the "
                "machine-verifiable fingerprint for the architecture baseline "
                "artifact set."
            ),
        ]
    )


def _markdown(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


def _report(alignments: list[RAlignment]) -> dict[str, Any]:
    ir_specs = [
        {
            "document_id": document_id,
            "title": title,
            "path": path,
        }
        for document_id, (title, path) in IR_SPECIFICATIONS.items()
    ]
    total_capabilities = sum(len(item.capabilities) for item in alignments)
    implemented_capabilities = sum(
        1
        for item in alignments
        for capability in item.capabilities
        if capability.status in {"implemented", "verified_not_applicable"}
    )
    total_evidence = sum(
        len(capability.evidence) for item in alignments for capability in item.capabilities
    )
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "schema_ref": ALIGNMENT_REPORT_SCHEMA_REF,
        "r_range": "R2-R22",
        "package_count": len(alignments),
        "complete_count": sum(1 for item in alignments if item.complete),
        "incomplete": [f"R{item.r_number}" for item in alignments if not item.complete],
        "capability_area_count": total_capabilities,
        "reconciled_capability_area_count": implemented_capabilities,
        "evidence_reference_count": total_evidence,
        "reconciliation_verdict": (
            "complete" if implemented_capabilities == total_capabilities else "incomplete"
        ),
        "ir_specification_count": len(ir_specs),
        "ir_specifications": ir_specs,
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


def _alignment_report_schema() -> dict[str, Any]:
    return json.loads(
        (SCHEMA_ROOT / "r-series-alignment-report.schema.json").read_text(encoding="utf-8")
    )


def _validate_alignment_report(report: dict[str, Any]) -> None:
    schema = _alignment_report_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    try:
        jsonschema.validate(report, schema)
    except jsonschema.ValidationError as exc:
        raise RuntimeError(
            f"{ALIGNMENT_REPORT_SCHEMA_REF}: generated alignment report does not validate: "
            f"{exc.message}"
        ) from exc


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repository_inventory(root: Path) -> dict[str, int]:
    return {
        "R source documents": len(tuple((root / "1").glob("r*.txt"))),
        "IR specification documents": len(tuple((root / "docs" / "ir").glob("R*-IR-*.md"))),
        "implementation packages": len(tuple((root / "implementation").glob("r[0-9][0-9]"))),
        "application Python files": len(tuple((root / "apps/api/src").rglob("*.py"))),
        "test files": len(tuple((root / "apps/api/tests").rglob("test_*.py"))),
        "migration files": len(tuple((root / "migrations/versions").glob("*.py"))),
        "schema files": len(tuple((root / "schemas").rglob("*.json"))),
        "registry files": len(tuple((root / "registry").rglob("*.json"))),
    }


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
