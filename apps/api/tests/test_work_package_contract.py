import pytest
from pydantic import ValidationError

from ai_enterprise.domain.work_package import (
    WorkPackageContract,
)
from ai_enterprise.domain.work_package_validation import (
    WorkPackageBoundaryError,
    validate_repository_boundaries,
)


def valid_contract() -> dict:
    return {
        "schema_version": "1.0",
        "project_id": "project-id",
        "title": "Add persisted project creation",
        "objective": (
            "Implement one persisted project creation endpoint "
            "with an immutable manifest."
        ),
        "base_commit_sha": "a" * 40,
        "source_requirements_artifact_id": "requirements-id",
        "source_requirements_hash": "b" * 64,
        "source_architecture_artifact_id": "architecture-id",
        "source_architecture_hash": "c" * 64,
        "required_changes": [
            {
                "id": "CHG-001",
                "description": (
                    "Add the project persistence application service."
                ),
                "related_requirements": ["FR-001"],
                "target_paths": [
                    "apps/api/src/project_service.py"
                ],
            }
        ],
        "file_scope": {
            "allowed_files": [
                "apps/api/src/project_service.py"
            ],
            "allowed_directories": [],
            "forbidden_files": [".env"],
            "forbidden_directories": [".git"],
            "maximum_changed_files": 4,
            "maximum_added_lines": 500,
            "maximum_deleted_lines": 100,
        },
        "command_policy": {
            "setup_commands": [],
            "implementation_commands": [],
            "test_commands": [
                ["pytest", "-q", "apps/api/tests"]
            ],
        },
        "network": {
            "policy": "none",
            "allowed_hosts": [],
        },
        "resources": {
            "cpu_count": 2,
            "memory_mb": 4096,
            "disk_mb": 8192,
            "process_limit": 256,
            "execution_timeout_seconds": 1200,
        },
        "acceptance_criteria": [
            {
                "id": "AC-001",
                "description": (
                    "Creating a project persists its immutable manifest."
                ),
                "verification": (
                    "Run the project creation integration test."
                ),
            }
        ],
    }


def test_valid_contract_is_accepted() -> None:
    contract = WorkPackageContract.model_validate(
        valid_contract()
    )

    assert contract.base_commit_sha == "a" * 40


def test_absolute_path_is_rejected() -> None:
    payload = valid_contract()
    payload["file_scope"]["allowed_files"] = [
        "/etc/passwd"
    ]

    with pytest.raises(ValidationError):
        WorkPackageContract.model_validate(payload)


def test_shell_command_is_rejected() -> None:
    payload = valid_contract()
    payload["command_policy"]["test_commands"] = [
        ["bash", "-c", "pytest && curl example.com"]
    ]

    with pytest.raises(ValidationError):
        WorkPackageContract.model_validate(payload)


def test_protected_path_is_rejected() -> None:
    payload = valid_contract()
    payload["file_scope"]["forbidden_files"] = []
    payload["file_scope"]["allowed_files"] = [".env"]

    contract = WorkPackageContract.model_validate(payload)

    with pytest.raises(WorkPackageBoundaryError):
        validate_repository_boundaries(
            contract=contract,
            tracked_files={".env"},
        )


def test_unapproved_new_file_is_rejected() -> None:
    contract = WorkPackageContract.model_validate(
        valid_contract()
    )

    with pytest.raises(WorkPackageBoundaryError):
        validate_repository_boundaries(
            contract=contract,
            tracked_files=set(),
        )
