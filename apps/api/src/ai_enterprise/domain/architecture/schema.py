from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FunctionalDomain(StrictModel):
    id: str = Field(pattern=r"^DOM-[A-Z0-9-]+$")
    name: str = Field(min_length=1, max_length=200)
    responsibilities: tuple[str, ...] = Field(min_length=1)
    requirement_ids: tuple[str, ...] = Field(min_length=1)


class ArchitectureModule(StrictModel):
    id: str = Field(pattern=r"^MOD-[A-Z0-9-]+$")
    name: str = Field(min_length=1, max_length=200)
    domain_id: str
    responsibilities: tuple[str, ...] = Field(min_length=1)
    dependencies: tuple[str, ...] = ()
    requirement_ids: tuple[str, ...] = Field(min_length=1)


class InterfaceContract(StrictModel):
    id: str = Field(pattern=r"^(API|EVT|QUE)-[A-Z0-9-]+$")
    name: str = Field(min_length=1, max_length=200)
    kind: str = Field(pattern=r"^(rest|event|queue)$")
    owner_module_id: str
    consumers: tuple[str, ...] = ()
    contract: str = Field(min_length=1)
    requirement_ids: tuple[str, ...] = Field(min_length=1)


class DataEntity(StrictModel):
    id: str = Field(pattern=r"^ENT-[A-Z0-9-]+$")
    name: str = Field(min_length=1, max_length=200)
    owner_module_id: str
    persistence: str = Field(min_length=1)
    transaction_boundary: str = Field(min_length=1)
    requirement_ids: tuple[str, ...] = Field(min_length=1)


class RequirementTrace(StrictModel):
    requirement_id: str = Field(min_length=1)
    design_element_ids: tuple[str, ...] = Field(min_length=1)


class ArchitectureArtifactDocument(StrictModel):
    schema_version: str = Field(pattern=r"^1\.0$")
    overview: str = Field(min_length=1)
    goals: tuple[str, ...] = Field(min_length=1)
    constraints: tuple[str, ...] = Field(min_length=1)
    functional_domains: tuple[FunctionalDomain, ...] = Field(min_length=1)
    modules: tuple[ArchitectureModule, ...] = Field(min_length=1)
    interfaces: tuple[InterfaceContract, ...] = ()
    data_entities: tuple[DataEntity, ...] = ()
    deployment: tuple[str, ...] = Field(min_length=1)
    security: tuple[str, ...] = Field(min_length=1)
    reliability: tuple[str, ...] = Field(min_length=1)
    failure_scenarios: tuple[str, ...] = Field(min_length=1)
    scaling: tuple[str, ...] = Field(min_length=1)
    observability: tuple[str, ...] = Field(min_length=1)
    risks: tuple[str, ...] = ()
    open_questions: tuple[str, ...] = ()
    requirement_traceability: tuple[RequirementTrace, ...] = Field(min_length=1)
