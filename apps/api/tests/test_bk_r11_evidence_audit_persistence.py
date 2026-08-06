from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.dialects.postgresql import JSONB

from ai_enterprise.api.routes.bk_r11_evidence_audit import _archive_summary
from ai_enterprise.application.bk_r11_evidence_audit_runtime import (
    BKR11ArchiveVerificationReport,
    bk_r11_append_audit_record,
    bk_r11_build_evidence_package,
    bk_r11_create_archive_publication_record,
    bk_r11_create_evidence_artifact,
)
from ai_enterprise.application.bk_r11_persistence_service import BKR11PersistenceService
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
from ai_enterprise.observability import metrics_snapshot
from tests.test_bk_r11_evidence_audit_runtime import _actor, _subject

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = (
    ROOT
    / "migrations"
    / "versions"
    / "a1d5e8f2b9c4_add_bk_r11_evidence_audit_records.py"
)
PUBLICATION_MIGRATION = (
    ROOT
    / "migrations"
    / "versions"
    / "b2e6f9a3c8d1_add_bk_r11_archive_publication_records.py"
)


def _package():
    artifact = bk_r11_create_evidence_artifact(
        evidence_id="ev-test-report-001",
        evidence_type="test-report",
        source_system="ci",
        uri="evidence://ci/run/123/report.json",
        content_hash="sha256-test-report",
        captured_by=_actor("verification-runner"),
        subjects=(_subject(),),
    )
    audit_record = bk_r11_append_audit_record(
        (),
        stream_id="project:project-001",
        event_type="EvidenceCaptured",
        actor=_actor(),
        subject=_subject(),
        evidence_ids=(artifact.evidence_id,),
        payload={"result": "passed"},
    )
    return bk_r11_build_evidence_package(
        evidence_package_id="pkg-r11-001",
        project_id="project-001",
        baseline_refs={"requirements": "req-baseline-001"},
        artifacts=(artifact,),
        audit_records=(audit_record,),
        required_evidence_by_obligation={"obl-req-api-001": ("test-report",)},
    )


def test_bk_r11_persistence_models_use_jsonb_documents_and_query_indexes() -> None:
    models = (
        BKR11EvidencePackageModel,
        BKR11EvidenceArtifactModel,
        BKR11AuditRecordModel,
        BKR11CoverageReportModel,
        BKR11IntegrityReportModel,
        BKR11PackageEventModel,
        BKR11ArchivePublicationModel,
        BKR11ArchiveVerificationModel,
    )

    for model in models:
        assert isinstance(model.__table__.c.document.type, JSONB)
        assert any(index.name.endswith("project_key") for index in model.__table__.indexes)


def test_bk_r11_migration_chains_after_bk_r10_and_creates_append_only_tables() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'down_revision: str | None = "f8a6c2d4e9b1"' in source
    assert "bk_r11_evidence_packages" in source
    assert "bk_r11_audit_records" in source
    assert "CREATE TRIGGER prevent_{table_name}_mutation_trigger" in source
    publication_source = PUBLICATION_MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision: str | None = "a1d5e8f2b9c4"' in publication_source
    assert "bk_r11_archive_publications" in publication_source
    assert "bk_r11_archive_verifications" in publication_source
    assert "CREATE TRIGGER prevent_{table_name}_mutation_trigger" in publication_source


class BKR11PersistenceSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.audit_records: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)

    def add_all(self, values: list[object]) -> None:
        self.added.extend(values)
        if len(values) == 2 and values[1].__class__.__name__ == "AuditChainRecordModel":
            self.audit_records.append(values[1])

    async def scalar(self, _statement: object) -> object | None:
        return self.audit_records[-1] if self.audit_records else None

    async def flush(self) -> None:
        return None


class SummarySession:
    def __init__(self, values: list[object | None]) -> None:
        self.values = values

    async def scalar(self, _statement: object) -> object | None:
        return self.values.pop(0)


class SummaryRow:
    def __init__(self, document: dict[str, object]) -> None:
        self.document = document


@pytest.mark.asyncio
async def test_bk_r11_persistence_service_records_projection_audit_and_metrics() -> None:
    package = _package()
    session = BKR11PersistenceSession()
    before = metrics_snapshot()

    service = BKR11PersistenceService(session)  # type: ignore[arg-type]
    await service.record_package(
        package,
        actor_type="human",
        actor_id="audit-owner",
        action="accepted",
    )

    assert any(isinstance(item, BKR11EvidencePackageModel) for item in session.added)
    assert any(isinstance(item, BKR11EvidenceArtifactModel) for item in session.added)
    assert any(isinstance(item, BKR11AuditRecordModel) for item in session.added)
    assert any(isinstance(item, BKR11CoverageReportModel) for item in session.added)
    assert any(isinstance(item, BKR11IntegrityReportModel) for item in session.added)
    assert any(isinstance(item, BKR11PackageEventModel) for item in session.added)
    assert any(
        item.event_type == "bk_r11.evidence_package.accepted"
        for item in session.added
        if item.__class__.__name__ == "AuditEventModel"
    )
    after = metrics_snapshot()
    assert after["bk_r11_evidence_packages_accepted_total"] >= (
        before.get("bk_r11_evidence_packages_accepted_total", 0) + 1
    )


@pytest.mark.asyncio
async def test_bk_r11_persistence_records_publication_and_verification() -> None:
    package = _package()
    publication = bk_r11_create_archive_publication_record(
        package,
        archive_backend="filesystem",
        archive_uri="/tmp/pkg.tar.gz",
        metadata_uri="/tmp/pkg.publication.json",
        archive_hash="a" * 64,
    )
    report = BKR11ArchiveVerificationReport(
        status="verified",
        archive_backend="filesystem",
        archive_uri=publication.archive_uri,
        expected_archive_hash=publication.archive_hash,
        actual_archive_hash=publication.archive_hash,
        metadata_verified=True,
        diagnostics=(),
        verification_hash="b" * 64,
    )
    session = BKR11PersistenceSession()
    service = BKR11PersistenceService(session)  # type: ignore[arg-type]

    await service.record_publication(publication, actor_type="human", actor_id="audit-owner")
    await service.record_verification(
        report,
        project_key=publication.project_id,
        package_id=publication.evidence_package_id,
        actor_type="human",
        actor_id="audit-owner",
    )

    assert any(isinstance(item, BKR11ArchivePublicationModel) for item in session.added)
    assert any(isinstance(item, BKR11ArchiveVerificationModel) for item in session.added)
    assert any(
        item.event_type == "bk_r11.archive_publication.recorded"
        for item in session.added
        if item.__class__.__name__ == "AuditEventModel"
    )
    assert any(
        item.event_type == "bk_r11.archive_verification.recorded"
        for item in session.added
        if item.__class__.__name__ == "AuditEventModel"
    )


@pytest.mark.asyncio
async def test_bk_r11_archive_summary_status_transitions() -> None:
    assert (
        await _archive_summary(
            SummarySession([0, 0, 0, None, None]),  # type: ignore[arg-type]
            project_id="project-001",
            package_id=None,
        )
    )["status"] == "no_publications"

    assert (
        await _archive_summary(
            SummarySession([1, 0, 0, SummaryRow({"publication": "latest"}), None]),  # type: ignore[arg-type]
            project_id="project-001",
            package_id=None,
        )
    )["status"] == "verification_missing"

    assert (
        await _archive_summary(
            SummarySession(
                [
                    1,
                    1,
                    1,
                    SummaryRow({"publication": "latest"}),
                    SummaryRow({"verification": "failed"}),
                ]
            ),  # type: ignore[arg-type]
            project_id="project-001",
            package_id=None,
        )
    )["status"] == "verification_failed"

    verified = await _archive_summary(
        SummarySession(
            [
                1,
                1,
                0,
                SummaryRow({"publication": "latest"}),
                SummaryRow({"verification": "verified"}),
            ]
        ),  # type: ignore[arg-type]
        project_id="project-001",
        package_id="pkg-r11-001",
    )

    assert verified["status"] == "verified"
    assert verified["latest_publication"] == {"publication": "latest"}
    assert verified["latest_verification"] == {"verification": "verified"}
    assert len(str(verified["summary_hash"])) == 64
