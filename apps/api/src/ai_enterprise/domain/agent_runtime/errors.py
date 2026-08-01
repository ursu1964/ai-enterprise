class AgentRuntimeError(ValueError):
    """Base policy-bound runtime error."""


class RegistryIntegrityError(AgentRuntimeError):
    """A registry object is absent, mutable, inactive, or corrupt."""


class ToolPolicyError(AgentRuntimeError):
    """A tool definition or invocation violates runtime policy."""
