# Governed Enterprise Intelligence

Enterprise intelligence is an evidence-bound advisory layer. It correlates operational,
architectural, engineering, organizational, training, and business evidence, but it cannot approve,
fund, schedule, or execute work. Governance determines what is permitted; operational systems execute
only approved work.

## Contracts

The versioned contracts in `specifications/intelligence/` define the evidence catalog, objective
optimizer, dashboard, cross-domain reasoning, strategic memory, cognitive policy, and strategic
intelligence layer. Every recommendation carries evidence, confidence, affected systems, inference
lineage, required investments, lifecycle state, and an independent human review. Counterevidence and
uncertainty remain visible.

The optimizer produces a deterministic candidate ranking from expected value, confidence, inverse
risk, capacity fit, and constraint fit. Candidate status is not approval. A shared capacity budget and
complete dependency attestation are mandatory; recommended portfolios are checked in aggregate.
Infeasible capacity, hidden schema fields, dangling or cyclic dependencies, and automatic funding or
execution fail conformance.

Strategic memory stores immutable, content-hashed, evidence-linked outcomes and approved decisions. Corrections
are versioned, contradictions explicit, expiry evaluated, and raw model reasoning excluded. The
dashboard authorizes and classifies evidence before aggregation and never presents a recommendation as
a decision.

## Verification

Run `python tools/intelligence_verify.py --json`. The deterministic gate validates strict JSON,
in-repository regular files, evidence hashes, cognitive thresholds, optimizer feasibility, required
views, cross-domain diversity, memory integrity, sequential recommendation lifecycle, reviewer
independence, advisory authority, and CI enforcement. Any finding blocks conformance.

The governing principle is: **cognition proposes considerations; it never possesses authority**.
