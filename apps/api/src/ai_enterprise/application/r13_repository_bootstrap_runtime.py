from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from ai_enterprise.domain.specification.kernel import specification_hash


class R13RepositoryDirectory(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    responsibility: str
    authoritative: bool


class R13RepositoryLayoutContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    directory_count: int
    directories: tuple[R13RepositoryDirectory, ...]
    readme_sentence: str
    contract_hash: str


class R13RepositoryLayoutItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    responsibility: str
    authoritative: bool
    present: bool


class R13RepositoryLayoutReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    item_count: int
    present_count: int
    missing_count: int
    items: tuple[R13RepositoryLayoutItem, ...]
    readme_sentence_present: bool
    layout_hash: str


class R13BootstrapStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    step: int
    name: str
    purpose: str


class R13BootstrapSequenceContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    step_count: int
    steps: tuple[R13BootstrapStep, ...]
    guarantees: tuple[str, ...]
    contract_hash: str


class R13BootstrapSequenceFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: str
    severity: str
    detail: str


class R13BootstrapSequenceValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    finding_count: int
    findings: tuple[R13BootstrapSequenceFinding, ...]
    sequence_fingerprint: str
    contract_hash: str
    report_hash: str


class R13ComponentBoundary(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    responsibility: str
    exclusive: bool


class R13ComponentBoundaryContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    component_count: int
    components: tuple[R13ComponentBoundary, ...]
    invariant: str
    contract_hash: str


class R13DirectoryContentRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    allowed_content: tuple[str, ...]
    forbidden_content: tuple[str, ...]
    authoritative: bool


class R13DirectoryContentContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_count: int
    rules: tuple[R13DirectoryContentRule, ...]
    invariant: str
    contract_hash: str


class R13RepositoryPrinciple(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    guarantee: str


class R13RepositoryPrinciplesContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    principle_count: int
    principles: tuple[R13RepositoryPrinciple, ...]
    contract_hash: str


class R13ExecutableSkeletonReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    layout_missing_count: int
    internal_home_missing_count: int
    internal_home_count: int
    missing_internal_homes: tuple[str, ...]
    readme_sentence_present: bool
    component_count: int
    directory_rule_count: int
    principle_count: int
    bootstrap_step_count: int
    contract_hashes: dict[str, str]
    report_hash: str


class R13RepositoryMissionContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_artifact: str
    output_artifact: str
    ownership_boundary: str
    contract_hash: str


class R13BootstrapPipelineStage(BaseModel):
    model_config = ConfigDict(frozen=True)

    stage: int
    name: str
    consumes: str
    produces: str
    component: str


class R13BootstrapPipelineContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    stage_count: int
    stages: tuple[R13BootstrapPipelineStage, ...]
    invariant: str
    contract_hash: str


_README_SENTENCE = (
    "This repository converts an AI-Enterprise Manifest into a complete software system."
)

_MISSION_INPUT = "Manifest.json"
_MISSION_OUTPUT = "Entire Software System"
_MISSION_BOUNDARY = "Everything between Manifest.json and the output belongs to AI-Enterprise."

_DIRECTORIES: tuple[tuple[str, str, bool], ...] = (
    ("README.md", "Repository mission statement", True),
    ("manifest", "Current, historical, sample, and template manifests", True),
    ("registry", "Registered object definitions before any generation occurs", True),
    ("schemas", "Executable schemas that define validity", True),
    ("compiler", "Validated graph compiler and dependency resolver", True),
    ("planner", "Deterministic implementation order planner", True),
    ("runtime", "Explicit generation state and execution history", True),
    ("generators", "Independent generators consuming validated graph data", True),
    ("validators", "Pre-generation validation modules", True),
    ("knowledge", "Semantic memory and project graph data", True),
    ("workspace", "Regenerable temporary execution area", False),
    ("templates", "Reusable technical implementation templates", True),
    ("examples", "Example manifests for validation and tests", False),
    ("tests", "Module and generation verification suites", True),
    ("logs", "Append-only execution history and metrics", False),
    ("docs", "Repository documentation", True),
    ("config", "Repository configuration, never customer data", True),
)

_BOOTSTRAP_STEPS: tuple[tuple[str, str], ...] = (
    ("load_manifest", "Load the Manifest as the only project-specific input"),
    ("validate_manifest", "Reject invalid Manifest content before compilation"),
    ("load_registry", "Load the Registry as the only architectural definition source"),
    ("validate_registry", "Reject invalid registry definitions before expansion"),
    ("build_knowledge_graph", "Create semantic project memory"),
    ("resolve_dependencies", "Resolve dependencies before planning"),
    ("build_execution_graph", "Compile deterministic executable graph"),
    ("create_plan", "Create deterministic implementation phases"),
    ("execute_generators", "Generate artifacts only from validated graph data"),
    ("validate_output", "Validate generated output before publication"),
    ("produce_project", "Produce the complete software system"),
)

_BOOTSTRAP_GUARANTEES: tuple[str, ...] = (
    "manifest_only_project_specific_input",
    "registry_only_architectural_definition_source",
    "compiler_produces_deterministic_execution_graph",
    "generators_consume_validated_graph_data_only",
    "artifacts_reproducible_from_manifest_and_registry",
    "runtime_state_explicit_and_recoverable",
    "no_hidden_conversational_context",
)

_BOOTSTRAP_PIPELINE: tuple[tuple[str, str, str, str], ...] = (
    ("manifest", "Manifest.json", "Validated Manifest candidate", "manifest_engine"),
    ("validation", "Manifest", "Validation result", "validator"),
    ("registry_expansion", "Validated Manifest", "Expanded Registry", "registry"),
    ("dependency_resolution", "Expanded Registry", "Resolved dependency graph", "compiler"),
    ("knowledge_graph", "Resolved dependency graph", "Knowledge graph", "knowledge_graph"),
    ("execution_plan", "Knowledge graph", "Execution plan", "planner"),
    ("generators", "Execution plan", "Generated software system", "generator"),
)

_COMPONENT_BOUNDARIES: tuple[tuple[str, str], ...] = (
    ("manifest_engine", "Load and normalize Manifest input"),
    ("registry", "Own every architectural definition before generation"),
    ("validator", "Reject invalid Manifest, Registry, policy, dependency, and version state"),
    ("compiler", "Transform validated definitions into a deterministic execution graph"),
    ("planner", "Create deterministic phased implementation order"),
    ("knowledge_graph", "Store semantic memory, ontology, relations, and history"),
    ("ai_runtime", "Execute AI-assisted work only from explicit runtime state"),
    ("generator", "Produce artifacts from validated graph data"),
    ("synchronizer", "Coordinate generated artifacts and external project state"),
    ("runtime_workspace", "Hold regenerable generated, cached, snapshot, and preview state"),
)

_DIRECTORY_CONTENT_RULES: tuple[tuple[str, tuple[str, ...], tuple[str, ...], bool], ...] = (
    (
        "manifest",
        ("current manifests", "historical manifests", "sample manifests", "manifest templates"),
        ("registered object definitions", "generated source code"),
        True,
    ),
    (
        "registry",
        (
            "entities",
            "actions",
            "roles",
            "policies",
            "workflows",
            "components",
            "ui",
            "api",
            "infrastructure",
            "integrations",
        ),
        ("customer runtime data", "temporary workspace cache"),
        True,
    ),
    (
        "schemas",
        ("Manifest.schema.json", "Entity.schema.json", "Workflow.schema.json", "API.schema.json"),
        ("business-specific generated code",),
        True,
    ),
    (
        "compiler",
        ("validation", "registry expansion", "dependency resolution", "execution graph build"),
        ("direct artifact generation bypassing validated graph data",),
        True,
    ),
    (
        "planner",
        ("phase planning", "deployment planning", "deterministic ordering"),
        ("generate everything in one opaque step",),
        True,
    ),
    (
        "runtime",
        (
            "current context",
            "current phase",
            "generated objects",
            "pending objects",
            "failed objects",
            "retries",
            "execution history",
        ),
        ("hidden conversational memory",),
        True,
    ),
    (
        "generators",
        (
            "api generator",
            "database generator",
            "frontend generator",
            "backend generator",
            "workflow generator",
            "tests generator",
            "docker generator",
            "ci/cd generator",
            "infrastructure generator",
            "documentation generator",
        ),
        ("business logic in templates", "unvalidated graph input"),
        True,
    ),
    (
        "validators",
        (
            "manifest validation",
            "registry validation",
            "naming validation",
            "dependency validation",
            "cycle validation",
            "missing object validation",
            "version compatibility validation",
            "policy conflict validation",
        ),
        ("post-generation-only validation",),
        True,
    ),
    (
        "knowledge",
        ("graph.json", "ontology.json", "relations.json", "history.json"),
        ("authoritative generated source",),
        True,
    ),
    (
        "workspace",
        ("generated", "cache", "snapshots", "preview"),
        ("authoritative definitions",),
        False,
    ),
    (
        "templates",
        ("React", "Angular", "Vue", "Spring", ".NET", "Node", "Laravel", "Flutter", "Python", "Go"),
        ("business logic",),
        True,
    ),
    (
        "examples",
        (
            "Hospital",
            "Bank",
            "CRM",
            "ERP",
            "Marketplace",
            "Warehouse",
            "School",
            "Insurance",
            "Factory",
        ),
        ("production customer data",),
        False,
    ),
    (
        "tests",
        (
            "registry tests",
            "manifest tests",
            "compiler tests",
            "planner tests",
            "generator tests",
            "validator tests",
        ),
        ("untested generation approval",),
        True,
    ),
    (
        "logs",
        ("generation logs", "validation logs", "errors", "warnings", "metrics"),
        ("mutable authoritative definitions",),
        False,
    ),
    (
        "config",
        (
            "AI provider",
            "execution limits",
            "generator options",
            "template selection",
            "environment",
            "feature flags",
        ),
        ("customer data", "inline secret values"),
        True,
    ),
)

_REPOSITORY_PRINCIPLES: tuple[tuple[str, str], ...] = (
    ("Single Source of Intent", "the Manifest defines what the client wants"),
    ("Single Source of Definition", "the Registry defines what each concept means"),
    ("Deterministic Compilation", "identical inputs produce identical execution plans"),
    ("Stateless Generation", "generators never depend on prior chat history"),
    ("Complete Traceability", "every output can be traced back to Manifest and Registry entries"),
    ("Regenerability", "the entire project can be rebuilt from source definitions"),
)

_INTERNAL_HOMES: tuple[str, ...] = (
    "manifest/customer.json",
    "manifest/hospital.json",
    "manifest/crm.json",
    "manifest/erp.json",
    "registry/Entities",
    "registry/Actions",
    "registry/Roles",
    "registry/Policies",
    "registry/Workflows",
    "registry/Components",
    "registry/UI",
    "registry/API",
    "registry/Infrastructure",
    "registry/Integrations",
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
    "workspace/generated",
    "workspace/cache",
    "workspace/snapshots",
    "workspace/preview",
    "knowledge/graph.json",
    "knowledge/ontology.json",
    "knowledge/relations.json",
    "knowledge/history.json",
    "logs/generation",
    "logs/validation",
    "logs/errors",
    "logs/warnings",
    "logs/metrics",
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
)


def r13_repository_layout_contract() -> R13RepositoryLayoutContract:
    directories = tuple(
        R13RepositoryDirectory(
            path=path,
            responsibility=responsibility,
            authoritative=authoritative,
        )
        for path, responsibility, authoritative in _DIRECTORIES
    )
    payload = {
        "directories": [item.model_dump(mode="json") for item in directories],
        "readme_sentence": _README_SENTENCE,
    }
    return R13RepositoryLayoutContract(
        directory_count=len(directories),
        directories=directories,
        readme_sentence=_README_SENTENCE,
        contract_hash=specification_hash(payload),
    )


def r13_repository_mission_contract() -> R13RepositoryMissionContract:
    payload = {
        "input_artifact": _MISSION_INPUT,
        "output_artifact": _MISSION_OUTPUT,
        "ownership_boundary": _MISSION_BOUNDARY,
    }
    return R13RepositoryMissionContract(
        input_artifact=_MISSION_INPUT,
        output_artifact=_MISSION_OUTPUT,
        ownership_boundary=_MISSION_BOUNDARY,
        contract_hash=specification_hash(payload),
    )


def r13_repository_layout(repo_root: Path) -> R13RepositoryLayoutReport:
    contract = r13_repository_layout_contract()
    items = tuple(
        R13RepositoryLayoutItem(
            path=item.path,
            responsibility=item.responsibility,
            authoritative=item.authoritative,
            present=(repo_root / item.path).exists(),
        )
        for item in contract.directories
    )
    readme = repo_root / "README.md"
    sentence_present = readme.exists() and _README_SENTENCE in readme.read_text(
        encoding="utf-8", errors="ignore"
    )
    payload = {
        "items": [item.model_dump(mode="json") for item in items],
        "readme_sentence_present": sentence_present,
    }
    return R13RepositoryLayoutReport(
        item_count=len(items),
        present_count=sum(1 for item in items if item.present),
        missing_count=sum(1 for item in items if not item.present),
        items=items,
        readme_sentence_present=sentence_present,
        layout_hash=specification_hash(payload),
    )


def r13_bootstrap_sequence_contract() -> R13BootstrapSequenceContract:
    steps = tuple(
        R13BootstrapStep(step=index, name=name, purpose=purpose)
        for index, (name, purpose) in enumerate(_BOOTSTRAP_STEPS, start=1)
    )
    payload = {
        "steps": [item.model_dump(mode="json") for item in steps],
        "guarantees": list(_BOOTSTRAP_GUARANTEES),
    }
    return R13BootstrapSequenceContract(
        step_count=len(steps),
        steps=steps,
        guarantees=_BOOTSTRAP_GUARANTEES,
        contract_hash=specification_hash(payload),
    )


def r13_bootstrap_pipeline_contract() -> R13BootstrapPipelineContract:
    stages = tuple(
        R13BootstrapPipelineStage(
            stage=index,
            name=name,
            consumes=consumes,
            produces=produces,
            component=component,
        )
        for index, (name, consumes, produces, component) in enumerate(
            _BOOTSTRAP_PIPELINE,
            start=1,
        )
    )
    payload = {
        "stages": [item.model_dump(mode="json") for item in stages],
        "invariant": "No generation bypasses the compiler pipeline.",
    }
    return R13BootstrapPipelineContract(
        stage_count=len(stages),
        stages=stages,
        invariant="No generation bypasses the compiler pipeline.",
        contract_hash=specification_hash(payload),
    )


def r13_validate_bootstrap_sequence(
    sequence: dict[str, Any],
) -> R13BootstrapSequenceValidationReport:
    contract = r13_bootstrap_sequence_contract()
    findings: list[R13BootstrapSequenceFinding] = []
    steps = sequence.get("steps")
    guarantees = sequence.get("guarantees")
    expected_steps = [item.name for item in contract.steps]
    if not isinstance(steps, list) or not all(isinstance(item, str) for item in steps):
        findings.append(
            R13BootstrapSequenceFinding(
                field="steps",
                severity="error",
                detail="steps must be a list of bootstrap step names",
            )
        )
    elif steps != expected_steps:
        findings.append(
            R13BootstrapSequenceFinding(
                field="steps",
                severity="error",
                detail="bootstrap steps must exactly follow the R13 required order",
            )
        )
    if not isinstance(guarantees, list) or not all(
        isinstance(item, str) for item in guarantees
    ):
        findings.append(
            R13BootstrapSequenceFinding(
                field="guarantees",
                severity="error",
                detail="guarantees must be a list of guarantee identifiers",
            )
        )
    else:
        missing = sorted(set(contract.guarantees) - set(guarantees))
        for item in missing:
            findings.append(
                R13BootstrapSequenceFinding(
                    field="guarantees",
                    severity="error",
                    detail=f"required bootstrap guarantee is missing: {item}",
                )
            )
    if sequence.get("uses_conversation_memory") is True:
        findings.append(
            R13BootstrapSequenceFinding(
                field="uses_conversation_memory",
                severity="error",
                detail="R13 bootstrap must not rely on hidden conversational context",
            )
        )
    ordered = tuple(sorted(findings, key=lambda item: (item.field, item.detail)))
    valid = not any(item.severity == "error" for item in ordered)
    fingerprint = specification_hash(sequence)
    payload = {
        "valid": valid,
        "findings": [item.model_dump(mode="json") for item in ordered],
        "sequence_fingerprint": fingerprint,
        "contract_hash": contract.contract_hash,
    }
    return R13BootstrapSequenceValidationReport(
        valid=valid,
        finding_count=len(ordered),
        findings=ordered,
        sequence_fingerprint=fingerprint,
        contract_hash=contract.contract_hash,
        report_hash=specification_hash(payload),
    )


def r13_component_boundary_contract() -> R13ComponentBoundaryContract:
    components = tuple(
        R13ComponentBoundary(
            name=name,
            responsibility=responsibility,
            exclusive=True,
        )
        for name, responsibility in _COMPONENT_BOUNDARIES
    )
    payload = {
        "components": [item.model_dump(mode="json") for item in components],
        "invariant": "Nothing outside these components participates in generation.",
    }
    return R13ComponentBoundaryContract(
        component_count=len(components),
        components=components,
        invariant="Nothing outside these components participates in generation.",
        contract_hash=specification_hash(payload),
    )


def r13_directory_content_contract() -> R13DirectoryContentContract:
    rules = tuple(
        R13DirectoryContentRule(
            path=path,
            allowed_content=allowed,
            forbidden_content=forbidden,
            authoritative=authoritative,
        )
        for path, allowed, forbidden, authoritative in _DIRECTORY_CONTENT_RULES
    )
    payload = {
        "rules": [item.model_dump(mode="json") for item in rules],
        "invariant": "Every R13 directory has one responsibility and no mixed responsibilities.",
    }
    return R13DirectoryContentContract(
        rule_count=len(rules),
        rules=rules,
        invariant="Every R13 directory has one responsibility and no mixed responsibilities.",
        contract_hash=specification_hash(payload),
    )


def r13_repository_principles_contract() -> R13RepositoryPrinciplesContract:
    principles = tuple(
        R13RepositoryPrinciple(name=name, guarantee=guarantee)
        for name, guarantee in _REPOSITORY_PRINCIPLES
    )
    payload = {
        "principles": [item.model_dump(mode="json") for item in principles],
    }
    return R13RepositoryPrinciplesContract(
        principle_count=len(principles),
        principles=principles,
        contract_hash=specification_hash(payload),
    )


def r13_executable_skeleton_report(repo_root: Path) -> R13ExecutableSkeletonReport:
    layout = r13_repository_layout(repo_root)
    missing_internal_homes = tuple(
        path for path in _INTERNAL_HOMES if not (repo_root / path).exists()
    )
    mission_contract = r13_repository_mission_contract()
    component_contract = r13_component_boundary_contract()
    directory_contract = r13_directory_content_contract()
    principle_contract = r13_repository_principles_contract()
    bootstrap_contract = r13_bootstrap_sequence_contract()
    pipeline_contract = r13_bootstrap_pipeline_contract()
    contract_hashes = {
        "mission": mission_contract.contract_hash,
        "layout": r13_repository_layout_contract().contract_hash,
        "components": component_contract.contract_hash,
        "directory_content": directory_contract.contract_hash,
        "principles": principle_contract.contract_hash,
        "bootstrap_sequence": bootstrap_contract.contract_hash,
        "bootstrap_pipeline": pipeline_contract.contract_hash,
    }
    payload = {
        "layout_missing_count": layout.missing_count,
        "internal_home_count": len(_INTERNAL_HOMES),
        "missing_internal_homes": list(missing_internal_homes),
        "readme_sentence_present": layout.readme_sentence_present,
        "contract_hashes": contract_hashes,
    }
    valid = (
        layout.missing_count == 0
        and not missing_internal_homes
        and layout.readme_sentence_present
    )
    return R13ExecutableSkeletonReport(
        valid=valid,
        layout_missing_count=layout.missing_count,
        internal_home_missing_count=len(missing_internal_homes),
        internal_home_count=len(_INTERNAL_HOMES),
        missing_internal_homes=missing_internal_homes,
        readme_sentence_present=layout.readme_sentence_present,
        component_count=component_contract.component_count,
        directory_rule_count=directory_contract.rule_count,
        principle_count=principle_contract.principle_count,
        bootstrap_step_count=bootstrap_contract.step_count,
        contract_hashes=contract_hashes,
        report_hash=specification_hash(payload),
    )
