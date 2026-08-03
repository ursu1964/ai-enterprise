from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.routes.cognitive import _authority, decide, records, router
from ai_enterprise.application.cognitive_service import (
    RECORD_TYPES,
    CognitiveError,
    CognitiveService,
    CognitiveWorker,
)
from ai_enterprise.infrastructure.cognitive.models import CognitiveRecordModel


class Rows:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    def all(self) -> list[Any]:
        return self.rows


class Session:
    def __init__(self) -> None:
        self.gets: dict[tuple[type, uuid.UUID], Any] = {}
        self.scalar_values: list[Any] = []
        self.added: list[Any] = []

    async def get(self, model: type, identity: uuid.UUID) -> Any:
        return self.gets.get((model, identity))

    async def scalar(self, statement: object) -> Any:
        return self.scalar_values.pop(0) if self.scalar_values else None

    async def scalars(self, statement: object) -> Rows:
        return Rows([])

    def add(self, row: Any) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        return None


def record(organization_id: uuid.UUID, kind: str = "recommendation") -> CognitiveRecordModel:
    return CognitiveRecordModel(
        id=uuid.uuid4(),
        organization_id=organization_id,
        record_type=kind,
        record_key=f"{kind}.one",
        version="1.0.0",
        record_document={},
        record_hash="a" * 64,
        evidence_manifest=[{"type": "metric", "id": "m1", "hash": "b" * 64}],
        evidence_hash="c" * 64,
        classification="internal",
        confidence=0.8,
        parent_record_id=None,
        created_by="reasoner",
        created_at=datetime.now(UTC),
    )


def test_cognitive_authority_requires_scoped_capability() -> None:
    organization_id = uuid.uuid4()
    with pytest.raises(HTTPException, match="cognitive authority"):
        _authority(Actor("admin", "human", "platform-admin"), organization_id, "read")
    scoped = Actor(
        "analyst",
        "human",
        "analyst",
        frozenset({"cognitive.read"}),
        scopes=frozenset({f"organization:{organization_id}"}),
    )
    _authority(scoped, organization_id, "read")
    global_scoped = Actor(
        "analyst",
        "human",
        "analyst",
        frozenset({"cognitive.read"}),
        scopes=frozenset({"global"}),
    )
    _authority(global_scoped, organization_id, "read")
    with pytest.raises(HTTPException, match="cognitive authority"):
        _authority(scoped, uuid.uuid4(), "read")


@pytest.mark.asyncio
async def test_cognitive_record_reads_require_human_actor() -> None:
    organization_id = uuid.uuid4()
    denied = Actor(
        "cognitive-service",
        "service",
        "analyst",
        frozenset({"cognitive.read", "cognitive.classified.read"}),
        scopes=frozenset({f"organization:{organization_id}"}),
    )

    with pytest.raises(HTTPException) as exc:
        await records(
            Session(),  # type: ignore[arg-type]
            denied,
            organization_id,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Human cognitive read authority is required"


def test_p16_m1_m16_routes_types_and_append_only_migration() -> None:
    assert len(RECORD_TYPES) == 16
    paths = {f"/api/v1{route.path}" for route in router.routes}
    for path in (
        "semantics",
        "ontologies",
        "reasoning",
        "questions",
        "scenarios",
        "simulations",
        "digital-twins",
        "memory",
        "syntheses",
        "recommendations",
        "objectives",
        "dashboard",
        "cross-domain",
        "strategic-memory",
        "governance",
        "intelligence",
    ):
        assert f"/api/v1/cognitive/{path}" in paths
    migration = (
        Path(__file__).parents[3]
        / "migrations/versions/c61fc12de390_add_governed_cognitive_layer.py"
    ).read_text()
    assert 'down_revision: str | None = "c52eb01cd289"' in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "fk_cognitive_decision_org" in migration
    assert "DROP TRIGGER" in migration and "DROP FUNCTION" in migration
    hardening = (
        Path(__file__).parents[3]
        / "migrations/versions/c62ad23ef401_harden_cognitive_governance.py"
    ).read_text()
    assert 'down_revision: str | None = "c61fc12de390"' in hardening
    assert "fk_cognitive_decision_exact_record" in hardening
    assert "uq_cognitive_decision_nonce" in hardening
    assert "ck_cognitive_records_classification" in hardening
    assert "DISABLE" in hardening and "ENABLE" in hardening


@pytest.mark.asyncio
async def test_evidence_is_exact_and_secrets_fail_before_persistence() -> None:
    service = CognitiveService(Session())  # type: ignore[arg-type]
    values = dict(
        organization_id=uuid.uuid4(),
        record_type="reasoning",
        record_key="r1",
        version="1.0.0",
        document={},
        classification="internal",
        confidence=0.7,
        parent_record_id=None,
        created_by="reasoner",
    )
    with pytest.raises(CognitiveError, match="EVIDENCE-PROVENANCE-INVALID"):
        await service.register(
            **values, evidence=[{"type": "metric", "id": "m1", "hash": "x" * 64}]
        )
    values["document"] = {"nested": {"api-key": "unsafe"}}
    with pytest.raises(CognitiveError, match="SECRET-MATERIAL-DENIED"):
        await service.register(
            **values, evidence=[{"type": "metric", "id": "m1", "hash": "a" * 64}]
        )


@pytest.mark.asyncio
async def test_reasoning_worker_cannot_decide_or_create_objectives() -> None:
    worker = CognitiveWorker(Session(), "reasoner")  # type: ignore[arg-type]
    values = dict(
        organization_id=uuid.uuid4(),
        record_type="strategic_objective",
        record_key="objective.1",
        version="1.0.0",
        document={},
        classification="internal",
        evidence=[{"type": "metric", "id": "m1", "hash": "a" * 64}],
        confidence=0.5,
        parent_record_id=None,
        created_by="spoof",
    )
    with pytest.raises(CognitiveError, match="WORKER-HAS-NO-AUTHORITY"):
        await worker.produce(**values)


@pytest.mark.asyncio
async def test_decision_requires_human_independence_and_exact_hash() -> None:
    organization_id = uuid.uuid4()
    item = record(organization_id)
    service = CognitiveService(Session())  # type: ignore[arg-type]
    with pytest.raises(CognitiveError, match="RECORD-HASH-MISMATCH"):
        await service.decide(
            item,
            record_hash="f" * 64,
            decision="accept",
            rationale="wrong revision",
            decided_by="executive",
            decision_nonce=uuid.uuid4(),
        )
    with pytest.raises(CognitiveError, match="INDEPENDENT-HUMAN"):
        await service.decide(
            item,
            record_hash=item.record_hash,
            decision="accept",
            rationale="self approval",
            decided_by=item.created_by,
            decision_nonce=uuid.uuid4(),
        )
    session = Session()
    session.gets[(CognitiveRecordModel, item.id)] = item
    with pytest.raises(HTTPException, match="human decision"):
        await decide(item.id, Any, session, Actor("agent", "agent", "reasoner"))  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_decision_nonce_is_idempotent_and_conflicting_replay_fails() -> None:
    organization_id = uuid.uuid4()
    item = record(organization_id)
    nonce = uuid.uuid4()
    prior = type(
        "Prior",
        (),
        {
            "record_hash": item.record_hash,
            "decision": "accept",
            "decision_nonce": nonce,
        },
    )()
    session = Session()
    session.scalar_values = [prior, prior]
    service = CognitiveService(session)  # type: ignore[arg-type]
    assert (
        await service.decide(
            item,
            record_hash=item.record_hash,
            decision="accept",
            rationale="approved",
            decided_by="executive",
            decision_nonce=nonce,
        )
        is prior
    )
    with pytest.raises(CognitiveError, match="DECISION-NONCE-CONFLICT"):
        await service.decide(
            item,
            record_hash=item.record_hash,
            decision="reject",
            rationale="changed replay",
            decided_by="executive",
            decision_nonce=nonce,
        )


@pytest.mark.asyncio
async def test_cross_scope_and_type_confused_links_fail_closed() -> None:
    service = CognitiveService(Session())  # type: ignore[arg-type]
    with pytest.raises(CognitiveError, match="CROSS-SCOPE"):
        await service.link(
            record(uuid.uuid4()), record(uuid.uuid4()), relationship="supports", actor="analyst"
        )
    organization_id = uuid.uuid4()
    with pytest.raises(CognitiveError, match="RELATIONSHIP-TYPE-DENIED"):
        await service.link(
            record(organization_id),
            record(organization_id),
            relationship="executes",
            actor="analyst",
        )
