import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import jsonschema


def _load(name: str):
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(name, root / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_load("production_readiness_contracts")
_load("infrastructure_choices")
_load("production_readiness")
_load("production_evidence_plan")
production_evidence_status = _load("production_evidence_status")
SCHEMA = json.loads(
    (
        Path(__file__).resolve().parents[3]
        / "schemas"
        / "production-readiness"
        / "production-evidence-status.schema.json"
    ).read_text(encoding="utf-8")
)


def _choices() -> dict:
    return {
        "domain_tls": {
            "domain": "ai-enterprise.example.com",
            "tls_provider": "managed-load-balancer",
            "certificate_owner": "platform-team",
            "renewal_proof": "ticket://tls-renewal",
        }
    }


def _evidence() -> dict:
    return {
        "environment": "production",
        "reviewed_by": "release-owner",
        "proof": {
            "tls": {
                "status": "pending",
                "checked_at": "YYYY-MM-DDTHH:MM:SSZ",
                "valid_until": "YYYY-MM-DDTHH:MM:SSZ",
                "evidence": "certificate-check-output",
                "endpoint": "https://service.example.com",
                "certificate_expires_at": "YYYY-MM-DDTHH:MM:SSZ",
            }
        },
    }


def test_production_evidence_status_summarizes_blocked_items(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        production_evidence_status.production_evidence_plan,
        "datetime",
        _FrozenDatetime,
    )
    (tmp_path / "choices.json").write_text(json.dumps(_choices()), encoding="utf-8")
    (tmp_path / "evidence.json").write_text(json.dumps(_evidence()), encoding="utf-8")

    status = production_evidence_status.build_status(
        tmp_path,
        evidence_file=Path("evidence.json"),
        choices_file=Path("choices.json"),
    )

    assert status["production_allowed"] is False
    assert status["blocked_proof_count"] >= 1
    assert status["blocked_choice_count"] >= 1
    assert any(item["name"] == "tls" for item in status["blocked_proofs"])
    assert any(item["section"] == "domain_tls" for item in status["blocked_choices"])
    assert "rtk make production-readiness-contracts" in status["next_commands"]
    assert "rtk make production-readiness" in status["next_commands"]
    jsonschema.validate(status, SCHEMA)

    markdown = production_evidence_status.render_markdown(status)
    assert "# Production Evidence Status" in markdown
    assert "- [ ] `tls`" in markdown
    assert "- [ ] `domain_tls`" in markdown
    assert "`rtk make production-readiness-contracts`" in markdown
    assert "`rtk make production-readiness`" in markdown


def test_production_evidence_status_fails_closed_when_schema_validation_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        production_evidence_status.production_evidence_plan,
        "datetime",
        _FrozenDatetime,
    )
    (tmp_path / "choices.json").write_text(json.dumps(_choices()), encoding="utf-8")
    (tmp_path / "evidence.json").write_text(json.dumps(_evidence()), encoding="utf-8")
    original_schema = production_evidence_status._schema

    def stricter_schema() -> dict:
        schema = original_schema()
        return {**schema, "required": [*schema["required"], "impossible_field"]}

    monkeypatch.setattr(production_evidence_status, "_schema", stricter_schema)

    try:
        production_evidence_status.build_status(
            tmp_path,
            evidence_file=Path("evidence.json"),
            choices_file=Path("choices.json"),
        )
    except RuntimeError as exc:
        assert "production-evidence-status.schema.json" in str(exc)
        assert "generated production evidence status does not validate" in str(exc)
    else:
        raise AssertionError("invalid production evidence status report was accepted")


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: ANN001
        return datetime(2026, 8, 4, tzinfo=UTC)
