from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ai_enterprise.application.r12_bootstrap_runtime import (
    r12_bootstrap_plan,
    r12_build_manifest_contract,
    r12_compute_deterministic_fingerprint,
    r12_delivery_architecture_contract,
    r12_deterministic_fingerprint_contract,
    r12_error_contract,
    r12_implementation_status,
    r12_operational_baseline_contract,
    r12_platform_entity_catalog,
    r12_repository_layout,
    r12_roadmap_governance_contract,
    r12_shared_contract_catalog,
    r12_validate_build_manifest,
    r12_validate_delivery_architecture,
    r12_validate_error_contract,
    r12_validate_identity_contract,
    r12_validate_operational_baseline,
    r12_validate_roadmap_governance,
    r12_validate_shared_contract,
    r12_validate_verification_strategy,
    r12_verification_strategy_contract,
)
from ai_enterprise.main import app

ROOT = Path(__file__).resolve().parents[3]


def test_r12_reports_progressive_implementation_phase_status() -> None:
    report = r12_implementation_status(ROOT)

    assert report.phase_count == 8
    assert report.vertical_slice_ready is True
    assert report.phases[0].name == "Engineering Foundation"
    assert report.phases[4].name == "Artifact Generation"
    assert all(phase.required_signals for phase in report.phases)
    assert report.status_hash


def test_r12_repository_layout_tracks_bootstrap_structure() -> None:
    report = r12_repository_layout(ROOT)
    paths = {item.path: item for item in report.items}

    assert report.item_count >= 8
    assert paths["apps/api"].present is True
    assert paths["specifications"].present is True
    assert paths["tools"].present is True
    assert report.layout_hash


def test_r12_bootstrap_plan_is_ordered_and_api_driven() -> None:
    plan = r12_bootstrap_plan()

    assert plan.commands[0].command == "make server-readiness-template"
    assert any("alembic upgrade head" in command.command for command in plan.commands)
    assert any("pytest" in command.command for command in plan.commands)
    assert [command.step for command in plan.commands] == list(
        range(1, plan.command_count + 1)
    )
    assert plan.plan_hash


def test_r12_build_manifest_contract_covers_reproducibility_fields() -> None:
    contract = r12_build_manifest_contract()
    fields = {item.field for item in contract.requirements}

    assert {
        "build_id",
        "manifest_version",
        "registry_version",
        "generator_versions",
        "template_versions",
        "policy_versions",
        "checksums",
        "lineage_references",
    }.issubset(fields)
    assert all(item.required for item in contract.requirements)
    assert contract.contract_hash


def test_r12_build_manifest_validation_accepts_reproducible_manifest() -> None:
    manifest = _valid_build_manifest()

    report = r12_validate_build_manifest(manifest)

    assert report.valid is True
    assert report.finding_count == 0
    assert len(report.manifest_fingerprint) == 64
    assert report.required_contract_hash == r12_build_manifest_contract().contract_hash


def test_r12_build_manifest_validation_rejects_missing_lineage_and_bad_checksum() -> None:
    manifest = _valid_build_manifest() | {
        "checksums": {"../escape.txt": "not-a-sha"},
        "lineage_references": {},
    }

    report = r12_validate_build_manifest(manifest)
    details = {finding.detail for finding in report.findings}

    assert report.valid is False
    assert any("safe relative path" in detail for detail in details)
    assert any("lowercase sha256" in detail for detail in details)
    assert any("artifact lacks lineage reference" in detail for detail in details)


def test_r12_error_contract_covers_standard_service_error_fields() -> None:
    contract = r12_error_contract()
    fields = {item.field for item in contract.fields}

    assert {
        "error_code",
        "category",
        "severity",
        "message",
        "technical_detail",
        "correlation_id",
        "affected_object",
        "retry_guidance",
        "user_action",
        "documentation_reference",
    }.issubset(fields)
    assert all(item.required for item in contract.fields)
    assert contract.contract_hash


def test_r12_error_contract_validation_accepts_sanitized_error() -> None:
    report = r12_validate_error_contract(_valid_service_error())

    assert report.valid is True
    assert report.finding_count == 0
    assert len(report.error_fingerprint) == 64
    assert report.required_contract_hash == r12_error_contract().contract_hash


def test_r12_error_contract_validation_rejects_leaks_and_bad_semantics() -> None:
    error = _valid_service_error() | {
        "error_code": "bad code",
        "severity": "fatal",
        "technical_detail": 'Traceback File "/home/app/service.py" token=secret',
    }
    del error["user_action"]

    report = r12_validate_error_contract(error)
    details = {finding.detail for finding in report.findings}

    assert report.valid is False
    assert "required error contract field is missing" in details
    assert any("uppercase and stable" in detail for detail in details)
    assert any("severity must be one of" in detail for detail in details)
    assert any("internal or sensitive detail" in detail for detail in details)


def test_r12_shared_contract_catalog_covers_command_event_and_query() -> None:
    catalog = r12_shared_contract_catalog()
    contracts = {item.contract_type: item for item in catalog.contracts}

    assert {"command", "event", "query"} == set(contracts)
    assert {"command_id", "expected_version", "authorization_context"}.issubset(
        {item.field for item in contracts["command"].fields}
    )
    assert {"event_id", "causation_id", "immutable"}.issubset(
        {item.field for item in contracts["event"].fields}
    )
    assert {"query_id", "parameters", "authorization_context"}.issubset(
        {item.field for item in contracts["query"].fields}
    )
    assert catalog.catalog_hash


def test_r12_shared_contract_validation_accepts_valid_command_event_and_query() -> None:
    assert r12_validate_shared_contract("command", _valid_command_envelope()).valid is True
    assert r12_validate_shared_contract("event", _valid_event_envelope()).valid is True
    assert r12_validate_shared_contract("query", _valid_query_envelope()).valid is True


def test_r12_shared_contract_validation_rejects_invalid_envelopes() -> None:
    command_report = r12_validate_shared_contract(
        "command",
        _valid_command_envelope() | {"expected_version": -1, "authorization_context": {}},
    )
    event_report = r12_validate_shared_contract(
        "event",
        _valid_event_envelope() | {"immutable": False},
    )
    query_report = r12_validate_shared_contract(
        "query",
        _valid_query_envelope() | {"payload": {"mutate": True}},
    )

    assert command_report.valid is False
    assert any("non-negative integer" in finding.detail for finding in command_report.findings)
    assert any("non-empty object" in finding.detail for finding in command_report.findings)
    assert event_report.valid is False
    assert any("immutable=true" in finding.detail for finding in event_report.findings)
    assert query_report.valid is False
    assert any(
        "must not carry mutation payloads" in finding.detail
        for finding in query_report.findings
    )


def test_r12_platform_entity_catalog_covers_minimum_entity_model() -> None:
    catalog = r12_platform_entity_catalog()
    entities = {item.entity_type: item for item in catalog.entities}

    assert {
        "Tenant",
        "Workspace",
        "Project",
        "Manifest",
        "ManifestVersion",
        "KnowledgeNode",
        "TransformationRun",
        "ArtifactVersion",
        "Build",
        "GovernanceDecision",
        "AIInteraction",
        "IntegrationDefinition",
        "Deployment",
        "RuntimeService",
        "AuditRecord",
    }.issubset(entities)
    assert entities["Manifest"].versioned is True
    assert entities["AuditRecord"].scope == "tenant/workspace/project"
    assert catalog.catalog_hash


def test_r12_identity_contract_accepts_versioned_entity_identity() -> None:
    report = r12_validate_identity_contract(_valid_manifest_identity())

    assert report.valid is True
    assert report.finding_count == 0
    assert len(report.entity_fingerprint) == 64


def test_r12_identity_contract_rejects_semantic_internal_id_and_bad_key() -> None:
    report = r12_validate_identity_contract(
        _valid_manifest_identity()
        | {
            "internal_id": "MANIFEST.CRM",
            "canonical_key": "MANIFEST.CRM",
            "version": "",
        }
    )
    details = {finding.detail for finding in report.findings}

    assert report.valid is False
    assert "field must be a non-empty string" in details
    assert any("non-semantic and distinct" in detail for detail in details)


def test_r12_deterministic_fingerprint_contract_covers_required_inputs() -> None:
    contract = r12_deterministic_fingerprint_contract()

    assert contract.required_inputs == (
        "manifest_version",
        "registry_version",
        "transformation_engine_version",
        "generator_version",
        "template_version",
        "policy_version",
        "configuration_profile",
        "target_stack",
        "generation_options",
    )
    assert contract.contract_hash


def test_r12_deterministic_fingerprint_is_stable_and_rejects_missing_inputs() -> None:
    inputs = _valid_determinism_inputs()

    first = r12_compute_deterministic_fingerprint(inputs)
    second = r12_compute_deterministic_fingerprint(dict(reversed(inputs.items())))
    invalid = r12_compute_deterministic_fingerprint(
        {
            key: value
            for key, value in inputs.items()
            if key != "template_version"
        }
    )

    assert first.valid is True
    assert first.deterministic_fingerprint == second.deterministic_fingerprint
    assert invalid.valid is False
    assert any("required deterministic" in finding.detail for finding in invalid.findings)


def test_r12_operational_baseline_contract_covers_security_observability_and_dod() -> None:
    contract = r12_operational_baseline_contract()
    sections = {item.section: item for item in contract.sections}

    assert {
        "security_controls",
        "secret_hygiene",
        "audit_actions",
        "observability_signals",
        "request_context_fields",
        "health_endpoints",
        "core_metrics",
        "definition_of_done",
    } == set(sections)
    assert "tenant_workspace_isolation" in sections["security_controls"].required_items
    assert "sensitive_internal_information_protected" in sections["health_endpoints"].required_items
    assert "audit_behavior_verified" in sections["definition_of_done"].required_items
    assert contract.contract_hash


def test_r12_operational_baseline_validation_accepts_complete_evidence() -> None:
    report = r12_validate_operational_baseline(_valid_operational_evidence())

    assert report.valid is True
    assert report.finding_count == 0
    assert len(report.evidence_fingerprint) == 64
    assert report.contract_hash == r12_operational_baseline_contract().contract_hash


def test_r12_operational_baseline_validation_rejects_missing_items_and_secret_values() -> None:
    evidence = _valid_operational_evidence()
    evidence["security_controls"] = ["authenticated_access"]
    evidence["secret_hygiene"] = {
        "secret_manager_references_only": {"secret": "plain-value"}
    }

    report = r12_validate_operational_baseline(evidence)

    assert report.valid is False
    assert any(
        "required operational baseline item is missing" in item.detail
        for item in report.findings
    )
    assert any("must not embed secret values" in item.detail for item in report.findings)


def test_r12_verification_strategy_contract_covers_testing_golden_and_performance() -> None:
    contract = r12_verification_strategy_contract()
    sections = {item.section: item for item in contract.sections}

    assert {
        "test_levels",
        "unit_test_obligations",
        "contract_test_obligations",
        "mvp_e2e_sequence",
        "determinism_obligations",
        "golden_projects",
        "security_tests",
        "ai_safety_tests",
        "performance_targets",
    } == set(sections)
    assert "end_to_end" in sections["test_levels"].required_items
    assert "download_project" == sections["mvp_e2e_sequence"].required_items[-1]
    assert "minimal_contact_manager" in sections["golden_projects"].required_items
    assert contract.contract_hash


def test_r12_verification_strategy_validation_accepts_complete_evidence() -> None:
    report = r12_validate_verification_strategy(_valid_verification_evidence())

    assert report.valid is True
    assert report.finding_count == 0
    assert len(report.evidence_fingerprint) == 64
    assert report.contract_hash == r12_verification_strategy_contract().contract_hash


def test_r12_verification_strategy_validation_rejects_missing_items_and_bad_e2e_order() -> None:
    evidence = _valid_verification_evidence()
    evidence["security_tests"] = ["static_analysis"]
    evidence["mvp_e2e_sequence"] = list(reversed(evidence["mvp_e2e_sequence"]))  # type: ignore[arg-type]

    report = r12_validate_verification_strategy(evidence)

    assert report.valid is False
    assert any(
        "required verification strategy item is missing" in item.detail
        for item in report.findings
    )
    assert any("required order" in item.detail for item in report.findings)


def test_r12_roadmap_governance_contract_covers_release_pilot_and_self_hosting() -> None:
    contract = r12_roadmap_governance_contract()
    sections = {item.section: item for item in contract.sections}

    assert {
        "release_types",
        "pilot_constraints",
        "feedback_categories",
        "self_hosting_targets",
        "bootstrap_sequence",
        "bootstrap_boundary",
        "self_hosting_migration_stages",
        "mvp_success_scope",
        "mvp_exclusions",
    } == set(sections)
    assert "production_release" in sections["release_types"].required_items
    assert "manifest_language_issue" in sections["feedback_categories"].required_items
    assert sections["bootstrap_sequence"].required_items[0] == "handwritten_bootstrap_kernel"
    assert "fully_autonomous_software_development" in sections["mvp_exclusions"].required_items
    assert contract.contract_hash


def test_r12_roadmap_governance_validation_accepts_complete_evidence() -> None:
    report = r12_validate_roadmap_governance(_valid_roadmap_governance_evidence())

    assert report.valid is True
    assert report.finding_count == 0
    assert len(report.evidence_fingerprint) == 64
    assert report.contract_hash == r12_roadmap_governance_contract().contract_hash


def test_r12_roadmap_governance_validation_rejects_missing_release_limits_and_bad_order() -> None:
    evidence = _valid_roadmap_governance_evidence()
    release_types = evidence["release_types"]
    assert isinstance(release_types, dict)
    release_types["production_release"] = {"supported_capabilities": ["reference-stack"]}
    evidence["bootstrap_sequence"] = list(reversed(evidence["bootstrap_sequence"]))  # type: ignore[arg-type]
    evidence["mvp_exclusions"] = ["large_marketplace"]

    report = r12_validate_roadmap_governance(evidence)

    assert report.valid is False
    assert any("supported_capabilities and limitations" in item.detail for item in report.findings)
    assert any("bootstrap sequence" in item.detail for item in report.findings)
    assert any(
        "required roadmap governance item is missing" in item.detail
        for item in report.findings
    )


def test_r12_delivery_architecture_contract_covers_remaining_delivery_sections() -> None:
    contract = r12_delivery_architecture_contract()
    sections = {item.section: item for item in contract.sections}

    assert {
        "local_environment",
        "environment_model",
        "environment_controls",
        "configuration_precedence",
        "deployment_architecture",
        "modular_boundary",
        "initial_topology",
        "production_deployment",
        "migration_strategy",
        "backup_recovery",
        "artifact_storage",
        "cli_operations",
        "generator_sdk",
        "plugin_sdk",
        "registry_bootstrap",
        "registry_governance",
        "template_bootstrap",
        "reference_project",
        "delivery_milestones",
        "team_roles",
        "ownership_categories",
        "non_functional_requirements",
        "risk_controls",
    } == set(sections)
    assert "object_storage_emulator" in sections["local_environment"].required_items
    assert "destructive_changes_governed" in sections["migration_strategy"].required_items
    assert "api_backed" in sections["cli_operations"].required_items
    assert "customer" in sections["reference_project"].required_items
    assert contract.contract_hash


def test_r12_delivery_architecture_validation_accepts_complete_evidence() -> None:
    report = r12_validate_delivery_architecture(_valid_delivery_architecture_evidence())

    assert report.valid is True
    assert report.finding_count == 0
    assert len(report.evidence_fingerprint) == 64
    assert report.contract_hash == r12_delivery_architecture_contract().contract_hash


def test_r12_delivery_architecture_validation_rejects_bad_order_and_unowned_components() -> None:
    evidence = _valid_delivery_architecture_evidence()
    evidence["configuration_precedence"] = list(reversed(evidence["configuration_precedence"]))  # type: ignore[arg-type]
    ownership = evidence["ownership_categories"]
    assert isinstance(ownership, dict)
    ownership["security_ownership"] = {"proof": "missing owner"}
    evidence["generator_sdk"] = ["generator_interface"]

    report = r12_validate_delivery_architecture(evidence)

    assert report.valid is False
    assert any("configuration precedence" in item.detail for item in report.findings)
    assert any("must name an owner" in item.detail for item in report.findings)
    assert any(
        "required delivery architecture item is missing" in item.detail
        for item in report.findings
    )


def test_r12_bootstrap_routes_are_exposed_in_openapi() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "/api/v1/r12/implementation-status" in paths
    assert "/api/v1/r12/repository-layout" in paths
    assert "/api/v1/r12/bootstrap-plan" in paths
    assert "/api/v1/r12/build-manifest-contract" in paths
    assert "/api/v1/r12/build-manifest/validate" in paths
    assert "/api/v1/r12/error-contract" in paths
    assert "/api/v1/r12/error-contract/validate" in paths
    assert "/api/v1/r12/shared-contracts" in paths
    assert "/api/v1/r12/shared-contracts/validate" in paths
    assert "/api/v1/r12/platform-entities" in paths
    assert "/api/v1/r12/identity-contract/validate" in paths
    assert "/api/v1/r12/deterministic-fingerprint-contract" in paths
    assert "/api/v1/r12/deterministic-fingerprint" in paths
    assert "/api/v1/r12/operational-baseline-contract" in paths
    assert "/api/v1/r12/operational-baseline/validate" in paths
    assert "/api/v1/r12/verification-strategy-contract" in paths
    assert "/api/v1/r12/verification-strategy/validate" in paths
    assert "/api/v1/r12/roadmap-governance-contract" in paths
    assert "/api/v1/r12/roadmap-governance/validate" in paths
    assert "/api/v1/r12/delivery-architecture-contract" in paths
    assert "/api/v1/r12/delivery-architecture/validate" in paths
    assert paths["/api/v1/r12/implementation-status"]["get"]["tags"] == [
        "r12-bootstrap"
    ]


def _valid_build_manifest() -> dict[str, object]:
    return {
        "build_id": "build:crm:0001",
        "generation_timestamp": "2026-08-05T00:00:00Z",
        "project_id": "project:crm",
        "manifest_version": "1.0.0",
        "registry_version": "1.0.0",
        "generator_versions": {"uagf.core": "1.0.0"},
        "template_versions": {"backend.service": "1.0.0"},
        "policy_versions": {"generation": "1.0.0"},
        "target_stack": "python-fastapi-postgres",
        "generated_artifacts": ["backend/app.py"],
        "checksums": {"backend/app.py": "a" * 64},
        "warnings": [],
        "test_results": {"status": "passed"},
        "validation_results": {"status": "valid"},
        "lineage_references": {"backend/app.py": ["ENTITY.CUSTOMER"]},
    }


def _valid_service_error() -> dict[str, object]:
    return {
        "error_code": "AEP_VALIDATION_FAILED",
        "category": "validation",
        "severity": "error",
        "message": "The submitted manifest did not pass validation.",
        "technical_detail": "Schema rule entity.name.required failed.",
        "correlation_id": "trace-20260805-0001",
        "affected_object": {"type": "manifest", "id": "manifest:crm"},
        "retry_guidance": "Retry after correcting the manifest.",
        "user_action": "Open validation findings and update the missing entity name.",
        "documentation_reference": "docs/errors/aep-validation-failed",
    }


def _valid_command_envelope() -> dict[str, object]:
    return {
        "command_id": "cmd-00000001",
        "command_type": "GenerateArtifacts",
        "requesting_actor": {"actor_id": "user:operator", "role": "release-manager"},
        "tenant": "tenant:acme",
        "workspace": "workspace:engineering",
        "project": "project:crm",
        "correlation_id": "corr-00000001",
        "causation_id": "evt-00000000",
        "timestamp": "2026-08-05T00:00:00Z",
        "expected_version": 7,
        "authorization_context": {"policy_set": "policy:release", "decision": "allow"},
        "payload": {"target_stack": "python-fastapi-postgres"},
    }


def _valid_event_envelope() -> dict[str, object]:
    return {
        "event_id": "evt-00000001",
        "event_type": "ArtifactGenerated",
        "tenant": "tenant:acme",
        "workspace": "workspace:engineering",
        "project": "project:crm",
        "correlation_id": "corr-00000001",
        "causation_id": "cmd-00000001",
        "occurred_at": "2026-08-05T00:01:00Z",
        "immutable": True,
        "payload": {"artifact_id": "artifact:backend-service"},
    }


def _valid_query_envelope() -> dict[str, object]:
    return {
        "query_id": "qry-00000001",
        "query_type": "GetBuildStatus",
        "requesting_actor": {"actor_id": "user:operator", "role": "release-manager"},
        "tenant": "tenant:acme",
        "workspace": "workspace:engineering",
        "project": "project:crm",
        "correlation_id": "corr-00000002",
        "timestamp": "2026-08-05T00:02:00Z",
        "authorization_context": {"policy_set": "policy:read", "decision": "allow"},
        "parameters": {"build_id": "build:crm:0001"},
    }


def _valid_manifest_identity() -> dict[str, object]:
    return {
        "entity_type": "Manifest",
        "internal_id": "01J4Q6TX4KWR9X5Y7F2P8N3MAB",
        "canonical_key": "MANIFEST.CRM",
        "tenant": "tenant:acme",
        "workspace": "workspace:engineering",
        "project": "project:crm",
        "version": "1.0.0",
    }


def _valid_determinism_inputs() -> dict[str, object]:
    return {
        "manifest_version": "1.0.0",
        "registry_version": "1.0.0",
        "transformation_engine_version": "1.0.0",
        "generator_version": "uagf.core:1.0.0",
        "template_version": "backend.service:1.0.0",
        "policy_version": "generation:1.0.0",
        "configuration_profile": "default",
        "target_stack": "python-fastapi-postgres",
        "generation_options": {"include_tests": True, "include_openapi": True},
    }


def _valid_operational_evidence() -> dict[str, object]:
    contract = r12_operational_baseline_contract()
    return {
        section.section: {
            item: {"proof": f"docs/proof/{section.section}/{item}"}
            for item in section.required_items
        }
        for section in contract.sections
    }


def _valid_verification_evidence() -> dict[str, object]:
    contract = r12_verification_strategy_contract()
    evidence: dict[str, object] = {}
    for section in contract.sections:
        if section.section == "mvp_e2e_sequence":
            evidence[section.section] = list(section.required_items)
        else:
            evidence[section.section] = {
                item: {"proof": f"artifacts/verification/{section.section}/{item}.json"}
                for item in section.required_items
            }
    return evidence


def _valid_roadmap_governance_evidence() -> dict[str, object]:
    contract = r12_roadmap_governance_contract()
    evidence: dict[str, object] = {}
    for section in contract.sections:
        if section.section in {"bootstrap_sequence", "self_hosting_migration_stages"}:
            evidence[section.section] = list(section.required_items)
        elif section.section == "release_types":
            evidence[section.section] = {
                item: {
                    "supported_capabilities": [f"{item}:capability"],
                    "limitations": [f"{item}:limitation"],
                }
                for item in section.required_items
            }
        else:
            evidence[section.section] = {
                item: {"proof": f"docs/roadmap/{section.section}/{item}.md"}
                for item in section.required_items
            }
    return evidence


def _valid_delivery_architecture_evidence() -> dict[str, object]:
    contract = r12_delivery_architecture_contract()
    ordered_sections = {
        "configuration_precedence",
        "deployment_architecture",
        "registry_governance",
        "delivery_milestones",
    }
    evidence: dict[str, object] = {}
    for section in contract.sections:
        if section.section in ordered_sections:
            evidence[section.section] = list(section.required_items)
        elif section.section == "ownership_categories":
            evidence[section.section] = {
                item: {
                    "owner": f"{item}:owner",
                    "proof": f"docs/owners/{item}.md",
                }
                for item in section.required_items
            }
        else:
            evidence[section.section] = {
                item: {"proof": f"docs/delivery/{section.section}/{item}.md"}
                for item in section.required_items
            }
    return evidence
