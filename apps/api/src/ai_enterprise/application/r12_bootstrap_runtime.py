from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from ai_enterprise.domain.specification.kernel import specification_hash

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ERROR_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_:-]{2,120}$")
_CANONICAL_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:[._:-][A-Z0-9]+){1,12}$")


class R12PhaseStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    phase: int
    name: str
    required_signals: tuple[str, ...]
    present_signals: tuple[str, ...]
    missing_signals: tuple[str, ...]
    operational: bool


class R12ImplementationStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    phase_count: int
    operational_phase_count: int
    next_phase: str | None
    vertical_slice_ready: bool
    phases: tuple[R12PhaseStatus, ...]
    status_hash: str


class R12RepositoryLayoutItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    purpose: str
    present: bool


class R12RepositoryLayoutReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    item_count: int
    present_count: int
    missing_count: int
    items: tuple[R12RepositoryLayoutItem, ...]
    layout_hash: str


class R12BootstrapCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    step: int
    command: str
    purpose: str
    mutates_state: bool


class R12BootstrapPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    command_count: int
    commands: tuple[R12BootstrapCommand, ...]
    plan_hash: str


class R12BuildManifestRequirement(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: str
    purpose: str
    required: bool


class R12BuildManifestContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    requirement_count: int
    requirements: tuple[R12BuildManifestRequirement, ...]
    contract_hash: str


class R12BuildManifestFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: str
    severity: str
    detail: str


class R12BuildManifestValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    finding_count: int
    findings: tuple[R12BuildManifestFinding, ...]
    required_contract_hash: str
    manifest_fingerprint: str
    report_hash: str


class R12ErrorContractField(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: str
    purpose: str
    required: bool


class R12ErrorContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    field_count: int
    fields: tuple[R12ErrorContractField, ...]
    contract_hash: str


class R12ErrorContractFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: str
    severity: str
    detail: str


class R12ErrorContractValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    finding_count: int
    findings: tuple[R12ErrorContractFinding, ...]
    required_contract_hash: str
    error_fingerprint: str
    report_hash: str


class R12SharedContractField(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: str
    purpose: str
    required: bool


class R12SharedContractDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_type: str
    category: str
    fields: tuple[R12SharedContractField, ...]
    contract_hash: str


class R12SharedContractCatalog(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_count: int
    contracts: tuple[R12SharedContractDefinition, ...]
    catalog_hash: str


class R12SharedContractFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: str
    severity: str
    detail: str


class R12SharedContractValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    contract_type: str
    finding_count: int
    findings: tuple[R12SharedContractFinding, ...]
    required_contract_hash: str
    envelope_fingerprint: str
    report_hash: str


class R12PlatformEntityDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_type: str
    scope: str
    versioned: bool
    canonical_key_required: bool


class R12PlatformEntityCatalog(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_count: int
    versioned_entity_count: int
    entities: tuple[R12PlatformEntityDefinition, ...]
    catalog_hash: str


class R12IdentityContractFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: str
    severity: str
    detail: str


class R12IdentityContractValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    finding_count: int
    findings: tuple[R12IdentityContractFinding, ...]
    entity_fingerprint: str
    report_hash: str


class R12DeterministicFingerprintContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    required_input_count: int
    required_inputs: tuple[str, ...]
    contract_hash: str


class R12DeterministicFingerprintReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    finding_count: int
    findings: tuple[R12IdentityContractFinding, ...]
    deterministic_fingerprint: str
    contract_hash: str
    report_hash: str


class R12OperationalBaselineSection(BaseModel):
    model_config = ConfigDict(frozen=True)

    section: str
    required_items: tuple[str, ...]
    purpose: str


class R12OperationalBaselineContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    section_count: int
    sections: tuple[R12OperationalBaselineSection, ...]
    contract_hash: str


class R12OperationalBaselineFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    section: str
    item: str
    severity: str
    detail: str


class R12OperationalBaselineValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    finding_count: int
    findings: tuple[R12OperationalBaselineFinding, ...]
    evidence_fingerprint: str
    contract_hash: str
    report_hash: str


class R12VerificationStrategySection(BaseModel):
    model_config = ConfigDict(frozen=True)

    section: str
    required_items: tuple[str, ...]
    purpose: str


class R12VerificationStrategyContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    section_count: int
    sections: tuple[R12VerificationStrategySection, ...]
    contract_hash: str


class R12VerificationStrategyFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    section: str
    item: str
    severity: str
    detail: str


class R12VerificationStrategyValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    finding_count: int
    findings: tuple[R12VerificationStrategyFinding, ...]
    evidence_fingerprint: str
    contract_hash: str
    report_hash: str


class R12RoadmapGovernanceSection(BaseModel):
    model_config = ConfigDict(frozen=True)

    section: str
    required_items: tuple[str, ...]
    purpose: str


class R12RoadmapGovernanceContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    section_count: int
    sections: tuple[R12RoadmapGovernanceSection, ...]
    contract_hash: str


class R12RoadmapGovernanceFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    section: str
    item: str
    severity: str
    detail: str


class R12RoadmapGovernanceValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    finding_count: int
    findings: tuple[R12RoadmapGovernanceFinding, ...]
    evidence_fingerprint: str
    contract_hash: str
    report_hash: str


class R12DeliveryArchitectureSection(BaseModel):
    model_config = ConfigDict(frozen=True)

    section: str
    required_items: tuple[str, ...]
    purpose: str


class R12DeliveryArchitectureContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    section_count: int
    sections: tuple[R12DeliveryArchitectureSection, ...]
    contract_hash: str


class R12DeliveryArchitectureFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    section: str
    item: str
    severity: str
    detail: str


class R12DeliveryArchitectureValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    finding_count: int
    findings: tuple[R12DeliveryArchitectureFinding, ...]
    evidence_fingerprint: str
    contract_hash: str
    report_hash: str


_PHASE_SIGNALS: tuple[tuple[int, str, tuple[str, ...]], ...] = (
    (
        0,
        "Engineering Foundation",
        (
            "apps/api/pyproject.toml",
            "docker-compose.yml",
            "Makefile",
            "docs/reference-architecture",
            "apps/api/tests",
        ),
    ),
    (
        1,
        "Universal Manifest and UPDL",
        (
            "specifications/AEPM-0.1.schema.json",
            "apps/api/src/ai_enterprise/domain/aepm.py",
            "apps/api/src/ai_enterprise/domain/aepm_validation.py",
            "apps/api/tests/test_aepm_manifest.py",
        ),
    ),
    (
        2,
        "Knowledge Graph and Registry",
        (
            "knowledge/graph.json",
            "apps/api/src/ai_enterprise/infrastructure/knowledge",
            "apps/api/src/ai_enterprise/api/routes/knowledge.py",
        ),
    ),
    (
        3,
        "Transformation Engine",
        (
            "apps/api/src/ai_enterprise/domain/r5_umte.py",
            "apps/api/src/ai_enterprise/api/routes/r5_umte.py",
            "apps/api/tests/test_r5_umte_domain.py",
        ),
    ),
    (
        4,
        "Artifact Generation",
        (
            "apps/api/src/ai_enterprise/domain/r6_uagf.py",
            "apps/api/src/ai_enterprise/api/routes/r6_uagf.py",
            "apps/api/tests/test_r6_uagf_domain.py",
        ),
    ),
    (
        5,
        "Manifest Studio and Project Workspace",
        (
            "apps/api/src/ai_enterprise/domain/r10_ueif.py",
            "apps/api/src/ai_enterprise/api/routes/r10_ueif.py",
            "apps/web/index.html",
        ),
    ),
    (
        6,
        "Governance, Runtime and Integrations",
        (
            "apps/api/src/ai_enterprise/domain/r7_uerm.py",
            "apps/api/src/ai_enterprise/domain/r8_ugeif.py",
            "apps/api/src/ai_enterprise/domain/r11_uief.py",
        ),
    ),
    (
        7,
        "Enterprise Platform and Ecosystem",
        (
            "apps/api/src/ai_enterprise/domain/r9_uak.py",
            "apps/api/src/ai_enterprise/application/r9_uak_runtime.py",
            "deploy/kubernetes",
            "tools/production_readiness.py",
        ),
    ),
)


_REPOSITORY_ITEMS: tuple[tuple[str, str], ...] = (
    ("apps/api", "Platform API and modular backend application"),
    ("apps/web", "Initial browser experience/runtime shell"),
    ("specifications", "Versioned platform and generated-project contracts"),
    ("docs/reference-architecture", "Documented platform boundaries and roadmap"),
    ("migrations/versions", "Database migration history"),
    ("tools", "Bootstrap, verification, release, and operations tools"),
    ("deploy/kubernetes", "Managed deployment manifests"),
    ("docker", "Container and observability configuration"),
    ("examples", "Reference manifests and validation examples"),
    ("knowledge/graph.json", "Repository knowledge graph artifact"),
)


_BOOTSTRAP_COMMANDS: tuple[tuple[str, str, bool], ...] = (
    ("make server-readiness-template", "Validate checked-in server deployment template", False),
    ("cd apps/api && uv sync", "Install backend dependencies from lockfile", True),
    (
        "cd apps/api && uv run alembic upgrade head",
        "Apply versioned database migrations",
        True,
    ),
    (
        "cd apps/api && uv run python -m ai_enterprise.bootstrap --runtime-root runtime-data",
        "Create local runtime directories, development secrets, and seed authority",
        True,
    ),
    ("cd apps/api && uv run ruff check src tests", "Run deterministic lint gate", False),
    (
        "cd apps/api && PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider -q",
        "Run backend verification suite",
        False,
    ),
    ("graphify update .", "Refresh code knowledge graph after implementation changes", True),
)


_BUILD_MANIFEST_FIELDS: tuple[tuple[str, str], ...] = (
    ("build_id", "Permanent identifier for the generated build"),
    ("generation_timestamp", "Time the package was generated"),
    ("project_id", "Source project identifier"),
    ("manifest_version", "Approved Manifest version used as input"),
    ("registry_version", "Registry version used during transformation"),
    ("generator_versions", "Generator pack versions used for every output"),
    ("template_versions", "Template pack versions used for every output"),
    ("policy_versions", "Policy versions used for governance and generation"),
    ("target_stack", "Reference technology stack/profile"),
    ("generated_artifacts", "Generated files and logical artifacts"),
    ("checksums", "Content hashes for reproducibility"),
    ("warnings", "Non-blocking generation warnings"),
    ("test_results", "Verification results associated with the package"),
    ("validation_results", "Manifest/transformation validation results"),
    ("lineage_references", "Links from artifacts back to source Manifest objects"),
)


_ERROR_CONTRACT_FIELDS: tuple[tuple[str, str], ...] = (
    ("error_code", "Stable machine-readable error identifier"),
    ("category", "Operational category for routing, analytics, and support"),
    ("severity", "Impact level: info, warning, error, or critical"),
    ("message", "Safe user-facing summary"),
    ("technical_detail", "Sanitized diagnostic detail for authorized clients"),
    ("correlation_id", "Request, trace, or workflow correlation identifier"),
    ("affected_object", "Object, aggregate, artifact, or endpoint affected by the error"),
    ("retry_guidance", "Whether and how the client or worker should retry"),
    ("user_action", "Concrete action available to the user or operator"),
    ("documentation_reference", "Reference to durable product or operational documentation"),
)

_ERROR_REQUIRED_STRING_FIELDS = frozenset(
    {
        "error_code",
        "category",
        "severity",
        "message",
        "correlation_id",
        "retry_guidance",
        "user_action",
        "documentation_reference",
    }
)

_ERROR_SEVERITIES = frozenset({"info", "warning", "error", "critical"})
_DOCUMENTATION_PREFIXES = ("docs/", "https://", "urn:", "R")
_SENSITIVE_ERROR_MARKERS = (
    "Traceback",
    'File "',
    "Stack trace",
    "Exception at",
    "password=",
    "token=",
    "secret=",
    "/home/",
    "site-packages",
)

_SHARED_CONTRACTS: dict[str, tuple[str, tuple[tuple[str, str], ...]]] = {
    "command": (
        "Commands request state changes and must carry authorization and concurrency context",
        (
            ("command_id", "Permanent identifier for the command request"),
            ("command_type", "Machine-readable command name"),
            ("requesting_actor", "Actor requesting the state change"),
            ("tenant", "Tenant isolation boundary"),
            ("workspace", "Workspace isolation boundary"),
            ("project", "Project affected by the command"),
            ("correlation_id", "Trace identifier shared by related operations"),
            ("causation_id", "Identifier of the command or event that caused this command"),
            ("timestamp", "Time the command was issued"),
            ("expected_version", "Optimistic concurrency version expected by the caller"),
            ("authorization_context", "Policy and permission context used for authorization"),
            ("payload", "Command-specific state-change document"),
        ),
    ),
    "event": (
        "Events record immutable completed platform facts",
        (
            ("event_id", "Permanent identifier for the published event"),
            ("event_type", "Machine-readable event name"),
            ("tenant", "Tenant isolation boundary"),
            ("workspace", "Workspace isolation boundary"),
            ("project", "Project affected by the event"),
            ("correlation_id", "Trace identifier shared by related operations"),
            ("causation_id", "Command or event identifier that caused this fact"),
            ("occurred_at", "Time the fact occurred"),
            ("immutable", "Marker proving the event is append-only"),
            ("payload", "Event-specific fact document"),
        ),
    ),
    "query": (
        "Queries retrieve platform state without mutation",
        (
            ("query_id", "Permanent identifier for the query request"),
            ("query_type", "Machine-readable query name"),
            ("requesting_actor", "Actor requesting platform state"),
            ("tenant", "Tenant isolation boundary"),
            ("workspace", "Workspace isolation boundary"),
            ("project", "Project being queried"),
            ("correlation_id", "Trace identifier shared by related operations"),
            ("timestamp", "Time the query was issued"),
            ("authorization_context", "Policy and permission context used for authorization"),
            ("parameters", "Query-specific filter and pagination document"),
        ),
    ),
}

_SHARED_CONTRACT_REQUIRED_OBJECT_FIELDS = frozenset(
    {"authorization_context", "parameters", "payload", "requesting_actor"}
)
_SHARED_CONTRACT_REQUIRED_STRING_FIELDS = frozenset(
    {
        "causation_id",
        "command_id",
        "command_type",
        "correlation_id",
        "event_id",
        "event_type",
        "occurred_at",
        "project",
        "query_id",
        "query_type",
        "tenant",
        "timestamp",
        "workspace",
    }
)

_PLATFORM_ENTITIES: tuple[tuple[str, str, bool, bool], ...] = (
    ("Tenant", "tenant", False, True),
    ("Workspace", "tenant/workspace", False, True),
    ("Portfolio", "tenant/workspace", False, True),
    ("Project", "tenant/workspace/project", False, True),
    ("Manifest", "tenant/workspace/project", True, True),
    ("ManifestVersion", "tenant/workspace/project", True, True),
    ("ManifestObject", "tenant/workspace/project", True, True),
    ("RegistryEntry", "platform", True, True),
    ("RegistryVersion", "platform", True, True),
    ("KnowledgeNode", "tenant/workspace/project", True, True),
    ("KnowledgeEdge", "tenant/workspace/project", True, True),
    ("TransformationRun", "tenant/workspace/project", True, False),
    ("TransformationObject", "tenant/workspace/project", True, True),
    ("Generator", "platform", True, True),
    ("Template", "platform", True, True),
    ("Artifact", "tenant/workspace/project", True, True),
    ("ArtifactVersion", "tenant/workspace/project", True, True),
    ("Build", "tenant/workspace/project", True, False),
    ("Policy", "tenant/workspace", True, True),
    ("GovernanceDecision", "tenant/workspace/project", False, False),
    ("Approval", "tenant/workspace/project", False, False),
    ("AIInteraction", "tenant/workspace/project", False, False),
    ("IntegrationDefinition", "tenant/workspace", True, True),
    ("Deployment", "tenant/workspace/project/environment", True, True),
    ("RuntimeService", "tenant/workspace/project/environment", True, True),
    ("AuditRecord", "tenant/workspace/project", False, False),
)

_DETERMINISTIC_FINGERPRINT_INPUTS: tuple[str, ...] = (
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

_OPERATIONAL_BASELINE_SECTIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "security_controls",
        "Minimum controls that may not be postponed until enterprise scale",
        (
            "authenticated_access",
            "tenant_workspace_isolation",
            "role_based_authorization",
            "policy_based_sensitive_operation_checks",
            "encrypted_transport",
            "encrypted_secrets",
            "secure_identity_handling",
            "audit_logging",
            "input_validation",
            "dependency_scanning",
            "container_scanning",
            "rate_limiting",
            "secure_default_configuration",
        ),
    ),
    (
        "secret_hygiene",
        "Secret values are never persisted or emitted where references are required",
        (
            "secret_manager_references_only",
            "manifest_secret_values_forbidden",
            "logs_secret_values_forbidden",
            "ai_prompts_secret_values_forbidden",
            "generated_packages_secret_values_forbidden",
            "error_messages_secret_values_forbidden",
        ),
    ),
    (
        "audit_actions",
        "Sensitive actions must produce immutable audit evidence",
        (
            "authentication",
            "manifest_creation",
            "manifest_modification",
            "approval",
            "generation",
            "artifact_download",
            "policy_modification",
            "registry_modification",
            "ai_interaction",
            "integration_activation",
            "deployment_registration",
        ),
    ),
    (
        "observability_signals",
        "Every service emits operational signals needed by operators",
        (
            "structured_logs",
            "metrics",
            "distributed_traces",
            "health_status",
            "dependency_status",
        ),
    ),
    (
        "request_context_fields",
        "Every request carries traceability and isolation context",
        (
            "request_id",
            "correlation_id",
            "causation_id",
            "tenant_id",
            "actor_identity",
            "operation_name",
        ),
    ),
    (
        "health_endpoints",
        "Every service exposes safe operational health surfaces",
        (
            "liveness",
            "readiness",
            "dependency_health",
            "version_information",
            "build_information",
            "sensitive_internal_information_protected",
        ),
    ),
    (
        "core_metrics",
        "Initial platform metrics required by R12",
        (
            "manifest_validation_duration",
            "validation_failure_count",
            "graph_build_duration",
            "transformation_duration",
            "artifact_generation_duration",
            "generator_failure_count",
            "ai_request_count",
            "ai_validation_rejection_count",
            "approval_duration",
            "build_success_rate",
            "artifact_download_count",
            "active_projects",
            "queue_depth",
        ),
    ),
    (
        "definition_of_done",
        "Capability completion requires more than code presence",
        (
            "implementation_exists",
            "tests_pass",
            "contracts_versioned",
            "observability_exists",
            "security_review_complete",
            "documentation_exists",
            "operations_defined",
            "failure_behavior_tested",
            "audit_behavior_verified",
            "acceptance_criteria_met",
        ),
    ),
)

_VERIFICATION_STRATEGY_SECTIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "test_levels",
        "R12 requires layered verification across implementation risk levels",
        (
            "unit",
            "component",
            "contract",
            "integration",
            "end_to_end",
            "security",
            "performance",
            "determinism",
        ),
    ),
    (
        "unit_test_obligations",
        "Unit tests must prove core rule and contract behavior",
        (
            "registry_rules",
            "validators",
            "transformation_rules",
            "graph_queries",
            "generator_logic",
            "policy_decisions",
            "identifier_handling",
            "version_behavior",
        ),
    ),
    (
        "contract_test_obligations",
        "Service contracts cannot change silently",
        (
            "request_shape",
            "response_shape",
            "error_behavior",
            "event_schema",
            "version_compatibility",
            "required_metadata",
        ),
    ),
    (
        "mvp_e2e_sequence",
        "Critical Manifest-to-project sequence that must run automatically in CI",
        (
            "create_project",
            "submit_manifest",
            "validate_manifest",
            "approve_manifest",
            "build_knowledge_graph",
            "transform_project",
            "generate_artifacts",
            "verify_build",
            "download_project",
        ),
    ),
    (
        "determinism_obligations",
        "Repeated generation with identical inputs must remain stable",
        (
            "identical_transformation_model",
            "identical_artifact_inventory",
            "identical_checksums_excluding_classified_timestamps",
            "identical_traceability",
            "identical_dependency_graph",
            "nondeterministic_fields_classified",
        ),
    ),
    (
        "golden_projects",
        "Reference manifests provide regression evidence",
        (
            "minimal_contact_manager",
            "customer_relationship_system",
            "basic_commerce_system",
            "employee_leave_workflow",
            "document_approval_system",
        ),
    ),
    (
        "security_tests",
        "Security verification must cover static and runtime abuse paths",
        (
            "static_analysis",
            "dependency_vulnerability_scanning",
            "container_scanning",
            "secret_scanning",
            "authorization_tests",
            "tenant_isolation_tests",
            "injection_tests",
            "api_abuse_tests",
            "ai_prompt_boundary_tests",
        ),
    ),
    (
        "ai_safety_tests",
        "AI integration must remain controlled and auditable",
        (
            "context_isolation",
            "tenant_isolation",
            "prohibited_action_rejection",
            "structured_output_compliance",
            "unsupported_assumption_detection",
            "secret_exclusion",
            "malicious_prompt_resistance",
            "manifest_authority_enforcement",
            "audit_completeness",
        ),
    ),
    (
        "performance_targets",
        "Initial measurable MVP performance targets",
        (
            "manifest_validation_under_two_seconds",
            "knowledge_graph_construction_under_five_seconds",
            "transformation_under_ten_seconds",
            "first_artifact_generation_under_sixty_seconds",
            "api_p95_under_five_hundred_milliseconds",
            "no_cross_tenant_data_exposure",
            "golden_project_determinism_rate_one_hundred_percent",
        ),
    ),
)

_ROADMAP_GOVERNANCE_SECTIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "release_types",
        "Controlled releases must declare capabilities and limitations",
        (
            "internal_development_release",
            "technical_preview",
            "private_pilot",
            "controlled_beta",
            "production_release",
            "enterprise_release",
        ),
    ),
    (
        "pilot_constraints",
        "The first pilot must validate the Manifest-to-project pipeline in a bounded context",
        (
            "clear_business_entities",
            "one_or_two_workflows",
            "avoid_extreme_regulatory_complexity",
            "standard_crud_and_approvals",
            "small_integration_boundary",
            "stakeholders_available_for_feedback",
        ),
    ),
    (
        "feedback_categories",
        "Pilot feedback must update the correct platform source layer",
        (
            "manifest_language_issue",
            "registry_issue",
            "transformation_issue",
            "generation_issue",
            "user_experience_issue",
            "governance_issue",
            "implementation_defect",
            "missing_capability",
            "documentation_issue",
        ),
    ),
    (
        "self_hosting_targets",
        "Initial platform self-description targets",
        (
            "registry_definitions",
            "platform_entity_model",
            "platform_workflows",
            "api_contracts",
            "approval_processes",
            "project_lifecycle",
            "user_roles",
            "audit_requirements",
        ),
    ),
    (
        "bootstrap_sequence",
        "The bootstrap paradox is controlled by a minimal handwritten-to-generated sequence",
        (
            "handwritten_bootstrap_kernel",
            "initial_registry",
            "initial_manifest_engine",
            "initial_transformation_engine",
            "initial_generators",
            "generated_platform_modules",
            "progressive_self_hosting",
        ),
    ),
    (
        "bootstrap_boundary",
        "The handwritten bootstrap layer must remain minimal",
        (
            "kernel_orchestration",
            "manifest_parser",
            "registry_loader",
            "basic_validation",
            "transformation_rule_executor",
            "generator_host_interface",
            "artifact_storage",
            "security_foundation",
            "audit_foundation",
        ),
    ),
    (
        "self_hosting_migration_stages",
        "Self-hosting is introduced incrementally without destabilizing operations",
        (
            "stage_1_handwritten_core",
            "stage_2_generated_contracts_and_models",
            "stage_3_generated_apis_and_documentation",
            "stage_4_generated_administration_interfaces",
            "stage_5_manifest_driven_platform_evolution",
        ),
    ),
    (
        "mvp_success_scope",
        "The first operational release remains focused on the core vertical slice",
        (
            "create_workspace_and_project",
            "upload_or_author_manifest",
            "validate_manifest",
            "review_validation_errors",
            "approve_valid_manifest_version",
            "generate_knowledge_graph",
            "inspect_dependencies_and_lineage",
            "run_deterministic_transformation",
            "generate_reference_stack_project",
            "view_generated_artifacts",
            "download_project_package",
            "regenerate_after_manifest_change",
            "see_changed_artifacts",
            "preserve_custom_extension_boundaries",
            "audit_every_platform_action",
        ),
    ),
    (
        "mvp_exclusions",
        "Explicit exclusions prevent uncontrolled scope expansion before the first release",
        (
            "many_programming_language_targets",
            "full_multi_cloud_deployment",
            "autonomous_production_deployment",
            "large_marketplace",
            "advanced_portfolio_management",
            "broad_industry_compliance_packs",
            "sophisticated_predictive_intelligence",
            "real_time_collaborative_editing",
            "unlimited_plugin_execution",
            "generalized_low_code_application_building",
            "fully_autonomous_software_development",
        ),
    ),
)

_DELIVERY_ARCHITECTURE_SECTIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "local_environment",
        "One-command local startup must include all developer dependencies",
        (
            "databases",
            "object_storage_emulator",
            "message_broker",
            "development_identity",
            "required_services",
            "frontend",
            "observability_tools",
            "example_manifest",
        ),
    ),
    (
        "environment_model",
        "Every environment needs isolated configuration and operational history",
        ("local", "development", "testing", "staging", "production"),
    ),
    (
        "environment_controls",
        "Each environment must define isolated operational controls",
        (
            "explicit_configuration",
            "isolated_secrets",
            "independent_databases",
            "independent_object_storage",
            "independent_queues",
            "deployment_history",
            "access_policy",
        ),
    ),
    (
        "configuration_precedence",
        "Overrides must be validated and auditable",
        (
            "platform_defaults",
            "environment_configuration",
            "tenant_policy",
            "workspace_configuration",
            "project_configuration",
            "runtime_overrides",
        ),
    ),
    (
        "deployment_architecture",
        "MVP deployment uses modular monolith plus asynchronous workers",
        (
            "web_application",
            "platform_api",
            "core_modular_application",
            "worker_processes",
            "database_object_storage_and_broker",
        ),
    ),
    (
        "modular_boundary",
        "Single deployment units must preserve extractable service boundaries",
        ("public_module_interfaces", "commands", "events", "read_models"),
    ),
    (
        "initial_topology",
        "First topology includes the required runtime infrastructure",
        (
            "load_balancer",
            "web_frontend",
            "platform_api",
            "core_application",
            "background_workers",
            "postgresql",
            "object_storage",
            "message_broker",
            "cache",
            "identity_provider",
            "observability_stack",
        ),
    ),
    (
        "production_deployment",
        "Production deployment must support safe change and recovery",
        (
            "rolling_updates",
            "database_migrations",
            "health_checks",
            "zero_downtime_where_feasible",
            "rollback",
            "secrets_rotation",
            "backup",
            "disaster_recovery",
            "environment_promotion",
            "deployment_audit",
        ),
    ),
    (
        "migration_strategy",
        "Schema changes require controlled migration metadata",
        (
            "identifier",
            "version",
            "forward_operation",
            "rollback_strategy",
            "compatibility_classification",
            "expected_duration",
            "data_impact_statement",
            "verification_query",
            "destructive_changes_governed",
        ),
    ),
    (
        "backup_recovery",
        "Recovery procedures must be tested for all critical stores",
        (
            "manifest_repository",
            "registry_repository",
            "knowledge_data",
            "artifact_metadata",
            "governance_decisions",
            "audit_history",
            "configuration",
            "object_storage_artifacts",
            "recovery_procedures_tested",
        ),
    ),
    (
        "artifact_storage",
        "Large generated outputs stay outside the transactional database",
        (
            "metadata_in_database",
            "checksums_in_database",
            "lineage_in_database",
            "access_policy_in_database",
            "location_in_database",
            "retention_in_database",
            "generated_archives_in_object_store",
            "documentation_bundles_in_object_store",
            "source_packages_in_object_store",
            "reports_in_object_store",
            "exported_graphs_in_object_store",
        ),
    ),
    (
        "cli_operations",
        "The initial CLI calls platform APIs instead of duplicating logic",
        (
            "project_create",
            "manifest_validate",
            "manifest_approve",
            "graph_build",
            "transform_run",
            "generate",
            "build_verify",
            "artifact_download",
            "api_backed",
        ),
    ),
    (
        "generator_sdk",
        "Generators must be independently executable and testable",
        (
            "generator_interface",
            "input_model",
            "output_model",
            "template_access",
            "artifact_registration",
            "lineage_creation",
            "logging",
            "diagnostics",
            "validation_hooks",
            "test_harness",
        ),
    ),
    (
        "plugin_sdk",
        "Plugins must not gain unrestricted platform access",
        (
            "plugin_metadata",
            "version_compatibility",
            "capabilities",
            "permissions",
            "configuration_schema",
            "lifecycle_hooks",
            "isolation_requirements",
            "health_reporting",
            "installation",
            "activation",
            "deactivation",
        ),
    ),
    (
        "registry_bootstrap",
        "The first registry release is versioned platform data",
        (
            "foundational_object_definitions",
            "scalar_data_types",
            "relationship_types",
            "lifecycle_definitions",
            "validation_rules",
            "naming_rules",
            "basic_security_rules",
            "transformation_rules",
            "generator_bindings",
            "template_bindings",
            "versioned_data",
        ),
    ),
    (
        "registry_governance",
        "Registry modifications are platform-level governed changes",
        (
            "proposal",
            "compatibility_review",
            "rule_tests",
            "impact_analysis",
            "approval",
            "version_release",
        ),
    ),
    (
        "template_bootstrap",
        "The first template pack is simple, understandable, and replaceable",
        (
            "project_readme",
            "domain_entity",
            "repository_interface",
            "service_interface",
            "rest_controller",
            "request_response_models",
            "validation_class",
            "database_migration",
            "frontend_list_page",
            "frontend_form_page",
            "unit_test",
            "integration_test",
            "dockerfile",
            "compose_configuration",
        ),
    ),
    (
        "reference_project",
        "Customer and Order Management proves the full vertical slice",
        (
            "customer",
            "address",
            "product",
            "order",
            "order_item",
            "payment",
            "user",
            "role",
            "order_lifecycle",
            "payment_rules",
            "permissions",
            "rest_apis",
            "basic_ui_pages",
            "database",
            "tests",
            "docker_deployment",
        ),
    ),
    (
        "delivery_milestones",
        "Milestones preserve ordered implementation discipline",
        (
            "foundation",
            "manifest",
            "knowledge",
            "transformation",
            "generation",
            "experience",
            "governance_and_ai",
            "operational_release",
        ),
    ),
    (
        "team_roles",
        "Initial team covers platform capability ownership",
        (
            "platform_architect",
            "product_owner",
            "domain_language_engineer",
            "backend_engineers",
            "frontend_engineers",
            "ai_systems_engineer",
            "devops_or_platform_engineer",
            "quality_engineer",
            "security_engineer",
            "ux_designer",
            "technical_writer",
        ),
    ),
    (
        "ownership_categories",
        "Unowned components must not enter production",
        (
            "product_ownership",
            "architecture_ownership",
            "code_ownership",
            "registry_ownership",
            "template_ownership",
            "generator_ownership",
            "operational_ownership",
            "security_ownership",
        ),
    ),
    (
        "non_functional_requirements",
        "R12 platform qualities must remain explicit",
        (
            "reliability",
            "security",
            "scalability",
            "maintainability",
            "portability",
            "explainability",
            "reproducibility",
            "extensibility",
        ),
    ),
    (
        "risk_controls",
        "Implementation risks are controlled at every milestone",
        (
            "limit_mvp_scope",
            "require_structured_manifest_objects",
            "maintain_explicit_intermediate_models",
            "start_with_one_reference_stack",
            "use_golden_projects",
            "test_deterministic_output",
            "keep_bootstrap_core_small",
            "separate_registry_transformation_templates",
            "require_lineage_for_every_artifact",
            "govern_every_ai_generated_proposal",
        ),
    ),
)


def r12_implementation_status(repo_root: Path) -> R12ImplementationStatus:
    phases = tuple(
        _phase_status(repo_root, phase, name, signals)
        for phase, name, signals in _PHASE_SIGNALS
    )
    operational = sum(1 for item in phases if item.operational)
    next_phase = next((item.name for item in phases if not item.operational), None)
    payload = {
        "phases": [item.model_dump(mode="json") for item in phases],
        "operational_phase_count": operational,
        "next_phase": next_phase,
    }
    return R12ImplementationStatus(
        phase_count=len(phases),
        operational_phase_count=operational,
        next_phase=next_phase,
        vertical_slice_ready=all(item.operational for item in phases[:5]),
        phases=phases,
        status_hash=specification_hash(payload),
    )


def r12_repository_layout(repo_root: Path) -> R12RepositoryLayoutReport:
    items = tuple(
        R12RepositoryLayoutItem(
            path=path,
            purpose=purpose,
            present=(repo_root / path).exists(),
        )
        for path, purpose in _REPOSITORY_ITEMS
    )
    payload = {"items": [item.model_dump(mode="json") for item in items]}
    return R12RepositoryLayoutReport(
        item_count=len(items),
        present_count=sum(1 for item in items if item.present),
        missing_count=sum(1 for item in items if not item.present),
        items=items,
        layout_hash=specification_hash(payload),
    )


def r12_bootstrap_plan() -> R12BootstrapPlan:
    commands = tuple(
        R12BootstrapCommand(
            step=index,
            command=command,
            purpose=purpose,
            mutates_state=mutates_state,
        )
        for index, (command, purpose, mutates_state) in enumerate(_BOOTSTRAP_COMMANDS, start=1)
    )
    payload = {"commands": [item.model_dump(mode="json") for item in commands]}
    return R12BootstrapPlan(
        command_count=len(commands),
        commands=commands,
        plan_hash=specification_hash(payload),
    )


def r12_build_manifest_contract() -> R12BuildManifestContract:
    requirements = tuple(
        R12BuildManifestRequirement(field=field, purpose=purpose, required=True)
        for field, purpose in _BUILD_MANIFEST_FIELDS
    )
    payload = {"requirements": [item.model_dump(mode="json") for item in requirements]}
    return R12BuildManifestContract(
        requirement_count=len(requirements),
        requirements=requirements,
        contract_hash=specification_hash(payload),
    )


def r12_error_contract() -> R12ErrorContract:
    fields = tuple(
        R12ErrorContractField(field=field, purpose=purpose, required=True)
        for field, purpose in _ERROR_CONTRACT_FIELDS
    )
    payload = {"fields": [item.model_dump(mode="json") for item in fields]}
    return R12ErrorContract(
        field_count=len(fields),
        fields=fields,
        contract_hash=specification_hash(payload),
    )


def r12_shared_contract_catalog() -> R12SharedContractCatalog:
    contracts = tuple(
        _shared_contract_definition(contract_type, category, fields)
        for contract_type, (category, fields) in sorted(_SHARED_CONTRACTS.items())
    )
    payload = {"contracts": [item.model_dump(mode="json") for item in contracts]}
    return R12SharedContractCatalog(
        contract_count=len(contracts),
        contracts=contracts,
        catalog_hash=specification_hash(payload),
    )


def r12_platform_entity_catalog() -> R12PlatformEntityCatalog:
    entities = tuple(
        R12PlatformEntityDefinition(
            entity_type=entity_type,
            scope=scope,
            versioned=versioned,
            canonical_key_required=canonical_key_required,
        )
        for entity_type, scope, versioned, canonical_key_required in _PLATFORM_ENTITIES
    )
    payload = {"entities": [item.model_dump(mode="json") for item in entities]}
    return R12PlatformEntityCatalog(
        entity_count=len(entities),
        versioned_entity_count=sum(1 for item in entities if item.versioned),
        entities=entities,
        catalog_hash=specification_hash(payload),
    )


def r12_validate_identity_contract(
    entity: dict[str, Any],
) -> R12IdentityContractValidationReport:
    findings: list[R12IdentityContractFinding] = []
    entity_types = {item.entity_type for item in r12_platform_entity_catalog().entities}
    entity_type = entity.get("entity_type")
    if not isinstance(entity_type, str) or entity_type not in entity_types:
        findings.append(
            R12IdentityContractFinding(
                field="entity_type",
                severity="error",
                detail="entity_type must be one of the R12 platform entity types",
            )
        )
    definition = next(
        (
            item
            for item in r12_platform_entity_catalog().entities
            if item.entity_type == entity_type
        ),
        None,
    )
    for field in ("internal_id", "tenant"):
        _require_non_empty_identity_string(entity, field, findings)
    if definition is not None and "workspace" in definition.scope:
        _require_non_empty_identity_string(entity, "workspace", findings)
    if definition is not None and "project" in definition.scope:
        _require_non_empty_identity_string(entity, "project", findings)
    if definition is not None and "environment" in definition.scope:
        _require_non_empty_identity_string(entity, "environment", findings)
    if definition is not None and definition.canonical_key_required:
        _validate_canonical_key(entity, findings)
    if definition is not None and definition.versioned:
        _require_non_empty_identity_string(entity, "version", findings)
    if entity.get("internal_id") == entity.get("canonical_key"):
        findings.append(
            R12IdentityContractFinding(
                field="internal_id",
                severity="error",
                detail="internal_id must be non-semantic and distinct from canonical_key",
            )
        )
    ordered = tuple(sorted(findings, key=lambda item: (item.field, item.severity, item.detail)))
    valid = not any(item.severity == "error" for item in ordered)
    fingerprint = specification_hash(entity)
    payload = {
        "valid": valid,
        "findings": [item.model_dump(mode="json") for item in ordered],
        "entity_fingerprint": fingerprint,
    }
    return R12IdentityContractValidationReport(
        valid=valid,
        finding_count=len(ordered),
        findings=ordered,
        entity_fingerprint=fingerprint,
        report_hash=specification_hash(payload),
    )


def r12_deterministic_fingerprint_contract() -> R12DeterministicFingerprintContract:
    payload = {"required_inputs": list(_DETERMINISTIC_FINGERPRINT_INPUTS)}
    return R12DeterministicFingerprintContract(
        required_input_count=len(_DETERMINISTIC_FINGERPRINT_INPUTS),
        required_inputs=_DETERMINISTIC_FINGERPRINT_INPUTS,
        contract_hash=specification_hash(payload),
    )


def r12_compute_deterministic_fingerprint(
    inputs: dict[str, Any],
) -> R12DeterministicFingerprintReport:
    contract = r12_deterministic_fingerprint_contract()
    findings: list[R12IdentityContractFinding] = []
    for field in contract.required_inputs:
        if field not in inputs:
            findings.append(
                R12IdentityContractFinding(
                    field=field,
                    severity="error",
                    detail="required deterministic fingerprint input is missing",
                )
            )
            continue
        value = inputs[field]
        if field == "generation_options":
            if not isinstance(value, dict):
                findings.append(
                    R12IdentityContractFinding(
                        field=field,
                        severity="error",
                        detail="generation_options must be an object",
                    )
                )
        elif not isinstance(value, str) or not value.strip():
            findings.append(
                R12IdentityContractFinding(
                    field=field,
                    severity="error",
                    detail="field must be a non-empty string",
                )
            )
    relevant_inputs = {field: inputs.get(field) for field in contract.required_inputs}
    ordered = tuple(sorted(findings, key=lambda item: (item.field, item.severity, item.detail)))
    valid = not any(item.severity == "error" for item in ordered)
    fingerprint = specification_hash(relevant_inputs)
    payload = {
        "valid": valid,
        "findings": [item.model_dump(mode="json") for item in ordered],
        "deterministic_fingerprint": fingerprint,
        "contract_hash": contract.contract_hash,
    }
    return R12DeterministicFingerprintReport(
        valid=valid,
        finding_count=len(ordered),
        findings=ordered,
        deterministic_fingerprint=fingerprint,
        contract_hash=contract.contract_hash,
        report_hash=specification_hash(payload),
    )


def r12_operational_baseline_contract() -> R12OperationalBaselineContract:
    sections = tuple(
        R12OperationalBaselineSection(
            section=section,
            purpose=purpose,
            required_items=items,
        )
        for section, purpose, items in _OPERATIONAL_BASELINE_SECTIONS
    )
    payload = {"sections": [item.model_dump(mode="json") for item in sections]}
    return R12OperationalBaselineContract(
        section_count=len(sections),
        sections=sections,
        contract_hash=specification_hash(payload),
    )


def r12_validate_operational_baseline(
    evidence: dict[str, Any],
) -> R12OperationalBaselineValidationReport:
    contract = r12_operational_baseline_contract()
    findings: list[R12OperationalBaselineFinding] = []
    for section in contract.sections:
        raw = evidence.get(section.section)
        if raw is None:
            findings.append(
                R12OperationalBaselineFinding(
                    section=section.section,
                    item="*",
                    severity="error",
                    detail="required operational evidence section is missing",
                )
            )
            continue
        provided = _provided_operational_items(raw)
        if provided is None:
            findings.append(
                R12OperationalBaselineFinding(
                    section=section.section,
                    item="*",
                    severity="error",
                    detail=(
                        "section must be a list of item names or object "
                        "mapping item names to proof"
                    ),
                )
            )
            continue
        for item in section.required_items:
            if item not in provided:
                findings.append(
                    R12OperationalBaselineFinding(
                        section=section.section,
                        item=item,
                        severity="error",
                        detail="required operational baseline item is missing",
                    )
                )
    _validate_operational_secret_evidence(evidence, findings)
    ordered = tuple(
        sorted(findings, key=lambda item: (item.section, item.item, item.severity, item.detail))
    )
    valid = not any(item.severity == "error" for item in ordered)
    fingerprint = specification_hash(evidence)
    payload = {
        "valid": valid,
        "findings": [item.model_dump(mode="json") for item in ordered],
        "evidence_fingerprint": fingerprint,
        "contract_hash": contract.contract_hash,
    }
    return R12OperationalBaselineValidationReport(
        valid=valid,
        finding_count=len(ordered),
        findings=ordered,
        evidence_fingerprint=fingerprint,
        contract_hash=contract.contract_hash,
        report_hash=specification_hash(payload),
    )


def r12_verification_strategy_contract() -> R12VerificationStrategyContract:
    sections = tuple(
        R12VerificationStrategySection(
            section=section,
            purpose=purpose,
            required_items=items,
        )
        for section, purpose, items in _VERIFICATION_STRATEGY_SECTIONS
    )
    payload = {"sections": [item.model_dump(mode="json") for item in sections]}
    return R12VerificationStrategyContract(
        section_count=len(sections),
        sections=sections,
        contract_hash=specification_hash(payload),
    )


def r12_validate_verification_strategy(
    evidence: dict[str, Any],
) -> R12VerificationStrategyValidationReport:
    contract = r12_verification_strategy_contract()
    findings: list[R12VerificationStrategyFinding] = []
    for section in contract.sections:
        raw = evidence.get(section.section)
        if raw is None:
            findings.append(
                R12VerificationStrategyFinding(
                    section=section.section,
                    item="*",
                    severity="error",
                    detail="required verification evidence section is missing",
                )
            )
            continue
        provided = _provided_operational_items(raw)
        if provided is None:
            findings.append(
                R12VerificationStrategyFinding(
                    section=section.section,
                    item="*",
                    severity="error",
                    detail=(
                        "section must be a list of item names or object "
                        "mapping item names to proof"
                    ),
                )
            )
            continue
        for item in section.required_items:
            if item not in provided:
                findings.append(
                    R12VerificationStrategyFinding(
                        section=section.section,
                        item=item,
                        severity="error",
                        detail="required verification strategy item is missing",
                    )
                )
    _validate_e2e_order(evidence, findings)
    ordered = tuple(
        sorted(findings, key=lambda item: (item.section, item.item, item.severity, item.detail))
    )
    valid = not any(item.severity == "error" for item in ordered)
    fingerprint = specification_hash(evidence)
    payload = {
        "valid": valid,
        "findings": [item.model_dump(mode="json") for item in ordered],
        "evidence_fingerprint": fingerprint,
        "contract_hash": contract.contract_hash,
    }
    return R12VerificationStrategyValidationReport(
        valid=valid,
        finding_count=len(ordered),
        findings=ordered,
        evidence_fingerprint=fingerprint,
        contract_hash=contract.contract_hash,
        report_hash=specification_hash(payload),
    )


def r12_roadmap_governance_contract() -> R12RoadmapGovernanceContract:
    sections = tuple(
        R12RoadmapGovernanceSection(
            section=section,
            purpose=purpose,
            required_items=items,
        )
        for section, purpose, items in _ROADMAP_GOVERNANCE_SECTIONS
    )
    payload = {"sections": [item.model_dump(mode="json") for item in sections]}
    return R12RoadmapGovernanceContract(
        section_count=len(sections),
        sections=sections,
        contract_hash=specification_hash(payload),
    )


def r12_validate_roadmap_governance(
    evidence: dict[str, Any],
) -> R12RoadmapGovernanceValidationReport:
    contract = r12_roadmap_governance_contract()
    findings: list[R12RoadmapGovernanceFinding] = []
    for section in contract.sections:
        raw = evidence.get(section.section)
        if raw is None:
            findings.append(
                R12RoadmapGovernanceFinding(
                    section=section.section,
                    item="*",
                    severity="error",
                    detail="required roadmap governance evidence section is missing",
                )
            )
            continue
        provided = _provided_operational_items(raw)
        if provided is None:
            findings.append(
                R12RoadmapGovernanceFinding(
                    section=section.section,
                    item="*",
                    severity="error",
                    detail=(
                        "section must be a list of item names or object "
                        "mapping item names to proof"
                    ),
                )
            )
            continue
        for item in section.required_items:
            if item not in provided:
                findings.append(
                    R12RoadmapGovernanceFinding(
                        section=section.section,
                        item=item,
                        severity="error",
                        detail="required roadmap governance item is missing",
                    )
                )
    _validate_release_type_definitions(evidence, findings)
    _validate_roadmap_sequence(
        evidence,
        findings,
        "bootstrap_sequence",
        "bootstrap sequence must follow the R12 required order",
    )
    _validate_roadmap_sequence(
        evidence,
        findings,
        "self_hosting_migration_stages",
        "self-hosting migration stages must follow the R12 required order",
    )
    ordered = tuple(
        sorted(findings, key=lambda item: (item.section, item.item, item.severity, item.detail))
    )
    valid = not any(item.severity == "error" for item in ordered)
    fingerprint = specification_hash(evidence)
    payload = {
        "valid": valid,
        "findings": [item.model_dump(mode="json") for item in ordered],
        "evidence_fingerprint": fingerprint,
        "contract_hash": contract.contract_hash,
    }
    return R12RoadmapGovernanceValidationReport(
        valid=valid,
        finding_count=len(ordered),
        findings=ordered,
        evidence_fingerprint=fingerprint,
        contract_hash=contract.contract_hash,
        report_hash=specification_hash(payload),
    )


def r12_delivery_architecture_contract() -> R12DeliveryArchitectureContract:
    sections = tuple(
        R12DeliveryArchitectureSection(
            section=section,
            purpose=purpose,
            required_items=items,
        )
        for section, purpose, items in _DELIVERY_ARCHITECTURE_SECTIONS
    )
    payload = {"sections": [item.model_dump(mode="json") for item in sections]}
    return R12DeliveryArchitectureContract(
        section_count=len(sections),
        sections=sections,
        contract_hash=specification_hash(payload),
    )


def r12_validate_delivery_architecture(
    evidence: dict[str, Any],
) -> R12DeliveryArchitectureValidationReport:
    contract = r12_delivery_architecture_contract()
    findings: list[R12DeliveryArchitectureFinding] = []
    for section in contract.sections:
        raw = evidence.get(section.section)
        if raw is None:
            findings.append(
                R12DeliveryArchitectureFinding(
                    section=section.section,
                    item="*",
                    severity="error",
                    detail="required delivery architecture evidence section is missing",
                )
            )
            continue
        provided = _provided_operational_items(raw)
        if provided is None:
            findings.append(
                R12DeliveryArchitectureFinding(
                    section=section.section,
                    item="*",
                    severity="error",
                    detail=(
                        "section must be a list of item names or object "
                        "mapping item names to proof"
                    ),
                )
            )
            continue
        for item in section.required_items:
            if item not in provided:
                findings.append(
                    R12DeliveryArchitectureFinding(
                        section=section.section,
                        item=item,
                        severity="error",
                        detail="required delivery architecture item is missing",
                    )
                )
    for section_name, detail in (
        (
            "configuration_precedence",
            "configuration precedence must follow the R12 required order",
        ),
        (
            "deployment_architecture",
            "deployment architecture must follow the R12 modular-monolith order",
        ),
        ("registry_governance", "registry governance must follow the R12 required order"),
        ("delivery_milestones", "delivery milestones must follow the R12 required order"),
    ):
        _validate_delivery_sequence(evidence, findings, section_name, detail)
    _validate_ownership_proofs(evidence, findings)
    ordered = tuple(
        sorted(findings, key=lambda item: (item.section, item.item, item.severity, item.detail))
    )
    valid = not any(item.severity == "error" for item in ordered)
    fingerprint = specification_hash(evidence)
    payload = {
        "valid": valid,
        "findings": [item.model_dump(mode="json") for item in ordered],
        "evidence_fingerprint": fingerprint,
        "contract_hash": contract.contract_hash,
    }
    return R12DeliveryArchitectureValidationReport(
        valid=valid,
        finding_count=len(ordered),
        findings=ordered,
        evidence_fingerprint=fingerprint,
        contract_hash=contract.contract_hash,
        report_hash=specification_hash(payload),
    )


def r12_validate_build_manifest(
    manifest: dict[str, Any],
) -> R12BuildManifestValidationReport:
    contract = r12_build_manifest_contract()
    findings: list[R12BuildManifestFinding] = []
    required_fields = {item.field for item in contract.requirements}
    for field in sorted(required_fields):
        if field not in manifest:
            findings.append(
                R12BuildManifestFinding(
                    field=field,
                    severity="error",
                    detail="required build manifest field is missing",
                )
            )
    _validate_non_empty_strings(manifest, findings)
    _validate_version_fields(manifest, findings)
    _validate_checksums(manifest, findings)
    _validate_artifacts_and_lineage(manifest, findings)
    ordered = tuple(sorted(findings, key=lambda item: (item.field, item.severity, item.detail)))
    valid = not any(item.severity == "error" for item in ordered)
    fingerprint = specification_hash(manifest)
    payload = {
        "valid": valid,
        "findings": [item.model_dump(mode="json") for item in ordered],
        "required_contract_hash": contract.contract_hash,
        "manifest_fingerprint": fingerprint,
    }
    return R12BuildManifestValidationReport(
        valid=valid,
        finding_count=len(ordered),
        findings=ordered,
        required_contract_hash=contract.contract_hash,
        manifest_fingerprint=fingerprint,
        report_hash=specification_hash(payload),
    )


def r12_validate_error_contract(error: dict[str, Any]) -> R12ErrorContractValidationReport:
    contract = r12_error_contract()
    findings: list[R12ErrorContractFinding] = []
    required_fields = {item.field for item in contract.fields}
    for field in sorted(required_fields):
        if field not in error:
            findings.append(
                R12ErrorContractFinding(
                    field=field,
                    severity="error",
                    detail="required error contract field is missing",
                )
            )
    _validate_error_strings(error, findings)
    _validate_error_semantics(error, findings)
    _validate_error_sanitization(error, findings)
    ordered = tuple(sorted(findings, key=lambda item: (item.field, item.severity, item.detail)))
    valid = not any(item.severity == "error" for item in ordered)
    fingerprint = specification_hash(error)
    payload = {
        "valid": valid,
        "findings": [item.model_dump(mode="json") for item in ordered],
        "required_contract_hash": contract.contract_hash,
        "error_fingerprint": fingerprint,
    }
    return R12ErrorContractValidationReport(
        valid=valid,
        finding_count=len(ordered),
        findings=ordered,
        required_contract_hash=contract.contract_hash,
        error_fingerprint=fingerprint,
        report_hash=specification_hash(payload),
    )


def r12_validate_shared_contract(
    contract_type: str,
    envelope: dict[str, Any],
) -> R12SharedContractValidationReport:
    catalog = r12_shared_contract_catalog()
    contract = next(
        (item for item in catalog.contracts if item.contract_type == contract_type),
        None,
    )
    findings: list[R12SharedContractFinding] = []
    if contract is None:
        findings.append(
            R12SharedContractFinding(
                field="contract_type",
                severity="error",
                detail="contract_type must be one of command, event, query",
            )
        )
        required_hash = catalog.catalog_hash
    else:
        required_hash = contract.contract_hash
        for field in sorted(item.field for item in contract.fields):
            if field not in envelope:
                findings.append(
                    R12SharedContractFinding(
                        field=field,
                        severity="error",
                        detail="required shared contract field is missing",
                    )
                )
        _validate_shared_contract_strings(envelope, findings)
        _validate_shared_contract_objects(envelope, findings)
        _validate_shared_contract_semantics(contract_type, envelope, findings)
    ordered = tuple(sorted(findings, key=lambda item: (item.field, item.severity, item.detail)))
    valid = not any(item.severity == "error" for item in ordered)
    fingerprint = specification_hash(envelope)
    payload = {
        "valid": valid,
        "contract_type": contract_type,
        "findings": [item.model_dump(mode="json") for item in ordered],
        "required_contract_hash": required_hash,
        "envelope_fingerprint": fingerprint,
    }
    return R12SharedContractValidationReport(
        valid=valid,
        contract_type=contract_type,
        finding_count=len(ordered),
        findings=ordered,
        required_contract_hash=required_hash,
        envelope_fingerprint=fingerprint,
        report_hash=specification_hash(payload),
    )


def _phase_status(
    repo_root: Path,
    phase: int,
    name: str,
    signals: tuple[str, ...],
) -> R12PhaseStatus:
    present = tuple(signal for signal in signals if (repo_root / signal).exists())
    missing = tuple(signal for signal in signals if signal not in present)
    return R12PhaseStatus(
        phase=phase,
        name=name,
        required_signals=signals,
        present_signals=present,
        missing_signals=missing,
        operational=not missing,
    )


def _shared_contract_definition(
    contract_type: str,
    category: str,
    fields: tuple[tuple[str, str], ...],
) -> R12SharedContractDefinition:
    contract_fields = tuple(
        R12SharedContractField(field=field, purpose=purpose, required=True)
        for field, purpose in fields
    )
    payload = {
        "contract_type": contract_type,
        "category": category,
        "fields": [item.model_dump(mode="json") for item in contract_fields],
    }
    return R12SharedContractDefinition(
        contract_type=contract_type,
        category=category,
        fields=contract_fields,
        contract_hash=specification_hash(payload),
    )


def _require_non_empty_identity_string(
    entity: dict[str, Any],
    field: str,
    findings: list[R12IdentityContractFinding],
) -> None:
    value = entity.get(field)
    if not isinstance(value, str) or not value.strip():
        findings.append(
            R12IdentityContractFinding(
                field=field,
                severity="error",
                detail="field must be a non-empty string",
            )
        )


def _validate_canonical_key(
    entity: dict[str, Any],
    findings: list[R12IdentityContractFinding],
) -> None:
    key = entity.get("canonical_key")
    if not isinstance(key, str) or not key.strip():
        findings.append(
            R12IdentityContractFinding(
                field="canonical_key",
                severity="error",
                detail="canonical_key is required for this entity type",
            )
        )
    elif _CANONICAL_KEY_RE.fullmatch(key) is None:
        findings.append(
            R12IdentityContractFinding(
                field="canonical_key",
                severity="error",
                detail="canonical_key must be uppercase and human-readable",
            )
        )


def _provided_operational_items(raw: object) -> set[str] | None:
    if isinstance(raw, list) and all(isinstance(item, str) for item in raw):
        return {item for item in raw if item}
    if isinstance(raw, dict):
        return {
            str(key)
            for key, value in raw.items()
            if value not in (None, False, "", [], {})
        }
    return None


def _validate_operational_secret_evidence(
    evidence: dict[str, Any],
    findings: list[R12OperationalBaselineFinding],
) -> None:
    secret_hygiene = evidence.get("secret_hygiene")
    if not isinstance(secret_hygiene, dict):
        return
    for item, proof in secret_hygiene.items():
        if _contains_inline_secret_value(proof):
            findings.append(
                R12OperationalBaselineFinding(
                    section="secret_hygiene",
                    item=str(item),
                    severity="error",
                    detail=(
                        "secret hygiene proof must use references and must "
                        "not embed secret values"
                    ),
                )
            )


def _contains_inline_secret_value(value: object) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in {"secret", "password", "token", "api_key", "private_key"}:
                return True
            if _contains_inline_secret_value(item):
                return True
    if isinstance(value, list):
        return any(_contains_inline_secret_value(item) for item in value)
    if isinstance(value, str):
        return any(marker in value.lower() for marker in ("password=", "token=", "secret="))
    return False


def _validate_e2e_order(
    evidence: dict[str, Any],
    findings: list[R12VerificationStrategyFinding],
) -> None:
    raw = evidence.get("mvp_e2e_sequence")
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        return
    expected = next(
        items
        for section, _purpose, items in _VERIFICATION_STRATEGY_SECTIONS
        if section == "mvp_e2e_sequence"
    )
    if tuple(raw) != expected:
        findings.append(
            R12VerificationStrategyFinding(
                section="mvp_e2e_sequence",
                item="order",
                severity="error",
                detail="MVP end-to-end sequence must follow the R12 required order",
            )
        )


def _validate_release_type_definitions(
    evidence: dict[str, Any],
    findings: list[R12RoadmapGovernanceFinding],
) -> None:
    release_types = evidence.get("release_types")
    if not isinstance(release_types, dict):
        return
    required = next(
        items
        for section, _purpose, items in _ROADMAP_GOVERNANCE_SECTIONS
        if section == "release_types"
    )
    for release_type in required:
        proof = release_types.get(release_type)
        if not isinstance(proof, dict):
            continue
        for field in ("supported_capabilities", "limitations"):
            value = proof.get(field)
            if not isinstance(value, list) or not value:
                findings.append(
                    R12RoadmapGovernanceFinding(
                        section="release_types",
                        item=release_type,
                        severity="error",
                        detail=(
                            "each release type must define supported_capabilities "
                            "and limitations"
                        ),
                    )
                )


def _validate_roadmap_sequence(
    evidence: dict[str, Any],
    findings: list[R12RoadmapGovernanceFinding],
    section_name: str,
    detail: str,
) -> None:
    raw = evidence.get(section_name)
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        return
    expected = next(
        items
        for section, _purpose, items in _ROADMAP_GOVERNANCE_SECTIONS
        if section == section_name
    )
    if tuple(raw) != expected:
        findings.append(
            R12RoadmapGovernanceFinding(
                section=section_name,
                item="order",
                severity="error",
                detail=detail,
            )
        )


def _validate_delivery_sequence(
    evidence: dict[str, Any],
    findings: list[R12DeliveryArchitectureFinding],
    section_name: str,
    detail: str,
) -> None:
    raw = evidence.get(section_name)
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        return
    expected = next(
        items
        for section, _purpose, items in _DELIVERY_ARCHITECTURE_SECTIONS
        if section == section_name
    )
    if tuple(raw) != expected:
        findings.append(
            R12DeliveryArchitectureFinding(
                section=section_name,
                item="order",
                severity="error",
                detail=detail,
            )
        )


def _validate_ownership_proofs(
    evidence: dict[str, Any],
    findings: list[R12DeliveryArchitectureFinding],
) -> None:
    ownership = evidence.get("ownership_categories")
    if not isinstance(ownership, dict):
        return
    for item, proof in ownership.items():
        if not isinstance(proof, dict) or not proof.get("owner"):
            findings.append(
                R12DeliveryArchitectureFinding(
                    section="ownership_categories",
                    item=str(item),
                    severity="error",
                    detail="ownership proof must name an owner before production entry",
                )
            )


def _validate_non_empty_strings(
    manifest: dict[str, Any],
    findings: list[R12BuildManifestFinding],
) -> None:
    for field in (
        "build_id",
        "generation_timestamp",
        "project_id",
        "manifest_version",
        "registry_version",
        "target_stack",
    ):
        if field in manifest and not isinstance(manifest[field], str):
            findings.append(
                R12BuildManifestFinding(
                    field=field,
                    severity="error",
                    detail="field must be a string",
                )
            )
        elif field in manifest and not manifest[field].strip():
            findings.append(
                R12BuildManifestFinding(
                    field=field,
                    severity="error",
                    detail="field must not be empty",
                )
            )


def _validate_version_fields(
    manifest: dict[str, Any],
    findings: list[R12BuildManifestFinding],
) -> None:
    for field in ("generator_versions", "template_versions", "policy_versions"):
        value = manifest.get(field)
        if value is None:
            continue
        if not isinstance(value, dict) or not value:
            findings.append(
                R12BuildManifestFinding(
                    field=field,
                    severity="error",
                    detail="field must be a non-empty object mapping component keys to versions",
                )
            )
            continue
        for key, version in value.items():
            if not isinstance(key, str) or not key:
                findings.append(
                    R12BuildManifestFinding(
                        field=field,
                        severity="error",
                        detail="version map contains an empty or non-string component key",
                    )
                )
            if not isinstance(version, str) or not version:
                findings.append(
                    R12BuildManifestFinding(
                        field=field,
                        severity="error",
                        detail=f"component {key} has an empty or non-string version",
                    )
                )


def _validate_checksums(
    manifest: dict[str, Any],
    findings: list[R12BuildManifestFinding],
) -> None:
    checksums = manifest.get("checksums")
    if checksums is None:
        return
    if not isinstance(checksums, dict) or not checksums:
        findings.append(
            R12BuildManifestFinding(
                field="checksums",
                severity="error",
                detail="checksums must be a non-empty object of artifact paths to sha256 values",
            )
        )
        return
    for path, checksum in checksums.items():
        if (
            not isinstance(path, str)
            or not path
            or path.startswith("/")
            or ".." in Path(path).parts
        ):
            findings.append(
                R12BuildManifestFinding(
                    field="checksums",
                    severity="error",
                    detail=f"checksum path is not a safe relative path: {path}",
                )
            )
        if not isinstance(checksum, str) or _SHA256_RE.fullmatch(checksum) is None:
            findings.append(
                R12BuildManifestFinding(
                    field="checksums",
                    severity="error",
                    detail=f"checksum for {path} is not a lowercase sha256 hash",
                )
            )


def _validate_shared_contract_strings(
    envelope: dict[str, Any],
    findings: list[R12SharedContractFinding],
) -> None:
    for field in sorted(_SHARED_CONTRACT_REQUIRED_STRING_FIELDS):
        if field not in envelope:
            continue
        value = envelope[field]
        if not isinstance(value, str):
            findings.append(
                R12SharedContractFinding(
                    field=field,
                    severity="error",
                    detail="field must be a string",
                )
            )
        elif not value.strip():
            findings.append(
                R12SharedContractFinding(
                    field=field,
                    severity="error",
                    detail="field must not be empty",
                )
            )


def _validate_shared_contract_objects(
    envelope: dict[str, Any],
    findings: list[R12SharedContractFinding],
) -> None:
    for field in sorted(_SHARED_CONTRACT_REQUIRED_OBJECT_FIELDS):
        if field not in envelope:
            continue
        value = envelope[field]
        if not isinstance(value, dict) or not value:
            findings.append(
                R12SharedContractFinding(
                    field=field,
                    severity="error",
                    detail="field must be a non-empty object",
                )
            )


def _validate_shared_contract_semantics(
    contract_type: str,
    envelope: dict[str, Any],
    findings: list[R12SharedContractFinding],
) -> None:
    if contract_type == "command":
        expected_version = envelope.get("expected_version")
        if not isinstance(expected_version, int) or expected_version < 0:
            findings.append(
                R12SharedContractFinding(
                    field="expected_version",
                    severity="error",
                    detail="expected_version must be a non-negative integer",
                )
            )
    if contract_type == "event" and envelope.get("immutable") is not True:
        findings.append(
            R12SharedContractFinding(
                field="immutable",
                severity="error",
                detail="events must explicitly declare immutable=true",
            )
        )
    if contract_type == "query" and "payload" in envelope:
        findings.append(
            R12SharedContractFinding(
                field="payload",
                severity="error",
                detail="queries must use parameters and must not carry mutation payloads",
            )
        )


def _validate_error_strings(
    error: dict[str, Any],
    findings: list[R12ErrorContractFinding],
) -> None:
    for field in sorted(_ERROR_REQUIRED_STRING_FIELDS):
        value = error.get(field)
        if value is None:
            continue
        if not isinstance(value, str):
            findings.append(
                R12ErrorContractFinding(
                    field=field,
                    severity="error",
                    detail="field must be a string",
                )
            )
        elif not value.strip():
            findings.append(
                R12ErrorContractFinding(
                    field=field,
                    severity="error",
                    detail="field must not be empty",
                )
            )

    if "technical_detail" in error and not isinstance(error["technical_detail"], str):
        findings.append(
            R12ErrorContractFinding(
                field="technical_detail",
                severity="error",
                detail="field must be a string",
            )
        )
    if "affected_object" in error and error["affected_object"] is None:
        findings.append(
            R12ErrorContractFinding(
                field="affected_object",
                severity="error",
                detail="field must identify the affected object",
            )
        )


def _validate_error_semantics(
    error: dict[str, Any],
    findings: list[R12ErrorContractFinding],
) -> None:
    code = error.get("error_code")
    if isinstance(code, str) and code and _ERROR_CODE_RE.fullmatch(code) is None:
        findings.append(
            R12ErrorContractFinding(
                field="error_code",
                severity="error",
                detail="error_code must be uppercase and stable for machine matching",
            )
        )

    severity = error.get("severity")
    if isinstance(severity, str) and severity and severity not in _ERROR_SEVERITIES:
        findings.append(
            R12ErrorContractFinding(
                field="severity",
                severity="error",
                detail="severity must be one of info, warning, error, critical",
            )
        )

    docs = error.get("documentation_reference")
    if isinstance(docs, str) and docs and not docs.startswith(_DOCUMENTATION_PREFIXES):
        findings.append(
            R12ErrorContractFinding(
                field="documentation_reference",
                severity="error",
                detail=(
                    "documentation_reference must be docs/, https://, "
                    "urn:, or roadmap reference"
                ),
            )
        )


def _validate_error_sanitization(
    error: dict[str, Any],
    findings: list[R12ErrorContractFinding],
) -> None:
    for field in ("message", "technical_detail"):
        value = error.get(field)
        if not isinstance(value, str):
            continue
        leaked = tuple(marker for marker in _SENSITIVE_ERROR_MARKERS if marker in value)
        if leaked:
            findings.append(
                R12ErrorContractFinding(
                    field=field,
                    severity="error",
                    detail=f"field exposes internal or sensitive detail: {', '.join(leaked)}",
                )
            )


def _validate_artifacts_and_lineage(
    manifest: dict[str, Any],
    findings: list[R12BuildManifestFinding],
) -> None:
    artifacts = manifest.get("generated_artifacts")
    lineage = manifest.get("lineage_references")
    if artifacts is not None and (
        not isinstance(artifacts, list) or not all(isinstance(item, str) for item in artifacts)
    ):
        findings.append(
            R12BuildManifestFinding(
                field="generated_artifacts",
                severity="error",
                detail="generated_artifacts must be a list of artifact path strings",
            )
        )
    if lineage is not None and not isinstance(lineage, dict):
        findings.append(
            R12BuildManifestFinding(
                field="lineage_references",
                severity="error",
                detail="lineage_references must map artifact paths to source object references",
            )
        )
    if isinstance(artifacts, list) and isinstance(lineage, dict):
        missing_lineage = sorted(str(item) for item in artifacts if item not in lineage)
        for artifact in missing_lineage:
            findings.append(
                R12BuildManifestFinding(
                    field="lineage_references",
                    severity="error",
                    detail=f"artifact lacks lineage reference: {artifact}",
                )
            )
