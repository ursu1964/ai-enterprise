from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CandidateTestCommand(StrictCandidate):
    command_key: str = Field(min_length=1, max_length=100)
    argv: list[str] = Field(min_length=1, max_length=20)
    working_directory: str = "."
    timeout_seconds: int = Field(ge=1, le=1800)


class CandidateAcceptanceCriterion(StrictCandidate):
    criterion_key: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=10, max_length=500)
    verification_type: Literal[
        "test", "static-analysis", "inspection", "migration-check", "contract-test"
    ]
    command_ref: str | None = None


class CandidateExecutionPolicy(StrictCandidate):
    network: Literal["disabled", "enabled"] = "disabled"
    cpu_limit: float = Field(gt=0)
    memory_mb: int = Field(gt=0)
    pid_limit: int = Field(gt=0)
    timeout_seconds: int = Field(gt=0)
    privileged: bool = False
    host_repository_write: bool = False


class CandidateWorkPackage(StrictCandidate):
    candidate_key: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=300)
    objective: str = Field(min_length=10)
    requirement_refs: list[str]
    architecture_refs: list[str]
    allowed_paths: list[str]
    proposed_new_paths: list[str] = Field(default_factory=list)
    prohibited_paths: list[str] = Field(default_factory=list)
    dependency_candidates: list[str] = Field(default_factory=list)
    dependency_reasons: dict[str, str] = Field(default_factory=dict)
    acceptance_criteria: list[CandidateAcceptanceCriterion]
    test_commands: list[CandidateTestCommand]
    estimated_files: int = Field(ge=1)
    estimated_changed_lines: int = Field(ge=1)
    execution_policy: CandidateExecutionPolicy


class CandidateDecomposition(StrictCandidate):
    summary: str = Field(min_length=1)
    packages: list[CandidateWorkPackage] = Field(min_length=1)
    unresolved_questions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
