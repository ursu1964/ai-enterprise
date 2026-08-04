# AEPM v0.1

AEPM v0.1 is the deliberately narrow client-project manifest for the first
manifest-to-blueprint release. Its normative machine-readable contract is
[`aepm/AEPM-0.1.schema.json`](aepm/AEPM-0.1.schema.json).

The manifest covers only project intent, business outcomes, stakeholders, capabilities, core
processes, business rules, data entities, integrations, quality requirements, constraints, and
preferred technology targets. It is not an enterprise ontology, technical design, execution plan,
or authorization policy.

Rules:

- JSON is the canonical wire format for v0.1.
- Unknown fields are rejected so later additions require a version change.
- Stable prefixed identifiers allow later AEIR objects and artifacts to retain traceability.
- Technology targets express preferences, not approved architecture decisions.
- A valid manifest is intake evidence, not approved truth.

See [`examples/sample-project/aepm-0.1.json`](../examples/sample-project/aepm-0.1.json) for a
complete example.
