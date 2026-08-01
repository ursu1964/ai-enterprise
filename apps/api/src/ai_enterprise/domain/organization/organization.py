from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from .enums import OrganizationStatus
from .errors import InvalidOrganizationTransitionError
from .events import OrganizationActivated, OrganizationSuspended


@dataclass
class Organization:
    id: UUID
    name: str
    status: OrganizationStatus
    policy_set_id: UUID
    version: int = 0
    _events: list[object] = field(default_factory=list, repr=False)

    def activate(self, *, now: datetime) -> None:
        if self.status is not OrganizationStatus.DRAFT:
            raise InvalidOrganizationTransitionError("only a draft organization may activate")
        self.status = OrganizationStatus.ACTIVE
        self.version += 1
        self._events.append(OrganizationActivated(self.id, now))

    def suspend(self, *, reason: str, now: datetime) -> None:
        if self.status is not OrganizationStatus.ACTIVE:
            raise InvalidOrganizationTransitionError("only an active organization may suspend")
        if not reason.strip():
            raise InvalidOrganizationTransitionError("a suspension reason is required")
        self.status = OrganizationStatus.SUSPENDED
        self.version += 1
        self._events.append(OrganizationSuspended(self.id, reason, now))

    @property
    def permits_new_work(self) -> bool:
        return self.status is OrganizationStatus.ACTIVE
