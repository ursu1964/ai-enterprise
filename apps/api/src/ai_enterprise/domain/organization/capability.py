from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilityDefinition:
    key: str
    category: str
    description: str
    human_only: bool = False
    high_risk: bool = False
    required_tool_permissions: tuple[str, ...] = ()
    incompatible_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolPermission:
    key: str
    description: str
    prohibited_for_agents: bool = False


AGENT_PROHIBITED_TOOL_PERMISSIONS = frozenset(
    {
        "production_database.write",
        "authoritative_repository.push",
        "approval_record.create_as_human",
        "policy_override.write",
        "audit_record.delete",
    }
)
