from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.audit.writer import AuditWriter
from ai_enterprise.application.bk_r11_evidence_audit_runtime import (
    BKR11ArchivePublication,
    BKR11ArchiveVerificationReport,
    BKR11EvidencePackage,
)
from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.infrastructure.bk_r11.models import (
    BKR11ArchivePublicationModel,
    BKR11ArchiveVerificationModel,
    BKR11AuditRecordModel,
    BKR11CoverageReportModel,
    BKR11EvidenceArtifactModel,
    BKR11EvidencePackageModel,
    BKR11IntegrityReportModel,
    BKR11PackageEventModel,
)
from ai_enterprise.observability import increment_metric


class BKR11PersistenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_package(
        self,
        package: BKR11EvidencePackage,
        *,
        actor_type: str,
        actor_id: str,
        action: str,
    ) -> None:
        self.session.add(_package_row(package, actor_id))
        self.session.add_all(_projection_rows(package, actor_id, action))
        _increment_metrics(package, action)
        await self._audit(
            f"bk_r11.evidence_package.{action}",
            package.project_id,
            actor_type,
            actor_id,
            {
                "package_id": package.evidence_package_id,
                "acceptance_status": package.acceptance_status,
                "manifest_hash": package.manifest_hash,
                "artifact_count": len(package.artifacts),
                "audit_record_count": len(package.audit_records),
                "blockers": list(package.blockers),
            },
        )

    async def record_publication(
        self,
        publication: BKR11ArchivePublication,
        *,
        actor_type: str,
        actor_id: str,
    ) -> None:
        self.session.add(
            BKR11ArchivePublicationModel(
                project_key=publication.project_id,
                package_id=publication.evidence_package_id,
                archive_backend=publication.archive_backend,
                archive_uri=publication.archive_uri,
                archive_hash=publication.archive_hash,
                publication_hash=publication.publication_hash,
                status=publication.status,
                document=publication.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
        increment_metric("bk_r11_archive_publications_total")
        await self._audit(
            "bk_r11.archive_publication.recorded",
            publication.project_id,
            actor_type,
            actor_id,
            {
                "package_id": publication.evidence_package_id,
                "archive_backend": publication.archive_backend,
                "archive_hash": publication.archive_hash,
                "publication_hash": publication.publication_hash,
            },
        )

    async def record_verification(
        self,
        report: BKR11ArchiveVerificationReport,
        *,
        project_key: str,
        package_id: str,
        actor_type: str,
        actor_id: str,
    ) -> None:
        self.session.add(
            BKR11ArchiveVerificationModel(
                project_key=project_key,
                package_id=package_id,
                archive_backend=report.archive_backend,
                archive_uri=report.archive_uri,
                status=report.status,
                verification_hash=report.verification_hash,
                document=report.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
        increment_metric(f"bk_r11_archive_verifications_{report.status}_total")
        await self._audit(
            "bk_r11.archive_verification.recorded",
            project_key,
            actor_type,
            actor_id,
            {
                "package_id": package_id,
                "archive_backend": report.archive_backend,
                "archive_uri": report.archive_uri,
                "verification_hash": report.verification_hash,
                "status": report.status,
            },
        )

    async def flush(self) -> None:
        await self.session.flush()

    async def _audit(
        self,
        event_type: str,
        project_key: str,
        actor_type: str,
        actor_id: str,
        payload: dict[str, object],
    ) -> None:
        await AuditWriter(self.session).append_event(
            stream_id=f"bk-r11:{project_key}",
            project_id=None,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            payload={"project_key": project_key, **payload},
        )


def _package_row(package: BKR11EvidencePackage, actor_id: str) -> BKR11EvidencePackageModel:
    return BKR11EvidencePackageModel(
        project_key=package.project_id,
        package_id=package.evidence_package_id,
        package_version=package.package_version,
        acceptance_status=package.acceptance_status,
        manifest_hash=package.manifest_hash,
        document=package.model_dump(mode="json"),
        created_by=actor_id,
    )


def _projection_rows(
    package: BKR11EvidencePackage,
    actor_id: str,
    action: str,
) -> list[object]:
    rows: list[object] = []
    for artifact in package.artifacts:
        rows.append(
            BKR11EvidenceArtifactModel(
                project_key=package.project_id,
                package_id=package.evidence_package_id,
                evidence_id=artifact.evidence_id,
                evidence_type=artifact.evidence_type,
                source_system=artifact.source_system,
                classification=artifact.classification,
                artifact_hash=artifact.artifact_hash,
                document=artifact.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
    for record in package.audit_records:
        rows.append(
            BKR11AuditRecordModel(
                project_key=package.project_id,
                package_id=package.evidence_package_id,
                audit_record_id=record.audit_record_id,
                stream_id=record.stream_id,
                sequence=record.sequence,
                event_type=record.event_type,
                record_hash=record.record_hash,
                document=record.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
    rows.append(
        BKR11CoverageReportModel(
            project_key=package.project_id,
            package_id=package.evidence_package_id,
            status=package.coverage.status,
            coverage_hash=package.coverage.coverage_hash,
            document=package.coverage.model_dump(mode="json"),
            created_by=actor_id,
        )
    )
    rows.append(
        BKR11IntegrityReportModel(
            project_key=package.project_id,
            package_id=package.evidence_package_id,
            status=package.integrity.status,
            integrity_hash=package.integrity.integrity_hash,
            document=package.integrity.model_dump(mode="json"),
            created_by=actor_id,
        )
    )
    event = {
        "event_id": f"{package.evidence_package_id}:{action}:{package.manifest_hash}",
        "event_type": f"EvidencePackage{action.title().replace('_', '')}",
        "package_id": package.evidence_package_id,
        "project_id": package.project_id,
        "acceptance_status": package.acceptance_status,
        "manifest_hash": package.manifest_hash,
    }
    rows.append(
        BKR11PackageEventModel(
            project_key=package.project_id,
            package_id=package.evidence_package_id,
            event_id=event["event_id"],
            event_type=event["event_type"],
            event_hash=hash_json(event),
            document=event,
            created_by=actor_id,
        )
    )
    return rows


def _increment_metrics(package: BKR11EvidencePackage, action: str) -> None:
    increment_metric(f"bk_r11_evidence_packages_{action}_total")
    increment_metric("bk_r11_evidence_artifacts_total", len(package.artifacts))
    increment_metric("bk_r11_audit_records_total", len(package.audit_records))
    increment_metric(f"bk_r11_evidence_package_{package.acceptance_status}_total")
