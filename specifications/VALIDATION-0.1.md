# AEPM deterministic validation v0.1

The v0.1 validation engine evaluates raw AEPM input before AI interpretation. It emits immutable,
canonically ordered findings with stable codes, JSON-style paths, affected object identifiers,
severity, and a SHA-256 report identity.

| Code | Check |
| --- | --- |
| AEPM-VAL-000 | AEPM structural/schema violation |
| AEPM-VAL-001 | Missing project intent |
| AEPM-VAL-002 | Outcome without measurable indicator |
| AEPM-VAL-003 | Capability without a known owner |
| AEPM-VAL-004 | Process without trigger or output |
| AEPM-VAL-005 | Requirement without acceptance criteria |
| AEPM-VAL-006 | Entity without a known owner |
| AEPM-VAL-007 | Integration without security rules |
| AEPM-VAL-008 | Deterministically opposing mandatory statements |
| AEPM-VAL-009 | Unresolved assumption marker |
| AEPM-VAL-010 | Duplicate normalized concept |
| AEPM-VAL-011 | Object orphaned from its declared owner |

The engine performs no probabilistic interpretation. Contradiction detection is deliberately
limited to equivalent normalized statements with explicit opposing mandatory polarity. Broader
probable contradiction analysis belongs to the governed AI interpretation step.
