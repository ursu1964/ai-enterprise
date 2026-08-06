"""Audit the BK roadmap prompt/specification state against repository evidence.

The BK prompt in ``1/bk.txt`` is partly a roadmap instruction and partly a
concrete specification. This tool makes that boundary explicit:

* which concrete document IDs are present in the prompt,
* which implementation evidence exists in the repository, and
* whether the next referenced specification has enough source text to implement.

It does not infer or invent missing specification bodies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DOCUMENT_ID_PATTERN = re.compile(r"^Document ID:\s*(?P<document_id>[A-Z0-9-]+)\s*$", re.MULTILINE)
NEXT_SPEC_PATTERN = re.compile(
    r"The next required specification is\s+(?P<specification>R\d+-[A-Z0-9-]+)\s+—\s+"
    r"(?P<title>[^.\n]+)",
    re.MULTILINE,
)

BK_R10_EVIDENCE_PATHS: tuple[str, ...] = (
    "apps/api/src/ai_enterprise/application/bk_r10_verification_runtime.py",
    "apps/api/src/ai_enterprise/application/bk_r10_persistence_service.py",
    "apps/api/src/ai_enterprise/api/bk_r10_verification_schemas.py",
    "apps/api/src/ai_enterprise/api/routes/bk_r10_verification.py",
    "apps/api/src/ai_enterprise/infrastructure/bk_r10/models.py",
    "migrations/versions/f8a6c2d4e9b1_add_bk_r10_verification_records.py",
    "schemas/verification/handoff.schema.json",
    "schemas/verification/campaign.schema.json",
    "schemas/verification/external-backend.schema.json",
    "registry/verification-methods/bk-r10-default.json",
    "registry/verification-policies/bk-r10-default.json",
    "registry/verification-backends/bk-r10-default.json",
    "examples/verification/bk-r10-campaign.yaml",
    "apps/api/tests/test_bk_r10_verification_runtime.py",
    "apps/api/tests/test_bk_r10_verification_persistence.py",
    "apps/api/tests/test_bk_r10_verification_contracts.py",
    "docs/bk-r10-verification-validation-engine-status.md",
)

BK_R11_DERIVED_SPEC_PATH = "docs/bk-r11-evidence-audit-engine-spec.md"

BK_R11_CORE_EVIDENCE_PATHS: tuple[str, ...] = (
    BK_R11_DERIVED_SPEC_PATH,
    "apps/api/src/ai_enterprise/application/bk_r11_evidence_audit_runtime.py",
    "apps/api/src/ai_enterprise/application/bk_r11_persistence_service.py",
    "apps/api/src/ai_enterprise/api/bk_r11_evidence_audit_schemas.py",
    "apps/api/src/ai_enterprise/api/routes/bk_r11_evidence_audit.py",
    "apps/api/src/ai_enterprise/infrastructure/bk_r11/models.py",
    "apps/api/src/ai_enterprise/main.py",
    "migrations/versions/a1d5e8f2b9c4_add_bk_r11_evidence_audit_records.py",
    "migrations/versions/b2e6f9a3c8d1_add_bk_r11_archive_publication_records.py",
    "schemas/evidence-audit/evidence-package.schema.json",
    "schemas/evidence-audit/archive-backend.schema.json",
    "schemas/evidence-audit/archive-publication.schema.json",
    "schemas/evidence-audit/archive-verification.schema.json",
    "registry/evidence-audit/bk-r11-default.json",
    "examples/evidence-audit/bk-r11-package.json",
    "apps/api/tests/test_bk_r11_evidence_audit_runtime.py",
    "apps/api/tests/test_bk_r11_evidence_audit_persistence.py",
    "apps/api/tests/test_bk_r11_evidence_audit_contracts.py",
)


@dataclass(frozen=True)
class EvidenceCheck:
    path: str
    present: bool


@dataclass(frozen=True)
class ImplementedModule:
    module: str
    source_document_id: str
    title: str
    evidence: tuple[EvidenceCheck, ...]

    @property
    def complete(self) -> bool:
        return all(item.present for item in self.evidence)

    @property
    def missing_paths(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.evidence if not item.present)


def audit_bk_roadmap(root: Path, source: Path) -> dict[str, Any]:
    root = root.resolve()
    source_path = source if source.is_absolute() else root / source
    source_text = source_path.read_text(encoding="utf-8")

    document_ids = tuple(
        match.group("document_id") for match in DOCUMENT_ID_PATTERN.finditer(source_text)
    )
    next_spec = _next_spec(source_text)
    implemented_modules = (_bk_r10_module(root), _bk_r11_module(root))
    gaps = _gaps(document_ids, next_spec, implemented_modules)
    status = _status(gaps, implemented_modules)

    payload_without_hash: dict[str, Any] = {
        "schema_version": "1.0",
        "source_path": str(source_path),
        "source_hash": _sha256_text(source_text),
        "documents_detected": list(document_ids),
        "derived_specifications": _derived_specifications(root),
        "next_required_specification": next_spec,
        "implemented_modules": [
            {
                "module": module.module,
                "source_document_id": module.source_document_id,
                "title": module.title,
                "complete": module.complete,
                "missing_paths": list(module.missing_paths),
                "evidence": [asdict(item) for item in module.evidence],
            }
            for module in implemented_modules
        ],
        "gaps": gaps,
        "status": status,
        "next_action": _next_action(gaps, next_spec),
    }
    return {
        **payload_without_hash,
        "audit_hash": _stable_hash(payload_without_hash),
    }


def _bk_r10_module(root: Path) -> ImplementedModule:
    evidence = tuple(
        EvidenceCheck(path=path, present=(root / path).exists()) for path in BK_R10_EVIDENCE_PATHS
    )
    return ImplementedModule(
        module="BK-R10",
        source_document_id="R10-IR-01",
        title="AI-Enterprise Verification and Validation Engine",
        evidence=evidence,
    )


def _bk_r11_module(root: Path) -> ImplementedModule:
    evidence = tuple(
        EvidenceCheck(path=path, present=(root / path).exists())
        for path in BK_R11_CORE_EVIDENCE_PATHS
    )
    return ImplementedModule(
        module="BK-R11",
        source_document_id="R11-IR-01",
        title="Evidence and Audit Engine core runtime",
        evidence=evidence,
    )


def _derived_specifications(root: Path) -> list[dict[str, str]]:
    if not (root / BK_R11_DERIVED_SPEC_PATH).exists():
        return []
    return [
        {
            "document_id": "R11-IR-01",
            "title": "Evidence and Audit Engine",
            "path": BK_R11_DERIVED_SPEC_PATH,
            "status": "derived_local_specification",
        }
    ]


def _next_spec(source_text: str) -> dict[str, str] | None:
    matches = tuple(NEXT_SPEC_PATTERN.finditer(source_text))
    if not matches:
        return None
    match = matches[-1]
    return {
        "document_id": match.group("specification"),
        "title": match.group("title").strip(),
    }


def _gaps(
    document_ids: tuple[str, ...],
    next_spec: dict[str, str] | None,
    implemented_modules: tuple[ImplementedModule, ...],
) -> list[str]:
    gaps: list[str] = []
    for module in implemented_modules:
        if module.source_document_id not in document_ids and module.module != "BK-R11":
            gaps.append(f"{module.module}_SOURCE_DOCUMENT_MISSING")
        if not module.complete:
            gaps.append(f"{module.module}_IMPLEMENTATION_EVIDENCE_MISSING")

    if next_spec is not None and next_spec["document_id"] not in document_ids:
        gaps.append("BK_NEXT_CANONICAL_SPEC_BODY_MISSING")
    return gaps


def _next_action(gaps: list[str], next_spec: dict[str, str] | None) -> str:
    if not gaps:
        return "Continue with the next concrete BK specification."
    if gaps == ["BK_NEXT_CANONICAL_SPEC_BODY_MISSING"] and next_spec is not None:
        return (
            f"Canonicalize the full {next_spec['document_id']} source body in the roadmap "
            "prompt/file, or continue with clearly marked derived implementation slices."
        )
    return "Resolve missing source or implementation evidence before continuing."


def _status(gaps: list[str], implemented_modules: tuple[ImplementedModule, ...]) -> str:
    if not gaps:
        return "pass"
    if gaps == ["BK_NEXT_CANONICAL_SPEC_BODY_MISSING"] and all(
        module.complete for module in implemented_modules
    ):
        return "r11_core_runtime_ready_canonical_spec_missing"
    return "blocked"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_hash(payload: dict[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source", type=Path, default=Path("1/bk.txt"))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    report = audit_bk_roadmap(args.root, args.source)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"

    if args.output:
        target = args.output if args.output.is_absolute() else args.root / args.output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    elif args.json:
        print(rendered, end="")
    else:
        print(f"BK roadmap audit: {report['status']}")
        for gap in report["gaps"]:
            print(f"- {gap}")
        print(report["next_action"])

    return 0 if report["status"] != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
