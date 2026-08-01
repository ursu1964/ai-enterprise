from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConcurrencyPolicy:
    maximum_active_runs: int
    maximum_high_risk_runs: int
    allow_parallel_projects: bool


@dataclass(frozen=True)
class CrewCompositionPolicy:
    version: str
    required_roles: tuple[str, ...]
    optional_roles: tuple[str, ...] = ()
    minimum_members: int = 1
    maximum_members: int = 10
    require_distinct_review_agent: bool = True
    require_distinct_security_agent: bool = True
    deterministic_selection: bool = True
