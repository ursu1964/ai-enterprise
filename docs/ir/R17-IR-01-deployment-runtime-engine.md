# R17-IR-01 — AI-Enterprise Deployment and Runtime Engine Specification

Document ID: R17-IR-01  
Version: 1.0.0  
Status: IMPLEMENTATION READY  
Classification: Constitutional Platform Module  
Implementation Target: Future IR/P27 reconciliation  
Primary Dependencies: R2–R16-IR-01

## Purpose

R17-IR-01 defines the Deployment and Runtime Engine: the governed capability for
promoting verified artifacts and source revisions into controlled runtime
environments, operating them safely, observing health, rolling changes forward,
rolling changes back, and producing auditable deployment evidence.

Deployment is not just copying containers or running scripts. A deployment is a
policy-bound transition from an approved release candidate into an environment
with exact source revision, artifact provenance, configuration, secrets
references, infrastructure profile, health checks, rollout strategy, rollback
route, and evidence obligations.

R17 provides the runtime boundary between implementation/repository state and
operational service state.

## Architectural role

R17-IR-01 follows R16-IR-01. R16 governs repository integration; R17 governs the
deployment and runtime consequences of approved repository and artifact states.

Existing product-platform R17 remains the execution planning module. This IR
specification defines the constitutional deployment and runtime engine and does
not replace that R17 module.

R17-IR-01 SHALL reconcile with existing execution planning, Docker runtime,
release gates, production readiness, health endpoints, deployment blueprints,
runtime baseline, rollback metadata, and operations runbook components during
future implementation.

## Constitutional requirements

- Every deployment target has stable identity, environment class, owner,
  infrastructure profile, policy scope, and permitted workload classes.
- Every release candidate binds to exact source revision, artifact hashes,
  verification verdicts, policy decisions, configuration profile, and evidence.
- Deployment to production or production-like environments is deny-by-default
  until required gates, approvals, owners, credentials, rollback route, and
  evidence are validated.
- Runtime secrets are referenced through governed secret bindings and SHALL NOT
  be embedded in deployment records, logs, events, manifests, or artifacts.
- Rollout strategy, health checks, readiness checks, rollback trigger, and
  rollback procedure are required for authoritative deployment.
- Failed, cancelled, partial, rolled-back, degraded, superseded, and emergency
  deployments remain auditable.
- Runtime state SHALL be observable through health, readiness, metrics, logs,
  traces, deployment events, and incident signals.
- Deployment success SHALL NOT imply requirement satisfaction, verification pass,
  or production readiness unless the owning modules emit those verdicts.
- External infrastructure adapters require explicit configuration and preflight
  validation. The system SHALL NOT fabricate cloud, Kubernetes, registry, CDN,
  DNS, or production evidence.
- Runtime operations SHALL preserve tenant, project, credential, and
  environment isolation.

## Bounded context

Bounded Context: Release Candidate, Deployment, Runtime Environment, Rollout,
Rollback, and Operation

Owning Authority: Deployment Runtime Authority

Primary aggregate root:

- `DeploymentTarget`

Supporting aggregates:

- `RuntimeEnvironment`
- `InfrastructureProfile`
- `RuntimeConfigurationProfile`
- `RuntimeSecretBinding`
- `ReleaseCandidate`
- `DeploymentPlan`
- `DeploymentExecution`
- `DeploymentStep`
- `RolloutStrategy`
- `RuntimeHealthCheck`
- `RuntimeReadinessCheck`
- `RollbackPlan`
- `RollbackExecution`
- `RuntimeObservation`
- `RuntimeIncident`
- `RuntimeBaseline`
- `DeploymentEvidencePackage`
- `ExternalDeploymentAdapter`

## Canonical domain model

### DeploymentTarget

```yaml
DeploymentTarget:
  deployment_target_id: string
  organization_id: string
  project_id: string
  canonical_name: string
  environment_class: LOCAL | CI | DEVELOPMENT | TEST | STAGING | PRE_PRODUCTION | PRODUCTION | DISASTER_RECOVERY
  provider: LOCAL | DOCKER_COMPOSE | KUBERNETES | ECS | CLOUD_RUN | VM | SERVERLESS | CUSTOM
  infrastructure_profile_id: string
  configuration_profile_id: string
  permitted_workload_classes: [string]
  owner: ActorReference
  policy_scope: [string]
  lifecycle_status: DRAFT | VALIDATED | ACTIVE | SUSPENDED | DEGRADED | RETIRED
  created_at: datetime
  updated_at: datetime
  content_hash: string
```

### ReleaseCandidate

```yaml
ReleaseCandidate:
  release_candidate_id: string
  organization_id: string
  project_id: string
  version: string
  source_repository_connection_id: string
  source_commit_sha: string
  source_tree_sha: string
  artifact_references: [string]
  artifact_hashes: [string]
  verification_campaign_id: string | null
  verification_verdict: string | null
  policy_decision_references: [string]
  evidence_references: [EvidenceReference]
  status: DRAFT | VALIDATED | APPROVED | DEPLOYABLE | DEPLOYED | REJECTED | SUPERSEDED | REVOKED
  content_hash: string
```

### DeploymentPlan

```yaml
DeploymentPlan:
  deployment_plan_id: string
  release_candidate_id: string
  deployment_target_id: string
  rollout_strategy_id: string
  rollback_plan_id: string
  required_approval_references: [string]
  required_gate_references: [string]
  required_evidence_types: [string]
  deployment_steps: [string]
  preflight_checks: [string]
  post_deployment_checks: [string]
  status: DRAFT | VALIDATED | APPROVED | READY | SUPERSEDED | RETIRED
  content_hash: string
```

### DeploymentExecution

```yaml
DeploymentExecution:
  deployment_execution_id: string
  deployment_plan_id: string
  release_candidate_id: string
  deployment_target_id: string
  workflow_execution_id: string | null
  initiated_by: ActorReference
  source_commit_sha: string
  artifact_hashes: [string]
  configuration_hash: string
  secret_binding_references: [string]
  status: QUEUED | PREFLIGHTING | RUNNING | VERIFYING | SUCCEEDED | DEGRADED | FAILED | CANCELLED | ROLLING_BACK | ROLLED_BACK | PARTIAL
  started_at: datetime | null
  completed_at: datetime | null
  evidence_references: [EvidenceReference]
  correlation_id: string
```

### RuntimeEnvironment

```yaml
RuntimeEnvironment:
  runtime_environment_id: string
  deployment_target_id: string
  environment_class: string
  region: string | null
  isolation_boundary: string
  network_profile: string
  data_classification: string
  runtime_versions: object
  active_release_candidate_id: string | null
  health_status: UNKNOWN | HEALTHY | DEGRADED | UNHEALTHY | OFFLINE
  readiness_status: UNKNOWN | READY | NOT_READY | DEGRADED
  last_observed_at: datetime | null
```

### RolloutStrategy

```yaml
RolloutStrategy:
  rollout_strategy_id: string
  strategy_type: ALL_AT_ONCE | ROLLING | BLUE_GREEN | CANARY | SHADOW | FEATURE_FLAG | MANUAL
  batch_policy: object
  promotion_criteria: [string]
  halt_criteria: [string]
  rollback_triggers: [string]
  observation_window: string
  approval_required_between_stages: boolean
```

### RollbackPlan

```yaml
RollbackPlan:
  rollback_plan_id: string
  release_candidate_id: string
  deployment_target_id: string
  rollback_strategy: PREVIOUS_RELEASE | REDEPLOY_BASELINE | RESTORE_BACKUP | DISABLE_FLAG | TRAFFIC_SHIFT | CUSTOM
  target_release_candidate_id: string | null
  maximum_recovery_minutes: integer
  data_compatibility_notes: string
  required_backups: [string]
  verification_steps: [string]
  tested_evidence_reference: string | null
  status: DRAFT | VALIDATED | APPROVED | TESTED | EXPIRED | SUPERSEDED
```

### RuntimeObservation

```yaml
RuntimeObservation:
  runtime_observation_id: string
  deployment_execution_id: string | null
  deployment_target_id: string
  observation_type: HEALTH | READINESS | METRIC | LOG | TRACE | ALERT | INCIDENT | USER_SIGNAL | SYNTHETIC_CHECK
  observed_status: string
  signal_reference: string
  severity: LOW | MEDIUM | HIGH | CRITICAL
  observed_at: datetime
  evidence_reference: string | null
```

## Lifecycle and invariants

Release candidate lifecycle:

```text
DRAFT → VALIDATED → APPROVED → DEPLOYABLE → DEPLOYED
DRAFT → REJECTED
APPROVED → SUPERSEDED
DEPLOYED → REVOKED
```

Deployment execution lifecycle:

```text
QUEUED → PREFLIGHTING → RUNNING → VERIFYING → SUCCEEDED
QUEUED → PREFLIGHTING → FAILED
RUNNING → DEGRADED
RUNNING → FAILED
RUNNING → CANCELLED
FAILED → ROLLING_BACK → ROLLED_BACK
DEGRADED → ROLLING_BACK → ROLLED_BACK
RUNNING → PARTIAL
```

Core invariants:

- Every deployment execution references one approved deployment plan and one
  deployable release candidate.
- Every production deployment references validated owners, approvals, rollback
  plan, runtime configuration, secret bindings, and evidence plan.
- Every runtime deployment binds to exact source commit and artifact hashes.
- Every environment has explicit isolation, network, data-classification, and
  policy context.
- Every rollback preserves the failed or superseded deployment history.
- Every deployment result records health/readiness evidence or an explicit
  evidence gap.
- Every external adapter operation records preflight result and credential
  reference status without exposing secrets.
- Every deployment status transition is auditable.

## Commands

R17-IR-01 SHALL define at least:

- `RegisterDeploymentTarget`
- `ValidateDeploymentTarget`
- `ActivateDeploymentTarget`
- `SuspendDeploymentTarget`
- `RetireDeploymentTarget`
- `CreateInfrastructureProfile`
- `CreateRuntimeConfigurationProfile`
- `BindRuntimeSecret`
- `PreflightDeploymentAdapter`
- `CreateReleaseCandidate`
- `ValidateReleaseCandidate`
- `ApproveReleaseCandidate`
- `CreateDeploymentPlan`
- `ValidateDeploymentPlan`
- `ApproveDeploymentPlan`
- `StartDeploymentExecution`
- `RecordDeploymentStepResult`
- `RecordRuntimeHealthCheck`
- `RecordRuntimeReadinessCheck`
- `CompleteDeploymentExecution`
- `FailDeploymentExecution`
- `MarkDeploymentDegraded`
- `CancelDeploymentExecution`
- `StartRollbackExecution`
- `CompleteRollbackExecution`
- `RecordRuntimeObservation`
- `CreateRuntimeIncident`
- `CaptureRuntimeBaseline`
- `CreateDeploymentEvidencePackage`

Every mutating command SHALL include authenticated actor, organization, project,
target environment, expected aggregate revision, idempotency key, policy
context, reason, and correlation identifier.

## Queries

R17-IR-01 SHALL provide:

- `GetDeploymentTarget`
- `GetRuntimeEnvironment`
- `GetReleaseCandidate`
- `GetDeploymentPlan`
- `GetDeploymentExecution`
- `GetRollbackPlan`
- `GetRollbackExecution`
- `GetRuntimeObservation`
- `ListDeploymentTargets`
- `ListReleaseCandidates`
- `ListActiveDeployments`
- `ListFailedDeployments`
- `ListDegradedRuntimeEnvironments`
- `ListDeploymentsMissingEvidence`
- `TraceDeploymentToRepository`
- `TraceDeploymentToArtifacts`
- `TraceDeploymentToVerification`
- `TraceDeploymentToEvidence`
- `CompareRuntimeBaselines`
- `FindExpiredRollbackPlans`
- `FindProductionReadinessBlockers`

Queries SHALL be policy-filtered and SHALL redact secrets, private endpoint
details, infrastructure credentials, restricted runtime data, and sensitive logs.

## Events

R17-IR-01 SHALL publish immutable domain events including:

- `DeploymentTargetRegistered`
- `DeploymentTargetValidated`
- `DeploymentTargetActivated`
- `RuntimeSecretBound`
- `DeploymentAdapterPreflightPassed`
- `DeploymentAdapterPreflightFailed`
- `ReleaseCandidateCreated`
- `ReleaseCandidateValidated`
- `ReleaseCandidateApproved`
- `DeploymentPlanCreated`
- `DeploymentPlanApproved`
- `DeploymentExecutionStarted`
- `DeploymentStepCompleted`
- `DeploymentStepFailed`
- `RuntimeHealthCheckRecorded`
- `RuntimeReadinessCheckRecorded`
- `DeploymentExecutionSucceeded`
- `DeploymentExecutionFailed`
- `DeploymentMarkedDegraded`
- `DeploymentExecutionCancelled`
- `RollbackExecutionStarted`
- `RollbackExecutionCompleted`
- `RollbackExecutionFailed`
- `RuntimeObservationRecorded`
- `RuntimeIncidentCreated`
- `RuntimeBaselineCaptured`
- `DeploymentEvidencePackageCreated`
- `ProductionReadinessBlocked`
- `ProductionReadinessValidated`

Events SHALL include organization, project, deployment target, environment,
release candidate, source revision, artifact references, actor, policy,
evidence, correlation, causation, timestamp, and provider references.

## Security and governance

R17-IR-01 SHALL enforce:

- deny-by-default deployment to protected environments;
- role-, attribute-, and policy-based deployment authorization;
- separation of duties for production approval;
- tenant, project, environment, and network isolation;
- secret-reference-only runtime configuration;
- preflight validation for external cloud, container, registry, DNS, CDN, and
  orchestration adapters;
- immutable deployment and rollback evidence;
- deployment artifact integrity and provenance checks;
- production owner and run-artifact validation;
- rollback and recovery-route validation before production release;
- sensitive log and event redaction;
- controlled emergency deployment and rollback paths;
- runtime operation audit records.

AI may prepare deployment plans, classify operational signals, summarize
release evidence, recommend rollback, and identify missing readiness inputs.

AI SHALL NOT fabricate production evidence, approve its own production
deployment, obtain raw secrets, disable health gates, suppress incidents, or
mark production ready without required operational references.

## Cross-module contracts

R17-IR-01 integrates with:

- R5 for requirement release scope.
- R6 for architecture deployment constraints.
- R7 for planned release work.
- R8 for generated deployment artifacts.
- R9 for implementation result handoff.
- R10 for verification and validation gates.
- R11 for release and deployment evidence packages.
- R12 for deployment, exception, secret, and environment policies.
- R13 for AI-assisted deployment orchestration.
- R14 for agent authority in deployment workflows.
- R15 for workflow execution of release and rollout processes.
- R16 for source repository, commit, tag, release, and package provenance.
- R18 for runtime telemetry, metrics, traces, alerts, and incident observations.
- R19 for identity, secrets, and access enforcement.
- R20 for operational knowledge and lessons learned.
- R21 for platform operations and administration.
- R22 for constitutional release/evolution controls.

R17 SHALL NOT directly approve requirement satisfaction, fabricate verification
results, or bypass production readiness evidence.

## Repository implementation mapping

Existing repository capabilities relevant to R17-IR-01 include:

- `apps/api/src/ai_enterprise/application/r17_execution_planner_runtime.py`
- `apps/api/src/ai_enterprise/infrastructure/execution/docker_runtime.py`
- `apps/api/src/ai_enterprise/main.py`
- `apps/api/src/ai_enterprise/application/execution_workflow.py`
- `apps/api/src/ai_enterprise/domain/evolution/`
- `tools/docker_smoke.py`
- `tools/deployment_blueprint.py`
- `tools/production_readiness.py`
- `tools/production_evidence_plan.py`
- `tools/runtime_baseline.py`
- `tools/release_gate_evidence.py`
- `tools/release_artifact.py`
- `tools/release_evidence_bundle.py`
- `schemas/production-readiness/`
- `schemas/release-artifacts/`
- `deploy/`
- `runtime/`
- `docs/reference-architecture/09-runtime/`
- `docs/reference-architecture/11-operations/`

Future implementation SHALL inventory these components before adding new
runtime code. The existing R17 execution planner remains a product-platform
module and shall be reconciled as a planning input for deployment execution
where appropriate instead of replacing it.

No new root-level Python source tree SHALL be created. Application code remains
under `apps/api/src`.

## Verification strategy

Unit tests SHALL cover:

- deployment target validation;
- release candidate lifecycle;
- deployment plan approval;
- environment class restrictions;
- secret binding redaction;
- rollout strategy rules;
- rollback-plan requirements;
- production readiness blockers;
- deployment status transitions;
- runtime observation classification.

Contract tests SHALL cover:

- R10 verification gate integration;
- R11 deployment evidence packaging;
- R12 deployment policy decisions;
- R15 workflow execution;
- R16 source/artifact provenance;
- R18 telemetry contract;
- command, query, event, and error schemas.

Integration tests SHALL cover:

- local Docker/Compose deployment preflight;
- release candidate to deployment execution;
- health and readiness capture;
- failed deployment and rollback;
- production readiness validation with real evidence references;
- external adapter preflight without credentials;
- optional Kubernetes/cloud tests gated by real configuration.

Security tests SHALL cover:

- unauthorized production deployment;
- raw secret leakage;
- missing rollback route;
- unverified artifact deployment;
- forged deployment evidence;
- cross-project runtime access;
- suppressed health failure;
- agent self-approval.

Resilience tests SHALL cover:

- deployment adapter outage;
- health endpoint failure;
- partial rollout;
- rollback failure;
- evidence-store outage;
- policy-service outage;
- stale artifact or source revision;
- runtime baseline comparison after recovery.

## Acceptance criteria

R17-IR-01 is implementation-ready when:

- Deployment targets, environments, configuration profiles, secret bindings,
  release candidates, deployment plans, executions, rollout strategies, rollback
  plans, observations, incidents, and evidence packages have explicit schemas.
- Production deployment gates require owners, approvals, verification,
  rollback, configuration, secret references, and evidence.
- Runtime secrets are represented only by governed references.
- Deployment execution binds to exact source revision and artifact hashes.
- Health, readiness, observation, degraded, failed, and rollback states are
  distinct and auditable.
- External infrastructure adapters fail closed without real configuration.
- Local deterministic runtime checks remain testable without production
  credentials.
- Commands, queries, events, security rules, repository mapping, and verification
  strategy are defined.
- The document explicitly preserves the existing R17 execution planner module
  and does not create a second implementation architecture.

## Readiness verdict

| Gate | Status |
|---|---|
| Semantic completeness | PASS |
| Contract completeness | PASS |
| Governance completeness | PASS |
| Operational completeness | PASS |
| Repository compatibility | CONDITIONAL — requires IR/P27 reconciliation |
| Verification completeness | PASS |
| Cross-R consistency | PASS |

Overall status: IMPLEMENTATION READY.

R17-IR-01 is ready for Architecture Baseline v1.0 inclusion. Future
implementation should reconcile existing execution planning, Docker/runtime,
release-gate, production-readiness, deployment blueprint, runtime baseline, and
operations components into this IR contract without duplicating deployment
authority.
