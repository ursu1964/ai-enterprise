from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.routes.ecosystem import _human, router
from ai_enterprise.application.ecosystem_service import (
    ASSET_TYPES,
    EcosystemError,
    EcosystemObservationWorker,
    EcosystemService,
)
from ai_enterprise.infrastructure.ecosystem.models import (
    EcosystemAssetModel,
    EcosystemEntityModel,
    EcosystemGatewayInvocationModel,
)


class Rows:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    def all(self) -> list[Any]:
        return self.rows


class Session:
    def __init__(self) -> None:
        self.gets: dict[tuple[type, uuid.UUID], Any] = {}
        self.scalar_values: list[Any] = []
        self.scalars_values: list[list[Any]] = []
        self.added: list[Any] = []

    async def get(self, model: type, identity: uuid.UUID) -> Any:
        return self.gets.get((model, identity))

    async def scalar(self, statement: object) -> Any:
        return self.scalar_values.pop(0) if self.scalar_values else None

    async def scalars(self, statement: object) -> Rows:
        return Rows(self.scalars_values.pop(0) if self.scalars_values else [])

    def add(self, row: Any) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        return None


def entity(organization_id: uuid.UUID, entity_type: str = "partner") -> EcosystemEntityModel:
    return EcosystemEntityModel(
        id=uuid.uuid4(),
        organization_id=organization_id,
        entity_type=entity_type,
        entity_key=f"partner.{uuid.uuid4().hex}",
        display_name="Partner",
        entity_document={},
        entity_hash="a" * 64,
        classification="internal",
        created_by="registrar",
        created_at=datetime.now(UTC),
    )


def asset(organization_id: uuid.UUID, entity_id: uuid.UUID, kind: str) -> EcosystemAssetModel:
    return EcosystemAssetModel(
        id=uuid.uuid4(),
        organization_id=organization_id,
        entity_id=entity_id,
        asset_type=kind,
        asset_key=f"{kind}.primary",
        version="1.0.0",
        asset_document={},
        asset_hash=("b" if kind == "connector" else "c") * 64,
        evidence_manifest=[{"type": "audit", "id": "source", "hash": "d" * 64}],
        evidence_hash="e" * 64,
        parent_asset_id=None,
        created_by="integration-engineer",
        created_at=datetime.now(UTC),
    )


def test_m1_m16_asset_registry_api_and_append_only_migration_are_complete() -> None:
    assert ASSET_TYPES == {
        "connector",
        "external_contract",
        "federation_agreement",
        "trust_assessment",
        "identity_mapping",
        "capability_offer",
        "dependency",
        "vendor_risk",
        "data_exchange",
        "regulatory_policy",
        "cloud_binding",
        "event_binding",
        "federation_protocol",
        "connector_health",
        "contract_drift",
    }
    paths = {f"/api/v1{route.path}" for route in router.routes}
    for path in (
        "connectors",
        "contracts",
        "federations",
        "trust",
        "identities",
        "capabilities",
        "supply-chain",
        "vendor-risks",
        "data-exchanges",
        "regulations",
        "cloud-bindings",
        "event-bindings",
        "federation-protocols",
        "graph",
    ):
        assert f"/api/v1/ecosystem/{path}" in paths
    migration = (
        Path(__file__).parents[3]
        / "migrations/versions/c51da90bc178_add_governed_federated_ecosystem.py"
    ).read_text()
    assert 'down_revision: str | None = "c43c98fb0a67"' in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "DROP TRIGGER" in migration and "DROP FUNCTION" in migration
    assert EcosystemAssetModel.__table__.c.asset_hash.unique
    assert EcosystemGatewayInvocationModel.__table__.c.invocation_hash.unique


@pytest.mark.asyncio
async def test_connector_contract_gateway_requires_current_hash_bound_approvals() -> None:
    organization_id = uuid.uuid4()
    partner = entity(organization_id)
    connector = asset(organization_id, partner.id, "connector")
    contract = asset(organization_id, partner.id, "external_contract")
    session = Session()
    session.gets[(EcosystemAssetModel, connector.id)] = connector
    session.gets[(EcosystemAssetModel, contract.id)] = contract
    service = EcosystemService(session)  # type: ignore[arg-type]
    session.scalar_values = [None]
    with pytest.raises(EcosystemError, match="ACTIVE-APPROVAL-REQUIRED"):
        await service.record_invocation(
            organization_id=organization_id,
            connector_asset_id=connector.id,
            contract_asset_id=contract.id,
            direction="outbound",
            operation="issues.list",
            identity_reference="workload:sync",
            request_nonce=uuid.uuid4(),
            request_hash="f" * 64,
            response_hash=None,
            policy_version="gateway-v1",
            status="denied",
            evidence_document={"reason": "approval missing"},
            actor="gateway",
        )
    session.scalar_values = [None, "approve", uuid.uuid4(), "approve", uuid.uuid4(), None]
    row = await service.record_invocation(
        organization_id=organization_id,
        connector_asset_id=connector.id,
        contract_asset_id=contract.id,
        direction="outbound",
        operation="issues.list",
        identity_reference="workload:sync",
        request_nonce=uuid.uuid4(),
        request_hash="f" * 64,
        response_hash="1" * 64,
        policy_version="gateway-v1",
        status="completed",
        evidence_document={"schema_valid": True, "policy_allowed": True},
        actor="gateway",
    )
    assert row.connector_asset_id == connector.id
    assert len(row.invocation_hash) == 64


@pytest.mark.asyncio
async def test_approval_is_human_independent_hash_bound_and_expiring() -> None:
    organization_id = uuid.uuid4()
    partner = entity(organization_id)
    connector = asset(organization_id, partner.id, "connector")
    service = EcosystemService(Session())  # type: ignore[arg-type]
    with pytest.raises(EcosystemError, match="INDEPENDENT-APPROVAL"):
        await service.approve(
            connector,
            asset_hash=connector.asset_hash,
            decision="approve",
            decided_by=connector.created_by,
            board_role="federation-board",
            rationale="self approval",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
    with pytest.raises(EcosystemError, match="FUTURE-APPROVAL-EXPIRY"):
        await service.approve(
            connector,
            asset_hash=connector.asset_hash,
            decision="approve",
            decided_by="board",
            board_role="federation-board",
            rationale="expired",
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
    with pytest.raises(HTTPException, match="human approval"):
        _human(Actor("agent", "agent", "federation-board"))


@pytest.mark.asyncio
async def test_cross_organization_graph_edges_are_denied() -> None:
    source, target = entity(uuid.uuid4()), entity(uuid.uuid4())
    with pytest.raises(EcosystemError, match="CROSS-SCOPE-OR-SELF"):
        await EcosystemService(Session()).add_edge(  # type: ignore[arg-type]
            source, target, relationship="collaborates", document={}, actor="graph-worker"
        )


@pytest.mark.asyncio
async def test_worker_can_observe_but_cannot_create_trust_or_federation() -> None:
    organization_id = uuid.uuid4()
    partner = entity(organization_id)
    session = Session()
    session.gets[(EcosystemEntityModel, partner.id)] = partner
    worker = EcosystemObservationWorker(session, "health-worker")  # type: ignore[arg-type]
    values = dict(
        organization_id=organization_id,
        entity_id=partner.id,
        asset_type="trust_assessment",
        asset_key="trust.partner",
        version="1.0.0",
        document={"level": "strategic"},
        evidence=[{"type": "audit", "id": "health", "hash": "a" * 64}],
        parent_asset_id=None,
        created_by="spoofed-human",
    )
    with pytest.raises(EcosystemError, match="WORKER-MAY-ONLY-OBSERVE"):
        await worker.record(**values)
    values["asset_type"] = "connector_health"
    values["asset_key"] = "health.partner"
    observed = await worker.record(**values)
    assert observed.created_by == "health-worker"


@pytest.mark.asyncio
async def test_latest_rejection_revokes_gateway_and_nonce_replay_conflicts() -> None:
    organization_id = uuid.uuid4()
    partner = entity(organization_id)
    connector = asset(organization_id, partner.id, "connector")
    contract = asset(organization_id, partner.id, "external_contract")
    session = Session()
    session.gets[(EcosystemAssetModel, connector.id)] = connector
    session.gets[(EcosystemAssetModel, contract.id)] = contract
    service = EcosystemService(session)  # type: ignore[arg-type]
    nonce = uuid.uuid4()
    session.scalar_values = [None, "reject", uuid.uuid4()]
    with pytest.raises(EcosystemError, match="ACTIVE-APPROVAL-REQUIRED"):
        await service.record_invocation(
            organization_id=organization_id,
            connector_asset_id=connector.id,
            contract_asset_id=contract.id,
            direction="outbound",
            operation="sync",
            identity_reference="workload:sync",
            request_nonce=nonce,
            request_hash="f" * 64,
            response_hash=None,
            policy_version="v1",
            status="denied",
            evidence_document={},
            actor="gateway",
        )
    prior = EcosystemGatewayInvocationModel(
        id=uuid.uuid4(),
        organization_id=organization_id,
        connector_asset_id=connector.id,
        contract_asset_id=contract.id,
        direction="outbound",
        operation="sync",
        identity_reference="workload:sync",
        request_nonce=nonce,
        request_hash="1" * 64,
        response_hash=None,
        policy_version="v1",
        status="completed",
        evidence_document={},
        invocation_hash="2" * 64,
        occurred_at=datetime.now(UTC),
    )
    session.scalar_values = [prior]
    with pytest.raises(EcosystemError, match="REPLAY-NONCE-CONFLICT"):
        await service.record_invocation(
            organization_id=organization_id,
            connector_asset_id=connector.id,
            contract_asset_id=contract.id,
            direction="outbound",
            operation="sync",
            identity_reference="workload:sync",
            request_nonce=nonce,
            request_hash="3" * 64,
            response_hash=None,
            policy_version="v1",
            status="completed",
            evidence_document={},
            actor="gateway",
        )


@pytest.mark.asyncio
async def test_secret_material_and_relationship_type_are_rejected_before_persistence() -> None:
    organization_id = uuid.uuid4()
    source, target = entity(organization_id), entity(organization_id)
    service = EcosystemService(Session())  # type: ignore[arg-type]
    with pytest.raises(EcosystemError, match="SECRET-MATERIAL-DENIED"):
        await service.add_edge(
            source,
            target,
            relationship="trusts",
            document={"nested": {"client-secret": "do-not-store"}},
            actor="operator",
        )
    with pytest.raises(EcosystemError, match="RELATIONSHIP-TYPE-DENIED"):
        await service.add_edge(
            source,
            target,
            relationship="admin_override",
            document={},
            actor="operator",
        )


def test_hardening_migration_enforces_scope_replay_hashes_and_reversible_downgrade() -> None:
    migration = (
        Path(__file__).parents[3] / "migrations/versions/c52eb01cd289_harden_federated_ecosystem.py"
    ).read_text()
    assert 'down_revision: str | None = "c51da90bc178"' in migration
    assert "fk_ecosystem_assets_entity_org" in migration
    assert "uq_ecosystem_invocation_nonce" in migration
    assert "ck_ecosystem_approval_expiry" in migration
    assert "_sha256" in migration
    assert "drop_column" in migration and "create_unique_constraint" in migration
