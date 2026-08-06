from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ai_enterprise.application.r13_repository_bootstrap_runtime import (
    r13_bootstrap_pipeline_contract,
    r13_bootstrap_sequence_contract,
    r13_component_boundary_contract,
    r13_directory_content_contract,
    r13_executable_skeleton_report,
    r13_repository_layout,
    r13_repository_layout_contract,
    r13_repository_mission_contract,
    r13_repository_principles_contract,
    r13_validate_bootstrap_sequence,
)
from ai_enterprise.main import app

ROOT = Path(__file__).resolve().parents[3]


def test_r13_repository_layout_contract_covers_bootstrap_root_responsibilities() -> None:
    contract = r13_repository_layout_contract()
    paths = {item.path: item for item in contract.directories}

    assert contract.readme_sentence == (
        "This repository converts an AI-Enterprise Manifest into a complete software system."
    )
    assert {
        "manifest",
        "registry",
        "schemas",
        "compiler",
        "planner",
        "runtime",
        "generators",
        "validators",
        "knowledge",
        "workspace",
        "templates",
        "examples",
        "tests",
        "logs",
        "docs",
        "config",
    }.issubset(paths)
    assert paths["workspace"].authoritative is False
    assert paths["registry"].authoritative is True
    assert contract.contract_hash


def test_r13_repository_layout_reports_present_and_missing_items() -> None:
    report = r13_repository_layout(ROOT)
    paths = {item.path: item for item in report.items}

    assert report.item_count == r13_repository_layout_contract().directory_count
    assert paths["README.md"].present is True
    assert paths["manifest"].present is True
    assert paths["registry"].present is True
    assert paths["compiler"].present is True
    assert paths["runtime"].present is True
    assert paths["docs"].present is True
    assert report.readme_sentence_present is True
    assert report.missing_count == 0
    assert report.present_count + report.missing_count == report.item_count
    assert report.layout_hash


def test_r13_bootstrap_sequence_contract_is_ordered_and_guaranteed() -> None:
    contract = r13_bootstrap_sequence_contract()

    assert [item.name for item in contract.steps] == [
        "load_manifest",
        "validate_manifest",
        "load_registry",
        "validate_registry",
        "build_knowledge_graph",
        "resolve_dependencies",
        "build_execution_graph",
        "create_plan",
        "execute_generators",
        "validate_output",
        "produce_project",
    ]
    assert "no_hidden_conversational_context" in contract.guarantees
    assert contract.contract_hash


def test_r13_repository_mission_contract_sets_manifest_to_system_boundary() -> None:
    contract = r13_repository_mission_contract()

    assert contract.input_artifact == "Manifest.json"
    assert contract.output_artifact == "Entire Software System"
    assert "Everything between Manifest.json" in contract.ownership_boundary
    assert len(contract.contract_hash) == 64


def test_r13_bootstrap_pipeline_contract_matches_compiler_flow() -> None:
    contract = r13_bootstrap_pipeline_contract()

    assert [stage.name for stage in contract.stages] == [
        "manifest",
        "validation",
        "registry_expansion",
        "dependency_resolution",
        "knowledge_graph",
        "execution_plan",
        "generators",
    ]
    assert contract.stages[0].consumes == "Manifest.json"
    assert contract.stages[-1].produces == "Generated software system"
    assert "No generation bypasses the compiler pipeline" in contract.invariant
    assert len(contract.contract_hash) == 64


def test_r13_bootstrap_sequence_validation_accepts_contract_sequence() -> None:
    contract = r13_bootstrap_sequence_contract()
    report = r13_validate_bootstrap_sequence(
        {
            "steps": [item.name for item in contract.steps],
            "guarantees": list(contract.guarantees),
            "uses_conversation_memory": False,
        }
    )

    assert report.valid is True
    assert report.finding_count == 0
    assert len(report.sequence_fingerprint) == 64
    assert report.contract_hash == contract.contract_hash


def test_r13_bootstrap_sequence_validation_rejects_bypass_and_memory_dependency() -> None:
    contract = r13_bootstrap_sequence_contract()
    report = r13_validate_bootstrap_sequence(
        {
            "steps": list(reversed([item.name for item in contract.steps])),
            "guarantees": ["manifest_only_project_specific_input"],
            "uses_conversation_memory": True,
        }
    )
    details = {item.detail for item in report.findings}

    assert report.valid is False
    assert "bootstrap steps must exactly follow the R13 required order" in details
    assert any("required bootstrap guarantee is missing" in detail for detail in details)
    assert "R13 bootstrap must not rely on hidden conversational context" in details


def test_r13_component_boundary_contract_covers_generation_components() -> None:
    contract = r13_component_boundary_contract()
    components = {item.name: item for item in contract.components}

    assert contract.component_count == 10
    assert {
        "manifest_engine",
        "registry",
        "validator",
        "compiler",
        "planner",
        "knowledge_graph",
        "ai_runtime",
        "generator",
        "synchronizer",
        "runtime_workspace",
    } == set(components)
    assert components["compiler"].exclusive is True
    assert "Nothing outside these components" in contract.invariant
    assert len(contract.contract_hash) == 64


def test_r13_directory_content_contract_blocks_mixed_responsibilities() -> None:
    contract = r13_directory_content_contract()
    rules = {item.path: item for item in contract.rules}

    assert contract.rule_count >= 15
    assert "historical manifests" in rules["manifest"].allowed_content
    assert "registered object definitions" in rules["manifest"].forbidden_content
    assert "hidden conversational memory" in rules["runtime"].forbidden_content
    assert "business logic" in rules["templates"].forbidden_content
    assert "customer data" in rules["config"].forbidden_content
    assert rules["workspace"].authoritative is False
    assert len(contract.contract_hash) == 64


def test_r13_repository_principles_contract_covers_non_negotiables() -> None:
    contract = r13_repository_principles_contract()
    principles = {item.name: item.guarantee for item in contract.principles}

    assert contract.principle_count == 6
    assert principles["Single Source of Intent"] == (
        "the Manifest defines what the client wants"
    )
    assert principles["Stateless Generation"] == (
        "generators never depend on prior chat history"
    )
    assert "Manifest and Registry" in principles["Complete Traceability"]
    assert len(contract.contract_hash) == 64


def test_r13_executable_skeleton_report_is_complete_for_repository_root() -> None:
    report = r13_executable_skeleton_report(ROOT)

    assert report.valid is True
    assert report.layout_missing_count == 0
    assert report.internal_home_missing_count == 0
    assert report.internal_home_count >= 70
    assert report.missing_internal_homes == ()
    assert report.readme_sentence_present is True
    assert report.component_count == 10
    assert report.directory_rule_count >= 15
    assert report.principle_count == 6
    assert report.bootstrap_step_count == 11
    assert {
        "mission",
        "layout",
        "components",
        "directory_content",
        "principles",
        "bootstrap_sequence",
        "bootstrap_pipeline",
    } == set(report.contract_hashes)
    assert len(report.report_hash) == 64


def test_r13_physical_skeleton_contains_named_internal_homes() -> None:
    required_paths = {
        "manifest/customer.json",
        "manifest/hospital.json",
        "manifest/crm.json",
        "manifest/erp.json",
        "schemas/Manifest.schema.json",
        "schemas/Entity.schema.json",
        "schemas/Workflow.schema.json",
        "schemas/API.schema.json",
        "schemas/Component.schema.json",
        "schemas/Role.schema.json",
        "generators/API",
        "generators/Database",
        "generators/Frontend",
        "generators/Backend",
        "generators/Workflow",
        "generators/Tests",
        "generators/Docker",
        "generators/CI-CD",
        "generators/Infrastructure",
        "generators/Documentation",
        "validators/Manifest",
        "validators/Registry",
        "validators/Naming",
        "validators/Dependencies",
        "validators/CircularReferences",
        "validators/MissingObjects",
        "validators/VersionCompatibility",
        "validators/PolicyConflicts",
        "templates/React",
        "templates/Angular",
        "templates/Vue",
        "templates/Spring",
        "templates/DotNet",
        "templates/Node",
        "templates/Laravel",
        "templates/Flutter",
        "templates/Python",
        "templates/Go",
        "tests/Registry",
        "tests/Manifest",
        "tests/Compiler",
        "tests/Planner",
        "tests/Generator",
        "tests/Validator",
        "config/ai-provider",
        "config/execution-limits",
        "config/generator-options",
        "config/template-selection",
        "config/environment",
        "config/feature-flags",
    }

    assert all((ROOT / path).exists() for path in required_paths)


def test_r13_routes_are_exposed_in_openapi() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "/api/v1/r13/repository-layout-contract" in paths
    assert "/api/v1/r13/repository-layout" in paths
    assert "/api/v1/r13/repository-mission-contract" in paths
    assert "/api/v1/r13/bootstrap-sequence-contract" in paths
    assert "/api/v1/r13/bootstrap-pipeline-contract" in paths
    assert "/api/v1/r13/bootstrap-sequence/validate" in paths
    assert "/api/v1/r13/component-boundary-contract" in paths
    assert "/api/v1/r13/directory-content-contract" in paths
    assert "/api/v1/r13/repository-principles-contract" in paths
    assert "/api/v1/r13/executable-skeleton" in paths
    assert paths["/api/v1/r13/repository-layout-contract"]["get"]["tags"] == [
        "r13-repository-bootstrap"
    ]
