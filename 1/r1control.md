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
| 3 — Deterministic validation engine | **BLOCKED** | Step 2 complete |
| 4 — AI interpretation layer | **BLOCKED** | Step 3 complete |
| 5 — Knowledge storage | **BLOCKED** | Step 4 complete |
| 6 — Question engine | **BLOCKED** | Step 5 complete |
| 7 — Five artifact compilers | **BLOCKED** | Step 6 complete |
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
