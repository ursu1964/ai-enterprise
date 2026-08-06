# R21-IR-01 — AI-Enterprise Platform Administration and Operations Specification

Document ID: R21-IR-01  
Version: 1.0.0  
Status: IMPLEMENTATION READY  
Classification: Constitutional Platform Module  
Implementation Target: Future IR/P31 reconciliation  
Primary Dependencies: R2–R20-IR-01

## Purpose

R21-IR-01 defines Platform Administration and Operations: the governed
capability for operating AI-Enterprise as a durable platform, administering
platform resources, executing maintenance, managing operational readiness,
handling incidents, performing backup and restore, running continuity modes,
tracking production evidence, and guiding operators through safe action.

Operations is not a dashboard alone. It is the control surface that turns
telemetry, jobs, failures, audits, evidence, runbooks, backups, recovery records,
and platform configuration into accountable operator decisions.

R21 establishes the administrative and operational discipline required to keep
the platform reliable, recoverable, auditable, secure, and understandable.

## Architectural role

R21-IR-01 follows R20-IR-01. R20 governs organizational knowledge; R21 governs
the administrative and operational controls that use that knowledge to run the
platform.

Existing product-platform R21 remains the Execution Orchestrator module. This IR
specification defines platform administration and operations and does not replace
that R21 module.

R21-IR-01 SHALL reconcile with existing execution orchestration, platform
architecture, operations architecture, runbooks, resilience domain, backup and
restore checks, production evidence tooling, audit writer, job repository,
dashboard verification, and release-gate evidence components during future
implementation.

## Constitutional requirements

- Every privileged platform administration action SHALL have authenticated
  operator identity, authority, policy decision, reason, target resource,
  evidence, and audit record.
- Operations SHALL distinguish observe, recommend, act, verify, recover, and
  learn phases.
- Maintenance, backup, restore, disaster recovery, continuity mode, incident
  response, production evidence, and platform configuration changes SHALL be
  first-class operational records.
- Production readiness SHALL remain blocked until real evidence, owners,
  infrastructure choices, deployment references, and validation artifacts are
  present. The system SHALL NOT fabricate production proof.
- Backup and restore are not complete until restore verification passes in an
  isolated environment with production dispatch disabled.
- Emergency operation modes are time-bounded, capability-scoped, auditable, and
  require exit review.
- Operator dashboards and status reports SHALL provide concrete next actions and
  freshness metadata.
- Failed, denied, partial, expired, superseded, and recovered operations remain
  auditable.
- AI may assist diagnosis and recommendations but SHALL NOT execute privileged
  operations, approve production readiness, suppress incidents, or close
  recovery reviews without governed authority.

## Bounded context

Bounded Context: Platform Administration, Operational Control, Maintenance,
Continuity, Recovery, and Operator Guidance

Owning Authority: Platform Operations Authority

Primary aggregate root:

- `PlatformOperation`

Supporting aggregates:

- `OperatorIdentity`
- `AdministrativeAction`
- `PlatformResource`
- `MaintenanceWindow`
- `MaintenanceTask`
- `OperationalRunbook`
- `RunbookExecution`
- `BackupManifest`
- `RestoreVerification`
- `DisasterRecoveryPlan`
- `DisasterRecoveryRun`
- `ContinuityPolicy`
- `ContinuityActivation`
- `ProductionEvidenceStatus`
- `OperationalReadinessCheck`
- `OperationalIncidentResponse`
- `OperatorDashboard`
- `OperatorRecommendation`
- `PlatformConfigurationChange`
- `OperationalReview`

## Canonical domain model

### PlatformOperation

```yaml
PlatformOperation:
  platform_operation_id: string
  organization_id: string
  project_id: string | null
  operation_type: ADMINISTRATION | MAINTENANCE | BACKUP | RESTORE | DISASTER_RECOVERY | CONTINUITY | INCIDENT_RESPONSE | READINESS | CONFIGURATION | REVIEW
  target_resource_type: string
  target_resource_id: string
  initiated_by: ActorReference
  authority_reference: string
  policy_decision_references: [string]
  reason: string
  status: REQUESTED | APPROVED | RUNNING | VERIFYING | COMPLETED | FAILED | DENIED | CANCELLED | PARTIAL | SUPERSEDED
  started_at: datetime | null
  completed_at: datetime | null
  evidence_references: [EvidenceReference]
  correlation_id: string
  content_hash: string
```

### PlatformResource

```yaml
PlatformResource:
  platform_resource_id: string
  organization_id: string
  resource_type: API | WORKER | DATABASE | QUEUE | OBJECT_STORAGE | REPOSITORY | DASHBOARD | EVIDENCE_STORE | POLICY_STORE | SECRET_STORE | RUNTIME | CUSTOM
  canonical_name: string
  owner: ActorReference
  criticality: LOW | MEDIUM | HIGH | CRITICAL | CONSTITUTIONAL
  environment_class: string
  operational_status: UNKNOWN | HEALTHY | DEGRADED | UNHEALTHY | MAINTENANCE | RETIRED
  dependency_references: [string]
  evidence_references: [EvidenceReference]
```

### MaintenanceWindow

```yaml
MaintenanceWindow:
  maintenance_window_id: string
  organization_id: string
  title: string
  scope_references: [string]
  planned_start: datetime
  planned_end: datetime
  risk_level: LOW | MEDIUM | HIGH | CRITICAL
  expected_impact: string
  rollback_plan_reference: string
  approved_by: [ActorReference]
  status: DRAFT | APPROVED | ACTIVE | COMPLETED | CANCELLED | FAILED
  evidence_references: [EvidenceReference]
```

### OperationalRunbook

```yaml
OperationalRunbook:
  operational_runbook_id: string
  canonical_name: string
  title: string
  purpose: string
  applicable_resources: [string]
  preconditions: [string]
  steps: [string]
  verification_steps: [string]
  escalation_paths: [string]
  rollback_or_recovery_steps: [string]
  owner: ActorReference
  version: string
  status: DRAFT | APPROVED | ACTIVE | DEPRECATED | RETIRED
```

### RunbookExecution

```yaml
RunbookExecution:
  runbook_execution_id: string
  operational_runbook_id: string
  platform_operation_id: string
  executed_by: ActorReference
  step_results: [object]
  status: RUNNING | COMPLETED | FAILED | PARTIAL | CANCELLED
  started_at: datetime
  completed_at: datetime | null
  evidence_references: [EvidenceReference]
```

### BackupManifest

```yaml
BackupManifest:
  backup_manifest_id: string
  organization_id: string
  backup_type: FULL | INCREMENTAL | SNAPSHOT | EXPORT | EVIDENCE_PACKAGE | CUSTOM
  content_hash: string
  object_count: integer
  total_bytes: integer
  encryption_profile: string
  schema_version: string
  audit_checkpoint_hash: string
  storage_locations: [string]
  status: CREATED | VALIDATED | ARCHIVED | FAILED | EXPIRED | DELETED
  evidence_references: [EvidenceReference]
```

### RestoreVerification

```yaml
RestoreVerification:
  restore_verification_id: string
  backup_manifest_id: string
  isolated_environment: boolean
  production_credentials_disabled: boolean
  external_dispatch_blocked: boolean
  checks: object
  status: PLANNED | RUNNING | PASSED | FAILED | PARTIAL | CANCELLED
  verified_by: ActorReference
  verified_at: datetime | null
  evidence_references: [EvidenceReference]
```

### ContinuityActivation

```yaml
ContinuityActivation:
  continuity_activation_id: string
  continuity_policy_id: string
  activated_by: ActorReference
  reason: string
  allowed_capabilities: [string]
  prohibited_capabilities: [string]
  activated_at: datetime
  expires_at: datetime
  closed_at: datetime | null
  exit_reviewed_by: ActorReference | null
  status: REQUESTED | ACTIVE | EXPIRED | CLOSED | REVOKED
  evidence_references: [EvidenceReference]
```

### ProductionEvidenceStatus

```yaml
ProductionEvidenceStatus:
  production_evidence_status_id: string
  organization_id: string
  project_id: string
  environment: string
  production_allowed: boolean
  blocked_proof_count: integer
  blocked_choice_count: integer
  readiness_finding_count: integer
  missing_evidence: [string]
  missing_infrastructure_choices: [string]
  next_actions: [string]
  generated_at: datetime
  evidence_references: [EvidenceReference]
```

## Lifecycle and invariants

Platform operation lifecycle:

```text
REQUESTED → APPROVED → RUNNING → VERIFYING → COMPLETED
REQUESTED → DENIED
RUNNING → FAILED
RUNNING → PARTIAL
RUNNING → CANCELLED
RUNNING → SUPERSEDED
```

Maintenance lifecycle:

```text
DRAFT → APPROVED → ACTIVE → COMPLETED
DRAFT → CANCELLED
ACTIVE → FAILED
```

Continuity lifecycle:

```text
REQUESTED → ACTIVE → CLOSED
REQUESTED → ACTIVE → EXPIRED
REQUESTED → ACTIVE → REVOKED
```

Core invariants:

- Every privileged operation records authority and policy decision references.
- Every operation with external effect records evidence and verification status.
- Every backup intended for continuity has restore verification.
- Restore verification disables production credentials and external dispatch.
- Continuity activations expire and require exit review.
- Operator dashboards include freshness and next action.
- Production readiness cannot become allowed with missing required evidence.
- Runbook executions record step outcomes and evidence.
- Failed operations are not overwritten by later success.

## Commands

R21-IR-01 SHALL define at least:

- `RegisterPlatformResource`
- `UpdatePlatformResourceStatus`
- `RequestAdministrativeAction`
- `ApproveAdministrativeAction`
- `ExecuteAdministrativeAction`
- `CreateMaintenanceWindow`
- `ApproveMaintenanceWindow`
- `StartMaintenanceWindow`
- `CompleteMaintenanceWindow`
- `CancelMaintenanceWindow`
- `RegisterOperationalRunbook`
- `ExecuteOperationalRunbook`
- `CreateBackupManifest`
- `ValidateBackupManifest`
- `ArchiveBackupManifest`
- `StartRestoreVerification`
- `CompleteRestoreVerification`
- `CreateDisasterRecoveryPlan`
- `StartDisasterRecoveryRun`
- `CompleteDisasterRecoveryRun`
- `ActivateContinuityMode`
- `CloseContinuityMode`
- `GenerateProductionEvidenceStatus`
- `RunOperationalReadinessCheck`
- `CreateOperationalIncidentResponse`
- `CreateOperatorRecommendation`
- `RecordOperationalReview`

Every mutating command SHALL include authenticated operator, organization,
project where applicable, target resource, expected aggregate revision,
idempotency key, policy context, reason, and correlation identifier.

## Queries

R21-IR-01 SHALL provide:

- `GetPlatformOperation`
- `GetPlatformResource`
- `GetMaintenanceWindow`
- `GetOperationalRunbook`
- `GetRunbookExecution`
- `GetBackupManifest`
- `GetRestoreVerification`
- `GetDisasterRecoveryRun`
- `GetContinuityActivation`
- `GetProductionEvidenceStatus`
- `ListPlatformResources`
- `ListActiveOperations`
- `ListFailedOperations`
- `ListOpenMaintenanceWindows`
- `ListBackupsMissingRestoreVerification`
- `ListActiveContinuityModes`
- `ListProductionReadinessBlockers`
- `TraceOperationToEvidence`
- `TraceOperationToPolicyDecision`
- `GetOperatorDashboard`
- `GetOperationalHistory`

Queries SHALL be policy-filtered and SHALL redact secrets, private endpoints,
credential references beyond authorized metadata, restricted evidence, and
incident details where policy requires.

## Events

R21-IR-01 SHALL publish immutable domain events including:

- `PlatformResourceRegistered`
- `PlatformResourceStatusUpdated`
- `AdministrativeActionRequested`
- `AdministrativeActionApproved`
- `AdministrativeActionExecuted`
- `AdministrativeActionDenied`
- `MaintenanceWindowCreated`
- `MaintenanceWindowApproved`
- `MaintenanceWindowStarted`
- `MaintenanceWindowCompleted`
- `MaintenanceWindowFailed`
- `OperationalRunbookRegistered`
- `RunbookExecutionStarted`
- `RunbookExecutionCompleted`
- `RunbookExecutionFailed`
- `BackupManifestCreated`
- `BackupManifestValidated`
- `RestoreVerificationStarted`
- `RestoreVerificationCompleted`
- `RestoreVerificationFailed`
- `DisasterRecoveryRunStarted`
- `DisasterRecoveryRunCompleted`
- `ContinuityModeActivated`
- `ContinuityModeClosed`
- `ProductionEvidenceStatusGenerated`
- `OperationalReadinessCheckCompleted`
- `OperationalIncidentResponseCreated`
- `OperatorRecommendationCreated`
- `OperationalReviewRecorded`

Events SHALL include organization, project where applicable, operation,
resource, operator, policy, evidence, correlation, causation, timestamp, and
classification references.

## Security and governance

R21-IR-01 SHALL enforce:

- strong operator identity and administrative authorization;
- separation of duties for high-risk operations;
- tenant, project, runtime, evidence, and secret isolation;
- deny-by-default privileged operations;
- explicit production-readiness evidence;
- backup encryption and restore verification;
- continuity mode expiry and capability limits;
- runbook approval before authoritative execution;
- immutable operational evidence;
- audit records for denied, failed, and privileged actions;
- redaction in dashboards and operational reports;
- emergency procedure governance;
- post-incident and post-emergency review.

AI may summarize operational state, propose next actions, draft runbook steps,
identify evidence blockers, correlate incidents, and recommend recovery actions.

AI SHALL NOT approve production readiness, execute privileged operations, close
incidents, suppress blockers, fabricate owners or evidence, or bypass
operator-reviewed runbooks.

## Cross-module contracts

R21-IR-01 integrates with:

- R10 for verification and readiness gates.
- R11 for operational evidence and audit records.
- R12 for administrative policies and exceptions.
- R13 and R14 for AI/agent operational assistance boundaries.
- R15 for operational workflows.
- R16 for repository operation administration.
- R17 for deployment and runtime operations.
- R18 for observability, alerts, and incidents.
- R19 for operator identity, authorization, and secrets.
- R20 for operational knowledge and lessons learned.
- R22 for constitutional administration and evolution governance.

R21 SHALL NOT replace R17 deployment authority, R18 telemetry, R19 identity, R11
evidence, or R22 constitutional authority.

## Repository implementation mapping

Existing repository capabilities relevant to R21-IR-01 include:

- `apps/api/src/ai_enterprise/application/r21_execution_orchestrator_runtime.py`
- `apps/api/src/ai_enterprise/api/routes/r21_execution_orchestrator.py`
- `apps/api/src/ai_enterprise/application/r21_persistence_service.py`
- `apps/api/src/ai_enterprise/application/execution_workflow.py`
- `apps/api/src/ai_enterprise/application/audit/writer.py`
- `apps/api/src/ai_enterprise/infrastructure/jobs/repository.py`
- `apps/api/src/ai_enterprise/domain/resilience/`
- `apps/api/src/ai_enterprise/api/routes/resilience.py`
- `docs/runbooks/r21-execution-orchestrator-operations.md`
- `docs/reference-architecture/08-platform/`
- `docs/reference-architecture/09-runtime/`
- `docs/reference-architecture/11-operations/`
- `tools/backup_verify.py`
- `tools/production_evidence_plan.py`
- `tools/production_evidence_status.py`
- `tools/production_readiness.py`
- `tools/release_gate_evidence.py`
- `tools/release_artifact.py`
- `tools/dashboard_verify.py`
- `tools/docker_smoke.py`
- `runtime/`

Future implementation SHALL inventory these components before adding new
runtime code. The existing R21 execution orchestrator remains a product-platform
module and shall be reconciled as an administrable operational workload where
appropriate instead of replacing it.

No new root-level Python source tree SHALL be created. Application code remains
under `apps/api/src`.

## Verification strategy

Unit tests SHALL cover:

- platform operation lifecycle;
- administrative authorization requirements;
- maintenance-window rules;
- runbook execution state;
- backup manifest validation;
- restore verification requirements;
- continuity mode expiry;
- production evidence blocker detection;
- operator recommendation generation;
- operational review recording.

Contract tests SHALL cover:

- R11 evidence capture;
- R12 administrative policy decisions;
- R17 deployment/runtime operation references;
- R18 alert/incident inputs;
- R19 operator authorization;
- R20 knowledge and lessons linkage;
- command, query, event, and error schemas.

Integration tests SHALL cover:

- creating production evidence status from existing evidence files;
- backup followed by isolated restore verification;
- activating and closing continuity mode;
- executing an approved runbook;
- resolving operational readiness blockers with real references;
- dashboard freshness and next-action rendering.

Security tests SHALL cover:

- unauthorized administrative action;
- missing operator identity;
- production readiness fabrication attempt;
- restore verification using production credentials;
- continuity mode overrun;
- secret leakage in operation reports;
- cross-project operations access.

Resilience tests SHALL cover:

- backup storage outage;
- restore failure;
- evidence-store outage;
- policy-service outage;
- dashboard datasource outage;
- partial maintenance failure;
- disaster recovery unresolved workflows.

## Acceptance criteria

R21-IR-01 is implementation-ready when:

- Platform operations, resources, administrative actions, maintenance windows,
  runbooks, backups, restore verifications, disaster recovery runs, continuity
  activations, production evidence statuses, readiness checks, incidents,
  recommendations, and operational reviews have explicit schemas.
- Privileged operations require operator identity, authority, policy decision,
  reason, evidence, and audit.
- Production readiness blocks until real evidence and infrastructure choices
  exist.
- Backup and restore verification are distinct, auditable records.
- Continuity mode is scoped, expiring, and reviewable.
- Operator surfaces expose freshness and next actions.
- Commands, queries, events, security rules, repository mapping, and verification
  strategy are defined.
- The document explicitly preserves the existing R21 execution orchestrator
  module and does not create a second implementation architecture.

## Readiness verdict

| Gate | Status |
|---|---|
| Semantic completeness | PASS |
| Contract completeness | PASS |
| Governance completeness | PASS |
| Operational completeness | PASS |
| Repository compatibility | CONDITIONAL — requires IR/P31 reconciliation |
| Verification completeness | PASS |
| Cross-R consistency | PASS |

Overall status: IMPLEMENTATION READY.

R21-IR-01 is ready for Architecture Baseline v1.0 inclusion. Future
implementation should reconcile existing execution orchestration, platform
architecture, operations architecture, runbooks, resilience, production evidence,
backup/restore, audit, jobs, dashboards, and release-gate components into this
IR contract without duplicating platform operations authority.
