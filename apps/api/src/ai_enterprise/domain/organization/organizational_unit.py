from dataclasses import dataclass
from uuid import UUID

from .errors import OrganizationalHierarchyError


@dataclass(frozen=True)
class OrganizationalUnit:
    id: UUID
    organization_id: UUID
    parent_unit_id: UUID | None
    unit_key: str
    name: str
    purpose: str
    status: str = "active"


def validate_hierarchy_depth(*, ancestor_ids: tuple[UUID, ...], maximum_depth: int = 6) -> None:
    if maximum_depth < 1 or len(ancestor_ids) + 1 > maximum_depth:
        raise OrganizationalHierarchyError(f"organizational depth exceeds {maximum_depth}")
    if len(set(ancestor_ids)) != len(ancestor_ids):
        raise OrganizationalHierarchyError("organizational hierarchy contains a cycle")
