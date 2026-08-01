class IntegrationError(Exception):
    code = "INTEGRATION_ERROR"


class PatchNotEligibleError(IntegrationError):
    code = "PATCH_NOT_ELIGIBLE"


class HumanApprovalRequiredError(IntegrationError):
    code = "HUMAN_APPROVAL_REQUIRED"


class IntegrationApprovalNotActiveError(IntegrationError):
    code = "INTEGRATION_APPROVAL_NOT_ACTIVE"


class IntegrationBindingMismatchError(IntegrationError):
    code = "INTEGRATION_BINDING_MISMATCH"


class TargetBranchNotAllowedError(IntegrationError):
    code = "TARGET_BRANCH_NOT_ALLOWED"


class RevisionLineageError(IntegrationError):
    code = "INVALID_REVISION_LINEAGE"
