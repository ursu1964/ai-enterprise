from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class PromptVersion:
    id: UUID
    prompt_key: str
    semantic_version: str
    content_hash: str
    supported_models: tuple[str, ...]
    output_contract_version: str
    predecessor_id: UUID | None
    approved_by_human_id: UUID
    approved_at: datetime


@dataclass(frozen=True)
class LearningProposal:
    id: UUID
    title: str
    observation: str
    recommendation: str
    evidence_ids: tuple[UUID, ...]
    target_prompt_version_id: UUID
    status: str
    proposed_at: datetime
    proposed_prompt_content: str | None = None

    def __post_init__(self) -> None:
        if not self.evidence_ids:
            raise ValueError("learning proposals require immutable evidence")
        if self.status not in {"proposed", "under_review", "approved", "rejected", "withdrawn"}:
            raise ValueError("invalid governed learning status")


@dataclass(frozen=True)
class PromptChangeApproval:
    id: UUID
    proposal_id: UUID
    approved_by_human_id: UUID
    approved_at: datetime


def create_prompt_successor(
    *,
    version_id: UUID,
    predecessor: PromptVersion,
    proposal: LearningProposal,
    semantic_version: str,
    content_hash: str,
    approval: PromptChangeApproval,
    supported_models: tuple[str, ...] | None = None,
) -> PromptVersion:
    if (
        proposal.status != "approved"
        or proposal.target_prompt_version_id != predecessor.id
        or approval.proposal_id != proposal.id
    ):
        raise ValueError("a bound approved learning proposal is required")
    if len(content_hash) != 64 or any(
        character not in "0123456789abcdef" for character in content_hash
    ):
        raise ValueError("prompt content must be immutable and hash-bound")
    if semantic_version == predecessor.semantic_version:
        raise ValueError("a successor must have a new semantic version")
    return PromptVersion(
        version_id,
        predecessor.prompt_key,
        semantic_version,
        content_hash,
        supported_models or predecessor.supported_models,
        predecessor.output_contract_version,
        predecessor.id,
        approval.approved_by_human_id,
        approval.approved_at,
    )
