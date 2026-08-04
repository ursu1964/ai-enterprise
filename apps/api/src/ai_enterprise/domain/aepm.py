from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AepmValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProjectIntent(AepmValue):
    name: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=4000)
    problem: str = Field(min_length=1, max_length=4000)
    opportunity: str | None = Field(default=None, max_length=4000)


class BusinessOutcome(AepmValue):
    id: str = Field(pattern=r"^OUT-[0-9]{3}$")
    description: str = Field(min_length=1, max_length=2000)
    indicators: tuple[str, ...] = Field(min_length=1)


class Stakeholder(AepmValue):
    id: str = Field(pattern=r"^STK-[0-9]{3}$")
    name: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=200)
    responsibilities: tuple[str, ...] = ()


class Capability(AepmValue):
    id: str = Field(pattern=r"^CAP-[0-9]{3}$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    owner_stakeholder_id: str = Field(pattern=r"^STK-[0-9]{3}$")


class CoreProcess(AepmValue):
    id: str = Field(pattern=r"^PROC-[0-9]{3}$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    trigger: str = Field(min_length=1, max_length=1000)
    outputs: tuple[str, ...] = Field(min_length=1)


class BusinessRule(AepmValue):
    id: str = Field(pattern=r"^RULE-[0-9]{3}$")
    description: str = Field(min_length=1, max_length=2000)


class DataEntity(AepmValue):
    id: str = Field(pattern=r"^ENT-[0-9]{3}$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    owner_stakeholder_id: str = Field(pattern=r"^STK-[0-9]{3}$")


class Integration(AepmValue):
    id: str = Field(pattern=r"^INT-[0-9]{3}$")
    name: str = Field(min_length=1, max_length=200)
    system: str = Field(min_length=1, max_length=500)
    purpose: str = Field(min_length=1, max_length=2000)
    security_rules: tuple[str, ...] = Field(min_length=1)


class QualityRequirement(AepmValue):
    id: str = Field(pattern=r"^QUAL-[0-9]{3}$")
    category: Literal[
        "accessibility",
        "availability",
        "maintainability",
        "performance",
        "privacy",
        "reliability",
        "scalability",
        "security",
        "usability",
    ]
    description: str = Field(min_length=1, max_length=2000)
    acceptance_criteria: tuple[str, ...] = Field(min_length=1)


class Constraint(AepmValue):
    id: str = Field(pattern=r"^CON-[0-9]{3}$")
    category: Literal[
        "budget", "compliance", "delivery", "operational", "organizational", "technical"
    ]
    description: str = Field(min_length=1, max_length=2000)


class PreferredTechnologyTargets(AepmValue):
    frontend: tuple[str, ...] = ()
    backend: tuple[str, ...] = ()
    database: tuple[str, ...] = ()
    queue: tuple[str, ...] = ()
    object_storage: tuple[str, ...] = ()
    deployment: tuple[str, ...] = ()


class AepmManifest(AepmValue):
    schema_version: Literal["aepm-0.1"]
    project_intent: ProjectIntent
    business_outcomes: tuple[BusinessOutcome, ...] = Field(min_length=1)
    stakeholders: tuple[Stakeholder, ...] = Field(min_length=1)
    capabilities: tuple[Capability, ...]
    core_processes: tuple[CoreProcess, ...]
    business_rules: tuple[BusinessRule, ...]
    data_entities: tuple[DataEntity, ...]
    integrations: tuple[Integration, ...]
    quality_requirements: tuple[QualityRequirement, ...]
    constraints: tuple[Constraint, ...]
    preferred_technology_targets: PreferredTechnologyTargets
