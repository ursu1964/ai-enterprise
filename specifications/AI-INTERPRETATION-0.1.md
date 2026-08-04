# Governed AI interpretation v0.1

The interpretation layer uses the existing governed model executor only for semantic work that
ordinary deterministic validation cannot perform. Its structured output contract permits six
tasks: field extraction, ambiguity detection, clarification-question proposals, statement
classification, probable contradiction detection, and candidate requirement drafting.

Every item must contain a stable identifier, task, content, rationale, confidence, source
references, and an initial authority status. Model output is schema validated before use and then
bound to both its source and normalized model output by SHA-256 identities.

The model may emit only `proposed`, `inferred`, or `unverified`. It cannot emit `approved` or
`rejected`; those states require a separate `InterpretationReviewDecision` containing a reviewer
identity and rationale. Interpretation batches remain proposals and are not merged automatically
into AEIR canonical objects.

Task-specific constraints fail closed. Extracted fields require a field name, classifications
require one of fact, assumption, or recommendation, and probable contradictions require at least
two source references.
