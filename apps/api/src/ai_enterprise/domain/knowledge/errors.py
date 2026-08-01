class KnowledgeDomainError(ValueError):
    """A fail-closed organizational knowledge invariant was violated."""


class PromotionDenied(KnowledgeDomainError):
    pass


class InvalidEvidenceLocator(KnowledgeDomainError):
    pass
