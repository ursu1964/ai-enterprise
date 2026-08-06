import importlib.util
import json
import sys
from pathlib import Path


def _load_r_series_alignment():
    root = Path(__file__).resolve().parents[3]
    path = root / "tools" / "r_series_alignment.py"
    spec = importlib.util.spec_from_file_location("r_series_alignment", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_r_series_alignment_detects_r2_to_r22_repository_evidence() -> None:
    module = _load_r_series_alignment()
    root = Path(__file__).resolve().parents[3]

    report = module._report(module.build_alignment(root))

    assert report["schema_version"] == "1.0"
    assert report["r_range"] == "R2-R22"
    assert report["package_count"] == 21
    assert report["complete_count"] == 21
    assert report["incomplete"] == []
    assert len(report["alignment_hash"]) == 64

    packages = {item["r"]: item for item in report["packages"]}
    assert packages["R2"]["p_phase"] == "P12"
    assert packages["R22"]["p_phase"] == "P32"
    assert packages["R22"]["complete"] is True


def test_r_series_alignment_generates_required_package_structure(tmp_path: Path) -> None:
    module = _load_r_series_alignment()
    root = Path(__file__).resolve().parents[3]

    # Copy only the evidence paths required for a deterministic smoke generation.
    for alignment in module.build_alignment(root):
        source = root / alignment.spec_path
        target = tmp_path / alignment.spec_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        for capability in alignment.capabilities:
            for evidence in capability.evidence:
                evidence_source = root / evidence
                evidence_target = tmp_path / evidence
                evidence_target.parent.mkdir(parents=True, exist_ok=True)
                evidence_target.write_text(
                    evidence_source.read_text(encoding="utf-8", errors="replace"),
                    encoding="utf-8",
                )

    report = module.generate_alignment(tmp_path)

    assert report["complete_count"] == 21
    assert (tmp_path / "docs/R-INDEX.md").exists()
    assert (tmp_path / "docs/R-AUDIT-01-current-state-repository-audit.md").exists()
    assert (tmp_path / "docs/R-AUDIT-02-r1-r22-alignment-matrix.md").exists()
    assert (tmp_path / "docs/R-REV-01-corrected-r-series-baseline.md").exists()

    for r_number in range(2, 23):
        package = tmp_path / "implementation" / f"r{r_number:02d}"
        for relative_path in module.PACKAGE_FILES:
            assert (package / relative_path).exists()

    payload = json.loads((tmp_path / "artifacts/r-series-alignment-report.json").read_text())
    assert payload["alignment_hash"] == report["alignment_hash"]
