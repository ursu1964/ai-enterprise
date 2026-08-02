import uuid

import pytest

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.routes.agent_runtime import get_compiled_prompt
from ai_enterprise.application.agent_runtime_persistence_service import (
    AgentRuntimePersistenceService,
)
from ai_enterprise.infrastructure.agent_runtime.models import (
    PromptRegistryModel,
    PromptVersionModel,
)


class ScalarResult:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def all(self) -> list[object]:
        return self.rows


class RuntimeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.scalar_values: list[object | None] = []
        self.gets: dict[object, object] = {}
        self.commits = 0

    def add(self, row: object) -> None:
        self.added.append(row)

    def add_all(self, rows: object) -> None:
        self.added.extend(list(rows))

    async def scalar(self, statement: object) -> object | None:
        return self.scalar_values.pop(0) if self.scalar_values else None

    async def get(self, model: type, identity: object) -> object | None:
        return self.gets.get((model, identity))

    async def scalars(self, statement: object) -> ScalarResult:
        return ScalarResult([])

    async def commit(self) -> None:
        self.commits += 1


def admin() -> Actor:
    return Actor(
        subject="platform-admin",
        actor_type="human",
        role="platform-admin",
        capabilities=frozenset({"runtime.admin"}),
        scopes=frozenset({"global"}),
    )


def runtime_reader(organization_id: uuid.UUID) -> Actor:
    return Actor(
        subject="runtime-reader",
        actor_type="human",
        role="operator",
        capabilities=frozenset({"runtime.read"}),
        scopes=frozenset({f"organization:{organization_id}"}),
    )


@pytest.mark.asyncio
async def test_prompt_registry_supports_version_approval_and_rollback() -> None:
    organization_id = uuid.uuid4()
    session = RuntimeSession()
    service = AgentRuntimePersistenceService(session)  # type: ignore[arg-type]

    prompt = await service.create_prompt(
        {
            "organization_id": organization_id,
            "prompt_key": "architecture.review",
            "name": "Architecture Review",
            "owner": "Architecture Office",
            "department": "Engineering",
            "applicable_crew": "architecture",
        },
        admin(),
    )
    session.scalar_values.append(0)
    first = await service.create_prompt_version(
        prompt,
        {
            "prompt_layers": {
                "system": "Follow enterprise policy.",
                "task": "Review the architecture.",
            },
            "output_schema": {"type": "object"},
            "policy_document": {"requires_citations": True},
        },
        admin(),
    )
    session.gets[(PromptRegistryModel, prompt.id)] = prompt
    approved = await service.approve_prompt_version(first, admin())

    session.scalar_values.append(1)
    second = await service.create_prompt_version(
        prompt,
        {
            "prompt_layers": {"system": "Follow policy v2.", "task": "Review with risks."},
            "output_schema": {"type": "object"},
            "policy_document": {"requires_citations": True},
        },
        admin(),
    )
    second.approval_status = "approved"
    await service.rollback_prompt(prompt, approved, admin())

    assert prompt.status == "active"
    assert prompt.current_version_id == approved.id
    assert first.version_number == 1
    assert second.version_number == 2
    assert first.prompt_hash != second.prompt_hash
    assert session.commits == 5


@pytest.mark.asyncio
async def test_compiled_prompt_returns_ordered_manifest() -> None:
    prompt_id = uuid.uuid4()
    version_id = uuid.uuid4()
    prompt = PromptRegistryModel(
        id=prompt_id,
        organization_id=uuid.uuid4(),
        prompt_key="requirements.discovery",
        name="Requirements Discovery",
        owner="Product Office",
        department="Product",
        applicable_crew="requirements",
        status="active",
        current_version_id=version_id,
    )
    version = PromptVersionModel(
        id=version_id,
        prompt_id=prompt_id,
        version_number=1,
        prompt_layers={"system": "Respect policy.", "task": "Find missing facts."},
        output_schema={"type": "object"},
        policy_document={"tool_limits": []},
        prompt_hash="1" * 64,
        approval_status="approved",
    )
    session = RuntimeSession()
    session.gets[(PromptRegistryModel, prompt_id)] = prompt
    session.gets[(PromptVersionModel, version_id)] = version

    response = await get_compiled_prompt(
        prompt_id,
        session,  # type: ignore[arg-type]
        runtime_reader(prompt.organization_id),
    )

    assert response.prompt_key == "requirements.discovery"
    assert response.version_id == version_id
    assert response.compiled_layers[0]["name"] == "system"
    assert response.output_schema == {"type": "object"}
