# Service Operations Runbook

Owner: Platform Operations. Review every release and quarterly.

## Startup

Validate signed artifact and typed configuration, confirm identity/KMS/database/backup/model-gateway
readiness, apply approved migrations, start service, then require readiness and smoke checks.

## Shutdown

Disable intake, drain durable jobs, persist checkpoints, verify no executing work, terminate, and
record the audit event. Never discard leases or workspaces silently.

## Scaling

Scale stateless API workers independently from queues. Verify database/queue saturation, lease
behavior, rate limits, and SLOs. Scale down only after draining.

## Recovery and incident response

Declare incident and correlation ID, preserve evidence, classify blast radius, revoke compromised
credentials, fail over only to verified providers, recover durable jobs, validate integrity, and
record timeline/decisions. Promote lessons only through governed knowledge review.

## Backup and restoration

Monitor encrypted backup completion and immutable retention. Restore into an isolated environment,
verify hashes/migration head/referential integrity, run acceptance checks, and record achieved RPO/RTO.

## Upgrade and rollback

Verify compatibility and backup, deploy progressively, watch SLO/security/audit signals, and stop on
gate failure. Roll back the service artifact using release metadata; execute database recovery only
from the approved migration/restore plan. Re-run readiness and integrity checks.

