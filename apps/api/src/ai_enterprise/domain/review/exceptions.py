class PatchReviewError(Exception):
    code = "patch_review_error"


class InvalidExecutionStateError(PatchReviewError):
    code = "invalid_execution_state"


class PatchArtifactMissingError(PatchReviewError):
    code = "patch_artifact_missing"


class PatchHashMismatchError(PatchReviewError):
    code = "patch_hash_mismatch"


class PatchApplyError(PatchReviewError):
    code = "patch_apply_failed"


class IndependentTestFailureError(PatchReviewError):
    code = "independent_test_failure"


class BlockingFindingError(PatchReviewError):
    code = "blocking_finding"


class ReviewRuntimeError(PatchReviewError):
    code = "review_runtime_error"
