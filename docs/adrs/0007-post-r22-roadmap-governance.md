# ADR-0007: Post-R22 Roadmap Governance

- Status: accepted
- Date: 2026-08-07
- Owners: enterprise-architecture
- Supersedes: none
- Exception expiry: none

## Context

The R2–R22 architecture and implementation sequence is complete and protected by the roadmap
sequence gate. Starting a new roadmap module by simply creating `r23.txt` would weaken the baseline
because it would skip the decision that proves the next module is genuinely missing, non-duplicate,
and compatible with the existing architecture.

Post-R22 work must distinguish three different paths:

1. production-readiness evidence and deployment operations;
2. implementation hardening inside existing R2–R22 boundaries;
3. a new roadmap module such as R23.

Only the third path changes the architecture roadmap.

## Decision

Post-R22 roadmap expansion requires an accepted ADR before any new R-series source specification is
introduced.

The ADR must:

- name the proposed roadmap module;
- explain why existing R2–R22, BK/IR, or production-readiness scopes do not already cover it;
- identify affected existing modules and extension seams;
- define whether the work is a new R-series module, an implementation phase, an operational plan, or
  an ADR-only governance change;
- state migration, API, persistence, security, observability, and testing impact;
- define acceptance evidence;
- explicitly authorize the creation of any new `1/rNN.txt` or `docs/ir/RNN-*` file.

Until such an ADR exists, R23 is not authorized.

## Alternatives considered

Creating R23 immediately was rejected because the repository already contains the full R2–R22
baseline, R-INDEX, R-AUDIT-01, R-AUDIT-02, R-REV-01, and P12–P32 implementation evidence. A new
module needs a justified gap, not a continuation label.

Treating production launch evidence as R23 was rejected because credentials, owners, pilot results,
deployment proof, and backup/restore proof are operational inputs governed by existing production
readiness gates.

Treating every hardening task as a new roadmap module was rejected because most post-R22 work should
extend existing modules in place.

## Consequences

The roadmap sequence gate must verify that post-R22 roadmap governance exists.

R23 remains blocked until a later ADR explicitly authorizes it. That later ADR must be separate from
this governance ADR and must identify the actual module being added.

Implementation teams can continue with operational readiness, bug fixes, hardening, and ADR-backed
implementation phases without creating a new R-series module.

## Constitutional principles affected

This decision strengthens traceability, baseline integrity, non-duplication, controlled evolution,
and auditability.

## Migration and compatibility implications

No schema or runtime migration is required. Existing R2–R22 source specifications and P12–P32
implementation packages remain authoritative.

Future roadmap modules must extend the current repository architecture. They must not create a
second root-level Python source tree or duplicate existing platform capabilities.

## Security and privacy implications

New post-R22 proposals must explicitly state security impact, evidence requirements, and whether any
new credential, identity, authorization, retention, or audit boundary is introduced.

Production secrets, credentials, approval records, and pilot evidence must remain real external
evidence references. They must not be fabricated or embedded as raw secret values.

## Observability and operational implications

New roadmap modules must define required logs, metrics, traces, evidence records, release gates, and
operator runbooks before implementation begins.

Operational-only work remains governed by production readiness tooling and does not require a new
R-series document.

## Verification and rollback

Verification:

- `tools/roadmap_sequence_gate.py` must pass and include a post-R22 governance ADR check.
- Release gates must continue to include the roadmap sequence gate.
- Any later R23 source file must fail the sequence gate unless an accepted R23-authorizing ADR is
  added first.

Rollback:

- Supersede this ADR with a new ADR if the post-R22 governance model changes.
- Do not delete accepted ADR history.

## References

- [R-INDEX](../R-INDEX.md)
- [Architecture Baseline v1.0](../ARCHITECTURE-BASELINE-v1.0.md)
- [R-AUDIT-01](../R-AUDIT-01-current-state-repository-audit.md)
- [R-AUDIT-02](../R-AUDIT-02-r1-r22-alignment-matrix.md)
- [R-REV-01](../R-REV-01-corrected-r-series-baseline.md)
- [Production readiness remaining actions](../enterprise/production-readiness-remaining-actions.md)
