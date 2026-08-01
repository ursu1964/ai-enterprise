from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"


class TraceableRequirement(ContractModel):
    id: str = Field(pattern=r"^(FR|NFR)-[0-9]{3}$")
    statement: str = Field(min_length=10)
    acceptance_criteria: tuple[str, ...] = Field(min_length=1)


class RequirementsContract(ContractModel):
    sections: tuple[str, ...] = Field(min_length=1)
    requirements: tuple[TraceableRequirement, ...] = Field(min_length=1)
    traceability_ids: tuple[str, ...] = Field(min_length=1)


class ArchitectureContract(ContractModel):
    components: tuple[str, ...] = Field(min_length=1)
    interfaces: tuple[str, ...] = Field(min_length=1)
    technology_choices: tuple[str, ...]
    constraints: tuple[str, ...]
    risks: tuple[str, ...]
    traceability_ids: tuple[str, ...] = Field(min_length=1)


class PlanningTask(ContractModel):
    task: str = Field(min_length=5)
    files: tuple[str, ...] = Field(min_length=1)
    dependencies: tuple[str, ...] = ()
    acceptance_tests: tuple[str, ...] = Field(min_length=1)
    complexity: Literal["low", "medium", "high"]
    estimated_size: int = Field(ge=1)
