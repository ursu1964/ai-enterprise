from pathlib import PurePosixPath

from ai_enterprise.domain.work_package import WorkPackageContract

PROTECTED_PATHS = {
    ".env",
    ".git",
    ".git/config",
    ".git/hooks",
    "/etc",
    "/proc",
    "/sys",
    "/dev",
    "/run",
    "/var/run/docker.sock",
}


class WorkPackageBoundaryError(ValueError):
    pass


def validate_repository_boundaries(
    *,
    contract: WorkPackageContract,
    tracked_files: set[str],
) -> None:
    for path in contract.file_scope.allowed_files:
        _reject_protected_path(path)

        # Existing files must be tracked. New files are allowed only when
        # their parent appears in allowed_directories.
        if path not in tracked_files:
            parent = str(PurePosixPath(path).parent)

            if parent not in contract.file_scope.allowed_directories:
                raise WorkPackageBoundaryError(
                    f"New file is outside allowed directories: {path}"
                )

    for directory in contract.file_scope.allowed_directories:
        _reject_protected_path(directory)

    executables = {
        command[0]
        for command_group in (
            contract.command_policy.setup_commands,
            contract.command_policy.implementation_commands,
            contract.command_policy.test_commands,
        )
        for command in command_group
    }

    forbidden = set(
        contract.command_policy.forbidden_executables
    )

    violation = executables & forbidden

    if violation:
        raise WorkPackageBoundaryError(
            f"Forbidden executables requested: {sorted(violation)}"
        )


def _reject_protected_path(path: str) -> None:
    normalized = str(PurePosixPath(path))

    for protected in PROTECTED_PATHS:
        if normalized == protected:
            raise WorkPackageBoundaryError(
                f"Protected path requested: {path}"
            )

        protected_prefix = protected.rstrip("/") + "/"

        if normalized.startswith(protected_prefix):
            raise WorkPackageBoundaryError(
                f"Protected path requested: {path}"
            )
