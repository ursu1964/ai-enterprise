from pathlib import Path


def _repo_root() -> Path:
    for candidate in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
        if (candidate / "tools").is_dir():
            return candidate
    raise AssertionError("Could not locate repository root with tools directory")


ROOT = _repo_root()


def test_project_foundry_core_artifacts_exist() -> None:
    required = [
        ROOT / "docs/aeos/README.md",
        ROOT / "docs/aeos/project-foundry-core-v0.1.md",
        ROOT / "docs/aeos/quality-gates.md",
        ROOT / "specifications/aeos/project-intake.schema.yaml",
        ROOT / "specifications/aeos/requirements.schema.yaml",
        ROOT / "specifications/aeos/execution-plan.schema.yaml",
        ROOT / "specifications/aeos/agent-task.schema.yaml",
        ROOT / "specifications/aeos/review-report.schema.yaml",
        ROOT / "specifications/aeos/approval-matrix.yaml",
        ROOT / "templates/project-foundry/ROOT_AGENTS.md",
        ROOT / "templates/project-foundry/prompts/README.md",
        ROOT / "templates/project-foundry/REPOSITORY_TEMPLATE.md",
    ]

    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]

    assert missing == []


def test_aeos_master_spec_defines_platform_and_instance_boundary() -> None:
    text = (ROOT / "docs/aeos/README.md").read_text(encoding="utf-8")

    assert "AEOS is the Autonomous Enterprise Operating System" in text
    assert "AI Enterprise is the first enterprise instance built on AEOS" in text
    assert "Five Worlds" in text
    assert "Dependency Graph" in text
    assert "Canonical Entity Contract" in text


def test_project_foundry_schemas_define_execution_control_contracts() -> None:
    intake = (ROOT / "specifications/aeos/project-intake.schema.yaml").read_text(encoding="utf-8")
    task = (ROOT / "specifications/aeos/agent-task.schema.yaml").read_text(encoding="utf-8")
    approval = (ROOT / "specifications/aeos/approval-matrix.yaml").read_text(encoding="utf-8")

    assert "authority:" in intake
    assert "acceptance_criteria:" in task
    assert "files_allowed:" in task
    assert "production_deployment" in approval
    assert "creator_may_approve: false" in approval
