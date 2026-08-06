from __future__ import annotations

import base64
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from ai_enterprise.api.bk_r11_evidence_audit_schemas import (
    BKR11AppendAuditRecordRequest,
    BKR11ArchiveReadinessRequest,
    BKR11BuildPackageRequest,
    BKR11ContractResponse,
    BKR11CreateEvidenceArtifactRequest,
    BKR11ListResponse,
    BKR11PublishArchiveRequest,
    BKR11RecordResponse,
    BKR11SignedExportRequest,
    BKR11SignPackageRequest,
    BKR11VerifyPublicationRequest,
)
from ai_enterprise.api.dependencies import ActorDependency, SessionDependency
from ai_enterprise.application.bk_r11_evidence_audit_runtime import (
    ARCHIVE_BACKENDS,
    BK_R11_VERSION,
    EVIDENCE_TYPES,
    SIGNATURE_PROVIDERS,
    BKR11ArchivePublication,
    BKR11ArchiveVerificationReport,
    BKR11AuditRecord,
    BKR11EvidenceArtifact,
    BKR11PackageSignatureEnvelope,
    bk_r11_append_audit_record,
    bk_r11_archive_backend_readiness,
    bk_r11_build_evidence_package,
    bk_r11_create_archive_publication_record,
    bk_r11_create_evidence_artifact,
    bk_r11_package_export_files,
    bk_r11_prepare_package_signature,
    bk_r11_publish_filesystem_archive,
    bk_r11_verify_filesystem_publication,
)
from ai_enterprise.application.bk_r11_persistence_service import BKR11PersistenceService
from ai_enterprise.config import get_settings
from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.infrastructure.audit.audit_exporter import AuditExporter
from ai_enterprise.infrastructure.bk_r11.models import (
    BKR11ArchivePublicationModel,
    BKR11ArchiveVerificationModel,
)

router = APIRouter(prefix="/bk/r11-evidence-audit", tags=["bk-r11-evidence-audit"])


@router.get("/contract", response_model=BKR11ContractResponse)
async def contract(actor: ActorDependency) -> BKR11ContractResponse:
    _require_evidence_audit_authority(actor, "read")
    return BKR11ContractResponse(
        version=BK_R11_VERSION,
        evidence_types=list(EVIDENCE_TYPES),
        archive_backends=list(ARCHIVE_BACKENDS),
        signature_providers=list(SIGNATURE_PROVIDERS),
        principles=[
            "durable-evidence-before-acceptance",
            "append-only-audit-chain",
            "coverage-before-verdict",
            "missing-evidence-fails-closed",
            "sensitive-metadata-redaction",
            "manifest-hash-covers-package",
        ],
    )


@router.post("/archive-readiness", response_model=BKR11RecordResponse)
async def archive_readiness(
    request: BKR11ArchiveReadinessRequest,
    actor: ActorDependency,
) -> BKR11RecordResponse:
    _require_evidence_audit_authority(actor, "read")
    report = bk_r11_archive_backend_readiness(
        _archive_backend_config(request.backend_config),
        environment=request.environment,
    )
    return BKR11RecordResponse(record=report.model_dump(mode="json"))


@router.post("/artifacts", response_model=BKR11RecordResponse)
async def create_evidence_artifact(
    request: BKR11CreateEvidenceArtifactRequest,
    actor: ActorDependency,
) -> BKR11RecordResponse:
    _require_evidence_audit_authority(actor, "write")
    try:
        artifact = bk_r11_create_evidence_artifact(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BKR11RecordResponse(record=artifact.model_dump(mode="json"))


@router.post("/audit-records", response_model=BKR11RecordResponse)
async def append_audit_record(
    request: BKR11AppendAuditRecordRequest,
    actor: ActorDependency,
) -> BKR11RecordResponse:
    _require_evidence_audit_authority(actor, "write")
    try:
        existing = tuple(BKR11AuditRecord(**item) for item in request.existing_records)
        record = bk_r11_append_audit_record(
            existing,
            stream_id=request.stream_id,
            event_type=request.event_type,
            actor=request.actor,
            subject=request.subject,
            evidence_ids=request.evidence_ids,
            payload=request.payload,
            occurred_at=request.occurred_at,
        )
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BKR11RecordResponse(record=record.model_dump(mode="json"))


@router.post("/packages", response_model=BKR11RecordResponse)
async def build_evidence_package(
    request: BKR11BuildPackageRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> BKR11RecordResponse:
    _require_evidence_audit_authority(actor, "write")
    package = _build_package_from_request(request)
    if request.persist:
        await _record_package(session, package, actor, package.acceptance_status)
    return BKR11RecordResponse(record=package.model_dump(mode="json"))


@router.post("/packages/export")
async def export_evidence_package(
    request: BKR11BuildPackageRequest,
    actor: ActorDependency,
) -> Response:
    _require_evidence_audit_authority(actor, "read")
    package = _build_package_from_request(request)
    payload, archive_hash = AuditExporter().build(bk_r11_package_export_files(package))
    return Response(
        payload,
        media_type="application/gzip",
        headers={
            "X-BK-R11-Manifest-SHA256": package.manifest_hash,
            "X-BK-R11-Archive-SHA256": archive_hash,
            "Content-Disposition": (
                f'attachment; filename="bk-r11-evidence-{package.evidence_package_id}.tar.gz"'
            ),
        },
    )


@router.post("/packages/export-signed")
async def export_signed_evidence_package(
    request: BKR11SignedExportRequest,
    actor: ActorDependency,
) -> Response:
    _require_evidence_audit_authority(actor, "read")
    package = _build_package_from_request(request)
    payload, archive_hash = AuditExporter().build(bk_r11_package_export_files(package))
    try:
        signature = _prepare_or_execute_signature(
            package,
            archive_hash=archive_hash,
            config=_archive_backend_config(request.backend_config),
            environment=request.environment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    headers = {
        "X-BK-R11-Manifest-SHA256": package.manifest_hash,
        "X-BK-R11-Archive-SHA256": archive_hash,
        "Content-Disposition": (
            f'attachment; filename="bk-r11-evidence-{package.evidence_package_id}.tar.gz"'
        ),
    }
    if signature is not None:
        headers["X-BK-R11-Signature-Status"] = signature.status
        headers["X-BK-R11-Signature-SHA256"] = signature.signature_hash
        if signature.signature_reference:
            headers["X-BK-R11-Signature-Reference"] = signature.signature_reference
    return Response(payload, media_type="application/gzip", headers=headers)


@router.post("/packages/sign", response_model=BKR11RecordResponse)
async def sign_evidence_package(
    request: BKR11SignPackageRequest,
    actor: ActorDependency,
) -> BKR11RecordResponse:
    _require_evidence_audit_authority(actor, "write")
    package = _build_package_from_request(request)
    try:
        signature = _prepare_or_execute_signature(
            package,
            archive_hash=request.archive_hash,
            config=_archive_backend_config(request.backend_config),
            environment=request.environment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if signature is None:
        raise HTTPException(status_code=409, detail="BK/R11 package signature is disabled")
    return BKR11RecordResponse(record=signature.model_dump(mode="json"))


@router.post("/packages/publish-archive", response_model=BKR11RecordResponse)
async def publish_evidence_package_archive(
    request: BKR11PublishArchiveRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> BKR11RecordResponse:
    _require_evidence_audit_authority(actor, "write")
    config = _archive_backend_config(request.backend_config)
    readiness = bk_r11_archive_backend_readiness(config, environment=request.environment)
    if not readiness.ready:
        raise HTTPException(status_code=503, detail=readiness.model_dump(mode="json"))
    package = _build_package_from_request(request)
    payload, archive_hash = AuditExporter().build(bk_r11_package_export_files(package))
    signature = None
    if request.sign_archive:
        try:
            signature = _prepare_or_execute_signature(
                package,
                archive_hash=archive_hash,
                config=config,
                environment=request.environment,
            )
        except ValueError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    publication = _publish_archive_payload(
        config=config,
        package=package,
        payload=payload,
        archive_hash=archive_hash,
        signature=signature,
    )
    if request.persist_publication:
        await _record_publication(session, publication, actor)
    return BKR11RecordResponse(record=publication.model_dump(mode="json"))


@router.post("/packages/verify-publication", response_model=BKR11RecordResponse)
async def verify_archive_publication(
    request: BKR11VerifyPublicationRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> BKR11RecordResponse:
    _require_evidence_audit_authority(actor, "read")
    try:
        publication = BKR11ArchivePublication(**request.publication)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if publication.archive_backend == "filesystem":
        report = bk_r11_verify_filesystem_publication(publication)
        if request.persist_verification:
            await _record_verification(session, report, publication, actor)
        return BKR11RecordResponse(record=report.model_dump(mode="json"))
    report = _verify_remote_publication(
        publication,
        _archive_backend_config(request.backend_config),
    )
    if request.persist_verification:
        report_model = BKR11ArchiveVerificationReport(**report)
        await _record_verification(session, report_model, publication, actor)
    return BKR11RecordResponse(record=report)


@router.get("/projects/{project_id}/archive-publications", response_model=BKR11ListResponse)
async def list_archive_publications(
    project_id: str,
    actor: ActorDependency,
    session: SessionDependency,
    package_id: str | None = None,
    limit: int = 100,
) -> BKR11ListResponse:
    _require_evidence_audit_authority(actor, "read")
    return BKR11ListResponse(
        records=await _list_projection_documents(
            session,
            BKR11ArchivePublicationModel,
            project_id=project_id,
            package_id=package_id,
            limit=limit,
        )
    )


@router.get("/projects/{project_id}/archive-verifications", response_model=BKR11ListResponse)
async def list_archive_verifications(
    project_id: str,
    actor: ActorDependency,
    session: SessionDependency,
    package_id: str | None = None,
    limit: int = 100,
) -> BKR11ListResponse:
    _require_evidence_audit_authority(actor, "read")
    return BKR11ListResponse(
        records=await _list_projection_documents(
            session,
            BKR11ArchiveVerificationModel,
            project_id=project_id,
            package_id=package_id,
            limit=limit,
        )
    )


@router.get("/projects/{project_id}/archive-summary", response_model=BKR11RecordResponse)
async def archive_summary(
    project_id: str,
    actor: ActorDependency,
    session: SessionDependency,
    package_id: str | None = None,
) -> BKR11RecordResponse:
    _require_evidence_audit_authority(actor, "read")
    return BKR11RecordResponse(
        record=await _archive_summary(session, project_id=project_id, package_id=package_id)
    )


def _require_evidence_audit_authority(actor: ActorDependency, action: str) -> None:
    role = getattr(actor, "role", "")
    if role in {"platform-admin", "admin", "owner", "architect", "reviewer", "operator", "auditor"}:
        return
    if action == "read" and role in {"developer", "viewer", "analyst"}:
        return
    raise HTTPException(status_code=403, detail="Actor lacks BK/R11 evidence-audit authority")


async def _record_package(
    session: SessionDependency,
    package,
    actor: ActorDependency,
    action: str,
) -> None:
    try:
        service = BKR11PersistenceService(session)
        await service.record_package(
            package,
            actor_type=actor.actor_type,
            actor_id=actor.subject,
            action=action,
        )
        await service.flush()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"BK/R11 persistence failed for action {action}",
        ) from exc


async def _record_publication(
    session: SessionDependency,
    publication,
    actor: ActorDependency,
) -> None:
    try:
        service = BKR11PersistenceService(session)
        await service.record_publication(
            publication,
            actor_type=actor.actor_type,
            actor_id=actor.subject,
        )
        await service.flush()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="BK/R11 publication persistence failed",
        ) from exc


async def _record_verification(
    session: SessionDependency,
    report,
    publication,
    actor: ActorDependency,
) -> None:
    try:
        service = BKR11PersistenceService(session)
        await service.record_verification(
            report,
            project_key=publication.project_id,
            package_id=publication.evidence_package_id,
            actor_type=actor.actor_type,
            actor_id=actor.subject,
        )
        await service.flush()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="BK/R11 verification persistence failed",
        ) from exc


async def _list_projection_documents(
    session: SessionDependency,
    model,
    *,
    project_id: str,
    package_id: str | None,
    limit: int,
) -> list[dict[str, object]]:
    safe_limit = max(1, min(limit, 500))
    statement = select(model).where(model.project_key == project_id)
    if package_id:
        statement = statement.where(model.package_id == package_id)
    statement = statement.order_by(model.created_at.desc(), model.id.desc()).limit(safe_limit)
    rows = (await session.scalars(statement)).all()
    return [row.document for row in rows]


async def _archive_summary(
    session: SessionDependency,
    *,
    project_id: str,
    package_id: str | None,
) -> dict[str, object]:
    publication_filter = [BKR11ArchivePublicationModel.project_key == project_id]
    verification_filter = [BKR11ArchiveVerificationModel.project_key == project_id]
    if package_id:
        publication_filter.append(BKR11ArchivePublicationModel.package_id == package_id)
        verification_filter.append(BKR11ArchiveVerificationModel.package_id == package_id)
    publication_count = int(
        await session.scalar(
            select(func.count())
            .select_from(BKR11ArchivePublicationModel)
            .where(*publication_filter)
        )
        or 0
    )
    verification_count = int(
        await session.scalar(
            select(func.count())
            .select_from(BKR11ArchiveVerificationModel)
            .where(*verification_filter)
        )
        or 0
    )
    failed_verification_count = int(
        await session.scalar(
            select(func.count())
            .select_from(BKR11ArchiveVerificationModel)
            .where(*verification_filter, BKR11ArchiveVerificationModel.status == "failed")
        )
        or 0
    )
    latest_publication = await session.scalar(
        select(BKR11ArchivePublicationModel)
        .where(*publication_filter)
        .order_by(
            BKR11ArchivePublicationModel.created_at.desc(),
            BKR11ArchivePublicationModel.id.desc(),
        )
        .limit(1)
    )
    latest_verification = await session.scalar(
        select(BKR11ArchiveVerificationModel)
        .where(*verification_filter)
        .order_by(
            BKR11ArchiveVerificationModel.created_at.desc(),
            BKR11ArchiveVerificationModel.id.desc(),
        )
        .limit(1)
    )
    status = "no_publications"
    if publication_count and not verification_count:
        status = "verification_missing"
    elif failed_verification_count:
        status = "verification_failed"
    elif publication_count and verification_count:
        status = "verified"
    return {
        "project_id": project_id,
        "package_id": package_id,
        "status": status,
        "publication_count": publication_count,
        "verification_count": verification_count,
        "failed_verification_count": failed_verification_count,
        "latest_publication": latest_publication.document if latest_publication else None,
        "latest_verification": latest_verification.document if latest_verification else None,
        "summary_hash": hash_json(
            {
                "project_id": project_id,
                "package_id": package_id,
                "status": status,
                "publication_count": publication_count,
                "verification_count": verification_count,
                "failed_verification_count": failed_verification_count,
            }
        ),
    }


def _archive_backend_config(overrides: dict[str, object]) -> dict[str, object]:
    settings = get_settings()
    return {
        "archive_backend": settings.bk_r11_archive_backend,
        "archive_uri_ref": settings.bk_r11_archive_uri_ref,
        "credentials_reference": settings.bk_r11_archive_credentials_ref,
        "encryption_required": settings.bk_r11_archive_encryption_required,
        "kms_key_ref": settings.bk_r11_archive_kms_key_ref,
        "deployment_evidence_ref": settings.bk_r11_archive_deployment_evidence_ref,
        "connectivity_evidence_ref": settings.bk_r11_archive_connectivity_evidence_ref,
        "signature_provider": settings.bk_r11_signature_provider,
        "signature_required": settings.bk_r11_signature_required,
        "signer_key_ref": settings.bk_r11_signer_key_ref,
        "custom_signing_command": getattr(settings, "bk_r11_custom_signing_command", None),
        "mock_mode": settings.bk_r11_mock_backends_enabled,
        **overrides,
    }


def _build_package_from_request(request: BKR11BuildPackageRequest):
    try:
        return bk_r11_build_evidence_package(
            evidence_package_id=request.evidence_package_id,
            project_id=request.project_id,
            baseline_refs=request.baseline_refs,
            artifacts=tuple(BKR11EvidenceArtifact(**item) for item in request.artifacts),
            audit_records=tuple(BKR11AuditRecord(**item) for item in request.audit_records),
            required_evidence_by_obligation=request.required_evidence_by_obligation,
            package_version=request.package_version,
        )
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _publish_archive_payload(
    *,
    config: dict[str, object],
    package,
    payload: bytes,
    archive_hash: str,
    signature,
):
    backend = str(config["archive_backend"])
    if backend == "filesystem":
        return bk_r11_publish_filesystem_archive(
            package,
            archive_payload=payload,
            archive_hash=archive_hash,
            managed_root=get_settings().bk_r11_archive_filesystem_root,
            signature=signature,
        )
    base_uri = str(config.get("archive_uri_ref") or "").rstrip("/")
    archive_uri = _remote_archive_uri(base_uri, package)
    metadata_uri = archive_uri.removesuffix(".tar.gz") + ".publication.json"
    publication = bk_r11_create_archive_publication_record(
        package,
        archive_backend=backend,
        archive_uri=archive_uri,
        metadata_uri=metadata_uri,
        archive_hash=archive_hash,
        signature=signature,
    )
    with tempfile.TemporaryDirectory(prefix="bk-r11-publish-") as temp_dir:
        temp_root = Path(temp_dir)
        archive_file = temp_root / "package.tar.gz"
        metadata_file = temp_root / "publication.json"
        archive_file.write_bytes(payload)
        metadata_file.write_text(
            json.dumps(
                {
                    "publication": publication.model_dump(mode="json"),
                    "signature": signature.model_dump(mode="json") if signature else None,
                },
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        _publish_remote_file(backend, archive_file, archive_uri)
        _publish_remote_file(backend, metadata_file, metadata_uri)
    return publication


def _remote_archive_uri(base_uri: str, package) -> str:
    safe_project = _remote_token(package.project_id)
    safe_package = _remote_token(package.evidence_package_id)
    return f"{base_uri}/{safe_project}/{safe_package}/{package.manifest_hash}.tar.gz"


def _remote_token(value: str) -> str:
    safe = value.replace("/", "_").replace("\\", "_").replace("..", "_").strip()
    if not safe:
        raise HTTPException(status_code=422, detail="BK/R11 archive path token cannot be empty")
    return safe


def _publish_remote_file(backend: str, source: Path, destination: str) -> None:
    if backend == "s3":
        _require_destination(destination, "s3://")
        _run_archive_command(("aws", "s3", "cp", str(source), destination, "--only-show-errors"))
        return
    if backend == "gcs":
        _require_destination(destination, "gs://")
        executable = "gsutil" if shutil.which("gsutil") else "gcloud"
        if executable == "gsutil":
            _run_archive_command(("gsutil", "cp", str(source), destination))
        else:
            _run_archive_command(("gcloud", "storage", "cp", str(source), destination))
        return
    if backend == "azure_blob":
        _require_destination(destination, "azblob://")
        container, blob_name = _azure_destination(destination)
        _run_archive_command(
            (
                "az",
                "storage",
                "blob",
                "upload",
                "--only-show-errors",
                "--overwrite",
                "true",
                "--container-name",
                container,
                "--name",
                blob_name,
                "--file",
                str(source),
            )
        )
        return
    if backend == "minio":
        _run_archive_command(("mc", "cp", str(source), destination))
        return
    raise HTTPException(status_code=501, detail=f"BK/R11 archive backend is unsupported: {backend}")


def _run_archive_command(command: tuple[str, ...]) -> None:
    if shutil.which(command[0]) is None:
        raise HTTPException(status_code=409, detail=f"{command[0]} executable is not installed")
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        output = (completed.stderr or completed.stdout or "archive publication failed").strip()
        raise HTTPException(status_code=502, detail=output[:1000])


def _require_destination(destination: str, prefix: str) -> None:
    if not destination.startswith(prefix):
        raise HTTPException(status_code=422, detail=f"BK/R11 destination must start with {prefix}")


def _azure_destination(destination: str) -> tuple[str, str]:
    without_scheme = destination.removeprefix("azblob://")
    parts = without_scheme.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise HTTPException(
            status_code=422,
            detail="Azure blob destination must use azblob://container/path",
        )
    return parts[0], parts[1]


def _verify_remote_publication(
    publication: BKR11ArchivePublication,
    config: dict[str, object],
) -> dict[str, object]:
    backend = publication.archive_backend
    if backend != config["archive_backend"]:
        raise HTTPException(status_code=422, detail="Publication backend does not match config")
    _probe_remote_file(backend, publication.archive_uri)
    _probe_remote_file(backend, publication.metadata_uri)
    payload = {
        "status": "remote_reference_verified",
        "archive_backend": backend,
        "archive_uri": publication.archive_uri,
        "expected_archive_hash": publication.archive_hash,
        "actual_archive_hash": None,
        "metadata_verified": True,
        "diagnostics": [
            {
                "severity": "info",
                "code": "BK-R11-REMOTE-CONTENT-HASH-NOT-DOWNLOADED",
                "path": "archive_uri",
            }
        ],
    }
    return payload | {"verification_hash": hash_json(payload)}


def _probe_remote_file(backend: str, destination: str) -> None:
    if backend == "s3":
        _require_destination(destination, "s3://")
        _run_archive_command(("aws", "s3", "ls", destination))
        return
    if backend == "gcs":
        _require_destination(destination, "gs://")
        executable = "gsutil" if shutil.which("gsutil") else "gcloud"
        if executable == "gsutil":
            _run_archive_command(("gsutil", "ls", destination))
        else:
            _run_archive_command(("gcloud", "storage", "ls", destination))
        return
    if backend == "azure_blob":
        _require_destination(destination, "azblob://")
        container, blob_name = _azure_destination(destination)
        _run_archive_command(
            (
                "az",
                "storage",
                "blob",
                "exists",
                "--only-show-errors",
                "--container-name",
                container,
                "--name",
                blob_name,
            )
        )
        return
    if backend == "minio":
        _run_archive_command(("mc", "stat", destination))
        return
    raise HTTPException(status_code=501, detail=f"BK/R11 archive backend is unsupported: {backend}")


def _prepare_or_execute_signature(
    package,
    *,
    archive_hash: str,
    config: dict[str, object],
    environment: str,
) -> BKR11PackageSignatureEnvelope | None:
    prepared = bk_r11_prepare_package_signature(
        package,
        archive_hash=archive_hash,
        config=config,
        environment=environment,
    )
    if prepared is None or prepared.provider == "mock":
        return prepared
    digest = hash_json(
        {
            "manifest_hash": package.manifest_hash,
            "archive_hash": archive_hash,
            "signer_key_ref": prepared.signer_key_ref,
        }
    )
    if prepared.provider == "kms":
        signature = _aws_kms_sign_digest(prepared.signer_key_ref, digest)
        return _signed_envelope(prepared, signature=signature, signature_reference=None)
    if prepared.provider == "custom":
        command = str(config.get("custom_signing_command") or "").strip()
        if not command:
            raise ValueError("BK/R11 custom signing command is required")
        signed = _custom_sign_digest(command, prepared.signer_key_ref, digest)
        return _signed_envelope(
            prepared,
            signature=signed.get("signature"),
            signature_reference=signed.get("signature_reference"),
        )
    return prepared


def _aws_kms_sign_digest(key_ref: str, digest_hex: str) -> str:
    if shutil.which("aws") is None:
        raise ValueError("aws executable is not installed")
    completed = subprocess.run(
        (
            "aws",
            "kms",
            "sign",
            "--key-id",
            key_ref,
            "--message",
            base64.b64encode(bytes.fromhex(digest_hex)).decode("ascii"),
            "--message-type",
            "DIGEST",
            "--signing-algorithm",
            "RSASSA_PSS_SHA_256",
            "--output",
            "json",
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError((completed.stderr or completed.stdout or "AWS KMS signing failed")[:1000])
    payload = json.loads(completed.stdout or "{}")
    signature = payload.get("Signature")
    if not isinstance(signature, str) or not signature:
        raise ValueError("AWS KMS signing response did not contain Signature")
    return signature


def _custom_sign_digest(command: str, key_ref: str, digest_hex: str) -> dict[str, str | None]:
    executable = command.split()[0]
    if shutil.which(executable) is None:
        raise ValueError(f"{executable} executable is not installed")
    completed = subprocess.run(
        (*command.split(), "--key-ref", key_ref, "--digest-sha256", digest_hex),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError((completed.stderr or completed.stdout or "custom signing failed")[:1000])
    payload = json.loads(completed.stdout or "{}")
    signature = payload.get("signature")
    signature_reference = payload.get("signature_reference")
    if not signature and not signature_reference:
        raise ValueError("custom signing response must include signature or signature_reference")
    return {
        "signature": signature if isinstance(signature, str) else None,
        "signature_reference": (
            signature_reference if isinstance(signature_reference, str) else None
        ),
    }


def _signed_envelope(
    prepared: BKR11PackageSignatureEnvelope,
    *,
    signature: str | None,
    signature_reference: str | None,
) -> BKR11PackageSignatureEnvelope:
    payload = prepared.model_dump(mode="json") | {
        "status": "signed" if signature else "external_signature_recorded",
        "signature": signature,
        "signature_reference": signature_reference,
    }
    payload.pop("signature_hash", None)
    return BKR11PackageSignatureEnvelope(**payload, signature_hash=hash_json(payload))
