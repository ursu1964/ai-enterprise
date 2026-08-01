from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.domain.resilience.entities import (
    BackupManifest,
    ContinuityActivation,
    ContinuityPolicy,
    RecoveryObjective,
)
from ai_enterprise.domain.resilience.enums import (
    BackupStatus,
    Capability,
    ContinuityMode,
    CriticalityTier,
)
from ai_enterprise.infrastructure.database.models import AuditEventModel
from ai_enterprise.infrastructure.resilience.models import (
    BackupManifestModel,
    ContinuityActivationModel,
    RecoveryObjectiveModel,
    ResilienceServiceModel,
)


class SqlAlchemyResilienceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def active_continuity(self) -> tuple[ContinuityActivation, ...]:
        rows = (
            (
                await self.session.execute(
                    select(ContinuityActivationModel).where(
                        ContinuityActivationModel.closed_at.is_(None)
                    )
                )
            )
            .scalars()
            .all()
        )
        return tuple(
            ContinuityActivation(
                id=row.id,
                policy=ContinuityPolicy(
                    mode=ContinuityMode(row.mode),
                    allowed=frozenset(Capability(value) for value in row.allowed_capabilities),
                    prohibited=frozenset(
                        Capability(value) for value in row.prohibited_capabilities
                    ),
                    maximum_duration_seconds=int(
                        (row.expires_at - row.activated_at).total_seconds()
                    ),
                    policy_version=row.policy_version,
                ),
                activated_at=row.activated_at,
                expires_at=row.expires_at,
                activated_by=row.activated_by,
                reason=row.reason,
                closed_at=row.closed_at,
                exit_reviewed_by=row.exit_reviewed_by,
            )
            for row in rows
        )

    async def latest_objective(self, service_id: uuid.UUID) -> RecoveryObjective | None:
        result = await self.session.execute(
            select(RecoveryObjectiveModel, ResilienceServiceModel)
            .join(
                ResilienceServiceModel,
                ResilienceServiceModel.id == RecoveryObjectiveModel.service_id,
            )
            .where(RecoveryObjectiveModel.service_id == service_id)
            .order_by(RecoveryObjectiveModel.policy_version.desc())
            .limit(1)
        )
        pair = result.one_or_none()
        if pair is None:
            return None
        row, service = pair
        return RecoveryObjective(
            service_id=row.service_id,
            tier=CriticalityTier(row.tier),
            rto_seconds=row.rto_seconds,
            rpo_seconds=row.rpo_seconds,
            mtpd_seconds=row.mtpd_seconds,
            work_recovery_time_seconds=row.work_recovery_time_seconds,
            primary_owner=service.primary_owner,
            deputy_owner=service.deputy_owner,
            policy_version=row.policy_version,
            approved_by=row.approved_by,
            approved_at=row.approved_at,
        )

    async def latest_backup(self) -> BackupManifest | None:
        row = await self.session.scalar(
            select(BackupManifestModel).order_by(BackupManifestModel.created_at.desc()).limit(1)
        )
        if row is None:
            return None
        return BackupManifest(
            row.id,
            row.backup_type,
            row.content_hash,
            row.object_count,
            row.total_bytes,
            row.encryption_profile,
            row.schema_version,
            row.audit_checkpoint_hash,
            tuple(row.storage_locations),
            BackupStatus(row.status),
        )

    def audit(
        self,
        *,
        event_type: str,
        actor_id: str,
        payload: dict[str, object],
    ) -> None:
        self.session.add(
            AuditEventModel(
                id=uuid.uuid4(),
                project_id=None,
                event_type=event_type,
                actor_type="human",
                actor_id=actor_id,
                payload=payload,
                created_at=datetime.now(UTC),
            )
        )
