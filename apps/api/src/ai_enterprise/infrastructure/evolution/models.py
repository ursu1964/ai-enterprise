import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_enterprise.infrastructure.database.models import Base


class _ImmutableEvolutionModel(Base):
    __abstract__ = True
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    change_proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ArchitectureGovernanceRecordModel(_ImmutableEvolutionModel):
    __tablename__ = "architecture_governance_records"
    __table_args__ = (
        UniqueConstraint("change_proposal_id", "version", name="uq_arch_governance_version"),
    )


class PolicyEvolutionRecordModel(_ImmutableEvolutionModel):
    __tablename__ = "policy_evolution_records"
    __table_args__ = (
        UniqueConstraint("change_proposal_id", "version", name="uq_policy_evolution_version"),
    )


class WorkflowEvolutionRecordModel(_ImmutableEvolutionModel):
    __tablename__ = "workflow_evolution_records"
    __table_args__ = (
        UniqueConstraint("change_proposal_id", "version", name="uq_workflow_evolution_version"),
    )


class AgentCrewEvolutionRecordModel(_ImmutableEvolutionModel):
    __tablename__ = "agent_crew_evolution_records"
    __table_args__ = (
        UniqueConstraint("change_proposal_id", "version", name="uq_agent_crew_evolution_version"),
    )


class SchemaEvolutionRecordModel(_ImmutableEvolutionModel):
    __tablename__ = "schema_evolution_records"
    __table_args__ = (
        UniqueConstraint("change_proposal_id", "version", name="uq_schema_evolution_version"),
    )


class ExperimentRecordModel(_ImmutableEvolutionModel):
    __tablename__ = "enterprise_experiment_records"
    __table_args__ = (
        UniqueConstraint("change_proposal_id", "version", name="uq_experiment_version"),
    )


class SimulationRecordModel(_ImmutableEvolutionModel):
    __tablename__ = "simulation_shadow_records"
    __table_args__ = (
        UniqueConstraint("change_proposal_id", "version", name="uq_simulation_version"),
    )


class RolloutRecordModel(_ImmutableEvolutionModel):
    __tablename__ = "transformation_rollout_records"
    __table_args__ = (UniqueConstraint("change_proposal_id", "version", name="uq_rollout_version"),)


class ControlValidationRecordModel(_ImmutableEvolutionModel):
    __tablename__ = "control_validation_records"
    __table_args__ = (
        UniqueConstraint("change_proposal_id", "version", name="uq_control_validation_version"),
    )


class ImprovementDebtRecordModel(_ImmutableEvolutionModel):
    __tablename__ = "improvement_debt_records"
    __table_args__ = (
        UniqueConstraint("change_proposal_id", "version", name="uq_improvement_debt_version"),
    )


class ConstitutionalGovernanceRecordModel(_ImmutableEvolutionModel):
    __tablename__ = "constitutional_governance_records"
    __table_args__ = (
        UniqueConstraint("change_proposal_id", "version", name="uq_constitutional_version"),
    )
