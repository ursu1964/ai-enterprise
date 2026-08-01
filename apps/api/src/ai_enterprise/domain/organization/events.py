from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class OrganizationActivated:
    organization_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class OrganizationSuspended:
    organization_id: UUID
    reason: str
    occurred_at: datetime
