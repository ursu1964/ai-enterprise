# Clarification engine v0.1

The clarification engine deterministically transforms AEPM validation findings and governed AI
interpretation proposals into a hash-bound report with exactly five sections: critical blockers,
important ambiguities, unverified assumptions, recommended improvements, and optional
enhancements. Empty sections remain explicit, and the engine does not invent optional work.

Each question has a content-derived stable identifier, authority status, rationale, exact upstream
references, target object identifiers, and optional AI confidence. The report binds the validation
report hash and, when present, the interpretation batch hash.

Human answers are stored in a separate immutable, hash-bound batch tied to both the report and the
exact base AEIR hash. Corrections may change only the name or description of an object explicitly
in scope for that question. They cannot change identities, types, relationships, or arbitrary JSON
paths. Applying a valid batch creates a new AEIR value with human-clarification provenance; it does
not mutate the previous model or persist anything silently.
