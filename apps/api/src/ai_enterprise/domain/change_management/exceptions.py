class GovernedChangeError(Exception):
    code = "GOVERNED_CHANGE_ERROR"


class InvalidChangeTransition(GovernedChangeError):
    code = "INVALID_CHANGE_TRANSITION"


class ChangeEvidenceRequired(GovernedChangeError):
    code = "CHANGE_EVIDENCE_REQUIRED"


class UnknownImpactBlocksDecision(GovernedChangeError):
    code = "UNKNOWN_IMPACT_BLOCKS_DECISION"


class ChangeSelfApprovalForbidden(GovernedChangeError):
    code = "CHANGE_SELF_APPROVAL_FORBIDDEN"


class IndependentAssessmentRequired(GovernedChangeError):
    code = "INDEPENDENT_ASSESSMENT_REQUIRED"


class ChangeRecordImmutable(GovernedChangeError):
    code = "CHANGE_RECORD_IMMUTABLE"


class ActivationNotSupported(GovernedChangeError):
    code = "ACTIVATION_NOT_SUPPORTED"


class ChangeObservationRequired(GovernedChangeError):
    code = "CHANGE_OBSERVATION_REQUIRED"


class ChangeRiskUnderstated(GovernedChangeError):
    code = "CHANGE_RISK_UNDERSTATED"


class SelfModificationForbidden(GovernedChangeError):
    code = "SELF_MODIFICATION_FORBIDDEN"
