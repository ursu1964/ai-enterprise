from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .enums import AssignmentStatus


@dataclass(frozen=True)
class AgentAssignment:
    id: UUID
    organization_id: UUID
    agent_profile_id: UUID
    agent_profile_version_id: UUID
    role_version_id: UUID
    scope_type: str
    scope_id: UUID
    status: AssignmentStatus
    valid_from: datetime
    valid_until: datetime | None
    granted_capabilities: tuple[str, ...]
    denied_capabilities: tuple[str, ...]
    assigned_by: UUID
    assignment_hash: str
    version: int = 0
    priority: int = 100
    activated_at: datetime | None = None

    def is_active_at(self, now: datetime) -> bool:
        return (
            self.status is AssignmentStatus.ACTIVE
            and self.valid_from <= now
            and (self.valid_until is None or self.valid_until > now)
        )

    def covers(self, *, scope_type: str, scope_id: UUID) -> bool:
        return self.scope_type == scope_type and self.scope_id == scope_id
