from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from ai_enterprise.application.agent_runtime.skill_resolver import (
    SkillResolutionRequest,
    SkillResolver,
)
from ai_enterprise.application.agent_runtime.tool_authorization_service import (
    RuntimeToolManifest,
    ToolAuthorizationService,
)
from ai_enterprise.domain.agent_runtime.enums import (
    BindingStatus,
    RegistryStatus,
    ToolInvocationStatus,
    ToolSideEffect,
)
from ai_enterprise.domain.agent_runtime.errors import RegistryIntegrityError, ToolPolicyError
from ai_enterprise.domain.agent_runtime.skill import CapabilitySkillBinding, SkillVersion
from ai_enterprise.domain.agent_runtime.tool import ToolDefinition, ToolInvocationRequest
from ai_enterprise.domain.organization.authority import AuthorityDecision
from ai_enterprise.infrastructure.agent_runtime.tools.gateway import (
    GatewayInvocationContext,
    InMemoryInvocationStore,
    InMemoryToolRegistry,
    ToolGateway,
)


def skill(
    *,
    key: str = "patch-scope-review",
    version: int = 1,
    capabilities: tuple[str, ...] = ("patch.review",),
    permissions: tuple[str, ...] = ("repository.read",),
    risk: str = "low",
    priority: int = 100,
) -> SkillVersion:
    candidate = SkillVersion(
        id=uuid4(),
        skill_key=key,
        version_number=version,
        required_capabilities=capabilities,
        required_tool_permissions=permissions,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        procedure_document={
            "steps": [{"step_key": "inspect", "action": "read_context", "required": True}]
        },
        risk_level=risk,
        status=RegistryStatus.APPROVED,
        skill_hash="pending",
        policy_priority=priority,
    )
    return replace(candidate, skill_hash=candidate.calculated_hash())


def tool_definition() -> ToolDefinition:
    candidate = ToolDefinition(
        key="repository.file.read",
        version="1",
        description="Read a file from an approved repository snapshot.",
        required_capability="patch.review",
        required_permission="repository.read",
        input_schema={
            "type": "object",
            "required": ["project_id", "path"],
            "additionalProperties": False,
            "properties": {
                "project_id": {"type": "string"},
                "path": {"type": "string"},
            },
        },
        output_schema={
            "type": "object",
            "required": ["content"],
            "additionalProperties": False,
            "properties": {"content": {"type": "string"}},
        },
        side_effect_class=ToolSideEffect.READ_ONLY,
        risk_level="low",
        timeout_seconds=2,
        status=RegistryStatus.APPROVED,
        definition_hash="pending",
        argument_policy={
            "scope_id_argument": "project_id",
            "path_arguments": ["path"],
            "allowed_path_prefixes": ["src", "tests"],
            "forbidden_argument_keys": ["secret", "credential"],
            "maximum_input_bytes": 1024,
        },
    )
    return replace(candidate, definition_hash=candidate.calculated_hash())


class Sessions:
    def __init__(self, manifest: RuntimeToolManifest) -> None:
        self.manifest = manifest

    def get_active(self, session_id: UUID) -> RuntimeToolManifest | None:
        return self.manifest if session_id == self.manifest.id else None


class Authority:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.requests = []

    def evaluate(self, request):  # type annotation would duplicate the governed port
        self.requests.append(request)
        return AuthorityDecision(
            self.allowed,
            "AUTH-ALLOWED" if self.allowed else "AUTH-CAPABILITY-DENIED",
            (),
            ("org-v1",),
        )


@pytest.fixture
def governed_gateway():
    project_id = uuid4()
    profile_id = uuid4()
    profile_version_id = uuid4()
    assignment_id = uuid4()
    session_id = uuid4()
    definition = tool_definition()
    registry = InMemoryToolRegistry((definition,))
    manifest = RuntimeToolManifest(
        id=session_id,
        agent_profile_id=profile_id,
        agent_profile_version_id=profile_version_id,
        assignment_id=assignment_id,
        allowed_tools=frozenset({definition.key}),
        tool_permissions=frozenset({definition.required_permission}),
        status="active",
    )
    authority = Authority()
    authorization = ToolAuthorizationService(
        tool_registry=registry, sessions=Sessions(manifest), authority_service=authority
    )
    store = InMemoryInvocationStore()

    def handler(arguments, context):
        context.assert_gateway()
        return {"content": f"read:{arguments['path']}"}

    gateway = ToolGateway(
        registry=registry,
        authorization=authorization,
        invocation_store=store,
        handlers={(definition.key, definition.version): handler},
    )
    request = ToolInvocationRequest(
        runtime_session_id=session_id,
        agent_profile_version_id=profile_version_id,
        assignment_id=assignment_id,
        tool_key=definition.key,
        arguments={"project_id": str(project_id), "path": "src/service.py"},
        scope_type="project",
        scope_id=project_id,
    )
    return gateway, store, request, authority


def test_approved_skill_hash_is_immutable_and_procedure_is_structured() -> None:
    approved = skill()
    approved.assert_executable()
    with pytest.raises(RegistryIntegrityError, match="HASH-MISMATCH"):
        replace(approved, risk_level="critical").assert_executable()
    with pytest.raises(RegistryIntegrityError, match="PROCEDURE-INVALID"):
        invalid = replace(approved, procedure_document={})
        replace(invalid, skill_hash=invalid.calculated_hash()).assert_executable()


def test_skill_cannot_grant_missing_capability() -> None:
    candidate = skill(capabilities=("patch.review", "production.deploy"))
    decision = SkillResolver().resolve(
        request=SkillResolutionRequest(uuid4(), uuid4(), "patch.review", "review", uuid4()),
        bindings=(
            CapabilitySkillBinding(
                "patch.review", candidate.id, BindingStatus.ACTIVE, "skills-v1"
            ),
        ),
        skills=(candidate,),
        profile_skill_bundle=frozenset({candidate.id}),
        effective_capabilities=frozenset({"patch.review"}),
        tool_permissions=frozenset({"repository.read"}),
        maximum_risk_level="low",
    )
    assert decision.selected_skill_version_ids == ()
    assert decision.rejected_candidates[0]["code"] == "SKILL-REQUIRED-CAPABILITY-MISSING"


def test_skill_selection_is_deterministic_not_registration_order() -> None:
    older = skill(key="review", version=1)
    newer = skill(key="review", version=2)
    bindings = tuple(
        CapabilitySkillBinding("patch.review", item.id, BindingStatus.ACTIVE, "skills-v1")
        for item in (older, newer)
    )
    request = SkillResolutionRequest(uuid4(), uuid4(), "patch.review", "review", uuid4())
    kwargs = {
        "request": request,
        "profile_skill_bundle": frozenset({older.id, newer.id}),
        "effective_capabilities": frozenset({"patch.review"}),
        "tool_permissions": frozenset({"repository.read"}),
        "maximum_risk_level": "low",
    }
    first = SkillResolver().resolve(bindings=bindings, skills=(older, newer), **kwargs)
    second = SkillResolver().resolve(
        bindings=tuple(reversed(bindings)), skills=(newer, older), **kwargs
    )
    assert first == second
    assert first.selected_skill_version_ids == (newer.id, older.id)


def test_gateway_records_complete_success_lifecycle(governed_gateway) -> None:
    gateway, store, request, authority = governed_gateway
    result = gateway.invoke(request)
    record = store.records[result.invocation_id]
    assert result.status == ToolInvocationStatus.SUCCEEDED
    assert result.output == {"content": "read:src/service.py"}
    assert result.output_hash is not None
    assert record.input_hash
    assert record.authorization_decision["code"] == "TOOL-AUTHORIZED"
    assert record.started_at is not None and record.completed_at is not None
    assert authority.requests[0].scope_id == request.scope_id


def test_registered_but_unlisted_tool_is_denied(governed_gateway) -> None:
    gateway, _, request, _ = governed_gateway
    extra = replace(tool_definition(), key="repository.tree.read", definition_hash="pending")
    extra = replace(extra, definition_hash=extra.calculated_hash())
    gateway.registry.register(extra)
    result = gateway.invoke(replace(request, tool_key=extra.key))
    assert result.status == ToolInvocationStatus.DENIED
    assert result.error == {"code": "TOOL-NOT-IN-RUNTIME-MANIFEST"}


def test_authority_and_permission_are_both_required(governed_gateway) -> None:
    gateway, _, request, authority = governed_gateway
    authority.allowed = False
    denied = gateway.invoke(request)
    assert denied.error == {"code": "AUTH-CAPABILITY-DENIED"}
    authority.allowed = True
    sessions = gateway.authorization.sessions
    sessions.manifest = replace(sessions.manifest, tool_permissions=frozenset())
    denied = gateway.invoke(request)
    assert denied.error == {"code": "TOOL-PERMISSION-MISSING"}


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda request: replace(request, agent_profile_version_id=uuid4()), "IDENTITY-MISMATCH"),
        (lambda request: replace(request, assignment_id=uuid4()), "ASSIGNMENT-MISMATCH"),
        (lambda request: replace(request, tool_key="production.deploy"), "NOT-ACTIVE"),
        (
            lambda request: replace(
                request, arguments={**request.arguments, "project_id": str(uuid4())}
            ),
            "SCOPE-MISMATCH",
        ),
        (
            lambda request: replace(
                request, arguments={**request.arguments, "path": "src/../../.env"}
            ),
            "PATH-OUT-OF-SCOPE",
        ),
        (
            lambda request: replace(
                request, arguments={**request.arguments, "credential": "stolen"}
            ),
            "SCHEMA-ADDITIONAL",
        ),
    ],
)
def test_gateway_fails_closed_for_security_violations(
    governed_gateway, mutation, code: str
) -> None:
    gateway, store, request, _ = governed_gateway
    result = gateway.invoke(mutation(request))
    assert result.status == ToolInvocationStatus.DENIED
    assert code in result.error["code"]
    assert store.records[result.invocation_id].output_document is None


def test_tool_output_is_untrusted_and_schema_validated(governed_gateway) -> None:
    gateway, store, request, _ = governed_gateway
    definition = gateway.registry.get_active(request.tool_key)
    assert definition is not None
    gateway.handlers[(definition.key, definition.version)] = lambda _args, _context: {
        "content": "ok",
        "authority": "self-granted",
    }
    result = gateway.invoke(request)
    assert result.status == ToolInvocationStatus.FAILED
    assert result.output is None
    assert store.records[result.invocation_id].error_document == {
        "code": "TOOL-EXECUTION-FAILED",
        "type": "ValueError",
    }


def test_direct_tool_handler_context_is_rejected() -> None:
    forged = GatewayInvocationContext(uuid4(), uuid4(), object())
    with pytest.raises(ToolPolicyError, match="DIRECT-INFRASTRUCTURE"):
        forged.assert_gateway()


def test_tool_registry_rejects_corruption_and_mutation() -> None:
    definition = tool_definition()
    registry = InMemoryToolRegistry((definition,))
    with pytest.raises(RegistryIntegrityError, match="NOT-ACTIVE"):
        registry.register(replace(definition, definition_hash="0" * 64))
    changed = replace(definition, description="silently changed")
    changed = replace(changed, definition_hash=changed.calculated_hash())
    with pytest.raises(RegistryIntegrityError, match="IMMUTABLE"):
        registry.register(changed)


@pytest.mark.parametrize(
    "side_effect",
    ["authoritative_state_write", "human_approval_write", "production_external_effect"],
)
def test_agent_prohibited_side_effects_cannot_be_registered(side_effect: str) -> None:
    definition = replace(
        tool_definition(), side_effect_class=side_effect, definition_hash="pending"
    )
    definition = replace(definition, definition_hash=definition.calculated_hash())
    with pytest.raises(RegistryIntegrityError, match="NOT-ACTIVE"):
        InMemoryToolRegistry((definition,))
