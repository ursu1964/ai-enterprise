# UPDL Registry v0.1 Status

Status: implemented as an executable bootstrap kernel.

Implemented scope:

- Canonical object envelope with API version, metadata, spec, governance,
  provenance, epistemics, lifecycle, and validation status.
- Canonical identifier and namespace validation.
- System-managed revision, timestamps, actor attribution, and content hashes.
- TypeDefinition-backed object creation.
- Required, enum, primitive, nullable, list, map, and reference property
  validation.
- Type-safe reference resolution with structured resolution status.
- Object revisions with optimistic concurrency through `expected_revision`.
- Direct lifecycle/system-field mutation protection on ordinary updates.
- Policy evaluation with deterministic effect precedence:
  `DENY > ESCALATE > REQUIRE > WARN > ALLOW`.
- Policy obligation accumulation across matched policies.

Intentionally deferred:

- Persistent storage.
- Snapshot materialization.
- Relationship instance revisioning.
- Full invariant language.
- Full command/event store.
- Authorization adapters.
- Cross-registry reference resolution.

Verification:

```bash
cd apps/api
.venv/bin/pytest -q tests/test_updl_registry_kernel.py
.venv/bin/mypy src/ai_enterprise/domain/updl_registry.py
```
