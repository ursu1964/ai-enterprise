from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Meaning:
    label: str
    severity: str
    meaning: str
    operator_action: str

    def model_dump(self) -> dict[str, str]:
        return {
            "label": self.label,
            "severity": self.severity,
            "meaning": self.meaning,
            "operator_action": self.operator_action,
        }


_STATUS_MEANINGS: dict[str, Meaning] = {
    "created": Meaning(
        "Ready to start",
        "info",
        "The record exists and is ready for the next workflow action.",
        "Start or relink the governed workflow when the manifesto is ready.",
    ),
    "project_created": Meaning(
        "Ready to start",
        "info",
        "The project identity and manifesto are registered.",
        "Start the workflow before presenting execution proof.",
    ),
    "requirements_running": Meaning(
        "Requirements work running",
        "info",
        "The requirements phase is actively producing or checking evidence.",
        "Monitor requirements output and prepare for approval.",
    ),
    "waiting_requirements_approval": Meaning(
        "Ready for requirements review",
        "warn",
        "Requirements evidence exists and is waiting for an explicit decision.",
        "Review requirements evidence and approve or request changes.",
    ),
    "architecture_running": Meaning(
        "Architecture work running",
        "info",
        "The architecture phase is actively producing or checking evidence.",
        "Monitor architecture output and prepare for approval.",
    ),
    "waiting_architecture_approval": Meaning(
        "Ready for architecture review",
        "warn",
        "Architecture evidence exists and is waiting for an explicit decision.",
        "Review architecture evidence and approve or request changes.",
    ),
    "planning_running": Meaning(
        "Planning work running",
        "info",
        "The work-package planning phase is actively decomposing implementation work.",
        "Monitor planning output and prepare for work-package review.",
    ),
    "work_package_approved": Meaning(
        "Plan approved, execution not started",
        "ok",
        "The work package plan has been accepted but implementation has not begun.",
        "Start execution only after capacity and risk are clear.",
    ),
    "waiting_work_package_approval": Meaning(
        "Ready for work-package review",
        "warn",
        "A work package is waiting for an explicit human decision.",
        "Review the work package and approve or reject it.",
    ),
    "execution_running": Meaning(
        "Execution running",
        "info",
        "Approved implementation work is running and producing change evidence.",
        "Monitor execution evidence, tests, and failure signals.",
    ),
    "patch_review_running": Meaning(
        "Patch review running",
        "info",
        "The candidate patch is being reviewed against policy and evidence.",
        "Wait for review output before integration.",
    ),
    "waiting_integration_approval": Meaning(
        "Ready for integration approval",
        "warn",
        "Reviewed change evidence is waiting for an integration decision.",
        "Approve integration only after evidence and risk are clear.",
    ),
    "integrating": Meaning(
        "Integration running",
        "info",
        "Approved work is being integrated into the target branch or environment.",
        "Monitor integration status and rollback evidence.",
    ),
    "completed": Meaning(
        "Completed",
        "ok",
        "The workflow completed with the required evidence.",
        "Use the workflow evidence for reporting and reuse decisions.",
    ),
    "cancelling": Meaning(
        "Cancellation in progress",
        "warn",
        "The workflow is stopping and clearing active work safely.",
        "Wait for cancellation to finish before relaunching work.",
    ),
    "cancelled": Meaning(
        "Cancelled",
        "warn",
        "The workflow was stopped before completion.",
        "Review the cancellation reason before creating replacement work.",
    ),
    "manual_intervention": Meaning(
        "Review before running",
        "bad",
        "The workflow needs a human decision before work can safely continue.",
        "Open the related project or problem detail and record the decision.",
    ),
    "attention_required": Meaning(
        "Needs operator decision",
        "bad",
        "Current work has unresolved risk or failed execution evidence.",
        "Review Problems before scaling more work.",
    ),
    "dead_letter": Meaning(
        "Reviewed failure or recovery needed",
        "bad",
        "The job exhausted automated recovery and is preserved as failure evidence.",
        "Acknowledge it as history or create a recovery action after review.",
    ),
    "failed": Meaning(
        "Needs recovery action",
        "bad",
        "The work did not finish successfully.",
        "Inspect the diagnostic detail and decide whether to retry or repair.",
    ),
    "abandoned": Meaning(
        "Stopped and needs review",
        "bad",
        "The work stopped before completion.",
        "Review the reason and decide whether replacement work is required.",
    ),
    "queued": Meaning(
        "Waiting for worker capacity",
        "warn",
        "The work is ready but has not been accepted by a worker.",
        "Check worker capacity if this state persists.",
    ),
    "running": Meaning(
        "Work is running",
        "info",
        "The job is actively executing.",
        "Monitor telemetry and wait for completion or failure.",
    ),
    "leased": Meaning(
        "Worker has accepted the work",
        "info",
        "A worker has claimed the job lease.",
        "Monitor the worker heartbeat and lease expiry.",
    ),
    "retry_wait": Meaning(
        "Waiting before retry",
        "warn",
        "The job is intentionally delayed before another attempt.",
        "Review repeated failures if retry pressure grows.",
    ),
    "succeeded": Meaning(
        "Completed",
        "ok",
        "The work completed successfully.",
        "Use the result as evidence for the next phase.",
    ),
    "nominal": Meaning(
        "Healthy",
        "ok",
        "No current blocker is visible.",
        "Continue the guided route.",
    ),
    "active": Meaning(
        "Active",
        "ok",
        "The platform has live records to inspect.",
        "Open the relevant project or execution graph.",
    ),
    "standby": Meaning(
        "Standby",
        "info",
        "The item is waiting for useful work or a command.",
        "Continue monitoring or start the next action.",
    ),
    "not_started": Meaning(
        "Not started",
        "warn",
        "The workflow has not begun yet.",
        "Start or relink the workflow.",
    ),
    "waiting_for_manifesto": Meaning(
        "Waiting for manifesto",
        "info",
        "The factory needs project intent before it can create work.",
        "Open Factory and attach a manifesto or client idea.",
    ),
    "waiting_for_work": Meaning(
        "Ready for work",
        "info",
        "The system is healthy but no active work is moving.",
        "Create a project or inspect existing project proof.",
    ),
    "online": Meaning(
        "Online",
        "ok",
        "This worker is available for enterprise work.",
        "Use it as current capacity.",
    ),
    "offline": Meaning(
        "Offline",
        "warn",
        "This worker is not part of current capacity.",
        "Start worker services if capacity is required.",
    ),
    "degraded": Meaning(
        "Degraded",
        "warn",
        "The signal is available but incomplete or reduced.",
        "Inspect source details before relying on it.",
    ),
    "draft": Meaning(
        "Draft",
        "info",
        "The runtime or registry item is being prepared and is not approved yet.",
        "Review and approve it before production use.",
    ),
    "approved": Meaning(
        "Approved",
        "ok",
        "The item passed review and can be used within its approved scope.",
        "Use it only within the recorded capability and scope.",
    ),
    "registered": Meaning(
        "Registered",
        "info",
        "The item exists in the registry but may still need health or approval evidence.",
        "Check health, approval, and scope before relying on it.",
    ),
    "pending": Meaning(
        "Pending review",
        "warn",
        "The item is waiting for review or completion.",
        "Inspect the pending evidence and complete the required decision.",
    ),
    "awaiting_review": Meaning(
        "Awaiting review",
        "warn",
        "The item has been produced and is waiting for governed review.",
        "Review findings and approve or request changes.",
    ),
    "validation_failed": Meaning(
        "Validation failed",
        "bad",
        "Validation found issues that block trusted use.",
        "Inspect validation findings and repair the source artifact.",
    ),
    "started": Meaning(
        "Started",
        "info",
        "The runtime or workflow has started and should soon produce live evidence.",
        "Monitor follow-up events and health signals.",
    ),
    "current": Meaning(
        "Current phase",
        "info",
        "This is where the project is now.",
        "Open phase detail and follow the next action.",
    ),
    "executed": Meaning(
        "Completed phase",
        "ok",
        "This phase has execution evidence or is behind the current phase.",
        "Use its evidence when reviewing project proof.",
    ),
    "remaining": Meaning(
        "Remaining phase",
        "info",
        "This phase has not produced live evidence yet.",
        "Continue the workflow until this phase becomes current.",
    ),
    "empty": Meaning(
        "No records yet",
        "info",
        "The source is reachable but has no records for this section.",
        "Create or link records before expecting this section to show data.",
    ),
    "unavailable": Meaning(
        "Source unavailable",
        "bad",
        "The dashboard cannot read this source right now.",
        "Refresh and inspect API logs if the problem repeats.",
    ),
}


def meaning_for(status: object) -> dict[str, str]:
    raw = str(status or "not_reported").lower()
    meaning = _STATUS_MEANINGS.get(
        raw,
        Meaning(
            raw.replace("_", " ").title(),
            "info",
            "The platform recorded this state, but no specialized explanation exists yet.",
            "Open diagnostic detail if this state blocks progress.",
        ),
    )
    return {"raw": raw, **meaning.model_dump()}


def status_read_model(status: object) -> dict[str, Any]:
    meaning = meaning_for(status)
    return {
        "status": meaning["raw"],
        "status_label": meaning["label"],
        "status_meaning": meaning,
    }


def source_contract(
    *,
    name: str,
    endpoint: str,
    record_count: int,
    latest_at: datetime | None = None,
    available: bool = True,
    empty_reason: str | None = None,
    operator_action: str | None = None,
) -> dict[str, Any]:
    state = "available" if available and record_count else "empty" if available else "unavailable"
    return {
        "source": name,
        "endpoint": endpoint,
        "available": available,
        "state": state,
        "freshness": "fresh" if latest_at else "not_observed",
        "last_updated": latest_at,
        "record_count": record_count,
        "empty_reason": empty_reason if record_count == 0 else None,
        "operator_action": operator_action
        or (
            "No records exist yet; create or link records for this section."
            if record_count == 0
            else "Use this section for the current operating picture."
        ),
        "meaning": meaning_for(state),
        "generated_at": datetime.now(UTC),
    }
