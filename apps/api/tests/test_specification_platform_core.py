from copy import deepcopy

import pytest
from pydantic import ValidationError

from ai_enterprise.application.specification import SpecificationGenerator
from ai_enterprise.application.specification.generation import GeneratedArtifact
from ai_enterprise.domain.specification.api import classify_api_change, generate_openapi
from ai_enterprise.domain.specification.database import (
    ColumnSpecification,
    EntitySpecification,
    ForeignKeySpecification,
    IndexSpecification,
    classify_database_change,
    generate_create_table,
)
from ai_enterprise.domain.specification.event import (
    EventSpecification,
    classify_event_change,
    generate_event_schema,
)
from ai_enterprise.domain.specification.kernel import (
    Compatibility,
    Provenance,
    SpecificationArtifact,
    SpecificationError,
    SpecificationIdentity,
    canonical_json,
    require_version_for_change,
)
from ai_enterprise.domain.specification.service import (
    DataField,
    Endpoint,
    Operation,
    ServiceSpecification,
)


def _provenance() -> Provenance:
    return Provenance(requirements_hash="a" * 64, architecture_hash="b" * 64, package_hash="c" * 64)


def _identity(version: str = "1.2.0") -> SpecificationIdentity:
    return SpecificationIdentity(
        specification_key="project.orders.service", version=version, provenance=_provenance()
    )


def _field(name: str, *, required: bool = True) -> DataField:
    return DataField(name=name, type="uuid", required=required, description=f"The {name} value")


def _service() -> ServiceSpecification:
    return ServiceSpecification(
        name="ProjectService",
        purpose="Create and retrieve governed projects.",
        dependencies=("AuditService",),
        commands=(
            Operation(
                name="CreateProject",
                input_fields=(_field("project_id"),),
                output_fields=(_field("project_id"),),
                authorization_capability="project.create",
                timeout_seconds=10,
                retry_limit=0,
                idempotent=True,
            ),
        ),
        endpoints=(
            Endpoint(
                operation_name="CreateProject",
                method="POST",
                path="/projects",
                success_status=201,
            ),
        ),
        produced_events=("ProjectCreated",),
        permissions=("project.create",),
        p95_latency_ms=150,
    )


def _entity(*, extra: ColumnSpecification | None = None) -> EntitySpecification:
    columns = [
        ColumnSpecification(name="created_at", type="timestamptz", default_sql="now()"),
        ColumnSpecification(name="id", type="uuid", primary_key=True),
        ColumnSpecification(name="name", type="text"),
    ]
    if extra is not None:
        columns.append(extra)
        columns.sort(key=lambda item: item.name)
    return EntitySpecification(
        table_name="projects",
        columns=tuple(columns),
        indexes=(IndexSpecification(name="ix_projects_name", columns=("name",)),),
    )


def _event(*, extra: DataField | None = None) -> EventSpecification:
    fields = [_field("package_id"), _field("status")]
    if extra is not None:
        fields.append(extra)
        fields.sort(key=lambda item: item.name)
    return EventSpecification(
        name="PackageCompleted",
        version="1.0.0",
        producer="ExecutionService",
        consumers=("AuditService", "ReviewService"),
        payload=tuple(fields),
        retention_days=365,
        ordering_key="package_id",
        idempotency_key="package_id",
        replay_policy="audited",
    )


def test_kernel_canonicalization_is_order_independent_hash_bound_and_strict() -> None:
    assert canonical_json({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    artifact = SpecificationArtifact.build(
        identity=_identity(), kind="service", document={"z": 1, "a": [2, 1]}
    )
    assert artifact.verify()
    assert not artifact.model_copy(update={"document": {"z": 2}}).verify()
    with pytest.raises(ValidationError):
        Provenance(
            requirements_hash="not-a-hash", architecture_hash="b" * 64, package_hash="c" * 64
        )
    with pytest.raises(ValidationError):
        SpecificationIdentity(
            specification_key="project.orders.service",
            version="v1",
            provenance=_provenance(),
            unexpected=True,
        )


def test_service_language_rejects_invention_and_unbound_endpoints() -> None:
    service = _service()
    assert service.endpoints[0].operation_name == "CreateProject"
    with pytest.raises(ValidationError, match="declared operations"):
        service.model_copy(
            update={
                "endpoints": (
                    Endpoint(
                        operation_name="DeleteEverything",
                        method="DELETE",
                        path="/projects",
                        success_status=204,
                    ),
                )
            }
        ).model_validate(
            service.model_copy(
                update={
                    "endpoints": (
                        Endpoint(
                            operation_name="DeleteEverything",
                            method="DELETE",
                            path="/projects",
                            success_status=204,
                        ),
                    )
                }
            ).model_dump()
        )


def test_openapi_generation_golden_is_deterministic_and_provenance_bound() -> None:
    service = _service()
    document = generate_openapi(service, version="1.2.0", spec_hash="d" * 64)
    assert document == generate_openapi(service, version="1.2.0", spec_hash="d" * 64)
    assert document["info"] == {
        "title": "ProjectService",
        "version": "1.2.0",
        "x-spec-hash": "d" * 64,
    }
    operation = document["paths"]["/projects"]["post"]
    assert operation["operationId"] == "CreateProject"
    assert operation["x-required-capability"] == "project.create"
    generated = SpecificationGenerator().api(_identity(), service)
    assert generated.content["info"]["x-spec-hash"] == generated.source_spec_hash  # type: ignore[index]
    assert generated.provenance["requirements_hash"] == "a" * 64


def test_api_compatibility_detects_removed_operations_and_new_required_fields() -> None:
    old = generate_openapi(_service(), version="1.0.0", spec_hash="a" * 64)
    removed = deepcopy(old)
    removed["paths"] = {}
    assert classify_api_change(old, removed) is Compatibility.BREAKING
    required = deepcopy(old)
    required["components"]["schemas"]["CreateProjectInput"]["required"].append("new_field")
    assert classify_api_change(old, required) is Compatibility.BREAKING


def test_database_sql_golden_and_compatibility_are_fail_closed() -> None:
    entity = _entity()
    assert generate_create_table(entity) == (
        "CREATE TABLE projects (\n"
        "  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),\n"
        "  id UUID PRIMARY KEY NOT NULL,\n"
        "  name TEXT NOT NULL\n"
        ");\nCREATE INDEX ix_projects_name ON projects (name);"
    )
    optional = _entity(extra=ColumnSpecification(name="description", type="text", nullable=True))
    assert classify_database_change(entity, optional) is Compatibility.CONDITIONALLY_COMPATIBLE
    required = _entity(extra=ColumnSpecification(name="owner_id", type="uuid"))
    assert classify_database_change(entity, required) is Compatibility.BREAKING
    with pytest.raises(ValidationError, match="allowlist"):
        ColumnSpecification(name="bad", type="text", default_sql="drop table projects")


def test_event_schema_golden_preserves_governance_and_compatibility() -> None:
    event = _event()
    schema = generate_event_schema(event, spec_hash="e" * 64)
    assert schema["$id"] == "urn:ai-enterprise:event:PackageCompleted:1.0.0"
    assert schema["x-producer"] == "ExecutionService"
    assert schema["x-consumers"] == ["AuditService", "ReviewService"]
    assert schema["x-replay-policy"] == "audited"
    optional = _event(
        extra=DataField(
            name="patch_hash", type="string", required=False, description="Patch digest"
        )
    )
    assert classify_event_change(event, optional) is Compatibility.CONDITIONALLY_COMPATIBLE
    required = _event(
        extra=DataField(name="attempt_id", type="uuid", description="Attempt identity")
    )
    assert classify_event_change(event, required) is Compatibility.BREAKING


def test_versions_enforce_declared_compatibility() -> None:
    require_version_for_change("1.2.0", "1.3.0", Compatibility.COMPATIBLE)
    require_version_for_change("1.2.0", "2.0.0", Compatibility.BREAKING)
    with pytest.raises(SpecificationError, match="major"):
        require_version_for_change("1.2.0", "1.3.0", Compatibility.BREAKING)
    with pytest.raises(SpecificationError, match="increase"):
        require_version_for_change("1.2.0", "1.2.0", Compatibility.COMPATIBLE)


def test_canonicalization_rejects_ambiguous_numbers_keys_and_types() -> None:
    with pytest.raises(SpecificationError, match="non-finite"):
        canonical_json({"score": float("nan")})
    with pytest.raises(SpecificationError, match="collide"):
        canonical_json({"é": 1, "e\u0301": 2})
    with pytest.raises(SpecificationError, match="keys"):
        canonical_json({1: "not allowed"})  # type: ignore[dict-item]
    assert canonical_json({"name": "e\u0301"}) == canonical_json({"name": "é"})


def test_generated_artifact_detects_content_and_provenance_substitution() -> None:
    generated = SpecificationGenerator().api(_identity(), _service())
    assert generated.verify()
    assert not GeneratedArtifact(
        generated.artifact_type,
        generated.content,
        generated.source_spec_hash,
        {**generated.provenance, "requirements_hash": "f" * 64},
        generated.artifact_hash,
    ).verify()
    assert isinstance(generated.content, dict)
    generated.content["info"]["version"] = "9.9.9"
    assert not generated.verify()


def test_endpoint_collision_and_field_collision_cannot_overwrite_generation() -> None:
    service = _service()
    second = Operation(
        name="ArchiveProject",
        input_fields=(_field("project_id"),),
        authorization_capability="project.archive",
        timeout_seconds=10,
        retry_limit=0,
        idempotent=True,
    )
    with pytest.raises(ValidationError, match="method/path"):
        ServiceSpecification.model_validate(
            {
                **service.model_dump(),
                "commands": (*service.model_dump()["commands"], second.model_dump()),
                "endpoints": (
                    *service.model_dump()["endpoints"],
                    {
                        "operation_name": "ArchiveProject",
                        "method": "POST",
                        "path": "/projects",
                        "success_status": 202,
                    },
                ),
            },
            strict=True,
        )
    with pytest.raises(ValidationError, match="sorted and unique"):
        Operation(
            name="BadOperation",
            input_fields=(_field("value"), _field("value")),
            authorization_capability="bad.execute",
            timeout_seconds=1,
            retry_limit=0,
            idempotent=True,
        )


def test_compatibility_detects_schema_constraint_and_event_governance_changes() -> None:
    old_api = generate_openapi(_service(), version="1.0.0", spec_hash="a" * 64)
    changed_type = deepcopy(old_api)
    changed_type["components"]["schemas"]["CreateProjectInput"]["properties"]["project_id"][
        "type"
    ] = "integer"
    assert classify_api_change(old_api, changed_type) is Compatibility.BREAKING

    old_entity = _entity()
    changed_constraint = old_entity.model_copy(
        update={
            "columns": tuple(
                column.model_copy(update={"unique": True}) if column.name == "name" else column
                for column in old_entity.columns
            )
        }
    )
    assert classify_database_change(old_entity, changed_constraint) is Compatibility.BREAKING
    changed_replay = _event().model_copy(update={"replay_policy": "unrestricted"})
    assert classify_event_change(_event(), changed_replay) is Compatibility.BREAKING


def test_foreign_key_identifiers_cannot_inject_sql() -> None:
    with pytest.raises(ValidationError):
        ForeignKeySpecification(
            column="owner_id",
            referenced_table="users; DROP TABLE projects",
            referenced_column="id",
        )
