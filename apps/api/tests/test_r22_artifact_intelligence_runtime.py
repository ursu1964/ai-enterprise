from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from ai_enterprise.application.r21_execution_orchestrator_runtime import (
    r21_apply_approval,
    r21_compile_project,
    r21_create_execution_plan,
    r21_resume_execution,
    r21_start_execution,
)
from ai_enterprise.application.r22_artifact_intelligence_runtime import (
    ARTIFACT_INTELLIGENCE_VERSION,
    r22_empty_registry,
    r22_evidence_coverage,
    r22_generate_evidence_package,
    r22_graph_neighbors,
    r22_graph_path,
    r22_ingest_r21_execution,
    r22_mark_downstream_stale,
    r22_operational_readiness,
    r22_promote_artifact_version,
    r22_read_registry,
    r22_register_artifact,
    r22_reproducibility_record,
    r22_search_artifacts,
    r22_supersede_artifact_version,
    r22_verify_integrity,
    r22_write_registry,
)
from ai_enterprise.main import app

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "schemas" / "Manifest.schema.json"
REGISTRY = ROOT / "registry"
VALID_MANIFEST = ROOT / "manifest" / "crm.r14.json"


def _headers() -> dict[str, str]:
    return {
        "X-Actor-ID": "local-dashboard-admin",
        "X-Actor-Type": "human",
        "X-Actor-Role": "platform-admin",
    }


def _approved_r21_execution():
    manifest = json.loads(VALID_MANIFEST.read_text(encoding="utf-8"))
    compilation = r21_compile_project(manifest, SCHEMA, REGISTRY)
    plan = r21_create_execution_plan(manifest, compilation)
    execution = r21_start_execution(plan)
    execution = r21_apply_approval(
        execution,
        gate_id="gate-release",
        decision="approve",
        actor_role="project_owner",
        actor_id="owner",
    )
    execution = r21_apply_approval(
        execution,
        gate_id="gate-release",
        decision="approve",
        actor_role="release_authority",
        actor_id="release",
    )
    return r21_resume_execution(plan, execution)


def test_r22_registers_immutable_content_addressed_artifact() -> None:
    registry = r22_empty_registry("project-r22", "tenant-a")
    result = r22_register_artifact(
        registry,
        artifact_type="openapi-contract",
        artifact_class="implementation",
        title="OpenAPI Contract",
        content={"openapi": "3.1.0", "paths": {"/accounts": {}}},
        manifest_traces=(
            {
                "source_type": "REQUIREMENT",
                "source_id": "REQ-API-001",
                "relationship_type": "SATISFIES",
            },
        ),
        work_package_ids=("wp-api-contract",),
        validations=(
            {"validator_category": "schema", "validator_id": "openapi-schema", "status": "PASSED"},
        ),
        approvals=(
            {
                "approver_role": "architecture_authority",
                "approver_id": "arch-1",
                "decision": "APPROVED",
            },
        ),
    )

    assert result.accepted is True
    assert result.artifact_version_id is not None
    version = result.registry.versions[0]
    assert version.immutable is True
    assert version.content.checksum.startswith("sha256:")
    assert version.content.content_address.startswith("sha256/")
    assert version.state.integrity == "VERIFIED"
    assert version.state.validation == "PASSED"
    assert result.registry.provenance_records[0].subject_id == version.artifact_version_id


def test_r22_rejects_checksum_mismatch_and_records_security_event() -> None:
    result = r22_register_artifact(
        r22_empty_registry("project-r22", "tenant-a"),
        artifact_type="openapi-contract",
        artifact_class="implementation",
        title="OpenAPI Contract",
        content={"openapi": "3.1.0"},
        declared_checksum="sha256:not-the-real-checksum",
    )

    assert result.accepted is False
    assert any(item.code == "R22_CHECKSUM_MISMATCH" for item in result.diagnostics)
    assert result.registry.events[-1].event_type == "artifact.integrity.failed"


def test_r22_promotion_blocks_missing_trace_validation_and_approval() -> None:
    registered = r22_register_artifact(
        r22_empty_registry("project-r22", "tenant-a"),
        artifact_type="service-code",
        artifact_class="implementation",
        title="Service Code",
        content={"files": ["app.py"]},
    )

    report = r22_promote_artifact_version(
        registered.registry,
        registered.artifact_version_id or "",
        "RELEASED",
    )

    assert report.allowed is False
    codes = {item.code for item in report.diagnostics}
    assert {"R22_TRACE_REQUIRED", "R22_VALIDATION_REQUIRED", "R22_APPROVAL_REQUIRED"} <= codes


def test_r22_promotes_version_only_when_exact_evidence_is_bound() -> None:
    registered = r22_register_artifact(
        r22_empty_registry("project-r22", "tenant-a"),
        artifact_type="release-package",
        artifact_class="delivery",
        title="Release Package",
        content={"artifacts": ["api", "tests"]},
        manifest_traces=(
            {
                "source_type": "REQUIREMENT",
                "source_id": "REQ-API-001",
                "relationship_type": "SATISFIES",
            },
        ),
        validations=(
            {
                "validator_category": "integrity",
                "validator_id": "package-checksum",
                "status": "PASSED",
            },
        ),
        approvals=(
            {
                "approver_role": "release_authority",
                "approver_id": "release-1",
                "decision": "APPROVED",
            },
        ),
    )

    report = r22_promote_artifact_version(
        registered.registry,
        registered.artifact_version_id or "",
        "RELEASED",
    )

    assert report.allowed is True
    promoted = report.registry.versions[0]
    assert promoted.state.lifecycle == "RELEASED"
    assert promoted.approval_ids
    assert report.registry.events[-1].event_type == "artifact.released"


def test_r22_supersession_and_impact_preserve_history_and_mark_downstream_stale() -> None:
    first = r22_register_artifact(
        r22_empty_registry("project-r22", "tenant-a"),
        artifact_type="openapi-contract",
        artifact_class="implementation",
        title="OpenAPI Contract",
        content={"version": 1},
        manifest_traces=(
            {
                "source_type": "REQUIREMENT",
                "source_id": "REQ-API-001",
                "relationship_type": "SATISFIES",
            },
        ),
        validations=({"status": "PASSED"},),
        approvals=({"approver_id": "owner"},),
    )
    second = r22_register_artifact(
        first.registry,
        artifact_type="openapi-contract",
        artifact_class="implementation",
        title="OpenAPI Contract",
        content={"version": 2},
        manifest_traces=(
            {
                "source_type": "REQUIREMENT",
                "source_id": "REQ-API-001",
                "relationship_type": "SATISFIES",
            },
        ),
        validations=({"status": "PASSED"},),
        approvals=({"approver_id": "owner"},),
    )

    superseded = r22_supersede_artifact_version(
        second.registry,
        first.artifact_version_id or "",
        second.artifact_version_id or "",
        reason="requirement changed",
    )
    previous = next(
        item
        for item in superseded.versions
        if item.artifact_version_id == first.artifact_version_id
    )
    stale_registry, analysis = r22_mark_downstream_stale(superseded, "REQ-API-001")

    assert previous.state.lifecycle == "SUPERSEDED"
    assert previous.state.freshness == "STALE"
    assert second.artifact_version_id in analysis.affected_artifact_version_ids
    assert any(item.state.freshness == "STALE" for item in stale_registry.versions)


def test_r22_graph_traversal_coverage_package_integrity_and_reproducibility() -> None:
    registered = r22_register_artifact(
        r22_empty_registry("project-r22", "tenant-a"),
        artifact_type="test-report",
        artifact_class="validation",
        title="Test Report",
        content={"passed": True},
        manifest_traces=(
            {
                "source_type": "REQUIREMENT",
                "source_id": "REQ-API-001",
                "relationship_type": "VALIDATES",
            },
        ),
        validations=({"status": "PASSED"},),
        approvals=({"approver_id": "qa"},),
    )
    version_id = registered.artifact_version_id or ""

    downstream = r22_graph_neighbors(
        registered.registry,
        "REQUIREMENT:REQ-API-001",
        direction="downstream",
        actor_tenant_id="tenant-a",
    )
    denied = r22_graph_neighbors(
        registered.registry,
        "REQUIREMENT:REQ-API-001",
        direction="downstream",
        actor_tenant_id="tenant-b",
    )
    path = r22_graph_path(
        registered.registry,
        "REQUIREMENT:REQ-API-001",
        f"ARTIFACT_VERSION:{version_id}",
        actor_tenant_id="tenant-a",
    )
    coverage = r22_evidence_coverage(registered.registry)
    package = r22_generate_evidence_package(registered.registry, execution_id="exec-1")
    integrity = r22_verify_integrity(registered.registry, version_id, content={"passed": True})
    reproducibility = r22_reproducibility_record(registered.registry, version_id)

    assert downstream["authorized"] is True
    assert denied["authorized"] is False
    assert path["path"][0] == "REQUIREMENT:REQ-API-001"
    assert coverage.critical_gaps == ()
    assert package.integrity["package_checksum"].startswith("sha256:")
    assert integrity.conclusion == "AUTHENTIC"
    assert reproducibility.status in {"PARTIALLY_REPRODUCIBLE", "EXACTLY_REPRODUCIBLE"}


def test_r22_ingests_r21_execution_as_evidence_graph() -> None:
    execution = _approved_r21_execution()
    registry = r22_ingest_r21_execution(execution, tenant_id="tenant-a")

    assert registry.version == ARTIFACT_INTELLIGENCE_VERSION
    assert len(registry.artifacts) == len(execution.artifacts)
    assert len(registry.provenance_records) == len(execution.artifacts)
    assert registry.graph.nodes
    assert all(version.trace_relationship_ids for version in registry.versions)
    assert r22_search_artifacts(registry, artifact_class="implementation")


def _r22_operational_config() -> dict[str, object]:
    return {
        "signature": {
            "provider": "kms",
            "key_ref": "kms://artifact-signing-key",
            "algorithm": "RSASSA_PSS_SHA_256",
            "verification_ref": "runbook://r22/signature-verification",
        },
        "object_storage": {
            "provider": "s3",
            "bucket": "ai-enterprise-artifacts",
            "region": "eu-central-1",
            "credentials_ref": "secret-ref://aws/artifact-publisher",
            "encryption": "kms://artifact-storage-key",
        },
        "graph_backend": {
            "backend": "neo4j",
            "endpoint": "neo4j+s://graph.example.test",
            "repository": "artifact-intelligence",
            "credentials_ref": "secret-ref://neo4j/artifact-intelligence",
            "partition_strategy": "tenant-project",
        },
    }


def test_r22_operational_readiness_fails_closed_without_external_backends() -> None:
    report = r22_operational_readiness({}, production=True)

    assert report.ready is False
    assert report.status == "blocked"
    assert {check.backend for check in report.checks} == {
        "signature",
        "object_storage",
        "graph_backend",
    }
    codes = {finding.code for finding in report.findings}
    assert "R22_PRODUCTION_SIGNATURE_PROVIDER_INVALID" in codes
    assert "R22_PRODUCTION_OBJECT_STORAGE_PROVIDER_INVALID" in codes
    assert "R22_PRODUCTION_GRAPH_BACKEND_INVALID" in codes


def test_r22_operational_readiness_accepts_real_configuration_references() -> None:
    report = r22_operational_readiness(_r22_operational_config(), production=True)

    assert report.ready is True
    assert report.status == "ready"
    assert all(check.status == "ready" for check in report.checks)
    assert report.findings == ()
    assert len(report.report_hash) == 64


def test_r22_operational_readiness_rejects_inline_object_storage_secret() -> None:
    config = _r22_operational_config()
    object_storage = dict(config["object_storage"])
    object_storage["credentials_ref"] = "secret:inline-token"
    config["object_storage"] = object_storage

    report = r22_operational_readiness(config, production=True)

    assert report.ready is False
    assert any(finding.code == "R22_INLINE_STORAGE_SECRET_FORBIDDEN" for finding in report.findings)


def test_r22_registry_roundtrip(tmp_path: Path) -> None:
    registered = r22_register_artifact(
        r22_empty_registry("project-r22", "tenant-a"),
        artifact_type="architecture-decision",
        artifact_class="governance",
        title="Decision",
        content={"decision": "approve"},
    )
    path = tmp_path / "registry.json"

    registry_hash = r22_write_registry(registered.registry, path)
    loaded = r22_read_registry(path)

    assert loaded is not None
    assert loaded.registry_hash == registry_hash


def test_r22_api_is_exposed_in_openapi() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "/api/v1/r22/artifact-intelligence-contract" in paths
    assert "/api/v1/r22/operational-readiness" in paths
    assert "/api/v1/r22/projects/{project_id}/artifacts" in paths
    assert "/api/v1/r22/projects/{project_id}/evidence-package" in paths
    assert "/api/v1/r22/graph/path" in paths


def test_r22_api_registers_artifact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/api/v1/r22/projects/project-r22/artifacts",
        headers=_headers(),
        json={
            "tenant_id": "tenant-a",
            "artifact_type": "openapi-contract",
            "artifact_class": "implementation",
            "title": "OpenAPI Contract",
            "content": {"openapi": "3.1.0"},
            "manifest_traces": [
                {
                    "source_type": "REQUIREMENT",
                    "source_id": "REQ-API-001",
                    "relationship_type": "SATISFIES",
                }
            ],
            "validations": [{"status": "PASSED"}],
            "approvals": [{"approver_id": "owner"}],
            "persist": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["artifact_version_id"].startswith("artver-")


def test_r22_api_reports_operational_readiness() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/r22/operational-readiness",
        headers=_headers(),
        json={"production": True, "config": _r22_operational_config()},
    )

    assert response.status_code == 200
    payload = response.json()["report"]
    assert payload["status"] == "ready"
    assert payload["ready"] is True
