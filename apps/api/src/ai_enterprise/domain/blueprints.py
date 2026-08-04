from __future__ import annotations

BLUEPRINT_LIFECYCLES = {"proposed", "reviewed", "reusable", "deprecated", "improved"}

ALLOWED_BLUEPRINT_TRANSITIONS = {
    "proposed": {"reviewed", "deprecated"},
    "reviewed": {"reusable", "improved", "deprecated"},
    "reusable": {"improved", "deprecated"},
    "improved": {"reviewed", "reusable", "deprecated"},
    "deprecated": {"improved"},
}


class BlueprintLifecycleError(ValueError):
    pass


def require_blueprint_transition(current: str, target: str) -> None:
    if current not in BLUEPRINT_LIFECYCLES or target not in BLUEPRINT_LIFECYCLES:
        raise BlueprintLifecycleError("Unknown blueprint lifecycle state")
    if target not in ALLOWED_BLUEPRINT_TRANSITIONS[current]:
        raise BlueprintLifecycleError(f"Blueprint cannot transition from {current} to {target}")


def require_reuse_evidence(evidence: dict[str, object]) -> None:
    """Require review proof that is useful to a later blueprint consumer."""
    reviewed_by = evidence.get("reviewed_by")
    validation_summary = evidence.get("validation_summary")
    evidence_refs = evidence.get("evidence_refs")
    if not isinstance(reviewed_by, str) or not reviewed_by.strip():
        raise BlueprintLifecycleError("Reusable promotion requires a named evidence reviewer")
    if not isinstance(validation_summary, str) or len(validation_summary.strip()) < 10:
        raise BlueprintLifecycleError("Reusable promotion requires a validation summary")
    if (
        not isinstance(evidence_refs, list)
        or not evidence_refs
        or any(not isinstance(item, str) or not item.strip() for item in evidence_refs)
    ):
        raise BlueprintLifecycleError("Reusable promotion requires evidence references")
