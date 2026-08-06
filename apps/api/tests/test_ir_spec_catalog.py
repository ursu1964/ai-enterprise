import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
IR_DIR = ROOT / "docs" / "ir"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ir_catalog_tracks_r10_to_r12_without_r_series_collision() -> None:
    expected = {
        "R02-IR-01": IR_DIR / "R02-IR-01-foundational-domain-manifest-concepts.md",
        "R03-IR-01": IR_DIR / "R03-IR-01-registry-foundations-executable-foundation.md",
        "R04-IR-01": IR_DIR / "R04-IR-01-controlled-ai-participation.md",
        "R05-IR-01": IR_DIR / "R05-IR-01-manifest-transformation-engine.md",
        "R06-IR-01": IR_DIR / "R06-IR-01-artifact-generation-framework.md",
        "R07-IR-01": IR_DIR / "R07-IR-01-execution-runtime-model.md",
        "R08-IR-01": IR_DIR / "R08-IR-01-governance-evolution-intelligence-framework.md",
        "R09-IR-01": IR_DIR / "R09-IR-01-universal-ai-enterprise-kernel.md",
        "R10-IR-01": IR_DIR / "R10-IR-01-verification-validation-engine.md",
        "R11-IR-01": IR_DIR / "R11-IR-01-evidence-audit-engine.md",
        "R12-IR-01": IR_DIR / "R12-IR-01-policy-governance-engine.md",
        "R13-IR-01": IR_DIR / "R13-IR-01-ai-orchestration-engine.md",
        "R14-IR-01": IR_DIR / "R14-IR-01-agent-framework.md",
        "R15-IR-01": IR_DIR / "R15-IR-01-workflow-process-engine.md",
        "R16-IR-01": IR_DIR / "R16-IR-01-repository-integration-engine.md",
        "R17-IR-01": IR_DIR / "R17-IR-01-deployment-runtime-engine.md",
        "R18-IR-01": IR_DIR / "R18-IR-01-observability-telemetry-engine.md",
        "R19-IR-01": IR_DIR / "R19-IR-01-security-identity-engine.md",
        "R20-IR-01": IR_DIR / "R20-IR-01-organizational-knowledge-engine.md",
        "R21-IR-01": IR_DIR / "R21-IR-01-platform-administration-operations.md",
        "R22-IR-01": IR_DIR / "R22-IR-01-constitutional-kernel-evolution-framework.md",
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
