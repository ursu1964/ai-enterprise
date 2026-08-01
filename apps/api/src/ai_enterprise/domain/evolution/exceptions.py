class EvolutionError(Exception):
    code = "EVOLUTION_ERROR"


class EvolutionPrerequisiteMissing(EvolutionError):
    code = "EVOLUTION_PREREQUISITE_MISSING"


class EvolutionAuthorityViolation(EvolutionError):
    code = "EVOLUTION_AUTHORITY_VIOLATION"


class EvolutionSafetyViolation(EvolutionError):
    code = "EVOLUTION_SAFETY_VIOLATION"


class EvolutionCompatibilityViolation(EvolutionError):
    code = "EVOLUTION_COMPATIBILITY_VIOLATION"


class ConstitutionalQuorumMissing(EvolutionError):
    code = "CONSTITUTIONAL_QUORUM_MISSING"
