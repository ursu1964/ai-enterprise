import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


def _load(name: str):
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(name, root / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_load("infrastructure_choices")
production_readiness = _load("production_readiness")


def _choices() -> dict:
    return {
        section: {field: f"real-{section}-{field}" for field in fields}
        for section, fields in production_readiness.infrastructure_choices.REQUIRED_SECTIONS.items()
    }


def _evidence(status: str = "passed") -> dict:
    proof = {}
    for name, fields in production_readiness.REQUIRED_PROOF.items():
        item = {
            "status": status,
            "checked_at": "2026-08-01T10:00:00Z",
            "valid_until": "2026-09-01T10:00:00Z",
            "evidence": f"artifacts/{name}.json",
        }
        item.update(
            {
                field: True if field.endswith("verified") else f"real-{field}"
                for field in fields
            }
        )
        proof[name] = item
    return {"environment": "production", "reviewed_by": "release-owner", "proof": proof}


def test_production_readiness_requires_every_current_proof(tmp_path: Path) -> None:
    choices = _choices()
    choices["identity_proxy"]["signed_headers"] = [
        "X-Actor-ID", "X-Actor-Type", "X-Actor-Role", "X-Proxy-Timestamp", "X-Proxy-Signature"
    ]
    (tmp_path / "choices.json").write_text(json.dumps(choices), encoding="utf-8")
    (tmp_path / "evidence.json").write_text(json.dumps(_evidence()), encoding="utf-8")

    report = production_readiness.verify(
        tmp_path,
        Path("evidence.json"),
        Path("choices.json"),
        now=datetime(2026, 8, 4, tzinfo=UTC),
    )

    assert report["production_allowed"] is True
    assert len(report["checks"]) == 14
    assert {
        "production_owners",
        "pilot_results",
        "infrastructure_credentials",
        "production_run_artifacts",
        "r16_graph_backend",
    }.issubset({item["name"] for item in report["checks"]})


def test_production_readiness_blocks_missing_restore_proof(tmp_path: Path) -> None:
    choices = _choices()
    choices["identity_proxy"]["signed_headers"] = [
        "X-Actor-ID", "X-Actor-Type", "X-Actor-Role", "X-Proxy-Timestamp", "X-Proxy-Signature"
    ]
    evidence = _evidence()
    del evidence["proof"]["backup_restore"]
    (tmp_path / "choices.json").write_text(json.dumps(choices), encoding="utf-8")
    (tmp_path / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")

    report = production_readiness.verify(
        tmp_path,
        Path("evidence.json"),
        Path("choices.json"),
        now=datetime(2026, 8, 4, tzinfo=UTC),
    )

    assert report["production_allowed"] is False
    assert any(item.startswith("backup_restore:") for item in report["findings"])


def test_production_readiness_blocks_missing_operational_closure_proof(
    tmp_path: Path,
) -> None:
    choices = _choices()
    choices["identity_proxy"]["signed_headers"] = [
        "X-Actor-ID",
        "X-Actor-Type",
        "X-Actor-Role",
        "X-Proxy-Timestamp",
        "X-Proxy-Signature",
    ]
    evidence = _evidence()
    del evidence["proof"]["pilot_results"]
    evidence["proof"]["infrastructure_credentials"]["credential_inventory"] = {
        "token": "plain-secret"
    }
    (tmp_path / "choices.json").write_text(json.dumps(choices), encoding="utf-8")
    (tmp_path / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")

    report = production_readiness.verify(
        tmp_path,
        Path("evidence.json"),
        Path("choices.json"),
        now=datetime(2026, 8, 4, tzinfo=UTC),
    )

    assert report["production_allowed"] is False
    assert any(item.startswith("pilot_results:") for item in report["findings"])
    assert any("must be a reference" in item for item in report["findings"])


def test_production_readiness_blocks_missing_r16_graph_backend_proof(
    tmp_path: Path,
) -> None:
    choices = _choices()
    choices["identity_proxy"]["signed_headers"] = [
        "X-Actor-ID",
        "X-Actor-Type",
        "X-Actor-Role",
        "X-Proxy-Timestamp",
        "X-Proxy-Signature",
    ]
    evidence = _evidence()
    del evidence["proof"]["r16_graph_backend"]
    (tmp_path / "choices.json").write_text(json.dumps(choices), encoding="utf-8")
    (tmp_path / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")

    report = production_readiness.verify(
        tmp_path,
        Path("evidence.json"),
        Path("choices.json"),
        now=datetime(2026, 8, 4, tzinfo=UTC),
    )

    assert report["production_allowed"] is False
    assert any(item.startswith("r16_graph_backend:") for item in report["findings"])
