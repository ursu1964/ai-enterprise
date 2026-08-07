# P25 — R15 exact clause verification

Status: COMPLETE  
Scope: `1/r15.txt` — AI-Enterprise Manifest Compiler Specification  
Verification date: 2026-08-07

## Source reconciliation

| Source | Role | Decision |
|---|---|---|
| `1/r15.txt` | Authoritative product-platform R15 contract | Verified as Manifest Compiler Specification. |
| `docs/ir/R15-IR-01-workflow-process-engine.md` | Later implementation-ready IR contract | Preserved as Workflow and Process Engine architecture. It explicitly does not replace product-platform R15. |

R15 is closed against the executable Manifest Compiler contract. The workflow/process IR remains a separate constitutional architecture contract and is not a missing R15 compiler item.

## Clause-to-symbol verification

| R15 clause | Requirement | Repository evidence | Status |
|---|---|---|---|
| 1. Purpose | Transform a validated Manifest into deterministic semantic representation, not source code. | `r15_compile_manifest`; `R15CompilationResult`; `docs/r15-manifest-compiler-status.md` | IMPLEMENTED |
| 2. Compiler Mission | Input: validated Manifest, Registry, schemas. Output: knowledge graph, dependency graph, execution graph, compilation report. | `r15_compile_manifest(manifest, schema_path, registry_root)`; `R15KnowledgeGraph`; `R15DependencyGraph`; `R15ExecutionGraph`; `R15CompilationReport` | IMPLEMENTED |
| 3. Compiler Position | Compiler sits after validation and before knowledge graph/planner/generators; downstream originates from compiler output. | R14 validation is invoked before graph creation; API exposes compiler gateway only | IMPLEMENTED |
| 4. Compiler Principles | Deterministic, stateless, reproducible, explainable, incremental, traceable, technology-independent; no hidden memory/randomness. | Deterministic timestamp default; stable hashes; pure compile function; incremental impact report; tests comparing repeated output hashes | IMPLEMENTED |
| 5. Compilation Stages | Fixed nine-stage sequence; no stage skipped. | `COMPILATION_STAGES`; compilation report includes exact stages; tests assert stage list | IMPLEMENTED |
| 6. Stage 1 — Manifest Loading | Read Manifest, verify encoding/version/identifier, create immutable context. | JSON input contract; R14 schema validation; immutable Pydantic result models | IMPLEMENTED |
| 7. Stage 2 — Schema Validation | Required fields, types, cardinality, enumerations, mandatory sections, version compatibility; failures halt compilation. | `r14_validate_manifest`; invalid manifest test confirms no graphs are produced | IMPLEMENTED |
| 8. Stage 3 — Semantic Resolution | Resolve every business term to registry-backed semantics. | `_knowledge_nodes`; registry references on every node; missing-registry diagnostics | IMPLEMENTED |
| 9. Stage 4 — Registry Expansion | Enrich Manifest objects with registry metadata while Manifest remains concise. | `_load_registry`; `_node_metadata`; `registry_reference`; tests assert registry-backed nodes | IMPLEMENTED |
| 10. Stage 5 — Relationship Resolution | Establish typed edges between all objects. | `_knowledge_edges`; pass-enriched edges; tests assert `uses`, `references`, `owns`, `consumes`, `triggers`, `produces`, `implements` | IMPLEMENTED |
| 11. Stage 6 — Dependency Analysis | Determine explicit acyclic generation order; cycles are errors. | `_dependency_graph`; `_dependency_diagnostics`; circular dependency tests | IMPLEMENTED |
| 12. Stage 7 — Knowledge Graph Construction | Produce canonical project graph with required node/edge taxonomy. | `R15KnowledgeGraph`; `R15KnowledgeGraphNode`; `R15KnowledgeGraphEdge`; node/edge tests | IMPLEMENTED |
| 13. Knowledge Graph Requirements | Nodes have ID, type, registry reference, origin, version, metadata, relationships, status; edges have source, target, type, constraint, trace ID. | Pydantic node/edge models; tests assert registry reference, origin, resolved status, edge types | IMPLEMENTED |
| 14. Stage 8 — Execution Graph Construction | Produce implementation-order graph for planner. | `_execution_graph`; `R15ExecutionGraph`; tests assert canonical execution order | IMPLEMENTED |
| 15. Execution Graph Properties | Directed, acyclic, deterministic, versioned, serializable, incrementally updateable, node execution status. | `R15ExecutionGraph` fields; tests assert directed/acyclic/updateable and pending statuses | IMPLEMENTED |
| 16. Stage 9 — Compilation Report | Report includes manifest, registry, compiler version, timestamp, warnings, errors, counts, stats, summary; retained in history. | `R15CompilationReport`; `r15_persist_compilation_history`; history test | IMPLEMENTED |
| 17. Incremental Compilation | Manifest changes produce impact analysis, changed/reusable nodes, affected execution steps. | `R15IncrementalCompilationImpact`; `_incremental_impact`; incremental compilation tests | IMPLEMENTED |
| 18. Traceability | Generated artifact origin chains back through execution node, knowledge node, registry object, Manifest section. | Knowledge node `manifest_origin` and `registry_reference`; execution node `trace_node_ids`; edge trace identifiers | IMPLEMENTED |
| 19. Error Classification | Fatal, semantic, and advisory diagnostics are explicit. | `R15CompilationDiagnostic`; validation/semantic/dependency/advisory diagnostic functions; tests for fatal and advisory paths | IMPLEMENTED |
| 20. Compiler API | Canonical compile interface returns graphs, report, diagnostics, success status; compiler is gateway. | `/api/v1/r15/compile`; `/api/v1/r15/compiler-contract`; API test | IMPLEMENTED |
| 21. Compiler Invariants | Valid manifests produce valid semantic model; invalid manifests do not produce executable graphs; same inputs produce identical outputs; registry and traceability enforced. | deterministic compile tests; invalid/missing registry tests; graph hash tests | IMPLEMENTED |
| 22. Extension Model | Compilation passes enrich/validate/optimize as pure deterministic passes and do not mutate prior history. | `COMPILATION_PASSES`; `_run_compilation_passes`; `R15CompilationPassReport`; history append-only API | IMPLEMENTED |
| 23. Performance Requirements | Support incremental recompilation and stable semantics; parallel processing is allowed only where semantics are unchanged. | Incremental impact implementation; deterministic output hashing; no environment-dependent randomness | IMPLEMENTED |
| 24. Security Requirements | Reject malformed/untrusted manifests, validate external registry references, prevent embedded implementation/code, audit compilation, preserve artifact integrity. | R14 validation boundary; registry validation; `R14-INTENT-ONLY` rejection; append-only history; hash-bound reports | IMPLEMENTED |
| 25. Deliverable | Semantic core: deterministic compiler, canonical knowledge graph, execution graph, traceability, incremental recompilation, stable downstream contract. | Runtime, API, tests, status document, implementation package | IMPLEMENTED |

## Verification commands

Focused:

```bash
rtk bash -lc 'cd apps/api && .venv/bin/pytest -q tests/test_r15_manifest_compiler_runtime.py tests/test_traceability.py'
```

Full:

```bash
rtk make check
```

Release:

```bash
rtk make check-release
```

## Result

No R15 Manifest Compiler implementation gap remains. R15 does not generate source code; source generation is downstream of compiler graph outputs.
