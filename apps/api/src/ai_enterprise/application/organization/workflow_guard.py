"""Fail-closed organizational binding at every consequential workflow boundary.

The guard is deliberately independent of persistence.  SQL repositories can load the
governed identity and participation records, then pass them through this boundary.
Workers receive the resulting immutable grant and must verify it immediately before
invoking a model or a tool.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Protocol
from uuid import UUID


class WorkflowAction(StrEnum):
    REQUIREMENTS_AUTHOR = "author-requirements"
    REQUIREMENTS_REVIEW = "review-requirements"
    ARCHITECTURE_AUTHOR = "author-architecture"
    ARCHITECTURE_REVIEW = "review-architecture"
    DECOMPOSE = "decompose-work-packages"
    EXECUTE = "implement-work-package"
    PATCH_REVIEW = "review-generated-patch"
    INTEGRATE = "perform-controlled-integration"
    APPROVE_REQUIREMENTS = "approve-requirements"
    APPROVE_ARCHITECTURE = "approve-architecture"
    APPROVE_DECOMPOSITION = "approve-decomposition"
    APPROVE_INTEGRATION = "approve-integration"


HUMAN_ONLY_ACTIONS = frozenset(
    {
        WorkflowAction.APPROVE_REQUIREMENTS,
        WorkflowAction.APPROVE_ARCHITECTURE,
        WorkflowAction.APPROVE_DECOMPOSITION,
        WorkflowAction.APPROVE_INTEGRATION,
    }
)


@dataclass(frozen=True, slots=True)
class AgentRuntimeIdentity:
    agent_profile_id: UUID
    agent_profile_version_id: UUID
    assignment_id: UUID
    role_version_id: UUID
    configuration_hash: str

    def __post_init__(self) -> None:
        if len(self.configuration_hash) != 64:
            raise ValueError("configuration_hash must be a SHA-256 hex digest")
        try:
            bytes.fromhex(self.configuration_hash)
        except ValueError as exc:
            raise ValueError("configuration_hash must be hexadecimal") from exc


@dataclass(frozen=True, slots=True)
class WorkflowBinding:
    workflow_type: str
    action: WorkflowAction
    scope_type: str
    scope_id: UUID
    artifact_hash: str | None
    correlation_id: UUID
    causation_id: UUID | None = None
    high_risk: bool = False


@dataclass(frozen=True, slots=True)
class AuthorityResult:
    allowed: bool
    code: str
    reasons: tuple[str, ...]
    policy_versions: tuple[str, ...]


class AuthorityEvaluator(Protocol):
    def evaluate(
        self,
        *,
        identity: AgentRuntimeIdentity,
        capability: str,
        scope_type: str,
        scope_id: UUID,
        now: datetime,
    ) -> AuthorityResult: ...


class DomainAuthorityContextLoader(Protocol):
    """Loads one immutable organizational snapshot for an authority decision."""

    def load(
        self,
        *,
        identity: AgentRuntimeIdentity,
        scope_type: str,
        scope_id: UUID,
        now: datetime,
    ) -> object: ...


class DomainAuthorityAdapter:
    """Connect the workflow boundary to the P7 organizational domain evaluator."""

    def __init__(self, context_loader: DomainAuthorityContextLoader) -> None:
        from ai_enterprise.domain.organization.authority import AuthorityService

        self._context_loader = context_loader
        self._service = AuthorityService()

    def evaluate(
        self,
        *,
        identity: AgentRuntimeIdentity,
        capability: str,
        scope_type: str,
        scope_id: UUID,
        now: datetime,
    ) -> AuthorityResult:
        from ai_enterprise.domain.organization.authority import (
            AuthorityContext,
            AuthorityRequest,
        )

        context = self._context_loader.load(
            identity=identity,
            scope_type=scope_type,
            scope_id=scope_id,
            now=now,
        )
        if not isinstance(context, AuthorityContext):
            raise TypeError("Context loader must return an AuthorityContext")
        if (
            context.actor.id != identity.agent_profile_id
            or context.profile_version.id != identity.agent_profile_version_id
        ):
            return AuthorityResult(
                allowed=False,
                code="AUTH-IDENTITY-BINDING-MISMATCH",
                reasons=("Loaded authority context does not match the exact runtime identity",),
                policy_versions=context.policy_versions,
            )
        matching_assignment = next(
            (
                item
                for item in context.assignments
                if item.id == identity.assignment_id
                and item.role_version_id == identity.role_version_id
            ),
            None,
        )
        if matching_assignment is None:
            return AuthorityResult(
                allowed=False,
                code="AUTH-ASSIGNMENT-BINDING-MISMATCH",
                reasons=("The exact assignment and role binding is unavailable",),
                policy_versions=context.policy_versions,
            )
        if not hmac.compare_digest(
            context.profile_version.configuration_hash, identity.configuration_hash
        ):
            return AuthorityResult(
                allowed=False,
                code="AUTH-CONFIGURATION-BINDING-MISMATCH",
                reasons=("Profile configuration hash differs from authorization",),
                policy_versions=context.policy_versions,
            )
        decision = self._service.evaluate(
            AuthorityRequest(
                actor_id=identity.agent_profile_id,
                capability=capability,
                scope_type=scope_type,
                scope_id=scope_id,
                action_context={"activity_type": capability},
            ),
            context,
        )
        return AuthorityResult(
            allowed=decision.allowed,
            code=decision.code,
            reasons=tuple(str(reason) for reason in decision.reasons),
            policy_versions=decision.policy_versions,
        )


@dataclass(frozen=True, slots=True)
class Participation:
    identity: AgentRuntimeIdentity
    action: WorkflowAction
    scope_type: str
    scope_id: UUID
    artifact_hash: str | None
    correlation_id: UUID
    causation_id: UUID | None
    occurred_at: datetime


class ParticipationLedger(Protocol):
    def for_scope(self, *, scope_type: str, scope_id: UUID) -> tuple[Participation, ...]: ...

    def append(self, participation: Participation) -> None: ...


class InMemoryParticipationLedger:
    """Deterministic test/local adapter; production uses the SQL participation store."""

    def __init__(self) -> None:
        self._records: list[Participation] = []

    def for_scope(self, *, scope_type: str, scope_id: UUID) -> tuple[Participation, ...]:
        return tuple(
            record
            for record in self._records
            if record.scope_type == scope_type and record.scope_id == scope_id
        )

    def append(self, participation: Participation) -> None:
        self._records.append(participation)


@dataclass(frozen=True, slots=True)
class AuthorizationGrant:
    identity: AgentRuntimeIdentity
    binding: WorkflowBinding
    capability: str
    policy_versions: tuple[str, ...]
    issued_at: datetime
    binding_digest: str

    def verify_runtime_identity(self, actual: AgentRuntimeIdentity) -> None:
        if actual != self.identity:
            raise AuthorizationDenied(
                code="ORG-RUNTIME-IDENTITY-SUBSTITUTION",
                reasons=("Runtime identity differs from the authorized identity",),
            )
        expected = _binding_digest(self.identity, self.binding, self.capability)
        if not hmac.compare_digest(self.binding_digest, expected):
            raise AuthorizationDenied(
                code="ORG-AUTHORIZATION-BINDING-CORRUPT",
                reasons=("Authorization identity binding failed integrity verification",),
            )


class AuthorizationDenied(PermissionError):
    def __init__(self, *, code: str, reasons: tuple[str, ...]) -> None:
        self.code = code
        self.reasons = reasons
        super().__init__(f"{code}: {'; '.join(reasons)}")


INCOMPATIBLE_ACTIONS: dict[WorkflowAction, frozenset[WorkflowAction]] = {
    WorkflowAction.REQUIREMENTS_REVIEW: frozenset({WorkflowAction.REQUIREMENTS_AUTHOR}),
    WorkflowAction.APPROVE_REQUIREMENTS: frozenset({WorkflowAction.REQUIREMENTS_AUTHOR}),
    WorkflowAction.ARCHITECTURE_REVIEW: frozenset({WorkflowAction.ARCHITECTURE_AUTHOR}),
    WorkflowAction.APPROVE_ARCHITECTURE: frozenset({WorkflowAction.ARCHITECTURE_AUTHOR}),
    WorkflowAction.APPROVE_DECOMPOSITION: frozenset({WorkflowAction.DECOMPOSE}),
    WorkflowAction.PATCH_REVIEW: frozenset({WorkflowAction.EXECUTE}),
    WorkflowAction.APPROVE_INTEGRATION: frozenset(
        {WorkflowAction.PATCH_REVIEW, WorkflowAction.INTEGRATE}
    ),
}


class OrganizationalWorkflowGuard:
    def __init__(self, evaluator: AuthorityEvaluator, ledger: ParticipationLedger) -> None:
        self._evaluator = evaluator
        self._ledger = ledger

    def authorize_agent(
        self,
        *,
        identity: AgentRuntimeIdentity,
        binding: WorkflowBinding,
        now: datetime | None = None,
    ) -> AuthorizationGrant:
        if binding.action in HUMAN_ONLY_ACTIONS:
            raise AuthorizationDenied(
                code="ORG-HUMAN-AUTHORITY-REQUIRED",
                reasons=("This decision is reserved for a verified human principal",),
            )
        instant = now or datetime.now(UTC)
        decision = self._evaluator.evaluate(
            identity=identity,
            capability=binding.action.value,
            scope_type=binding.scope_type,
            scope_id=binding.scope_id,
            now=instant,
        )
        if not decision.allowed:
            raise AuthorizationDenied(code=decision.code, reasons=decision.reasons)
        self._enforce_separation_of_duties(identity=identity, binding=binding)
        return AuthorizationGrant(
            identity=identity,
            binding=binding,
            capability=binding.action.value,
            policy_versions=decision.policy_versions,
            issued_at=instant,
            binding_digest=_binding_digest(identity, binding, binding.action.value),
        )

    def record_completion(self, grant: AuthorizationGrant, actual: AgentRuntimeIdentity) -> None:
        grant.verify_runtime_identity(actual)
        self._ledger.append(
            Participation(
                identity=grant.identity,
                action=grant.binding.action,
                scope_type=grant.binding.scope_type,
                scope_id=grant.binding.scope_id,
                artifact_hash=grant.binding.artifact_hash,
                correlation_id=grant.binding.correlation_id,
                causation_id=grant.binding.causation_id,
                occurred_at=datetime.now(UTC),
            )
        )

    def _enforce_separation_of_duties(
        self, *, identity: AgentRuntimeIdentity, binding: WorkflowBinding
    ) -> None:
        prohibited = INCOMPATIBLE_ACTIONS.get(binding.action, frozenset())
        conflicts = tuple(
            record
            for record in self._ledger.for_scope(
                scope_type=binding.scope_type, scope_id=binding.scope_id
            )
            if record.identity.agent_profile_id == identity.agent_profile_id
            and record.action in prohibited
        )
        if conflicts:
            raise AuthorizationDenied(
                code="ORG-SEPARATION-OF-DUTIES-CONFLICT",
                reasons=tuple(
                    f"Actor already performed incompatible activity {item.action.value}"
                    for item in conflicts
                ),
            )


class RunningWorkDisposition(StrEnum):
    CANCEL = "cancel"
    CONTROLLED_TERMINATION = "controlled-termination"


@dataclass(frozen=True, slots=True)
class SuspensionPlan:
    profile_id: UUID
    reason: str
    policy_version: str
    revoke_unused_authorizations: bool
    recompose_queued_crews: bool
    running_work: RunningWorkDisposition
    artifact_approval_blocked: bool

    @classmethod
    def create(cls, *, profile_id: UUID, reason: str, high_risk: bool) -> SuspensionPlan:
        if not reason.strip():
            raise ValueError("Suspension reason is required")
        return cls(
            profile_id=profile_id,
            reason=reason,
            policy_version="agent-suspension-v1",
            revoke_unused_authorizations=True,
            recompose_queued_crews=True,
            running_work=(
                RunningWorkDisposition.CANCEL
                if high_risk
                else RunningWorkDisposition.CONTROLLED_TERMINATION
            ),
            artifact_approval_blocked=True,
        )


def _binding_digest(
    identity: AgentRuntimeIdentity, binding: WorkflowBinding, capability: str
) -> str:
    canonical = "|".join(
        (
            str(identity.agent_profile_id),
            str(identity.agent_profile_version_id),
            str(identity.assignment_id),
            str(identity.role_version_id),
            identity.configuration_hash,
            binding.workflow_type,
            capability,
            binding.scope_type,
            str(binding.scope_id),
            binding.artifact_hash or "",
            str(binding.correlation_id),
            str(binding.causation_id or ""),
        )
    )
    return sha256(canonical.encode()).hexdigest()
