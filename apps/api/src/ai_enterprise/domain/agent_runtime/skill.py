from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ai_enterprise.domain.hashing import hash_json

from .enums import BindingStatus, RegistryStatus
from .errors import RegistryIntegrityError


@dataclass(frozen=True)
class SkillVersion:
    id: UUID
    skill_key: str
    version_number: int
    required_capabilities: tuple[str, ...]
    required_tool_permissions: tuple[str, ...]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    procedure_document: dict[str, Any]
    risk_level: str
    status: RegistryStatus
    skill_hash: str
    policy_priority: int = 100

    def canonical_document(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "skill_key": self.skill_key,
            "version_number": self.version_number,
            "required_capabilities": sorted(set(self.required_capabilities)),
            "required_tool_permissions": sorted(set(self.required_tool_permissions)),
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "procedure_document": self.procedure_document,
            "risk_level": self.risk_level,
            "policy_priority": self.policy_priority,
        }

    def calculated_hash(self) -> str:
        return hash_json(self.canonical_document())

    @property
    def is_executable(self) -> bool:
        return self.status is RegistryStatus.APPROVED and self.skill_hash == self.calculated_hash()

    def assert_executable(self) -> None:
        if self.status is not RegistryStatus.APPROVED:
            raise RegistryIntegrityError("SKILL-VERSION-NOT-APPROVED")
        if self.skill_hash != self.calculated_hash():
            raise RegistryIntegrityError("SKILL-VERSION-HASH-MISMATCH")
        steps = self.procedure_document.get("steps")
        if not isinstance(steps, list) or not steps:
            raise RegistryIntegrityError("SKILL-PROCEDURE-INVALID")


@dataclass(frozen=True)
class CapabilitySkillBinding:
    capability_key: str
    skill_version_id: UUID
    binding_status: BindingStatus
    policy_version: str
    explicit_assignment: bool = False
