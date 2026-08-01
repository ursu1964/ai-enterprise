import uuid
from datetime import UTC, datetime

import pytest

from ai_enterprise.api.routes.knowledge import router
from ai_enterprise.application.knowledge_commands import (
    ExtractKnowledgeCandidates,
    PromoteProjectKnowledgeToOrganization,
    RetrieveKnowledge,
)
from ai_enterprise.application.knowledge_extraction_handler import (
    ExtractionCommand,
    ExtractKnowledgeCandidatesHandler,
)
from ai_enterprise.application.knowledge_service import KnowledgeService
from ai_enterprise.infrastructure.agent_runtime.seed import KNOWLEDGE_SKILLS
from ai_enterprise.infrastructure.knowledge.models import (
    KnowledgeCandidateEvidenceModel,
    KnowledgeCandidateModel,
    KnowledgeContradictionModel,
    KnowledgeIndexVersionModel,
    KnowledgeItemModel,
    KnowledgeItemVersionModel,
    KnowledgePromotionReviewModel,
    KnowledgeRetrievalManifestModel,
    KnowledgeRetrievalResultModel,
    KnowledgeRetrievalSessionModel,
    KnowledgeSourceModel,
    KnowledgeSupersessionModel,
)


def test_knowledge_schema_preserves_evidence_promotion_and_retrieval_lineage() -> None:
    assert KnowledgeSourceModel.__table__.constraints
    assert KnowledgeCandidateModel.__table__.c.candidate_hash.unique is True
    assert KnowledgeItemModel.__table__.c.knowledge_hash.unique is True
    assert KnowledgeItemVersionModel.__table__.c.version_hash.unique is True
    assert KnowledgeRetrievalManifestModel.__table__.c.manifest_hash.unique is True
    for model in (
        KnowledgeCandidateEvidenceModel,
        KnowledgePromotionReviewModel,
        KnowledgeSupersessionModel,
        KnowledgeContradictionModel,
        KnowledgeIndexVersionModel,
        KnowledgeRetrievalSessionModel,
        KnowledgeRetrievalResultModel,
    ):
        assert len(model.__table__.columns) >= 4


def test_knowledge_api_surface_is_complete() -> None:
    paths = {f"/api/v1{route.path}" for route in router.routes}
    assert {
        "/api/v1/knowledge-sources/{source_id}",
        "/api/v1/projects/{project_id}/knowledge-sources",
        "/api/v1/knowledge-candidates/extractions",
        "/api/v1/knowledge-candidates/{candidate_id}",
        "/api/v1/knowledge-candidates/{candidate_id}/reviews",
        "/api/v1/knowledge-items/{item_id}",
        "/api/v1/knowledge-items",
        "/api/v1/knowledge-items/{item_id}/supersede",
        "/api/v1/knowledge-items/{item_id}/withdraw",
        "/api/v1/knowledge/retrieve",
        "/api/v1/knowledge-contradictions",
        "/api/v1/knowledge-contradictions/{contradiction_id}/resolve",
    } <= paths


def test_validation_rejects_classification_downgrade_and_secrets() -> None:
    source = KnowledgeSourceModel(
        id=uuid.uuid4(),
        source_type="integration-result",
        source_id=uuid.uuid4(),
        source_hash="a" * 64,
        organization_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        classification="confidential",
        trust_level="verified",
        occurred_at=datetime.now(UTC),
    )
    findings = KnowledgeService._validate(
        source,
        {
            "classification": "internal",
            "statement": "password=do-not-promote",
            "evidence_locators": [],
        },
    )
    assert {item["code"] for item in findings} == {"KNOW-003", "KNOW-005", "KNOW-008"}


def test_governed_extraction_skill_and_commands_are_explicit() -> None:
    assert KNOWLEDGE_SKILLS == (
        (
            "knowledge-extraction-v1",
            "Governed knowledge extraction",
            "extract-knowledge-candidates",
        ),
    )
    correlation = uuid.uuid4()
    source_id, runtime_id = uuid.uuid4(), uuid.uuid4()
    assert (
        ExtractKnowledgeCandidates(correlation, source_id, runtime_id).runtime_session_id
        == runtime_id
    )
    assert RetrieveKnowledge(correlation, runtime_id, "migration policy").query_text
    assert PromoteProjectKnowledgeToOrganization(correlation, source_id).item_id == source_id


@pytest.mark.asyncio
async def test_extraction_handler_preserves_runtime_skill_and_source_lineage() -> None:
    source = KnowledgeSourceModel(
        id=uuid.uuid4(),
        source_type="integration-result",
        source_id=uuid.uuid4(),
        source_hash="a" * 64,
        organization_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        classification="internal",
        trust_level="verified",
        occurred_at=datetime.now(UTC),
    )
    runtime_id, skill_id, observed = uuid.uuid4(), uuid.uuid4(), {}

    class Runtime:
        async def execute(self, **values: object) -> tuple[uuid.UUID, uuid.UUID, dict]:
            observed.update(values)
            return (
                runtime_id,
                skill_id,
                {
                    "candidates": [
                        {
                            "candidate_type": "lesson",
                            "title": "Gate database migrations",
                    "statement": (
                        "Run migrations only after the database health check succeeds."
                    ),
                            "scope_type": "project",
                            "scope_id": source.project_id,
                            "evidence_locators": [{"test_result": "migration-success"}],
                            "confidence_band": "high",
                            "classification": "internal",
                        }
                    ]
                },
            )

    persisted: list[object] = []

    async def load(identifier: uuid.UUID) -> KnowledgeSourceModel | None:
        return source if identifier == source.id else None

    async def persist(*values: object) -> tuple[uuid.UUID, ...]:
        persisted.extend(values)
        return (uuid.uuid4(),)

    result = await ExtractKnowledgeCandidatesHandler(
        source_loader=load, runtime=Runtime(), persister=persist
    ).handle(ExtractionCommand(source.id, ("lesson",)))
    assert len(result) == 1
    assert observed["source_hash"] == source.source_hash
    assert observed["requested_capability"] == "extract-knowledge-candidates"
    assert persisted[1:3] == [runtime_id, skill_id]
