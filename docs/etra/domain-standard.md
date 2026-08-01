# Domain Module Standard

Each bounded context names commands, queries, events, aggregates, policies, workflows, knowledge
extractors, metrics, and public contracts that it actually owns. Domain objects are deterministic,
framework-neutral Python and enforce invariants at construction and transition boundaries. IDs and
hashes bind immutable lineage. Cross-context access uses explicit ports/contracts; imports cannot
bypass application orchestration. Policies deny by default and emit stable finding codes.

