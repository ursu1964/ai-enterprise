import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.organization_persistence_service import canonical_hash
from ai_enterprise.infrastructure.agent_runtime.models import SkillModel, SkillVersionModel

INITIAL_SKILLS: tuple[tuple[str, str, str], ...] = (
    ("requirements-analysis-v1", "Requirements analysis", "requirements.analyze"),
    ("requirements-review-v1", "Requirements review", "requirements.review"),
    ("architecture-analysis-v1", "Architecture analysis", "architecture.analyze"),
    ("interface-design-v1", "Interface design", "architecture.interface.design"),
    ("threat-analysis-v1", "Threat analysis", "security.threat.analyze"),
    ("failure-analysis-v1", "Failure analysis", "resilience.failure.analyze"),
    ("work-package-decomposition-v1", "Work-package decomposition", "work.decompose"),
    ("python-implementation-v1", "Python implementation", "implementation.python"),
    ("test-evidence-analysis-v1", "Test evidence analysis", "test.evidence.analyze"),
    ("patch-review-v1", "Patch review", "patch.review"),
)

KNOWLEDGE_SKILLS: tuple[tuple[str, str, str], ...] = (
    ("knowledge-extraction-v1", "Governed knowledge extraction", "extract-knowledge-candidates"),
)


def initial_skill_document(key: str, capability: str) -> dict[str, object]:
    return {
        "skill_key": key,
        "required_capabilities": [capability],
        "required_tool_permissions": [],
        "input_schema": {"type": "object", "additionalProperties": False},
        "output_schema": {"type": "object"},
        "risk_level": "bounded",
        "failure_behavior": "abstain_and_escalate",
        "procedure": {
            "steps": [
                {"step_key": "inspect-inputs", "action": "read_context", "required": True},
                {"step_key": "produce-output", "action": "structured_output", "required": True},
            ]
        },
    }


async def seed_initial_skills(session: AsyncSession, organization_id: uuid.UUID) -> int:
    """Idempotently install approved baseline procedures for an organization."""
    inserted = 0
    for key, name, capability in INITIAL_SKILLS + KNOWLEDGE_SKILLS:
        existing = await session.scalar(
            select(SkillModel).where(
                SkillModel.organization_id == organization_id,
                SkillModel.skill_key == key,
            )
        )
        if existing is not None:
            continue
        document = initial_skill_document(key, capability)
        skill_id, version_id = uuid.uuid4(), uuid.uuid4()
        session.add_all(
            (
                SkillModel(
                    id=skill_id,
                    organization_id=organization_id,
                    skill_key=key,
                    name=name,
                    status="active",
                    current_version_id=version_id,
                ),
                SkillVersionModel(
                    id=version_id,
                    skill_id=skill_id,
                    version_number=1,
                    skill_document=document,
                    skill_hash=canonical_hash(document),
                    approval_status="approved",
                ),
            )
        )
        inserted += 1
    await session.flush()
    return inserted
