# R16 Knowledge Graph Status

R16 is implemented as the formal semantic model layer consumed after R15 compilation.

Implemented:

- Canonical ontology contract with graph layers, node taxonomy, relationship model, and export formats.
- Registry-backed relationship semantics from `registry/Relationships`.
- R15 Knowledge Graph loading into an immutable, versioned R16 graph model.
- Validation for unknown node types, unknown relationships, missing traceability, ambiguous references, duplicate nodes, and orphan nodes.
- Validation for generated-artifact traceability hooks on every node.
- Semantic access filtering for node types, specific nodes, relationship types, graph versions, domains, metadata visibility, and query-scope style policies.
- Partition metadata for deterministic layer-based incremental loading.
- Governance impact propagation for policies, security requirements, and constraints.
- Semantic operations matching the R16 API contract:
  - load
  - query
  - find
  - traverse
  - diff
  - validate
  - export
- Deterministic JSON/property-graph/RDF/OWL/GraphQL/Neo4j-style export surfaces.
- Deterministic custom binary export envelope.
- Explicit high-scale graph backend readiness checks for in-process, filesystem, Neo4j, RDF, and custom backends.
- Filesystem graph backend publication physically materializes immutable graph versions.
- External graph backends fail closed until endpoint, database/repository, credentials reference, and partition strategy are configured.
- Production external graph backends additionally require deployment, connectivity, restore/export, and owner-approval evidence references.
- Production-readiness evidence tooling includes an explicit `r16_graph_backend` proof gate.
- External graph publication returns deterministic dry-run commands/refs rather than pretending to publish to unavailable infrastructure.
- API endpoints under `/api/v1/r16`.

Boundary:

- R16 defines and validates the semantic model. It does not generate software.
- Large-scale distributed graph clusters still require real infrastructure and credentials, but the application now blocks production readiness until those operational facts are referenced by evidence. No external graph backend is treated as production-ready from endpoint strings alone.
