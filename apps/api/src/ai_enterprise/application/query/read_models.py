from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
    "requirements_queued": Meaning(
        "Requirements work queued",
        "warn",
        "Requirements work is ready but waiting for worker capacity.",
        "Check worker capacity if this state persists.",
    ),
    "requirements_failed": Meaning(
        "Requirements need repair",
        "bad",
        "Requirements work failed before producing trusted evidence.",
        "Review failed job evidence and repair the requirements input or crew path.",
    ),
    "awaiting_requirements_approval": Meaning(
        "Ready for requirements review",
        "warn",
        "Requirements evidence exists and is waiting for an explicit decision.",
        "Review requirements evidence and approve or request changes.",
    ),
    "requirements_approved": Meaning(
        "Requirements approved",
        "ok",
        "Requirements evidence passed the governed review gate.",
        "Use approved requirements as input to architecture.",
    ),
    "requirements_rejected": Meaning(
        "Requirements changes requested",
        "warn",
        "Requirements evidence was reviewed and needs revision.",
        "Revise the requirements evidence before advancing.",
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
    "architecture_queued": Meaning(
        "Architecture work queued",
        "warn",
        "Architecture work is ready but waiting for worker capacity.",
        "Check worker capacity if this state persists.",
    ),
    "architecture_failed": Meaning(
        "Architecture needs repair",
        "bad",
        "Architecture work failed before producing trusted evidence.",
        "Review failed job evidence and repair the architecture input or crew path.",
    ),
    "awaiting_architecture_approval": Meaning(
        "Ready for architecture review",
        "warn",
        "Architecture evidence exists and is waiting for an explicit decision.",
        "Review architecture evidence and approve or request changes.",
    ),
    "architecture_approved": Meaning(
        "Architecture approved",
        "ok",
        "Architecture evidence passed the governed review gate.",
        "Use approved architecture as input to work-package planning.",
    ),
    "architecture_rejected": Meaning(
        "Architecture changes requested",
        "warn",
        "Architecture evidence was reviewed and needs revision.",
        "Revise architecture evidence before advancing.",
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
    "work_package_queued": Meaning(
        "Work-package planning queued",
        "warn",
        "Planning work is ready but waiting for worker capacity.",
        "Check worker capacity if this state persists.",
    ),
    "work_package_planning": Meaning(
        "Work-package planning running",
        "info",
        "Implementation work is being decomposed into governed work packages.",
        "Monitor planning output and prepare for approval.",
    ),
    "work_package_failed": Meaning(
        "Work-package planning needs repair",
        "bad",
        "Planning failed before producing trusted work-package evidence.",
        "Review failed job evidence and repair the planning inputs.",
    ),
    "awaiting_work_package_approval": Meaning(
        "Ready for work-package review",
        "warn",
        "A work package is waiting for an explicit human decision.",
        "Review the work package and approve or reject it.",
    ),
    "work_package_approved": Meaning(
        "Plan approved, execution not started",
        "ok",
        "The work package plan has been accepted but implementation has not begun.",
        "Start execution only after capacity and risk are clear.",
    ),
    "work_package_rejected": Meaning(
        "Work-package changes requested",
        "warn",
        "The work package was reviewed and needs revision.",
        "Revise the package before execution starts.",
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
    "execution_queued": Meaning(
        "Execution queued",
        "warn",
        "Approved implementation work is waiting for execution capacity.",
        "Check worker capacity and dispatch queues if this state persists.",
    ),
    "executing": Meaning(
        "Execution running",
        "info",
        "Approved implementation work is actively producing change evidence.",
        "Monitor execution evidence, tests, and failure signals.",
    ),
    "execution_succeeded": Meaning(
        "Execution completed",
        "ok",
        "Implementation work completed and should have evidence attached.",
        "Use the execution evidence for patch review or integration.",
    ),
    "execution_failed": Meaning(
        "Execution needs recovery",
        "bad",
        "Implementation work failed before trusted completion.",
        "Review execution logs and repair or retry through governance.",
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
    "deprecated": Meaning(
        "Deprecated",
        "warn",
        "The item has been replaced or should no longer be selected for new work.",
        "Use the recommended replacement or keep it only for historical context.",
    ),
    "retired": Meaning(
        "Retired",
        "warn",
        "The item is no longer active in the operating system.",
        "Do not use it for new work unless governance reactivates it.",
    ),
    "inactive": Meaning(
        "Inactive",
        "warn",
        "The binding or item is not currently available for use.",
        "Activate it only after scope, health, and approval evidence are valid.",
    ),
    "pending": Meaning(
        "Pending review",
        "warn",
        "The item is waiting for review or completion.",
        "Inspect the pending evidence and complete the required decision.",
    ),
    "awaiting_approval": Meaning(
        "Awaiting approval",
        "warn",
        "The item is complete enough to review and is waiting for an explicit approval.",
        "Review evidence and approve or request changes.",
    ),
    "requested": Meaning(
        "Requested",
        "info",
        "A governed request has been recorded and is waiting for authorization or execution.",
        "Check the next approval or dispatch step.",
    ),
    "authorized": Meaning(
        "Authorized",
        "ok",
        "The request has permission to proceed within its recorded scope.",
        "Continue only within the approved capability and scope.",
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
    "available": Meaning(
        "Available",
        "ok",
        "The source is reachable and has records for this section.",
        "Use this section for the current operating picture.",
    ),
    "intake": Meaning(
        "Intake needed",
        "info",
        "The project exists, but the factory still needs enough intent to plan work.",
        "Open Factory and complete manifesto or client-intake details.",
    ),
    "ready": Meaning(
        "Ready",
        "ok",
        "The item has enough information for the next governed action.",
        "Continue with the recommended command or review step.",
    ),
    "blocked": Meaning(
        "Blocked",
        "bad",
        "A required input, approval, dependency, or evidence item is missing.",
        "Open the detail view and resolve the listed blocker before continuing.",
    ),
    "dispatchable": Meaning(
        "Ready to dispatch",
        "ok",
        "The governed schedule has enough inputs to assign work.",
        "Dispatch work when capacity and priority are appropriate.",
    ),
    "suspended": Meaning(
        "Suspended",
        "warn",
        "The item is intentionally paused by governance or operations.",
        "Review suspension reason before reactivation.",
    ),
    "certified": Meaning(
        "Certified",
        "ok",
        "The module or capability has passed its certification checks.",
        "Use it within the certified scope.",
    ),
    "open": Meaning(
        "Open",
        "info",
        "The thread or issue is active and still collecting work or evidence.",
        "Continue tracking until it is complete or blocked.",
    ),
    "complete": Meaning(
        "Complete",
        "ok",
        "The thread or item completed its intended workflow.",
        "Use it as current proof or historical evidence.",
    ),
    "partial": Meaning(
        "Partially started",
        "warn",
        "Some work started, but other related work is blocked or failed.",
        "Inspect created, reused, blocked, and failed launch items.",
    ),
    "ready_for_approval": Meaning(
        "Ready for approval",
        "warn",
        "The item is complete enough for a human approval decision.",
        "Review evidence and approve or request changes.",
    ),
    "draft_needs_clarification": Meaning(
        "Clarification needed",
        "warn",
        "The draft exists but lacks required information for trusted execution.",
        "Fill the missing intake details before approval.",
    ),
    "proposed": Meaning(
        "Proposed",
        "info",
        "The item is a candidate and has not yet been accepted for reuse or action.",
        "Review the proposal and evidence before promotion.",
    ),
    "promoted": Meaning(
        "Promoted",
        "ok",
        "The candidate was accepted into the governed knowledge or reuse surface.",
        "Use it within its recorded scope and evidence.",
    ),
    "rejected": Meaning(
        "Rejected",
        "warn",
        "The proposal or candidate was reviewed and not accepted.",
        "Use the rejection reason before submitting replacement work.",
    ),
    "pending_human_review": Meaning(
        "Waiting for human review",
        "warn",
        "The system produced a recommendation that requires human governance.",
        "Review the recommendation and record an explicit decision.",
    ),
    "revertible": Meaning(
        "Rollback possible",
        "warn",
        "Recovery evidence indicates a controlled rollback can be attempted.",
        "Approve rollback only after checking branch and test evidence.",
    ),
    "consumed": Meaning(
        "Already used",
        "info",
        "The approval or token was consumed and cannot be reused.",
        "Create a new approval if more recovery work is required.",
    ),
    "expired": Meaning(
        "Expired",
        "warn",
        "The approval, lease, or evidence window is no longer valid.",
        "Refresh evidence or request a new decision before continuing.",
    ),
    "timed_out": Meaning(
        "Timed out",
        "bad",
        "The check or command did not finish within its trusted execution window.",
        "Inspect logs and retry only after the cause is understood.",
    ),
    "passed": Meaning(
        "Passed",
        "ok",
        "The check completed successfully.",
        "Use this result as supporting evidence.",
    ),
    "tested": Meaning(
        "Tested",
        "ok",
        "The item has test evidence attached.",
        "Keep the evidence with the related decision or release proof.",
    ),
    "closed": Meaning(
        "Closed",
        "ok",
        "The record has completed its governance lifecycle.",
        "Use it as history unless new evidence reopens the issue.",
    ),
    "denied": Meaning(
        "Denied",
        "warn",
        "The request was explicitly refused by policy or governance.",
        "Review the denial reason before retrying.",
    ),
    "analyzed": Meaning(
        "Analyzed",
        "info",
        "The proposal has analysis evidence but is not yet approved.",
        "Continue through simulation, review, or approval gates.",
    ),
    "simulated": Meaning(
        "Simulated",
        "info",
        "The change was evaluated in a non-production or modelled path.",
        "Review simulation evidence before approval.",
    ),
    "reviewed": Meaning(
        "Reviewed",
        "ok",
        "A human or governed review has examined the evidence.",
        "Follow the recorded decision or next gate.",
    ),
    "superseded": Meaning(
        "Superseded",
        "info",
        "A newer version or replacement now carries the active meaning.",
        "Use the superseding item for current work.",
    ),
    "stale": Meaning(
        "Stale",
        "warn",
        "The information may no longer reflect current operating reality.",
        "Refresh or verify before relying on it.",
    ),
    "disputed": Meaning(
        "Disputed",
        "warn",
        "The information conflicts with other evidence or has not been settled.",
        "Resolve the contradiction before using it as trusted input.",
    ),
    "verified": Meaning(
        "Verified",
        "ok",
        "Integrity or evidence checks passed.",
        "Use this result as trusted proof.",
    ),
    "unsupported": Meaning(
        "Unsupported",
        "warn",
        "The current data does not support this verification path.",
        "Use a newer evidence source or inspect diagnostic details.",
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
    stale_after: timedelta | None = None,
    empty_reason: str | None = None,
    operator_action: str | None = None,
) -> dict[str, Any]:
    generated_at = datetime.now(UTC)
    age_seconds: float | None = None
    if latest_at is not None:
        age_seconds = max(0.0, (generated_at - latest_at).total_seconds())
    is_stale = (
        available
        and record_count > 0
        and latest_at is not None
        and stale_after is not None
        and generated_at - latest_at > stale_after
    )
    if not available:
        state = "unavailable"
    elif record_count == 0:
        state = "empty"
    elif is_stale:
        state = "stale"
    else:
        state = "available"
    freshness = (
        "unavailable"
        if not available
        else "not_observed"
        if latest_at is None
        else "stale"
        if is_stale
        else "fresh"
    )
    return {
        "source": name,
        "endpoint": endpoint,
        "available": available,
        "state": state,
        "freshness": freshness,
        "last_updated": latest_at,
        "freshness_age_seconds": age_seconds,
        "stale_after_seconds": (
            None if stale_after is None else int(stale_after.total_seconds())
        ),
        "record_count": record_count,
        "empty_reason": empty_reason if available and record_count == 0 else None,
        "operator_action": operator_action
        or (
            "No records exist yet; create or link records for this section."
            if record_count == 0
            else "Refresh this source before making delivery decisions."
            if is_stale
            else "Use this section for the current operating picture."
        ),
        "meaning": meaning_for(state),
        "generated_at": generated_at,
    }
