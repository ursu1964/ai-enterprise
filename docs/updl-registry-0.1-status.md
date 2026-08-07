# UPDL Registry v0.1 Status

Status: implemented as an executable bootstrap kernel.

Implemented scope:

- Canonical object envelope with API version, metadata, spec, governance,
  provenance, epistemics, lifecycle, and validation status.
- Canonical identifier and namespace validation.
- Namespace registration with parent validation, cycle detection, active-state
  enforcement, and reserved-root protection.
- System-managed revision, timestamps, actor attribution, and content hashes.
- TypeDefinition-backed object creation.
- Deterministic `ValidationResult` output for type-schema validation, including
  machine-readable errors, warnings, property paths, schema version, validation
  timestamp, and validator version.
- Required, enum, primitive, nullable, list, map, and reference property
  validation.
- TypeDefinition `additional_properties` policy with `forbid`, `warn`, and
  `allow` behavior.
- Type-safe reference resolution with structured resolution status.
- Object revisions with optimistic concurrency through `expected_revision`.
- Direct lifecycle/system-field mutation protection on ordinary updates.
- RelationshipType registration with source/target kind validation.
- Type-safe relationship creation that records canonical relationship identity
  on the source object.
- Relationship changes create a new source-object revision and ordinary updates
  preserve existing relationships.
- StateMachineDefinition registration with applies-to-kind validation, unique
  state validation, initial-state validation, transition endpoint validation,
  terminal-state protection, and version metadata.
- Non-mutating lifecycle transition evaluation with structured denial reasons.
- Governed lifecycle transition execution that requires a declared transition,
  matching source state, optional action binding, expected revision, and creates
  a new object revision with the target lifecycle state.
- Policy evaluation with deterministic effect precedence:
  `DENY > ESCALATE > REQUIRE > WARN > ALLOW`.
- Policy obligation accumulation across matched policies.

Intentionally deferred:

- Persistent storage.
- Snapshot materialization.
- Independent relationship-object revisioning and relationship removal.
- Transition guards, required evidence, transition-specific authorization,
  entry/exit conditions, postconditions, side effects, audit events, and
  idempotency.
- Full invariant language.
- Full command/event store.
- Authorization adapters.
- Cross-registry reference resolution.

Verification:

```bash
cd apps/api
.venv/bin/pytest -q tests/test_updl_registry_kernel.py
.venv/bin/ruff check src/ai_enterprise/domain/updl_registry.py tests/test_updl_registry_kernel.py
.venv/bin/mypy src/ai_enterprise/domain/updl_registry.py
```
