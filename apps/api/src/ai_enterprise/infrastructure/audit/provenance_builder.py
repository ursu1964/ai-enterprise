from collections.abc import Iterable
from typing import Any
from uuid import UUID

from ai_enterprise.application.audit.dto import (
    ProjectProvenanceResponse,
    ProvenanceEdgeResponse,
    ProvenanceNodeResponse,
)


class ProvenanceBuilder:
    def build(
        self,
        *,
        project: Any,
        artifacts: Iterable[Any],
        crew_runs: Iterable[Any],
        approvals: Iterable[Any],
        work_packages: Iterable[Any],
        executions: Iterable[Any],
        reviews: Iterable[Any],
    ) -> ProjectProvenanceResponse:
        nodes: dict[UUID, ProvenanceNodeResponse] = {
            project.id: ProvenanceNodeResponse(
                id=project.id, node_type="project", label=project.name,
                created_at=project.created_at,
                metadata={"manifest_sha256": project.manifest_hash},
            )
        }
        edges: list[ProvenanceEdgeResponse] = []

        for item in artifacts:
            nodes[item.id] = ProvenanceNodeResponse(
                id=item.id, node_type="artifact", label=item.artifact_type,
                sha256=item.content_hash, created_at=item.created_at,
                metadata={"media_type": item.media_type},
            )
            if item.run_id:
                edges.append(ProvenanceEdgeResponse(
                    source_id=item.run_id, target_id=item.id, relationship="produces"
                ))
        for item in crew_runs:
            nodes[item.id] = ProvenanceNodeResponse(
                id=item.id, node_type="crew_run", label=item.crew_name,
                created_at=item.created_at, metadata={"status": item.status},
            )
        for item in approvals:
            nodes[item.id] = ProvenanceNodeResponse(
                id=item.id, node_type="approval", label=f"{item.decision} approval",
                created_at=item.created_at, metadata={"reviewer": item.reviewer},
            )
            edges.append(ProvenanceEdgeResponse(
                source_id=item.artifact_id, target_id=item.id, relationship="approved_by"
            ))
        for item in work_packages:
            nodes[item.id] = ProvenanceNodeResponse(
                id=item.id, node_type="work_package", label=item.title,
                sha256=item.contract_hash, created_at=item.created_at,
                metadata={"status": item.status},
            )
        for item in executions:
            nodes[item.id] = ProvenanceNodeResponse(
                id=item.id, node_type="execution_run", label="Disposable execution",
                sha256=item.patch_sha256, created_at=item.created_at,
                metadata={"status": item.status},
            )
            edges.append(ProvenanceEdgeResponse(
                source_id=item.work_package_id, target_id=item.id, relationship="executes"
            ))
            if item.patch_artifact_id:
                edges.append(ProvenanceEdgeResponse(
                    source_id=item.id, target_id=item.patch_artifact_id,
                    relationship="generates"
                ))
        for item in reviews:
            nodes[item.id] = ProvenanceNodeResponse(
                id=item.id, node_type="patch_review_run", label="Independent patch review",
                sha256=item.actual_patch_sha256, created_at=item.created_at,
                metadata={"status": item.status},
            )
            edges.append(ProvenanceEdgeResponse(
                source_id=item.patch_artifact_id, target_id=item.id, relationship="reviews"
            ))
            if item.review_report_artifact_id:
                edges.append(ProvenanceEdgeResponse(
                    source_id=item.id, target_id=item.review_report_artifact_id,
                    relationship="produces"
                ))
        return ProjectProvenanceResponse(
            project_id=project.id,
            nodes=sorted(nodes.values(), key=lambda node: (node.node_type, str(node.id))),
            edges=sorted(edges, key=lambda edge: (
                str(edge.source_id), str(edge.target_id), edge.relationship
            )),
        )
