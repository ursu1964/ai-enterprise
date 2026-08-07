#!/usr/bin/env python3
"""Verify the R2-R22 architecture-to-implementation sequence gate.

This gate is intentionally read-only. It proves the repository has the
architecture baseline, audit/revision documents, implementation packages, and
R-to-P phase ordering required before any new roadmap module such as R23 is
introduced.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema
import r_series_alignment

SCHEMA_REF = "schemas/architecture-baseline/roadmap-sequence-gate.schema.json"
REQUIRED_BASELINE_DOCS = (
    "docs/R-INDEX.md",
    "docs/ARCHITECTURE-BASELINE-v1.0.md",
    "docs/R-AUDIT-01-current-state-repository-audit.md",
    "docs/R-AUDIT-02-r1-r22-alignment-matrix.md",
    "docs/R-REV-01-corrected-r-series-baseline.md",
)
REQUIRED_PACKAGE_FILES = r_series_alignment.PACKAGE_FILES
R_RANGE = tuple(range(2, 23))


@dataclass(frozen=True)
class Finding:
    check: str
    severity: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "check": self.check,
            "severity": self.severity,
            "message": self.message,
        }


def verify_roadmap_sequence(root: Path) -> dict[str, Any]:
    root = root.resolve()
    alignments = r_series_alignment.build_alignment(root)
    alignment_report = r_series_alignment._report(alignments)
    r_series_alignment._validate_alignment_report(alignment_report)

    findings: list[Finding] = []
    checks = [
        _check_baseline_docs(root, findings),
        _check_source_specs(root, findings),
        _check_ir_specs(root, findings),
        _check_implementation_packages(root, findings),
        _check_phase_sequence(alignments, findings),
        _check_alignment_report(alignment_report, findings),
        _check_no_premature_r23(root, findings),
    ]
    status = "failed" if findings else "passed"
    report = {
        "schema_version": "1.0",
        "schema_ref": SCHEMA_REF,
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(),
        "r_range": "R2-R22",
        "implementation_phase_range": "P12-P32",
        "alignment_report_hash": alignment_report["alignment_hash"],
        "checks": checks,
        "findings": [finding.as_dict() for finding in findings],
        "next_action": (
            "Proceed only with ADR-backed post-R22 roadmap work."
            if status == "passed"
            else "Resolve failed roadmap sequence findings before starting new roadmap work."
        ),
    }
    _validate_report(root, report)
    return report


def _check_baseline_docs(root: Path, findings: list[Finding]) -> dict[str, str]:
    missing = [path for path in REQUIRED_BASELINE_DOCS if not (root / path).is_file()]
    for path in missing:
        findings.append(
            Finding(
                check="baseline-documents",
                severity="critical",
                message=f"Required architecture baseline document is missing: {path}",
            )
        )
    present = len(REQUIRED_BASELINE_DOCS) - len(missing)
    return _check(
        "baseline-documents",
        not missing,
        f"{present}/{len(REQUIRED_BASELINE_DOCS)} required baseline documents present",
    )


def _check_source_specs(root: Path, findings: list[Finding]) -> dict[str, str]:
    missing = [
        f"1/r{number}.txt" for number in R_RANGE if not (root / "1" / f"r{number}.txt").is_file()
    ]
    for path in missing:
        findings.append(
            Finding(
                check="source-specifications",
                severity="critical",
                message=f"Required R-series source specification is missing: {path}",
            )
        )
    return _check(
        "source-specifications",
        not missing,
        f"{len(R_RANGE) - len(missing)}/{len(R_RANGE)} R2-R22 source specifications present",
    )


def _check_ir_specs(root: Path, findings: list[Finding]) -> dict[str, str]:
    missing: list[str] = []
    not_ready: list[str] = []
    for document_id, (_title, relative_path) in r_series_alignment.IR_SPECIFICATIONS.items():
        path = root / relative_path
        if not path.is_file():
            missing.append(relative_path)
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        if "Status: IMPLEMENTATION READY" not in content:
            not_ready.append(f"{document_id} ({relative_path})")
    for path in missing:
        findings.append(
            Finding(
                check="ir-specifications",
                severity="critical",
                message=f"Required IR implementation-ready specification is missing: {path}",
            )
        )
    for item in not_ready:
        findings.append(
            Finding(
                check="ir-specifications",
                severity="high",
                message=f"IR specification is not marked IMPLEMENTATION READY: {item}",
            )
        )
    passed = not missing and not not_ready
    ready_count = len(r_series_alignment.IR_SPECIFICATIONS) - len(missing) - len(not_ready)
    return _check(
        "ir-specifications",
        passed,
        (
            f"{ready_count}/{len(r_series_alignment.IR_SPECIFICATIONS)} "
            "IR specifications implementation-ready"
        ),
    )


def _check_implementation_packages(root: Path, findings: list[Finding]) -> dict[str, str]:
    missing: list[str] = []
    for number in R_RANGE:
        package = root / "implementation" / f"r{number:02d}"
        for relative_path in REQUIRED_PACKAGE_FILES:
            path = package / relative_path
            if not path.is_file():
                missing.append(str(path.relative_to(root)))
    for path in missing:
        findings.append(
            Finding(
                check="implementation-packages",
                severity="critical",
                message=f"Required P-phase implementation package file is missing: {path}",
            )
        )
    expected = len(R_RANGE) * len(REQUIRED_PACKAGE_FILES)
    return _check(
        "implementation-packages",
        not missing,
        f"{expected - len(missing)}/{expected} required implementation package files present",
    )


def _check_phase_sequence(
    alignments: list[r_series_alignment.RAlignment],
    findings: list[Finding],
) -> dict[str, str]:
    out_of_order = [
        f"R{alignment.r_number} mapped to {alignment.p_phase}, expected P{alignment.r_number + 10}"
        for alignment in alignments
        if alignment.p_phase != f"P{alignment.r_number + 10}"
    ]
    for message in out_of_order:
        findings.append(
            Finding(
                check="phase-sequence",
                severity="critical",
                message=message,
            )
        )
    return _check("phase-sequence", not out_of_order, "R2-R22 map sequentially to P12-P32")


def _check_alignment_report(
    alignment_report: dict[str, Any],
    findings: list[Finding],
) -> dict[str, str]:
    expected = {
        "r_range": "R2-R22",
        "package_count": 21,
        "complete_count": 21,
        "reconciliation_verdict": "complete",
        "ir_specification_count": 21,
    }
    failed = [
        f"{key}={alignment_report.get(key)!r}, expected {value!r}"
        for key, value in expected.items()
        if alignment_report.get(key) != value
    ]
    if alignment_report.get("incomplete") != []:
        failed.append(f"incomplete={alignment_report.get('incomplete')!r}, expected []")
    for message in failed:
        findings.append(
            Finding(
                check="alignment-report",
                severity="critical",
                message=message,
            )
        )
    return _check(
        "alignment-report",
        not failed,
        "R-series alignment report is schema-valid and complete",
    )


def _check_no_premature_r23(root: Path, findings: list[Finding]) -> dict[str, str]:
    forbidden = (
        root / "1" / "r23.txt",
        root / "docs" / "ir" / "R23-IR-01.md",
    )
    present = [str(path.relative_to(root)) for path in forbidden if path.exists()]
    for path in present:
        findings.append(
            Finding(
                check="no-premature-r23",
                severity="high",
                message=(
                    f"R23 artifact exists before an ADR-backed post-R22 module decision: {path}"
                ),
            )
        )
    return _check("no-premature-r23", not present, "No premature R23 roadmap artifact detected")


def _check(name: str, passed: bool, summary: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "passed" if passed else "failed",
        "summary": summary,
    }


def _schema(root: Path) -> dict[str, Any]:
    schema = json.loads((root / SCHEMA_REF).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return schema


def _validate_report(root: Path, report: dict[str, Any]) -> None:
    try:
        jsonschema.validate(report, _schema(root))
    except jsonschema.ValidationError as exc:
        raise RuntimeError(
            f"{SCHEMA_REF}: generated roadmap sequence gate report does not validate: {exc.message}"
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify R2-R22 roadmap sequence readiness.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="artifacts/roadmap-sequence-gate.json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    report = verify_roadmap_sequence(root)
    output = Path(args.output)
    target = output if output.is_absolute() else root / output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
