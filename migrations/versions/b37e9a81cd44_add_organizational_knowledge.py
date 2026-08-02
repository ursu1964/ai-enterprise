"""add organizational knowledge

Revision ID: b37e9a81cd44
Revises: a92d41c70be3
"""

from collections.abc import Sequence

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
from alembic import op

revision: str = "b37e9a81cd44"
down_revision: str | None = "a92d41c70be3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    KnowledgeSourceModel,
    KnowledgeCandidateModel,
    KnowledgeCandidateEvidenceModel,
    KnowledgePromotionReviewModel,
    KnowledgeItemModel,
    KnowledgeItemVersionModel,
    KnowledgeSupersessionModel,
    KnowledgeContradictionModel,
    KnowledgeIndexVersionModel,
    KnowledgeRetrievalSessionModel,
    KnowledgeRetrievalResultModel,
    KnowledgeRetrievalManifestModel,
)


def upgrade() -> None:
    bind = op.get_bind()
    for model in TABLES:
        model.__table__.create(bind, checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    for model in reversed(TABLES):
        model.__table__.drop(bind, checkfirst=False)
