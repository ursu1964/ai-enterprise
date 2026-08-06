# Traceability v0.1

R3 requires every canonical object and relationship to be traceable to registered source evidence.

The foundation implementation stores traceability in:

- source object records for uploaded manifests;
- canonical `source_refs` and `evidence_refs`;
- normalized object source links;
- normalized relationship source links;
- normalized evidence rows;
- immutable event log payloads;
- project snapshots that bind object and relationship versions to a model hash.

R3 derivation types are:

- `direct`
- `normalized`
- `manually_added`

AI-specific derivation types are reserved for later releases and must not be used to silently approve
project knowledge.
