from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class ResourceLimits(BaseModel):
    cpu_count: float = Field(default=2.0, gt=0, le=16)
    memory_mb: int = Field(default=4096, ge=512, le=32768)
    disk_mb: int = Field(default=8192, ge=1024, le=65536)
    process_limit: int = Field(default=256, ge=32, le=2048)
    execution_timeout_seconds: int = Field(
        default=1800,
        ge=30,
        le=7200,
    )


class NetworkRules(BaseModel):
    policy: Literal["none", "loopback_only", "allowlist"] = "none"
    allowed_hosts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_allowlist(self) -> NetworkRules:
        if self.policy != "allowlist" and self.allowed_hosts:
            raise ValueError(
                "allowed_hosts may only be used with allowlist policy"
            )

        if self.policy == "allowlist" and not self.allowed_hosts:
            raise ValueError(
                "allowlist policy requires at least one allowed host"
            )

        return self


class FileScope(BaseModel):
    allowed_files: list[str] = Field(min_length=1)
    allowed_directories: list[str] = Field(default_factory=list)
    forbidden_files: list[str] = Field(default_factory=list)
    forbidden_directories: list[str] = Field(default_factory=list)
    maximum_changed_files: int = Field(default=12, ge=1, le=100)
    maximum_added_lines: int = Field(default=1000, ge=1, le=10000)
    maximum_deleted_lines: int = Field(default=500, ge=0, le=10000)

    @field_validator(
        "allowed_files",
        "allowed_directories",
        "forbidden_files",
        "forbidden_directories",
    )
    @classmethod
    def validate_paths(cls, paths: list[str]) -> list[str]:
        normalized: list[str] = []

        for raw_path in paths:
            path = raw_path.strip()

            if not path:
                raise ValueError("Empty paths are not allowed")

            pure_path = PurePosixPath(path)

            if pure_path.is_absolute():
                raise ValueError(
                    f"Absolute repository path is forbidden: {path}"
                )

            if ".." in pure_path.parts:
                raise ValueError(
                    f"Parent traversal is forbidden: {path}"
                )

            normalized.append(str(pure_path))

        if len(normalized) != len(set(normalized)):
            raise ValueError("Duplicate paths are not allowed")

        return normalized

    @model_validator(mode="after")
    def prevent_scope_conflicts(self) -> FileScope:
        overlap = set(self.allowed_files) & set(self.forbidden_files)

        if overlap:
            raise ValueError(
                f"Paths cannot be both allowed and forbidden: {overlap}"
            )

        return self


class CommandPolicy(BaseModel):
    setup_commands: list[list[str]] = Field(default_factory=list)
    implementation_commands: list[list[str]] = Field(default_factory=list)
    test_commands: list[list[str]] = Field(min_length=1)
    forbidden_executables: list[str] = Field(
        default_factory=lambda: [
            "sudo",
            "su",
            "ssh",
            "scp",
            "mount",
            "umount",
            "systemctl",
            "service",
            "reboot",
            "shutdown",
            "docker",
            "podman",
            "kubectl",
        ]
    )

    @field_validator(
        "setup_commands",
        "implementation_commands",
        "test_commands",
    )
    @classmethod
    def validate_commands(
        cls,
        commands: list[list[str]],
    ) -> list[list[str]]:
        for command in commands:
            if not command:
                raise ValueError("Empty command arrays are forbidden")

            executable = command[0].strip()

            if not executable:
                raise ValueError("Command executable is missing")

            if executable in {"sh", "bash", "zsh"}:
                raise ValueError(
                    "Shell interpreter commands are forbidden; "
                    "commands must use argument arrays"
                )

        return commands


class AcceptanceCriterion(BaseModel):
    id: str = Field(pattern=r"^AC-[0-9]{3}$")
    description: str = Field(min_length=10, max_length=2000)
    verification: str = Field(min_length=5, max_length=2000)


class RequiredChange(BaseModel):
    id: str = Field(pattern=r"^CHG-[0-9]{3}$")
    description: str = Field(min_length=10, max_length=2000)
    related_requirements: list[str] = Field(min_length=1)
    target_paths: list[str] = Field(min_length=1)


class WorkPackageContract(BaseModel):
    schema_version: Literal["1.0"] = "1.0"

    project_id: str
    title: str = Field(min_length=5, max_length=250)
    objective: str = Field(min_length=20, max_length=5000)

    base_commit_sha: str
    source_requirements_artifact_id: str
    source_requirements_hash: str
    source_architecture_artifact_id: str
    source_architecture_hash: str

    required_changes: list[RequiredChange] = Field(
        min_length=1,
        max_length=12,
    )

    file_scope: FileScope
    command_policy: CommandPolicy
    network: NetworkRules = Field(default_factory=NetworkRules)
    resources: ResourceLimits = Field(default_factory=ResourceLimits)

    acceptance_criteria: list[AcceptanceCriterion] = Field(
        min_length=1,
        max_length=30,
    )

    expected_artifacts: list[str] = Field(
        default_factory=lambda: [
            "implementation.patch",
            "test-report.json",
            "execution-log.jsonl",
            "changed-files.json",
        ]
    )

    forbidden_actions: list[str] = Field(
        default_factory=lambda: [
            "Modify files outside the approved repository checkout",
            "Access the Docker socket",
            "Use privileged container execution",
            "Mount host system directories",
            "Change host services",
            "Read host credentials",
            "Push commits or tags",
            "Contact unapproved network destinations",
        ]
    )

    @field_validator("base_commit_sha")
    @classmethod
    def validate_commit_sha(cls, value: str) -> str:
        normalized = value.lower().strip()

        if not COMMIT_SHA_PATTERN.fullmatch(normalized):
            raise ValueError(
                "base_commit_sha must be a full 40-character Git SHA"
            )

        return normalized

    @field_validator(
        "source_requirements_hash",
        "source_architecture_hash",
    )
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        normalized = value.lower().strip()

        if not re.fullmatch(r"[0-9a-f]{64}", normalized):
            raise ValueError(
                "Artifact hashes must be 64-character SHA-256 values"
            )

        return normalized

    @model_validator(mode="after")
    def validate_criterion_ids(self) -> WorkPackageContract:
        criterion_ids = [
            criterion.id for criterion in self.acceptance_criteria
        ]

        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError(
                "Acceptance criterion IDs must be unique"
            )

        change_ids = [change.id for change in self.required_changes]

        if len(change_ids) != len(set(change_ids)):
            raise ValueError("Required-change IDs must be unique")

        return self
