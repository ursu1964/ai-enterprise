from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ai_enterprise.domain.hashing import hash_json


@dataclass(frozen=True)
class ModelPolicy:
    id: UUID
    version: str
    provider_class: str
    allowed_model_families: tuple[str, ...]
    minimum_context_window: int
    maximum_output_tokens: int
    temperature: float
    tool_calling_required: bool
    allow_external_provider: bool
    allow_local_provider: bool
    data_classification_limit: str


@dataclass(frozen=True)
class AgentProfileVersion:
    id: UUID
    agent_profile_id: UUID
    version_number: int
    role_version_ids: tuple[UUID, ...]
    capability_grants: tuple[str, ...]
    tool_permissions: tuple[str, ...]
    model_policy_id: UUID
    prompt_bundle_id: UUID
    skill_bundle_ids: tuple[UUID, ...]
    knowledge_policy_id: UUID
    runtime_policy_id: UUID
    configuration_hash: str
    created_at: datetime
    approval_status: str = "pending"

    def calculated_hash(self) -> str:
        return hash_json(
            {
                "agent_profile_id": str(self.agent_profile_id),
                "version_number": self.version_number,
                "role_version_ids": sorted(map(str, self.role_version_ids)),
                "capability_grants": sorted(self.capability_grants),
                "tool_permissions": sorted(self.tool_permissions),
                "model_policy_id": str(self.model_policy_id),
                "prompt_bundle_id": str(self.prompt_bundle_id),
                "skill_bundle_ids": sorted(map(str, self.skill_bundle_ids)),
                "knowledge_policy_id": str(self.knowledge_policy_id),
                "runtime_policy_id": str(self.runtime_policy_id),
            }
        )

    @property
    def is_approved(self) -> bool:
        return (
            self.approval_status == "approved"
            and self.configuration_hash == self.calculated_hash()
        )
