from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from ai_enterprise.domain.hashing import hash_json

BK_R11_VERSION = "evidence-audit-engine-1.0"
DETERMINISTIC_AUDIT_TIMESTAMP = "1970-01-01T00:00:00Z"

EVIDENCE_TYPES: tuple[str, ...] = (
    "test-report",
    "scan-report",
    "review-record",
    "approval-record",
    "runtime-log",
    "deployment-proof",
    "configuration-snapshot",
    "traceability-export",
    "audit-export",
    "policy-decision",
    "waiver-record",
)

ARCHIVE_BACKENDS: tuple[str, ...] = (
    "filesystem",
    "s3",
    "gcs",
    "azure_blob",
    "minio",
    "custom",
)

SIGNATURE_PROVIDERS: tuple[str, ...] = (
    "disabled",
    "mock",
    "kms",
    "custom",
)

SENSITIVE_KEYS: tuple[str, ...] = (
    "api_key",
    "apikey",
    "authorization",
    "client_secret",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
)


class BKR11ActorReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    actor_type: str
    actor_id: str
    role: str


class BKR11SubjectReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    subject_type: str
    subject_id: str
    relationship: str = "supports"


class BKR11EvidenceArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    evidence_type: str
    source_system: str
    uri: str
    content_hash: str
    captured_at: str
    captured_by: BKR11ActorReference
    subjects: tuple[BKR11SubjectReference, ...]
    classification: str
    retention_class: str
    metadata: dict[str, Any]
    artifact_hash: str


class BKR11AuditRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    audit_record_id: str
    stream_id: str
    sequence: int
    previous_hash: str | None
    event_type: str
    occurred_at: str
    actor: BKR11ActorReference
    subject: BKR11SubjectReference
    evidence_ids: tuple[str, ...]
    payload_hash: str
    record_hash: str


class BKR11EvidenceCoverageItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    obligation_id: str
    required_evidence_types: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    status: str
    missing_evidence_types: tuple[str, ...]


class BKR11EvidenceCoverageReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    obligations_total: int
    obligations_satisfied: int
    obligations_blocked: int
    items: tuple[BKR11EvidenceCoverageItem, ...]
    coverage_hash: str


class BKR11AuditIntegrityReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    stream_count: int
    record_count: int
    failures: tuple[dict[str, Any], ...]
    integrity_hash: str


class BKR11EvidencePackage(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_package_id: str
    project_id: str
    package_version: str
    baseline_refs: dict[str, str]
    artifacts: tuple[BKR11EvidenceArtifact, ...]
    audit_records: tuple[BKR11AuditRecord, ...]
    coverage: BKR11EvidenceCoverageReport
    integrity: BKR11AuditIntegrityReport
    acceptance_status: str
    blockers: tuple[str, ...]
    manifest_hash: str


class BKR11ArchiveBackendConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    archive_backend: str = "filesystem"
    archive_uri_ref: str | None = None
    credentials_reference: str | None = None
    encryption_required: bool = False
    kms_key_ref: str | None = None
    deployment_evidence_ref: str | None = None
    connectivity_evidence_ref: str | None = None
    signature_provider: str = "disabled"
    signature_required: bool = False
    signer_key_ref: str | None = None
    mock_mode: bool = True


class BKR11ArchiveBackendReadiness(BaseModel):
    model_config = ConfigDict(frozen=True)

    ready: bool
    environment: str
    checks: dict[str, dict[str, Any]]
    diagnostics: tuple[dict[str, Any], ...]
    config_hash: str


class BKR11PackageSignatureEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    signer_key_ref: str
    algorithm: str
    manifest_hash: str
    archive_hash: str
    status: str
    signature: str | None
    signature_reference: str | None
    signed_at: str
    signature_hash: str


class BKR11ArchivePublication(BaseModel):
    model_config = ConfigDict(frozen=True)

    publication_id: str
    archive_backend: str
    archive_uri: str
    metadata_uri: str
    project_id: str
    evidence_package_id: str
    manifest_hash: str
    archive_hash: str
    signature_hash: str | None
    status: str
    publication_hash: str


class BKR11ArchiveVerificationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    archive_backend: str
    archive_uri: str
    expected_archive_hash: str
    actual_archive_hash: str | None
    metadata_verified: bool
    diagnostics: tuple[dict[str, Any], ...]
    verification_hash: str


def bk_r11_verify_filesystem_publication(
    publication: BKR11ArchivePublication,
) -> BKR11ArchiveVerificationReport:
    diagnostics: list[dict[str, Any]] = []
    archive_path = Path(publication.archive_uri)
    metadata_path = Path(publication.metadata_uri)
    actual_hash: str | None = None
    if not archive_path.exists():
        diagnostics.append(_diag("fatal", "BK-R11-ARCHIVE-MISSING", "archive_uri"))
    elif not archive_path.is_file():
        diagnostics.append(_diag("fatal", "BK-R11-ARCHIVE-NOT-FILE", "archive_uri"))
    else:
        import hashlib

        actual_hash = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        if actual_hash != publication.archive_hash:
            diagnostics.append(_diag("fatal", "BK-R11-ARCHIVE-HASH-MISMATCH", "archive_hash"))
    metadata_verified = False
    if not metadata_path.exists():
        diagnostics.append(_diag("warning", "BK-R11-PUBLICATION-METADATA-MISSING", "metadata_uri"))
    else:
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata_verified = (
                metadata.get("publication", {}).get("publication_hash")
                == publication.publication_hash
            )
            if not metadata_verified:
                diagnostics.append(
                    _diag("fatal", "BK-R11-PUBLICATION-METADATA-MISMATCH", "metadata_uri")
                )
        except json.JSONDecodeError:
            diagnostics.append(
                _diag("fatal", "BK-R11-PUBLICATION-METADATA-INVALID", "metadata_uri")
            )
    status = (
        "verified"
        if not any(item["severity"] == "fatal" for item in diagnostics)
        else "failed"
    )
    payload = {
        "status": status,
        "archive_backend": publication.archive_backend,
        "archive_uri": publication.archive_uri,
        "expected_archive_hash": publication.archive_hash,
        "actual_archive_hash": actual_hash,
        "metadata_verified": metadata_verified,
        "diagnostics": diagnostics,
    }
    return BKR11ArchiveVerificationReport(**payload, verification_hash=hash_json(payload))


def bk_r11_create_evidence_artifact(
    *,
    evidence_id: str,
    evidence_type: str,
    source_system: str,
    uri: str,
    content_hash: str,
    captured_by: dict[str, str] | BKR11ActorReference,
    subjects: Iterable[dict[str, str] | BKR11SubjectReference],
    captured_at: str = DETERMINISTIC_AUDIT_TIMESTAMP,
    classification: str = "internal",
    retention_class: str = "project-lifecycle",
    metadata: dict[str, Any] | None = None,
) -> BKR11EvidenceArtifact:
    if evidence_type not in EVIDENCE_TYPES:
        raise ValueError(f"unsupported evidence type: {evidence_type}")
    if not uri.strip():
        raise ValueError("evidence uri is required")
    if not content_hash.strip():
        raise ValueError("evidence content hash is required")
    clean_metadata = _sanitize_metadata(metadata or {})
    artifact_without_hash = {
        "evidence_id": evidence_id,
        "evidence_type": evidence_type,
        "source_system": source_system,
        "uri": uri,
        "content_hash": content_hash,
        "captured_at": captured_at,
        "captured_by": _actor(captured_by).model_dump(mode="json"),
        "subjects": [_subject(item).model_dump(mode="json") for item in subjects],
        "classification": classification,
        "retention_class": retention_class,
        "metadata": clean_metadata,
    }
    return BKR11EvidenceArtifact(
        **artifact_without_hash,
        artifact_hash=hash_json(artifact_without_hash),
    )


def bk_r11_append_audit_record(
    existing_records: Iterable[BKR11AuditRecord],
    *,
    stream_id: str,
    event_type: str,
    actor: dict[str, str] | BKR11ActorReference,
    subject: dict[str, str] | BKR11SubjectReference,
    evidence_ids: Iterable[str],
    payload: dict[str, Any],
    occurred_at: str = DETERMINISTIC_AUDIT_TIMESTAMP,
) -> BKR11AuditRecord:
    records = sorted(existing_records, key=lambda item: item.sequence)
    previous = records[-1] if records else None
    sequence = 1 if previous is None else previous.sequence + 1
    previous_hash = None if previous is None else previous.record_hash
    clean_payload = _sanitize_metadata(payload)
    evidence_tuple = tuple(sorted(set(evidence_ids)))
    if not evidence_tuple:
        raise ValueError("audit record must reference at least one evidence item")
    payload_hash = hash_json(clean_payload)
    record_without_hash = {
        "audit_record_id": f"{stream_id}:{sequence}",
        "stream_id": stream_id,
        "sequence": sequence,
        "previous_hash": previous_hash,
        "event_type": event_type,
        "occurred_at": occurred_at,
        "actor": _actor(actor).model_dump(mode="json"),
        "subject": _subject(subject).model_dump(mode="json"),
        "evidence_ids": list(evidence_tuple),
        "payload_hash": payload_hash,
    }
    return BKR11AuditRecord(
        **record_without_hash,
        record_hash=hash_json(record_without_hash),
    )


def bk_r11_build_evidence_package(
    *,
    evidence_package_id: str,
    project_id: str,
    baseline_refs: dict[str, str],
    artifacts: Iterable[BKR11EvidenceArtifact],
    audit_records: Iterable[BKR11AuditRecord],
    required_evidence_by_obligation: dict[str, tuple[str, ...]],
    package_version: str = BK_R11_VERSION,
) -> BKR11EvidencePackage:
    artifact_tuple = tuple(sorted(artifacts, key=lambda item: item.evidence_id))
    record_tuple = tuple(sorted(audit_records, key=lambda item: (item.stream_id, item.sequence)))
    evidence_by_id = {item.evidence_id: item for item in artifact_tuple}
    blockers = list(_package_reference_blockers(evidence_by_id, record_tuple))
    integrity = bk_r11_verify_audit_integrity(record_tuple)
    if integrity.status != "verified":
        blockers.append("audit_integrity_not_verified")
    coverage = bk_r11_assess_evidence_coverage(
        artifact_tuple,
        required_evidence_by_obligation=required_evidence_by_obligation,
    )
    if coverage.status != "satisfied":
        blockers.append("evidence_coverage_incomplete")
    if _contains_sensitive_material([item.metadata for item in artifact_tuple]):
        blockers.append("sensitive_metadata_present")
    acceptance_status = "accepted" if not blockers else "blocked"
    package_without_hash = {
        "evidence_package_id": evidence_package_id,
        "project_id": project_id,
        "package_version": package_version,
        "baseline_refs": dict(sorted(baseline_refs.items())),
        "artifacts": [item.model_dump(mode="json") for item in artifact_tuple],
        "audit_records": [item.model_dump(mode="json") for item in record_tuple],
        "coverage": coverage.model_dump(mode="json"),
        "integrity": integrity.model_dump(mode="json"),
        "acceptance_status": acceptance_status,
        "blockers": tuple(sorted(set(blockers))),
    }
    return BKR11EvidencePackage(
        **package_without_hash,
        manifest_hash=hash_json(package_without_hash),
    )


def bk_r11_package_export_files(package: BKR11EvidencePackage) -> dict[str, Any]:
    return {
        "manifest.json": package.model_dump(mode="json"),
        "artifacts.json": [item.model_dump(mode="json") for item in package.artifacts],
        "audit-records.json": [item.model_dump(mode="json") for item in package.audit_records],
        "coverage.json": package.coverage.model_dump(mode="json"),
        "integrity.json": package.integrity.model_dump(mode="json"),
    }


def bk_r11_archive_backend_readiness(
    config: dict[str, Any] | BKR11ArchiveBackendConfig,
    *,
    environment: str = "development",
) -> BKR11ArchiveBackendReadiness:
    model = (
        config
        if isinstance(config, BKR11ArchiveBackendConfig)
        else BKR11ArchiveBackendConfig(**config)
    )
    normalized_env = environment.lower()
    production_like = normalized_env in {"production", "staging"}
    external_archive = model.archive_backend != "filesystem"
    diagnostics: list[dict[str, Any]] = []
    checks: dict[str, dict[str, Any]] = {}

    checks["archive_backend"] = {
        "ok": model.archive_backend in ARCHIVE_BACKENDS,
        "required": True,
        "value": model.archive_backend,
    }
    if not checks["archive_backend"]["ok"]:
        diagnostics.append(_diag("fatal", "BK-R11-ARCHIVE-BACKEND-UNKNOWN", "archive_backend"))

    checks["archive_uri"] = {
        "ok": bool(model.archive_uri_ref) or not (external_archive or production_like),
        "required": external_archive or production_like,
        "value": model.archive_uri_ref,
    }
    if not checks["archive_uri"]["ok"]:
        diagnostics.append(_diag("fatal", "BK-R11-ARCHIVE-URI-MISSING", "archive_uri_ref"))

    checks["credentials"] = {
        "ok": bool(model.credentials_reference) or not external_archive,
        "required": external_archive,
        "value": model.credentials_reference,
    }
    if not checks["credentials"]["ok"]:
        diagnostics.append(_diag("fatal", "BK-R11-ARCHIVE-CREDENTIALS-MISSING", "credentials"))

    checks["deployment_evidence"] = {
        "ok": bool(model.deployment_evidence_ref) or not (external_archive and production_like),
        "required": external_archive and production_like,
        "value": model.deployment_evidence_ref,
    }
    if not checks["deployment_evidence"]["ok"]:
        diagnostics.append(
            _diag("fatal", "BK-R11-ARCHIVE-DEPLOYMENT-EVIDENCE-MISSING", "deployment_evidence")
        )

    checks["connectivity_evidence"] = {
        "ok": bool(model.connectivity_evidence_ref) or not (external_archive and production_like),
        "required": external_archive and production_like,
        "value": model.connectivity_evidence_ref,
    }
    if not checks["connectivity_evidence"]["ok"]:
        diagnostics.append(
            _diag("fatal", "BK-R11-ARCHIVE-CONNECTIVITY-EVIDENCE-MISSING", "connectivity_evidence")
        )

    checks["kms"] = {
        "ok": bool(model.kms_key_ref) or not model.encryption_required,
        "required": model.encryption_required,
        "value": model.kms_key_ref,
    }
    if not checks["kms"]["ok"]:
        diagnostics.append(_diag("fatal", "BK-R11-KMS-KEY-MISSING", "kms_key_ref"))

    checks["signature_provider"] = {
        "ok": model.signature_provider in SIGNATURE_PROVIDERS,
        "required": model.signature_required,
        "value": model.signature_provider,
    }
    if not checks["signature_provider"]["ok"]:
        diagnostics.append(
            _diag("fatal", "BK-R11-SIGNATURE-PROVIDER-UNKNOWN", "signature_provider")
        )

    checks["signer_key"] = {
        "ok": bool(model.signer_key_ref)
        or not model.signature_required
        or model.signature_provider == "disabled",
        "required": model.signature_required and model.signature_provider != "disabled",
        "value": model.signer_key_ref,
    }
    if not checks["signer_key"]["ok"]:
        diagnostics.append(_diag("fatal", "BK-R11-SIGNER-KEY-MISSING", "signer_key_ref"))

    checks["production_mock_mode"] = {
        "ok": not production_like
        or not model.mock_mode
        or (not external_archive and model.signature_provider != "mock"),
        "required": production_like,
        "value": model.mock_mode,
    }
    if not checks["production_mock_mode"]["ok"]:
        diagnostics.append(_diag("fatal", "BK-R11-MOCK-MODE-FORBIDDEN", "mock_mode"))

    checks["production_signature"] = {
        "ok": (
            not production_like
            or not model.signature_required
            or model.signature_provider != "mock"
        ),
        "required": production_like and model.signature_required,
        "value": model.signature_provider,
    }
    if not checks["production_signature"]["ok"]:
        diagnostics.append(
            _diag("fatal", "BK-R11-MOCK-SIGNATURE-FORBIDDEN", "signature_provider")
        )

    checks["production_signature_evidence"] = {
        "ok": not production_like
        or not model.signature_required
        or bool(model.deployment_evidence_ref and model.connectivity_evidence_ref),
        "required": production_like and model.signature_required,
        "value": {
            "deployment_evidence_ref": model.deployment_evidence_ref,
            "connectivity_evidence_ref": model.connectivity_evidence_ref,
        },
    }
    if not checks["production_signature_evidence"]["ok"]:
        diagnostics.append(
            _diag("fatal", "BK-R11-SIGNATURE-EVIDENCE-MISSING", "signature_evidence")
        )

    ready = not any(item["severity"] == "fatal" for item in diagnostics)
    payload = {
        "ready": ready,
        "environment": normalized_env,
        "checks": checks,
        "diagnostics": diagnostics,
        "backend_config": model.model_dump(mode="json"),
    }
    return BKR11ArchiveBackendReadiness(
        ready=ready,
        environment=normalized_env,
        checks=checks,
        diagnostics=tuple(diagnostics),
        config_hash=hash_json(payload),
    )


def bk_r11_prepare_package_signature(
    package: BKR11EvidencePackage,
    *,
    archive_hash: str,
    config: dict[str, Any] | BKR11ArchiveBackendConfig,
    environment: str = "development",
) -> BKR11PackageSignatureEnvelope | None:
    model = (
        config
        if isinstance(config, BKR11ArchiveBackendConfig)
        else BKR11ArchiveBackendConfig(**config)
    )
    if not model.signature_required and model.signature_provider == "disabled":
        return None
    readiness = bk_r11_archive_backend_readiness(model, environment=environment)
    if not readiness.ready:
        raise ValueError("BK/R11 archive backend is not ready for signing")
    if model.signature_provider == "disabled":
        raise ValueError("BK/R11 signature is required but signature provider is disabled")
    if not model.signer_key_ref:
        raise ValueError("BK/R11 signer key reference is required")

    unsigned = {
        "provider": model.signature_provider,
        "signer_key_ref": model.signer_key_ref,
        "algorithm": "sha256-reference-signature-v1",
        "manifest_hash": package.manifest_hash,
        "archive_hash": archive_hash,
        "signed_at": DETERMINISTIC_AUDIT_TIMESTAMP,
    }
    if model.signature_provider == "mock":
        status = "signed"
        signature = hash_json({**unsigned, "mode": "mock"})
        signature_reference = None
    else:
        status = "external_signature_required"
        signature = None
        signature_reference = f"{model.signature_provider}://sign/{hash_json(unsigned)}"
    payload = {
        **unsigned,
        "status": status,
        "signature": signature,
        "signature_reference": signature_reference,
    }
    return BKR11PackageSignatureEnvelope(**payload, signature_hash=hash_json(payload))


def bk_r11_publish_filesystem_archive(
    package: BKR11EvidencePackage,
    *,
    archive_payload: bytes,
    archive_hash: str,
    managed_root: Path,
    signature: BKR11PackageSignatureEnvelope | None = None,
) -> BKR11ArchivePublication:
    root = managed_root.resolve()
    if root.is_symlink():
        raise ValueError("BK/R11 archive root cannot be a symbolic link")
    root.mkdir(parents=True, exist_ok=True)
    safe_project = _safe_path_token(package.project_id)
    safe_package = _safe_path_token(package.evidence_package_id)
    target_root = (root / safe_project / safe_package).resolve()
    if root != target_root and root not in target_root.parents:
        raise ValueError("BK/R11 archive target escapes managed root")
    target_root.mkdir(parents=True, exist_ok=True)
    archive_path = (target_root / f"{package.manifest_hash}.tar.gz").resolve()
    metadata_path = (target_root / f"{package.manifest_hash}.publication.json").resolve()
    if target_root not in archive_path.parents or target_root not in metadata_path.parents:
        raise ValueError("BK/R11 archive file escapes package root")
    archive_path.write_bytes(archive_payload)
    publication_without_hash = {
        "publication_id": f"bk-r11-pub:{package.evidence_package_id}:{archive_hash}",
        "archive_backend": "filesystem",
        "archive_uri": str(archive_path),
        "metadata_uri": str(metadata_path),
        "project_id": package.project_id,
        "evidence_package_id": package.evidence_package_id,
        "manifest_hash": package.manifest_hash,
        "archive_hash": archive_hash,
        "signature_hash": signature.signature_hash if signature else None,
        "status": "published",
    }
    publication = BKR11ArchivePublication(
        **publication_without_hash,
        publication_hash=hash_json(publication_without_hash),
    )
    metadata_path.write_text(
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
    return publication


def bk_r11_create_archive_publication_record(
    package: BKR11EvidencePackage,
    *,
    archive_backend: str,
    archive_uri: str,
    metadata_uri: str,
    archive_hash: str,
    signature: BKR11PackageSignatureEnvelope | None = None,
    status: str = "published",
) -> BKR11ArchivePublication:
    publication_without_hash = {
        "publication_id": f"bk-r11-pub:{package.evidence_package_id}:{archive_hash}",
        "archive_backend": archive_backend,
        "archive_uri": archive_uri,
        "metadata_uri": metadata_uri,
        "project_id": package.project_id,
        "evidence_package_id": package.evidence_package_id,
        "manifest_hash": package.manifest_hash,
        "archive_hash": archive_hash,
        "signature_hash": signature.signature_hash if signature else None,
        "status": status,
    }
    return BKR11ArchivePublication(
        **publication_without_hash,
        publication_hash=hash_json(publication_without_hash),
    )


def bk_r11_assess_evidence_coverage(
    artifacts: Iterable[BKR11EvidenceArtifact],
    *,
    required_evidence_by_obligation: dict[str, tuple[str, ...]],
) -> BKR11EvidenceCoverageReport:
    artifact_tuple = tuple(artifacts)
    items: list[BKR11EvidenceCoverageItem] = []
    for obligation_id, required_types in sorted(required_evidence_by_obligation.items()):
        matching = tuple(
            item
            for item in artifact_tuple
            if any(
                subject.subject_type == "verification_obligation"
                and subject.subject_id == obligation_id
                for subject in item.subjects
            )
        )
        present_types = {item.evidence_type for item in matching}
        missing = tuple(item for item in required_types if item not in present_types)
        items.append(
            BKR11EvidenceCoverageItem(
                obligation_id=obligation_id,
                required_evidence_types=required_types,
                evidence_ids=tuple(sorted(item.evidence_id for item in matching)),
                status="satisfied" if not missing else "blocked",
                missing_evidence_types=missing,
            )
        )
    status = "satisfied" if all(item.status == "satisfied" for item in items) else "blocked"
    coverage_without_hash = {
        "status": status,
        "obligations_total": len(items),
        "obligations_satisfied": sum(1 for item in items if item.status == "satisfied"),
        "obligations_blocked": sum(1 for item in items if item.status != "satisfied"),
        "items": [item.model_dump(mode="json") for item in items],
    }
    return BKR11EvidenceCoverageReport(
        **coverage_without_hash,
        coverage_hash=hash_json(coverage_without_hash),
    )


def bk_r11_verify_audit_integrity(
    audit_records: Iterable[BKR11AuditRecord],
) -> BKR11AuditIntegrityReport:
    records_by_stream: dict[str, list[BKR11AuditRecord]] = {}
    for record in audit_records:
        records_by_stream.setdefault(record.stream_id, []).append(record)
    failures: list[dict[str, Any]] = []
    for stream_id, records in sorted(records_by_stream.items()):
        previous_hash: str | None = None
        for expected_sequence, record in enumerate(
            sorted(records, key=lambda item: item.sequence),
            start=1,
        ):
            if record.sequence != expected_sequence:
                failures.append(
                    {
                        "stream_id": stream_id,
                        "sequence": record.sequence,
                        "reason": "sequence_gap",
                        "expected_sequence": expected_sequence,
                    }
                )
            if record.previous_hash != previous_hash:
                failures.append(
                    {
                        "stream_id": stream_id,
                        "sequence": record.sequence,
                        "reason": "previous_hash_mismatch",
                        "expected_previous_hash": previous_hash,
                        "actual_previous_hash": record.previous_hash,
                    }
                )
            expected_hash = hash_json(
                {
                    "audit_record_id": record.audit_record_id,
                    "stream_id": record.stream_id,
                    "sequence": record.sequence,
                    "previous_hash": record.previous_hash,
                    "event_type": record.event_type,
                    "occurred_at": record.occurred_at,
                    "actor": record.actor.model_dump(mode="json"),
                    "subject": record.subject.model_dump(mode="json"),
                    "evidence_ids": list(record.evidence_ids),
                    "payload_hash": record.payload_hash,
                }
            )
            if expected_hash != record.record_hash:
                failures.append(
                    {
                        "stream_id": stream_id,
                        "sequence": record.sequence,
                        "reason": "record_hash_mismatch",
                        "expected_hash": expected_hash,
                        "actual_hash": record.record_hash,
                    }
                )
            previous_hash = record.record_hash
    integrity_without_hash = {
        "status": "failed" if failures else "verified",
        "stream_count": len(records_by_stream),
        "record_count": sum(len(records) for records in records_by_stream.values()),
        "failures": failures,
    }
    return BKR11AuditIntegrityReport(
        **integrity_without_hash,
        integrity_hash=hash_json(integrity_without_hash),
    )


def _package_reference_blockers(
    evidence_by_id: dict[str, BKR11EvidenceArtifact],
    records: tuple[BKR11AuditRecord, ...],
) -> Iterable[str]:
    for record in records:
        for evidence_id in record.evidence_ids:
            if evidence_id not in evidence_by_id:
                yield (
                    "audit_record_references_missing_evidence:"
                    f"{record.audit_record_id}:{evidence_id}"
                )


def _actor(value: dict[str, str] | BKR11ActorReference) -> BKR11ActorReference:
    return value if isinstance(value, BKR11ActorReference) else BKR11ActorReference(**value)


def _subject(value: dict[str, str] | BKR11SubjectReference) -> BKR11SubjectReference:
    return value if isinstance(value, BKR11SubjectReference) else BKR11SubjectReference(**value)


def _sanitize_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            if _sensitive_key(str(key)):
                clean[str(key)] = "<redacted>"
            else:
                clean[str(key)] = _sanitize_metadata(item)
        return clean
    if isinstance(value, list | tuple):
        return [_sanitize_metadata(item) for item in value]
    return value


def _contains_sensitive_material(values: Iterable[Any]) -> bool:
    return any(_walk_contains_sensitive(value) for value in values)


def _walk_contains_sensitive(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            _sensitive_key(str(key)) and item != "<redacted>" or _walk_contains_sensitive(item)
            for key, item in value.items()
        )
    if isinstance(value, list | tuple):
        return any(_walk_contains_sensitive(item) for item in value)
    return False


def _sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(token in lowered for token in SENSITIVE_KEYS)


def _diag(severity: str, code: str, path: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "path": path}


def _safe_path_token(value: str) -> str:
    safe = value.replace("/", "_").replace("\\", "_").replace("..", "_").strip()
    if not safe:
        raise ValueError("BK/R11 archive path token cannot be empty")
    return safe
