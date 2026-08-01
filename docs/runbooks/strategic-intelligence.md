# Strategic Intelligence Runbook

Owner: Enterprise Strategy Governance. Review after evidence, scoring, model, policy, dashboard, or
recommendation lifecycle changes.

## Generate and review

Classify and authorize source evidence before use. Validate hashes, freshness, scope, and provenance;
record contradictory evidence. Generate the candidate ranking and cross-domain inference, then run
`python tools/intelligence_verify.py --json`. A human reviewer independent of the proposer evaluates
assumptions, uncertainty, prohibited domains, affected systems, shared portfolio capacity, declared
dependencies, and alternatives. Treat undeclared dependency or capacity fields as a conformance incident.

Advance recommendations only in order: generated, reviewed, accepted, planned, implemented, measured.
Each transition requires external governance evidence. Acceptance does not fund or execute work;
approved operational workflows retain those authorities.

## Abstention and incidents

Abstain when evidence or domain diversity is below policy, confidence is outside the approved range,
sources conflict, provenance is unavailable, authorization is uncertain, or the request falls in a
prohibited domain. Never infer missing approval.

On suspected poisoning, leakage, unexplained ranking change, self-review, lifecycle bypass, or attempted
execution: block the recommendation, preserve hashes and decision records, revoke affected evidence,
notify Strategy Governance and Security, compare the last conformant specification, and rerun the gate.
Restore service only after independent human approval and deterministic reproduction.

## Memory correction

Do not overwrite strategic memory. Add an evidence-linked correction that supersedes the prior item,
mark contradictions and temporal status explicitly, and retain the earlier hash for audit. Never store
raw prompts, hidden reasoning, credentials, or unrestricted personal data.
