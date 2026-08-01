class OrganizationError(ValueError):
    """Base error for organizational policy violations."""


class InvalidOrganizationTransitionError(OrganizationError):
    pass


class ImmutableRoleVersionError(OrganizationError):
    pass


class InvalidProfileTransitionError(OrganizationError):
    pass


class OrganizationalHierarchyError(OrganizationError):
    pass
