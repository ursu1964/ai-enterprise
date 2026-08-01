from ai_enterprise.domain.architecture.enums import (
    ArchitectureArtifactStatus,
    ArchitectureReviewStatus,
    ArchitectureRunStatus,
)


class InvalidArchitectureTransition(ValueError):
    pass


RUN_TRANSITIONS = {
    ArchitectureRunStatus.READY: {ArchitectureRunStatus.RUNNING},
    ArchitectureRunStatus.RUNNING: {
        ArchitectureRunStatus.COMPLETED,
        ArchitectureRunStatus.FAILED_VALIDATION,
        ArchitectureRunStatus.FAILED,
    },
}
ARTIFACT_TRANSITIONS = {
    ArchitectureArtifactStatus.DRAFT: {ArchitectureArtifactStatus.UNDER_REVIEW},
    ArchitectureArtifactStatus.UNDER_REVIEW: {
        ArchitectureArtifactStatus.CHANGES_REQUESTED,
        ArchitectureArtifactStatus.REJECTED,
        ArchitectureArtifactStatus.APPROVED,
    },
    ArchitectureArtifactStatus.APPROVED: {ArchitectureArtifactStatus.SUPERSEDED},
}
REVIEW_TRANSITIONS = {
    ArchitectureReviewStatus.OPEN: {
        ArchitectureReviewStatus.COMPLETED,
        ArchitectureReviewStatus.CANCELLED,
    },
    ArchitectureReviewStatus.COMPLETED: {ArchitectureReviewStatus.SUPERSEDED},
}


def require_transition(current: object, target: object, graph: dict[object, set[object]]) -> None:
    if target not in graph.get(current, set()):
        raise InvalidArchitectureTransition(
            f"Illegal architecture transition: {current} -> {target}"
        )
