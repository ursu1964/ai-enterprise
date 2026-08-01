import uuid

import pytest

from ai_enterprise.application.decomposition_service import DecompositionError, DecompositionService
from ai_enterprise.domain.decomposition.core import DecompositionState, assert_transition
from ai_enterprise.infrastructure.decomposition.models import (
    DecompositionApprovalModel,
    DecompositionArtifactModel,
    WorkPackageDependencyModel,
    WorkPackageModel,
)


class RecordingSession:
    def __init__(self) -> None:
        self.values: list[object] = []

    def add(self, value: object) -> None:
        self.values.append(value)

    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_materialization_uses_graph_order_and_blocks_non_roots() -> None:
    project_id = uuid.uuid4()
    artifact_id = uuid.uuid4()
    root_id = uuid.uuid4()
    leaf_id = uuid.uuid4()
    artifact = DecompositionArtifactModel(
        id=artifact_id,
        decomposition_run_id=uuid.uuid4(),
        project_id=project_id,
        schema_version=1,
        artifact_hash="a" * 64,
        graph_hash="b" * 64,
        validation_status="valid",
        status="approved",
        artifact_document={
            "packages": [
                {
                    "id": str(leaf_id),
                    "key": "leaf",
                    "title": "Leaf",
                    "objective": "Build leaf",
                    "package_hash": "d" * 64,
                },
                {
                    "id": str(root_id),
                    "key": "root",
                    "title": "Root",
                    "objective": "Build root",
                    "package_hash": "c" * 64,
                },
            ],
            "graph": {
                "topological_order": ["root", "leaf"],
                "edges": [["root", "leaf", "blocking", "required"]],
            },
        },
    )
    session = RecordingSession()
    service = DecompositionService(session)  # type: ignore[arg-type]
    await service._materialize(artifact)
    packages = [item for item in session.values if isinstance(item, WorkPackageModel)]
    edges = [item for item in session.values if isinstance(item, WorkPackageDependencyModel)]
    assert [(item.package_key, item.sequence_number, item.status) for item in packages] == [
        ("root", 1, "ready"),
        ("leaf", 2, "blocked"),
    ]
    assert len(edges) == 1
    assert edges[0].predecessor_package_id == root_id
    assert edges[0].successor_package_id == leaf_id


def test_models_bind_approval_to_immutable_hash_and_exact_artifact() -> None:
    assert DecompositionApprovalModel.__table__.c.artifact_hash.nullable is False
    assert DecompositionApprovalModel.__table__.c.decomposition_artifact_id.unique is True
    assert WorkPackageModel.__table__.c.decomposition_artifact_id.nullable is False


def test_lifecycle_has_no_shortcut_from_pending_to_approved() -> None:
    with pytest.raises(ValueError, match="Invalid decomposition transition"):
        assert_transition(DecompositionState.PENDING, DecompositionState.APPROVED)


def test_decomposition_errors_expose_safe_http_status() -> None:
    assert DecompositionError("missing", 404).status_code == 404
