from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.organization_persistence_service import canonical_hash
from ai_enterprise.domain.specification.kernel import semantic_version
from ai_enterprise.infrastructure.database.models import AuditEventModel
from ai_enterprise.infrastructure.ecosystem.models import (
    EcosystemApprovalModel,
    EcosystemAssetModel,
    EcosystemEdgeModel,
    EcosystemEntityModel,
    EcosystemGatewayInvocationModel,
)
from ai_enterprise.observability import increment_metric

ENTITY_TYPES = {
    "partner",
    "supplier",
    "customer",
    "cloud_provider",
    "identity_provider",
    "open_source_project",
    "regulator",
    "certification_body",
    "external_service",
}
ASSET_TYPES = {
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
OBSERVATION_TYPES = {"connector_health", "contract_drift", "vendor_risk"}
MAX_DOCUMENT_BYTES = 1_048_576
RELATIONSHIPS = {
    "consumes",
    "provides",
    "certifies",
    "regulates",
    "supplies",
    "collaborates",
    "federates_with",
    "trusts",
}
SENSITIVE_FIELDS = {
    "access_token",
    "api_key",
    "authorization",
    "client_secret",
    "credential",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "token",
}


class EcosystemError(ValueError):
    def __init__(self, detail: str, status_code: int = 409) -> None:
        super().__init__(detail)
        self.status_code = status_code


class EcosystemService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _audit(self, event: str, actor: str, payload: dict[str, Any]) -> None:
        self.session.add(
            AuditEventModel(
                project_id=None,
                event_type=event,
                actor_type="ecosystem-governance",
                actor_id=actor,
                payload=payload,
            )
        )

    @staticmethod
    def _bounded(document: dict[str, Any]) -> None:
        if len(json.dumps(document, sort_keys=True).encode()) > MAX_DOCUMENT_BYTES:
            raise EcosystemError("ECO-001 DOCUMENT-TOO-LARGE", 413)

        def contains_secret(value: Any) -> bool:
            if isinstance(value, dict):
                return any(
                    str(key).lower().replace("-", "_") in SENSITIVE_FIELDS or contains_secret(item)
                    for key, item in value.items()
                )
            if isinstance(value, list):
                return any(contains_secret(item) for item in value)
            return False

        if contains_secret(document):
            raise EcosystemError("ECO-003 SECRET-MATERIAL-DENIED", 422)

    async def register_entity(
        self,
        *,
        organization_id: uuid.UUID,
        entity_type: str,
        entity_key: str,
        display_name: str,
        document: dict[str, Any],
        classification: str,
        created_by: str,
    ) -> EcosystemEntityModel:
        if entity_type not in ENTITY_TYPES:
            raise EcosystemError("ECO-002 ENTITY-TYPE-DENIED", 422)
        self._bounded(document)
        bound = {
            "organization_id": str(organization_id),
            "entity_type": entity_type,
            "entity_key": entity_key,
            "display_name": display_name,
            "document": document,
            "classification": classification,
        }
        digest = canonical_hash(bound)
        existing = await self.session.scalar(
            select(EcosystemEntityModel).where(EcosystemEntityModel.entity_hash == digest)
        )
        if existing is not None:
            return existing
        row = EcosystemEntityModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            entity_type=entity_type,
            entity_key=entity_key,
            display_name=display_name,
            entity_document=document,
            entity_hash=digest,
            classification=classification,
            created_by=created_by,
            created_at=datetime.now(UTC),
        )
        self.session.add(row)
        self._audit(
            "EcosystemEntityRegistered",
            created_by,
            {"entity_id": str(row.id), "entity_hash": digest},
        )
        increment_metric(f"ecosystem.entities.{entity_type}")
        await self.session.commit()
        return row

    async def register_asset(
        self,
        *,
        organization_id: uuid.UUID,
        entity_id: uuid.UUID,
        asset_type: str,
        asset_key: str,
        version: str,
        document: dict[str, Any],
        evidence: list[dict[str, str]],
        created_by: str,
        parent_asset_id: uuid.UUID | None = None,
    ) -> EcosystemAssetModel:
        if asset_type not in ASSET_TYPES:
            raise EcosystemError("ECO-010 ASSET-TYPE-DENIED", 422)
        self._bounded(document)
        entity = await self.session.get(EcosystemEntityModel, entity_id)
        if entity is None or entity.organization_id != organization_id:
            raise EcosystemError("ECO-011 ENTITY-SCOPE-MISMATCH", 403)
        if not evidence or any(len(item.get("hash", "")) != 64 for item in evidence):
            raise EcosystemError("ECO-012 EVIDENCE-MANIFEST-INVALID", 422)
        evidence_manifest = sorted(
            evidence, key=lambda item: (item.get("type", ""), item.get("id", ""))
        )
        evidence_hash = canonical_hash({"evidence": evidence_manifest})
        if parent_asset_id:
            parent = await self.session.get(EcosystemAssetModel, parent_asset_id)
            if (
                parent is None
                or parent.organization_id != organization_id
                or parent.asset_type != asset_type
                or parent.asset_key != asset_key
                or semantic_version(version) <= semantic_version(parent.version)
            ):
                raise EcosystemError("ECO-013 INVALID-ASSET-LINEAGE", 422)
        bound = {
            "organization_id": str(organization_id),
            "entity_id": str(entity_id),
            "asset_type": asset_type,
            "asset_key": asset_key,
            "version": version,
            "document": document,
            "evidence_hash": evidence_hash,
            "parent_asset_id": str(parent_asset_id) if parent_asset_id else None,
        }
        digest = canonical_hash(bound)
        existing = await self.session.scalar(
            select(EcosystemAssetModel).where(EcosystemAssetModel.asset_hash == digest)
        )
        if existing is not None:
            return existing
        row = EcosystemAssetModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            entity_id=entity_id,
            asset_type=asset_type,
            asset_key=asset_key,
            version=version,
            asset_document=document,
            asset_hash=digest,
            evidence_manifest=evidence_manifest,
            evidence_hash=evidence_hash,
            parent_asset_id=parent_asset_id,
            created_by=created_by,
            created_at=datetime.now(UTC),
        )
        self.session.add(row)
        self._audit(
            "EcosystemAssetRegistered",
            created_by,
            {"asset_id": str(row.id), "asset_type": asset_type, "asset_hash": digest},
        )
        increment_metric(f"ecosystem.assets.{asset_type}")
        await self.session.commit()
        return row

    async def approve(
        self,
        asset: EcosystemAssetModel,
        *,
        asset_hash: str,
        decision: str,
        decided_by: str,
        board_role: str,
        rationale: str,
        expires_at: datetime | None,
    ) -> EcosystemApprovalModel:
        if asset.asset_hash != asset_hash:
            raise EcosystemError("ECO-020 ASSET-HASH-MISMATCH")
        if asset.created_by == decided_by:
            raise EcosystemError("ECO-021 INDEPENDENT-APPROVAL-REQUIRED", 403)
        if decision not in {"approve", "reject"} or not rationale.strip():
            raise EcosystemError("ECO-022 INVALID-DECISION", 422)
        if decision == "approve" and (expires_at is None or expires_at <= datetime.now(UTC)):
            raise EcosystemError("ECO-023 FUTURE-APPROVAL-EXPIRY-REQUIRED", 422)
        existing = await self.session.scalar(
            select(EcosystemApprovalModel).where(
                EcosystemApprovalModel.asset_id == asset.id,
                EcosystemApprovalModel.asset_hash == asset_hash,
                EcosystemApprovalModel.decision == decision,
                EcosystemApprovalModel.decided_by == decided_by,
                EcosystemApprovalModel.expires_at == expires_at,
            )
        )
        if existing is not None:
            return existing
        row = EcosystemApprovalModel(
            id=uuid.uuid4(),
            organization_id=asset.organization_id,
            asset_id=asset.id,
            asset_hash=asset_hash,
            decision=decision,
            decided_by=decided_by,
            board_role=board_role,
            rationale=rationale,
            expires_at=expires_at,
            decided_at=datetime.now(UTC),
        )
        self.session.add(row)
        self._audit(
            "EcosystemAssetHumanDecision",
            decided_by,
            {"approval_id": str(row.id), "asset_hash": asset_hash, "decision": decision},
        )
        await self.session.commit()
        return row

    async def record_invocation(
        self,
        *,
        organization_id: uuid.UUID,
        connector_asset_id: uuid.UUID,
        contract_asset_id: uuid.UUID,
        direction: str,
        operation: str,
        identity_reference: str,
        request_nonce: uuid.UUID,
        request_hash: str,
        response_hash: str | None,
        policy_version: str,
        status: str,
        evidence_document: dict[str, Any],
        actor: str,
    ) -> EcosystemGatewayInvocationModel:
        connector = await self.session.get(EcosystemAssetModel, connector_asset_id)
        contract = await self.session.get(EcosystemAssetModel, contract_asset_id)
        if (
            connector is None
            or contract is None
            or connector.organization_id != organization_id
            or contract.organization_id != organization_id
            or connector.asset_type != "connector"
            or contract.asset_type != "external_contract"
        ):
            raise EcosystemError("ECO-030 CONNECTOR-CONTRACT-SCOPE-MISMATCH", 403)
        if direction not in {"inbound", "outbound"} or status not in {
            "authorized",
            "denied",
            "completed",
            "failed",
        }:
            raise EcosystemError("ECO-032 INVOCATION-TYPE-DENIED", 422)
        replay = await self.session.scalar(
            select(EcosystemGatewayInvocationModel).where(
                EcosystemGatewayInvocationModel.organization_id == organization_id,
                EcosystemGatewayInvocationModel.connector_asset_id == connector_asset_id,
                EcosystemGatewayInvocationModel.request_nonce == request_nonce,
            )
        )
        if replay is not None:
            if replay.request_hash != request_hash or replay.contract_asset_id != contract_asset_id:
                raise EcosystemError("ECO-033 REPLAY-NONCE-CONFLICT", 409)
            return replay
        now = datetime.now(UTC)
        for asset in (connector, contract):
            latest_decision = await self.session.scalar(
                select(EcosystemApprovalModel.decision)
                .where(
                    EcosystemApprovalModel.asset_id == asset.id,
                    EcosystemApprovalModel.asset_hash == asset.asset_hash,
                )
                .order_by(EcosystemApprovalModel.decided_at.desc())
                .limit(1)
            )
            active_approval = await self.session.scalar(
                select(EcosystemApprovalModel.id)
                .where(
                    EcosystemApprovalModel.asset_id == asset.id,
                    EcosystemApprovalModel.asset_hash == asset.asset_hash,
                    EcosystemApprovalModel.decision == "approve",
                    EcosystemApprovalModel.expires_at > now,
                )
                .order_by(EcosystemApprovalModel.decided_at.desc())
                .limit(1)
            )
            if latest_decision != "approve" or active_approval is None:
                raise EcosystemError("ECO-031 ACTIVE-APPROVAL-REQUIRED", 403)
        self._bounded(evidence_document)
        bound = {
            "organization_id": str(organization_id),
            "connector_asset_id": str(connector_asset_id),
            "contract_asset_id": str(contract_asset_id),
            "direction": direction,
            "operation": operation,
            "identity_reference": identity_reference,
            "request_nonce": str(request_nonce),
            "request_hash": request_hash,
            "response_hash": response_hash,
            "policy_version": policy_version,
            "status": status,
            "evidence": evidence_document,
        }
        digest = canonical_hash(bound)
        existing = await self.session.scalar(
            select(EcosystemGatewayInvocationModel).where(
                EcosystemGatewayInvocationModel.invocation_hash == digest
            )
        )
        if existing is not None:
            return existing
        row = EcosystemGatewayInvocationModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            connector_asset_id=connector_asset_id,
            contract_asset_id=contract_asset_id,
            direction=direction,
            operation=operation,
            identity_reference=identity_reference,
            request_nonce=request_nonce,
            request_hash=request_hash,
            response_hash=response_hash,
            policy_version=policy_version,
            status=status,
            evidence_document=evidence_document,
            invocation_hash=digest,
            occurred_at=now,
        )
        self.session.add(row)
        self._audit(
            "EcosystemGatewayInvocationRecorded",
            actor,
            {"invocation_id": str(row.id), "status": status, "invocation_hash": digest},
        )
        increment_metric(f"ecosystem.gateway.{direction}.{status}")
        await self.session.commit()
        return row

    async def add_edge(
        self,
        source: EcosystemEntityModel,
        target: EcosystemEntityModel,
        *,
        relationship: str,
        document: dict[str, Any],
        actor: str,
    ) -> EcosystemEdgeModel:
        if source.id == target.id or source.organization_id != target.organization_id:
            raise EcosystemError("ECO-040 CROSS-SCOPE-OR-SELF-EDGE", 403)
        if relationship not in RELATIONSHIPS:
            raise EcosystemError("ECO-041 RELATIONSHIP-TYPE-DENIED", 422)
        self._bounded(document)
        bound = {
            "source_hash": source.entity_hash,
            "target_hash": target.entity_hash,
            "relationship": relationship,
            "document": document,
        }
        digest = canonical_hash(bound)
        existing = await self.session.scalar(
            select(EcosystemEdgeModel).where(EcosystemEdgeModel.edge_hash == digest)
        )
        if existing is not None:
            return existing
        row = EcosystemEdgeModel(
            id=uuid.uuid4(),
            organization_id=source.organization_id,
            source_entity_id=source.id,
            target_entity_id=target.id,
            relationship=relationship,
            edge_document=document,
            edge_hash=digest,
            recorded_at=datetime.now(UTC),
        )
        self.session.add(row)
        self._audit(
            "EcosystemRelationshipRecorded", actor, {"edge_id": str(row.id), "edge_hash": digest}
        )
        await self.session.commit()
        return row


class EcosystemObservationWorker:
    def __init__(self, session: AsyncSession, worker_id: str) -> None:
        self.service, self.worker_id = EcosystemService(session), worker_id

    async def record(self, **values: Any) -> EcosystemAssetModel:
        if values.get("asset_type") not in OBSERVATION_TYPES:
            raise EcosystemError("ECO-050 WORKER-MAY-ONLY-OBSERVE", 403)
        values.pop("created_by", None)
        return await self.service.register_asset(**values, created_by=self.worker_id)
