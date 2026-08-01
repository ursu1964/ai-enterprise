# Workflow Standard

Every workflow declares identifier, semantic version, owner, states, permitted transitions, entry
and exit criteria, approval rules, timeouts, retry classification, recovery strategy, evidence, and
terminal states. State transitions are validated and persisted transactionally. Policy failures do
not retry, provider failures use bounded retry, output repair is bounded, and operator recovery is
auditable. No workflow skips approval gates or trusts a superseded input.

