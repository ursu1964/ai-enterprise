import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ai_enterprise.api.dependencies import (
    Actor,
    ActorDependency,
    SessionDependency,
    SettingsDependency,
    require_capability,
)
from ai_enterprise.api.schemas import (
    ApprovalRequest,
    ArtifactResponse,
    CreateProjectRequest,
    ProjectResponse,
    RunResponse,
    WorkPackageApprovalRequest,
    WorkPackageResponse,
)
from ai_enterprise.application.operator_job_resolution import (
    job_is_acknowledged,
    job_resolution,
    unresolved_problem_jobs,
)
from ai_enterprise.application.project_workflow import (
    ArtifactNotFoundError,
    InvalidProjectStateError,
    ProjectNotFoundError,
    ProjectWorkflowService,
)
from ai_enterprise.application.query.read_models import meaning_for
from ai_enterprise.application.workflow.service import WorkflowService
from ai_enterprise.infrastructure.database.models import (
    ArtifactModel,
    CrewRunModel,
    JobModel,
    ProjectModel,
    WorkPackageModel,
)
from ai_enterprise.infrastructure.database.workflow_models import (
    WorkflowInstanceModel,
    WorkflowTransitionModel,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def _count_phrase(count: int, singular: str, plural: str | None = None) -> str:
    label = singular if count == 1 else plural or f"{singular}s"
    return f"{count} {label}"


def _require_project_read(actor: Actor, project_id: uuid.UUID | None = None) -> None:
    if actor.actor_type != "human":
        raise HTTPException(status_code=403, detail="Human project authority is required")
    require_capability(
        actor,
        "project.read",
        "global" if project_id is None else f"project:{project_id}",
    )


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    session: SessionDependency, actor: ActorDependency
) -> list[ProjectResponse]:
    _require_project_read(actor)
    projects = (
        await session.scalars(select(ProjectModel).order_by(ProjectModel.updated_at.desc()))
    ).all()
    return [ProjectResponse.model_validate(project) for project in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> ProjectResponse:
    project = await session.get(ProjectModel, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    _require_project_read(actor, project_id)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}/intelligence")
async def project_intelligence(
    project_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> dict[str, object]:
    project = await session.get(ProjectModel, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    _require_project_read(actor, project_id)
    workflow = await session.scalar(
        select(WorkflowInstanceModel)
        .where(WorkflowInstanceModel.project_id == project_id)
        .order_by(WorkflowInstanceModel.updated_at.desc())
    )
    transitions = (
        list(
            (
                await session.scalars(
                    select(WorkflowTransitionModel)
                    .where(WorkflowTransitionModel.workflow_id == workflow.id)
                    .order_by(WorkflowTransitionModel.sequence)
                )
            ).all()
        )
        if workflow is not None
        else []
    )
    jobs = list(
        (
            await session.scalars(
                select(JobModel)
                .where(JobModel.project_id == project_id)
                .order_by(JobModel.created_at)
            )
        ).all()
    )
    runs = list(
        (
            await session.scalars(
                select(CrewRunModel)
                .where(CrewRunModel.project_id == project_id)
                .order_by(CrewRunModel.created_at)
            )
        ).all()
    )
    artifacts = list(
        (
            await session.scalars(
                select(ArtifactModel)
                .where(ArtifactModel.project_id == project_id)
                .order_by(ArtifactModel.created_at)
            )
        ).all()
    )
    work_packages = list(
        (
            await session.scalars(
                select(WorkPackageModel)
                .where(WorkPackageModel.project_id == project_id)
                .order_by(WorkPackageModel.created_at)
            )
        ).all()
    )
    phase_states = [
        ("intake", {"created", "draft", "intake"}),
        ("requirements", {"requirements_running", "waiting_requirements_approval"}),
        ("architecture", {"architecture_running", "waiting_architecture_approval"}),
        ("planning", {"planning_running", "waiting_work_package_approval"}),
        ("execution", {"execution_running"}),
        ("patch_review", {"patch_review_running", "waiting_integration_approval"}),
        ("integration", {"integrating"}),
        ("completed", {"completed"}),
    ]
    seen_states = {transition.current_state for transition in transitions}
    fallback_current_phase = _phase_from_project_status(project.status)
    current_state = fallback_current_phase if workflow is None else workflow.state
    current_phase = _phase_from_workflow_state(current_state) or fallback_current_phase
    current_index = next(
        (
            index
            for index, (_, states) in enumerate(phase_states)
            if current_phase == phase_states[index][0]
            or current_state in states
            or current_state == phase_states[index][0]
        ),
        0,
    )
    problem_jobs = unresolved_problem_jobs(jobs)
    historical_problem_jobs = [
        job
        for job in jobs
        if job.status in {"failed", "dead_letter", "abandoned"} and job_is_acknowledged(job)
    ]
    phases = []
    for index, (name, states) in enumerate(phase_states):
        phase_transitions = [
            transition for transition in transitions if transition.current_state in states
        ]
        artifact_proves_phase = _artifact_proves_phase(name, artifacts)
        job_proves_phase = _job_proves_phase(name, jobs)
        if current_state in states or current_state == name:
            status_value = "current"
        elif (
            phase_transitions
            or artifact_proves_phase
            or job_proves_phase
            or index < current_index
        ):
            status_value = "executed"
        else:
            status_value = "remaining"
        phase_evidence = _phase_evidence(name, phase_transitions, artifacts, jobs)
        is_current = status_value == "current"
        current_issues = [_classified_error(job) for job in problem_jobs] if is_current else []
        historical_issues = [
            _historical_issue(job) for job in historical_problem_jobs
        ] if is_current else []
        phase_confidence = _phase_confidence(
            status_value, phase_evidence, workflow, current_issues
        )
        phases.append(
            {
                "name": name,
                "label": name.replace("_", " ").title(),
                "status": status_value,
                "status_meaning": meaning_for(status_value),
                "confidence": phase_confidence,
                "confidence_detail": _phase_confidence_detail(
                    phase_confidence,
                    phase_evidence,
                    current_issues,
                ),
                "proof_status": _phase_proof_status(status_value, phase_evidence),
                "states": sorted(states),
                "transition_count": len(phase_transitions),
                "last_transition_at": (
                    None if not phase_transitions else phase_transitions[-1].occurred_at
                ),
                "details": [transition.reason for transition in phase_transitions[-3:]],
                "owner_crew": _owner_crew_for_phase(name, runs),
                "completed_evidence": phase_evidence,
                "remaining_work": _phase_remaining_work(name, status_value),
                "next_action": _phase_next_action(
                    name,
                    status_value,
                    workflow.recommended_operator_action if workflow is not None else None,
                ),
                "issue_summary": _phase_issue_summary(current_issues, historical_issues),
                "current_issues": current_issues,
                "historical_issues": historical_issues,
            }
        )
    remaining_count = sum(1 for phase in phases if phase["status"] == "remaining")
    project_type = _project_type(project)
    specialist_agents = _specialist_agents(project_type)
    economic_effects = _economic_effects(jobs, runs, artifacts, work_packages, phases)
    return {
        "project": ProjectResponse.model_validate(project).model_dump(mode="json"),
        "workflow": None
        if workflow is None
        else {
            "id": workflow.id,
            "state": workflow.state,
            "current_step": workflow.current_step,
            "recommended_operator_action": workflow.recommended_operator_action,
            "started_at": workflow.started_at,
            "completed_at": workflow.completed_at,
        },
        "project_phase": current_phase,
        "project_status_phase": fallback_current_phase,
        "phases": phases,
        "executed_steps": [transition.current_state for transition in transitions],
        "remaining_steps": [
            phase["name"] for phase in phases if phase["status"] == "remaining"
        ],
        "estimate": _estimate_remaining_work(transitions, remaining_count),
        "operating_state": {
            "degraded": workflow is None,
            "reason": None
            if workflow is not None
            else "Workflow tracking is not linked to this project.",
            "recommended_action": None
            if workflow is not None
            else "Start or relink the workflow before treating inferred phases as live execution.",
        },
        "telemetry": _telemetry(workflow, jobs, runs, artifacts, work_packages, phases),
        "calibration": _calibration(project, workflow, jobs, artifacts, phases),
        "errors": [
            _classified_error(job)
            for job in problem_jobs
        ],
        "current_issues": [_classified_error(job) for job in problem_jobs],
        "historical_issues": [_historical_issue(job) for job in historical_problem_jobs],
        "improvements": _improvements(problem_jobs, workflow, phases),
        "economic_effects": economic_effects,
        "reuse": {
            "repository_path": project.repository_path,
            "artifact_count": len(artifacts),
            "work_package_count": len(work_packages),
            "artifact_types": sorted({artifact.artifact_type for artifact in artifacts}),
            "template": _reusable_template(project, project_type),
        },
        "specialist_agents": specialist_agents,
        "blueprints": _blueprints(
            project, project_type, phases, specialist_agents, economic_effects
        ),
        "crew": [
            {
                "crew_name": run.crew_name,
                "status": run.status,
                "created_at": run.created_at,
                "error_message": run.error_message,
            }
            for run in runs
        ],
        "jobs": [
            {
                "id": job.id,
                "job_type": job.job_type,
                "status": job.status,
                "attempt_count": job.attempt_count,
                "last_error": job.last_error,
            }
            for job in jobs
        ],
        "life": {
            "known_states": sorted(seen_states),
            "transition_count": len(transitions),
            "job_count": len(jobs),
        },
    }


def _estimate_remaining_work(
    transitions: list[WorkflowTransitionModel],
    remaining_phase_count: int,
) -> dict[str, object]:
    if remaining_phase_count <= 0:
        return {
            "remaining_phase_count": 0,
            "estimated_minutes_remaining": 0,
            "basis": "Project has no remaining phases in the current read model.",
            "confidence": "complete",
            "label": "Complete",
            "historical_sample_count": 0,
            "average_phase_minutes": 0,
        }
    ordered = sorted(
        transition.occurred_at for transition in transitions if transition.occurred_at
    )
    durations = [
        (current - previous).total_seconds() / 60
        for previous, current in zip(ordered, ordered[1:], strict=False)
        if current > previous
    ]
    if durations:
        average = round(sum(durations) / len(durations), 1)
        return {
            "remaining_phase_count": remaining_phase_count,
            "estimated_minutes_remaining": max(1, round(average * remaining_phase_count)),
            "basis": (
                "Observed workflow transition timing from this project. Treat as calibrated "
                "when more phase history accumulates."
            ),
            "confidence": "calibrated" if len(durations) >= 3 else "observed",
            "label": "Calibrated estimate" if len(durations) >= 3 else "Observed estimate",
            "historical_sample_count": len(durations),
            "average_phase_minutes": average,
        }
    return {
        "remaining_phase_count": remaining_phase_count,
        "estimated_minutes_remaining": remaining_phase_count * 30,
        "basis": "Local heuristic until historical duration telemetry is available.",
        "confidence": "early",
        "label": "Early estimate",
        "historical_sample_count": 0,
        "average_phase_minutes": 30,
    }


def _project_type(project: ProjectModel) -> str:
    manifest = project.manifest if isinstance(project.manifest, dict) else {}
    manifest_type = manifest.get("project_type") or manifest.get("factory_type")
    if isinstance(manifest_type, str) and manifest_type:
        return manifest_type
    description = project.description.lower()
    if "dashboard" in description or "report" in description:
        return "dashboards_reporting"
    if "portal" in description or "web" in description or "mobile" in description:
        return "web_mobile_app_development"
    if "api" in description or "integration" in description:
        return "api_integration_development"
    return "ai_software_development"


def _telemetry(
    workflow: WorkflowInstanceModel | None,
    jobs: list[JobModel],
    runs: list[CrewRunModel],
    artifacts: list[ArtifactModel],
    work_packages: list[WorkPackageModel],
    phases: list[dict[str, object]],
) -> dict[str, object]:
    problem_count = len(unresolved_problem_jobs(jobs))
    completed_phases = sum(1 for phase in phases if phase["status"] == "executed")
    total_phases = len(phases)
    return {
        "always_active": True,
        "workflow_state": None if workflow is None else workflow.state,
        "phase_completion_percent": 0
        if total_phases == 0
        else round((completed_phases / total_phases) * 100, 1),
        "job_count": len(jobs),
        "problem_count": problem_count,
        "historical_problem_count": sum(
            1
            for job in jobs
            if job.status in {"failed", "dead_letter", "abandoned"}
            and job_is_acknowledged(job)
        ),
        "crew_run_count": len(runs),
        "artifact_count": len(artifacts),
        "work_package_count": len(work_packages),
        "signal": "attention_required" if problem_count else "nominal",
    }


def _economic_effects(
    jobs: list[JobModel],
    runs: list[CrewRunModel],
    artifacts: list[ArtifactModel],
    work_packages: list[WorkPackageModel],
    phases: list[dict[str, object]],
) -> dict[str, object]:
    completed_phase_count = sum(1 for phase in phases if phase["status"] == "executed")
    current_phase_count = sum(1 for phase in phases if phase["status"] == "current")
    problem_count = len(unresolved_problem_jobs(jobs))
    reusable_asset_count = len(artifacts) + len(work_packages)
    automation_units = len(runs) + sum(1 for job in jobs if job.status == "succeeded")
    return {
        "viability": "attention_required" if problem_count else "viable",
        "automation_units_completed": automation_units,
        "estimated_manual_hours_avoided": round(
            (completed_phase_count + current_phase_count) * 4.0, 1
        ),
        "reusable_asset_count": reusable_asset_count,
        "reuse_multiplier": round(1.0 + reusable_asset_count * 0.08, 2),
        "risk_items_prevented_or_exposed": problem_count
        + sum(1 for phase in phases if phase["status"] == "current"),
        "economic_basis": (
            "Heuristic proof signal from phases, jobs, crew runs, artifacts, and reusable work "
            "packages until calibrated business metrics are collected."
        ),
    }


def _calibration(
    project: ProjectModel,
    workflow: WorkflowInstanceModel | None,
    jobs: list[JobModel],
    artifacts: list[ArtifactModel],
    phases: list[dict[str, object]],
) -> list[dict[str, object]]:
    return [
        {
            "name": "manifest_integrity",
            "status": "passed" if project.manifest_hash else "attention",
            "detail": "Project manifest hash is available.",
        },
        {
            "name": "workflow_tracking",
            "status": "passed" if workflow is not None else "attention",
            "detail": "Workflow instance is linked to the project.",
        },
        {
            "name": "error_followup",
            "status": "attention"
            if unresolved_problem_jobs(jobs)
            else "passed",
            "detail": (
                "Unresolved failed work is visible in project intelligence. Reviewed historical "
                "failures remain evidence, not active risk."
            ),
        },
        {
            "name": "reuse_capture",
            "status": "passed" if artifacts else "attention",
            "detail": "Artifacts and work packages become reusable project template material.",
        },
        {
            "name": "phase_alignment",
            "status": "passed"
            if any(phase["status"] == "current" for phase in phases)
            else "attention",
            "detail": "The graph can identify a current execution phase.",
        },
    ]


def _improvements(
    problem_jobs: list[JobModel],
    workflow: WorkflowInstanceModel | None,
    phases: list[dict[str, object]],
) -> list[dict[str, str]]:
    improvements = []
    for job in problem_jobs[:5]:
        improvements.append(
            {
                "source": job.job_type,
                "recommendation": _job_recommendation(job),
                "status": "proposed",
            }
        )
    if workflow is None:
        improvements.append(
            {
                "source": "workflow_tracking",
                "recommendation": (
                    "Start or relink the workflow so every phase has live transition history."
                ),
                "status": "proposed",
            }
        )
    if not any(phase["status"] == "current" for phase in phases):
        improvements.append(
            {
                "source": "phase_alignment",
                "recommendation": (
                    "Calibrate project status and artifacts so the execution graph has a current "
                    "phase."
                ),
                "status": "proposed",
            }
        )
    if not improvements:
        improvements.append(
            {
                "source": "telemetry",
                "recommendation": (
                    "Continue collecting telemetry and promote completed artifacts into templates."
                ),
                "status": "active",
            }
        )
    return improvements


def _classified_error(job: JobModel) -> dict[str, object]:
    error = (job.last_error or "").lower()
    if "invalid json" in error:
        explanation = "A generated response did not match the required JSON contract."
        likely_cause = "Model output formatting or schema repair failed."
    elif "result.json" in error:
        explanation = "The execution container did not return the expected result artifact."
        likely_cause = "Artifact capture or execution-result contract failed."
    elif "head" in error or "not a git repository" in error:
        explanation = "The repository is not prepared for workflow execution."
        likely_cause = "The project path may be missing a valid Git branch or initial commit."
    elif job.status == "dead_letter":
        explanation = "The job exhausted retry handling and needs recovery attention."
        likely_cause = "Repeated failure exceeded the configured retry policy."
    else:
        explanation = "A worker job failed and needs operator review."
        likely_cause = "The exact cause needs diagnostic inspection."
    return {
        "job_id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "failure_class": job.last_failure_class,
        "explanation": explanation,
        "likely_cause": likely_cause,
        "next_action": _job_recommendation(job),
        "raw_diagnostic": job.last_error,
    }


def _historical_issue(job: JobModel) -> dict[str, object]:
    resolution = job_resolution(job) or {}
    return {
        "job_id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "status_meaning": meaning_for("dead_letter" if job.status == "dead_letter" else job.status),
        "resolution": resolution,
        "explanation": "Reviewed history. The evidence is preserved but is not current risk.",
        "operator_action": "Use this as learning evidence; do not block current project health.",
        "raw_diagnostic": job.last_error,
    }


def _job_recommendation(job: JobModel) -> str:
    error = (job.last_error or "").lower()
    if "invalid json" in error:
        return (
            "Tighten model output schema repair and add a deterministic fallback for this crew "
            "step."
        )
    if "result.json" in error:
        return (
            "Inspect execution container artifact capture and enforce result contract before retry."
        )
    if job.status == "dead_letter":
        return (
            "Create a recovery work package from the dead-letter job and preserve the failure as "
            "training evidence."
        )
    return "Review job attempts, capture root cause, and convert the fix into a reusable checklist."


def _reusable_template(project: ProjectModel, project_type: str) -> dict[str, object]:
    return {
        "template_key": f"{project_type}.{project.name.lower().replace(' ', '_')}",
        "project_type": project_type,
        "default_branch": project.default_branch,
        "repository_root": project.repository_path,
        "manifest_hash": project.manifest_hash,
        "future_use": (
            "Can seed future manifesto projects with the same type, agents, phases, and checks."
        ),
    }


def _blueprints(
    project: ProjectModel,
    project_type: str,
    phases: list[dict[str, object]],
    specialist_agents: list[dict[str, str]],
    economic_effects: dict[str, object],
) -> list[dict[str, object]]:
    phase_names = [str(phase["name"]) for phase in phases]
    agent_keys = [agent["agent_key"] for agent in specialist_agents]
    completed_phase_count = sum(1 for phase in phases if phase["status"] == "executed")
    evidence_count = 0
    problem_count = 0
    for phase in phases:
        completed_evidence = phase.get("completed_evidence")
        if isinstance(completed_evidence, list):
            evidence_count += len(completed_evidence)
        current_issues = phase.get("current_issues")
        if isinstance(current_issues, list):
            problem_count += len(current_issues)
    lifecycle = _blueprint_lifecycle(
        completed_phase_count=completed_phase_count,
        evidence_count=evidence_count,
        problem_count=problem_count,
        viability=str(economic_effects["viability"]),
    )
    improvement_proposals = _blueprint_improvement_proposals(phases)
    base = {
        "lifecycle": lifecycle,
        "source_project_id": str(project.id),
        "source_project_name": project.name,
        "source_project_type": project_type,
        "evidence_count": evidence_count,
        "completed_phase_count": completed_phase_count,
        "lifecycle_detail": _blueprint_lifecycle_detail(
            lifecycle=lifecycle,
            completed_phase_count=completed_phase_count,
            evidence_count=evidence_count,
            problem_count=problem_count,
            viability=str(economic_effects["viability"]),
        ),
        "reuse_proof": {
            "economic_viability": economic_effects["viability"],
            "reuse_multiplier": economic_effects["reuse_multiplier"],
            "reusable_asset_count": economic_effects["reusable_asset_count"],
            "manual_hours_avoided": economic_effects["estimated_manual_hours_avoided"],
        },
        "improvement_proposals": improvement_proposals,
    }
    return [
        {
            **base,
            "blueprint_key": f"{project_type}.delivery_workflow",
            "title": "Reusable delivery workflow",
            "kind": "workflow_pattern",
            "reusable_for": project_type,
            "source_phase": "workflow",
            "pattern": {
                "phases": phase_names,
                "approval_gates": ["requirements", "architecture", "work_package"],
                "telemetry_required": True,
                "calibration_required": True,
            },
            "proof": {
                "source_project_id": str(project.id),
                "economic_viability": economic_effects["viability"],
            },
        },
        {
            **base,
            "blueprint_key": f"{project_type}.specialist_crew",
            "title": "Specialist crew pattern",
            "kind": "agent_team_pattern",
            "reusable_for": project_type,
            "source_phase": "crew",
            "pattern": {
                "agents": agent_keys,
                "coordination": "manifesto_to_workflow_to_verified_artifacts",
                "mistake_prevention": ["availability", "calibration", "review", "telemetry"],
            },
            "proof": {
                "source_project_id": str(project.id),
                "agent_count": len(agent_keys),
            },
        },
        {
            **base,
            "blueprint_key": f"{project_type}.economic_proof",
            "title": "Economic proof pattern",
            "kind": "business_effect_pattern",
            "reusable_for": project_type,
            "source_phase": "economic_proof",
            "pattern": {
                "signals": [
                    "manual_hours_avoided",
                    "reuse_multiplier",
                    "risk_items_prevented_or_exposed",
                    "automation_units_completed",
                ],
                "proof_method": "telemetry_plus_artifacts_plus_jobs",
            },
            "proof": economic_effects,
        },
    ]


def _blueprint_lifecycle(
    *,
    completed_phase_count: int,
    evidence_count: int,
    problem_count: int,
    viability: str,
) -> str:
    if problem_count:
        return "improved"
    if viability == "viable" and completed_phase_count >= 7 and evidence_count >= 4:
        return "reusable"
    if evidence_count:
        return "reviewed"
    return "candidate"


def _blueprint_lifecycle_detail(
    *,
    lifecycle: str,
    completed_phase_count: int,
    evidence_count: int,
    problem_count: int,
    viability: str,
) -> dict[str, object]:
    blockers: list[str] = []
    if completed_phase_count < 7:
        blockers.append("complete all delivery phases")
    if evidence_count < 4:
        blockers.append("bind at least four evidence items")
    if viability != "viable":
        blockers.append("record viable economic proof")
    if problem_count:
        blockers.append("resolve current issues before reuse")
    if lifecycle == "reusable":
        return {
            "label": "Reusable",
            "trust_level": "reuse_ready",
            "meaning": "This blueprint has enough delivery proof to seed future work.",
            "next_action": "Promote through the blueprint catalog with its evidence bundle.",
            "promotion_blockers": [],
        }
    if lifecycle == "reviewed":
        return {
            "label": "Reviewed candidate",
            "trust_level": "reviewed",
            "meaning": "Evidence exists, but the blueprint still needs proof before reuse.",
            "next_action": "Collect the remaining proof and review it for catalog promotion.",
            "promotion_blockers": blockers,
        }
    if lifecycle == "improved":
        return {
            "label": "Improvement needed",
            "trust_level": "guardrail_required",
            "meaning": "Current issues should become guardrails before this pattern is reused.",
            "next_action": "Resolve failures, attach evidence, and update the reusable pattern.",
            "promotion_blockers": blockers,
        }
    if lifecycle == "deprecated":
        return {
            "label": "Deprecated",
            "trust_level": "do_not_reuse",
            "meaning": "This blueprint has been replaced or retired.",
            "next_action": "Use the superseding blueprint before starting new work.",
            "promotion_blockers": ["use superseding blueprint"],
        }
    return {
        "label": "Candidate",
        "trust_level": "candidate",
        "meaning": "The pattern is visible but not yet reviewed or proven for reuse.",
        "next_action": "Finish execution and collect governed evidence before promotion.",
        "promotion_blockers": blockers,
    }


def _blueprint_improvement_proposals(
    phases: list[dict[str, object]],
) -> list[dict[str, object]]:
    proposals: list[dict[str, object]] = []
    for phase in phases:
        issues = phase.get("current_issues")
        if not isinstance(issues, list):
            continue
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            phase_name = str(phase["name"])
            failure_class = str(issue.get("failure_class") or "unknown")
            job_id = str(issue.get("job_id") or "")
            proposals.append(
                {
                    "proposal_key": (
                        f"blueprint.{phase_name}.{failure_class}.guardrail"
                    ),
                    "phase": phase_name,
                    "failure_class": failure_class,
                    "proposal_type": "guardrail_or_template_update",
                    "status": "proposed",
                    "proposal": str(
                        issue.get("next_action")
                        or "Convert this repeated failure into a guardrail or template."
                    ),
                    "evidence_required": True,
                    "evidence_sources": [
                        {
                            "type": "project_job_failure",
                            "job_id": job_id,
                            "job_type": str(issue.get("job_type") or "unknown"),
                            "status": str(issue.get("status") or "unknown"),
                        }
                    ],
                    "operator_action": (
                        "Review the failed job evidence, update the reusable "
                        "blueprint, and keep the proposal in review until the "
                        "guardrail is verified."
                    ),
                }
            )
    return proposals[:5]


def _specialist_agents(project_type: str) -> list[dict[str, str]]:
    base_agents = [
        (
            "requirements_agent",
            "requirements",
            "Extracts objectives, constraints, and acceptance criteria.",
        ),
        (
            "architecture_agent",
            "architecture",
            "Creates structure, interfaces, risks, and technical plan.",
        ),
        ("implementation_agent", "implementation", "Builds scoped work packages and code changes."),
        ("test_agent", "verification", "Runs tests, evidence checks, and regression verification."),
        (
            "review_agent",
            "review",
            "Reviews patches, security, correctness, and integration readiness.",
        ),
        (
            "integration_agent",
            "integration",
            "Integrates approved changes and watches recovery signals.",
        ),
        (
            "evolution_agent",
            "evolution",
            "Turns telemetry and errors into improvements and templates.",
        ),
    ]
    specialists = {
        "dashboards_reporting": (
            "dashboard_agent",
            "analytics",
            "Designs operational dashboards, indicators, and reporting views.",
        ),
        "devops_infrastructure": (
            "infrastructure_agent",
            "infrastructure",
            "Plans deployment, runtime, observability, and cloud automation.",
        ),
        "api_integration_development": (
            "integration_design_agent",
            "api",
            "Designs API contracts, integrations, idempotency, and compatibility checks.",
        ),
        "web_mobile_app_development": (
            "experience_agent",
            "frontend",
            "Designs user journeys, screens, and interaction quality.",
        ),
    }
    agents = list(base_agents)
    if project_type in specialists:
        agents.insert(2, specialists[project_type])
    return [
        {"agent_key": key, "specialty": specialty, "mission": mission, "status": "ready"}
        for key, specialty, mission in agents
    ]


def _phase_from_project_status(status: str) -> str:
    status_value = str(status)
    if status_value in {"created", "draft"}:
        return "intake"
    if status_value.startswith("requirements") or "requirements" in status_value:
        return "requirements"
    if status_value.startswith("architecture") or "architecture" in status_value:
        return "architecture"
    if status_value.startswith("work_package") or "work_package" in status_value:
        if status_value == "work_package_approved":
            return "execution"
        return "planning"
    return "requirements"


def _phase_from_workflow_state(state: str | None) -> str | None:
    if state is None:
        return None
    state_value = str(state)
    if state_value in {"created", "draft", "intake"}:
        return "intake"
    if "requirements" in state_value:
        return "requirements"
    if "architecture" in state_value:
        return "architecture"
    if "work_package" in state_value or "planning" in state_value:
        return "planning"
    if "execution" in state_value:
        return "execution"
    if "patch_review" in state_value or "review" in state_value:
        return "patch_review"
    if "integration" in state_value or "integrating" in state_value:
        return "integration"
    if state_value == "completed":
        return "completed"
    return None


def _artifact_proves_phase(name: str, artifacts: list[ArtifactModel]) -> bool:
    artifact_types = {artifact.artifact_type for artifact in artifacts}
    return (
        name == "requirements"
        and "requirements_specification" in artifact_types
        or name == "architecture"
        and "architecture_specification" in artifact_types
        or name == "planning"
        and "work_package" in artifact_types
        or name == "execution"
        and "execution-log" in artifact_types
        or name == "patch_review"
        and "patch-review-report" in artifact_types
    )


def _phase_evidence(
    name: str,
    transitions: list[WorkflowTransitionModel],
    artifacts: list[ArtifactModel],
    jobs: list[JobModel],
) -> list[str]:
    evidence: list[str] = []
    if transitions:
        evidence.append(_count_phrase(len(transitions), "workflow transition"))
    if _artifact_proves_phase(name, artifacts):
        evidence.append("phase artifact")
    if _job_proves_phase(name, jobs):
        evidence.append("worker job evidence")
    return evidence


def _phase_confidence(
    status: str,
    evidence: list[str],
    workflow: WorkflowInstanceModel | None,
    current_issues: list[dict[str, object]],
) -> str:
    if current_issues:
        return "needs review"
    if status == "current" and workflow is not None:
        return "live workflow"
    if evidence:
        return "evidence backed"
    if status == "remaining":
        return "planned"
    return "inferred"


def _phase_confidence_detail(
    confidence: str,
    evidence: list[str],
    current_issues: list[dict[str, object]],
) -> dict[str, object]:
    if confidence == "needs review":
        score = max(10, 45 - (len(current_issues) * 10))
    elif confidence == "live workflow":
        score = min(95, 70 + (len(evidence) * 5))
    elif confidence == "evidence backed":
        score = min(85, 55 + (len(evidence) * 10))
    elif confidence == "planned":
        score = 25
    else:
        score = 35
    meaning = meaning_for(confidence)
    return {
        "state": confidence,
        "score": score,
        "label": meaning["label"],
        "severity": meaning["severity"],
        "meaning": meaning["meaning"],
        "operator_action": meaning["operator_action"],
        "evidence_count": len(evidence),
        "current_blocker_count": len(current_issues),
    }


def _phase_proof_status(status: str, evidence: list[str]) -> dict[str, object]:
    if evidence:
        return {
            "state": "evidence_backed",
            "available": True,
            "evidence_count": len(evidence),
            "operator_action": "Use completed evidence when reviewing this phase.",
        }
    if status == "current":
        return {
            "state": "waiting_for_current_phase_proof",
            "available": False,
            "evidence_count": 0,
            "operator_action": "Finish the current gate so phase proof can be recorded.",
        }
    if status == "remaining":
        return {
            "state": "not_started",
            "available": False,
            "evidence_count": 0,
            "operator_action": "Complete earlier phases before expecting proof here.",
        }
    return {
        "state": "inferred_without_direct_proof",
        "available": False,
        "evidence_count": 0,
        "operator_action": "Inspect workflow history before relying on this inferred phase.",
    }


def _phase_issue_summary(
    current_issues: list[dict[str, object]],
    historical_issues: list[dict[str, object]],
) -> dict[str, object]:
    current_count = len(current_issues)
    history_count = len(historical_issues)
    return {
        "current_count": current_count,
        "historical_count": history_count,
        "state": "needs_action" if current_count else "clear",
        "operator_action": (
            "Open Problems and resolve current blockers for this phase."
            if current_count
            else "No active blockers are attached to this phase."
        ),
    }


def _owner_crew_for_phase(name: str, runs: list[CrewRunModel]) -> str:
    phase_keywords = {
        "requirements": ("requirements",),
        "architecture": ("architecture",),
        "planning": ("work_package", "planning"),
        "execution": ("execution", "implementation"),
        "patch_review": ("review",),
        "integration": ("integration",),
    }.get(name, (name,))
    for run in reversed(runs):
        crew_name = run.crew_name.lower()
        if any(keyword in crew_name for keyword in phase_keywords):
            return run.crew_name
    if name in {"intake", "completed"}:
        return "workflow-engine"
    return f"{name.replace('_', ' ')} crew"


def _phase_remaining_work(name: str, status: str) -> str:
    if status == "executed":
        return "Preserve evidence and continue to later phases."
    if status == "current":
        return "Finish the current gate and record the next transition."
    return {
        "requirements": "Produce and approve requirements evidence.",
        "architecture": "Produce and approve architecture evidence.",
        "planning": "Create and approve work packages.",
        "execution": "Run implementation work under worker control.",
        "patch_review": "Review implementation evidence before integration.",
        "integration": "Integrate approved changes and verify recovery signals.",
        "completed": "Collect completion evidence and reusable blueprints.",
    }.get(name, "Wait for earlier phases to complete.")


def _phase_next_action(
    name: str,
    status: str,
    workflow_action: str | None,
) -> str:
    if status == "current" and workflow_action:
        return workflow_action
    if status == "executed":
        return "Use this phase evidence when reviewing project proof."
    if status == "current":
        return "Complete the current phase and record the workflow transition."
    return {
        "requirements": "Start requirements when intake is complete.",
        "architecture": "Approve requirements before architecture starts.",
        "planning": "Approve architecture before work-package planning starts.",
        "execution": "Approve the work package before execution starts.",
        "patch_review": "Run implementation before patch review.",
        "integration": "Approve patch review before integration.",
        "completed": "Verify all evidence before marking the project complete.",
    }.get(name, "Continue the guided workflow.")


def _job_proves_phase(name: str, jobs: list[JobModel]) -> bool:
    succeeded_types = {job.job_type for job in jobs if job.status == "succeeded"}
    return (
        name == "planning"
        and "plan_work_package" in succeeded_types
        or name == "execution"
        and "execute_work_package" in succeeded_types
        or name == "patch_review"
        and "review_candidate_patch" in succeeded_types
        or name == "integration"
        and "integrate_approved_patch" in succeeded_types
    )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    request: CreateProjectRequest,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ProjectResponse:
    service = ProjectWorkflowService(
        session=session,
        settings=settings,
    )

    project = await service.create_project(
        name=request.name,
        description=request.description,
        repository_path=request.repository_path,
        repository_url=request.repository_url,
        default_branch=request.default_branch,
        actor_id="local-user",
        manifest=request.manifest,
        project_type=request.project_type,
    )

    return ProjectResponse.model_validate(project)


@router.post(
    "/{project_id}/requirements-runs",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_requirements_run(
    project_id: uuid.UUID,
    session: SessionDependency,
    settings: SettingsDependency,
) -> RunResponse:
    service = ProjectWorkflowService(
        session=session,
        settings=settings,
    )

    try:
        run = await service.queue_requirements_run(
            project_id=project_id,
            actor_id="local-user",
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except InvalidProjectStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return RunResponse.model_validate(run)


@router.get(
    "/{project_id}/artifacts",
    response_model=list[ArtifactResponse],
)
async def list_artifacts(
    project_id: uuid.UUID,
    session: SessionDependency,
) -> list[ArtifactResponse]:
    result = await session.execute(
        select(ArtifactModel)
        .where(ArtifactModel.project_id == project_id)
        .order_by(ArtifactModel.created_at)
    )

    return [ArtifactResponse.model_validate(artifact) for artifact in result.scalars().all()]


@router.post(
    "/{project_id}/artifacts/{artifact_id}/approval",
    response_model=ProjectResponse,
)
async def approve_artifact(
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    request: ApprovalRequest,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ProjectResponse:
    service = ProjectWorkflowService(
        session=session,
        settings=settings,
    )

    try:
        project = await service.approve_requirements(
            project_id=project_id,
            artifact_id=artifact_id,
            decision=request.decision,
            reviewer=request.reviewer,
            comment=request.comment,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ArtifactNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Artifact not found") from exc
    except InvalidProjectStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await WorkflowService(session, settings).notify(project_id)
    return ProjectResponse.model_validate(project)


@router.post(
    "/{project_id}/architecture-runs",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_architecture_run(
    project_id: uuid.UUID,
    session: SessionDependency,
    settings: SettingsDependency,
) -> RunResponse:
    service = ProjectWorkflowService(
        session=session,
        settings=settings,
    )

    try:
        run = await service.queue_architecture_run(
            project_id=project_id,
            actor_id="local-user",
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        ) from exc
    except ArtifactNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except InvalidProjectStateError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return RunResponse.model_validate(run)


@router.post(
    "/{project_id}/architecture-artifacts/{artifact_id}/approval",
    response_model=ProjectResponse,
)
async def approve_architecture_artifact(
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    request: ApprovalRequest,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ProjectResponse:
    service = ProjectWorkflowService(
        session=session,
        settings=settings,
    )

    try:
        project = await service.approve_architecture(
            project_id=project_id,
            artifact_id=artifact_id,
            decision=request.decision,
            reviewer=request.reviewer,
            comment=request.comment,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        ) from exc
    except ArtifactNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Artifact not found",
        ) from exc
    except InvalidProjectStateError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    await WorkflowService(session, settings).notify(project_id)
    return ProjectResponse.model_validate(project)


@router.post(
    "/{project_id}/work-package-runs",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_work_package_planning(
    project_id: uuid.UUID,
    session: SessionDependency,
    settings: SettingsDependency,
) -> RunResponse:
    service = ProjectWorkflowService(
        session=session,
        settings=settings,
    )

    try:
        run = await service.queue_work_package_planning(
            project_id=project_id,
            actor_id="local-user",
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        ) from exc
    except ArtifactNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except InvalidProjectStateError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return RunResponse.model_validate(run)


@router.get(
    "/{project_id}/work-packages",
    response_model=list[WorkPackageResponse],
)
async def list_work_packages(
    project_id: uuid.UUID,
    session: SessionDependency,
) -> list[WorkPackageResponse]:
    result = await session.execute(
        select(WorkPackageModel)
        .where(WorkPackageModel.project_id == project_id)
        .order_by(WorkPackageModel.created_at)
    )

    return [WorkPackageResponse.model_validate(item) for item in result.scalars().all()]


@router.post(
    "/{project_id}/work-packages/{work_package_id}/approval",
    response_model=WorkPackageResponse,
)
async def approve_work_package(
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    request: WorkPackageApprovalRequest,
    session: SessionDependency,
    settings: SettingsDependency,
) -> WorkPackageResponse:
    service = ProjectWorkflowService(
        session=session,
        settings=settings,
    )

    try:
        work_package = await service.approve_work_package(
            project_id=project_id,
            work_package_id=work_package_id,
            decision=request.decision,
            reviewer=request.reviewer,
            comment=request.comment,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        ) from exc
    except ArtifactNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Work package not found",
        ) from exc
    except InvalidProjectStateError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    await WorkflowService(session, settings).notify(project_id)
    return WorkPackageResponse.model_validate(work_package)
