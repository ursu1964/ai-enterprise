import asyncio
import hashlib
import json
import uuid
from collections import deque
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.api.architecture_schemas import ArchitectureApprovalResponse
from ai_enterprise.api.dependencies import Actor
from ai_enterprise.application.architecture_operations.contracts import ArchitectureRunSnapshot
from ai_enterprise.application.architecture_operations.recovery import ArchitectureRecoveryService
from ai_enterprise.application.architecture_service import (
    ArchitectureGovernanceError,
    ArchitectureGovernanceService,
)
from ai_enterprise.domain.architecture.enums import (
    ArchitectureArtifactStatus,
    ArchitectureReviewDecision,
    ArchitectureReviewStatus,
)
from ai_enterprise.domain.audit.policies import sanitize_payload
from ai_enterprise.infrastructure.architecture.contracts import (
    ArchitectureExecutionContext,
    AttemptEvidence,
)
from ai_enterprise.infrastructure.architecture.executor import TrustedArchitectureExecutor
from ai_enterprise.infrastructure.architecture.fake_provider import ScriptedArchitectureProvider
from ai_enterprise.infrastructure.architecture.models import (
    ArchitectureArtifactModel,
    ArchitectureReviewModel,
    ArchitectureRunModel,
)
from ai_enterprise.infrastructure.database.models import ApprovalModel, ArtifactModel


class EvidenceWriter:
    def __init__(self) -> None:
        self.items: list[AttemptEvidence] = []

    async def record(self, evidence: AttemptEvidence) -> None:
        self.items.append(evidence)


class ScalarRows:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values


class ServiceSession:
    """Small persistence-port fake; governance decisions remain production code."""

    def __init__(self, rows: list[object], scalars: list[object]) -> None:
        self.rows = {row.id: row for row in rows}
        self.scalar_values: deque[object] = deque(scalars)
        self.added: list[object] = []

    async def get(self, model: type[object], identity: object, **kwargs: object) -> object | None:
        value = self.rows.get(identity)
        return value if value is None or isinstance(value, model) else None

    async def scalar(self, statement: object) -> object:
        return self.scalar_values.popleft()

    async def scalars(self, statement: object) -> ScalarRows:
        value = self.scalar_values.popleft()
        assert isinstance(value, list)
        return ScalarRows(value)

    def add(self, value: object) -> None:
        self.added.append(value)

    def add_all(self, values: list[object]) -> None:
        self.added.extend(values)

    async def commit(self) -> None:
        return None

    async def flush(self) -> None:
        return None

    async def refresh(self, value: object) -> None:
        return None


def context(*, expired: bool = False) -> ArchitectureExecutionContext:
    deadline = datetime.now(UTC) + timedelta(seconds=-1 if expired else 10)
    return ArchitectureExecutionContext(
        run_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        project_name="Acceptance",
        project_description="Architecture acceptance",
        project_manifest_checksum="a" * 64,
        requirements_artifact_id=uuid.uuid4(),
        requirements_version=1,
        requirements_checksum="b" * 64,
        requirements_markdown="REQ-001: preserve the repository",
        approved_requirement_ids=frozenset({"REQ-001"}),
        schema_version="1.0",
        crew_version="architecture-crew-v1",
        deadline_at=deadline,
    )


def valid_output() -> str:
    return json.dumps(
        {
            "schema_version": "1.0",
            "overview": "A governed service architecture.",
            "goals": ["Deliver REQ-001"],
            "constraints": ["No host mutation"],
            "functional_domains": [
                {
                    "id": "DOM-CORE",
                    "name": "Core",
                    "responsibilities": ["Govern"],
                    "requirement_ids": ["REQ-001"],
                }
            ],
            "modules": [
                {
                    "id": "MOD-API",
                    "name": "API",
                    "domain_id": "DOM-CORE",
                    "responsibilities": ["Serve"],
                    "dependencies": [],
                    "requirement_ids": ["REQ-001"],
                }
            ],
            "interfaces": [
                {
                    "id": "API-MAIN",
                    "name": "Main",
                    "kind": "rest",
                    "owner_module_id": "MOD-API",
                    "consumers": [],
                    "contract": "POST /runs",
                    "requirement_ids": ["REQ-001"],
                }
            ],
            "data_entities": [
                {
                    "id": "ENT-RUN",
                    "name": "Run",
                    "owner_module_id": "MOD-API",
                    "persistence": "PostgreSQL",
                    "transaction_boundary": "one run",
                    "requirement_ids": ["REQ-001"],
                }
            ],
            "deployment": ["Container"],
            "security": ["Least privilege"],
            "reliability": ["Fenced leases"],
            "failure_scenarios": ["Worker crash"],
            "scaling": ["Horizontal workers"],
            "observability": ["Metrics"],
            "risks": [],
            "open_questions": [],
            "requirement_traceability": [
                {"requirement_id": "REQ-001", "design_element_ids": ["MOD-API", "API-MAIN"]}
            ],
        },
        separators=(",", ":"),
    )


def tree_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def artifact(project_id: uuid.UUID, requirements_id: uuid.UUID) -> ArchitectureArtifactModel:
    return ArchitectureArtifactModel(
        id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        project_id=project_id,
        requirements_artifact_id=requirements_id,
        parent_artifact_id=None,
        version=1,
        status=ArchitectureArtifactStatus.CHANGES_REQUESTED,
        markdown_content="architecture content long enough",
        structured_content={"schema_version": "1.0"},
        checksum="c" * 64,
        schema_version="1.0",
    )


async def test_happy_path_preserves_host_repository(tmp_path: Path) -> None:
    repository = tmp_path / "host-repository"
    repository.mkdir()
    (repository / "tracked.py").write_text("VALUE = 1\n")
    before = tree_fingerprint(repository)
    evidence = EvidenceWriter()
    result = await TrustedArchitectureExecutor(
        provider=ScriptedArchitectureProvider([valid_output()]), evidence_writer=evidence
    ).execute(context())
    assert result.invocation_count == 1
    assert [item.status for item in evidence.items] == ["succeeded"]
    assert tree_fingerprint(repository) == before


async def test_timeout_is_terminal_and_does_not_invoke_provider() -> None:
    provider = ScriptedArchitectureProvider([valid_output()])
    evidence = EvidenceWriter()
    with pytest.raises(TimeoutError):
        await TrustedArchitectureExecutor(provider=provider, evidence_writer=evidence).execute(
            context(expired=True)
        )
    assert provider.operations == []
    assert evidence.items[0].status == "timed_out"


async def test_crash_recovery_is_idempotent_under_concurrent_requests() -> None:
    calls = 0
    lock = asyncio.Lock()

    async def reconstruct(run_id: str) -> None:
        nonlocal calls
        async with lock:
            if calls == 0:
                calls += 1

    async def unused(run_id: str) -> None:
        raise AssertionError(f"unexpected callback for {run_id}")

    service = ArchitectureRecoveryService(
        reconstruct=reconstruct, complete=unused, retry=unused
    )
    crashed = ArchitectureRunSnapshot(
        "run-1", "project-1", "running", "succeeded", False, successful_attempt_count=1
    )
    await asyncio.gather(service.recover(crashed), service.recover(crashed))
    assert calls == 1


async def test_duplicate_active_run_is_rejected_by_governance_service() -> None:
    project_id, requirements_id = uuid.uuid4(), uuid.uuid4()
    requirements = ArtifactModel(
        id=requirements_id,
        project_id=project_id,
        artifact_type="requirements_specification",
        media_type="text/markdown",
        content="approved",
        content_hash="a" * 64,
    )
    approved = ApprovalModel(
        id=uuid.uuid4(),
        project_id=project_id,
        artifact_id=requirements_id,
        decision="approved",
        reviewer="requirements-reviewer",
    )
    active = ArchitectureRunModel(id=uuid.uuid4(), project_id=project_id)
    session = ServiceSession([requirements], [approved, active])
    with pytest.raises(ArchitectureGovernanceError, match="active architecture run"):
        await ArchitectureGovernanceService(cast(AsyncSession, session)).create_run(
            project_id, requirements_id
        )


async def test_changes_requested_revision_preserves_parent_and_findings() -> None:
    project_id, requirements_id = uuid.uuid4(), uuid.uuid4()
    source = artifact(project_id, requirements_id)
    review = ArchitectureReviewModel(
        id=uuid.uuid4(),
        architecture_artifact_id=source.id,
        review_round=1,
        status=ArchitectureReviewStatus.COMPLETED,
        reviewer_id="reviewer-1",
        reviewer_role="architecture_reviewer",
        reviewer_subject_type="human",
        decision=ArchitectureReviewDecision.REQUEST_CHANGES,
        reviewed_checksum=source.checksum,
        policy_version="architecture-review-policy-v1",
    )
    requirements = ArtifactModel(
        id=requirements_id,
        project_id=project_id,
        artifact_type="requirements_specification",
        media_type="text/markdown",
        content="approved",
        content_hash="a" * 64,
    )
    finding = type(
        "Finding",
        (),
        {
            "finding_key": "SEC-001",
            "description": "Boundary incomplete",
            "required_change": "Define boundary",
            "blocking": True,
        },
    )()
    session = ServiceSession([review, source, requirements], [None, None, [finding]])
    actor = Actor(
        "reviewer-1",
        "human",
        "architecture_reviewer",
        frozenset({"architecture.revision.create"}),
    )
    request, run = await ArchitectureGovernanceService(
        cast(AsyncSession, session)
    ).create_revision(
        review.id, "Apply the required security boundary change.", actor
    )
    assert run.parent_architecture_artifact_id == source.id
    assert run.revision_request_id == request.id
    assert request.inherited_findings[0]["key"] == "SEC-001"
    assert review.status == ArchitectureReviewStatus.SUPERSEDED


async def test_artifact_corruption_blocks_approval() -> None:
    project_id, requirements_id = uuid.uuid4(), uuid.uuid4()
    value = artifact(project_id, requirements_id)
    value.status = ArchitectureArtifactStatus.UNDER_REVIEW
    review = ArchitectureReviewModel(
        id=uuid.uuid4(),
        architecture_artifact_id=value.id,
        review_round=1,
        status=ArchitectureReviewStatus.COMPLETED,
        reviewer_id="reviewer-1",
        reviewer_role="architecture_reviewer",
        reviewer_subject_type="human",
        decision=ArchitectureReviewDecision.RECOMMEND_APPROVAL,
        reviewed_checksum="d" * 64,
        policy_version="architecture-review-policy-v1",
    )
    session = ServiceSession([value], [value, review])
    actor = Actor(
        "approver-1",
        "human",
        "architecture_approver",
        frozenset({"architecture.approve"}),
    )
    with pytest.raises(ArchitectureGovernanceError, match="checksum"):
        await ArchitectureGovernanceService(cast(AsyncSession, session)).approve(
            value.id, {}, actor
        )


def test_concurrent_version_and_approval_constraints_are_database_enforced() -> None:
    artifact_table = ArchitectureArtifactModel.__table__
    approval_table = ApprovalModel.metadata.tables["architecture_approvals"]
    unique_artifact_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in artifact_table.constraints
        if hasattr(constraint, "columns")
    }
    assert ("project_id", "version") in unique_artifact_constraints
    assert approval_table.c.architecture_artifact_id.unique
    assert approval_table.c.approving_review_id.unique


def test_security_responses_and_audit_payloads_redact_sensitive_evidence() -> None:
    approval = ArchitectureApprovalResponse.model_validate(
        {
            "id": uuid.uuid4(),
            "architecture_artifact_id": uuid.uuid4(),
            "approving_review_id": uuid.uuid4(),
            "approved_by": "approver-1",
            "approved_checksum": "a" * 64,
            "architecture_version": 1,
            "evidence_checksum": "b" * 64,
            "approved_at": datetime.now(UTC),
            "evidence": {"access_token": "must-not-escape"},
        }
    )
    assert "evidence" not in approval.model_dump()
    redacted = sanitize_payload(
        {"authorization": "Bearer secret", "nested": {"password": "secret"}}
    )
    assert "secret" not in json.dumps(redacted)
