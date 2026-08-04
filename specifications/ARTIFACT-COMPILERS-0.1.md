# AEIR artifact compilers v0.1

The first compiler bundle produces exactly five artifacts from a validated AEIR model: Executive
Project Brief, Software Requirements Specification, Domain and Data Model, Solution Architecture
Blueprint, and Delivery Backlog with Acceptance Criteria.

Compilation is deterministic and does not call an LLM or read original client prose. Every output
uses an immutable structured section contract, binds the exact source AEIR hash, and validates both
its content hash and artifact-envelope hash. The bundle validates the exact five artifact types and
canonical order and has its own SHA-256 identity.

Markdown rendering is a pure projection of structured sections. Empty source categories are stated
as absent rather than invented. Section-level source-object references are deliberately deferred to
the dedicated traceability contract in Step 8.
