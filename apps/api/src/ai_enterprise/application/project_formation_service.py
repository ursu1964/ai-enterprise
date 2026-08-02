from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.api.project_formation_schemas import (
    FormationArtifactResponse,
    FormationRequest,
    FormationResponse,
)
from ai_enterprise.domain.enums import ArtifactType
from ai_enterprise.domain.hashing import canonical_json, hash_json
from ai_enterprise.infrastructure.database.models import (
    ArtifactModel,
    AuditEventModel,
    ProjectModel,
)


class ProjectFormationError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class FormationDocument:
    artifact_type: ArtifactType
    title: str
    body: dict[str, Any]
    human_summary: str


class ProjectFormationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_formation_pack(
        self, request: FormationRequest, *, actor_id: str
    ) -> FormationResponse:
        project = await self._session.get(ProjectModel, request.project_id)
        if project is None:
            raise ProjectFormationError("Project not found")
        missing = self._missing_information(request)
        status = "draft_needs_clarification" if missing else "ready_for_approval"
        generated_at = datetime.now(UTC)
        traceability = {
            "project_id": str(project.id),
            "manifest_hash": project.manifest_hash,
            "idea_hash": hash_json({"idea": request.idea}),
            "formation_status": status,
            "source": "deterministic-project-formation-v1",
        }
        documents = self._documents(project, request, missing, status, traceability)
        artifacts: list[ArtifactModel] = []
        responses: list[FormationArtifactResponse] = []
        for document in documents:
            body = {
                "schema_version": "1.0",
                "title": document.title,
                "artifact_type": document.artifact_type.value,
                "project_id": str(project.id),
                "generated_at": generated_at.isoformat(),
                "traceability": traceability,
                "content": document.body,
            }
            digest = hash_json(body)
            artifact = ArtifactModel(
                id=uuid.uuid4(),
                project_id=project.id,
                run_id=None,
                artifact_type=document.artifact_type,
                media_type="application/json",
                content=canonical_json(body),
                content_hash=digest,
            )
            artifacts.append(artifact)
            responses.append(
                FormationArtifactResponse(
                    artifact_id=artifact.id,
                    artifact_type=document.artifact_type.value,
                    content_hash=digest,
                    title=document.title,
                    human_summary=document.human_summary,
                )
            )
        self._session.add_all(
            [
                *artifacts,
                AuditEventModel(
                    id=uuid.uuid4(),
                    project_id=project.id,
                    event_type="project_formation.pack_created",
                    actor_type="human",
                    actor_id=actor_id,
                    payload={
                        "status": status,
                        "artifact_ids": [str(item.id) for item in artifacts],
                        "missing_information": missing,
                    },
                ),
            ]
        )
        await self._session.commit()
        return FormationResponse(
            project_id=project.id,
            status=status,
            correction_attempt=request.correction_attempt,
            missing_information=missing,
            next_action=self._next_action(missing),
            generated_at=generated_at,
            artifacts=responses,
            traceability=traceability,
        )

    def _missing_information(self, request: FormationRequest) -> list[str]:
        missing: list[str] = []
        if not request.expected_outcome:
            missing.append("expected outcome")
        if not request.target_users:
            missing.append("target users")
        if not request.constraints:
            missing.append("constraints or known limits")
        if not request.known_systems:
            missing.append("existing systems or integrations")
        return missing

    def _next_action(self, missing: list[str]) -> str:
        if missing:
            return "Ask the client for the missing information, then regenerate the formation pack."
        return "Review the formation approval pack and approve before starting execution work."

    def _documents(
        self,
        project: ProjectModel,
        request: FormationRequest,
        missing: list[str],
        status: str,
        traceability: dict[str, Any],
    ) -> list[FormationDocument]:
        modules = self._modules(request.idea, project.manifest.get("project_type"))
        return [
            FormationDocument(
                ArtifactType.PROJECT_BRIEF,
                "Project Brief",
                {
                    "problem_statement": request.idea,
                    "business_objectives": [request.expected_outcome or "Clarify expected outcome"],
                    "stakeholders": request.target_users or ["to be confirmed"],
                    "constraints": request.constraints,
                    "assumptions": missing,
                    "success_metrics": self._success_metrics(request),
                },
                (
                    "Business brief created from the idea, target users, constraints, "
                    "and success signals."
                ),
            ),
            FormationDocument(
                ArtifactType.SOLUTION_PROPOSAL,
                "Solution Proposal",
                {
                    "recommended_modules": modules,
                    "integration_targets": request.known_systems,
                    "security_requirements": [
                        "human approval before execution",
                        "audit trail for decisions",
                        "repository boundary validation",
                    ],
                    "architecture_direction": "modular monolith first with clear bounded contexts",
                },
                (
                    "Solution proposal created with modules, integrations, security, "
                    "and architecture direction."
                ),
            ),
            FormationDocument(
                ArtifactType.DELIVERY_PLAN,
                "Delivery Plan",
                {
                    "phases": [
                        "intake",
                        "requirements",
                        "architecture",
                        "work package planning",
                        "implementation",
                        "validation",
                        "handover",
                    ],
                    "parallelization_rule": (
                        "Only tasks with approved interfaces and non-overlapping files "
                        "may run in parallel."
                    ),
                    "deadline": request.deadline,
                    "budget_signal": request.budget_signal,
                },
                (
                    "Delivery plan created with phases, parallelization rule, deadline, "
                    "and budget signal."
                ),
            ),
            FormationDocument(
                ArtifactType.FORMATION_QUALITY_REVIEW,
                "Formation Quality Review",
                {
                    "status": status,
                    "missing_information": missing,
                    "risk_register": self._risks(request, missing),
                    "confidence": "medium" if missing else "high",
                    "correction_attempt": request.correction_attempt,
                },
                "Quality review explains readiness, missing information, risks, and confidence.",
            ),
            FormationDocument(
                ArtifactType.FORMATION_APPROVAL_PACK,
                "Formation Approval Pack",
                {
                    "approval_state": "pending_human_review",
                    "recommended_decision": "request_clarification" if missing else "approve",
                    "operator_message": self._next_action(missing),
                    "traceability": traceability,
                },
                "Approval pack tells the operator whether to approve or ask targeted questions.",
            ),
        ]

    def _modules(self, idea: str, project_type: str | None) -> list[str]:
        words = idea.lower()
        modules = ["project governance", "requirements", "architecture", "delivery planning"]
        if project_type:
            modules.insert(0, project_type.replace("_", " "))
        if "dashboard" in words or "report" in words:
            modules.append("dashboards and reporting")
        if "api" in words or "integrat" in words:
            modules.append("API and integration")
        if "security" in words or "compliance" in words:
            modules.append("security and compliance")
        if "deploy" in words or "cloud" in words:
            modules.append("DevOps and infrastructure")
        return list(dict.fromkeys(modules))

    def _success_metrics(self, request: FormationRequest) -> list[str]:
        metrics = ["approved project plan", "clear execution graph", "reusable blueprint output"]
        if request.budget_signal:
            metrics.append("budget alignment visible before implementation")
        if request.deadline:
            metrics.append("delivery plan aligned to deadline")
        return metrics

    def _risks(self, request: FormationRequest, missing: list[str]) -> list[dict[str, str]]:
        risks = [
            {
                "risk": "unclear scope",
                "mitigation": "keep human approval before execution",
            }
        ]
        if missing:
            risks.append(
                {
                    "risk": "missing formation information",
                    "mitigation": "ask targeted clarification questions before approval",
                }
            )
        if not request.known_systems:
            risks.append(
                {
                    "risk": "unknown integrations",
                    "mitigation": "run infrastructure discovery before architecture approval",
                }
            )
        return risks
