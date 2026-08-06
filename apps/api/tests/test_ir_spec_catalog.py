import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
IR_DIR = ROOT / "docs" / "ir"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ir_catalog_tracks_r10_to_r12_without_r_series_collision() -> None:
    expected = {
        "R10-IR-01": IR_DIR / "R10-IR-01-verification-validation-engine.md",
        "R11-IR-01": IR_DIR / "R11-IR-01-evidence-audit-engine.md",
        "R12-IR-01": IR_DIR / "R12-IR-01-policy-governance-engine.md",
        "R13-IR-01": IR_DIR / "R13-IR-01-ai-orchestration-engine.md",
        "R14-IR-01": IR_DIR / "R14-IR-01-agent-framework.md",
    }

    for document_id, path in expected.items():
        text = _read(path)
        assert f"Document ID: {document_id}" in text
        assert "Status: IMPLEMENTATION READY" in text
        assert "does not replace" in text or "instead of replacing" in text

    catalog = _read(IR_DIR / "README.md")
    for document_id, path in expected.items():
        assert document_id in catalog
        assert path.relative_to(ROOT).as_posix() in catalog


def test_ir_specs_have_required_implementation_ready_sections() -> None:
    required_sections = {
        "Purpose",
        "Constitutional requirements",
        "Canonical domain model",
        "Commands",
        "Events",
        "Security and governance",
        "Repository implementation mapping",
        "Acceptance criteria",
        "Readiness verdict",
    }

    for path in sorted(IR_DIR.glob("R*-IR-*.md")):
        text = _read(path)
        headings = {
            match.group(1).strip()
            for match in re.finditer(r"^##\s+(.+)$", text, flags=re.MULTILINE)
        }
        assert required_sections <= headings, path
