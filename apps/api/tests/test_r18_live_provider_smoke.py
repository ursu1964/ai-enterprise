from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ai_enterprise.application.r15_manifest_compiler_runtime import r15_compile_manifest
from ai_enterprise.application.r16_knowledge_graph_runtime import r16_load_graph
from ai_enterprise.application.r17_execution_planner_runtime import r17_create_execution_plan
from ai_enterprise.application.r18_generator_orchestration_runtime import (
    BUILTIN_GENERATOR_REGISTRY,
    r18_orchestrate_execution,
)

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "schemas" / "Manifest.schema.json"
REGISTRY = ROOT / "registry"
VALID_MANIFEST = ROOT / "manifest" / "crm.r14.json"


pytestmark = pytest.mark.live_provider


def _enabled() -> bool:
    return os.environ.get("R18_RUN_LIVE_PROVIDER_TESTS") == "true"


def _plan_and_graph() -> tuple[dict[str, object], dict[str, object]]:
    compiled = r15_compile_manifest(
        json.loads(VALID_MANIFEST.read_text(encoding="utf-8")),
        SCHEMA,
        REGISTRY,
    )
    assert compiled.success_status is True
    assert compiled.knowledge_graph is not None
    graph = r16_load_graph(
        compiled.knowledge_graph.model_dump(mode="json"),
        compilation_report=compiled.compilation_report.model_dump(mode="json"),
        registry_root=REGISTRY,
    ).model_dump(mode="json")
    plan = r17_create_execution_plan(graph)
    payload = plan.model_dump(mode="json")
    payload["_test_approvals"] = {gate.approval_id: True for gate in plan.approval_gates}
    return payload, graph


@pytest.mark.skipif(
    not _enabled() or not os.environ.get("R18_OPENAI_API_KEY"),
    reason="Set R18_RUN_LIVE_PROVIDER_TESTS=true and R18_OPENAI_API_KEY to run.",
)
def test_r18_live_openai_provider_smoke() -> None:
    plan, graph = _plan_and_graph()
    approvals = plan.pop("_test_approvals")
    registry = [item.model_dump(mode="json") for item in BUILTIN_GENERATOR_REGISTRY]
    database = next(item for item in registry if item["generator_id"] == "generator.database")
    database["model_provider"] = "openai"
    database["model_version"] = os.environ.get("R18_OPENAI_MODEL", "gpt-5.1")

    result = r18_orchestrate_execution(
        plan,
        graph,
        generator_registry=registry,
        orchestration_options={
            "approvals": approvals,
            "enable_live_provider_calls": True,
            "provider_configs": {
                "openai": {
                    "api_key": os.environ["R18_OPENAI_API_KEY"],
                    "model_reference": database["model_version"],
                    "endpoint_reference": os.environ.get(
                        "R18_OPENAI_BASE_URL",
                        "https://api.openai.com/v1/responses",
                    ),
                    "timeout_seconds": int(os.environ.get("R18_PROVIDER_TIMEOUT_SECONDS", "120")),
                }
            },
        },
    )

    assert result.status == "completed"
    assert result.metrics["provider_call_count"] >= 1
    assert any(
        artifact.generated_content
        for record in result.task_records
        if record.generator_id == "generator.database"
        for artifact in record.artifacts
    )
