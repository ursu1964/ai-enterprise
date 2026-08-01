class IntegrationGitError(RuntimeError):
    """Base failure at the controlled Git boundary."""


class SnapshotVerificationError(IntegrationGitError):
    pass


class PatchVerificationError(IntegrationGitError):
    pass


class WorkspaceVerificationError(IntegrationGitError):
    pass


class ApprovedTestError(IntegrationGitError):
    def __init__(self, code: str, *, evidence: tuple[object, ...] = ()) -> None:
        super().__init__(code)
        self.code = code
        self.evidence = evidence


class CommitVerificationError(IntegrationGitError):
    pass


class TargetBranchAdvancedError(IntegrationGitError):
    pass


class RemoteVerificationError(IntegrationGitError):
    pass
