import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]


def _json(path: str) -> dict[str, object]:
    document = json.loads((ROOT / path).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(document)
    return document


def test_r3_required_specification_deliverables_exist_and_are_valid() -> None:
    for path in (
        "specifications/AEPM-0.1.schema.json",
        "specifications/AEIR-0.1.schema.json",
        "specifications/RELATIONSHIP-0.1.schema.json",
        "specifications/SOURCE-0.1.schema.json",
        "specifications/validation/VALIDATION-FINDING-0.1.schema.json",
        "specifications/SNAPSHOT-0.1.schema.json",
        "specifications/EVENT-0.1.schema.json",
    ):
        _json(path)
    for path in (
        "specifications/AEPM-0.1.md",
        "specifications/AEIR-0.1.md",
        "specifications/RELATIONSHIP-0.1.md",
        "specifications/TRACEABILITY-0.1.md",
        "specifications/LIFECYCLE-0.1.md",
    ):
        assert (ROOT / path).read_text(encoding="utf-8").strip()


def test_r3_yaml_examples_cover_valid_and_invalid_foundation_manifests() -> None:
    schema = _json("specifications/aepm/AEPM-0.1.schema.json")
    valid = yaml.safe_load(
        (ROOT / "examples/valid/inventory-management.aepm.yaml").read_text(encoding="utf-8")
    )
    invalid = yaml.safe_load(
        (ROOT / "examples/invalid/incomplete-inventory-management.aepm.yaml").read_text(
            encoding="utf-8"
        )
    )

    Draft202012Validator(schema).validate(valid)
    assert list(Draft202012Validator(schema).iter_errors(invalid))


def test_r3_snapshot_source_and_event_schema_accept_foundation_instances() -> None:
    Draft202012Validator(_json("specifications/SNAPSHOT-0.1.schema.json")).validate(
        {
            "schema_version": "aeir-snapshot-0.1",
            "snapshot_id": "SNP-0001",
            "project_id": "PRJ-001",
            "aepm_version": "0.1",
            "aeir_version": "0.1",
            "source_model_sha256": "a" * 64,
            "object_versions": ["INTENT-001:0.1.0"],
            "relationship_versions": ["REL-001:0.1.0"],
            "status": "approved",
            "created_at": "2026-08-05T00:00:00Z",
            "created_by": "client-reviewer",
            "approved_by": "client-reviewer",
            "snapshot_sha256": "b" * 64,
        }
    )
    Draft202012Validator(_json("specifications/SOURCE-0.1.schema.json")).validate(
        {
            "id": "SRCROW-001",
            "project_id": "PRJ-001",
            "storage_provider": "local",
            "bucket": "aepm-sources",
            "object_key": "PRJ-001/source",
            "original_filename": "inventory-management.aepm.yaml",
            "media_type": "application/yaml",
            "content_sha256": "c" * 64,
            "size_bytes": 1024,
            "source_metadata": {"stage": "r3_foundation_import"},
            "uploaded_by": "client-reviewer",
        }
    )
    Draft202012Validator(_json("specifications/EVENT-0.1.schema.json")).validate(
        {
            "event_id": "EVT-0001",
            "project_id": "PRJ-001",
            "sequence": 1,
            "event_type": "snapshot.created",
            "entity_type": "snapshot",
            "entity_id": "SNP-0001",
            "entity_version": 1,
            "actor_type": "human",
            "actor_id": "client-reviewer",
            "previous_hash": None,
            "event_hash": "d" * 64,
            "payload": {"snapshot_id": "SNP-0001"},
        }
    )
