import uuid
from dataclasses import dataclass

MODEL_BACKED_WORKFLOWS = frozenset(
    {"requirements", "architecture", "decomposition", "implementation", "review"}
)


@dataclass(frozen=True, slots=True)
class GovernedWorkflowRuntimeBinding:
    workflow_type: str
    workflow_run_id: uuid.UUID
    runtime_session_id: uuid.UUID
    runtime_specification_hash: str
    context_manifest_hash: str

    def __post_init__(self) -> None:
        if self.workflow_type not in MODEL_BACKED_WORKFLOWS:
            raise ValueError("Unsupported model-backed workflow")
        if len(self.runtime_specification_hash) != 64 or len(self.context_manifest_hash) != 64:
            raise ValueError("Workflow binding requires immutable SHA-256 lineage")


def require_governed_runtime(
    workflow_type: str, binding: GovernedWorkflowRuntimeBinding | None
) -> GovernedWorkflowRuntimeBinding:
    if workflow_type in MODEL_BACKED_WORKFLOWS and binding is None:
        raise PermissionError("GOVERNED-RUNTIME-SESSION-REQUIRED")
    if binding is None or binding.workflow_type != workflow_type:
        raise PermissionError("GOVERNED-RUNTIME-WORKFLOW-MISMATCH")
    return binding
