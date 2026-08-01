from dataclasses import dataclass
from uuid import UUID

from .enums import AgentStatus, Availability
from .errors import InvalidProfileTransitionError


@dataclass
class AgentProfile:
    id: UUID
    organization_id: UUID
    agent_key: str
    display_name: str
    status: AgentStatus
    current_version_id: UUID
    home_unit_id: UUID
    version: int = 0
    availability: Availability = Availability.AVAILABLE

    def activate(self) -> None:
        if self.status is not AgentStatus.DRAFT:
            raise InvalidProfileTransitionError("only a draft profile may activate")
        self.status = AgentStatus.ACTIVE
        self.version += 1

    def suspend(self) -> None:
        if self.status is not AgentStatus.ACTIVE:
            raise InvalidProfileTransitionError("only an active profile may suspend")
        self.status = AgentStatus.SUSPENDED
        self.availability = Availability.SUSPENDED
        self.version += 1
