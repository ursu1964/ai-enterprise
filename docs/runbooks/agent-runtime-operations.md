# Governed Agent Runtime Runbook

Owner: AI Runtime Operations.

## Startup and readiness

Confirm authority, skill/tool registry, model deployments, context sources, secrets provider, durable
queue, and audit store. Run one fake-provider structured-output probe; production model probes use
non-sensitive content. Keep execution disabled until all required dependencies are ready.

## Shutdown

Disable new session creation, drain or explicitly cancel bounded sessions, persist invocation and
validation lineage, release leases, verify no gateway execution remains, and record shutdown audit.

## Scaling

Scale workers from durable queue depth, provider limits, database saturation, and latency SLOs.
Preserve one runtime identity per crew member. Drain workers before scale-down and verify leases are
recovered rather than duplicated.

## Degraded operation

Unavailable providers may use only policy-approved classification-compatible fallback. Authority,
scope, tool, classification, or budget failures never retry. Invalid output gets at most one approved
repair. Otherwise abstain and escalate with evidence.

## Recovery and incident response

Cancel or time out orphan sessions, reconcile invocation counters and hashes, quarantine suspect
outputs, rotate exposed credentials, and verify no direct provider/tool bypass. Preserve context,
route, model, tool, validation, and escalation lineage.

## Backup and restoration

Back up runtime specifications, registries, sessions, invocations, manifests, validations, and audit
evidence under the platform retention policy. Restore into isolation, verify hashes and foreign-key
lineage, run gateway-denial and fake-provider probes, then reconcile unfinished sessions before use.

## Upgrade and rollback

Release prompt, skill, policy, tool, and model changes as immutable versions. Canary against fixed
evaluation suites, compare denial and validation metrics, then promote. Rollback selects the prior
approved versions; never mutate historical runtime specifications.
