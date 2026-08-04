# r1.txt implementation control

Status date: 2026-08-04

## Execution discipline

1. Implement `r1.txt` in numbered order.
2. Do not begin a later step while the active step has a failing test, unresolved contract defect,
   or incomplete evidence.
3. Preserve the existing application and reuse proven modules where their contracts match.
4. Keep AI-proposed information explicitly distinct from approved canonical information.
5. Every completed step requires an executable contract, focused tests, the full applicable gate,
   an updated code graph, and a clean commit.

## Step ledger

| Step | State | Exit evidence |
| --- | --- | --- |
| 1 — AEPM v0.1 | **COMPLETE** | Narrow JSON manifest contract, example, documentation, and tests |
| 2 — Canonical project model / AEIR | **COMPLETE** | Deterministic AEPM-to-AEIR compiler and integrity contract |
| 3 — Deterministic validation engine | **COMPLETE** | Stable classified report and hash contract |
| 4 — AI interpretation layer | **COMPLETE** | Governed structured proposals and review boundary |
| 5 — Knowledge storage | **COMPLETE** | Versioned PostgreSQL AEIR and immutable event storage |
| 6 — Question engine | **COMPLETE** | Hash-bound clarification and correction workflow |
| 7 — Five artifact compilers | **COMPLETE** | Five deterministic AEIR-bound artifacts |
| 8 — Traceability | **BLOCKED** | Step 7 complete |

## Step 1 acceptance

- [x] Contract covers only the eleven categories authorized by `r1.txt`.
- [x] JSON is the canonical v0.1 wire format.
- [x] Unknown fields are rejected.
- [x] Stable identifiers exist for objects that later require traceability.
- [x] A complete sample project validates through the executable Pydantic contract.
- [x] A normative Draft 2020-12 JSON Schema is published.
- [x] Full repository verification passes.
- [x] Code graph is updated and the implementation is committed cleanly.

## Execution log

- 2026-08-04: Compared `r1.txt` with the current Project Foundry intake. The existing YAML file is
  a broad field outline rather than a normative AEPM contract and includes later-phase delivery and
  authority concerns. Started a separate, deliberately narrow AEPM v0.1 contract rather than
  silently changing the existing Foundry format.
- 2026-08-04: AEPM v0.1 focused tests passed, followed by Ruff, MyPy over 413 source files,
  tooling invariants, all 826 tests, and a refreshed code graph. Step 1 is complete; Step 2 may begin
  only from this committed contract.
- 2026-08-04: Started Step 2 with a generic, immutable AEIR object contract supporting every object
  kind named by `r1.txt`. The deterministic compiler maps only facts present in AEPM, retains exact
  source references and the manifest hash, marks client claims `unverified`, and keeps preferred
  technologies `proposed`. It deliberately does not invent Risk or Artifact objects.

## Step 2 acceptance

- [x] AEIR supports Project, Intent, Outcome, Stakeholder, Capability, Process, Requirement, Rule,
  Entity, Integration, Constraint, Risk, Decision, Artifact, and Relationship types.
- [x] Every canonical object has id, type, name, description, status, source, confidence, version,
  and relationship references.
- [x] Identical AEPM input compiles to an identical canonical model and SHA-256 identity.
- [x] Direct manifest facts remain unverified; technology preferences remain proposed.
- [x] Ownership and containment relationships have explicit endpoints and back-references.
- [x] Duplicate identities, missing endpoints, inconsistent references, and hash tampering fail
  closed.
- [x] Full repository verification passes.
- [x] Code graph is updated and the implementation is committed cleanly.

## Step 2 completion evidence

- 2026-08-04: Step 2 focused tests passed, followed by Ruff, MyPy over 414 source files,
  tooling invariants, all 830 tests, and a refreshed code graph. Step 2 is complete; deterministic
  validation is now the only authorized next step.

## Step 3 acceptance

- [x] Raw AEPM input is checked without an LLM or probabilistic interpretation.
- [x] Findings have stable codes, severity, paths, affected identifiers, and canonical ordering.
- [x] Missing intent, indicators, ownership, process boundaries, acceptance criteria, and
  integration security rules are classified explicitly.
- [x] Deterministic contradictions, unresolved assumptions, duplicates, and orphaned objects are
  classified explicitly.
- [x] Structural AEPM violations are retained as validation findings rather than escaping as
  exceptions.
- [x] Identical input produces an identical validation report and SHA-256 identity.
- [x] Full repository verification passes.
- [x] Code graph is updated and the implementation is committed cleanly.

## Step 3 completion evidence

- 2026-08-04: Step 3 focused tests passed, followed by Ruff, MyPy over 415 source files,
  tooling invariants, all 834 tests, and a refreshed code graph. Step 3 is complete; governed AI
  interpretation is now the only authorized next step.

## Step 4 acceptance

- [x] AI use is limited to extraction, ambiguity analysis, question proposals, classification,
  probable contradiction detection, and candidate requirement drafting.
- [x] Model output is validated against a strict structured schema before use.
- [x] Every interpretation retains source references, rationale, confidence, and authority status.
- [x] The model may emit proposed, inferred, or unverified information only.
- [x] Approval and rejection require a separate human review decision with reviewer evidence.
- [x] Interpretation output remains separate from canonical AEIR objects.
- [x] Identical normalized output produces an identical tamper-evident batch.
- [x] Full repository verification passes.
- [x] Code graph is updated and the implementation is committed cleanly.

## Step 4 completion evidence

- 2026-08-04: Step 4 focused tests passed alongside the existing governed model runtime tests,
  followed by Ruff, MyPy over 416 source files, tooling invariants, all 841 tests, and a refreshed
  code graph. Step 4 is complete; knowledge storage is now the only authorized next step.

## Step 5 acceptance

- [x] PostgreSQL stores immutable canonical model versions and hashes.
- [x] Canonical objects and relationships have dedicated relational tables and foreign keys.
- [x] Extensible model, object, relationship, event, and source metadata uses JSONB.
- [x] Uploaded source content remains in object storage with immutable PostgreSQL metadata.
- [x] Model changes create hash-linked events in the same persistence unit.
- [x] PostgreSQL rejects event updates and deletes through an append-only trigger.
- [x] Version allocation is serialized per project and protected by uniqueness constraints.
- [x] No graph database is introduced.
- [x] Full repository verification passes.
- [x] Code graph is updated and the implementation is committed cleanly.

## Step 5 completion evidence

- 2026-08-04: Step 5 focused persistence and object-storage tests passed; the new migration was
  verified as the single reversible head and applied successfully to laptop PostgreSQL. Ruff,
  MyPy over 418 source files, tooling invariants, all 846 tests, and a refreshed code graph passed.
  Step 5 is complete; the clarification question engine is now the only authorized next step.

## Step 6 acceptance

- [x] Reports always contain Critical blockers, Important ambiguities, Unverified assumptions,
  Recommended improvements, and Optional enhancements sections.
- [x] Deterministic findings and governed AI proposals retain exact upstream provenance.
- [x] Question identifiers, section ordering, and report hashes are stable.
- [x] The engine does not invent optional enhancements when no explicit source exists.
- [x] Human answers are separately hash-bound to the report and exact base AEIR model.
- [x] Unknown, duplicate, stale, tampered, and out-of-scope answers fail closed.
- [x] Accepted corrections create a new AEIR value and preserve the previous model unchanged.
- [x] Corrections cannot change object identity, type, relationships, or arbitrary fields.
- [x] Full repository verification passes.
- [x] Code graph is updated and the implementation is committed cleanly.

## Step 6 completion evidence

- 2026-08-04: Step 6 focused clarification, interpretation, validation, AEIR, and storage tests
  passed, followed by Ruff, MyPy over 419 source files, tooling invariants, all 851 tests, and a
  refreshed code graph. Step 6 is complete; the five artifact compilers are now the only authorized
  next step.

## Step 7 acceptance

- [x] The bundle contains exactly the five outputs authorized by `r1.txt`.
- [x] Compilers consume only validated AEIR input and do not call an LLM or original client prose.
- [x] Executive, requirements, domain/data, architecture, and delivery concerns are projected into
  explicit structured sections.
- [x] Empty AEIR categories are reported as absent rather than populated with invented content.
- [x] Every artifact binds the exact AEIR model hash and validates content and envelope hashes.
- [x] The bundle validates exact artifact types, canonical order, source consistency, and identity.
- [x] Markdown rendering is deterministic and derived only from the structured artifact.
- [x] Full repository verification passes.
- [x] Code graph is updated and the implementation is committed cleanly.

## Step 7 completion evidence

- 2026-08-04: Step 7 focused compiler, AEIR, and clarification tests passed, followed by Ruff,
  MyPy over 420 source files, tooling invariants, all 856 tests, and a refreshed code graph. Step 7
  is complete; formal section-level traceability is now the only authorized next step.
