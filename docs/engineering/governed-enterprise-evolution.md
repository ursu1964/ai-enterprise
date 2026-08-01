# Governed Enterprise Evolution

Enterprise evolution is specified under `specifications/evolution` and verified with
`python tools/evolution_verify.py --json`. Capability maturity follows an ordered lifecycle;
organizational maturity is the floor of evidence scores, never a self-reported label. Benchmarks
compare historical, current, and objective values and produce ranked opportunities—not decisions.

Roadmap proposals declare current state, dependencies, investment, expected outcomes, and success
measures. Refactoring requires independent human approval, bounded work packages, immutable lineage,
and a verified rollback. Scheduled reflection emits strategic recommendations into that roadmap and
cannot approve or implement them. The verifier emits canonical deterministic evidence and fails if
an agent grants itself authority, certifies its own maturity, skips lifecycle states, creates roadmap
cycles, removes rollback, or turns recommendations into autonomous actions.

