import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KnowledgeCommand:
    correlation_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class RegisterKnowledgeSource(KnowledgeCommand):
    source_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ExtractKnowledgeCandidates(KnowledgeCommand):
    source_id: uuid.UUID
    runtime_session_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ValidateKnowledgeCandidate(KnowledgeCommand):
    candidate_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class SubmitKnowledgeCandidateForReview(ValidateKnowledgeCandidate):
    pass


@dataclass(frozen=True, slots=True)
class ReviewKnowledgeCandidate(ValidateKnowledgeCandidate):
    reviewer_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PromoteKnowledgeCandidate(ValidateKnowledgeCandidate):
    pass


@dataclass(frozen=True, slots=True)
class RejectKnowledgeCandidate(ValidateKnowledgeCandidate):
    pass


@dataclass(frozen=True, slots=True)
class SupersedeKnowledgeItem(KnowledgeCommand):
    item_id: uuid.UUID
    superseding_item_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class WithdrawKnowledgeItem(KnowledgeCommand):
    item_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class DetectKnowledgeContradictions(KnowledgeCommand):
    item_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ResolveKnowledgeContradiction(KnowledgeCommand):
    contradiction_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class RevalidateKnowledgeItem(KnowledgeCommand):
    item_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class RetrieveKnowledge(KnowledgeCommand):
    runtime_session_id: uuid.UUID
    query_text: str


@dataclass(frozen=True, slots=True)
class BuildKnowledgeIndex(KnowledgeCommand):
    organization_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PromoteProjectKnowledgeToOrganization(KnowledgeCommand):
    item_id: uuid.UUID
