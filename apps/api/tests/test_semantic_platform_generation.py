import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools"
SRC = ROOT / "apps/api/src"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import semantic_platform_generate  # noqa: E402


def test_semantic_platform_04_generates_all_targets_atomically(tmp_path: Path) -> None:
    output = tmp_path / "generated"

    manifest = semantic_platform_generate.write_generation(ROOT, output)

    assert manifest["registry"]["id"] == "org.reference.approval"
    assert manifest["registry"]["version"] == "0.4.0"
    assert manifest["diagnostics"] == []
    artifacts = {item["path"]: item for item in manifest["artifacts"]}
    assert {
        "database/schema.sql",
        "database/mapping.json",
        "database/enforcement.json",
        "openapi/openapi.json",
        "ui/model.json",
        "tests/semantic-contracts.generated.md",
        "docs/index.md",
        "docs/objects/approval.object.request.md",
        "diagrams/request-lifecycle.mmd",
        "ai/context.json",
    } <= set(artifacts)
    assert (output / "generation-manifest.json").is_file()

    sql = (output / "database/schema.sql").read_text(encoding="utf-8")
    assert "-- semantic-id: approval.object.request" in sql
    assert "CREATE TABLE approval_request" in sql
    assert "request_number TEXT NOT NULL UNIQUE" in sql
    assert "status IN ('approved', 'cancelled', 'draft', 'rejected', 'submitted')" in sql
    assert "REFERENCES approval_person(id)" in sql

    openapi = json.loads((output / "openapi/openapi.json").read_text(encoding="utf-8"))
    assert openapi["paths"]["/requests/{id}/submit"]["post"]["x-semantic-command"] == (
        "approval.command.submit_request"
    )
    request_schema = openapi["components"]["schemas"]["Request"]
    assert request_schema["x-semantic-id"] == "approval.object.request"
    assert request_schema["properties"]["status"]["$ref"] == (
        "#/components/schemas/RequestStatus"
    )


def test_semantic_platform_04_reports_generator_coverage_without_false_enforcement(
    tmp_path: Path,
) -> None:
    manifest = semantic_platform_generate.write_generation(ROOT, tmp_path / "generated")

    coverage = {
        (item["semanticElementId"], item["target"]): item for item in manifest["coverage"]
    }
    assert coverage[("approval.constraint.description_required", "postgresql")][
        "status"
    ] == "runtime_required"
    assert coverage[("approval.transition.submit_request", "ui")]["status"] == (
        "documented_only"
    )
    assert coverage[("approval.object.request", "openapi")]["status"] == "fully_enforced"


def test_semantic_platform_04_outputs_are_deterministic(tmp_path: Path) -> None:
    first = semantic_platform_generate.write_generation(ROOT, tmp_path / "one")
    second = semantic_platform_generate.write_generation(ROOT, tmp_path / "two")

    assert first["generation_hash"] == second["generation_hash"]
    first_manifest = json.loads((tmp_path / "one/generation-manifest.json").read_text())
    second_manifest = json.loads((tmp_path / "two/generation-manifest.json").read_text())
    assert first_manifest == second_manifest


def test_semantic_platform_04_rejects_invalid_reference(tmp_path: Path) -> None:
    registry = json.loads(
        (ROOT / semantic_platform_generate.DEFAULT_REGISTRY).read_text(encoding="utf-8")
    )
    registry["objects"]["approval.object.request"]["properties"]["requester"]["type"] = (
        "Reference<approval.object.missing>"
    )
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(registry), encoding="utf-8")

    try:
        semantic_platform_generate.write_generation(
            ROOT,
            tmp_path / "generated",
            registry_path=broken,
        )
    except RuntimeError as exc:
        assert "unknown reference approval.object.missing" in str(exc)
    else:
        raise AssertionError("invalid reference was accepted")
