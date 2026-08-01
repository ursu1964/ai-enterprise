import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.domain.agent_runtime.context import ContextManifest
from ai_enterprise.domain.agent_runtime.output import RuntimeOutputValidation
from ai_enterprise.domain.agent_runtime.runtime import AgentEscalation, AgentRuntimeSession
from ai_enterprise.infrastructure.agent_runtime.models import (
    AgentEscalationModel,
    AgentOutputValidationModel,
    AgentRuntimeSessionModel,
    ContextManifestModel,
    ModelInvocationModel,
)
from ai_enterprise.observability import increment_metric


class RuntimeLineageRepository:
    """Transactional persistence boundary for state, context, model and output lineage."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_update(self, session_id: uuid.UUID) -> AgentRuntimeSessionModel | None:
        return await self.session.scalar(
            select(AgentRuntimeSessionModel)
            .where(AgentRuntimeSessionModel.id == session_id)
            .with_for_update()
        )

    async def save_state(self, aggregate: AgentRuntimeSession) -> None:
        row = await self.get_for_update(aggregate.id)
        if row is None:
            raise LookupError("Runtime session not found")
        row.status = aggregate.status
        row.context_manifest_hash = aggregate.context_manifest_hash or None
        row.selected_model_deployment_id = aggregate.selected_model_deployment_id
        row.counters = {
            "model_calls": aggregate.model_calls,
            "tool_calls": aggregate.tool_calls,
            "input_tokens": aggregate.input_tokens,
            "output_tokens": aggregate.output_tokens,
            "cost_units": aggregate.cost_units,
        }
        if aggregate.status == "running" and row.started_at is None:
            row.started_at = datetime.now(UTC)
        if aggregate.status in {"completed", "failed", "escalated", "cancelled", "timed_out"}:
            row.completed_at = datetime.now(UTC)
        increment_metric(f"agent_runtime_sessions.{aggregate.workflow_type}.{aggregate.status}")
        await self.session.commit()

    async def insert_context(self, manifest: ContextManifest) -> ContextManifestModel:
        document: dict[str, Any] = {
            "runtime_session_id": str(manifest.runtime_session_id),
            "policy_version": manifest.policy_version,
            "sources": list(manifest.sources),
            "prompt_sections": list(manifest.prompt_sections),
            "maximum_classification": manifest.maximum_classification,
        }
        row = ContextManifestModel(
            id=uuid.uuid4(),
            runtime_session_id=manifest.runtime_session_id,
            policy_version=manifest.policy_version,
            manifest_document=document,
            manifest_hash=manifest.manifest_hash,
            total_tokens=manifest.total_tokens,
        )
        self.session.add(row)
        await self.session.commit()
        return row

    async def insert_model_invocation(
        self,
        *,
        runtime_session_id: uuid.UUID,
        model_deployment_id: uuid.UUID,
        invocation_number: int,
        prompt_manifest_hash: str,
        context_manifest_hash: str,
        status: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        response_hash: str | None = None,
        error: dict[str, Any] | None = None,
    ) -> ModelInvocationModel:
        row = ModelInvocationModel(
            id=uuid.uuid4(),
            runtime_session_id=runtime_session_id,
            model_deployment_id=model_deployment_id,
            invocation_number=invocation_number,
            prompt_manifest_hash=prompt_manifest_hash,
            context_manifest_hash=context_manifest_hash,
            input_token_count=input_tokens,
            output_token_count=output_tokens,
            status=status,
            response_hash=response_hash,
            error_document=error,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC) if status in {"succeeded", "failed"} else None,
        )
        self.session.add(row)
        increment_metric(f"agent_model_invocations.{status}")
        await self.session.commit()
        return row

    async def insert_validation(
        self, session_id: uuid.UUID, attempt: int, result: RuntimeOutputValidation
    ) -> AgentOutputValidationModel:
        row = AgentOutputValidationModel(
            id=uuid.uuid4(),
            runtime_session_id=session_id,
            attempt_number=attempt,
            validation_document={"findings": list(result.findings)},
            output_document=result.normalized_output,
            output_hash=result.output_hash,
            valid=result.valid,
        )
        self.session.add(row)
        increment_metric(f"agent_output_validation.{str(result.valid).lower()}")
        await self.session.commit()
        return row

    async def insert_escalation(self, escalation: AgentEscalation) -> AgentEscalationModel:
        row = AgentEscalationModel(
            id=escalation.id,
            runtime_session_id=escalation.runtime_session_id,
            reason_code=escalation.reason_code,
            summary=escalation.summary,
            evidence={"items": list(escalation.evidence)},
            recommended_action=escalation.recommended_action,
            required_human_role=escalation.required_human_role,
        )
        self.session.add(row)
        increment_metric(f"agent_escalations.{escalation.reason_code}")
        await self.session.commit()
        return row
