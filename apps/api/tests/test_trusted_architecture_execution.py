import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from ai_enterprise.domain.architecture.renderer import render_architecture_markdown
from ai_enterprise.domain.architecture.schema import ArchitectureArtifactDocument
from ai_enterprise.domain.architecture.validation import ArchitectureValidationError
from ai_enterprise.infrastructure.architecture.contracts import (
    ArchitectureExecutionContext,
    AttemptEvidence,
)
from ai_enterprise.infrastructure.architecture.executor import TrustedArchitectureExecutor
from ai_enterprise.infrastructure.architecture.fake_provider import ScriptedArchitectureProvider
from ai_enterprise.infrastructure.architecture.parser import ArchitectureOutputParseError


class EvidenceWriter:
    def __init__(self) -> None:
        self.items: list[AttemptEvidence] = []

    async def record(self, evidence: AttemptEvidence) -> None:
        self.items.append(evidence)


def document_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "overview": "A governed service architecture.",
        "goals": ["Deliver REQ-001"],
        "constraints": ["No host mutation"],
        "functional_domains": [
            {
                "id": "DOM-CORE",
                "name": "Core",
                "responsibilities": ["Govern"],
                "requirement_ids": ["REQ-001"],
            }
        ],
        "modules": [
            {
                "id": "MOD-API",
                "name": "API",
                "domain_id": "DOM-CORE",
                "responsibilities": ["Serve"],
                "dependencies": [],
                "requirement_ids": ["REQ-001"],
            }
        ],
        "interfaces": [
            {
                "id": "API-MAIN",
                "name": "Main",
                "kind": "rest",
                "owner_module_id": "MOD-API",
                "consumers": [],
                "contract": "POST /runs",
                "requirement_ids": ["REQ-001"],
            }
        ],
        "data_entities": [
            {
                "id": "ENT-RUN",
                "name": "Run",
                "owner_module_id": "MOD-API",
                "persistence": "PostgreSQL",
                "transaction_boundary": "one run",
                "requirement_ids": ["REQ-001"],
            }
        ],
        "deployment": ["Container"],
        "security": ["Least privilege"],
        "reliability": ["Fenced leases"],
        "failure_scenarios": ["Worker crash"],
        "scaling": ["Horizontal workers"],
        "observability": ["Metrics"],
        "risks": [],
        "open_questions": [],
        "requirement_traceability": [
            {"requirement_id": "REQ-001", "design_element_ids": ["MOD-API", "API-MAIN"]}
        ],
    }


def context() -> ArchitectureExecutionContext:
    return ArchitectureExecutionContext(
        run_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        project_name="P",
        project_description="D",
        project_manifest_checksum="a" * 64,
        requirements_artifact_id=uuid.uuid4(),
        requirements_version=1,
        requirements_checksum="b" * 64,
        requirements_markdown="REQ-001: governed",
        approved_requirement_ids=frozenset({"REQ-001"}),
        schema_version="1.0",
        crew_version="architecture-crew-v1",
        deadline_at=datetime.now(UTC) + timedelta(seconds=10),
    )


@pytest.mark.asyncio
async def test_invalid_output_receives_exactly_one_bounded_repair() -> None:
    valid = json.dumps(document_payload(), separators=(",", ":"))
    provider = ScriptedArchitectureProvider(["not-json", valid, valid])
    evidence = EvidenceWriter()
    result = await TrustedArchitectureExecutor(provider=provider, evidence_writer=evidence).execute(
        context()
    )
    assert provider.operations == ["generate", "repair"]
    assert [item.status for item in evidence.items] == ["validation_failed", "succeeded"]
    assert result.invocation_count == 2
    assert result.markdown == render_architecture_markdown(result.document)


@pytest.mark.asyncio
async def test_second_invalid_output_fails_without_third_invocation() -> None:
    provider = ScriptedArchitectureProvider(["{}", "{}", json.dumps(document_payload())])
    evidence = EvidenceWriter()
    with pytest.raises(ArchitectureOutputParseError):
        await TrustedArchitectureExecutor(provider=provider, evidence_writer=evidence).execute(
            context()
        )
    assert provider.operations == ["generate", "repair"]
    assert [item.status for item in evidence.items] == ["validation_failed", "validation_failed"]


def test_schema_and_semantics_fail_closed() -> None:
    payload = document_payload()
    payload["unexpected"] = True
    with pytest.raises(ValidationError):
        ArchitectureArtifactDocument.model_validate(payload)
    document = ArchitectureArtifactDocument.model_validate(document_payload())
    from ai_enterprise.domain.architecture.validation import validate_architecture

    with pytest.raises(ArchitectureValidationError):
        validate_architecture(document, approved_requirement_ids=frozenset({"REQ-001", "REQ-002"}))
