# Federation Operations Runbook

Owner: Federation Security and Compliance. Review after regulatory, provider, partner, or protocol changes.

## Partner onboarding

Verify legal entity and signed contract, exchange pinned identities through an independent channel,
run signed challenge and protocol conformance, negotiate schemas/policies, restrict capabilities and
delegation scope, enable replay cache and audit interoperability, then obtain local human approval.

## Regulatory and cloud activation

Classify jurisdiction, customer, workload, residency, and export obligations before placement. Generate
provider artifacts from the common specification, verify adapter evidence, rehearse failover without
sensitive data, and require human activation. Deny unclassified deployments or incompatible regions.

## External event incident

Disable issuer/key, reject and retain event hashes, preserve gateway decisions, inspect nonce/replay and
clock evidence, revoke delegated work, rotate federation keys, revalidate downstream candidate events,
and notify legal/security owners. External events never receive direct state-repair privileges.

## Provider outage and recovery

Freeze new external effects, assess jurisdiction-compatible fallback health, obtain activation approval,
restore from verified artifacts, reconcile contracts/events/audit evidence, and validate synchronization.
Fail back only after integrity, regulatory, and provider evidence gates pass.

## Offboarding and revocation

Revoke keys, contracts, delegation, capabilities, connectors, and graph relationships; stop exchanges;
apply retention/deletion obligations; preserve required audit evidence; and prove that transitive access
and remote mutation remain unavailable.

