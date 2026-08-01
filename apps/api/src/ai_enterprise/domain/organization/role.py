from dataclasses import dataclass
from uuid import UUID

from .enums import RoleStatus


@dataclass(frozen=True)
class RoleVersion:
    id: UUID
    role_id: UUID
    role_key: str
    version_number: int
    allowed_task_classes: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    forbidden_capabilities: tuple[str, ...] = ()
    human_only_decisions: tuple[str, ...] = ()
    incompatible_roles: tuple[str, ...] = ()
    status: RoleStatus = RoleStatus.DRAFT
    role_hash: str = ""

    @property
    def is_active(self) -> bool:
        return self.status is RoleStatus.ACTIVE
