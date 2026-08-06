import pytest
from fastapi.testclient import TestClient

from ai_enterprise.api.routes import bk_r11_evidence_audit as bk_r11_routes
from ai_enterprise.application.bk_r11_evidence_audit_runtime import (
    BK_R11_VERSION,
    BKR11AuditRecord,
    bk_r11_append_audit_record,
    bk_r11_archive_backend_readiness,
    bk_r11_build_evidence_package,
    bk_r11_create_evidence_artifact,
    bk_r11_package_export_files,
    bk_r11_prepare_package_signature,
    bk_r11_publish_filesystem_archive,
    bk_r11_verify_audit_integrity,
    bk_r11_verify_filesystem_publication,
)
from ai_enterprise.infrastructure.audit.audit_exporter import AuditExporter
from ai_enterprise.main import app


def _actor(role: str = "auditor") -> dict[str, str]:
    return {"actor_type": "human", "actor_id": f"{role}-1", "role": role}


def _subject(obligation_id: str = "obl-req-api-001") -> dict[str, str]:
    return {
        "subject_type": "verification_obligation",
        "subject_id": obligation_id,
        "relationship": "satisfies",
    }


def _artifact():
    return bk_r11_create_evidence_artifact(
        evidence_id="ev-test-report-001",
        evidence_type="test-report",
        source_system="ci",
        uri="evidence://ci/run/123/report.json",
        content_hash="sha256-test-report",
        captured_by=_actor("verification-runner"),
        subjects=(_subject(),),
        metadata={"tool": "pytest", "token": "must-not-leak"},
    )


def test_bk_r11_evidence_artifact_is_hashed_and_redacts_sensitive_metadata() -> None:
    artifact = _artifact()

    assert artifact.evidence_type == "test-report"
    assert artifact.metadata["token"] == "<redacted>"
    assert len(artifact.artifact_hash) == 64


def test_bk_r11_audit_records_form_verifiable_hash_chain() -> None:
    first = bk_r11_append_audit_record(
        (),
        stream_id="project:project-001",
        event_type="EvidenceCaptured",
        actor=_actor(),
        subject=_subject(),
        evidence_ids=("ev-test-report-001",),
        payload={"result": "passed"},
    )
    second = bk_r11_append_audit_record(
        (first,),
        stream_id="project:project-001",
        event_type="EvidenceReviewed",
        actor=_actor("audit-reviewer"),
        subject=_subject(),
        evidence_ids=("ev-test-report-001",),
        payload={"review": "accepted"},
    )

    report = bk_r11_verify_audit_integrity((first, second))

    assert report.status == "verified"
    assert second.previous_hash == first.record_hash
    assert report.record_count == 2


def test_bk_r11_integrity_fails_on_hash_chain_tamper() -> None:
    first = bk_r11_append_audit_record(
        (),
        stream_id="project:project-001",
        event_type="EvidenceCaptured",
        actor=_actor(),
        subject=_subject(),
        evidence_ids=("ev-test-report-001",),
        payload={"result": "passed"},
    )
    tampered = first.model_copy(update={"record_hash": "0" * 64})

    report = bk_r11_verify_audit_integrity((tampered,))

    assert report.status == "failed"
    assert any(item["reason"] == "record_hash_mismatch" for item in report.failures)


def test_bk_r11_package_accepts_only_complete_covered_verified_evidence() -> None:
    artifact = _artifact()
    record = bk_r11_append_audit_record(
        (),
        stream_id="project:project-001",
        event_type="EvidenceCaptured",
        actor=_actor(),
        subject=_subject(),
        evidence_ids=(artifact.evidence_id,),
        payload={"result": "passed"},
    )

    package = bk_r11_build_evidence_package(
        evidence_package_id="pkg-r11-001",
        project_id="project-001",
        baseline_refs={"requirements": "req-baseline-001", "verification": "campaign-001"},
        artifacts=(artifact,),
        audit_records=(record,),
        required_evidence_by_obligation={"obl-req-api-001": ("test-report",)},
    )

    assert package.package_version == BK_R11_VERSION
    assert package.acceptance_status == "accepted"
    assert package.blockers == ()
    assert package.coverage.status == "satisfied"
    assert package.integrity.status == "verified"
    assert len(package.manifest_hash) == 64


def test_bk_r11_archive_readiness_fails_closed_for_unconfigured_production_backend() -> None:
    report = bk_r11_archive_backend_readiness(
        {
            "archive_backend": "s3",
            "signature_required": True,
            "signature_provider": "mock",
            "mock_mode": True,
        },
        environment="production",
    )

    assert report.ready is False
    codes = {item["code"] for item in report.diagnostics}
    assert {
        "BK-R11-ARCHIVE-URI-MISSING",
        "BK-R11-ARCHIVE-CREDENTIALS-MISSING",
        "BK-R11-MOCK-MODE-FORBIDDEN",
        "BK-R11-MOCK-SIGNATURE-FORBIDDEN",
    } <= codes


def test_bk_r11_signature_hook_prepares_mock_or_external_signature_without_raw_secret() -> None:
    artifact = _artifact()
    record = bk_r11_append_audit_record(
        (),
        stream_id="project:project-001",
        event_type="EvidenceCaptured",
        actor=_actor(),
        subject=_subject(),
        evidence_ids=(artifact.evidence_id,),
        payload={"result": "passed"},
    )
    package = bk_r11_build_evidence_package(
        evidence_package_id="pkg-r11-001",
        project_id="project-001",
        baseline_refs={"requirements": "req-baseline-001"},
        artifacts=(artifact,),
        audit_records=(record,),
        required_evidence_by_obligation={"obl-req-api-001": ("test-report",)},
    )

    mock_signature = bk_r11_prepare_package_signature(
        package,
        archive_hash="archive-sha256",
        config={
            "signature_required": True,
            "signature_provider": "mock",
            "signer_key_ref": "secret-ref://dev/signing-key",
        },
    )
    assert mock_signature is not None
    assert mock_signature.status == "signed"
    assert mock_signature.signature
    assert "secret-ref://dev/signing-key" == mock_signature.signer_key_ref

    external_signature = bk_r11_prepare_package_signature(
        package,
        archive_hash="archive-sha256",
        config={
            "signature_required": True,
            "signature_provider": "kms",
            "signer_key_ref": "kms://key/releases",
            "encryption_required": True,
            "kms_key_ref": "kms://key/archive",
            "mock_mode": False,
        },
    )
    assert external_signature is not None
    assert external_signature.status == "external_signature_required"
    assert external_signature.signature is None
    assert external_signature.signature_reference is not None


def test_bk_r11_filesystem_archive_publication_writes_archive_and_metadata(tmp_path) -> None:
    artifact = _artifact()
    record = bk_r11_append_audit_record(
        (),
        stream_id="project:project-001",
        event_type="EvidenceCaptured",
        actor=_actor(),
        subject=_subject(),
        evidence_ids=(artifact.evidence_id,),
        payload={"result": "passed"},
    )
    package = bk_r11_build_evidence_package(
        evidence_package_id="pkg-r11-001",
        project_id="project-001",
        baseline_refs={"requirements": "req-baseline-001"},
        artifacts=(artifact,),
        audit_records=(record,),
        required_evidence_by_obligation={"obl-req-api-001": ("test-report",)},
    )
    payload, archive_hash = AuditExporter().build(bk_r11_package_export_files(package))

    publication = bk_r11_publish_filesystem_archive(
        package,
        archive_payload=payload,
        archive_hash=archive_hash,
        managed_root=tmp_path / "archives",
    )

    assert publication.status == "published"
    assert publication.archive_backend == "filesystem"
    archive_path = tmp_path / "archives" / "project-001" / "pkg-r11-001"
    assert (archive_path / f"{package.manifest_hash}.tar.gz").read_bytes() == payload
    metadata = archive_path / f"{package.manifest_hash}.publication.json"
    assert publication.publication_hash in metadata.read_text(encoding="utf-8")
    verification = bk_r11_verify_filesystem_publication(publication)
    assert verification.status == "verified"
    assert verification.actual_archive_hash == archive_hash
    assert verification.metadata_verified is True


def test_bk_r11_package_blocks_missing_evidence_reference_and_coverage_gap() -> None:
    artifact = _artifact()
    record = BKR11AuditRecord(
        **bk_r11_append_audit_record(
            (),
            stream_id="project:project-001",
            event_type="EvidenceCaptured",
            actor=_actor(),
            subject=_subject(),
            evidence_ids=(artifact.evidence_id,),
            payload={"result": "passed"},
        ).model_copy(update={"evidence_ids": ("missing-evidence",)}).model_dump()
    )

    package = bk_r11_build_evidence_package(
        evidence_package_id="pkg-r11-001",
        project_id="project-001",
        baseline_refs={"requirements": "req-baseline-001"},
        artifacts=(artifact,),
        audit_records=(record,),
        required_evidence_by_obligation={
            "obl-req-api-001": ("test-report", "scan-report"),
        },
    )

    assert package.acceptance_status == "blocked"
    assert "evidence_coverage_incomplete" in package.blockers
    assert any(
        item.startswith("audit_record_references_missing_evidence")
        for item in package.blockers
    )


def test_bk_r11_api_builds_evidence_package() -> None:
    client = TestClient(app)
    headers = {
        "X-Actor-ID": "local-dashboard-admin",
        "X-Actor-Type": "human",
        "X-Actor-Role": "platform-admin",
    }
    artifact = client.post(
        "/api/v1/bk/r11-evidence-audit/artifacts",
        headers=headers,
        json={
            "evidence_id": "ev-test-report-001",
            "evidence_type": "test-report",
            "source_system": "ci",
            "uri": "evidence://ci/run/123/report.json",
            "content_hash": "sha256-test-report",
            "captured_by": _actor("verification-runner"),
            "subjects": [_subject()],
            "metadata": {"token": "must-not-leak"},
        },
    )
    assert artifact.status_code == 200
    artifact_record = artifact.json()["record"]
    assert artifact_record["metadata"]["token"] == "<redacted>"

    audit_record = client.post(
        "/api/v1/bk/r11-evidence-audit/audit-records",
        headers=headers,
        json={
            "stream_id": "project:project-001",
            "event_type": "EvidenceCaptured",
            "actor": _actor(),
            "subject": _subject(),
            "evidence_ids": ["ev-test-report-001"],
            "payload": {"result": "passed"},
        },
    )
    assert audit_record.status_code == 200

    package = client.post(
        "/api/v1/bk/r11-evidence-audit/packages",
        headers=headers,
        json={
            "evidence_package_id": "pkg-r11-001",
            "project_id": "project-001",
            "baseline_refs": {"requirements": "req-baseline-001"},
            "artifacts": [artifact_record],
            "audit_records": [audit_record.json()["record"]],
            "required_evidence_by_obligation": {"obl-req-api-001": ["test-report"]},
        },
    )

    assert package.status_code == 200
    assert package.json()["record"]["acceptance_status"] == "accepted"

    archive = client.post(
        "/api/v1/bk/r11-evidence-audit/packages/export",
        headers=headers,
        json={
            "evidence_package_id": "pkg-r11-001",
            "project_id": "project-001",
            "baseline_refs": {"requirements": "req-baseline-001"},
            "artifacts": [artifact_record],
            "audit_records": [audit_record.json()["record"]],
            "required_evidence_by_obligation": {"obl-req-api-001": ["test-report"]},
        },
    )
    assert archive.status_code == 200
    assert archive.headers["X-BK-R11-Manifest-SHA256"] == package.json()["record"]["manifest_hash"]
    assert archive.headers["X-BK-R11-Archive-SHA256"]

    readiness = client.post(
        "/api/v1/bk/r11-evidence-audit/archive-readiness",
        headers=headers,
        json={
            "environment": "development",
            "backend_config": {
                "signature_required": True,
                "signature_provider": "mock",
                "signer_key_ref": "secret-ref://dev/signing-key",
            },
        },
    )
    assert readiness.status_code == 200
    assert readiness.json()["record"]["ready"] is True

    signed_archive = client.post(
        "/api/v1/bk/r11-evidence-audit/packages/export-signed",
        headers=headers,
        json={
            "environment": "development",
            "backend_config": {
                "signature_required": True,
                "signature_provider": "mock",
                "signer_key_ref": "secret-ref://dev/signing-key",
            },
            "evidence_package_id": "pkg-r11-001",
            "project_id": "project-001",
            "baseline_refs": {"requirements": "req-baseline-001"},
            "artifacts": [artifact_record],
            "audit_records": [audit_record.json()["record"]],
            "required_evidence_by_obligation": {"obl-req-api-001": ["test-report"]},
        },
    )
    assert signed_archive.status_code == 200
    assert signed_archive.headers["X-BK-R11-Signature-Status"] == "signed"
    assert signed_archive.headers["X-BK-R11-Signature-SHA256"]


def test_bk_r11_api_exposes_publication_query_endpoints() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "/api/v1/bk/r11-evidence-audit/projects/{project_id}/archive-publications" in paths
    assert "/api/v1/bk/r11-evidence-audit/projects/{project_id}/archive-verifications" in paths
    assert "/api/v1/bk/r11-evidence-audit/projects/{project_id}/archive-summary" in paths


def test_bk_r11_api_publishes_filesystem_archive(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Settings:
        bk_r11_archive_backend = "filesystem"
        bk_r11_archive_filesystem_root = tmp_path / "bk-r11-archives"
        bk_r11_archive_uri_ref = None
        bk_r11_archive_credentials_ref = None
        bk_r11_archive_encryption_required = False
        bk_r11_archive_kms_key_ref = None
        bk_r11_archive_deployment_evidence_ref = None
        bk_r11_archive_connectivity_evidence_ref = None
        bk_r11_signature_provider = "mock"
        bk_r11_signature_required = True
        bk_r11_signer_key_ref = "secret-ref://dev/signing-key"
        bk_r11_mock_backends_enabled = True

    monkeypatch.setattr(bk_r11_routes, "get_settings", lambda: _Settings())
    client = TestClient(app)
    headers = {
        "X-Actor-ID": "local-dashboard-admin",
        "X-Actor-Type": "human",
        "X-Actor-Role": "platform-admin",
    }
    artifact = _artifact().model_dump(mode="json")
    audit_record = bk_r11_append_audit_record(
        (),
        stream_id="project:project-001",
        event_type="EvidenceCaptured",
        actor=_actor(),
        subject=_subject(),
        evidence_ids=("ev-test-report-001",),
        payload={"result": "passed"},
    ).model_dump(mode="json")

    published = client.post(
        "/api/v1/bk/r11-evidence-audit/packages/publish-archive",
        headers=headers,
        json={
            "environment": "development",
            "sign_archive": True,
            "evidence_package_id": "pkg-r11-001",
            "project_id": "project-001",
            "baseline_refs": {"requirements": "req-baseline-001"},
            "artifacts": [artifact],
            "audit_records": [audit_record],
            "required_evidence_by_obligation": {"obl-req-api-001": ["test-report"]},
        },
    )

    assert published.status_code == 200
    record = published.json()["record"]
    assert record["status"] == "published"
    assert (tmp_path / "bk-r11-archives" / "project-001" / "pkg-r11-001").exists()

    verified = client.post(
        "/api/v1/bk/r11-evidence-audit/packages/verify-publication",
        headers=headers,
        json={"publication": record},
    )
    assert verified.status_code == 200
    assert verified.json()["record"]["status"] == "verified"


def test_bk_r11_api_publishes_s3_archive_with_command_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []

    class _Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(bk_r11_routes.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        bk_r11_routes.subprocess,
        "run",
        lambda command, **_kwargs: commands.append(tuple(command)) or _Completed(),
    )
    client = TestClient(app)
    headers = {
        "X-Actor-ID": "local-dashboard-admin",
        "X-Actor-Type": "human",
        "X-Actor-Role": "platform-admin",
    }
    response = client.post(
        "/api/v1/bk/r11-evidence-audit/packages/publish-archive",
        headers=headers,
        json={
            "environment": "development",
            "backend_config": {
                "archive_backend": "s3",
                "archive_uri_ref": "s3://bucket/prefix",
                "credentials_reference": "secret-ref://aws/archive",
                "mock_mode": False,
            },
            "evidence_package_id": "pkg-r11-001",
            "project_id": "project-001",
            "baseline_refs": {"requirements": "req-baseline-001"},
            "artifacts": [_artifact().model_dump(mode="json")],
            "audit_records": [
                bk_r11_append_audit_record(
                    (),
                    stream_id="project:project-001",
                    event_type="EvidenceCaptured",
                    actor=_actor(),
                    subject=_subject(),
                    evidence_ids=("ev-test-report-001",),
                    payload={"result": "passed"},
                ).model_dump(mode="json")
            ],
            "required_evidence_by_obligation": {"obl-req-api-001": ["test-report"]},
        },
    )

    assert response.status_code == 200
    record = response.json()["record"]
    assert record["archive_backend"] == "s3"
    assert record["archive_uri"].startswith("s3://bucket/prefix/project-001/pkg-r11-001/")
    assert len(commands) == 2
    assert commands[0][0:3] == ("aws", "s3", "cp")
    assert commands[1][0:3] == ("aws", "s3", "cp")

    verified = client.post(
        "/api/v1/bk/r11-evidence-audit/packages/verify-publication",
        headers=headers,
        json={
            "publication": record,
            "backend_config": {
                "archive_backend": "s3",
                "archive_uri_ref": "s3://bucket/prefix",
                "credentials_reference": "secret-ref://aws/archive",
                "mock_mode": False,
            },
        },
    )
    assert verified.status_code == 200
    assert verified.json()["record"]["status"] == "remote_reference_verified"
    assert commands[-1][0:3] == ("aws", "s3", "ls")


def test_bk_r11_api_signs_package_with_aws_kms_command_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []

    class _Completed:
        returncode = 0
        stdout = '{"Signature": "base64-kms-signature"}'
        stderr = ""

    monkeypatch.setattr(bk_r11_routes.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        bk_r11_routes.subprocess,
        "run",
        lambda command, **_kwargs: commands.append(tuple(command)) or _Completed(),
    )
    client = TestClient(app)
    headers = {
        "X-Actor-ID": "local-dashboard-admin",
        "X-Actor-Type": "human",
        "X-Actor-Role": "platform-admin",
    }

    response = client.post(
        "/api/v1/bk/r11-evidence-audit/packages/sign",
        headers=headers,
        json={
            "environment": "development",
            "archive_hash": "a" * 64,
            "backend_config": {
                "signature_required": True,
                "signature_provider": "kms",
                "signer_key_ref": "arn:aws:kms:eu-west-1:123:key/release",
                "mock_mode": False,
            },
            "evidence_package_id": "pkg-r11-001",
            "project_id": "project-001",
            "baseline_refs": {"requirements": "req-baseline-001"},
            "artifacts": [_artifact().model_dump(mode="json")],
            "audit_records": [
                bk_r11_append_audit_record(
                    (),
                    stream_id="project:project-001",
                    event_type="EvidenceCaptured",
                    actor=_actor(),
                    subject=_subject(),
                    evidence_ids=("ev-test-report-001",),
                    payload={"result": "passed"},
                ).model_dump(mode="json")
            ],
            "required_evidence_by_obligation": {"obl-req-api-001": ["test-report"]},
        },
    )

    assert response.status_code == 200
    record = response.json()["record"]
    assert record["provider"] == "kms"
    assert record["status"] == "signed"
    assert record["signature"] == "base64-kms-signature"
    assert commands[0][0:3] == ("aws", "kms", "sign")
    assert "--message-type" in commands[0]


def test_bk_r11_api_signs_package_with_custom_command_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []

    class _Completed:
        returncode = 0
        stdout = '{"signature_reference": "custom://signature/pkg-r11-001"}'
        stderr = ""

    monkeypatch.setattr(bk_r11_routes.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        bk_r11_routes.subprocess,
        "run",
        lambda command, **_kwargs: commands.append(tuple(command)) or _Completed(),
    )
    client = TestClient(app)
    headers = {
        "X-Actor-ID": "local-dashboard-admin",
        "X-Actor-Type": "human",
        "X-Actor-Role": "platform-admin",
    }

    response = client.post(
        "/api/v1/bk/r11-evidence-audit/packages/sign",
        headers=headers,
        json={
            "environment": "development",
            "archive_hash": "b" * 64,
            "backend_config": {
                "signature_required": True,
                "signature_provider": "custom",
                "signer_key_ref": "custom://signing-key/release",
                "custom_signing_command": "bk-sign",
                "mock_mode": False,
            },
            "evidence_package_id": "pkg-r11-001",
            "project_id": "project-001",
            "baseline_refs": {"requirements": "req-baseline-001"},
            "artifacts": [_artifact().model_dump(mode="json")],
            "audit_records": [
                bk_r11_append_audit_record(
                    (),
                    stream_id="project:project-001",
                    event_type="EvidenceCaptured",
                    actor=_actor(),
                    subject=_subject(),
                    evidence_ids=("ev-test-report-001",),
                    payload={"result": "passed"},
                ).model_dump(mode="json")
            ],
            "required_evidence_by_obligation": {"obl-req-api-001": ["test-report"]},
        },
    )

    assert response.status_code == 200
    record = response.json()["record"]
    assert record["provider"] == "custom"
    assert record["status"] == "external_signature_recorded"
    assert record["signature_reference"] == "custom://signature/pkg-r11-001"
    assert commands[0][0] == "bk-sign"
    assert "--digest-sha256" in commands[0]


def test_bk_r11_api_fails_closed_when_cloud_publication_cli_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bk_r11_routes.shutil, "which", lambda _name: None)
    client = TestClient(app)
    headers = {
        "X-Actor-ID": "local-dashboard-admin",
        "X-Actor-Type": "human",
        "X-Actor-Role": "platform-admin",
    }
    response = client.post(
        "/api/v1/bk/r11-evidence-audit/packages/publish-archive",
        headers=headers,
        json={
            "environment": "development",
            "backend_config": {
                "archive_backend": "s3",
                "archive_uri_ref": "s3://bucket/prefix",
                "credentials_reference": "secret-ref://aws/archive",
                "mock_mode": False,
            },
            "evidence_package_id": "pkg-r11-001",
            "project_id": "project-001",
            "baseline_refs": {"requirements": "req-baseline-001"},
            "artifacts": [_artifact().model_dump(mode="json")],
            "audit_records": [
                bk_r11_append_audit_record(
                    (),
                    stream_id="project:project-001",
                    event_type="EvidenceCaptured",
                    actor=_actor(),
                    subject=_subject(),
                    evidence_ids=("ev-test-report-001",),
                    payload={"result": "passed"},
                ).model_dump(mode="json")
            ],
            "required_evidence_by_obligation": {"obl-req-api-001": ["test-report"]},
        },
    )

    assert response.status_code == 409
    assert "aws executable is not installed" in response.json()["detail"]
