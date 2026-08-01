from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RequirementsReviewFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    requirement_id: str | None = Field(default=None, max_length=100)
    category: Literal[
        "missing",
        "ambiguous",
        "incorrect",
        "inconsistent",
        "unverifiable",
        "scope",
        "security",
        "performance",
        "compliance",
        "other",
    ]
    severity: Literal["low", "medium", "high", "critical"]
    description: str = Field(min_length=3, max_length=4000)
    requested_change: str = Field(min_length=3, max_length=4000)


class RequirementsReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: Literal["approved", "changes_requested"]
    summary: str = Field(min_length=3, max_length=4000)
    findings: tuple[RequirementsReviewFinding, ...] = Field(default=(), max_length=100)

    @model_validator(mode="after")
    def require_actionable_findings(self) -> "RequirementsReviewDecision":
        if self.decision == "changes_requested" and not self.findings:
            raise ValueError("Changes requested requires at least one actionable finding")
        return self


class RequirementItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^(?:FR|NFR|REQ)-\d{3,}$")
    statement: str = Field(min_length=3, max_length=8000)
    acceptance_criteria: tuple[str, ...] = Field(min_length=1, max_length=50)


class RequirementsArtifactDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    title: str = Field(min_length=3, max_length=300)
    executive_summary: str = Field(min_length=3, max_length=8000)
    functional_requirements: tuple[RequirementItem, ...] = Field(min_length=1, max_length=500)
    non_functional_requirements: tuple[RequirementItem, ...] = Field(default=(), max_length=500)
    assumptions: tuple[str, ...] = Field(default=(), max_length=200)
    risks: tuple[str, ...] = Field(default=(), max_length=200)
    open_questions: tuple[str, ...] = Field(default=(), max_length=200)
