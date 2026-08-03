from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ai_enterprise.api.dependencies import (
    Actor,
    ActorDependency,
    SessionDependency,
    require_capability,
)
from ai_enterprise.application.operator_job_resolution import (
    job_is_acknowledged,
    job_resolution,
    unresolved_problem_jobs,
)
from ai_enterprise.application.query.read_models import (
    meaning_for,
    source_contract,
    status_read_model,
)
from ai_enterprise.infrastructure.database.models import (
    ArtifactModel,
    AuditEventModel,
    CrewRunModel,
    JobModel,
    ProjectModel,
    WorkPackageModel,
)
from ai_enterprise.infrastructure.database.workflow_models import WorkflowInstanceModel
from ai_enterprise.infrastructure.enterprise_kernel.models import (
    EnterpriseModuleModel,
    EnterpriseResourceModel,
    EnterpriseScheduleModel,
    OperatingMaturitySnapshotModel,
    OrganizationalThreadModel,
)
from ai_enterprise.infrastructure.jobs.models import WorkerInstanceModel
from ai_enterprise.infrastructure.knowledge.models import KnowledgeItemModel
from ai_enterprise.infrastructure.performance.models import (
    LearningProposalModel,
    PerformanceMetricModel,
)

router = APIRouter(prefix="/query", tags=["query-platform"])

def _require_query_read(actor: Actor, project_id: uuid.UUID | None = None) -> None:
    if actor.actor_type != "human":
        raise HTTPException(403, "Human query authority is required")
    require_capability(
        actor,
        "query.read",
        "global" if project_id is None else f"project:{project_id}",
    )


def _status_counts(rows: list[Any], field: str = "status") -> dict[str, int]:
    return dict(Counter(str(getattr(row, field, "unknown")) for row in rows))


def _latest_time(rows: list[Any], field: str) -> datetime | None:
    values = [getattr(row, field, None) for row in rows]
    timestamps = [value for value in values if isinstance(value, datetime)]
    return max(timestamps) if timestamps else None


def _count_phrase(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else plural or singular + 's'}"


def _resolution_counts(jobs: list[JobModel]) -> dict[str, int]:
    states = [
        resolution["state"]
        for job in jobs
        if (resolution := job_resolution(job)) is not None and "state" in resolution
    ]
    return dict(Counter(str(state) for state in states))


def _recommendations(
    *,
    projects: list[ProjectModel],
    jobs: list[JobModel],
    workers: list[WorkerInstanceModel],
    workflows: list[WorkflowInstanceModel],
    schedules: list[EnterpriseScheduleModel],
) -> list[dict[str, str]]:
    failed_jobs = unresolved_problem_jobs(jobs)
    blocked_schedules = [item for item in schedules if item.state == "blocked"]
    online_workers = [worker for worker in workers if worker.status == "online"]
    missing_workflow_projects = {
        project.id for project in projects
    } - {workflow.project_id for workflow in workflows}

    items: list[dict[str, str]] = []
    if failed_jobs:
        items.append(
            {
                "priority": "urgent",
                "title": "Resolve blocked work",
                "message": (
                    f"{len(failed_jobs)} work item(s) need recovery review. Open Problems, "
                    "review the human explanation, then retry only after the cause is clear."
                ),
                "next_action": "Open the Problems dashboard.",
            }
        )
    if blocked_schedules:
        items.append(
            {
                "priority": "high",
                "title": "Unblock enterprise schedules",
                "message": (
                    f"{len(blocked_schedules)} governed schedule(s) cannot dispatch. "
                    "Check dependencies, approval gates, and resource claims."
                ),
                "next_action": "Open Enterprise Kernel schedules.",
            }
        )
    if missing_workflow_projects:
        items.append(
            {
                "priority": "medium",
                "title": "Link projects to workflows",
                "message": (
                    f"{len(missing_workflow_projects)} project(s) exist without a durable "
                    "workflow. Start or relink the workflow before presenting execution proof."
                ),
                "next_action": "Open Projects and start the governed workflow.",
            }
        )
    if projects and not online_workers:
        items.append(
            {
                "priority": "high",
                "title": "Start worker capacity",
                "message": "Projects exist, but no online worker instance is visible.",
                "next_action": "Start the worker service and check worker heartbeat.",
            }
        )
    if not items:
        items.append(
            {
                "priority": "normal",
                "title": "Continue controlled delivery",
                "message": "The operating picture has no urgent blockers.",
                "next_action": "Create the next manifesto or inspect project proof.",
            }
        )
    return items


def _graph(
    *,
    projects: list[ProjectModel],
    jobs: list[JobModel],
    workers: list[WorkerInstanceModel],
    workflows: list[WorkflowInstanceModel],
    resource_count: int,
    module_count: int,
    knowledge_count: int,
) -> dict[str, list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = [
        {
            "id": "enterprise",
            "label": "Enterprise Factory",
            "kind": "enterprise",
            **status_read_model("active"),
            "human_summary": (
                "The central operating system coordinating projects, crews, proof, "
                "and reusable knowledge."
            ),
        },
        {
            "id": "resources",
            "label": "Managed Resources",
            "kind": "resource-group",
            **status_read_model("active" if resource_count else "empty"),
            "human_summary": f"{resource_count} enterprise resource(s) are registered.",
        },
        {
            "id": "modules",
            "label": "Enterprise Modules",
            "kind": "module-group",
            **status_read_model("active" if module_count else "empty"),
            "human_summary": f"{module_count} governed module(s) are registered.",
        },
        {
            "id": "knowledge",
            "label": "Reusable Knowledge",
            "kind": "knowledge-group",
            **status_read_model("active" if knowledge_count else "empty"),
            "human_summary": (
                f"{knowledge_count} approved knowledge item(s) can inform future projects."
            ),
        },
    ]
    edges: list[dict[str, Any]] = [
        {"from": "enterprise", "to": "resources", "label": "governs"},
        {"from": "enterprise", "to": "modules", "label": "operates"},
        {"from": "enterprise", "to": "knowledge", "label": "learns"},
    ]
    for project in projects:
        project_node = f"project:{project.id}"
        nodes.append(
            {
                "id": project_node,
                "label": project.name,
                "kind": "project",
                **status_read_model(project.status),
                "human_summary": (
                    f"{project.name} is {meaning_for(project.status)['label']}. "
                    "Open it to inspect workflow, work, proof, and reusable blueprints."
                ),
            }
        )
        edges.append({"from": "enterprise", "to": project_node, "label": "creates"})
    workflow_by_project = {workflow.project_id: workflow for workflow in workflows}
    for project in projects:
        workflow = workflow_by_project.get(project.id)
        if workflow is None:
            continue
        workflow_node = f"workflow:{workflow.id}"
        nodes.append(
            {
                "id": workflow_node,
                "label": workflow.current_step or workflow.state,
                "kind": "workflow",
                **status_read_model(workflow.state),
                "human_summary": (
                    f"The workflow is at {workflow.current_step or workflow.state}. "
                    "Recommended action: "
                    f"{workflow.recommended_operator_action or 'continue monitoring'}."
                ),
            }
        )
        edges.append(
            {"from": f"project:{project.id}", "to": workflow_node, "label": "executes"}
        )
    for job in jobs[:25]:
        job_node = f"job:{job.id}"
        nodes.append(
            {
                "id": job_node,
                "label": job.job_type.replace("_", " ").title(),
                "kind": "job",
                **status_read_model(job.status),
                "human_summary": (
                    f"{job.job_type.replace('_', ' ')} is {meaning_for(job.status)['label']}. "
                    f"Attempt {job.attempt_count} of {job.max_attempts}."
                ),
            }
        )
        edges.append({"from": f"project:{job.project_id}", "to": job_node, "label": "has work"})
    for worker in workers[:12]:
        worker_node = f"worker:{worker.worker_id}"
        nodes.append(
            {
                "id": worker_node,
                "label": worker.profile,
                "kind": "worker",
                **status_read_model(worker.status),
                "human_summary": (
                    f"{worker.profile} worker is {meaning_for(worker.status)['label']}."
                ),
            }
        )
        edges.append({"from": "enterprise", "to": worker_node, "label": "capacity"})
    return {"nodes": nodes, "edges": edges}


def _task_summary(
    jobs: list[JobModel], work_packages: list[WorkPackageModel]
) -> dict[str, int]:
    done = sum(1 for job in jobs if job.status == "succeeded")
    active = sum(1 for job in jobs if job.status in {"queued", "running", "leased", "retry_wait"})
    problems = len(unresolved_problem_jobs(jobs))
    standby = sum(
        1
        for package in work_packages
        if str(getattr(package.status, "value", package.status))
        in {"awaiting_approval", "approved", "planned"}
    )
    return {
        "done": done,
        "active": active,
        "standby": standby,
        "problems": problems,
        "total": done + active + standby + problems,
    }


def _project_phase_from_workflow(workflow: WorkflowInstanceModel | None) -> str:
    if workflow is None:
        return "intake"
    state = workflow.state
    if "requirements" in state:
        return "requirements"
    if "architecture" in state:
        return "architecture"
    if "work_package" in state or "planning" in state:
        return "planning"
    if "execution" in state:
        return "execution"
    if "integration" in state:
        return "integration"
    if "completed" in state:
        return "completed"
    return state.replace("_", " ")


def _phase_owner(phase: str, crews: list[CrewRunModel], jobs: list[JobModel]) -> str:
    phase_keywords = {
        "requirements": ("requirements",),
        "architecture": ("architecture",),
        "planning": ("planning", "work_package"),
        "execution": ("execution", "implementation"),
        "integration": ("integration",),
    }.get(phase, (phase,))
    for crew in reversed(crews):
        crew_name = crew.crew_name.lower()
        if any(keyword in crew_name for keyword in phase_keywords):
            return crew.crew_name
    for job in jobs:
        job_type = job.job_type.lower()
        if any(keyword in job_type for keyword in phase_keywords):
            return job.job_type.replace("_", " ")
    if phase == "intake":
        return "manifesto factory"
    if phase == "completed":
        return "workflow engine"
    return f"{phase.replace('_', ' ')} crew"


def _phase_evidence(
    phase: str,
    workflow: WorkflowInstanceModel | None,
    jobs: list[JobModel],
    crews: list[CrewRunModel],
    packages: list[WorkPackageModel],
) -> list[str]:
    evidence: list[str] = []
    if workflow is not None:
        evidence.append("linked workflow")
    succeeded_jobs = [
        job for job in jobs if job.status == "succeeded" and phase in job.job_type
    ]
    if succeeded_jobs:
        evidence.append(f"{len(succeeded_jobs)} completed worker job(s)")
    matching_crews = [crew for crew in crews if phase in crew.crew_name.lower()]
    if matching_crews:
        evidence.append(f"{len(matching_crews)} crew signal(s)")
    if phase in {"planning", "execution"} and packages:
        evidence.append(f"{len(packages)} work package record(s)")
    return evidence


def _phase_confidence(
    workflow: WorkflowInstanceModel | None,
    evidence: list[str],
    current_issues: list[dict[str, Any]],
) -> str:
    if current_issues:
        return "needs review"
    if workflow is not None:
        return "live workflow"
    if evidence:
        return "evidence backed"
    return "early estimate"


def _phase_confidence_detail(
    confidence: str,
    evidence: list[str],
    current_issues: list[dict[str, Any]],
) -> dict[str, Any]:
    if confidence == "needs review":
        score = max(10, 45 - (len(current_issues) * 10))
    elif confidence == "live workflow":
        score = min(95, 70 + (len(evidence) * 5))
    elif confidence == "evidence backed":
        score = min(85, 55 + (len(evidence) * 10))
    else:
        score = 30
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


def _phase_proof_status(
    evidence: list[str], workflow: WorkflowInstanceModel | None
) -> dict[str, object]:
    if evidence:
        return {
            "state": "evidence_backed",
            "available": True,
            "evidence_count": len(evidence),
            "operator_action": "Use completed evidence when reviewing this phase.",
        }
    if workflow is not None:
        return {
            "state": "waiting_for_current_phase_proof",
            "available": False,
            "evidence_count": 0,
            "operator_action": "Let the workflow record phase movement or artifacts.",
        }
    return {
        "state": "not_started",
        "available": False,
        "evidence_count": 0,
        "operator_action": "Start or relink the workflow before expecting phase proof.",
    }


def _phase_issue_summary(
    current_issues: list[dict[str, Any]],
    historical_issues: list[dict[str, Any]],
) -> dict[str, object]:
    current_count = len(current_issues)
    historical_count = len(historical_issues)
    return {
        "current_count": current_count,
        "historical_count": historical_count,
        "state": "needs_action" if current_count else "clear",
        "operator_action": (
            "Open Problems and resolve current blockers for this phase."
            if current_count
            else "No active blockers are attached to this phase."
        ),
    }


def _dashboard_issue(job: JobModel, *, historical: bool) -> dict[str, Any]:
    resolution = job_resolution(job) or {}
    label = "Reviewed history" if historical else meaning_for(job.status)["label"]
    action = (
        "Use this as learning evidence; it does not block current health."
        if historical
        else "Open Problems, inspect attempts, and decide whether to retry or repair."
    )
    return {
        "job_id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "label": label,
        "failure_class": job.last_failure_class,
        "last_error": job.last_error,
        "resolution": resolution,
        "operator_action": action,
    }


def _phase_detail(
    *,
    phase: str,
    workflow: WorkflowInstanceModel | None,
    jobs: list[JobModel],
    crews: list[CrewRunModel],
    packages: list[WorkPackageModel],
    next_action: str,
) -> dict[str, Any]:
    current_issues = [
        _dashboard_issue(job, historical=False) for job in unresolved_problem_jobs(jobs)
    ]
    historical_issues = [
        _dashboard_issue(job, historical=True)
        for job in jobs
        if job.status in {"failed", "dead_letter", "abandoned"} and job_is_acknowledged(job)
    ]
    evidence = _phase_evidence(phase, workflow, jobs, crews, packages)
    confidence = _phase_confidence(workflow, evidence, current_issues)
    return {
        "label": phase.replace("_", " ").title(),
        "confidence": confidence,
        "confidence_detail": _phase_confidence_detail(
            confidence, evidence, current_issues
        ),
        "proof_status": _phase_proof_status(evidence, workflow),
        "owner_crew": _phase_owner(phase, crews, jobs),
        "completed_evidence": evidence,
        "remaining_work": (
            "Resolve current issues before scaling this project."
            if current_issues
            else "Continue the workflow and preserve proof for this phase."
            if workflow is not None
            else "Start or relink the workflow before treating this phase as live."
        ),
        "next_action": next_action,
        "issue_summary": _phase_issue_summary(current_issues, historical_issues),
        "current_issues": current_issues,
        "historical_issues": historical_issues,
    }


def _failure_improvement_proposals(jobs: list[JobModel]) -> list[dict[str, Any]]:
    jobs_by_failure_class: dict[str, list[JobModel]] = {}
    for job in unresolved_problem_jobs(jobs):
        jobs_by_failure_class.setdefault(str(job.last_failure_class or "unknown"), []).append(job)
    counts = Counter(
        {
            failure_class: len(failure_jobs)
            for failure_class, failure_jobs in jobs_by_failure_class.items()
        }
    )
    proposals: list[dict[str, Any]] = []
    for failure_class, count in counts.most_common(4):
        if count < 2:
            continue
        source_jobs = jobs_by_failure_class[failure_class][:5]
        proposals.append(
            {
                "title": f"Guardrail proposal: {failure_class.replace('_', ' ')}",
                "failure_class": failure_class,
                "current_failure_count": count,
                "source_jobs": [
                    {
                        "job_id": job.id,
                        "project_id": job.project_id,
                        "job_type": job.job_type,
                        "status": job.status,
                        "attempt_count": job.attempt_count,
                        "max_attempts": job.max_attempts,
                    }
                    for job in source_jobs
                ],
                "status": "proposed",
                "evolution_endpoint": "/api/v1/enterprise-evolution/improvements",
                "evidence_status": {
                    "state": "evidence_required",
                    "ready_to_submit": False,
                    "required_sources": ["operator_job_attempts"],
                    "missing": [
                        "immutable evidence reference for enterprise evolution"
                    ],
                    "submission_endpoint": "/api/v1/enterprise-evolution/improvements",
                    "operator_action": (
                        "Open the listed job attempts, bind immutable evidence, "
                        "then submit the improvement draft through Enterprise "
                        "Evolution."
                    ),
                },
                "improvement_draft": {
                    "improvement_key": f"operations.failure.{failure_class}_guardrail",
                    "category": "operations",
                    "origin": "dashboard-manager.recovery",
                    "title": f"Reduce repeated {failure_class} problems",
                    "expected_benefit": (
                        f"Prevent repeated {failure_class} problems from blocking "
                        "future project execution."
                    ),
                    "risk_document": {
                        "risk_class": "operational_recovery",
                        "failure_class": failure_class,
                        "current_failure_count": count,
                        "requires_human_review": True,
                    },
                    "dependencies": [],
                    "evidence_required": True,
                    "evidence_collection": [
                        {
                            "type": "operator_job_attempts",
                            "endpoint": (
                                f"/api/v1/operator/jobs/by-id/{job.id}/attempts"
                            ),
                            "job_id": str(job.id),
                        }
                        for job in source_jobs
                    ],
                },
                "recommendation": (
                    "Convert this recurring problem class into a recovery checklist, "
                    "test guardrail, or project template improvement."
                ),
                "operator_action": (
                    "Open Problems, inspect attempts for this problem class, then "
                    "record the reusable guardrail before queuing more work."
                ),
            }
        )
    return proposals


def _catalog_review_criteria(evidence_sources: dict[str, int]) -> list[dict[str, Any]]:
    criteria = [
        ("at least two succeeded jobs", "succeeded_jobs", 2),
        ("at least one succeeded crew run", "succeeded_crew_runs", 1),
        ("at least one work package", "work_packages", 1),
    ]
    return [
        {
            "criterion": criterion,
            "actual": evidence_sources.get(source, 0),
            "required": required,
            "passed": evidence_sources.get(source, 0) >= required,
        }
        for criterion, source, required in criteria
    ]


def _reuse_learning_summary(
    projects: list[ProjectModel],
    jobs: list[JobModel],
    crew_runs: list[CrewRunModel],
    work_packages: list[WorkPackageModel],
    recovery_proposals: list[dict[str, Any]],
) -> dict[str, Any]:
    jobs_by_project: dict[uuid.UUID, list[JobModel]] = {}
    crew_by_project: dict[uuid.UUID, list[CrewRunModel]] = {}
    packages_by_project: dict[uuid.UUID, list[WorkPackageModel]] = {}
    for job in jobs:
        jobs_by_project.setdefault(job.project_id, []).append(job)
    for run in crew_runs:
        crew_by_project.setdefault(run.project_id, []).append(run)
    for package in work_packages:
        packages_by_project.setdefault(package.project_id, []).append(package)

    blueprint_candidates: list[dict[str, Any]] = []
    for project in projects:
        project_jobs = jobs_by_project.get(project.id, [])
        project_runs = crew_by_project.get(project.id, [])
        project_packages = packages_by_project.get(project.id, [])
        completed_jobs = [job for job in project_jobs if job.status == "succeeded"]
        completed_runs = [run for run in project_runs if run.status == "succeeded"]
        evidence_count = len(completed_jobs) + len(completed_runs) + len(project_packages)
        if evidence_count == 0:
            continue
        project_type = (
            str(project.manifest.get("project_type", "enterprise_project"))
            if isinstance(project.manifest, dict)
            else "enterprise_project"
        )
        evidence_sources = {
            "succeeded_jobs": len(completed_jobs),
            "succeeded_crew_runs": len(completed_runs),
            "work_packages": len(project_packages),
        }
        criteria_status = _catalog_review_criteria(evidence_sources)
        promotion_blockers = [
            str(criterion["criterion"])
            for criterion in criteria_status
            if not criterion["passed"]
        ]
        lifecycle = "reviewed" if not promotion_blockers else "candidate"
        readiness_level = "catalog_review_ready" if lifecycle == "reviewed" else "needs_more_proof"
        blueprint_candidates.append(
            {
                "blueprint_key": f"{project_type}.{project.id}.learning_candidate",
                "project_id": str(project.id),
                "project_name": project.name,
                "project_type": project_type,
                "lifecycle": lifecycle,
                "readiness_level": readiness_level,
                "evidence_count": evidence_count,
                "evidence_sources": evidence_sources,
                "criteria_status": criteria_status,
                "promotion_blockers": promotion_blockers,
                "readiness_detail": {
                    "label": (
                        "Ready for catalog review"
                        if readiness_level == "catalog_review_ready"
                        else "Needs more proof"
                    ),
                    "meaning": (
                        "The candidate has enough operational proof for human catalog review."
                        if readiness_level == "catalog_review_ready"
                        else "The candidate is visible, but promotion would be premature."
                    ),
                    "next_action": (
                        "Review the evidence bundle and decide whether to promote it."
                        if readiness_level == "catalog_review_ready"
                        else "Collect the missing proof before catalog review."
                    ),
                },
                "reuse_readiness": (
                    "review evidence for catalog promotion"
                    if lifecycle == "reviewed"
                    else "collect more proof before reuse"
                ),
                "operator_action": (
                    "Open the project dashboard, review proof, then promote the "
                    "workflow or crew pattern only after evidence review."
                ),
            }
        )

    guardrail_candidates = [
        {
            "proposal_key": proposal["improvement_draft"]["improvement_key"],
            "failure_class": proposal["failure_class"],
            "current_failure_count": proposal["current_failure_count"],
            "evidence_status": proposal["evidence_status"],
            "readiness_level": (
                "ready_to_submit"
                if proposal["evidence_status"].get("ready_to_submit")
                else "evidence_required"
            ),
            "promotion_blockers": proposal["evidence_status"].get("missing", []),
            "operator_action": proposal["operator_action"],
        }
        for proposal in recovery_proposals
        if "improvement_draft" in proposal and "evidence_status" in proposal
    ]
    ready_blueprints = [
        candidate
        for candidate in blueprint_candidates
        if candidate["readiness_level"] == "catalog_review_ready"
    ]
    blocked_blueprints = len(blueprint_candidates) - len(ready_blueprints)

    return {
        "blueprint_candidates": blueprint_candidates[:5],
        "guardrail_candidates": guardrail_candidates[:5],
        "next_catalog_review": None
        if not ready_blueprints
        else {
            "blueprint_key": ready_blueprints[0]["blueprint_key"],
            "project_id": ready_blueprints[0]["project_id"],
            "project_name": ready_blueprints[0]["project_name"],
            "evidence_count": ready_blueprints[0]["evidence_count"],
            "evidence_bundle": {
                "sources": ready_blueprints[0]["evidence_sources"],
                "promotion_blockers": ready_blueprints[0]["promotion_blockers"],
                "review_criteria": [
                    "at least two succeeded jobs",
                    "at least one succeeded crew run",
                    "at least one work package",
                ],
                "criteria_status": ready_blueprints[0]["criteria_status"],
            },
            "operator_action": ready_blueprints[0]["readiness_detail"]["next_action"],
        },
        "readiness": {
            "catalog_review_ready": len(ready_blueprints),
            "needs_more_proof": blocked_blueprints,
            "guardrails_evidence_required": sum(
                1
                for candidate in guardrail_candidates
                if candidate["readiness_level"] == "evidence_required"
            ),
        },
        "summary": (
            f"{_count_phrase(len(blueprint_candidates), 'blueprint candidate')}, "
            f"{_count_phrase(len(guardrail_candidates), 'guardrail candidate')}."
        ),
        "operator_action": (
            "Promote reusable project patterns only after proof review, and convert "
            "recurring problems into guarded templates."
        ),
    }


def _crew_summary(runs: list[CrewRunModel], jobs: list[JobModel]) -> list[dict[str, object]]:
    completed: list[dict[str, object]] = [
        {
            "name": run.crew_name,
            **status_read_model(run.status),
            "assignment": (
                "Completed project crew run."
                if run.status == "succeeded"
                else "Crew run ended with a recorded status and remains part of project evidence."
            ),
            "last_signal_at": run.completed_at or run.started_at or run.created_at,
        }
        for run in runs
    ]
    active_jobs = [
        job for job in jobs if job.status in {"queued", "running", "leased", "retry_wait"}
    ]
    active: list[dict[str, object]] = [
        {
            "name": job.job_type.replace("_", " "),
            **status_read_model(job.status),
            "assignment": "Work item controlled by the enterprise worker system.",
            "last_signal_at": job.last_leased_at or job.available_at or job.created_at,
        }
        for job in active_jobs
    ]
    return (active + completed)[:8]


def _manager_graph(
    projects: list[ProjectModel],
    workflows_by_project: dict[uuid.UUID, WorkflowInstanceModel],
    jobs_by_project: dict[uuid.UUID, list[JobModel]],
    crew_by_project: dict[uuid.UUID, list[CrewRunModel]],
) -> dict[str, list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = [
        {
            "id": "factory",
            "label": "Manifesto Factory",
            "kind": "factory",
            **status_read_model("active" if projects else "waiting_for_manifesto"),
            "human_summary": (
                "Manifestos become governed projects, workflows, tasks, crews, proof, "
                "and reusable templates."
            ),
        }
    ]
    edges: list[dict[str, Any]] = []
    for project in projects:
        workflow = workflows_by_project.get(project.id)
        jobs = jobs_by_project.get(project.id, [])
        crews = crew_by_project.get(project.id, [])
        summary = _task_summary(jobs, [])
        project_node = f"project:{project.id}"
        workflow_node = f"workflow:{workflow.id}" if workflow else f"workflow:missing:{project.id}"
        crew_node = f"crew:{project.id}"
        telemetry_node = f"telemetry:{project.id}"
        project_status = (
            "attention_required"
            if summary["problems"]
            else "active"
            if workflow or jobs
            else "intake"
        )
        nodes.extend(
            [
                {
                    "id": project_node,
                    "label": project.name,
                    "kind": "project",
                    **status_read_model(project_status),
                    "human_summary": (
                        f"{project.name}: {summary['done']} done, {summary['active']} active, "
                        f"{summary['standby']} standby, {summary['problems']} problem tasks."
                    ),
                },
                {
                    "id": workflow_node,
                    "label": _project_phase_from_workflow(workflow),
                    "kind": "workflow",
                    **status_read_model("not_started" if workflow is None else workflow.state),
                    "human_summary": (
                        "Workflow is not started yet. Start it after manifesto intake."
                        if workflow is None
                        else workflow.recommended_operator_action
                        or "Workflow is linked and moving through controlled phases."
                    ),
                },
                {
                    "id": crew_node,
                    "label": "Crew Activity",
                    "kind": "crew",
                    **status_read_model("active" if crews or summary["active"] else "standby"),
                    "human_summary": (
                        f"{len(crews)} completed crew signal(s), "
                        f"{summary['active']} active work signal(s)."
                    ),
                },
                {
                    "id": telemetry_node,
                    "label": "Telemetry",
                    "kind": "telemetry",
                    **status_read_model(
                        "attention_required" if summary["problems"] else "nominal"
                    ),
                    "human_summary": (
                        "Task, crew, workflow, and event signals are collected for this "
                        "project."
                    ),
                },
            ]
        )
        edges.extend(
            [
                {"from": "factory", "to": project_node, "label": "creates"},
                {"from": project_node, "to": workflow_node, "label": "executes"},
                {"from": workflow_node, "to": crew_node, "label": "assigns"},
                {"from": crew_node, "to": telemetry_node, "label": "reports"},
                {"from": telemetry_node, "to": project_node, "label": "calibrates"},
            ]
        )
    return {"nodes": nodes, "edges": edges}


@router.get("/dashboard-manager")
@router.get("/dashboard-read-model")
async def dashboard_manager(
    session: SessionDependency,
    actor: ActorDependency,
    organization_id: uuid.UUID | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    _require_query_read(actor)
    if limit < 1 or limit > 100:
        raise HTTPException(422, "limit must be between 1 and 100")

    projects = list(
        (
            await session.scalars(
                select(ProjectModel).order_by(ProjectModel.updated_at.desc()).limit(limit)
            )
        ).all()
    )
    project_ids = [project.id for project in projects]
    workflows = list(
        (
            await session.scalars(
                select(WorkflowInstanceModel)
                .where(WorkflowInstanceModel.project_id.in_(project_ids))
                .order_by(WorkflowInstanceModel.updated_at.desc())
            )
        ).all()
        if project_ids
        else []
    )
    jobs = list(
        (
            await session.scalars(
                select(JobModel)
                .where(JobModel.project_id.in_(project_ids))
                .order_by(JobModel.created_at.desc())
            )
        ).all()
        if project_ids
        else []
    )
    crew_runs = list(
        (
            await session.scalars(
                select(CrewRunModel)
                .where(CrewRunModel.project_id.in_(project_ids))
                .order_by(CrewRunModel.created_at.desc())
            )
        ).all()
        if project_ids
        else []
    )
    work_packages = list(
        (
            await session.scalars(
                select(WorkPackageModel)
                .where(WorkPackageModel.project_id.in_(project_ids))
                .order_by(WorkPackageModel.created_at.desc())
            )
        ).all()
        if project_ids
        else []
    )
    workers = list(
        (
            await session.scalars(
                select(WorkerInstanceModel)
                .order_by(WorkerInstanceModel.last_heartbeat_at.desc())
                .limit(100)
            )
        ).all()
    )
    audits = list(
        (
            await session.scalars(
                select(AuditEventModel)
                .where(AuditEventModel.project_id.in_(project_ids))
                .order_by(AuditEventModel.created_at.desc())
                .limit(50)
            )
        ).all()
        if project_ids
        else []
    )
    metrics_query = select(PerformanceMetricModel)
    if organization_id is not None:
        metrics_query = metrics_query.where(
            PerformanceMetricModel.organization_id == organization_id
        )
    metrics = list(
        (
            await session.scalars(
                metrics_query.order_by(PerformanceMetricModel.calculated_at.desc()).limit(limit)
            )
        ).all()
    )

    workflows_by_project: dict[uuid.UUID, WorkflowInstanceModel] = {}
    for workflow in workflows:
        workflows_by_project.setdefault(workflow.project_id, workflow)
    jobs_by_project: dict[uuid.UUID, list[JobModel]] = {project.id: [] for project in projects}
    for job in jobs:
        jobs_by_project.setdefault(job.project_id, []).append(job)
    crew_by_project: dict[uuid.UUID, list[CrewRunModel]] = {
        project.id: [] for project in projects
    }
    for run in crew_runs:
        crew_by_project.setdefault(run.project_id, []).append(run)
    packages_by_project: dict[uuid.UUID, list[WorkPackageModel]] = {
        project.id: [] for project in projects
    }
    for package in work_packages:
        packages_by_project.setdefault(package.project_id, []).append(package)
    audits_by_project: dict[uuid.UUID, list[AuditEventModel]] = {
        project.id: [] for project in projects
    }
    for audit in audits:
        if audit.project_id is not None:
            audits_by_project.setdefault(audit.project_id, []).append(audit)

    summaries = []
    total_done = total_active = total_standby = total_problems = 0
    for project in projects:
        project_workflow = workflows_by_project.get(project.id)
        project_jobs = jobs_by_project.get(project.id, [])
        project_packages = packages_by_project.get(project.id, [])
        tasks = _task_summary(project_jobs, project_packages)
        total_done += tasks["done"]
        total_active += tasks["active"]
        total_standby += tasks["standby"]
        total_problems += tasks["problems"]
        crews = _crew_summary(crew_by_project.get(project.id, []), project_jobs)
        recent_events = [
            {
                "event_type": audit.event_type,
                "actor": audit.actor_id,
                "created_at": audit.created_at,
                "summary": f"{audit.actor_id} recorded {audit.event_type}.",
            }
            for audit in audits_by_project.get(project.id, [])[:5]
        ]
        phase = _project_phase_from_workflow(project_workflow)
        state = (
            "attention_required"
            if tasks["problems"]
            else "active"
            if project_workflow or project_jobs
            else "intake"
        )
        current_meaning = meaning_for(state)
        phase_meaning = meaning_for(phase)
        next_action = (
            "Open Problems and resolve failed work before scaling this project."
            if tasks["problems"]
            else project_workflow.recommended_operator_action
            if project_workflow and project_workflow.recommended_operator_action
            else "Start or relink the workflow after manifesto intake."
            if project_workflow is None
            else "Continue monitoring this project execution graph."
        )
        summaries.append(
            {
                "id": project.id,
                "name": project.name,
                **status_read_model(project.status),
                "phase": phase,
                "phase_meaning": phase_meaning,
                "phase_detail": _phase_detail(
                    phase=phase,
                    workflow=project_workflow,
                    jobs=project_jobs,
                    crews=crew_by_project.get(project.id, []),
                    packages=project_packages,
                    next_action=next_action,
                ),
                "state": state,
                "state_meaning": current_meaning,
                "repository_path": project.repository_path,
                "project_type": project.manifest.get("project_type", "enterprise_project")
                if isinstance(project.manifest, dict)
                else "enterprise_project",
                "workflow": None
                if project_workflow is None
                else {
                    "id": project_workflow.id,
                    "state": project_workflow.state,
                    **status_read_model(project_workflow.state),
                    "current_step": project_workflow.current_step,
                    "recommended_operator_action": (
                        project_workflow.recommended_operator_action
                    ),
                    "updated_at": project_workflow.updated_at,
                },
                "tasks": tasks,
                "crews": crews,
                "recent_events": recent_events,
                "telemetry": {
                    "signal": "attention_required" if tasks["problems"] else "nominal",
                    "signal_meaning": meaning_for(
                        "attention_required" if tasks["problems"] else "nominal"
                    ),
                    "event_count": len(audits_by_project.get(project.id, [])),
                    "crew_signal_count": len(crew_by_project.get(project.id, [])),
                    "job_signal_count": len(project_jobs),
                    "work_package_count": len(project_packages),
                },
                "human_summary": (
                    f"{project.name} is in {phase}. "
                    f"{tasks['done']} done, {tasks['active']} active, "
                    f"{tasks['standby']} standby, {tasks['problems']} problem tasks."
                ),
                "next_action": next_action,
            }
        )

    online_workers = [worker for worker in workers if worker.status == "online"]
    manager_state = (
        "attention_required"
        if total_problems
        else "active"
        if total_active or summaries
        else "waiting_for_manifesto"
    )
    recovery_proposals = _failure_improvement_proposals(jobs)
    return {
        "generated_at": datetime.now(UTC),
        "query_policy": {
            "mode": "dashboard_manager_projection",
            "human_language": True,
            "mutation_allowed": False,
            "actor": actor.subject,
        },
        "headline": {
            "state": manager_state,
            "meaning": meaning_for(manager_state),
            "summary": (
                f"{_count_phrase(len(summaries), 'project')}, "
                f"{_count_phrase(total_done, 'done task')}, "
                f"{_count_phrase(total_active, 'active task')}, "
                f"{_count_phrase(total_standby, 'standby task')}, "
                f"{_count_phrase(total_problems, 'problem task')}."
            ),
            "business_meaning": (
                "Some project work needs recovery before the factory should scale further."
                if manager_state == "attention_required"
                else "The factory is coordinating project execution and can be inspected live."
                if manager_state == "active"
                else "Attach a manifesto to create the first governed project."
            ),
        },
        "totals": {
            "projects": len(summaries),
            "tasks_done": total_done,
            "tasks_active": total_active,
            "tasks_standby": total_standby,
            "tasks_problem": total_problems,
            "online_workers": len(online_workers),
            "worker_signals": len(workers),
            "events": len(audits),
            "governed_metrics": len(metrics),
        },
        "recovery": {
            "improvement_proposals": recovery_proposals,
            "proposal_basis": (
                "Recurring unresolved problem classes across dashboard-manager jobs."
            ),
        },
        "reuse": _reuse_learning_summary(
            projects,
            jobs,
            crew_runs,
            work_packages,
            recovery_proposals,
        ),
        "sections": {
            "projects": source_contract(
                name="Projects",
                endpoint="/api/v1/projects",
                record_count=len(projects),
                latest_at=_latest_time(projects, "updated_at"),
                stale_after=timedelta(hours=24),
                empty_reason="No manifesto project has been created yet.",
                operator_action="Open Factory and create or ingest a manifesto project.",
            ),
            "workflows": source_contract(
                name="Workflows",
                endpoint="/api/v1/workflows",
                record_count=len(workflows),
                latest_at=_latest_time(workflows, "updated_at"),
                stale_after=timedelta(hours=2),
                empty_reason="Projects exist without durable workflow records.",
                operator_action="Start or relink workflows before presenting execution proof.",
            ),
            "jobs": source_contract(
                name="Jobs",
                endpoint="/api/v1/operator/jobs",
                record_count=len(jobs),
                latest_at=_latest_time(jobs, "created_at"),
                stale_after=timedelta(minutes=30),
                empty_reason="No worker jobs have been queued or executed for these projects.",
                operator_action="Start workflow execution to create job evidence.",
            ),
            "workers": source_contract(
                name="Workers",
                endpoint="/api/v1/operator/jobs/worker-instances",
                record_count=len(workers),
                latest_at=_latest_time(workers, "last_heartbeat_at"),
                stale_after=timedelta(minutes=5),
                empty_reason="No worker heartbeat is visible.",
                operator_action="Start worker services before scaling parallel work.",
            ),
            "telemetry": source_contract(
                name="Telemetry",
                endpoint="/dashboard/telemetry-summary",
                record_count=len(metrics) + len(audits),
                latest_at=_latest_time(metrics, "calculated_at")
                or _latest_time(audits, "created_at"),
                stale_after=timedelta(minutes=15),
                empty_reason="No governed metrics or audit events are visible for this view.",
                operator_action="Run work and collect audit or performance evidence.",
            ),
            "graph": source_contract(
                name="Execution Graph",
                endpoint="/api/v1/query/dashboard-manager",
                record_count=len(summaries),
                latest_at=datetime.now(UTC) if summaries else None,
                stale_after=timedelta(minutes=5),
                empty_reason=(
                    "The graph has no project nodes because no project records are visible."
                ),
                operator_action="Use this section for the current operating picture.",
            ),
        },
        "projects": summaries,
        "telemetry": {
            "always_active": True,
            "latest_event_at": _latest_time(audits, "created_at"),
            "latest_worker_heartbeat_at": _latest_time(workers, "last_heartbeat_at"),
            "latest_metric_at": _latest_time(metrics, "calculated_at"),
            "status_counts": {
                "projects": _status_counts(projects),
                "jobs": _status_counts(jobs),
                "crews": _status_counts(crew_runs),
                "workers": _status_counts(workers),
            },
        },
        "graph": _manager_graph(
            projects,
            workflows_by_project,
            jobs_by_project,
            crew_by_project,
        ),
        "guidance": [
            {
                "title": "Start from manifesto",
                "message": (
                    "Ingest the client document, confirm repository details, then launch "
                    "the governed workflow."
                ),
            },
            {
                "title": "Inspect live execution",
                "message": (
                    "Click a project node to see phase, tasks, crew, events, telemetry, "
                    "and next action."
                ),
            },
            {
                "title": "Convert proof into reuse",
                "message": (
                    "When a project stabilizes, promote its successful workflow and crew "
                    "pattern into a template."
                ),
            },
        ],
    }


@router.get("/operating-picture")
async def operating_picture(
    session: SessionDependency,
    actor: ActorDependency,
    organization_id: uuid.UUID | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    _require_query_read(actor)
    if limit < 1 or limit > 200:
        raise HTTPException(422, "limit must be between 1 and 200")

    projects = list(
        (
            await session.scalars(
                select(ProjectModel).order_by(ProjectModel.updated_at.desc()).limit(limit)
            )
        ).all()
    )
    workflows = list(
        (
            await session.scalars(
                select(WorkflowInstanceModel)
                .order_by(WorkflowInstanceModel.updated_at.desc())
                .limit(limit)
            )
        ).all()
    )
    jobs = list(
        (
            await session.scalars(
                select(JobModel).order_by(JobModel.created_at.desc()).limit(limit)
            )
        ).all()
    )
    workers = list(
        (
            await session.scalars(
                select(WorkerInstanceModel)
                .order_by(WorkerInstanceModel.last_heartbeat_at.desc())
                .limit(100)
            )
        ).all()
    )
    resources_query = select(EnterpriseResourceModel)
    modules_query = select(EnterpriseModuleModel)
    schedules_query = select(EnterpriseScheduleModel)
    threads_query = select(OrganizationalThreadModel)
    maturity_query = select(OperatingMaturitySnapshotModel)
    metrics_query = select(PerformanceMetricModel)
    learning_query = select(LearningProposalModel)
    knowledge_query = select(KnowledgeItemModel)
    if organization_id is not None:
        resources_query = resources_query.where(
            EnterpriseResourceModel.organization_id == organization_id
        )
        modules_query = modules_query.where(
            EnterpriseModuleModel.organization_id == organization_id
        )
        schedules_query = schedules_query.where(
            EnterpriseScheduleModel.organization_id == organization_id
        )
        threads_query = threads_query.where(
            OrganizationalThreadModel.organization_id == organization_id
        )
        maturity_query = maturity_query.where(
            OperatingMaturitySnapshotModel.organization_id == organization_id
        )
        metrics_query = metrics_query.where(
            PerformanceMetricModel.organization_id == organization_id
        )
        learning_query = learning_query.where(
            LearningProposalModel.organization_id == organization_id
        )
        knowledge_query = knowledge_query.where(
            KnowledgeItemModel.scope_type == "organization",
            KnowledgeItemModel.scope_id == organization_id,
        )
    resources = list((await session.scalars(resources_query.limit(limit))).all())
    modules = list((await session.scalars(modules_query.limit(limit))).all())
    schedules = list((await session.scalars(schedules_query.limit(limit))).all())
    threads = list((await session.scalars(threads_query.limit(limit))).all())
    maturity = list(
        (
            await session.scalars(
                maturity_query.order_by(OperatingMaturitySnapshotModel.recorded_at.desc()).limit(1)
            )
        ).all()
    )
    metrics = list(
        (
            await session.scalars(
                metrics_query.order_by(PerformanceMetricModel.calculated_at.desc()).limit(limit)
            )
        ).all()
    )
    learning = list((await session.scalars(learning_query.limit(limit))).all())
    knowledge = list((await session.scalars(knowledge_query.limit(limit))).all())

    problem_jobs = unresolved_problem_jobs(jobs)
    acknowledged_jobs = [
        job
        for job in jobs
        if job.status in {"failed", "dead_letter", "abandoned"} and job_is_acknowledged(job)
    ]
    online_workers = [worker for worker in workers if worker.status == "online"]
    moving_jobs = [job for job in jobs if job.status in {"queued", "running", "leased"}]
    state = (
        "attention_required"
        if problem_jobs
        else "active"
        if moving_jobs or online_workers
        else "waiting_for_work"
    )

    return {
        "generated_at": datetime.now(UTC),
        "query_policy": {
            "mode": "read_only_projection",
            "human_language": True,
            "mutation_allowed": False,
            "actor": actor.subject,
        },
        "headline": {
            "state": state,
            "summary": (
                f"{len(projects)} project(s), {len(moving_jobs)} moving work item(s), "
                f"{len(problem_jobs)} problem(s), {len(online_workers)} online worker(s)."
            ),
            "business_meaning": (
                "The enterprise is ready to create and coordinate work."
                if state == "waiting_for_work"
                else "The enterprise has live delivery signals to inspect."
                if state == "active"
                else (
                    "The enterprise has issues that should become recovery actions "
                    "and reusable lessons."
                )
            ),
        },
        "counts": {
            "projects": len(projects),
            "workflows": len(workflows),
            "jobs": len(jobs),
            "unresolved_problem_jobs": len(problem_jobs),
            "acknowledged_problem_jobs": len(acknowledged_jobs),
            "workers": len(workers),
            "enterprise_resources": len(resources),
            "enterprise_modules": len(modules),
            "enterprise_schedules": len(schedules),
            "organizational_threads": len(threads),
            "performance_metrics": len(metrics),
            "learning_proposals": len(learning),
            "knowledge_items": len(knowledge),
        },
        "status_counts": {
            "projects": _status_counts(projects),
            "workflows": _status_counts(workflows, "state"),
            "jobs": _status_counts(jobs),
            "job_resolution": _resolution_counts(acknowledged_jobs),
            "workers": _status_counts(workers),
            "resources": _status_counts(resources, "state"),
            "modules": _status_counts(modules, "state"),
            "schedules": _status_counts(schedules, "state"),
            "threads": _status_counts(threads, "current_state"),
        },
        "freshness": {
            "projects": _latest_time(projects, "updated_at"),
            "jobs": _latest_time(jobs, "created_at"),
            "workers": _latest_time(workers, "last_heartbeat_at"),
            "performance_metrics": _latest_time(metrics, "calculated_at"),
        },
        "maturity": None
        if not maturity
        else {
            "level": maturity[0].maturity_level,
            "covered_resource_types": maturity[0].covered_resource_types,
            "module_count": maturity[0].module_count,
            "active_thread_count": maturity[0].active_thread_count,
            "human_summary": (
                f"Maturity level {maturity[0].maturity_level} covers "
                f"{len(maturity[0].covered_resource_types)} resource type(s)."
            ),
        },
        "recommendations": _recommendations(
            projects=projects,
            jobs=jobs,
            workers=workers,
            workflows=workflows,
            schedules=schedules,
        ),
        "graph": _graph(
            projects=projects,
            jobs=jobs,
            workers=workers,
            workflows=workflows,
            resource_count=len(resources),
            module_count=len(modules),
            knowledge_count=len(knowledge),
        ),
    }


@router.get("/projects/{project_id}/operating-picture")
async def project_operating_picture(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, Any]:
    _require_query_read(actor, project_id)
    project = await session.get(ProjectModel, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    workflows = list(
        (
            await session.scalars(
                select(WorkflowInstanceModel)
                .where(WorkflowInstanceModel.project_id == project_id)
                .order_by(WorkflowInstanceModel.updated_at.desc())
            )
        ).all()
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
    artifacts = list(
        (
            await session.scalars(
                select(ArtifactModel)
                .where(ArtifactModel.project_id == project_id)
                .order_by(ArtifactModel.created_at)
            )
        ).all()
    )
    crew_runs = list(
        (
            await session.scalars(
                select(CrewRunModel)
                .where(CrewRunModel.project_id == project_id)
                .order_by(CrewRunModel.created_at)
            )
        ).all()
    )
    audits = list(
        (
            await session.scalars(
                select(AuditEventModel)
                .where(AuditEventModel.project_id == project_id)
                .order_by(AuditEventModel.created_at.desc())
                .limit(20)
            )
        ).all()
    )
    problem_jobs = unresolved_problem_jobs(jobs)
    acknowledged_jobs = [
        job
        for job in jobs
        if job.status in {"failed", "dead_letter", "abandoned"} and job_is_acknowledged(job)
    ]
    state = "attention_required" if problem_jobs else "active" if jobs or workflows else "intake"
    project_status = status_read_model(project.status)
    nodes = [
        {
            "id": f"project:{project.id}",
            "label": project.name,
            "kind": "project",
            **project_status,
            "human_summary": (
                "The project identity, manifesto, and repository are registered. "
                f"Current state: {project_status['status_label']}."
            ),
        }
    ]
    edges: list[dict[str, str]] = []
    for workflow in workflows:
        node_id = f"workflow:{workflow.id}"
        workflow_status = status_read_model(workflow.state)
        nodes.append(
            {
                "id": node_id,
                "label": workflow.current_step or workflow.state,
                "kind": "workflow",
                **workflow_status,
                "human_summary": (
                    workflow.recommended_operator_action or "Monitor workflow progress."
                ),
            }
        )
        edges.append({"from": f"project:{project.id}", "to": node_id, "label": "controls"})
    for job in jobs:
        node_id = f"job:{job.id}"
        job_status = status_read_model(job.status)
        nodes.append(
            {
                "id": node_id,
                "label": job.job_type.replace("_", " ").title(),
                "kind": "job",
                **job_status,
                "human_summary": (
                    f"{job_status['status_label']}; attempt {job.attempt_count} "
                    f"of {job.max_attempts}."
                ),
            }
        )
        edges.append({"from": f"project:{project.id}", "to": node_id, "label": "executes"})
    return {
        "generated_at": datetime.now(UTC),
        "project": {
            "id": project.id,
            "name": project.name,
            "status": project.status,
            "project_type": project.manifest.get("project_type", "enterprise_project"),
        },
        "headline": {
            "state": state,
            "summary": (
                f"{len(workflows)} workflow(s), {len(jobs)} job(s), "
                f"{len(artifacts)} artifact(s), {len(crew_runs)} crew run(s)."
            ),
            "business_meaning": (
                "Resolve the visible failed work before presenting project proof."
                if state == "attention_required"
                else "The project has enough operating data to inspect live proof."
                if state == "active"
                else "The project is registered and ready for workflow launch."
            ),
        },
        "status_counts": {
            "workflows": _status_counts(workflows, "state"),
            "jobs": _status_counts(jobs),
            "job_resolution": _resolution_counts(acknowledged_jobs),
            "crew_runs": _status_counts(crew_runs),
            "artifacts": _status_counts(artifacts, "artifact_type"),
        },
        "latest_audit_events": [
            {
                "event_type": audit.event_type,
                "actor": audit.actor_id,
                "created_at": audit.created_at,
                "human_summary": f"{audit.actor_id} recorded {audit.event_type}.",
            }
            for audit in audits
        ],
        "recommendations": _recommendations(
            projects=[project],
            jobs=jobs,
            workers=[],
            workflows=workflows,
            schedules=[],
        ),
        "graph": {"nodes": nodes, "edges": edges},
    }
